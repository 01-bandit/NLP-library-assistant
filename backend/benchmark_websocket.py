import asyncio
import json
import time
from uuid import uuid4

import websockets


URI = "ws://localhost:8000/ws/chat"
PROMPT = "Explain the library borrowing policy in detail."


async def main() -> None:
	try:
		async with websockets.connect(URI) as socket:
			request = {"session_id": str(uuid4()), "message": PROMPT}
			start = time.perf_counter()
			await socket.send(json.dumps(request))

			first_token_time = None
			response_parts = []
			chunk_count = 0

			while True:
				data = json.loads(await socket.recv())

				if data.get("type") == "token":
					if first_token_time is None:
						first_token_time = time.perf_counter()
					response_parts.append(data.get("content", ""))
					chunk_count += 1
				elif data.get("type") == "error":
					raise RuntimeError(data.get("message", "Unknown server error"))
				elif data.get("type") == "done":
					break

			end = time.perf_counter()

		response = "".join(response_parts)
		characters = len(response)
		estimated_tokens = characters / 4
		first_token_ms = (
			(first_token_time - start) * 1000 if first_token_time else None
		)
		total_time = end - start

		print("Library Assistant WebSocket Benchmark")
		print(f"Prompt: {PROMPT}")
		print(
			f"Time to first token: "
			f"{first_token_ms:.2f} ms" if first_token_ms else "No token received"
		)
		print(f"Total response time: {total_time:.2f} s")
		print(f"Received chunks: {chunk_count}")
		print(f"Received characters: {characters}")
		print(f"Estimated tokens: {estimated_tokens:.0f} (characters / 4)")
		if estimated_tokens and total_time:
			print(f"Estimated tokens per second: {estimated_tokens / total_time:.2f}")
	except Exception as error:
		print(f"Benchmark failed: {error}")
		raise SystemExit(1)


if __name__ == "__main__":
	asyncio.run(main())