# Freya - Ambient Companion

Freya is a witty, emotionally aware, slightly sarcastic AI laptop companion. It functions as a real-time voice-activated assistant built completely using local open-source models, avoiding reliance on external cloud APIs for the core pipeline.

## Features

- **Local Speech-To-Text (STT):** Uses OpenAI's Whisper model (running locally) to accurately transcribe user speech in real-time.
- **Local Large Language Model (LLM):** Powered by Ollama running the `phi3:mini` model. Freya has a custom system prompt that gives her a distinct personality—she's concise, conversational, and avoids typical "AI assistant" tropes.
- **Local Text-To-Speech (TTS):** Uses Piper TTS to generate fast, high-quality, and natural-sounding human speech.
- **Continuous Listening:** Automatically detects speech based on volume thresholds and processes silence to know when you have finished talking.

## Architecture

The project consists of three main pipelines in Python:

1. **`stt.py`**: Handles microphone input utilizing `sounddevice` and `numpy` to detect speech vs. silence. Once speech finishes, it runs inference using the Whisper `base` model.
2. **`llm.py`**: Sends the transcribed text to a locally running Ollama instance (`http://localhost:11434/api/generate`) requesting the `phi3:mini` model. It injects a detailed system prompt defining Freya's personality.
3. **`tts.py`**: Takes the LLM text output and uses Piper (`piper.exe`) via `subprocess` to generate a `.wav` file, which is then played back to the user via `sounddevice` and `soundfile`.
4. **`main.py`**: Orchestrates the entire loop (Listen -> Generate -> Speak).

## Requirements

- Python 3.8+
- [Ollama](https://ollama.com/) installed and running with the `phi3:mini` model (`ollama run phi3:mini`).
- [Piper TTS](https://github.com/rhasspy/piper) downloaded and available at `C:\piper\piper\piper.exe` (or modify `tts.py` to match your local path).
- A working microphone.

### Python Dependencies

```bash
pip install -r backend/requirements.txt
```
*Note: Depending on your system, installing PyTorch (`torch`) with CUDA support is recommended for faster Whisper inference.*

## How to Run

1. Make sure Ollama is running in the background.
2. Ensure Piper is installed at the correct path specified in `tts.py`.
3. Run the main application loop:

```bash
cd backend
python -m app.main
```

## System Prompt Overview

Freya's personality is defined directly in `llm.py`:
- Never says she is an AI language model.
- Keeps responses under 2 sentences (pref. 1).
- Playful, witty, and slightly sarcastic during casual chats.
- Sound human and emotionally aware.
