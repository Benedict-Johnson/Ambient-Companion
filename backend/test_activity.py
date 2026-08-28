import time
from app.context import ContextEngine
from app.activity import ActivityEngine

def test():
    # We create engines directly
    context_engine = ContextEngine()
    
    # We create the activity engine and override duration milestones for fast testing
    activity_engine = ActivityEngine(context_engine)
    activity_engine.debounce_seconds = 2.0
    activity_engine.milestones = [5, 10]  # Fast milestones for testing
    
    context_engine.start()
    activity_engine.start()
    
    print("Testing started. Please switch applications to observe events...")
    
    try:
        for i in range(20):
            events = activity_engine.get_events()
            for event in events:
                print(f"EVENT EMITTED: {event}")
            time.sleep(1)
    finally:
        activity_engine.stop()
        context_engine.stop()
        print("Testing stopped.")

if __name__ == "__main__":
    test()
