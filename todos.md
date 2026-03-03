# TO-DO

## What's already solid

- **Dependency Inversion** via `LibraryContextProvider` Protocol — testable, decoupled
- **Null Object** for optional MCP — no if-guards at call sites
- **Pre-filter** before AI call — saves tokens for irrelevant articles
- **In-memory cache** in `Context7Client` — avoids duplicate MCP roundtrips

---

## High-impact improvements

### 2. Structured output validation

`json.loads(response.text)` with no schema check. If Gemini hallucinates a missing `score` key or returns a string where an int is expected, the article gets silently scored as 0. Use Pydantic for boundary validation:

```python
class AnalysisResult(BaseModel):
    score: int = Field(ge=0, le=10)
    reason: str
    tags: list[str] = []
```

### 3. Concurrent article analysis

Articles are almost certainly analyzed one-by-one. `asyncio.Semaphore` + `gather` would parallelize the batch while respecting API rate limits — a significant throughput gain:

```python
sem = asyncio.Semaphore(5)
async def bounded_analyze(a):
    async with sem:
        return await analyzer.analyze(a, keywords)

results = await asyncio.gather(*[bounded_analyze(a) for a in articles])
```

### 4. `DigestGenerator` doesn't support context7

`GeminiArticleAnalyzer` accepts a `LibraryContextProvider`, but `GeminiDigestGenerator` has no equivalent. The digest synthesis could benefit from the same context enrichment — it's an inconsistency in the design.

### 5. Prompt extraction / versioning

Prompts are f-strings buried in static methods, making iteration and A/B testing hard. Separating them into `distill_rss/prompts.py` as named constants is a low-effort, high-ROI practice:

```python
# prompts.py
ANALYSIS_SYSTEM = "Você é o 'Agente da Práxis'..."
ANALYSIS_USER_TEMPLATE = "Título: {title}\nFonte: {source}\n..."
```

This also enables prompt testing without running the full pipeline.

---

## Medium-impact improvements

### 7. Agentic reflection / self-critique loop

The current pipeline is single-shot: one prompt → one score. A reflection step where the agent critiques its own score would improve calibration:

> "Given you scored this 7, what is one reason it might deserve a 4? Adjust if necessary."

This is the **ReAct** / **self-refine** pattern and is particularly valuable for the scoring task where calibration drift matters.

### 8. Native function calling instead of prompt-engineered JSON

Currently relying on `"Responda APENAS com JSON válido"` + `response_mime_type="application/json"`. Gemini supports native function calling / tool declarations, which gives stronger schema guarantees and eliminates the JSON-from-free-text fragility.

### 9. Semantic deduplication before analysis

Articles from multiple feeds often overlap. A cheap embedding similarity check before the AI layer would avoid paying for duplicate analysis. Even a simple URL hash + title fuzzy match (via `rapidfuzz`) would catch most duplicates.

---

## Priority order

| Priority | Improvement                     | Why                                      |
| -------- | ------------------------------- | ---------------------------------------- |
| 1        | Retry + backoff                 | Silent article loss is a correctness bug |
| 2        | Pydantic output validation      | Prevents score corruption                |
| 3        | Concurrent analysis             | Immediate throughput gain                |
| 4        | Observability logging           | Can't tune what you can't see            |
| 5        | Prompt extraction               | Enables iteration and testing            |
| 6        | DigestGenerator context7 parity | Consistency                              |
| 7        | Self-critique reflection        | Quality improvement                      |

The first three are essentially correctness/reliability issues; the rest are quality-of-life for an agentic system meant to run unattended.
