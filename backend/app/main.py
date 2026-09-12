from app.llm import stream_response
from app.tts import speak
from app.stt import listen, listen_for_wake_word
from app.memory import ConversationMemory
from app.context import ContextEngine
from app.activity import ActivityEngine
import traceback
import threading
import queue
from app.stt import MIC_STREAM
from app.ocr import capture_screen_text
from app.rag import MemoryStore, extract_memories

GLOBAL_SHUTDOWN = threading.Event()


def main():
    print("[DEBUG] Program startup.")
    print("Freya Voice Online.")

    memory = ConversationMemory()
    memory_store = MemoryStore()
    context_engine = ContextEngine()
    activity_engine = ActivityEngine(context_engine)
    context_engine.start()
    activity_engine.start()
    
    next_user_input = None

    try:
        while True:
            try:
                print("\n[DEBUG] Main loop restarted.")
                
                if next_user_input:
                    user_input = next_user_input
                    next_user_input = None
                else:
                    context_engine.update_freya_state("listening")
                    user_input = listen(barge_in_mode=False, shutdown_event=GLOBAL_SHUTDOWN)
                
                if GLOBAL_SHUTDOWN.is_set():
                    break

                # If listen() returned empty or a hallucination, skip this loop iteration
                if not user_input:
                    continue
                    
                context_engine.update_user_activity()
                print(f"\nYou: {user_input}")

                history = memory.get_messages()
                sentence_queue = queue.Queue()
                interruption_event = threading.Event()
                abort_event = threading.Event()
                
                # Get Context String
                context_snapshot = context_engine.get_context()
                activity_snapshot = activity_engine.get_current_activity()
                
                context_str = "CURRENT LOCAL CONTEXT:\n"
                context_str += f"* Active application: {context_snapshot.get('active_application', 'unknown')}\n"
                context_str += f"* Active window: {context_snapshot.get('active_window', 'unknown')}\n"
                context_str += f"* Active process: {context_snapshot.get('active_process', 'unknown')}\n"
                context_str += f"* Time of day: {context_snapshot.get('time_of_day', 'unknown')}\n"
                context_str += f"* Freya state: {context_snapshot.get('freya_state', 'unknown')}\n"
                context_str += f"* Last user activity: {context_snapshot.get('last_user_activity', 'unknown')}\n"
                
                if activity_snapshot:
                    context_str += "\nACTIVITY:\n"
                    context_str += f"* Current activity: Working in {activity_snapshot.get('application', 'unknown')}\n"
                    context_str += f"* Duration: {activity_snapshot.get('duration_seconds', 0)} seconds\n"
                    
                # OCR Integration
                screen_keywords = ["screen", "display", "monitor", "what's on my screen", "what is on my screen", "read my screen", "read the screen", "screen text", "what does this say on my screen"]
                if any(word in user_input.lower() for word in screen_keywords):
                    ocr_result = capture_screen_text()
                    context_str += "\nSCREEN TEXT (OCR):\n"
                    if ocr_result:
                        context_str += f"The following text is currently visible on the screen:\n{ocr_result}\n"
                    else:
                        context_str += "No readable text could be extracted from the screen.\n"
                
                # RAG: retrieve relevant long-term memories
                relevant_memories = memory_store.retrieve(user_input)
                if relevant_memories:
                    context_str += "\nRELEVANT LONG-TERM MEMORIES:\n"
                    for mem in relevant_memories:
                        context_str += f"* {mem['text']}\n"
                
                context_engine.update_freya_state("thinking")
                llm_thread = threading.Thread(
                    target=stream_response,
                    args=(user_input, history, sentence_queue, interruption_event, GLOBAL_SHUTDOWN, context_str)
                )
                llm_thread.start()
                
                # Start barge-in listener
                barge_in_result = []
                def barge_in_listener():
                    print("[DEBUG BARGE-IN] monitor started")
                    text = listen(barge_in_mode=True, interruption_event=interruption_event, abort_event=abort_event, shutdown_event=GLOBAL_SHUTDOWN)
                    if text:
                        barge_in_result.append(text)
                    print("[DEBUG BARGE-IN] monitor stopped")

                barge_in_thread = threading.Thread(target=barge_in_listener)
                barge_in_thread.start()
                
                full_response = ""
                print(f"\nFreya: ", end="", flush=True)
                
                while True:
                    if GLOBAL_SHUTDOWN.is_set():
                        print("\n[DEBUG] Shutdown requested, stopping TTS playback.")
                        break
                        
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
                        
                    if GLOBAL_SHUTDOWN.is_set():
                        print("[DEBUG TTS] shutdown detected, discarding queued audio")
                        break
                        
                    print("[DEBUG TTS] starting chunk")
                    context_engine.update_freya_state("speaking")
                    print(f"{sentence} ", end="", flush=True)
                    speak(sentence, interruption_event, shutdown_event=GLOBAL_SHUTDOWN)
                    print("[DEBUG TTS] finished chunk")
                    
                    if not interruption_event.is_set():
                        full_response += sentence + " "
                    
                # Clean up barge-in thread
                abort_event.set()
                
                # Clear queue to stop consumer
                while not sentence_queue.empty():
                    try:
                        sentence_queue.get_nowait()
                    except queue.Empty:
                        break
                        
                barge_in_thread.join()
                llm_thread.join()
                print() # New line after the full response
                
                if interruption_event.is_set():
                    context_engine.update_freya_state("interrupted")
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
                    
                    # RAG: extract and store explicit facts
                    new_facts = extract_memories(user_input, full_response)
                    for fact in new_facts:
                        memory_store.add_memory(fact)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n[Unexpected Error in loop] {e}")
                
    except KeyboardInterrupt:
        print("\n\nShutting down Freya. Goodbye!")
        GLOBAL_SHUTDOWN.set()
        # Ensure barge-in abort event is set if it exists in scope, though it's local.
        # The shutdown_event passed to listen will break it.
    finally:
        GLOBAL_SHUTDOWN.set()
        MIC_STREAM.stop()
        if 'memory_store' in locals():
            memory_store.close()
        if 'activity_engine' in locals():
            activity_engine.stop()
        if 'context_engine' in locals():
            context_engine.stop()

if __name__ == "__main__":
    main()