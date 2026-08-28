import sounddevice as sd
import numpy as np
import threading
import time

def test():
    samplerate = 44100
    # Generate 3 seconds of a sine wave
    t = np.linspace(0, 3, 3 * samplerate, False)
    data = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    interruption_event = threading.Event()
    
    def stopper():
        time.sleep(1)
        print("Stopping!")
        interruption_event.set()

    threading.Thread(target=stopper).start()

    print("Playing...")
    stream = sd.OutputStream(samplerate=samplerate, channels=1)
    stream.start()
    
    # write in chunks
    chunk_size = int(samplerate * 0.1) # 100ms
    for i in range(0, len(data), chunk_size):
        if interruption_event.is_set():
            break
        chunk = data[i:i+chunk_size]
        stream.write(chunk)
    
    stream.stop()
    stream.close()
    print("Done!")

if __name__ == "__main__":
    test()
