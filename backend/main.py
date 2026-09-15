import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .conversation import ConversationManager
from .llm import LLMEngine


app = FastAPI()
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)

conversation_manager = ConversationManager()
llm_engine = LLMEngine()


def get_next_chunk(stream):
	try:
		return next(stream)
	except StopIteration:
		return None


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

			conversation_manager.add_message(session_id, "user", message)
			stream = iter(
				llm_engine.stream_response(
					conversation_manager.build_messages(session_id)
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
			await websocket.send_json({"type": "done"})
	except WebSocketDisconnect:
			return
	except Exception as error:
			try:
				await websocket.send_json({"type": "error", "message": str(error)})
			except Exception:
				return
