import time
import threading
import queue
from app.config import ACTIVITY_ENABLED, ACTIVITY_DEBOUNCE_SECONDS, ACTIVITY_DURATION_MILESTONES

class ActivityEngine:
    def __init__(self, context_engine):
        self.context_engine = context_engine
        self.enabled = ACTIVITY_ENABLED
        self.debounce_seconds = ACTIVITY_DEBOUNCE_SECONDS
        self.milestones = ACTIVITY_DURATION_MILESTONES
        
        self._lock = threading.Lock()
        self._events = queue.Queue()
        
        # Debounce tracking
        self._pending_context = None
        self._pending_since = 0.0
        
        # Confirmed active state
        self._current_app = "unknown"
        self._current_window = "unknown"
        self._current_process = "unknown"
        self._activity_start_time = 0.0
        self._milestones_reached = set()

    def start(self):
        if not self.enabled:
            return
        print("[DEBUG Activity] ActivityEngine initialized.")
        self.context_engine.add_listener(self._on_context_update)

    def stop(self):
        if not self.enabled:
            return
        self.context_engine.remove_listener(self._on_context_update)

    def _on_context_update(self, context):
        app = context.get("active_application", "unknown")
        win = context.get("active_window", "unknown")
        proc = context.get("active_process", "unknown")
        timestamp = context.get("timestamp")
        
        # Ignore unknown states if we can
        if app == "unknown" and win == "unknown":
            return
            
        now = time.time()
        
        with self._lock:
            # If the raw context changes from our pending context, reset debounce
            if self._pending_context is None or self._pending_context["app"] != app or self._pending_context["win"] != win:
                self._pending_context = {"app": app, "win": win, "proc": proc}
                self._pending_since = now
                
            # Check if debounce period has elapsed
            if now - self._pending_since >= self.debounce_seconds:
                self._confirm_activity(app, win, proc, timestamp, now)
                
            # Check duration milestones
            if self._current_app != "unknown":
                duration = int(now - self._activity_start_time)
                for milestone in sorted(self.milestones):
                    if duration >= milestone and milestone not in self._milestones_reached:
                        self._milestones_reached.add(milestone)
                        self._emit_event({
                            "type": "activity_duration",
                            "application": self._current_app,
                            "duration_seconds": milestone,
                            "timestamp": timestamp
                        })
                        print(f"[DEBUG Activity] Activity milestone reached: {self._current_app} ({milestone} seconds)")

    def _confirm_activity(self, app, win, proc, timestamp, now):
        app_changed = (app != self._current_app)
        win_changed = (win != self._current_window)
        
        if app_changed:
            if self._current_app != "unknown":
                self._emit_event({
                    "type": "application_changed",
                    "previous": self._current_app,
                    "current": app,
                    "timestamp": timestamp
                })
                print(f"[DEBUG Activity] Application changed: {self._current_app} -> {app}")
            
            self._current_app = app
            self._current_process = proc
            self._activity_start_time = now
            self._milestones_reached.clear()
            print(f"[DEBUG Activity] Activity started: {app}")
            
        elif win_changed:
            if self._current_window != "unknown":
                self._emit_event({
                    "type": "window_changed",
                    "application": app,
                    "previous_window": self._current_window,
                    "current_window": win,
                    "timestamp": timestamp
                })
                print(f"[DEBUG Activity] Window changed: {self._current_window} -> {win}")
            
        self._current_window = win

    def _emit_event(self, event):
        self._events.put(event)

    def get_events(self):
        events = []
        while not self._events.empty():
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def get_current_activity(self):
        with self._lock:
            if self._current_app == "unknown":
                return None
            
            return {
                "application": self._current_app,
                "window": self._current_window,
                "process": self._current_process,
                "duration_seconds": int(time.time() - self._activity_start_time) if self._activity_start_time > 0 else 0
            }
