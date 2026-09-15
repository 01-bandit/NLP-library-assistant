import asyncio
import json
from urllib.request import urlopen

import websockets


URI = "ws://localhost:8000/ws/chat"


async def print_server_result(socket) -> None:
	try:
		result = await socket.recv()
		print(f"Server returned: {result}")
	except websockets.ConnectionClosed as error:
		print(f"Server closed the connection: {error}")


async def check_server() -> None:
	with urlopen("http://localhost:8000/health") as response:
		print(f"Health check: {response.read().decode()}")


async def invalid_json() -> None:
	print("\n1. Invalid JSON")
	async with websockets.connect(URI) as socket:
		await socket.send("not valid JSON")
		await print_server_result(socket)
	await check_server()


async def missing_message() -> None:
	print("\n2. Missing message field")
	async with websockets.connect(URI) as socket:
		await socket.send(json.dumps({"session_id": "failure-test"}))
		await print_server_result(socket)
	await check_server()


async def empty_message() -> None:
	print("\n3. Empty message")
	async with websockets.connect(URI) as socket:
		await socket.send(
			json.dumps({"session_id": "failure-test", "message": ""})
		)
		await print_server_result(socket)
	await check_server()


async def close_during_response() -> None:
	print("\n4. Close during response")
	socket = await websockets.connect(URI)
	try:
		await socket.send(
			json.dumps(
				{
					"session_id": "close-test",
					"message": "What books are available?",
				}
			)
		)
		print("Closing the client while the response is streaming.")
		await socket.close()
	finally:
		await check_server()


async def main() -> None:
	try:
		await invalid_json()
		await missing_message()
		await empty_message()
		await close_during_response()
		print("\nFailure tests completed; server is still running.")
	except Exception as error:
		print(f"Failure test error: {error}")
		raise SystemExit(1)


if __name__ == "__main__":
	asyncio.run(main())