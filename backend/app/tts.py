import subprocess
import sounddevice as sd
import soundfile as sf


PIPER_PATH = r"C:\piper\piper\piper.exe"

VOICE_MODEL = r"C:\piper\piper\models\en_US-amy-medium.onnx"

OUTPUT_FILE = "output.wav"


def speak(text: str):

    command = [
        PIPER_PATH,
        "--model",
        VOICE_MODEL,
        "--output_file",
        OUTPUT_FILE
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        text=True
    )

    process.communicate(text)

    data, samplerate = sf.read(OUTPUT_FILE)

    sd.play(data, samplerate)
    sd.wait()