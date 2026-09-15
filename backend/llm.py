import json

import httpx


class LLMEngine:
	def __init__(
		self,
		model: str = "qwen2.5:1.5b",
		api_url: str = "http://localhost:11434/api/chat",
	) -> None:
		self.model = model
		self.api_url = api_url

	def stream_response(self, messages: list[dict[str, str]]):
		payload = {
			"model": self.model,
			"messages": messages,
			"stream": True,
		}

		try:
			with httpx.Client(timeout=None) as client:
				with client.stream("POST", self.api_url, json=payload) as response:
					response.raise_for_status()

					for line in response.iter_lines():
						if not line:
							continue

						data = json.loads(line)
						text = data.get("message", {}).get("content", "")
						if text:
							yield text
		except httpx.ConnectError as error:
			raise RuntimeError(
				"Ollama is unavailable. Start Ollama and try again."
			) from error
		except httpx.HTTPStatusError as error:
			raise RuntimeError(
				f"Ollama returned an error: {error.response.status_code}"
			) from error
