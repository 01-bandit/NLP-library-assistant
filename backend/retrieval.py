import json
import threading
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "data" / "index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 4
# Cosine similarity below this is treated as "no relevant match".
MIN_SCORE = 0.35

_model = None
_model_lock = threading.Lock()


def embed(texts: list[str]) -> np.ndarray:
	global _model
	with _model_lock:
		if _model is None:
			_model = SentenceTransformer(MODEL_NAME, device="cpu")
	return _model.encode(texts, normalize_embeddings=True).astype("float32")


class Retriever:
	def __init__(self, index_dir: Path = INDEX_DIR) -> None:
		self.index_dir = index_dir
		self.index = None
		self.chunks: list[dict[str, str]] = []
		self._lock = threading.Lock()

	def load(self) -> None:
		with self._lock:
			if self.index is None:
				self.chunks = json.loads(
					(self.index_dir / "chunks.json").read_text(encoding="utf-8")
				)
				self.index = faiss.read_index(str(self.index_dir / "index.faiss"))
				embed(["warm up"])

	def search(self, query: str) -> list[dict]:
		self.load()
		return list(self._cached_search(" ".join(query.lower().split())))

	@lru_cache(maxsize=512)
	def _cached_search(self, query: str) -> tuple[dict, ...]:
		scores, ids = self.index.search(embed([query]), TOP_K)
		return tuple(
			{**self.chunks[i], "score": float(score)}
			for score, i in zip(scores[0], ids[0])
			if i != -1 and score >= MIN_SCORE
		)
