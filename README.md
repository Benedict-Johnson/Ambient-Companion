# Freya

Freya is an offline/local desktop voice assistant designed to be a witty, emotionally aware, and slightly sarcastic AI companion. Built completely on local open-source models, Freya avoids reliance on cloud APIs for its core pipeline, providing voice-first interaction with ambient listening, context awareness, and local tool execution capabilities.

## Overview

- **Local/Offline Operation:** The core assistant runs locally on your machine, ensuring privacy and fast responses without external cloud dependencies.
- **Voice-First Interaction:** Built to interact naturally through speech, combining STT, LLM, and TTS pipelines.
- **Ambient/Continuous Listening:** Automatically detects speech based on volume thresholds and processes silence to know when you have finished talking.
- **Contextual Awareness:** Understands your current active application, window, and desktop activity.
- **Screen Text (OCR):** Capable of reading visible text on your screen upon explicit request.
- **Short-Term Conversational Memory:** Remembers recent exchanges for coherent back-and-forth dialogue.
- **Long-Term Local Memory (RAG):** Extracts facts during conversations and retrieves them using local embeddings.
- **Local Tool Execution:** Securely executes specific local tasks (like opening apps or creating files) based on your intent.

## Core Capabilities

### 1. Offline Voice Pipeline
- **STT:** OpenAI's Whisper model (`base`) running locally transcribes speech in real-time.
- **LLM:** Ollama running the `phi3:mini` model generates Freya's conversational responses.
- **TTS:** Piper TTS generates fast, high-quality, and natural-sounding human speech.
- **VAD (Voice Activity Detection):** Uses audio RMS thresholds to handle ambient listening and detect when you're speaking.

### 2. Streaming Responses
- **LLM Streaming:** Responses are streamed directly from Ollama.
- **Natural Chunking:** Text is chunked into logical sentences/phrases before being sent to TTS.
- **Producer/Consumer:** A threaded producer-consumer queue ensures TTS playback begins as soon as the first sentence is generated, drastically reducing latency.

### 3. Barge-In / Interruption
- **User Interruption:** You can interrupt Freya while she is speaking.
- **Propagation:** Detecting speech during playback triggers an interruption event, immediately aborting the current TTS playback, discarding remaining queued sentences, and feeding your new input into the pipeline.

### 4. Continuous/Ambient Listening
- **Current Behavior:** Freya listens continuously using an energy-based threshold (RMS) to determine when you speak.
- *Note: Earlier iterations used a keyword spotter (wake word), but the current architecture relies on continuous ambient listening to maintain an organic, fluid conversational flow.*

### 5. Context Awareness
- **State Polling:** A background `ContextEngine` polls system state at regular intervals.
- **Injected Context:** Tracks the active application, active window title, active process, time of day, last user activity, and Freya's current state (listening, thinking, speaking).

### 6. Activity / Event Awareness
- **Application Tracking:** Monitors application changes to track how long you've been working in specific software.
- **Debouncing:** Prevents rapid window switching from spamming the activity log.
- **Duration Milestones:** Records when you cross significant time thresholds in applications (e.g., 5 mins, 15 mins, 30 mins).

### 7. Screen Text / OCR
- **Explicit Intent:** When you explicitly ask about your screen (e.g., "what does this say on my screen"), Freya triggers an OCR pass.
- **Tesseract OCR:** Captures a screenshot and extracts text locally.
- **Limitations:** This is strictly text extraction, not general visual understanding. Privacy is maintained by keeping all processing local.

### 8. Short-Term Conversation Memory
- Maintains an in-memory queue of recent exchanges (currently limited to 10 exchanges / 20 messages) to provide context for follow-up questions.

### 9. Long-Term Memory and RAG
- **Storage:** Persists facts to a local SQLite database (`memories.db`).
- **Embeddings:** Uses the `sentence-transformers` library to create local embeddings for semantic retrieval.
- **Extraction:** Deterministically extracts facts from conversations and stores them for future reference.
- *Note: There is currently a known environment compatibility issue with Keras 3 / `tf-keras` for the sentence transformer model in some setups.*

### 10. Local Tool Calling / Task Execution
- **Strict JSON Decision Stage:** Before generating a streaming response, Freya evaluates your request using a strict JSON-formatted prompt to decide if a tool is needed.
- **Tool Registry:** A centralized router manages available tools and isolates their execution from the LLM.
- **Available Tools:**
  - `get_current_context`
  - `get_current_activity`
  - `open_application`
  - `create_file`
- **Safety & Sandboxing:**
  - `open_application` uses a strict allowlist (Chrome, Edge, VS Code, Notepad, File Explorer). Arbitrary shell execution is forbidden.
  - `create_file` strictly writes to the `backend/workspace/` sandbox directory, rejects path traversal attempts, and prevents overwriting existing files.
  - No autonomous or background tool execution occurs without explicit user intent.

## Architecture

The system operates via the following real-time flow:

```text
User speech
    ↓
Whisper STT (transcription)
    ↓
Context / Activity / OCR (snapshot generation when required)
    ↓
RAG memory retrieval (injecting historical facts)
    ↓
LLM tool decision (JSON evaluation)
    ↓
Tool Router (execution when required)
    ↓
Tool result (injected back into context)
    ↓
LLM response generation (streaming chunks)
    ↓
Piper TTS (audio generation)
    ↓
Speaker
```

*Barge-in handling runs concurrently during the TTS playback stage, capable of aborting the flow and jumping back to the user speech block.*

## Tool Architecture

Tools are registered in a centralized registry in `app/tools.py`. When the LLM decides an action is necessary via its strict JSON output, the router validates the tool name and arguments. Execution is entirely isolated within Python functions containing their own error handling and safety checks. If a tool fails, a structured JSON failure is passed back to the LLM, allowing Freya to explain the failure naturally. Model-generated strings are **never** passed directly to arbitrary shell execution.

## Project Structure

```text
Freya/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── activity.py     # Tracks time spent in applications
│   │   ├── config.py       # Centralized configuration settings
│   │   ├── context.py      # Polls active window/system state
│   │   ├── llm.py          # Ollama integration, system prompts, tool logic
│   │   ├── main.py         # Main orchestration loop
│   │   ├── memory.py       # Short-term conversation history
│   │   ├── ocr.py          # Screen capture and text extraction
│   │   ├── rag.py          # Long-term memory, SQLite, embeddings
│   │   ├── stt.py          # Audio capture, VAD, Whisper
│   │   ├── tools.py        # Tool registry and implementations
│   │   └── tts.py          # Piper TTS integration
│   ├── workspace/          # Sandboxed directory for generated files
│   ├── requirements.txt    # Python dependencies
│   ├── test_*.py           # Test suite files
│   └── ...
├── .gitignore
└── README.md
```

## Installation / Setup

1. **Python:** Ensure you have Python 3.8+ installed (the project currently runs in Python 3.13 on Windows).
2. **Virtual Environment:**
   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. **Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Ollama & Model:**
   Install [Ollama](https://ollama.com/) and download the required model:
   ```powershell
   ollama run phi3:mini
   ```
5. **Piper TTS:**
   Download [Piper](https://github.com/rhasspy/piper) and place it at `C:\piper\piper\piper.exe`, along with the `en_US-amy-medium.onnx` voice model in the `models` subdirectory.
6. **Tesseract OCR:**
   Install Tesseract OCR for Windows and ensure it is located at `C:\Program Files\Tesseract-OCR\tesseract.exe`.

## Configuration

Settings are managed in `backend/app/config.py`:
- **Model Configuration:** `OLLAMA_URL`, `MODEL_NAME` (phi3:mini).
- **Audio & VAD:** `SAMPLE_RATE`, `VAD_THRESHOLD`, `SILENCE_DURATION`.
- **Barge-In:** `BARGE_IN_THRESHOLD_MULTIPLIER`, `BARGE_IN_CONSECUTIVE_CHUNKS`.
- **Context & Activity:** `CONTEXT_POLL_INTERVAL`, `ACTIVITY_DEBOUNCE_SECONDS`, `ACTIVITY_DURATION_MILESTONES`.
- **Paths:** `PIPER_PATH`, `VOICE_MODEL`, `TESSERACT_PATH`.

## Running Freya

With Ollama running in the background, execute:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m app.main
```

Freya will print `[DEBUG] Program startup.` and `Freya Voice Online.` before beginning to ambiently listen to your microphone.

## Testing

The project includes multiple test suites separated by functionality:
- **Fast / Unit Tests:** `test_tools.py`, `test_context.py`, `test_activity.py`, `test_chunk.py`.
- **OCR Tests:** `test_ocr.py` (may require display access, falls back gracefully in headless environments).
- **RAG Tests:** `test_rag.py` (requires `sentence-transformers` and SQLite).
- **Audio / Live Tests:** `test_mic_stream.py`, `test_mic_conflict.py`, `test_wake.py`. These tests require active microphone/speaker hardware and will block execution.
- **Integration Tests:** `test_full_sequence.py` tests end-to-end processing.

Run tests using:
```powershell
python -m unittest test_tools.py
```

## Current Verification Status (Phase 9)

- **Phase 9 Tool Test Suite:** 13/13 passed.
- **Context Regression:** Passed.
- **Activity Regression:** Passed.
- **OCR Regression:** Passed gracefully in a headless environment.
- **Chunk Regression:** Passed.
- **RAG Regression:** The RAG test currently has a pre-existing `tf-keras` / Keras 3 environment compatibility issue that causes a crash upon model loading.
- **Live-Audio Tests:** Five live-audio tests were skipped during automated CI as they are blocking/live-audio dependent.
- **Regressions:** No Phase 9 regressions were identified.

## Git / Development Workflow

The project utilizes a phase-based branching strategy. Stable checkpoints are preserved in main history, while new feature work is developed on designated phase branches (e.g., `phase-9-tool-calling`). 

## Safety / Privacy

Freya is designed with a strict local-processing architecture:
- **Local Everything:** LLM (Ollama), STT (Whisper), TTS (Piper), OCR (Tesseract), memory (SQLite), and embeddings are all processed entirely on your local machine. No cloud APIs are required for the core pipeline.
- **Tool Restrictions:** System interactions via tools are tightly sandboxed. Absolute paths, shell execution, and overwrites are intentionally prohibited to ensure safety.

## Known Limitations

- **JSON Reliability:** The `phi3:mini` model is fast but small; its JSON tool decision reliability may fluctuate for highly complex multi-part requests.
- **Chained Actions:** Autonomous chained actions (running multiple tools sequentially without user intervention) are not currently supported.
- **Visual Understanding:** OCR performs text extraction only; Freya cannot "see" or analyze non-text visual elements on your screen.
- **Audio Tests:** Live audio tests require physical hardware and will block continuous integration pipelines.
- **RAG Environment:** A current environment compatibility issue exists with `sentence-transformers` and Keras 3 on some machines.

## Roadmap / Project Status

Freya has successfully completed Phase 9 (Local Tool Calling).

**Next Step - Phase 10:** Final integration, regression testing, cleanup, and demo freeze.
