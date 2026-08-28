import whisper
import sounddevice as sd
import numpy as np
import time
import queue
import traceback
from app.config import WHISPER_MODEL, SAMPLE_RATE, VAD_THRESHOLD, SILENCE_DURATION, WAKE_WORD, WAKE_WORD_THRESHOLD
from pocketsphinx import Decoder, Config

print("Loading Whisper model...")
try:
    MODEL = whisper.load_model(WHISPER_MODEL)
    print("Whisper loaded.")
except Exception as e:
    print(f"Failed to load Whisper model: {e}")
    traceback.print_exc()
    MODEL = None

# Common Whisper hallucinations when there is silence or background noise
HALLUCINATIONS = [
    "thank you.", "thank you", "thanks.", "thanks",
    "you", "[silence]", "[blank]", "bye.", "bye",
    "thank you for watching.", "thank you for watching",
    "i'm sorry.", "i'm sorry"
]

def is_hallucination(text):
    t = text.strip().lower()
    if not t:
        return True
    for h in HALLUCINATIONS:
        if t == h:
            return True
    # Filter very short meaningless transcripts
    if len(t) <= 2:
        return True
    return False

import threading

class MicrophoneStream:
    def __init__(self):
        print("[DEBUG] MicrophoneStream initialization started.")
        self.stream = None
        self.listeners = []
        self.listener_lock = threading.Lock()
        self.init_lock = threading.Lock()
        self.first_callback_received = False
        
    def callback(self, indata, frames, time_info, status):
        if not self.first_callback_received:
            print("[DEBUG] First microphone callback received.")
            self.first_callback_received = True
            
        if status:
            pass
            
        data = indata.copy()
        with self.listener_lock:
            for q in self.listeners:
                q.put(data)

    def start(self):
        print("[DEBUG] MicrophoneStream.start() entered.")
        with self.init_lock:
            if self.stream is None:
                print(f"\n[DEBUG] Creating shared sd.InputStream")
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
        with self.listener_lock:
            if q not in self.listeners:
                self.listeners.append(q)
                
    def unregister_listener(self, q: queue.Queue):
        with self.listener_lock:
            if q in self.listeners:
                self.listeners.remove(q)

MIC_STREAM = MicrophoneStream()

def listen_for_wake_word():
    print("[DEBUG] Freya state: AMBIENT")
    MIC_STREAM.start()
    print("[DEBUG] MicrophoneStream ready.")
    q = queue.Queue()
    MIC_STREAM.register_listener(q)
    print("[DEBUG] Wake-word listener begins consuming audio.")

    print(f"[DEBUG WakeWord] Wake word: {WAKE_WORD}")
    print(f"[DEBUG WakeWord] Threshold: {WAKE_WORD_THRESHOLD}")
    print(f"[DEBUG WakeWord] Sample rate: {SAMPLE_RATE}")

    config = Config(lm=False, keyphrase=WAKE_WORD, kws_threshold=WAKE_WORD_THRESHOLD)
    decoder = Decoder(config)
    decoder.start_utt()
    
    recent_chunks = []
    
    first_chunk_received = False
    last_log_time = time.time()
    last_hyp_log_time = time.time()
    empty_queue_count = 0

    try:
        while True:
            try:
                audio_chunk = q.get(timeout=0.1)
                empty_queue_count = 0
            except queue.Empty:
                empty_queue_count += 1
                if empty_queue_count == 20: # 2 seconds of empty queue
                    print("[DEBUG WakeWord] Waiting for microphone audio...")
                    empty_queue_count = 0
                continue
            
            if not first_chunk_received:
                print("[DEBUG WakeWord] First audio chunk received.")
                first_chunk_received = True
                
            current_time = time.time()
            if current_time - last_log_time >= 0.5:
                rms = np.sqrt(np.mean(np.square(audio_chunk)))
                print(f"[DEBUG WakeWord] dtype: {audio_chunk.dtype} | shape: {audio_chunk.shape} | Audio RMS: {rms:.4f} | Min: {np.min(audio_chunk):.4f} | Max: {np.max(audio_chunk):.4f}")
                last_log_time = current_time

            recent_chunks.append(audio_chunk)
            if len(recent_chunks) > 5:
                recent_chunks.pop(0)

            # Safe conversion: Ensure float32 audio is clipped to [-1.0, 1.0] before conversion
            clipped_audio = np.clip(audio_chunk, -1.0, 1.0)
            chunk_int16 = (clipped_audio * 32767).astype(np.int16)
            decoder.process_raw(chunk_int16.tobytes(), False, False)
            
            if current_time - last_hyp_log_time >= 1.0:
                hyp = decoder.hyp()
                hyp_text = hyp.hypstr if hyp is not None else "None"
                print(f"[DEBUG WakeWord] Pocketsphinx hypothesis: '{hyp_text}'")
                last_hyp_log_time = current_time
            
            if decoder.hyp() is not None:
                # Wake word detected
                decoder.end_utt()
                # Return the queue and recent chunks so listen() can smoothly take over
                return q, recent_chunks
    except Exception as e:
        print(f"\n[Error] during wake word detection: {e}")
        MIC_STREAM.unregister_listener(q)
        return None, None

def listen(barge_in_mode=False, interruption_event=None, abort_event=None, existing_q=None, initial_recent_chunks=None):
    if MODEL is None:
        print("Whisper model not loaded.")
        time.sleep(2)
        return ""

    if not barge_in_mode and existing_q is None:
        print("\nWaiting for speech...")
        
    # Ensure mic is running
    MIC_STREAM.start()
    
    if existing_q is not None:
        q = existing_q
    else:
        q = queue.Queue()
        MIC_STREAM.register_listener(q)
    
    recording = []
    started = False
    silence_start = None
    consecutive_speech_chunks = 0
    recent_chunks = initial_recent_chunks if initial_recent_chunks is not None else []

    try:
        while True:
            if abort_event and abort_event.is_set():
                return ""
                
            try:
                audio_chunk = q.get(timeout=0.1)
            except queue.Empty:
                continue

            volume = np.sqrt(np.mean(audio_chunk**2))
            
            # Apply barge-in specific threshold
            if barge_in_mode:
                from app.config import BARGE_IN_THRESHOLD_MULTIPLIER, BARGE_IN_CONSECUTIVE_CHUNKS
                current_threshold = VAD_THRESHOLD * BARGE_IN_THRESHOLD_MULTIPLIER
                required_chunks = BARGE_IN_CONSECUTIVE_CHUNKS
            else:
                current_threshold = VAD_THRESHOLD
                required_chunks = 1
                
            if not barge_in_mode:
                # Provide feedback without spamming new lines
                print(f"\rVolume: {volume:.4f}   ", end="", flush=True)

            if not started:
                recent_chunks.append(audio_chunk)
                if len(recent_chunks) > 5: # keep 5 chunks of context before speech
                    recent_chunks.pop(0)
                    
                if volume > current_threshold:
                    consecutive_speech_chunks += 1
                    if consecutive_speech_chunks >= required_chunks:
                        if not barge_in_mode:
                            print("\n[DEBUG] Voice detected (recording started).")
                        if barge_in_mode and interruption_event:
                            print("\n[DEBUG] Barge-in detected.")
                            interruption_event.set()
                        started = True
                        recording.extend(recent_chunks)
                else:
                    consecutive_speech_chunks = 0
            else:
                recording.append(audio_chunk)
                if volume < current_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_DURATION:
                        if not barge_in_mode:
                            print("\n[DEBUG] Silence detected (recording stopped).")
                        break
                else:
                    silence_start = None
    except Exception as e:
        print(f"\n[Error] during recording: {e}")
        traceback.print_exc()
        return ""
    finally:
        # We always unregister the queue when we are done, even if we were passed an existing one
        MIC_STREAM.unregister_listener(q)

    if not recording:
        return ""
        
    if barge_in_mode and abort_event and abort_event.is_set():
        # If we got interrupted by the main thread finishing before we transcribed
        return ""

    # Whisper needs 1D float32 array
    audio = np.concatenate(recording, axis=0).flatten()
    
    if not barge_in_mode:
        print("[DEBUG] Whisper transcription begins.")
        
    try:
        result = MODEL.transcribe(audio, fp16=False)
        text = result.get("text", "").strip()
        
        if is_hallucination(text):
            if not barge_in_mode:
                print("[DEBUG] Transcript was filtered as empty or hallucination.")
            return ""
            
        if not barge_in_mode:
            print("RAW TRANSCRIPTION:", text)
        return text
    except Exception as e:
        print(f"\n[Error] during transcription: {e}")
        traceback.print_exc()
        return ""