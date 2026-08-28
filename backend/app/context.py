import time
import threading
import ctypes
import ctypes.wintypes
import datetime
from app.config import CONTEXT_ENABLED, CONTEXT_POLL_INTERVAL

class ContextEngine:
    def __init__(self):
        self.enabled = CONTEXT_ENABLED
        self.poll_interval = CONTEXT_POLL_INTERVAL
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        
        self._context = {
            "timestamp": "unknown",
            "time_of_day": "unknown",
            "active_application": "unknown",
            "active_window": "unknown",
            "active_process": "unknown",
            "freya_state": "ambient",
            "last_user_activity": "unknown"
        }

    def start(self):
        if not self.enabled:
            return
            
        print("[DEBUG] ContextEngine initialized.")
        with self._lock:
            self._running = True
            
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _get_time_of_day(self, hour):
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    def _get_active_window_info(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                print(f"[DEBUG] GetForegroundWindow returned {hwnd}")
                return "unknown", "unknown", "unknown"
                
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            window_title = buf.value if buf.value else "unknown"
            
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            process_name = "unknown"
            application_name = "unknown"
            
            # PROCESS_QUERY_INFORMATION (0x0400) | PROCESS_VM_READ (0x0010)
            # Actually, PROCESS_QUERY_LIMITED_INFORMATION is 0x1000, better for getting process name without admin rights
            h_process = kernel32.OpenProcess(0x1000, False, pid)
            if h_process:
                exe_path_buf = ctypes.create_unicode_buffer(260)
                if psapi.GetModuleFileNameExW(h_process, 0, exe_path_buf, 260):
                    process_name = exe_path_buf.value.split("\\")[-1]
                    application_name = process_name.replace(".exe", "")
                kernel32.CloseHandle(h_process)
            else:
                print(f"[DEBUG] OpenProcess failed for pid {pid.value}")
                
            return application_name, window_title, process_name
        except Exception as e:
            print(f"[DEBUG] Exception in _get_active_window_info: {e}")
            return "unknown", "unknown", "unknown"

    def _poll_loop(self):
        last_app = "unknown"
        last_win = "unknown"
        
        while True:
            with self._lock:
                if not self._running:
                    break
                    
            now = datetime.datetime.now()
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
            time_of_day = self._get_time_of_day(now.hour)
            
            app_name, win_title, proc_name = self._get_active_window_info()
            
            with self._lock:
                self._context["timestamp"] = timestamp
                self._context["time_of_day"] = time_of_day
                self._context["active_application"] = app_name
                self._context["active_window"] = win_title
                self._context["active_process"] = proc_name
                
            if app_name != last_app or win_title != last_win:
                if app_name != "unknown" or win_title != "unknown":
                    print(f"[DEBUG Context] Active application: {app_name} | Active window: {win_title}")
                last_app = app_name
                last_win = win_title
                
            time.sleep(self.poll_interval)

    def get_context(self):
        with self._lock:
            return self._context.copy()

    def update_freya_state(self, state):
        with self._lock:
            self._context["freya_state"] = state

    def update_user_activity(self):
        now = datetime.datetime.now()
        with self._lock:
            self._context["last_user_activity"] = now.strftime("%Y-%m-%d %H:%M:%S")
