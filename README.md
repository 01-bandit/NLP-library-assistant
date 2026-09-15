# Library Assistant

A local conversational AI system for a fictional university library. The application combines a plain HTML/CSS/JavaScript web interface with a FastAPI WebSocket backend and a locally hosted Qwen 2.5 1.5B model served by Ollama.

## 1. Project Overview

Library Assistant answers questions about a small fictional library catalogue and its borrowing policies. It maintains short conversation histories per session, streams model output to the browser, and keeps all model inference on the local machine.

This is a university assignment focused on conversational AI integration, WebSockets, streaming responses, and simple session-based context management.

## 2. Business Use Case

A university library can use a conversational assistant to answer common questions such as:

- Which books are currently available?
- Who wrote a particular catalogue book?
- How many books may a student borrow?
- How long is the standard borrowing period?

The assistant explains information but does not modify library accounts or perform real borrowing operations.

## 3. Features

- Fully local LLM inference through Ollama
- Qwen 2.5 1.5B model support
- Streaming responses over WebSockets
- FastAPI WebSocket endpoint at `/ws/chat`
- In-memory, session-based conversation memory
- Independent histories for different session IDs
- Library-specific system prompt
- Catalogue and borrowing-policy guidance
- Off-topic refusal or redirection
- New Chat session reset in the frontend
- Error messages for invalid input and backend/model failures
- Simple responsive HTML/CSS/JavaScript web interface
- Health endpoint at `/health`

## 4. System Architecture

```text
┌──────────────────────────┐
│     Web Chat Frontend    │
│       HTML/CSS/JS        │
└────────────┬─────────────┘
						 │ WebSocket
						 ▼
┌──────────────────────────┐
│       FastAPI            │
│       /ws/chat           │
└────────────┬─────────────┘
						 ▼
┌──────────────────────────┐
│   Conversation Manager   │
│  Sessions + History +    │
│    Prompt Orchestration  │
└────────────┬─────────────┘
						 ▼
┌──────────────────────────┐
│       LLM Engine         │
└────────────┬─────────────┘
						 │ HTTP
						 ▼
┌──────────────────────────┐
│         Ollama           │
│      Qwen 2.5 1.5B      │
└──────────────────────────┘
```

The browser sends JSON over a WebSocket. FastAPI passes the session history and library system prompt to `ConversationManager`, then passes the resulting messages to `LLMEngine`. `LLMEngine` calls Ollama's local `/api/chat` endpoint with streaming enabled. FastAPI forwards each generated chunk to the browser.

The Ollama HTTP client is synchronous, so the WebSocket handler advances the stream with `asyncio.to_thread()`. This keeps blocking model/network reads away from the FastAPI event loop and allows multiple connections to make progress.

## 5. Conversation Flow

1. The frontend creates a UUID session ID when the page loads.
2. The frontend opens a WebSocket connection to `/ws/chat`.
3. The user submits a message.
4. The frontend sends the session ID and message as JSON.
5. The backend creates the session if necessary.
6. The user's message is added to the session history.
7. The system prompt and recent history are passed to `LLMEngine`.
8. Ollama generates a streaming response using Qwen 2.5 1.5B.
9. Each text chunk is sent to the browser as a `token` message.
10. After the stream ends, the complete assistant response is stored and a `done` message is sent.

## 6. Model Selection and Justification

The project uses `qwen2.5:1.5b`, a compact Qwen 2.5 model available through Ollama.

It was selected because:

- It can run locally without cloud APIs.
- Its smaller size is appropriate for a laptop-based assignment.
- It is fast enough to demonstrate streaming responses.
- It supports general question answering and instruction following.
- It makes the complete system easier to install and explain.

The model is used through Ollama's local HTTP API at:

```text
http://localhost:11434/api/chat
```

## 7. Context/Memory Management

`ConversationManager` stores conversations in a Python dictionary:

```python
session_id -> list of message dictionaries
```

Each message has this structure:

```json
{
	"role": "user",
	"content": "What books are available?"
}
```

`build_messages(session_id)` returns the library system prompt first, followed by the most recent 10 conversation messages. The complete assistant response is added only after streaming finishes.

The frontend creates a new UUID for New Chat, clears the visible messages, closes the old WebSocket, and opens a connection for the new session when the next message is sent. No conversation data is stored in localStorage, sessionStorage, cookies, or a database.

## 8. Project Structure

```text
library-assistant/
├── README.md
├── requirements.txt
├── backend/
│   ├── benchmark_websocket.py
│   ├── conversation.py
│   ├── llm.py
│   ├── main.py
│   ├── prompts.py
│   ├── test_conversation.py
│   ├── test_llm.py
│   ├── test_websocket.py
│   └── test_websocket_failures.py
└── frontend/
		├── app.js
		├── index.html
		└── style.css
```

### Main modules

- `backend/main.py`: FastAPI application, health route, and WebSocket route.
- `backend/conversation.py`: In-memory sessions and context-window handling.
- `backend/llm.py`: Local Ollama streaming client.
- `backend/prompts.py`: Fictional library system prompt, catalogue, and policies.
- `frontend/app.js`: WebSocket client, session handling, and streaming UI updates.

## 9. Requirements

- Python 3.10 or newer recommended
- Ollama installed and running
- Qwen model downloaded in Ollama
- A browser with WebSocket support
- Python packages listed in `requirements.txt`

The project dependencies are:

```text
fastapi
uvicorn[standard]
httpx
websockets
pytest
```

## 10. Installation

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start Ollama and download the model if needed:

```powershell
ollama pull qwen2.5:1.5b
ollama serve
```

The Ollama service should be available at `http://localhost:11434` before starting a chat request.

## 11. Running the Backend

From the project root, start FastAPI:

```powershell
uvicorn backend.main:app --reload
```

The backend runs at:

```text
http://localhost:8000
```

Check its health endpoint:

```powershell
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 12. Running the Frontend

Do not open `index.html` directly with `file://`. Serve the frontend over HTTP from a second terminal:

```powershell
python -m http.server 5500 --directory frontend
```

Open this address in a browser:

```text
http://localhost:5500
```

Keep both Ollama and the FastAPI backend running while using the frontend.

## 13. WebSocket API Format

### Endpoint

```text
ws://localhost:8000/ws/chat
```

### Client message

```json
{
	"session_id": "some-session-id",
	"message": "What books are available?"
}
```

### Streaming token response

```json
{
	"type": "token",
	"content": "The Hobbit"
}
```

The frontend appends each `content` value to the current assistant message immediately.

### Completion response

```json
{
	"type": "done"
}
```

### Error response

```json
{
	"type": "error",
	"message": "Message must be a non-empty string."
}
```

## 14. Example Dialogues

### Example 1: Catalogue availability

```text
User: What books are available?
Assistant: The Hobbit, Clean Code, and Harry Potter and the Philosopher's Stone are available.
```

### Example 2: Conversation context

```text
User: I want to know about Clean Code.
Assistant: Clean Code is a programming book by Robert C. Martin, and it is available.
User: Who wrote it?
Assistant: Clean Code was written by Robert C. Martin.
```

### Example 3: Borrowing policy

```text
User: How many books may a student borrow?
Assistant: A student may borrow up to 3 books. The standard borrowing period is 14 days.
```

## 15. Off-topic Handling

The system prompt restricts the assistant to the library domain. For unrelated questions, it should politely refuse or redirect the user.

```text
User: What's the weather in Islamabad?
Assistant: I can only help with library-related questions, such as books, catalogue availability, or borrowing policies.
```

The assistant is also instructed not to invent books, catalogue information, availability, or library policies. The catalogue and policies in `prompts.py` are fictional assignment data, not a connection to a real library system.

## 16. Testing

Run the standalone conversation test:

```powershell
python backend/test_conversation.py
```

It checks session creation, message storage, system-prompt inclusion, the ten-message history limit, and reset behavior.

Run the local Ollama streaming test:

```powershell
python backend/test_llm.py
```

With the FastAPI backend running, run the WebSocket integration test:

```powershell
python backend/test_websocket.py
```

It sends two messages with the same session ID, prints streamed JSON frames, and checks that responses complete.

Run the WebSocket failure test:

```powershell
python backend/test_websocket_failures.py
```

It checks invalid JSON, missing messages, empty messages, and a client closing during a response. It also checks `/health` after each case.

## 17. Latency Benchmark

Run the benchmark while the FastAPI backend and Ollama are running:

```powershell
python backend/benchmark_websocket.py
```

Record the values from your own machine here. Do not compare them directly with another machine because model loading, hardware, Ollama state, and prompt length affect the results.

| Measurement | Value |
|---|---|
| Time to first token | `[YOUR VALUE] ms` |
| Total response time | `[YOUR VALUE] s` |
| Received chunks | `[YOUR VALUE]` |
| Received characters | `[YOUR VALUE]` |
| Estimated tokens | `[YOUR VALUE]` |
| Estimated tokens per second | `[YOUR VALUE]` |

The script estimates tokens as approximately `characters / 4`. This is only a rough estimate because the application receives text chunks rather than tokenizer-level token IDs.

## 18. Failure Handling

- If Ollama is unavailable, `LLMEngine` raises a clear runtime error.
- Ollama HTTP errors are converted into a readable error message.
- Invalid JSON sent over the WebSocket returns an error frame when possible.
- Missing or empty messages return an error frame without starting generation.
- A client disconnect during streaming is handled without crashing the server.
- The frontend displays connection, disconnection, and assistant error states.
- The backend exposes `/health` so its availability can be checked independently.

## 19. Known Limitations

- Sessions are stored only in process memory and disappear when the backend restarts.
- There is no database, Redis layer, or durable conversation history.
- The history context is limited to the most recent 10 messages; summarization is not implemented.
- The catalogue and policies are fictional and hard-coded in the system prompt.
- The assistant cannot check or modify a real library account.
- The character-based token estimate is approximate.
- The default WebSocket URL assumes the frontend and backend run on localhost with the documented ports.
- There is no authentication or per-user access control.
- The small local model may produce imperfect or repetitive answers.

## 20. Future Improvements

Possible future work includes:

- Replace in-memory storage with a persistent session store if required.
- Add real catalogue and account-service integration behind an authenticated API.
- Add configurable backend and WebSocket URLs for deployment environments.
- Add automated browser tests and broader automated API tests.
- Add proper tokenizer-based token measurements.
- Improve reconnect and retry behavior for temporary network failures.
- Add conversation summarization for longer sessions.
- Add monitoring and structured logging for production deployments.

These improvements are outside the scope of the current assignment. The current implementation intentionally remains local, small, and easy to explain.
