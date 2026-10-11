import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import main as server
from backend.build_index import chunk_document
from backend.conversation import (
	CONTEXT_WINDOW_TOKENS,
	RESPONSE_TOKENS,
	ConversationManager,
	estimate_tokens,
)
from backend.prompts import NO_MATCH_PROMPT
from backend.retrieval import Retriever


def check(name: str, condition: bool) -> None:
	if not condition:
		raise AssertionError(name)
	print(f"{name}: PASS")


def main() -> None:
	chunks = chunk_document("# Title\n\n" + "\n\n".join(["word " * 100] * 5))
	check("Chunking", len(chunks) > 1 and all(c.startswith("# Title") for c in chunks))

	retriever = Retriever()
	results = retriever.search("How much is the fine for an overdue book?")
	check("Relevant retrieval", len(results) >= 3 and results[0]["source"] == "fines-and-fees.md")
	check("No match for off-topic query", retriever.search("best pizza recipe") == [])

	start = time.perf_counter()
	retriever.search("How much is the fine for an overdue book?")
	check("Cached query", (time.perf_counter() - start) < 0.01)

	manager = ConversationManager()
	session_id = manager.create_session()
	manager.add_message(session_id, "user", "best pizza recipe")
	check(
		"No-match prompt",
		manager.build_messages(session_id, [])[-1]["content"]
		== f"{NO_MATCH_PROMPT}\nUser question: best pizza recipe",
	)

	huge = [{"source": "big.md", "text": "x" * 50_000}] * 4
	for _ in range(6):
		manager.add_message(session_id, "assistant", "y" * 8_000)
		manager.add_message(session_id, "user", "z" * 8_000)
	messages = manager.build_messages(session_id, huge)
	used = sum(estimate_tokens(m["content"]) for m in messages)
	check(
		"Context window not exceeded",
		used <= CONTEXT_WINDOW_TOKENS - RESPONSE_TOKENS + len(messages)
		and messages[-1]["content"].endswith("z"),
	)

	class BrokenRetriever:
		def search(self, query):
			raise RuntimeError("vector store down")

	class SlowRetriever:
		def search(self, query):
			time.sleep(5)

	server.retriever = BrokenRetriever()
	check("Retrieval failure falls back", asyncio.run(server.retrieve("fines")) == [])
	server.retriever = SlowRetriever()
	server.RETRIEVAL_TIMEOUT_SECONDS = 0.5
	check("Retrieval timeout falls back", asyncio.run(server.retrieve("fines")) == [])


if __name__ == "__main__":
	try:
		main()
	except AssertionError as error:
		print(f"Test failed: {error}")
		raise SystemExit(1)
