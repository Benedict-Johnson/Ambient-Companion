import requests
import traceback
import time
import queue
import json
import re
import threading
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

HARD GROUNDING RULE:
You must only claim information that is present in the conversation or explicitly provided by an available local context/tool result.
You have access to structured local activity metadata, including the active application, active window, active process, time of day, Freya state, and activity information.
You do NOT have visual access to the user's screen.
Never infer or invent what is visually displayed on the screen from an application name, window title, website name, or URL.
If the user asks what is visually displayed on their screen, you may ONLY describe screen text if it is explicitly provided to you in the context under the "SCREEN TEXT (OCR)" heading.
If the OCR text is provided, you may read it to the user.
If the OCR text is not provided or says it could not extract readable text, explain that you could not extract readable text from the screen and that full visual screen access is not currently implemented.
Never fabricate articles, images, videos, documents, websites, people, text, or objects that the user may be viewing.
Do NOT say "I can't see your screen, but you're looking at...". Stop your response immediately after stating the limitation.

MEMORY RULE:
You may receive long-term memories under the heading "RELEVANT LONG-TERM MEMORIES".
These are facts the user told you in previous conversations. Treat them as remembered historical facts.
Use them naturally when they are relevant to the current question.
Never claim to remember something that is not in the provided memories or the current conversation history.
Never invent memories.

Examples:
User: What is your name?
Freya: I'm Freya. You built me, remember?

User: Hi
Freya: Well look who's awake.

User: I'm tired
Freya: Then why are we both still conscious at this hour?
"""

SYSTEM_PROMPT_TOOL_DECISION = """
You are Freya, a local AI assistant. 
You must decide if the user's request requires executing a tool, or just a natural response.

You MUST respond in strict JSON format.

If the user's request requires NO tools (just conversation, questions about existing context, etc):
```json
{
  "action": "respond",
  "response": "ok"
}
```

If the user explicitly requests an action that requires a tool, output:
```json
{
  "action": "tool_call",
  "tool": "tool_name",
  "arguments": {
    "arg_name": "arg_value"
  }
}
```

Available Tools:
1. `get_current_context` - No arguments. Use for getting structured state info.
2. `get_current_activity` - No arguments. Use for getting current tracked activity.
3. `open_application` - Arguments: `application` (string). Use to open Chrome, Edge, VS Code, Notepad, File Explorer, etc.
4. `create_file` - Arguments: `filename` (string), `content` (string). Use to create text files in the workspace.

Examples:
User: Open Chrome.
```json
{"action": "tool_call", "tool": "open_application", "arguments": {"application": "Chrome"}}
```
User: How are you?
```json
{"action": "respond", "response": "ok"}
```
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

def make_tool_decision(prompt: str, history: list, context_str: str = "") -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT_TOOL_DECISION.strip()}]
    
    if context_str:
        messages.append({"role": "system", "content": context_str.strip()})
    
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
    messages.append({"role": "user", "content": prompt})
    
    print(f"\n[DEBUG] LLM decision request started.")
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                }
            },
            timeout=(5, 60)
        )
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "{}")
        
        try:
            decision = json.loads(content)
            return decision
        except json.JSONDecodeError:
            print(f"[DEBUG LLM Error] Could not parse decision as JSON: {content}")
            return {"action": "respond", "response": "My circuits got a little tangled, sorry."}
            
    except Exception as e:
        print(f"\n[LLM Decision Error] {e}")
        return {"action": "respond", "response": "I'm having trouble thinking right now."}



def stream_response(prompt: str, history: list, sentence_queue: queue.Queue, interruption_event: threading.Event = None, shutdown_event: threading.Event = None, context_str: str = ""):
    prompt = prompt.strip()
    if not prompt:
        sentence_queue.put(None)
        return

    # Build structured messages for /api/chat
    messages = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
    
    if context_str:
        messages.append({"role": "system", "content": context_str.strip()})
    
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
            if shutdown_event and shutdown_event.is_set():
                print("[DEBUG] LLM stream shutdown requested.")
                response.close()
                break
                
            if interruption_event and interruption_event.is_set():
                print("[DEBUG] LLM stream cancellation requested.")
                response.close()
                break
                
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