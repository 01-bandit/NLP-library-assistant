import asyncio
import json

import websockets


async def receive_response(socket) -> None:
	has_token = False
	has_done = False

	while not has_done:
		message = json.loads(await socket.recv())
		print(json.dumps(message))

		if message.get("type") == "token":
			has_token = True
		elif message.get("type") == "done":
			has_done = True
		elif message.get("type") == "error":
			raise RuntimeError(message.get("message", "Unknown server error"))

	if not has_token:
		raise RuntimeError("The server returned no token messages.")


async def main() -> None:
	uri = "ws://localhost:8000/ws/chat"
	session_id = "test-session"

	try:
		async with websockets.connect(uri) as socket:
			print("Connected")

			await socket.send(
				json.dumps(
					{
						"session_id": session_id,
						"message": "What books are available?",
					}
				)
			)
			await receive_response(socket)

			print("\nSending second message...")
			await socket.send(
				json.dumps(
					{
						"session_id": session_id,
						"message": "Who wrote Clean Code?",
					}
				)
			)
			await receive_response(socket)

		print("\nTest completed")
	except Exception as error:
		print(f"WebSocket test failed: {error}")
		raise SystemExit(1)


if __name__ == "__main__":
	asyncio.run(main())