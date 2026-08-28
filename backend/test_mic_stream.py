"""
Test: Does the MicrophoneStream pattern from stt.py hang?
Reproduces the exact initialization sequence from the app.
"""
import sounddevice as sd
import numpy as np
import threading
import queue
import time

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
                print(f"[DEBUG] parameters: samplerate={SAMPLE_RATE}, channels=1, dtype=float32, blocksize=2048")
                self.stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=2048,
                    callback=self.callback
                )
                print("[DEBUG] sd.InputStream object created.")
                print("[DEBUG] Starting shared microphone stream...")
                self.stream.start()
                print("[DEBUG] Shared microphone stream started.")
        print("[DEBUG] MicrophoneStream.start() completed.")
                
    def register_listener(self, q: queue.Queue):
        with self.lock:
            if q not in self.listeners:
                self.listeners.append(q)
                
    def unregister_listener(self, q: queue.Queue):
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)

print("Creating MicrophoneStream instance...")
MIC_STREAM = MicrophoneStream()

print("Calling MIC_STREAM.start()...")
MIC_STREAM.start()

print("Registering a listener...")
q = queue.Queue()
MIC_STREAM.register_listener(q)

print("Waiting for 2 seconds of audio...")
time.sleep(2)

print("Getting queued audio chunks...")
count = 0
while not q.empty():
    q.get()
    count += 1
print(f"Got {count} audio chunks")

MIC_STREAM.unregister_listener(q)
print("Test completed successfully!")
