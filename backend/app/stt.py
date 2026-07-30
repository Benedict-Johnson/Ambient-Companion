import whisper
import sounddevice as sd
import numpy as np
import time
import queue
import traceback
from app.config import WHISPER_MODEL, SAMPLE_RATE, VAD_THRESHOLD, SILENCE_DURATION

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

def listen():
    if MODEL is None:
        print("Whisper model not loaded.")
        time.sleep(2)
        return ""

    print("\nWaiting for speech...")
    
    q = queue.Queue()
    debug_callback_count = 0

    def callback(indata, frames, time_info, status):
        nonlocal debug_callback_count
        if status:
            print(f"\n[DEBUG] SoundDevice Status: {status}")
            
        # Calculate RMS immediately inside callback
        rms_before = np.sqrt(np.mean(indata**2))
        
        if debug_callback_count < 10:
            print(f"\n[DEBUG Callback] indata dtype: {indata.dtype}, shape: {indata.shape}")
            print(f"[DEBUG Callback] Min: {indata.min():.6f}, Max: {indata.max():.6f}, RMS before processing: {rms_before:.6f}")
            debug_callback_count += 1
            
        q.put(indata.copy())

    try:
        print(f"\n[DEBUG] Creating sd.InputStream with parameters:")
        print(f"        device=None (Default)")
        print(f"        samplerate={SAMPLE_RATE}")
        print(f"        channels=1")
        print(f"        dtype='float32'")
        print(f"        blocksize=2048")
        
        stream = sd.InputStream(
            device=None,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=2048,
            callback=callback
        )
        stream.start()
        print("[DEBUG] Microphone initialized.")
    except Exception as e:
        print(f"\n[Error] Failed to open microphone: {e}")
        traceback.print_exc()
        time.sleep(2)
        return ""

    recording = []
    started = False
    silence_start = None
    debug_count = 0

    try:
        while True:
            audio_chunk = q.get()
            # Calculate RMS (Root Mean Square) for volume
            volume = np.sqrt(np.mean(audio_chunk**2))
            
            if debug_count < 10:
                print(f"\n[DEBUG] Chunk shape: {audio_chunk.shape}, Dtype: {audio_chunk.dtype}")
                print(f"[DEBUG] Min: {np.min(audio_chunk):.6f}, Max: {np.max(audio_chunk):.6f}, RMS: {volume:.6f}")
                debug_count += 1
                
            # Provide feedback without spamming new lines
            print(f"\rVolume: {volume:.4f}   ", end="", flush=True)

            if not started:
                if volume > VAD_THRESHOLD:
                    print("\n[DEBUG] Voice detected (recording started).")
                    started = True
                    recording.append(audio_chunk)
            else:
                recording.append(audio_chunk)
                if volume < VAD_THRESHOLD:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_DURATION:
                        print("\n[DEBUG] Silence detected (recording stopped).")
                        break
                else:
                    silence_start = None
    except Exception as e:
        print(f"\n[Error] during recording: {e}")
        traceback.print_exc()
        stream.stop()
        stream.close()
        return ""

    stream.stop()
    stream.close()

    if not recording:
        return ""

    # Whisper needs 1D float32 array
    audio = np.concatenate(recording, axis=0).flatten()
    final_rms = np.sqrt(np.mean(audio**2))
    
    print(f"[DEBUG] Audio length recorded: {len(audio)} samples")
    print(f"[DEBUG] RMS immediately before Whisper transcription: {final_rms:.6f}")

    print("[DEBUG] Whisper transcription begins.")
    try:
        # Pass numpy array directly to Whisper to avoid file I/O
        result = MODEL.transcribe(audio, fp16=False)
        text = result.get("text", "").strip()
        print(f"[DEBUG] Whisper transcription result: '{text}'")
        
        if is_hallucination(text):
            print("[DEBUG] Transcript was filtered as empty or hallucination.")
            return ""
            
        print("RAW TRANSCRIPTION:", text)
        return text
    except Exception as e:
        print(f"\n[Error] during transcription: {e}")
        traceback.print_exc()
        return ""