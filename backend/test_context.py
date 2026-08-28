import time
from app.context import ContextEngine

def test():
    engine = ContextEngine()
    engine.start()
    
    for i in range(5):
        print(engine.get_context())
        time.sleep(1)
        
    engine.stop()
    print("Stopped.")

if __name__ == "__main__":
    test()
