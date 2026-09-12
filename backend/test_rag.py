"""
Test suite for the RAG / long-term memory system.
Run with:  python test_rag.py
"""

import os
import sys
import time
import tempfile

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.rag import MemoryStore, extract_memories

PASS = 0
FAIL = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    tag = "PASS" if ok else "FAIL"
    if not ok:
        FAIL += 1
    else:
        PASS += 1
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))


def test_store_and_retrieve():
    print("\n--- Test A: Store and retrieve a fact ---")
    db = tempfile.mktemp(suffix=".db")
    store = MemoryStore(db_path=db)
    store.add_memory("The user's favorite programming language is Python.", category="preference")

    results = store.retrieve("What programming language do I prefer?")
    found = any("Python" in m["text"] for m in results)
    report("Python memory retrieved", found, f"results={len(results)}")
    store.close()
    os.remove(db)


def test_unrelated_query():
    print("\n--- Test B: Unrelated query should not retrieve ---")
    db = tempfile.mktemp(suffix=".db")
    store = MemoryStore(db_path=db)
    store.add_memory("The user's favorite programming language is Python.", category="preference")

    results = store.retrieve("What is the weather like today?")
    found = any("Python" in m["text"] for m in results)
    report("Unrelated query returns no Python memory", not found, f"results={len(results)}")
    store.close()
    os.remove(db)


def test_dedup():
    print("\n--- Test C: Duplicate prevention ---")
    db = tempfile.mktemp(suffix=".db")
    store = MemoryStore(db_path=db)
    ok1 = store.add_memory("The user's favorite programming language is Python.")
    ok2 = store.add_memory("The user's favorite programming language is Python.")  # exact dup
    ok3 = store.add_memory("My favorite programming language is Python.")           # near dup

    count = store._count()
    report("First insert succeeds", ok1)
    report("Exact duplicate blocked", not ok2)
    report("Near-duplicate blocked", not ok3)
    report("Total stored = 1", count == 1, f"count={count}")
    store.close()
    os.remove(db)


def test_persistence():
    print("\n--- Test D: Persistence across restarts ---")
    db = tempfile.mktemp(suffix=".db")

    # session 1 – store
    store = MemoryStore(db_path=db)
    store.add_memory("The user's favorite color is blue.", category="preference")
    store.close()

    # session 2 – retrieve
    store2 = MemoryStore(db_path=db)
    results = store2.retrieve("What is my favorite color?")
    found = any("blue" in m["text"] for m in results)
    report("Memory persists across restart", found, f"results={len(results)}")
    store2.close()
    os.remove(db)


def test_extraction():
    print("\n--- Test E: Memory extraction patterns ---")

    facts = extract_memories("My name is Benedict", "Nice to meet you!")
    report("Name extracted", len(facts) == 1, f"facts={facts}")

    facts2 = extract_memories("Hello, how are you?", "I'm good!")
    report("Chitchat ignored", len(facts2) == 0, f"facts={facts2}")

    facts3 = extract_memories("I'm working on a voice assistant called Freya", "Cool!")
    report("Project extracted", len(facts3) == 1, f"facts={facts3}")


if __name__ == "__main__":
    print("=" * 50)
    print("  RAG / Long-Term Memory Test Suite")
    print("=" * 50)

    test_store_and_retrieve()
    test_unrelated_query()
    test_dedup()
    test_persistence()
    test_extraction()

    print(f"\n{'=' * 50}")
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 50}")
    sys.exit(1 if FAIL else 0)
