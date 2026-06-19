from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ConversationSession:
    session_id: str
    history: list[dict] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_turn(self, question: str, answer: str):
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})

    def get_history(self, last_n_turns: int = 5) -> list[dict]:
        """Return last N turns to keep context window small."""
        return self.history[-(last_n_turns * 2):]

    def clear(self):
        self.history = []


class MemoryStore:
    def __init__(self):
        self._sessions: dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: str) -> ConversationSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(
                session_id=session_id
            )
        return self._sessions[session_id]

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def active_sessions(self) -> int:
        return len(self._sessions)


# Module-level singleton
memory_store = MemoryStore()
