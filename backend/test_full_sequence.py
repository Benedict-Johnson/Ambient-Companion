"""
Test: Reproduce the EXACT stt.py module-level loading sequence.
Import whisper, load model, import pocketsphinx, then start MicrophoneStream.
"""
import sounddevice as sd
import numpy as np
import threading
import queue
import time
import sys

SAMPLE_RATE = 16000

class MicrophoneStream:
    def __init__(self):
        self.stream = None
        self.listeners = []
        self.lock = threading.Lock()
        self.first_callback_received = False
        
    def callback(self, indata, frames, time_info, status):
        if not self.first_callback_received:
            print("[DEBUG] First microphone callback received.")
            self.first_callback_received = True
        if status:
            pass
        data = indata.copy()
        with self.lock:
            for q in self.listeners:
                q.put(data)

    def start(self):
        print("[DEBUG] MicrophoneStream.start() entered.")
        with self.lock:
            if self.stream is None:
                print("[DEBUG] Creating shared sd.InputStream")
                self.stream = sd.InputStream(
                    samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                    blocksize=2048, callback=self.callback
                )
                print("[DEBUG] sd.InputStream object created.")
                self.stream.start()
                print("[DEBUG] Shared microphone stream started.")
        print("[DEBUG] MicrophoneStream.start() completed.")

# Step 1: Load Whisper (like stt.py module level)
print("Step 1: Loading Whisper...")
import whisper
MODEL = whisper.load_model("base")
print("Step 1: Whisper loaded.")

# Step 2: Import pocketsphinx (like stt.py line 8)
print("Step 2: Importing pocketsphinx...")
from pocketsphinx import Decoder, Config
print("Step 2: Pocketsphinx imported.")

# Step 3: Create MicrophoneStream (like stt.py line 90)
print("Step 3: Creating MicrophoneStream...")
MIC_STREAM = MicrophoneStream()
print("Step 3: MicrophoneStream created.")

# Step 4: Start it (like listen_for_wake_word does)
print("Step 4: Starting MicrophoneStream...")
MIC_STREAM.start()
print("Step 4: MicrophoneStream started.")

# Step 5: Register listener and get audio
q = queue.Queue()
MIC_STREAM.register_listener(q)
time.sleep(1)
count = 0
while not q.empty():
    q.get()
    count += 1
print(f"Step 5: Got {count} audio chunks. All OK!")
