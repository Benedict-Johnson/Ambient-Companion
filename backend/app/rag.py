"""
Long-term memory store with SQLite persistence and semantic retrieval.
Uses sentence-transformers for local embeddings.
"""

import sqlite3
import json
import time
import os
import threading
import numpy as np
import traceback

# ---------- configuration ----------
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = os.path.join(DB_DIR, "freya_memory.db")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.45      # minimum cosine similarity to count as relevant
MAX_RETRIEVED = 5                # max memories injected per turn
DEDUP_THRESHOLD = 0.90           # above this → treat as duplicate

# ---------- lazy model loading ----------
_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                print("[DEBUG RAG] Loading embedding model …")
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                print("[DEBUG RAG] Embedding model loaded.")
    return _model


def _embed(text: str) -> np.ndarray:
    model = _get_model()
    return model.encode(text, normalize_embeddings=True)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


# ---------- MemoryStore ----------

class MemoryStore:
    """SQLite-backed long-term memory with embedding search."""

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_db()
        count = self._count()
        print(f"[DEBUG RAG] MemoryStore opened ({count} memories)")

    # ---- schema ----
    def _init_db(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    text        TEXT    NOT NULL,
                    embedding   BLOB    NOT NULL,
                    category    TEXT    DEFAULT 'general',
                    source      TEXT    DEFAULT 'conversation',
                    created_at  REAL    NOT NULL
                )
            """)
            self._conn.commit()

    # ---- helpers ----
    def _count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM memories")
        return cur.fetchone()[0]

    # ---- store ----
    def add_memory(self, text: str, category: str = "general", source: str = "conversation") -> bool:
        """Store a memory. Returns False if a near-duplicate already exists."""
        text = text.strip()
        if not text:
            return False

        embedding = _embed(text)

        # dedup check
        if self._is_duplicate(embedding):
            print(f"[DEBUG RAG] Duplicate memory skipped")
            return False

        blob = embedding.tobytes()
        with self._lock:
            self._conn.execute(
                "INSERT INTO memories (text, embedding, category, source, created_at) VALUES (?, ?, ?, ?, ?)",
                (text, blob, category, source, time.time()),
            )
            self._conn.commit()
        print(f"[DEBUG RAG] Memory stored (category={category})")
        return True

    def _is_duplicate(self, embedding: np.ndarray) -> bool:
        rows = self._all_embeddings()
        for _id, vec in rows:
            if _cosine_similarity(embedding, vec) >= DEDUP_THRESHOLD:
                return True
        return False

    def _all_embeddings(self):
        with self._lock:
            cur = self._conn.execute("SELECT id, embedding FROM memories")
            results = []
            for row in cur.fetchall():
                vec = np.frombuffer(row[1], dtype=np.float32)
                results.append((row[0], vec))
            return results

    # ---- retrieve ----
    def retrieve(self, query: str, top_k: int = MAX_RETRIEVED) -> list[dict]:
        """Return the most relevant memories for a query."""
        query_emb = _embed(query)
        print("[DEBUG RAG] Query embedding generated")

        with self._lock:
            cur = self._conn.execute("SELECT id, text, embedding, category, created_at FROM memories")
            rows = cur.fetchall()

        if not rows:
            print("[DEBUG RAG] No memories in store")
            return []

        scored = []
        for row in rows:
            vec = np.frombuffer(row[2], dtype=np.float32)
            sim = _cosine_similarity(query_emb, vec)
            if sim >= SIMILARITY_THRESHOLD:
                scored.append({
                    "id": row[0],
                    "text": row[1],
                    "category": row[3],
                    "created_at": row[4],
                    "similarity": sim,
                })

        scored.sort(key=lambda m: m["similarity"], reverse=True)
        results = scored[:top_k]

        if results:
            print(f"[DEBUG RAG] Retrieved memories: {len(results)}")
            for m in results:
                print(f"[DEBUG RAG]   sim={m['similarity']:.2f}  cat={m['category']}")
        else:
            print("[DEBUG RAG] No relevant memories found")

        return results

    # ---- close ----
    def close(self):
        with self._lock:
            self._conn.close()
        print("[DEBUG RAG] MemoryStore closed")


# ---------- memory extraction helpers ----------

# Simple deterministic patterns that strongly signal an explicit personal fact.
_FACT_PATTERNS = [
    "my name is",
    "i'm called",
    "call me",
    "my favorite",
    "my favourite",
    "i prefer",
    "i like",
    "i love",
    "i hate",
    "i'm working on",
    "i am working on",
    "my project",
    "i work at",
    "i work for",
    "i live in",
    "i'm from",
    "i am from",
    "my birthday",
    "my goal is",
    "my goals are",
    "remember that",
    "remember this",
    "don't forget",
    "i always",
    "i never",
]


def extract_memories(user_text: str, assistant_text: str) -> list[str]:
    """
    Return a list of factual strings worth storing from a single exchange.
    Uses simple deterministic pattern matching on the user utterance.
    """
    lower = user_text.lower().strip()
    facts = []

    for pattern in _FACT_PATTERNS:
        if pattern in lower:
            # Store the original user text as the memory (preserves casing / detail)
            facts.append(user_text.strip())
            break  # one memory per turn is enough for MVP

    return facts
