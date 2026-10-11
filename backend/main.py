import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .conversation import ConversationManager
from .llm import LLMEngine
from .retrieval import Retriever

RETRIEVAL_TIMEOUT_SECONDS = 2.0

conversation_manager = ConversationManager()
llm_engine = LLMEngine()
retriever = Retriever()


@asynccontextmanager
async def lifespan(app: FastAPI):
	# Load the index and embedding model once so the first query is not slow.
	try:
		await asyncio.to_thread(retriever.load)
	except Exception as error:
		print(f"Retriever unavailable, continuing without RAG: {error}")
	yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)


def get_next_chunk(stream):
	try:
		return next(stream)
	except StopIteration:
		return None


async def retrieve(query: str) -> list[dict]:
	"""Retrieve in a worker thread; on failure or timeout, fall back to no context."""
	try:
		return await asyncio.wait_for(
			asyncio.to_thread(retriever.search, query), RETRIEVAL_TIMEOUT_SECONDS
		)
	except Exception as error:
		print(f"Retrieval failed, answering without documents: {error!r}")
		return []


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok"}


@app.websocket("/ws/chat")
async def chat(websocket: WebSocket) -> None:
	await websocket.accept()

	try:
		while True:
			request = await websocket.receive_json()
			session_id = request.get("session_id")
			message = request.get("message")

			if not isinstance(session_id, str) or not session_id:
				session_id = conversation_manager.create_session()
			elif session_id not in conversation_manager.conversations:
				conversation_manager.conversations[session_id] = []

			if not isinstance(message, str) or not message.strip():
				await websocket.send_json(
					{"type": "error", "message": "Message must be a non-empty string."}
				)
				continue

			# Include the previous user message so follow-ups such as
			# "for how many days?" still retrieve the right documents.
			previous = next(
				(m["content"] for m in reversed(conversation_manager.get_history(session_id)) if m["role"] == "user"),
				"",
			)
			chunks = await retrieve(f"{previous} {message}".strip())
			conversation_manager.add_message(session_id, "user", message)
			stream = iter(
				llm_engine.stream_response(
					conversation_manager.build_messages(session_id, chunks)
				)
			)
			assistant_response = []

			while True:
				# Keep synchronous HTTP reads off the FastAPI event loop.
				chunk = await asyncio.to_thread(get_next_chunk, stream)
				if chunk is None:
					break
				assistant_response.append(chunk)
				await websocket.send_json({"type": "token", "content": chunk})

			conversation_manager.add_message(
				session_id, "assistant", "".join(assistant_response)
			)
			sources = list(dict.fromkeys(c["source"] for c in chunks))
			await websocket.send_json({"type": "done", "sources": sources})
	except WebSocketDisconnect:
			return
	except Exception as error:
			try:
				await websocket.send_json({"type": "error", "message": str(error)})
			except Exception:
				return
