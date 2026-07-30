import subprocess
import sounddevice as sd
import soundfile as sf
import tempfile
import os
import traceback
from app.config import PIPER_PATH, VOICE_MODEL


def speak(text: str):
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

        # Play audio
        data, samplerate = sf.read(temp_wav_path)
        print(f"[DEBUG] Piper playback started.")
        sd.play(data, samplerate)
        sd.wait()
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