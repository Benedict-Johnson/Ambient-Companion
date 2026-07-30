import requests
import traceback
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


def generate_response(prompt: str):
    prompt = prompt.strip()
    if not prompt:
        return ""

    final_prompt = f"""
{SYSTEM_PROMPT}

User: {prompt}

Freya:
"""

    try:
        print(f"[DEBUG] LLM request sent to {OLLAMA_URL} with prompt length {len(final_prompt)}")
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": final_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "num_predict": 60
                }
            },
            timeout=LLM_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        resp_text = data.get("response", "").strip()
        print(f"[DEBUG] LLM response received: '{resp_text}'")
        return resp_text
    except requests.exceptions.RequestException as e:
        print(f"\n[LLM Error] {e}")
        traceback.print_exc()
        return "I'm having trouble thinking right now."
    except Exception as e:
        print(f"\n[LLM Unexpected Error] {e}")
        traceback.print_exc()
        return "Oops, my brain just glitched."