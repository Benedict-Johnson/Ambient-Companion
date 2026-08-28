"""
Test: Does sd.InputStream.start() block if the callback can't acquire a lock?
This tests the EXACT deadlock scenario: start() holds a lock, callback needs the lock.
"""
import sounddevice as sd
import threading
import time

lock = threading.Lock()
callback_entered = False

def callback(indata, frames, time_info, status):
    global callback_entered
    print(f"  callback: trying to acquire lock... (thread={threading.current_thread().name})")
    with lock:
        callback_entered = True
        print(f"  callback: got lock, processing audio")

print("Test: start() holding lock while callback needs it")
print(f"  main thread: {threading.current_thread().name}")

stream = sd.InputStream(
    samplerate=16000, channels=1, dtype="float32",
    blocksize=2048, callback=callback
)
print("  stream created")

print("  acquiring lock...")
with lock:
    print("  lock acquired, calling stream.start()...")
    stream.start()
    print("  stream.start() returned (lock still held)")
    time.sleep(0.5)  # Give callback time to try to run
    print(f"  callback_entered = {callback_entered}")
print("  lock released")
time.sleep(0.5)
print(f"  callback_entered = {callback_entered}")

stream.stop()
stream.close()
print("  Test completed!")
