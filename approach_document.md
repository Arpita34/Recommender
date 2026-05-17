# SHL Assessment Recommender — Approach Document

## 1. Design Choices

**Stack:** FastAPI (stateless REST), FAISS (local vector search), Groq Llama 3.3-70b-versatile (LLM inference), sentence-transformers all-MiniLM-L6-v2 (embeddings), Python 3.8.

**Why Groq over Gemini/GPT-4:** Groq delivers ~200 tok/s inference — roughly 5–10× faster than hosted alternatives. Given the 30-second timeout per call, speed was the primary selection criterion. The free tier handles evaluation traffic without rate limiting.

**Why FAISS over ChromaDB:** FAISS loads from a binary file in under a second, with zero network dependencies. ChromaDB requires a running server process, adding deployment complexity inside a Docker container.

**Why a single LLM call:** Sequential LLM calls cost 2–5 seconds each. Combining intent classification, context extraction, and response generation into one call keeps latency comfortably within the 30-second budget.

**Catalog source:** Initially scraped SHL's product catalog using httpx + BeautifulSoup with paginated requests. The scraper only returned ~24 assessments from the static HTML. Switched to directly downloading the official JSON catalog from SHL's internal API endpoint, which yielded 400+ assessments with accurate metadata (duration, job levels, languages, test type keys). All URLs were patched from `/products/` to `/solutions/products/` to match the live site.

## 2. Retrieval Setup

Each catalog entry is embedded by concatenating its name, description, keys (test types), and job levels into a single string. Vectors are stored in a `faiss.IndexFlatIP` index (inner product ≈ cosine similarity on normalized vectors). At query time, all user messages in the conversation are concatenated and used as the retrieval query, returning top-10 candidates.

The retrieved names are injected into the system prompt as a JSON catalog context. After the LLM responds, a **hallucination guard** resolves every name in `recommended_names` against the in-memory catalog — any name not present is silently dropped. This means the agent can never return a URL it invented.

## 3. Prompt Design

The system prompt enforces ten explicit rules covering:
- Catalog-grounding (only names from the injected context)
- JD extraction behavior (extract role/seniority/competencies silently, recommend in the same reply)
- Turn budget awareness (8 total messages; recommend by turn 6 at the latest)
- Experience-to-seniority mapping (0–2 yrs → Entry, 3–5 → Mid, 6+ → Senior)
- Refusal policy (off-topic, legal questions, prompt injection attempts)
- Comparison behavior (use catalog data only, not model priors)

The output schema is enforced via Groq's `response_format={"type": "json_object"}` parameter, guaranteeing parseable JSON on every call.

**What didn't work:**
- Early versions asked for seniority even when years of experience were already mentioned. Fixed by adding an explicit experience-to-seniority mapping with a rule to never re-ask.
- When a JD was pasted, the agent would summarise what it extracted as a separate message without recommendations, wasting a turn. Fixed by adding a mandatory JD response structure rule: extract silently, recommend immediately in the same reply.
- `llama3-70b-8192` was decommissioned by Groq mid-build. Switched to `llama-3.3-70b-versatile`.

## 4. Evaluation Approach

**Local evaluation:** A `scripts/evaluate.py` replay harness reads the 10 public conversation traces (C1–C10), simulates multi-turn conversations against the live `/chat` endpoint, and computes Recall@10 per trace. Mean Recall@10 on the public traces reached **1.000** after switching to the official API catalog.

**Behavioral probes tested manually:**
- Vague query on turn 1 → `recommendations: []` with clarifying question ✅
- Prompt injection attempt → polite refusal, `recommendations: []` ✅
- Off-topic question (legal advice) → in-scope refusal ✅
- JD pasted → immediate recommendations without asking for confirmation ✅
- Mid-conversation refinement → shortlist updates without restarting ✅

**What was measured:** After each prompt change, the public traces were re-evaluated to confirm Recall@10 did not drop. Behavioral probes were re-tested manually via a local chat UI (`chat_test.html`) built to avoid manual JSON construction in Swagger.

## 5. AI Tools Used

**Antigravity (agentic coding assistant)** was used for: scaffolding FastAPI boilerplate, writing the FAISS index builder, drafting the initial system prompt, converting 10 markdown conversation traces to JSON evaluation fixtures, and iterating on prompt rules based on observed failure modes. All design decisions, stack choices, and debugging were directed and validated by me.
