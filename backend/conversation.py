from uuid import uuid4

from .prompts import LIBRARY_SYSTEM_PROMPT

MAX_HISTORY_MESSAGES = 10


class ConversationManager:
	def __init__(self) -> None:
		self.conversations: dict[str, list[dict[str, str]]] = {}

	def create_session(self) -> str:
		session_id = str(uuid4())
		self.conversations[session_id] = []
		return session_id

	def get_history(self, session_id: str) -> list[dict[str, str]]:
		return self.conversations[session_id]

	def add_message(self, session_id: str, role: str, content: str) -> None:
		self.get_history(session_id).append({"role": role, "content": content})

	def reset_session(self, session_id: str) -> None:
		self.conversations[session_id] = []

	def build_messages(self, session_id: str) -> list[dict[str, str]]:
		return [
			{"role": "system", "content": LIBRARY_SYSTEM_PROMPT},
			*self.get_history(session_id)[-MAX_HISTORY_MESSAGES:],
		]