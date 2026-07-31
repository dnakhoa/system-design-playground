# Module 16: RAG System Architecture at Scale

> **Designing production retrieval-augmented generation.** RAG is the most common pattern for grounding LLMs in external knowledge. At scale, the challenges shift from "does it work?" to "is it fast, accurate, and cost-effective?"

## Learning Objectives

- Design a complete RAG pipeline from ingestion to generation
- Choose appropriate chunking strategies for different document types
- Implement two-stage retrieval with reranking
- Evaluate RAG quality with faithfulness and relevancy metrics
- Handle the "lost in the middle" problem

---

## The RAG Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                   RAG Architecture                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  INGESTION (offline)                              │   │
│  │  Documents → Chunking → Embedding → Vector DB    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  RETRIEVAL (online)                               │   │
│  │  Query → Embedding → Vector Search → Rerank      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  GENERATION (online)                              │   │
│  │  Query + Context → LLM → Answer + Citations      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Ingestion Pipeline

### Chunking Strategies

```
  Fixed-size chunking (recommended starting point):
  ┌─────────────────────────────────────────────┐
  │ Document                                     │
  │ ┌─────────┐┌─────────┐┌─────────┐┌────────┐│
  │ │Chunk 1  ││Chunk 2  ││Chunk 3  ││Chunk 4 ││
  │ │512 tok  ││512 tok  ││512 tok  ││512 tok ││
  │ └─────────┘└─────────┘└─────────┘└────────┘│
  │ (overlap: 50 tokens between chunks)         │
  └─────────────────────────────────────────────┘

  Semantic chunking:
  ┌─────────────────────────────────────────────┐
  │ Document                                     │
  │ ┌──────────┐┌────────┐┌──────────────────┐ │
  │ │ Intro    ││Methods ││ Results &        │ │
  │ │(topic 1) ││(topic 2)││ Discussion       │ │
  │ └──────────┘└────────┘└──────────────────┘ │
  │ (splits at topic boundaries)                │
  └─────────────────────────────────────────────┘

  Contextual chunking (Anthropic 2024):
  ┌─────────────────────────────────────────────┐
  │ Each chunk gets LLM-generated context:      │
  │ ┌─────────────────────────────────────────┐ │
  │ │ Context: This section discusses...       │ │
  │ │ Chunk: The embedding model was trained   │ │
  │ │ on 2B pairs and achieves 92% on MTEB...  │ │
  │ └─────────────────────────────────────────┘ │
  └─────────────────────────────────────────────┘
```

### Chunking Strategy Comparison

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **Fixed-size** | Simple, predictable | May split mid-sentence | Starting point |
| **Recursive** | Respects document structure | Language-dependent | Markdown, code |
| **Semantic** | Respects topic boundaries | Complex, slower | Research papers |
| **Contextual** | Richer embeddings | LLM cost per chunk | High-quality RAG |

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
┌─────────────────────────────────────────────────────────┐
│              Two-Stage Retrieval                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Stage 1: Broad Retrieval (fast, high recall)           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Query embedding → Vector search → top_k=50      │   │
│  │  Latency: ~10ms                                  │   │
│  │  Recall: 95%+ (catches most relevant docs)       │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  Stage 2: Reranking (slower, high precision)           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  50 candidates → Cross-encoder reranker → top_n=5│   │
│  │  Latency: ~50ms                                  │   │
│  │  Precision: Significantly better than bi-encoder │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  Final: 5 most relevant chunks → LLM                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
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
┌─────────────────────────────────────────────────────────┐
│              RAG Evaluation Pipeline                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Test Dataset                                     │   │
│  │  [{question, expected_answer, context}]           │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Run RAG Pipeline                                 │   │
│  │  question → retrieve → generate → answer          │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Evaluate                                         │   │
│  │  - Faithfulness: answer vs retrieved context      │   │
│  │  - Relevancy: answer vs question                  │   │
│  │  - Precision: retrieved chunks vs relevant docs   │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Report                                           │   │
│  │  Overall score + per-metric breakdown             │   │
│  │  Failed examples for manual review                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Case Study: Perplexity AI

Perplexity built a production search-augmented LLM that cites its sources.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Perplexity AI Architecture                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User query → Query understanding                       │
│  │                                                       │
│  ├── Web search (multiple queries)                      │
│  ├── News search                                        │
│  ├── Academic search                                    │
│  └── proprietary index                                  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Retrieval & Reranking                            │   │
│  │  - Fetch 10-20 web pages                         │   │
│  │  - Extract relevant passages                     │   │
│  │  - Rerank by relevance                           │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Generation                                       │   │
│  │  - LLM generates answer with inline citations    │   │
│  │  - [1] [2] [3] refer to source passages          │   │
│  │  - Follow-up questions suggested                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
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

---

## Discussion Questions

1. You're building a RAG system for a legal document search engine. Documents are 50-200 pages long. What chunking strategy would you use and why?

2. Explain the "lost in the middle" problem to a non-technical stakeholder. How does it affect the quality of answers?

3. You're choosing between pgvector and Qdrant for a RAG system with 5M document chunks. Which would you choose and why?

4. Design an evaluation pipeline for a customer support RAG system. What metrics would you track, and how would you build a test dataset?

5. Your RAG system retrieves relevant chunks but the LLM generates incorrect answers. What's happening and how do you fix it?

---

**Previous**: [LLM Inference Serving Architecture](../15-llm-inference-serving/README.md)
**Next**: [Agent System Architecture](../17-agent-architecture/README.md)

