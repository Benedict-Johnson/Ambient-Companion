import whisper
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import time


print("Loading Whisper model...")

MODEL = whisper.load_model("base")

print("Whisper loaded.")


def listen(
    samplerate=44100,
    voice_threshold=2000,
    silence_threshold=1000,
    silence_duration=2
):

    print("\nWaiting for speech...")

    stream = sd.InputStream(
        device=1,
        samplerate=samplerate,
        channels=1,
        dtype="int16",
        blocksize=2048
    )

    stream.start()

    recording = []

    started = False
    silence_start = None

    while True:

        audio_chunk, _ = stream.read(2048)

        volume = np.linalg.norm(audio_chunk)

        print(f"\rVolume: {int(volume)}", end="")

        # WAIT FOR USER TO START TALKING
        if not started:

            if volume > voice_threshold:
                print("\nSpeech detected. Recording...")
                started = True
                recording.append(audio_chunk)

        else:

            recording.append(audio_chunk)

            # DETECT SILENCE AFTER SPEECH
            if volume < silence_threshold:

                if silence_start is None:
                    silence_start = time.time()

                elif time.time() - silence_start > silence_duration:
                    print("\nSilence detected. Processing...")
                    break

            else:
                silence_start = None

    stream.stop()
    stream.close()

    audio = np.concatenate(recording, axis=0)

    wav.write("input.wav", samplerate, audio)

    print("Transcribing...")

    result = MODEL.transcribe("input.wav")

    print("RAW TRANSCRIPTION:", result["text"])

    return result["text"]