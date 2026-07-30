from app.llm import stream_response
from app.tts import speak
from app.stt import listen
from app.memory import ConversationMemory
import traceback
import threading
import queue


def main():
    print("[DEBUG] Program startup.")
    print("Freya Voice Online.")

    memory = ConversationMemory()

    try:
        while True:
            try:
                print("\n[DEBUG] Main loop restarted.")
                user_input = listen()
                
                # If listen() returned empty or a hallucination, skip this loop iteration
                if not user_input:
                    continue
                    
                print(f"\nYou: {user_input}")

                history = memory.get_messages()
                sentence_queue = queue.Queue()
                
                llm_thread = threading.Thread(
                    target=stream_response,
                    args=(user_input, history, sentence_queue)
                )
                llm_thread.start()
                
                full_response = ""
                print(f"\nFreya: ", end="", flush=True)
                
                while True:
                    sentence = sentence_queue.get()
                    if sentence is None:
                        break
                        
                    print(f"{sentence} ", end="", flush=True)
                    speak(sentence)
                    full_response += sentence + " "
                    
                llm_thread.join()
                print() # New line after the full response
                
                full_response = full_response.strip()
                if not full_response:
                    continue

                memory.add_user(user_input)
                memory.add_assistant(full_response)
                print(f"[DEBUG] Conversation history length: {memory.get_exchange_count()} exchanges")
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n[Unexpected Error in loop] {e}")
                
    except KeyboardInterrupt:
        print("\n\nShutting down Freya. Goodbye!")

if __name__ == "__main__":
    main()