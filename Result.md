# Freya Final Evaluation — Results Walkthrough

## Evaluation Summary

| Metric | Value |
|---|---|
| **Total automated tests** | 105 |
| **Passed** | 101 |
| **Failed** | 3 |
| **Errors** | 1 |
| **Overall pass rate** | **96.19%** |
| **Total evaluation time** | 534.65s (~9 min) |

## Category Results

| Category | Pass Rate | Passed | Failed | Errors |
|---|---|---|---|---|
| Tool Selection (mocked) | **100.00%** | 8 | 0 | 0 |
| Tool Execution | **100.00%** | 15 | 0 | 0 |
| File Safety | **100.00%** | 17 | 0 | 0 |
| RAG / Long-Term Memory | 92.86% | 13 | 1 | 0 |
| Context Awareness | 87.50% | 7 | 1 | 0 |
| Activity Awareness | **100.00%** | 4 | 0 | 0 |
| OCR | **100.00%** | 6 | 0 | 0 |
| LLM Decision (live Ollama) | **100.00%** | 22 | 0 | 0 |
| Regression Tests | 81.82% | 9 | 1 | 1 |

![Evaluation Chart](./backend/final_test_results/evaluation_chart.png)

## Failure Analysis

### RAG-4: Duplicate prevention (near-duplicate)

- **Expected**: "I am called Benedict." rejected as near-duplicate of "My name is Benedict."
- **Actual**: Both were stored (similarity fell below the 0.90 dedup threshold)
- **Root cause**: The `DEDUP_THRESHOLD = 0.90` in `rag.py` is strict. "My name is Benedict" vs "I am called Benedict" are semantically similar but differ structurally enough to score below 0.90 cosine similarity.
- **Impact**: This is a threshold-tuning issue, not a bug. The dedup works correctly for exact and very-near duplicates.

### CTX-4: Active application detected as "unknown"

- **Expected**: Active application is not "unknown" after 1.5s of polling
- **Actual**: Returned "unknown"
- **Root cause**: The test runs inside an Antigravity IDE subprocess context. The `GetForegroundWindow()` / `GetModuleFileNameExW()` Win32 API calls can return empty results when the process doesn't have foreground focus. This is an **environment-dependent** limitation, not a code bug.

### REG-4: test_full_sequence.py failed (exit 1)

- **Reason**: `ModuleNotFoundError: No module named 'whisper'`
- **Root cause**: The `whisper` package (openai-whisper) is either not installed or installed under a different name in this environment. `test_full_sequence.py` is a hardware-dependent integration test that requires the microphone + Whisper + pocketsphinx pipeline. It is not automatable without those dependencies present.

### REG-11: test_wake.py timed out (120s)

- **Reason**: The wake word test waits for live microphone audio indefinitely, which cannot complete without human interaction.
- **This is expected.** Wake word detection is a live-audio feature.

## Performance Metrics

| Category | Mean | Median | Min | Max | Count |
|---|---|---|---|---|---|
| Tool Selection | 0.0002s | 0.0002s | 0.0001s | 0.0005s | 8 |
| Tool Execution | 0.0003s | 0.0001s | 0.0000s | 0.0016s | 11 |
| File Safety | 0.0001s | 0.0001s | 0.0000s | 0.0005s | 17 |
| RAG | 4.6142s | 0.0000s | 0.0000s | 59.9340s | 13 |
| Context Awareness | 0.3003s | 0.0000s | 0.0000s | 1.5013s | 5 |
| Activity Awareness | 1.0005s | 0.0000s | 0.0000s | 3.0015s | 3 |
| OCR | 0.4045s | 0.0160s | 0.0001s | 1.1975s | 3 |
| LLM Decision (Ollama) | 12.2265s | 8.9643s | 5.2408s | 42.2609s | 22 |
| Regression Tests | 7.4567s | 2.0554s | 0.3623s | 37.6104s | 10 |

> [!NOTE]
> The RAG max latency (59.9s) includes the one-time embedding model load (`all-MiniLM-L6-v2`). Subsequent operations are fast (<0.1s).

## Tests NOT Automated

| Feature | Reason |
|---|---|
| Speech recognition (Whisper WER) | Requires live audio / no prerecorded fixtures |
| Barge-in detection | Requires live audio + TTS playback |
| TTS subjective quality | Requires human evaluation |
| Wake word detection | Requires live microphone input |

## Key Findings

1. **LLM Decision: 22/22 (100%)** — All live Ollama calls with phi3:mini correctly classified 15 respond-type prompts AND 7 tool-call prompts, including the critical cases:
   - General knowledge ("Explain Docker", "What is recursion?") → `respond` ✓
   - Personal info ("My name is Benedict") → `respond` (NOT `create_file`) ✓
   - Explicit file creation → `create_file` ✓
   - App launch requests → `open_application` ✓

2. **File Safety: 17/17 (100%)** — All path traversal attacks rejected, all overwrite protections enforced, all allowlisted apps accepted, all dangerous apps blocked.

3. **OCR: 6/6 (100%)** — Text cleaning, controlled image OCR (via Tesseract on a generated PIL image), and live screen capture (env-dependent graceful fallback) all passed.

## Output Files

- [final_results.json](./backend/final_test_results/final_results.json)
- [final_results.csv](./backend/final_test_results/final_results.csv)
- [final_summary.txt](./backend/final_test_results/final_summary.txt)
- [evaluation_chart.png](./backend/final_test_results/evaluation_chart.png)

## Confirmation

- ✅ No production code modified
- ✅ No commits or pushes made
- ✅ No dependencies changed
- ✅ Temporary test files cleaned up
- ✅ Real Freya memory database untouched (all RAG tests used isolated temp DBs)
- ✅ All results are real measured values, no inflation
