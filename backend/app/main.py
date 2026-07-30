from app.llm import generate_response
from app.tts import speak
from app.stt import listen


def main():
    print("[DEBUG] Program startup.")
    print("Freya Voice Online.")

    try:
        while True:
            try:
                print("\n[DEBUG] Main loop restarted.")
                user_input = listen()
                
                # If listen() returned empty or a hallucination, skip this loop iteration
                if not user_input:
                    continue
                    
                print(f"\nYou: {user_input}")

                response = generate_response(user_input)
                
                if not response:
                    continue

                print(f"\nFreya: {response}")

                speak(response)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n[Unexpected Error in loop] {e}")
                
    except KeyboardInterrupt:
        print("\n\nShutting down Freya. Goodbye!")

if __name__ == "__main__":
    main()