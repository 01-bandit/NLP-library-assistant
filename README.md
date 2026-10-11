# Library Assistant

A local conversational AI system for a fictional university library. The application combines a plain HTML/CSS/JavaScript web interface with a FastAPI WebSocket backend and a locally hosted Qwen 2.5 1.5B model served by Ollama. Assignment 2 adds Retrieval-Augmented Generation (RAG): answers are grounded in a collection of 71 library documents that are chunked, embedded and indexed offline, then retrieved for every user message.

## 1. Project Overview

Library Assistant answers questions about the fictional Northbridge University Library: its catalogue, borrowing policies, fines and services. Library facts come from retrieved documents rather than from the system prompt. It maintains short conversation histories per session, streams model output to the browser, and keeps all model inference on the local machine.

This is a university assignment series. Assignment 1 built the conversational core (WebSockets, streaming, session memory). Assignment 2 (this version) adds Retrieval-Augmented Generation over a document collection; the hard-coded catalogue and policies from Assignment 1's system prompt were removed, and all library facts now come from `data/documents/`.

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
- RAG over 71 documents (36 catalogue records, 35 policy/service/FAQ pages)
- Offline, re-runnable indexing pipeline (`all-MiniLM-L6-v2` + FAISS)
- Top-k retrieval with a relevance threshold and graceful "no match" fallback
- Explicit token budget so documents + history never overflow the context window
- Retrieval timeout/failure fallback, query result caching
- Visible citations: source documents shown under each answer (bonus)

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
│   Conversation Manager   │      ┌──────────────────────────┐
│  Sessions + History +    │─────▶│    Retrieval Module      │
│    Prompt Orchestration  │◀─────│ MiniLM embedding + FAISS │
└────────────┬─────────────┘ top-k └────────────▲─────────────┘
                                                 │ loads
                                   ┌─────────────┴────────────┐
                                   │ data/index (built offline │
                                   │ by backend/build_index.py)│
                                   └──────────────────────────┘
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
6. The message (together with the previous user message, so follow-ups work) is embedded and the top-k relevant chunks are retrieved (in a worker thread, with a timeout).
7. The user's message is added to the session history.
8. The system prompt, recent history and retrieved chunks are combined within the token budget and passed to `LLMEngine`.
9. Ollama generates a streaming response using Qwen 2.5 1.5B.
10. Each text chunk is sent to the browser as a `token` message.
11. After the stream ends, the complete assistant response is stored and a `done` message (with the source file names) is sent.

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

`build_messages(session_id, chunks)` returns the library system prompt first, followed by as many of the most recent 10 conversation messages as fit in the token budget (see the RAG section). The retrieved documents are attached to the latest user message. The complete assistant response is added only after streaming finishes.

The frontend creates a new UUID for New Chat, clears the visible messages, closes the old WebSocket, and opens a connection for the new session when the next message is sent. No conversation data is stored in localStorage, sessionStorage, cookies, or a database.

## 8. Retrieval-Augmented Generation (Assignment 2)

### Document collection

`data/documents/` holds 71 Markdown documents written for this assistant:

- `catalogue/` (36): one record per book with author, year, subject, call number, branch/floor, copies held, availability, return dates and holds.
- `policies/` (35): borrowing, renewals, holds, fines, paying fines, lost/damaged items, overdue notices, membership types, opening hours, holiday closures, returns, course reserves, interlibrary loan, study rooms, printing, laptops, e-resources, research help, accessibility, FAQs and more.

The facts (for example PKR 20/day fines, a one-day grace period, a PKR 1,500 cap, Science Library hours) are specific to this fictional library, so a grounded answer is clearly different from what the model would guess.

### Architecture

```text
Offline:  data/documents/*.md ──chunk──▶ all-MiniLM-L6-v2 ──▶ FAISS IndexFlatIP ──▶ data/index/
                                                                      (index.faiss, embeddings.npy, chunks.json)

Online:   Web UI ◀──WebSocket──▶ FastAPI /ws/chat
                                    │ 1. retrieve(previous + message)  [thread + 2 s timeout, LRU cache]
                                    ▼
                              Retrieval Module ──▶ top-4 chunks with cosine ≥ 0.35
                                    │ 2. build_messages(session, chunks)  [token budget]
                                    ▼
                           Conversation Manager ──▶ LLM Engine ──▶ Ollama qwen2.5:1.5b
                                    │ 3. stream tokens, then {"type":"done","sources":[...]}
```

### Embedding model and vector store

- **Embedding model: `sentence-transformers/all-MiniLM-L6-v2`.** It is small (22M parameters, 384-dimensional vectors, ~90 MB), runs on CPU, embeds a query in a few milliseconds, and performs well on short semantic-search passages like ours.
- **Vector store: FAISS (`faiss-cpu`), `IndexFlatIP`.** Embeddings are L2-normalised, so inner product equals cosine similarity. With ~80 chunks, exact (flat) search takes well under a millisecond, so an approximate index would add complexity for no gain. FAISS is a single pip package with no server process, unlike Chroma.

### Indexing pipeline

```powershell
python -m backend.build_index
```

`backend/build_index.py` reads every `*.md` file under `data/documents/`, chunks it, embeds the chunks and writes `data/index/`. It is **re-runnable**: each chunk's SHA-256 hash is stored, and on the next run only new or edited chunks are embedded; the rest reuse their saved embeddings. Deleted documents simply drop out. Example output after editing the 36 catalogue files:

```text
Indexed 80 chunks from 71 documents (37 newly embedded, 43 reused).
```

### Chunking and top-k

- **Chunking:** paragraph-based. Paragraphs are merged until a chunk would exceed **800 characters** (~200 tokens, within MiniLM's 256-token input limit). Every chunk is prefixed with its document title (`# Fines and Fees`), so a chunk taken from the middle of a document still says what it is about. No overlap is needed because chunks never split a paragraph. Most documents fit in one chunk; the 71 documents produce 80 chunks.
- **Top-k = 4**, with a **minimum cosine similarity of 0.35**. Chunks below the threshold are discarded, so off-topic questions (for example "best pizza recipe") retrieve nothing instead of a weak, misleading match.

### Context-window strategy

Ollama is called with `num_ctx = 4096`. `conversation.py` estimates tokens as `characters / 4` and allocates:

| Part | Budget |
|---|---|
| Reserved for the response | 1,024 tokens |
| System prompt | ~170 tokens (always included) |
| Retrieved documents | at most 1,200 tokens; chunks are added in rank order and the last one is truncated if needed |
| Conversation history | whatever is left (~1,700 tokens), filled newest-first, at most 10 messages |

The latest user message is always kept (truncated only if it alone is larger than the remaining budget), and older history is dropped first. This guarantees that a large chunk combined with a long history can never overflow the context window. The documents are placed in the latest user turn, because `qwen2.5:1.5b` followed them noticeably more reliably there than in a second system message.

### Grounding and citations

The prompt asks the model to answer from the documents and cite the source file in square brackets, for example `[fines-and-fees.md]`. The `done` frame also carries the list of retrieved source files, and the web UI shows them under the answer as **"Sources: …"** (bonus: visible citations). Generation uses `temperature = 0.1` to keep answers close to the documents.

### Real-time behaviour

- **Startup warm-up:** the FAISS index and the embedding model are loaded once at startup, so the first user does not pay the model-loading cost.
- **Non-blocking:** retrieval runs in `asyncio.to_thread()`, like LLM streaming, so the event loop keeps serving other WebSocket clients.
- **Caching:** results are cached per normalised query (lower-cased, whitespace-collapsed) in an LRU cache of 512 entries. A repeated question skips embedding and search entirely.
- **Streaming:** the WebSocket contract is unchanged: `token` frames followed by `done`. `done` only gains an optional `sources` field, which older clients ignore.

### Retrieval latency benchmark

Measured on CPU, separately from generation, with `python -m backend.benchmark_retrieval`:

| Measurement | Value |
|---|---|
| Index + model load (once, at startup) | 1.37 s |
| Uncached query (embed + search), average | 29.3 ms |
| Uncached query, worst case | 93.4 ms |
| Cached query | 0.005 ms |
| 8 concurrent uncached queries (wall clock) | 196 ms |

Retrieval is well under the 1-second target; even 8 simultaneous queries finish in under 0.2 s. End-to-end time is dominated by the LLM (see the latency benchmark below).

### RAG failure handling

| Failure | Behaviour |
|---|---|
| No relevant match (all scores < 0.35) | No documents are injected; the model is told nothing matched and to say it could not find the information instead of guessing. No sources are shown. |
| Vector store or embedding error (for example a missing index) | `retrieve()` catches the exception, logs it and continues with no documents, so the chat still works as a normal conversation. Startup also continues if the index cannot be loaded. |
| Retrieval timeout | `asyncio.wait_for(..., 2 s)`; on timeout the answer is generated without documents. |
| Documents + history would overflow the context | The token budget truncates documents and drops the oldest history (see above). |

### Grounded vs ungrounded example

```text
User: How much is the late fine for a standard book?
Assignment 1 (no RAG): the fine amount is not in the prompt, so the model can only guess or say it doesn't know.
Assignment 2 (RAG):    The late fine for a standard book is PKR 20 per day. This fine accrues after a
                       one-day grace period and is capped at PKR 1,500 per book.
                       Sources: fines-and-fees.md, lost-and-damaged-items.md, faq-borrowing.md, paying-fines.md

User: Can I bring a laptop back to the book drop?
Assistant: No, laptops cannot be returned at the book drop. They must be returned at the circulation
           desk in person, as they can be damaged in the drop box.
           Sources: returning-items.md, laptop-loans.md, ...
```

## 9. Project Structure

```text
library-assistant/
├── README.md
├── requirements.txt
├── backend/
│   ├── benchmark_retrieval.py
│   ├── benchmark_websocket.py
│   ├── build_index.py
│   ├── conversation.py
│   ├── llm.py
│   ├── main.py
│   ├── prompts.py
│   ├── retrieval.py
│   ├── test_conversation.py
│   ├── test_llm.py
│   ├── test_retrieval.py
│   ├── test_websocket.py
│   └── test_websocket_failures.py
├── data/
│   ├── documents/
│   │   ├── catalogue/   (36 book records)
│   │   └── policies/    (35 policy, service and FAQ pages)
│   └── index/           (generated by build_index.py, git-ignored)
└── frontend/
		├── app.js
		├── index.html
		└── style.css
```

### Main modules

- `backend/main.py`: FastAPI application, health route, and WebSocket route.
- `backend/conversation.py`: In-memory sessions and context-window handling.
- `backend/llm.py`: Local Ollama streaming client.
- `backend/prompts.py`: System prompt plus the document-context and no-match prompts.
- `backend/retrieval.py`: Embedding model, FAISS index loading, top-k search and result cache.
- `backend/build_index.py`: Offline chunking, embedding and indexing pipeline.
- `frontend/app.js`: WebSocket client, session handling, and streaming UI updates.

## 10. Requirements

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
sentence-transformers
faiss-cpu
```

`sentence-transformers` installs PyTorch (CPU), so the first install is large. The embedding model (~90 MB) is downloaded from Hugging Face on the first run of the indexing pipeline.

## 11. Installation

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

Build the document index (re-run whenever documents change):

```powershell
python -m backend.build_index
```

## 12. Running the Backend

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

## 13. Running the Frontend

Do not open `index.html` directly with `file://`. Serve the frontend over HTTP from a second terminal:

```powershell
python -m http.server 5500 --directory frontend
```

Open this address in a browser:

```text
http://localhost:5500
```

Keep both Ollama and the FastAPI backend running while using the frontend.

## 14. WebSocket API Format

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
	"type": "done",
	"sources": ["fines-and-fees.md", "faq-borrowing.md"]
}
```

`sources` lists the documents the answer was grounded in (empty when nothing relevant was found). The rest of the contract is unchanged from Assignment 1.

### Error response

```json
{
	"type": "error",
	"message": "Message must be a non-empty string."
}
```

## 15. Example Dialogues

Real outputs from the running system (`qwen2.5:1.5b`, RAG enabled). The source list is what the UI shows under each answer.

### Example 1: Grounded policy answer

```text
User: How much is the late fine for a standard book?
Assistant: The late fine for a standard book is PKR 20 per day. This fine accrues after a one-day
           grace period and is capped at PKR 1,500 per book.
Sources: fines-and-fees.md, lost-and-damaged-items.md, faq-borrowing.md, paying-fines.md
```

### Example 2: Follow-up using conversation memory

```text
User: How many books can a postgraduate borrow
Assistant: A postgraduate student can borrow up to 8 books at a time for 28 days.
User: for how many days/
Assistant: For postgraduate students, the borrowing policy allows up to 8 books at a time for 28 days.
Sources: borrowing-policy.md, ...
```

### Example 3: Rule that the model could not guess

```text
User: Can I bring a laptop back to the book drop?
Assistant: No, laptops cannot be returned at the book drop. They must be returned at the circulation
           desk in person, as they can be damaged in the drop box.
Sources: returning-items.md, laptop-loans.md, ...
```

## 16. Off-topic Handling

The system prompt restricts the assistant to the library domain. Off-topic questions retrieve no documents (every score is below the 0.35 threshold), so no sources are shown and the model receives the no-match instruction to decline and offer library help instead.

```text
User: What's the best pizza recipe?
(retrieval: 0 chunks, no sources)
```

The small model does not always follow this instruction: it may still answer simple general-knowledge questions (see Known Limitations). It is instructed never to invent books, availability, policies or fees. The documents in `data/documents/` are fictional assignment data, not a connection to a real library system.

## 17. Testing

Run the standalone conversation test:

```powershell
python backend/test_conversation.py
```

It checks session creation, message storage, system-prompt inclusion, the ten-message history limit, and reset behavior.

Run the retrieval tests (no server or Ollama needed, index must be built):

```powershell
python backend/test_retrieval.py
```

They check chunking, relevant retrieval (at least 3 chunks, correct top source), no match for off-topic queries, caching, the no-match prompt, that a huge chunk plus a long history stays within the context budget, and the fallback when the vector store raises an error or times out.

Run the retrieval latency benchmark:

```powershell
python -m backend.benchmark_retrieval
```

Run the local Ollama streaming test:

```powershell
python backend/test_llm.py
```

With the FastAPI backend running, run the WebSocket integration test:

```powershell
python backend/test_websocket.py
```

It sends a question and a follow-up with the same session ID, prints streamed JSON frames, and checks that responses complete and that the `done` frame cites the expected source documents.

Run the WebSocket failure test:

```powershell
python backend/test_websocket_failures.py
```

It checks invalid JSON, missing messages, empty messages, and a client closing during a response. It also checks `/health` after each case.

## 18. Latency Benchmark

Run the benchmark while the FastAPI backend and Ollama are running:

```powershell
python backend/benchmark_websocket.py
```

Record the values from your own machine here. Do not compare them directly with another machine because model loading, hardware, Ollama state, and prompt length affect the results.

| Measurement | Value |
|---|---|
| Time to first token | 2821.21 ms |
| Total response time | 10.71 s |
| Received chunks | 398 |
| Received characters | 1798 |
| Estimated tokens | 450 |
| Estimated tokens per second | 41.96 |

These values include retrieval (~30 ms), which is a small fraction of the time to first token; the rest is prompt processing and generation in Ollama. With 3 concurrent clients asking different questions, all received tokens and completed; first-token times rise because Ollama serves the requests in turn on one CPU/GPU.

The script estimates tokens as approximately `characters / 4`. This is only a rough estimate because the application receives text chunks rather than tokenizer-level token IDs.

## 19. Failure Handling

- If Ollama is unavailable, `LLMEngine` raises a clear runtime error.
- Ollama HTTP errors are converted into a readable error message.
- Invalid JSON sent over the WebSocket returns an error frame when possible.
- Missing or empty messages return an error frame without starting generation.
- A client disconnect during streaming is handled without crashing the server.
- The frontend displays connection, disconnection, and assistant error states.
- The backend exposes `/health` so its availability can be checked independently.
- RAG-specific failures (no match, vector store error, timeout, context overflow) are described in the RAG section above.

## 20. Known Limitations

- Sessions are stored only in process memory and disappear when the backend restarts.
- There is no database, Redis layer, or durable conversation history.
- The history context is limited to the most recent 10 messages; summarization is not implemented.
- The catalogue and policies are fictional; availability is a static snapshot in the documents, not live data.
- `qwen2.5:1.5b` is small and sometimes misreads grounded facts. It has a strong "yes" bias for availability questions: it may say a book is available while repeating that all copies are on loan. A larger model would follow the documents more reliably.
- Off-topic refusal is weak: with no documents retrieved, the model may still answer general-knowledge questions (for example "What is the capital of France?").
- For follow-ups, retrieval combines the previous and the latest user message (e.g. "How many books can a postgraduate borrow" + "for how many days?"). Topic switches may therefore pull in one or two chunks about the previous topic.
- Token counts are estimated as characters / 4, not with the real tokenizer.
- The result cache is in memory and cleared on restart; the index must be rebuilt manually after documents change.
- The assistant cannot check or modify a real library account.
- The character-based token estimate is approximate.
- The default WebSocket URL assumes the frontend and backend run on localhost with the documented ports.
- There is no authentication or per-user access control.
- The small local model may produce imperfect or repetitive answers.

## 21. Future Improvements

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
