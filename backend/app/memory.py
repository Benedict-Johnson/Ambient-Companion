from app.config import MAX_MESSAGES

class ConversationMemory:
    def __init__(self):
        self.messages = []

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str):
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def _trim(self):
        while len(self.messages) > MAX_MESSAGES:
            self.messages.pop(0)

    def get_messages(self) -> list:
        return self.messages

    def get_exchange_count(self) -> int:
        return len(self.messages) // 2

    def clear(self):
        self.messages = []
