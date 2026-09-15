from llm import LLMEngine


engine = LLMEngine(model="qwen2.5:1.5b")
messages = [
	{"role": "system", "content": "You are a helpful library assistant."},
	{"role": "user", "content": "Suggest one good book for learning Python."},
]

try:
	for chunk in engine.stream_response(messages):
		print(chunk, end="", flush=True)
	print()
except RuntimeError as error:
	print(f"LLM integration test failed: {error}")
