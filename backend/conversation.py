from uuid import uuid4

from .prompts import CONTEXT_PROMPT, LIBRARY_SYSTEM_PROMPT, NO_MATCH_PROMPT

MAX_HISTORY_MESSAGES = 10
# Token budget for qwen2.5:1.5b with num_ctx=4096 (see llm.py).
CONTEXT_WINDOW_TOKENS = 4096
RESPONSE_TOKENS = 1024
MAX_DOCUMENT_TOKENS = 1200


def estimate_tokens(text: str) -> int:
	# Rough English estimate: ~4 characters per token.
	return len(text) // 4 + 1


def truncate(text: str, tokens: int) -> str:
	return text[: max(tokens, 0) * 4]


def format_documents(chunks: list[dict]) -> str:
	"""Add chunks in rank order until MAX_DOCUMENT_TOKENS is used up."""
	if not chunks:
		return NO_MATCH_PROMPT
	parts, budget = [], MAX_DOCUMENT_TOKENS
	for chunk in chunks:
		part = f"[{chunk['source']}]\n{chunk['text']}"
		if estimate_tokens(part) > budget:
			part = truncate(part, budget)
		parts.append(part)
		budget -= estimate_tokens(part)
		if budget <= 0:
			break
	return CONTEXT_PROMPT.format(documents="\n\n".join(parts))


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

	def build_messages(
		self, session_id: str, chunks: list[dict] | None = None
	) -> list[dict[str, str]]:
		"""System prompt + as much recent history as fits + retrieved documents.

		History is added newest-first until the context window (minus room for
		the response and the documents) is full; the latest user message is
		always kept. Documents are attached to the latest user message because
		the small model follows them more reliably there than in a system message.
		"""
		system = {"role": "system", "content": LIBRARY_SYSTEM_PROMPT}
		documents = (
			f"{format_documents(chunks)}\nUser question: " if chunks is not None else ""
		)

		budget = (
			CONTEXT_WINDOW_TOKENS
			- RESPONSE_TOKENS
			- estimate_tokens(system["content"])
			- estimate_tokens(documents)
		)
		history = []
		for message in reversed(self.get_history(session_id)[-MAX_HISTORY_MESSAGES:]):
			cost = estimate_tokens(message["content"])
			if cost > budget:
				if not history:
					history.append({**message, "content": truncate(message["content"], budget)})
				break
			history.append(message)
			budget -= cost
		history.reverse()
		if documents and history and history[-1]["role"] == "user":
			history[-1] = {
				"role": "user",
				"content": documents + history[-1]["content"],
			}
		return [system, *history]
