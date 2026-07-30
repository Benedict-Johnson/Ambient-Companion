import os

# LLM Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini"
LLM_TIMEOUT = 10 # seconds

# STT Configuration
WHISPER_MODEL = "base"
SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.01  # RMS threshold for voice activity
SILENCE_DURATION = 1.2  # Seconds of silence before stopping recording

# TTS Configuration
PIPER_PATH = r"C:\piper\piper\piper.exe"
VOICE_MODEL = r"C:\piper\piper\models\en_US-amy-medium.onnx"