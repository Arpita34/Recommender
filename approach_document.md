# SHL Assessment Recommender — Approach Document

## 1. Design Choices

**Stack:** FastAPI, FAISS + BM25 (hybrid retrieval), Groq Llama 3.3-70b-versatile, sentence-transformers all-MiniLM-L6-v2, Docker on Render.

- **Groq** was chosen for inference speed (~200 tok/s). With a 30-second timeout per call, this leaves comfortable headroom. The free tier handles evaluation traffic without rate limits.
- **FAISS** loads from a binary file in <1s with no external services — simpler than ChromaDB in a Docker container.
- **Single LLM call per turn** combines intent classification, context extraction, and response generation. Sequential calls would risk the timeout budget.

**Catalog:** The SHL product catalog page only exposes ~24 items via static HTML. I switched to SHL's internal JSON endpoint (`shl_product_catalog.json`), which returned 400+ Individual Test Solutions with structured metadata (duration, job levels, languages, test type keys). URLs were normalized from `/products/` to `/solutions/products/` to match the live site.

## 2. Retrieval Setup

**Indexing:** Each catalog entry is embedded by concatenating its name, description, test type keys, and job levels. Vectors are stored in a `faiss.IndexFlatIP` index (inner product on L2-normalized vectors ≈ cosine similarity).

**Hybrid Search (Dense + BM25):** At query time, all user messages are concatenated into a single retrieval query. Two searches run in parallel:

1. **Dense (FAISS):** Semantic similarity — captures intent like "leadership assessment" matching "OPQ Leadership Report."
2. **Lexical (BM25):** Exact keyword matching — catches specific product names and technical skills like "SAP ABAP", "Core Java", or "OPQ32r" that embeddings handle poorly.

Results are merged using **Reciprocal Rank Fusion (RRF)** with k=60, returning the top-10 candidates. This consistently outperformed dense-only retrieval on queries containing exact product names.

**Hallucination Guard:** After the LLM responds, every name in `recommended_names` is resolved against the in-memory catalog. Any name not found is silently dropped. The agent cannot return a URL it invented.

## 3. Prompt Design

The system prompt is structured around seven responsibilities:

- **Grounding:** Only recommend from the injected catalog context.
- **JD Handling:** If a job description is provided, extract role/seniority/competencies internally and recommend in the same reply — no separate extraction step.
- **Turn Budget:** The 8-turn cap is explicitly stated. The agent prioritizes early recommendations and avoids filler turns.
- **Seniority Inference:** 0–2 yrs → Entry, 3–5 → Mid, 6+ → Senior. If years are mentioned, seniority is inferred automatically.
- **Scope Enforcement:** Off-topic questions, legal queries, and prompt injection attempts are refused politely.
- **Refinement:** Constraints changed mid-conversation update the shortlist rather than restarting.
- **Comparison:** Answered using catalog data only, not model priors.

JSON output is enforced via Groq's `response_format={"type": "json_object"}`, guaranteeing parseable responses on every call.

## 4. What Didn't Work

- **Redundant seniority questions:** Early prompts asked for seniority even when years of experience were already stated. Fixed by adding an explicit mapping rule.
- **JD summarization instead of action:** When a JD was pasted, the agent would spend a turn restating what it extracted before recommending. Fixed by requiring immediate recommendations in the same reply.
- **Dense-only retrieval missed exact names:** Queries like "OPQ32r" or "Core Java" returned semantically similar but wrong assessments. Adding BM25 as a second signal resolved this.
- **Model decommissioned:** `llama3-70b-8192` was retired by Groq mid-development. Switched to `llama-3.3-70b-versatile`.
- **Render OOM on free tier:** The 512MB memory limit was exceeded during startup when the embedding model was downloaded at runtime. Fixed by pre-downloading the model during Docker build and setting `MALLOC_ARENA_MAX=2`.

## 5. Evaluation

**Automated:** A replay harness (`scripts/evaluate.py`) reads the 10 public conversation traces, runs multi-turn conversations against the live `/chat` endpoint, and computes Recall@10 per trace. Mean Recall@10 = **1.00** on all 10 public traces.

**Manual behavioral probes:**

| Probe | Result |
|---|---|
| Vague query on turn 1 → clarifying question, no recommendations | ✅ |
| Prompt injection → polite refusal | ✅ |
| Off-topic question → scoped refusal | ✅ |
| Full JD pasted → immediate recommendations | ✅ |
| Mid-conversation refinement → updated shortlist | ✅ |
| Assessment comparison → grounded in catalog data | ✅ |

After each prompt or retrieval change, public traces were re-evaluated to confirm Recall@10 did not regress.

## 6. AI Tools Used

**Antigravity (agentic coding assistant)** was used for: scaffolding FastAPI boilerplate, writing the FAISS index builder, drafting the initial system prompt, iterating on prompt rules based on observed failure modes, and building the evaluation harness. All architecture decisions, stack selection, and debugging were directed and validated by me.
