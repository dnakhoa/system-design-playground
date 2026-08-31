# Module 19: RAG System Architecture at Scale

> **Designing production retrieval-augmented generation.** RAG is the most common pattern for grounding LLMs in external knowledge. At scale, the challenges shift from "does it work?" to "is it fast, accurate, and cost-effective?"

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 18 | LLM Inference Serving Architecture | [../18-llm-inference-serving/](../18-llm-inference-serving/) |
| **Module 19** | **RAG System Architecture at Scale** | **(current)** |
| Module 20 | Agent System Architecture | [../20-agent-architecture/](../20-agent-architecture/) |

---

## Learning Objectives

- Design a complete RAG pipeline from ingestion to generation
- Choose appropriate chunking strategies for different document types
- Implement two-stage retrieval with reranking
- Evaluate RAG quality with faithfulness and relevancy metrics
- Handle the "lost in the middle" problem

---

## Table of Contents

1. [The RAG Pipeline](#the-rag-pipeline)
2. [Ingestion Pipeline](#ingestion-pipeline)
3. [Vector Database Selection](#vector-database-selection)
4. [Two-Stage Retrieval](#two-stage-retrieval)
5. [Hybrid Search](#hybrid-search)
6. [The "Lost in the Middle" Problem](#the-lost-in-the-middle-problem)
7. [RAG Evaluation](#rag-evaluation)
8. [Case Study: Perplexity AI](#case-study-perplexity-ai)
9. [Key References](#key-references)
10. [Practice Exercise](#practice-exercise)
11. [Common Mistakes](#common-mistakes)
12. [Discussion Questions](#discussion-questions)

---

## The RAG Pipeline

```
┌───────────────────────────────────────────────────────────┐
│                   RAG Architecture                        │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  INGESTION (offline)                              │    │
│  │  Documents → Chunking → Embedding → Vector DB     │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  RETRIEVAL (online)                               │    │
│  │  Query → Embedding → Vector Search → Rerank       │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  GENERATION (online)                              │    │
│  │  Query + Context → LLM → Answer + Citations       │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Ingestion Pipeline

### Chunking Strategies

```
  Fixed-size chunking (recommended starting point):
  ┌──────────────────────────────────────────────┐
  │ Document                                     │
  │ ┌─────────┐┌─────────┐┌─────────┐┌────────┐  │
  │ │Chunk 1  ││Chunk 2  ││Chunk 3  ││Chunk 4 │  │
  │ │512 tok  ││512 tok  ││512 tok  ││512 tok │  │
  │ └─────────┘└─────────┘└─────────┘└────────┘  │
  │ (overlap: 50 tokens between chunks)          │
  └──────────────────────────────────────────────┘

  Semantic chunking:
  ┌──────────────────────────────────────────────┐
  │ Document                                     │
  │ ┌──────────┐┌─────────┐┌──────────────────┐  │
  │ │ Intro    ││Methods  ││ Results &        │  │
  │ │(topic 1) ││(topic 2)││ Discussion       │  │
  │ └──────────┘└─────────┘└──────────────────┘  │
  │ (splits at topic boundaries)                 │
  └──────────────────────────────────────────────┘

  Contextual chunking (Anthropic 2024):
  ┌──────────────────────────────────────────────┐
  │ Each chunk gets LLM-generated context:       │
  │ ┌──────────────────────────────────────────┐ │
  │ │ Context: This section discusses...       │ │
  │ │ Chunk: The embedding model was trained   │ │
  │ │ on 2B pairs and achieves 92% on MTEB...  │ │
  │ └──────────────────────────────────────────┘ │
  └──────────────────────────────────────────────┘
```

### Late Chunking: An Alternative to Adding Context

Late chunking (Jina AI, late 2024) solves the same problem as contextual
chunking above — a chunk embedded in isolation has no idea what the rest of
the document said — but fixes it at a different stage of the pipeline:

```
  Contextual chunking:
    chunk text → LLM writes a context blurb → (blurb + chunk) → embed
    adds tokens; works with any embedding model

  Late chunking:
    full document → long-context embedding model → token-level embeddings
    → split into per-chunk spans → mean-pool each span → one vector/chunk
    adds no tokens; needs a long-context-capable embedding model
```

Contextual chunking adds information in the *text*, before embedding. Late
chunking moves the chunk boundary into the *embedding* step instead: the
whole document is embedded first, in one pass, and only then is that single
long sequence of token-level embeddings sliced into per-chunk spans and
mean-pooled into one vector each. Every chunk vector still carries long-range
signal from the rest of the document — because it was computed as part of a
full-document forward pass — at no extra token cost, since no LLM call and no
extra text ever enters the embedding model.

The trade-off mirrors what you already have on hand: contextual chunking
works with any embedding model but pays an LLM generation cost per chunk.
Late chunking has no per-chunk generation cost but requires a long-context-
capable embedding model (e.g., jina-embeddings-v3).

**Which to reach for:** stay with contextual chunking if you want to keep
your current embedding model. Reach for late chunking when indexing cost and
latency matter more than a specific embedder choice, and you have — or can
adopt — a long-context embedder.

### Chunking Strategy Comparison

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **Fixed-size** | Simple, predictable | May split mid-sentence | Starting point |
| **Recursive** | Respects document structure | Language-dependent | Markdown, code |
| **Semantic** | Respects topic boundaries | Complex, slower | Research papers |
| **Contextual** | Richer embeddings | LLM cost per chunk | High-quality RAG |
| **Late chunking** | Document-level context, zero extra tokens | Needs long-context embedding model | Large-scale or cost-sensitive indexing |

### Recommended Starting Point

```
  Chunk size: 512 tokens (sweet spot for most use cases)
  Chunk overlap: 50 tokens (prevents context loss at boundaries)
  Embedding model: text-embedding-3-small (OpenAI) or BGE-M3 (open source)

  Why 512 tokens?
  - Small enough for precise retrieval
  - Large enough for meaningful context
  - Fits well in most embedding model contexts
  - Reranking works best with chunks < 512 tokens
```

---

## Vector Database Selection

| Database | Key Features | Production Notes |
|----------|-------------|-----------------|
| **pgvector** | HNSW, IVFFlat, halfvec, hybrid search | Native Postgres, good for <10M vectors |
| **Qdrant** | Replication, sharding, hybrid search | Strong for >10M vectors |
| **Weaviate** | Built-in RAG modules, hybrid search | Good for agent-driven RAG |
| **Pinecone** | Managed, serverless, no ops | Easiest to start with |
| **Milvus** | High performance, GPU-accelerated | Best for >100M vectors |
| **Chroma** | Simple, embedded, developer-friendly | Good for prototyping |

### Decision Tree

```
  How many vectors?
  │
  ├── <10M ....... pgvector — if you already run Postgres, stop here.
  │                One system to operate, and you get real JOINs and
  │                transactions between vectors and your relational data.
  │
  ├── 10M-100M ... Qdrant or Weaviate — purpose-built, horizontally
  │                sharded, native hybrid search.
  │
  ├── 100M-1B .... Milvus (self-hosted, GPU-accelerated) or
  │                Pinecone (managed, no ops).
  │
  └── >1B ........ Expect a custom tier: shard by tenant or time,
                   quantize aggressively (PQ/binary), and accept
                   approximate recall.
```

> **Vector count is the weakest of the real decision inputs.** Before optimizing
> for scale, check these:
>
> | Question | Why it dominates |
> |----------|------------------|
> | Do you need metadata filters *with* vector search? | Pre- vs post-filtering differs sharply between engines and can wreck recall |
> | How often does the corpus change? | Frequent updates punish IVF indexes; HNSW handles them better but costs more memory |
> | Do you need hybrid (dense + sparse) in one query? | Some engines do it natively; otherwise you fuse in application code |
> | Multi-tenant isolation? | Per-tenant collections vs a filter column is an architecture decision, not a tuning knob |
>
> Most teams outgrow their *filtering* requirements long before their vector
> count. A well-tuned pgvector instance handling 10M vectors with rich SQL
> predicates usually beats a dedicated store you cannot query relationally.

---

## Two-Stage Retrieval

The production standard for high-quality retrieval.

```
┌───────────────────────────────────────────────────────────┐
│              Two-Stage Retrieval                          │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Stage 1: Broad Retrieval (fast, high recall)             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Query embedding → Vector search → top_k=50      │     │
│  │  Latency: ~10ms                                  │     │
│  │  Recall: 95%+ (catches most relevant docs)       │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│                         ▼                                 │
│  Stage 2: Reranking (slower, high precision)              │
│  ┌──────────────────────────────────────────────────┐     │
│  │  50 candidates → Cross-encoder reranker → top_n=5│     │
│  │  Latency: ~50ms                                  │     │
│  │  Precision: Significantly better than bi-encoder │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│                         ▼                                 │
│  Final: 5 most relevant chunks → LLM                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Why Two Stages?

```
  Bi-encoder (Stage 1):
  - Encodes query and document independently
  - Fast: document embeddings pre-computed
  - Weak: can't capture fine-grained relevance
  - Use for: broad retrieval (top 50)

  Cross-encoder (Stage 2):
  - Encodes query and document TOGETHER
  - Slow: must score each query-document pair
  - Strong: captures nuanced relevance
  - Use for: precise reranking (top 5)

  Example:
  Query: "How does PagedAttention work?"

  Bi-encoder might rank:
  1. "GPU memory optimization techniques" (0.82)
  2. "PagedAttention reduces KV cache waste" (0.80) ← actual answer
  3. "vLLM serving framework" (0.78)

  Cross-encoder reranks:
  1. "PagedAttention reduces KV cache waste" (0.95) ← correctly promoted
  2. "vLLM serving framework" (0.85)
  3. "GPU memory optimization techniques" (0.60) ← correctly demoted
```

**The effect size is worth naming.** In Anthropic's published evaluation of
its retrieval pipeline, layering a reranking step on top of contextual
embeddings and contextual BM25 cut the top-20-chunk retrieval failure rate by
up to 67% relative to standard top-k retrieval — reranking was the single
largest contributor of any technique measured (Anthropic, 2024). That gap is
the concrete case for the second-stage precision pass above: at production
scale, the extra ~50ms of cross-encoder latency is usually the cheapest
retrieval-quality improvement available.

---

## Hybrid Search

Combine dense (vector) and sparse (keyword) search.

```
  Dense search (embedding-based):
  Query: "how does PagedAttention reduce memory waste"
  → Finds semantically similar chunks (even without keyword match)

  Sparse search (BM25/keyword-based):
  Query: "PagedAttention reduce memory waste"
  → Finds chunks containing exact keywords

  Hybrid (combine both):
  → Best of both worlds: semantic understanding + keyword precision
```

### Fusion Strategies

```
  Reciprocal Rank Fusion (RRF):

    score(d) = Σ  1 / (k + rank_i(d))
              i∈rankings

  where rank_i(d) is d's 1-based position in ranking i,
  and k is a smoothing constant — k = 60 is the standard
  default from the original RRF paper (Cormack et al., 2009).

  With k = 60:

  Chunk A: dense rank=2, sparse rank=5
    1/(60+2) + 1/(60+5) = 0.01613 + 0.01538 = 0.03151

  Chunk B: dense rank=5, sparse rank=1
    1/(60+5) + 1/(60+1) = 0.01538 + 0.01639 = 0.03177

  Chunk B wins — its rank-1 sparse hit outweighs A's rank-2 dense hit.
```

**Why RRF is the default fusion method:** it consumes only *ranks*, never
scores. Cosine similarity (0-1, tightly clustered) and BM25 (unbounded, corpus-
dependent) live on incomparable scales, so any weighted sum of raw scores needs
per-corpus normalisation and re-tuning. Ranks sidestep the problem entirely.

**What `k` controls:** it damps how much the top positions dominate.

```
  k = 0    → 1/1 vs 1/2 = 1.000 vs 0.500   rank 1 counts 2× rank 2
  k = 60   → 1/61 vs 1/62 = 0.0164 vs 0.0161   nearly equal
```

Small `k` trusts each retriever's top hit and lets one confident ranker win.
Large `k` flattens the curve so agreement *across* retrievers matters more than
any single #1. Start at 60; lower it only if you have evidence that one
retriever's top result is reliably correct.

---

## The "Lost in the Middle" Problem

LLMs struggle to use information in the middle of long contexts.

Retrieval accuracy against the position of the relevant fact in the context
window traces a **U-shape**:

```
  Recall
   100% ┤ ███                                   ███
        │ ███ ███                           ███ ███
    75% ┤ ███ ███ ███                   ███ ███ ███
        │ ███ ███ ███ ███           ███ ███ ███ ███
    50% ┤ ███ ███ ███ ███ ███   ███ ███ ███ ███ ███
        │ ███ ███ ███ ███ ███ █ ███ ███ ███ ███ ███
    25% ┤ ███ ███ ███ ███ ███ █ ███ ███ ███ ███ ███
        │ ███ ███ ███ ███ ███ █ ███ ███ ███ ███ ███
     0% ┴──┬───┬───┬───┬───┬──┬──┬───┬───┬───┬───┬──
           1   2   3   4   5  6  7   8   9  10  11
          ◄── start ──►   ◄─ middle ─►  ◄── end ──►
                      position of the relevant fact

  Taller bar = the model found and used the fact.
  The dip in the middle is the failure mode: a fact placed there
  can be effectively invisible even though it IS in the context.
```

**The counter-intuitive part:** on some tasks, a model given the fact in the
middle of a long context does *worse* than the same model given no context at
all. Adding retrieved material is not automatically an improvement — placement
matters as much as relevance.

This is why **more context is not more accuracy**, and why "just use the
1M-token window and skip retrieval" fails in practice. A longer window widens
the middle where facts go to die.

> **RAG vs. long context is not an either/or choice.** A larger context
> window does not retire retrieval: cost and latency still scale with context
> length, and even frontier models with context windows in the hundreds of
> thousands to millions of tokens still show measurable "lost in the middle"
> degradation once you actually fill roughly a few hundred thousand tokens of
> it with real content. Retrieval-and-rerank has a structural advantage a
> bigger window can't buy on its own: it puts the handful of facts that
> matter at the *top* of the prompt, where models attend best, instead of
> leaving them to be found somewhere in a much larger haystack. The practical
> 2026 consensus (see *Long Context vs. RAG* in Key References) is hybrid, not
> "pick one": RAG retrieves and reranks the right material, then hands it to
> a long-context model — this combination outperforms either approach alone
> on multi-hop reasoning, multi-source integration, and agentic workflows
> with tool use.

### Mitigation Strategies

| Strategy | Description |
|----------|-------------|
| **Reranking** | Put most relevant chunks first (highest recall position) |
| **Chunk limiting** | Use only top 3-5 chunks (avoid long context) |
| **Re-statement** | Repeat key information at the end of context |
| **Query routing** | Break complex queries into sub-queries |

---

## RAG Evaluation

### Key Metrics

| Metric | What It Measures | Tool |
|--------|-----------------|------|
| **Faithfulness** | Does the answer align with retrieved context? | DeepEval, LangSmith |
| **Answer Relevancy** | Does the answer address the question? | DeepEval |
| **Context Precision** | Are the retrieved chunks relevant? | DeepEval |
| **Context Recall** | Did we retrieve all relevant chunks? | DeepEval |
| **Hallucination** | Does the answer contain unsupported claims? | DeepEval |

### Evaluation Pipeline

```
┌───────────────────────────────────────────────────────────┐
│              RAG Evaluation Pipeline                      │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Test Dataset                                     │    │
│  │  [{question, expected_answer, context}]           │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Run RAG Pipeline                                 │    │
│  │  question → retrieve → generate → answer          │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Evaluate                                         │    │
│  │  - Faithfulness: answer vs retrieved context      │    │
│  │  - Relevancy: answer vs question                  │    │
│  │  - Precision: retrieved chunks vs relevant docs   │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Report                                           │    │
│  │  Overall score + per-metric breakdown             │    │
│  │  Failed examples for manual review                │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Case Study: Perplexity AI

Perplexity built a production search-augmented LLM that cites its sources.

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│              Perplexity AI Architecture                   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  User query → Query understanding                         │
│  │                                                        │
│  ├── Web search (multiple queries)                        │
│  ├── News search                                          │
│  ├── Academic search                                      │
│  └── proprietary index                                    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Retrieval & Reranking                            │    │
│  │  - Fetch 10-20 web pages                          │    │
│  │  - Extract relevant passages                      │    │
│  │  - Rerank by relevance                            │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Generation                                       │    │
│  │  - LLM generates answer with inline citations     │    │
│  │  - [1] [2] [3] refer to source passages           │    │
│  │  - Follow-up questions suggested                  │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Multi-source retrieval**: Don't rely on one search engine. Combine web, news, academic, and proprietary sources.

2. **Aggressive reranking**: Use a cross-encoder to rerank all retrieved passages. This is the single biggest quality improvement.

3. **Citation-by-generation**: The LLM is trained to cite sources inline. This builds user trust and enables verification.

4. **Query decomposition**: Complex questions are broken into sub-queries, each searching for specific information.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Pinecone RAG Guide | Docs | Chunking, retrieval, evaluation |
| RAG Survey (arXiv:2312.10997) | Paper | RAG taxonomy |
| LlamaIndex Documentation | Docs | RAG implementation |
| DeepEval Documentation | Docs | RAG evaluation metrics |
| Anthropic Contextual Chunking | Blog | Advanced chunking strategies |
| Late Chunking (Jina AI, 2024) | Blog/Paper | Document-level context without extra tokens |
| Long Context vs. RAG: An Evaluation and Revisits (2025) | Paper | When retrieval still beats a bigger context window |

---

## Practice Exercise

**25-minute design**: Design a RAG system for customer support:

- 100K support articles
- 10K queries/day
- Must cite sources
- Must handle follow-up questions

**Key decisions**:
1. What chunking strategy would you use?
2. How would you implement two-stage retrieval?
3. How do you evaluate answer quality?
4. How do you handle questions that can't be answered from the knowledge base?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **No evaluation set** | Every change is a vibe check, and regressions ship unnoticed | 50-100 real question/answer pairs before tuning anything |
| **Measuring the pipeline end-to-end only** | You can't tell whether retrieval missed the chunk or generation ignored it | Measure retrieval (recall@k, MRR) and generation (faithfulness) separately |
| **Chunking by character count** | Splits mid-sentence and mid-table, embedding fragments that mean nothing | Token-aware splitting on structural boundaries, with overlap |
| **One chunk size for every document type** | A legal contract and a chat log have nothing in common structurally | Tune per corpus; 512 tokens is a starting point, not an answer |
| **Skipping the reranker** | Bi-encoder top-5 is materially worse than reranked top-5 — usually the cheapest quality win available | Retrieve top-50, rerank to top-5 with a cross-encoder |
| **Dense retrieval only** | Embeddings miss exact identifiers, error codes, SKUs, and rare proper nouns | Hybrid dense + BM25, fused with RRF |
| **Weighted-sum fusion of raw scores** | Cosine and BM25 are on incomparable scales, so weights need per-corpus retuning | RRF — it uses ranks, so scale is irrelevant |
| **Stuffing the context window because it's large** | The middle of a long context is where facts go unread | Fewer, better-ranked chunks; put the strongest first |
| **Assuming a bigger context window replaces retrieval** | Cost and latency still scale with context length, and lost-in-the-middle doesn't go away just because the window grew | Retrieve and rerank regardless of window size; spend the extra room on more ranked chunks, not on skipping retrieval |
| **No "I don't know" path** | Forced to answer from irrelevant chunks, the model invents something plausible | Threshold on retrieval score and abstain below it |
| **Re-embedding with a different model** | Vectors from two models aren't comparable; retrieval quality collapses silently | Version the embedding model with the index; re-embed everything on change |
| **Answers without citations** | Users can't verify, and you can't debug a bad answer | Return chunk IDs with every claim |

---

## Discussion Questions

1. You're building a RAG system for a legal document search engine. Documents are 50-200 pages long. What chunking strategy would you use and why?

2. Explain the "lost in the middle" problem to a non-technical stakeholder. How does it affect the quality of answers?

3. You're choosing between pgvector and Qdrant for a RAG system with 5M document chunks. Which would you choose and why?

4. Design an evaluation pipeline for a customer support RAG system. What metrics would you track, and how would you build a test dataset?

5. Your RAG system retrieves relevant chunks but the LLM generates incorrect answers. What's happening and how do you fix it?

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 02: Databases and Storage](../02-databases-storage/README.md) | Vector databases are a specialized storage layer — the pgvector/Qdrant/Milvus selection tree extends this module's storage trade-offs |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Scaling retrieval past a billion vectors means sharding, quantization, and approximate recall — the same distributed trade-offs this module covers |
| [Module 15: Observability](../15-observability/README.md) | Faithfulness, relevancy, and hallucination metrics are the RAG-specific instance of the monitoring and evaluation discipline this module teaches |
| [Module 22: Production AI System Architecture](../22-production-ai-system/README.md) | RAG is typically one subsystem wired into a larger production AI system alongside inference serving and agents |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│        RAG System Architecture at Scale — Key Takeaways        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Chunk on structure, not character count — mid-sentence     │
│     splits produce embeddings that mean nothing                │
│  2. Late chunking and contextual chunking fix the same context-│
│     loss problem from opposite ends — reach for late chunking  │
│     when tokens matter more than keeping your current embedder │
│  3. Always rerank — the cheapest, highest-leverage retrieval   │
│     quality improvement you can buy                            │
│  4. RRF beats weighted-score fusion because it combines ranks, │
│     not incomparable raw scores                                │
│  5. More context is not more accuracy — the middle of a long   │
│     context window is where retrieved facts go to die          │
│  6. A bigger context window doesn't retire retrieval — cost,   │
│     latency, and lost-in-the-middle persist regardless of      │
│     window size                                                │
│  7. Evaluate retrieval and generation separately, or you'll    │
│     never know which stage actually failed                     │
│  8. Give your RAG system an "I don't know" path — forced to    │
│     answer from irrelevant chunks, a model will invent         │
│     something plausible                                        │
│  9. Version your embedding model with your index — re-embed    │
│     everything on change, or retrieval quality collapses       │
│     silently                                                   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 18: LLM Inference Serving Architecture](../18-llm-inference-serving/README.md)

**Next:** [Module 20: Agent System Architecture](../20-agent-architecture/README.md)

---

*Module 19 of 22 in the System Design Playground*