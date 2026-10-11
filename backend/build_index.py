"""Offline indexing pipeline: python -m backend.build_index

Re-runnable: embeddings of unchanged chunks are reused from the previous run,
so only new or edited documents are embedded again.
"""
import hashlib
import json

import faiss
import numpy as np

from .retrieval import INDEX_DIR, ROOT, embed

DOCS_DIR = ROOT / "data" / "documents"
CHUNK_CHARS = 800


def chunk_document(text: str) -> list[str]:
	"""Merge paragraphs up to CHUNK_CHARS and prefix each chunk with the title."""
	title = text.strip().splitlines()[0].lstrip("# ").strip()
	chunks, current = [], ""
	for paragraph in (p.strip() for p in text.split("\n\n") if p.strip()):
		if current and len(current) + len(paragraph) > CHUNK_CHARS:
			chunks.append(current)
			current = ""
		current = f"{current}\n\n{paragraph}".strip()
	if current:
		chunks.append(current)
	return [c if c.startswith("# ") else f"# {title}\n\n{c}" for c in chunks]


def text_hash(text: str) -> str:
	return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_previous() -> dict[str, np.ndarray]:
	try:
		chunks = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
		vectors = np.load(INDEX_DIR / "embeddings.npy")
		return {chunk["hash"]: vector for chunk, vector in zip(chunks, vectors)}
	except (FileNotFoundError, ValueError):
		return {}


def main() -> None:
	chunks = [
		{"source": path.name, "text": text, "hash": text_hash(text)}
		for path in sorted(DOCS_DIR.rglob("*.md"))
		for text in chunk_document(path.read_text(encoding="utf-8"))
	]
	previous = load_previous()
	new_chunks = [c for c in chunks if c["hash"] not in previous]
	if new_chunks:
		vectors = embed([c["text"] for c in new_chunks])
		previous.update({c["hash"]: v for c, v in zip(new_chunks, vectors)})
	embeddings = np.array([previous[c["hash"]] for c in chunks], dtype="float32")

	index = faiss.IndexFlatIP(embeddings.shape[1])
	index.add(embeddings)

	INDEX_DIR.mkdir(parents=True, exist_ok=True)
	faiss.write_index(index, str(INDEX_DIR / "index.faiss"))
	np.save(INDEX_DIR / "embeddings.npy", embeddings)
	(INDEX_DIR / "chunks.json").write_text(json.dumps(chunks, indent=1), encoding="utf-8")
	print(
		f"Indexed {len(chunks)} chunks from {len({c['source'] for c in chunks})} "
		f"documents ({len(new_chunks)} newly embedded, "
		f"{len(chunks) - len(new_chunks)} reused)."
	)


if __name__ == "__main__":
	main()
