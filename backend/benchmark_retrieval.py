"""Benchmark retrieval on its own (no LLM): python -m backend.benchmark_retrieval"""
import time
from concurrent.futures import ThreadPoolExecutor
from statistics import mean

from .retrieval import Retriever

QUERIES = [
	"How much is the fine for a late book?",
	"Is Introduction to Algorithms available?",
	"Can I book a group study room?",
	"What are the opening hours on Sunday?",
	"How do I access databases from home?",
	"How many books can a postgraduate borrow?",
	"Where is the book drop?",
	"Can alumni borrow books?",
]


def timed(retriever: Retriever, query: str) -> float:
	start = time.perf_counter()
	retriever.search(query)
	return (time.perf_counter() - start) * 1000


def main() -> None:
	retriever = Retriever()
	start = time.perf_counter()
	retriever.load()
	print(f"Index + model load (once, at startup): {(time.perf_counter() - start):.2f} s")

	uncached = [timed(retriever, q) for q in QUERIES]
	cached = [timed(retriever, q) for q in QUERIES]
	print(f"Uncached query: avg {mean(uncached):.1f} ms, max {max(uncached):.1f} ms")
	print(f"Cached query:   avg {mean(cached):.3f} ms")

	retriever._cached_search.cache_clear()
	with ThreadPoolExecutor(max_workers=8) as pool:
		start = time.perf_counter()
		concurrent = list(pool.map(lambda q: timed(retriever, q), QUERIES))
		wall = (time.perf_counter() - start) * 1000
	print(
		f"8 concurrent uncached queries: wall {wall:.1f} ms, "
		f"max per query {max(concurrent):.1f} ms"
	)


if __name__ == "__main__":
	main()
