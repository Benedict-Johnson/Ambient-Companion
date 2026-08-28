"""
Test whether importing pocketsphinx before creating sd.InputStream causes a hang.
"""
import sounddevice as sd
import sys

print("Test 1: sd.InputStream WITHOUT pocketsphinx import")
try:
    stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=2048)
    stream.start()
    print("  -> OK: stream started successfully")
    stream.stop()
    stream.close()
    print("  -> OK: stream closed")
except Exception as e:
    print(f"  -> FAILED: {e}")

print()
print("Test 2: Import pocketsphinx, then create sd.InputStream")
from pocketsphinx import Decoder, Config
print("  -> pocketsphinx imported")
try:
    print("  -> Creating sd.InputStream...")
    stream2 = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=2048)
    print("  -> sd.InputStream object created")
    print("  -> Starting stream...")
    stream2.start()
    print("  -> OK: stream started successfully")
    stream2.stop()
    stream2.close()
    print("  -> OK: stream closed")
except Exception as e:
    print(f"  -> FAILED: {e}")

print()
print("Test 3: Create sd.InputStream FIRST, then import pocketsphinx")
try:
    print("  -> Creating sd.InputStream...")
    stream3 = sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=2048)
    print("  -> sd.InputStream object created")
    stream3.start()
    print("  -> OK: stream started successfully")
    from pocketsphinx import Decoder as D2, Config as C2
    print("  -> pocketsphinx imported after stream start")
    config = C2(lm=False, keyphrase='hey freya', kws_threshold=1e-15)
    decoder = D2(config)
    print("  -> Decoder created OK")
    stream3.stop()
    stream3.close()
    print("  -> OK: stream closed")
except Exception as e:
    print(f"  -> FAILED: {e}")

print()
print("All tests completed.")
