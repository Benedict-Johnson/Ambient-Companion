import subprocess
import sounddevice as sd
import soundfile as sf
import tempfile
import os
import threading
import traceback
from app.config import PIPER_PATH, VOICE_MODEL


def speak(text: str, interruption_event: threading.Event = None):
    text = text.strip()
    if not text:
        return
        
    if not os.path.exists(PIPER_PATH):
        print(f"\n[TTS Error] Piper executable not found at {PIPER_PATH}")
        return
        
    if not os.path.exists(VOICE_MODEL):
        print(f"\n[TTS Error] Voice model not found at {VOICE_MODEL}")
        return

    # Use a temporary file to avoid overwriting and ensure clean up
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        temp_wav_path = temp_wav.name

    try:
        command = [
            PIPER_PATH,
            "--model",
            VOICE_MODEL,
            "--output_file",
            temp_wav_path
        ]

        print(f"[DEBUG] Piper synthesis started.")
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            text=True,
            stderr=subprocess.DEVNULL
        )

        process.communicate(text)
        
        if process.returncode != 0:
            print(f"\n[TTS Error] Piper process failed with code {process.returncode}")
            return

        import numpy as np

        # Play audio
        data, samplerate = sf.read(temp_wav_path)
        data = data.astype(np.float32, copy=False)
        
        print(f"[DEBUG] Piper playback started.")
        print(f"[DEBUG] TTS audio dtype: {data.dtype}")
        print(f"[DEBUG] TTS audio shape: {data.shape}")
        print(f"[DEBUG] TTS sample rate: {samplerate}")
        
        chunk_size = int(samplerate * 0.1) # 100ms chunks
        channels = 1 if len(data.shape) == 1 else data.shape[1]
        
        stream = sd.OutputStream(samplerate=samplerate, channels=channels, dtype="float32")
        stream.start()
        
        for i in range(0, len(data), chunk_size):
            if interruption_event and interruption_event.is_set():
                break
            chunk = data[i:i+chunk_size]
            stream.write(chunk)
            
        stream.stop()
        stream.close()
        print(f"[DEBUG] Piper playback finished.")
        
    except Exception as e:
        print(f"\n[TTS Error] {e}")
        traceback.print_exc()
    finally:
        # Clean up temporary file
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except OSError:
                pass