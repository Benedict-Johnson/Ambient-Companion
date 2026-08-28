from app.llm import stream_response
from app.tts import speak
from app.stt import listen, listen_for_wake_word
from app.memory import ConversationMemory
import traceback
import threading
import queue


def main():
    print("[DEBUG] Program startup.")
    print("Freya Voice Online.")

    memory = ConversationMemory()
    
    next_user_input = None
    is_ambient_mode = True

    try:
        while True:
            try:
                print("\n[DEBUG] Main loop restarted.")
                
                existing_q = None
                initial_chunks = None

                if is_ambient_mode and not next_user_input:
                    existing_q, initial_chunks = listen_for_wake_word()
                    if existing_q is None:
                        # Error occurred or stream closed
                        time.sleep(1)
                        continue
                    is_ambient_mode = False
                
                if next_user_input:
                    user_input = next_user_input
                    next_user_input = None
                else:
                    user_input = listen(barge_in_mode=False, existing_q=existing_q, initial_recent_chunks=initial_chunks)
                
                # If listen() returned empty or a hallucination, skip this loop iteration
                if not user_input:
                    is_ambient_mode = True
                    continue
                    
                print(f"\nYou: {user_input}")

                history = memory.get_messages()
                sentence_queue = queue.Queue()
                interruption_event = threading.Event()
                abort_event = threading.Event()
                
                llm_thread = threading.Thread(
                    target=stream_response,
                    args=(user_input, history, sentence_queue, interruption_event)
                )
                llm_thread.start()
                
                # Start barge-in listener
                barge_in_result = []
                def barge_in_listener():
                    print("[DEBUG] Barge-in monitoring active.")
                    text = listen(barge_in_mode=True, interruption_event=interruption_event, abort_event=abort_event)
                    if text:
                        barge_in_result.append(text)

                barge_in_thread = threading.Thread(target=barge_in_listener)
                barge_in_thread.start()
                
                full_response = ""
                print(f"\nFreya: ", end="", flush=True)
                
                while True:
                    if interruption_event.is_set():
                        print("\n[DEBUG] Stopping TTS playback.")
                        break
                        
                    try:
                        sentence = sentence_queue.get(timeout=0.1)
                    except queue.Empty:
                        if not llm_thread.is_alive() and sentence_queue.empty():
                            break
                        continue
                        
                    if sentence is None:
                        break
                        
                    print(f"{sentence} ", end="", flush=True)
                    speak(sentence, interruption_event)
                    
                    if not interruption_event.is_set():
                        full_response += sentence + " "
                    
                # Clean up barge-in thread
                abort_event.set()
                barge_in_thread.join()
                llm_thread.join()
                print() # New line after the full response
                
                if interruption_event.is_set():
                    print("[DEBUG] Interrupted response discarded.")
                    print("[DEBUG] Resuming user input.")
                    if barge_in_result:
                        next_user_input = barge_in_result[0]
                else:
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