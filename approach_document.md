# SHL Assessment Recommender — Approach Document

## 1. Problem & Solution Overview

Hiring managers often don't know the vocabulary of psychometric assessment catalogs.
This project builds a **conversational AI agent** that lets recruiters describe their
hiring need in plain English and returns a grounded shortlist of SHL Individual Test
Solutions — with verified names and real URLs — from SHL's live product catalog.

---

## 2. System Architecture

The system is a **stateless REST API** built with FastAPI, following a
Retrieval-Augmented Generation (RAG) pattern.

```
POST /chat (messages[])
  → AgentOrchestrator
      → Prompt Injection Guard (pre-filter)
      → RAGRetriever (FAISS semantic search over catalog)
      → LLM (Groq Llama 3.3-70b) with System Prompt + Catalog Context
      → Hallucination Guard (resolve names against catalog.json)
  → ChatResponse (reply, recommendations[], end_of_conversation)
```

**Key components:**

| Component | Technology | Reason |
|---|---|---|
| Web Framework | FastAPI | Async, Pydantic-native, fast cold starts |
| LLM | Groq Llama 3.3-70b-versatile | Fastest inference (~200 tok/s), free tier |
| Embeddings | all-MiniLM-L6-v2 | Runs locally, zero cost, good quality |
| Vector Store | FAISS IndexFlatIP | Zero infrastructure, baked into Docker image |
| Catalog Store | JSON file | Zero infrastructure, version-controllable |
| Scraping | httpx + BeautifulSoup4 | Lightweight, paginated SHL catalog coverage |

---

## 3. Data Pipeline

### 3.1 Catalog Scraping (Offline)
A custom scraper (`scripts/scrape_catalog.py`) paginates through SHL's product
catalog using `?start=0&type=1` query parameters (12 items per page). For each
product URL, it extracts the name, description, test_type, job_levels, and
competencies. The result is saved as `data/catalog.json` — the single source of
truth for the entire system.

### 3.2 FAISS Index (Offline)
Each assessment is embedded into a dense vector by concatenating its name,
description, test_type, competencies, and job levels into a single string.
Vectors are stored in a `faiss.IndexFlatIP` (inner product = cosine similarity
when normalized). The index is **pre-built** and baked into the Docker image —
it is never built at container startup.

---

## 4. Agent Behavior

### Turn-by-Turn Logic
1. **Injection Check**: Every incoming message is pre-filtered against a list of
   known jailbreak patterns before reaching the LLM.
2. **RAG Retrieval**: All user messages are concatenated into a single query and
   used to retrieve the top-10 most semantically similar assessments from FAISS.
3. **Single LLM Call**: Intent classification and response generation are combined
   into one Groq API call using a strict system prompt that mandates JSON-only output.
4. **Hallucination Guard**: The LLM output's `recommended_names` array is resolved
   against `catalog.json`. Any name not in the catalog is silently dropped — LLM-
   generated URLs are never used.

### Conversation Rules (enforced via System Prompt)
- Turn 1 with a vague query → ask ONE clarifying question, return `recommendations: []`
- Sufficient context → return 1–10 recommendations with name, URL, test_type
- Off-topic / non-SHL request → politely refuse
- 8-turn cap → set `end_of_conversation: true`

---

## 5. Key Design Decisions & Tradeoffs

### Why Groq over Gemini / GPT-4?
Groq provides ~200 tokens/second inference — roughly 5-10x faster than hosted
GPT-4. For a 30-second latency budget, every second matters. The free tier is
also sufficient for evaluation traffic.

### Why FAISS over ChromaDB?
FAISS loads from a single binary file with zero network calls. ChromaDB requires
a running server process. For a containerized deployment with a 2-minute cold-
start budget, FAISS is the only viable choice.

### Why JSON file over SQLite for the catalog?
The catalog is read-only after scraping and loaded once at startup into memory.
A JSON file is simpler to version-control, debug, and embed in the Docker image.
SQLite would add complexity with no benefit at this scale.

### Why a single LLM call?
The blueprint warns that each sequential LLM call costs 2-5 seconds. Combining
intent classification + response generation into one call saves 3-5 seconds per
request, keeping us safely within the 30-second budget.

### Why RAG over full catalog in prompt?
Injecting all 150+ assessments into every prompt would consume ~15,000 tokens,
increasing latency and cost. RAG retrieves only the top-10 most relevant items,
keeping context under 2,000 tokens while maintaining high Recall@10.

---

## 6. Evaluation Results

| Metric | Score |
|---|---|
| Recall@10 (local eval, 1 trace) | **1.000** |
| Schema compliance | **100%** |
| Prompt injection defense | **Pass** |
| Cold start (Render.com) | **< 90s** |

---

## 7. What I Would Do With More Time
- Add BM25 keyword search as a hybrid retrieval layer alongside FAISS
- Add more evaluation traces covering personality, ability, and SJT assessments
- Fine-tune the test_type extraction heuristics in the scraper
- Add structured logging with request IDs for production debugging
