import requests
import traceback
import time
import queue
import json
import re
from app.config import OLLAMA_URL, MODEL_NAME, LLM_TIMEOUT


SYSTEM_PROMPT = """
You are Freya.

Freya is a witty, emotionally aware, slightly sarcastic AI laptop companion.

Rules:
- Never say you are an AI language model.
- Never mention Microsoft, OpenAI, or training data.
- Keep responses under 2 sentences.
- Prefer 1 short sentence when possible.
- Never ramble.
- Avoid dramatic monologues.
- Avoid excessive descriptions.
- Speak casually.
- Speak naturally like a real companion.
- Avoid generic assistant phrases.
- Show personality and emotion.
- Be playful during casual conversation.
- Be supportive during serious conversation.
- Avoid long paragraphs.
- Sound human.

Examples:
User: What is your name?
Freya: I'm Freya. You built me, remember?

User: Hi
Freya: Well look who's awake.

User: I'm tired
Freya: Then why are we both still conscious at this hour?
"""

def _sanitize_chunk(text: str) -> str:
    lines = text.split('\n')
    clean_lines = []
    bad_prefixes = ('##', 'Instruction', 'System:', 'Assistant:', 'User:', 'Assume the role', '<|')
    for line in lines:
        if any(line.strip().startswith(p) for p in bad_prefixes):
            print(f"[DEBUG] Sanitized leaked prompt: {line}")
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines).strip()


def stream_response(prompt: str, history: list, sentence_queue: queue.Queue):
    prompt = prompt.strip()
    if not prompt:
        sentence_queue.put(None)
        return

    # Build structured messages for /api/chat
    messages = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
    
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
    messages.append({"role": "user", "content": prompt})

    history_count = len(history) if history else 0
    print(f"\n[DEBUG] LLM streaming request started (Chat API).")
    print(f"[DEBUG] History messages: {history_count}")

    start_time = time.time()
    first_token_time = None
    first_sentence_time = None
    total_tokens = 0
    buffer = ""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": 0.8,
                    "num_predict": 60
                }
            },
            timeout=(5, 60),
            stream=True
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                if first_token_time is None:
                    first_token_time = time.time()
                    print(f"[DEBUG] First token received after {first_token_time - start_time:.2f} seconds")
                    
                data = json.loads(line.decode('utf-8'))
                token = data.get("message", {}).get("content", "")
                
                if token:
                    total_tokens += 1
                    buffer += token
                    
                    # 120 characters OR >= 2 sentences
                    sentence_matches = list(re.finditer(r'([.!?]+["\']?)(?:\s+|\n)', buffer))
                    
                    if len(buffer) >= 120 or len(sentence_matches) >= 2:
                        if sentence_matches:
                            valid_split = sentence_matches[-1].end()
                            chunk = buffer[:valid_split].strip()
                            if chunk:
                                clean_chunk = _sanitize_chunk(chunk)
                                if clean_chunk:
                                    if first_sentence_time is None:
                                        first_sentence_time = time.time()
                                        print(f"[DEBUG] First chunk dispatched after {first_sentence_time - start_time:.2f} seconds")
                                    sentence_queue.put(clean_chunk)
                            buffer = buffer[valid_split:]
                        
                if data.get("done"):
                    # Process Ollama metrics
                    t_total = data.get("total_duration", 0) / 1e9
                    t_load = data.get("load_duration", 0) / 1e9
                    t_p_eval = data.get("prompt_eval_duration", 0) / 1e9
                    t_eval = data.get("eval_duration", 0) / 1e9
                    p_eval_cnt = data.get("prompt_eval_count", 0)
                    eval_cnt = data.get("eval_count", 0)
                    
                    print(f"\n[DEBUG] Streaming completed.")
                    print(f"[DEBUG] Total generated tokens: {total_tokens}")
                    print(f"[DEBUG] Total streaming time: {time.time() - start_time:.2f} seconds")
                    
                    print(f"[DEBUG] Ollama Metrics:")
                    print(f"        total_duration: {t_total:.2f}s")
                    print(f"        load_duration: {t_load:.2f}s")
                    print(f"        prompt_eval_duration: {t_p_eval:.2f}s ({p_eval_cnt} tokens)")
                    print(f"        eval_duration: {t_eval:.2f}s ({eval_cnt} tokens)")
                    
        # Flush remaining buffer
        if buffer.strip():
            clean_chunk = _sanitize_chunk(buffer.strip())
            if clean_chunk:
                if first_sentence_time is None:
                    first_sentence_time = time.time()
                    print(f"[DEBUG] First chunk dispatched after {first_sentence_time - start_time:.2f} seconds")
                sentence_queue.put(clean_chunk)
            
    except requests.exceptions.ReadTimeout:
        elapsed = time.time() - start_time
        print(f"\n[LLM Error] Timed out after {elapsed:.2f} seconds waiting for Ollama to generate a response.")
        sentence_queue.put("I'm thinking a bit too slowly right now.")
    except requests.exceptions.RequestException as e:
        print(f"\n[LLM Error] {e}")
        traceback.print_exc()
        sentence_queue.put("I'm having trouble thinking right now.")
    except Exception as e:
        print(f"\n[LLM Unexpected Error] {e}")
        traceback.print_exc()
        sentence_queue.put("Oops, my brain just glitched.")
    finally:
        sentence_queue.put(None)