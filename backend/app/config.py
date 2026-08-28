import os

# LLM Configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3:mini"
LLM_TIMEOUT = 10 # seconds

# Memory Configuration
MAX_EXCHANGES = 10
MAX_MESSAGES = MAX_EXCHANGES * 2

# STT Configuration
WHISPER_MODEL = "base"
SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.01  # RMS threshold for voice activity
SILENCE_DURATION = 1.2  # Seconds of silence before stopping recording

# Barge-In Configuration
BARGE_IN_THRESHOLD_MULTIPLIER = 2.0
BARGE_IN_CONSECUTIVE_CHUNKS = 3

# TTS Configuration
PIPER_PATH = r"C:\piper\piper\piper.exe"
VOICE_MODEL = r"C:\piper\piper\models\en_US-amy-medium.onnx"

# Wake Word Configuration
WAKE_WORD = "hey freya"
WAKE_WORD_THRESHOLD = 1e-15  # Pocketsphinx keyword spotter threshold

# Context Configuration
CONTEXT_ENABLED = True
CONTEXT_POLL_INTERVAL = 1.0

# Activity Configuration
ACTIVITY_ENABLED = True
ACTIVITY_DEBOUNCE_SECONDS = 2.0
ACTIVITY_DURATION_MILESTONES = [300, 900, 1800, 3600]