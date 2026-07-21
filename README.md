# System Design: From Fundamentals to LLM AI Systems

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Modules](https://img.shields.io/badge/modules-16-blue.svg)]()
[![Theory](https://img.shields.io/badge/type-theory%20%2B%20design-orange.svg)]()

> **The most comprehensive open-source system design course** — 16 modules covering distributed systems fundamentals, classic design cases, and LLM AI system architecture. Theory-first with diagrams, trade-off tables, real-world case studies, and hands-on exercises.

## What You'll Learn

This course takes you from system design fundamentals to designing production LLM AI systems:

| Phase | Topics | Modules |
|-------|--------|---------|
| **Foundations** | Scalability, databases, caching, load balancing | 01-04 |
| **Intermediate** | Async systems, microservices, reliability, distributed systems | 05-08 |
| **Design Cases** | URL shortener, chat, payments, file storage, video streaming | 09-12 |
| **LLM AI Systems** | Inference serving, RAG at scale, agents, production AI | 13-16 |

## Why This Course?

| Feature | Traditional SD Courses | **This Course** |
|---------|----------------------|-----------------|
| LLM system design | ❌ | ✅ Modules 13-16 |
| RAG architecture at scale | ❌ | ✅ Module 14 |
| Agent system architecture | ❌ | ✅ Module 15 |
| Production AI observability | ❌ | ✅ Module 16 |
| Classic fundamentals | ✅ | ✅ Modules 01-08 |
| Real-world case studies | Partial | ✅ Every module |
| Hands-on exercises | Partial | ✅ Every module |
| ASCII diagrams | Rare | ✅ Every module |
| **Total coverage** | 10-12 modules | **16 modules** |

## Who This Course Is For

- **Software engineers** preparing for system design interviews
- **ML engineers** building production AI systems
- **Architects** designing scalable distributed systems
- **Students** learning system design from scratch
- **Teams** needing a shared reference for design patterns

**Prerequisites:** Basic programming knowledge. No distributed systems background required — we start from fundamentals.

---

## Learning Paths

Choose your path based on your goals:

### Path A: System Design Interview Prep (~16 hours)

Focus on the most commonly asked topics:

```
Module 01 (Fundamentals) → Module 09 (URL Shortener) → Module 10 (Chat/News Feed)
    → Module 12 (Payments) → Module 03 (Caching) → Module 04 (Load Balancing)
```

| Priority | Module | Why |
|----------|--------|-----|
| **Must** | 01 | 9-step framework, estimation, CAP theorem |
| **Must** | 09 | URL shortener is the #1 most-asked question |
| **Must** | 10 | Chat/news feed tests real-time design |
| **Must** | 12 | Payments tests consistency and idempotency |
| **Should** | 03 | Caching comes up in every design |
| **Should** | 04 | Rate limiting is a common follow-up |
| Nice to have | 06 | Microservices for architecture discussions |

### Path B: Build LLM AI Systems (~12 hours)

Focus on LLM-specific architecture:

```
Module 13 (Inference Serving) → Module 14 (RAG at Scale)
    → Module 15 (Agent Architecture) → Module 16 (Production AI)
```

| Priority | Module | Why |
|----------|--------|-----|
| **Must** | 13 | How to serve LLMs at scale (PagedAttention, batching) |
| **Must** | 14 | RAG is the most common LLM pattern |
| **Should** | 15 | Agents are the future of LLM applications |
| **Should** | 16 | Putting it all together in production |
| Nice to have | 01 | Foundation concepts still apply |

### Path C: Full Curriculum (~32 hours)

Work through all 16 modules in order. Each builds on the previous.

### Path D: Fill Your Gaps

| Your Gap | Go to |
|----------|-------|
| Can't estimate QPS/storage | Module 01 (Fundamentals) |
| Don't know when to use SQL vs NoSQL | Module 02 (Databases) |
| Cache invalidation keeps breaking | Module 03 (Caching) |
| Need to design a chat system | Module 10 (Chat/News Feed) |
| Building a RAG system | Module 14 (RAG at Scale) |
| Need to serve LLMs at scale | Module 13 (Inference Serving) |
| Building autonomous agents | Module 15 (Agent Architecture) |
| Don't know how to monitor AI systems | Module 16 (Production AI) |

---

## Curriculum

### Phase 1: Foundations (Modules 01-04)

| Module | Topic | Key Concepts | Time |
|--------|-------|-------------|------|
| 01 | System Design Fundamentals | 9-step framework, CAP theorem, estimation | ~2h |
| 02 | Databases and Storage | SQL vs NoSQL, sharding, replication, ACID | ~2h |
| 03 | Caching Strategies | Cache patterns, Redis, CDN, cache stampede | ~2h |
| 04 | Load Balancing | Algorithms, L4/L7, rate limiting, API gateway | ~2h |

### Phase 2: Intermediate (Modules 05-08)

| Module | Topic | Key Concepts | Time |
|--------|-------|-------------|------|
| 05 | Async Systems | Kafka, event-driven, CQRS, delivery guarantees | ~2h |
| 06 | Microservices | DDD, saga pattern, service mesh, observability | ~2h |
| 07 | Reliability Engineering | Circuit breakers, chaos engineering, SLOs | ~2h |
| 08 | Distributed Systems | Raft, consensus, CRDTs, leader election | ~2h |

### Phase 3: Design Cases (Modules 09-12)

| Module | Topic | Key Concepts | Time |
|--------|-------|-------------|------|
| 09 | URL Shortener & Rate Limiter | ID generation, token bucket, distributed counting | ~2h |
| 10 | Chat System & News Feed | WebSocket, fan-out, presence, ranking | ~2h |
| 11 | File Storage & Video Streaming | Chunking, sync, transcoding, adaptive bitrate | ~2h |
| 12 | Payment System & E-commerce | Idempotency, inventory, flash sales, reconciliation | ~2h |

### Phase 4: LLM AI Systems (Modules 13-16)

| Module | Topic | Key Concepts | Time |
|--------|-------|-------------|------|
| 13 | LLM Inference Serving | PagedAttention, batching, quantization, GPU clusters | ~2h |
| 14 | RAG at Scale | Chunking, two-stage retrieval, hybrid search, evaluation | ~2h |
| 15 | Agent Architecture | ReAct, middleware stack, multi-agent, cost control | ~2h |
| 16 | Production AI System | Model routing, guardrails, observability, scaling | ~2h |

---

## Complementary Courses

This course pairs with the **[LLM Engineering Course](https://github.com/dnakhoa/llm-engineering-playground)**:

| System Design (This Course) | LLM Engineering |
|---------------------------|-----------------|
| Module 13: LLM Inference Serving | Module 05-06: Deployment & Optimization |
| Module 14: RAG at Scale | Module 02: RAG Systems |
| Module 15: Agent Architecture | Module 07: Agentic Workflows |
| Module 16: Production AI | Module 08-10: LLM Ops, EvalOps, Guardrails |

**System Design** teaches you *how to think about architecture*.  
**LLM Engineering** teaches you *how to build the implementations*.

**Recommended order**: Take LLM Engineering first (build the skills), then System Design (learn to architect at scale). Or take them in parallel — each System Design module links to the relevant LLM Engineering module.

---

## How to Use This Course

### For Self-Study
1. Start with Module 01 — even if you're experienced, review the fundamentals
2. Follow the sequence — each module builds on previous concepts
3. Read the case studies — they show how theory applies to real systems
4. **Do the exercises** — they test your understanding better than reading
5. Answer the discussion questions — they test your understanding

### For Interview Prep
1. Complete Phase 1 (Foundations) for the basics
2. Work through Phase 3 (Design Cases) for common interview questions
3. Review Phase 4 (LLM AI) for AI/ML system design questions
4. Practice the 9-step framework from Module 01
5. Time yourself: 45 minutes per design problem

### For Teams
1. Use as training material for new team members
2. Reference architecture decisions in design docs
3. Share the LLM modules (13-16) with AI/ML teams
4. Establish common vocabulary and patterns

---

## References

### Essential Books
| Book | Author | Focus |
|------|--------|-------|
| Designing Data-Intensive Applications | Martin Kleppmann | Distributed systems depth |
| System Design Interview (Vol 1 & 2) | Alex Xu | Interview prep, breadth |
| Site Reliability Engineering | Google | Reliability practices |
| Building Microservices | Sam Newman | Service architecture |
| Designing Machine Learning Systems | Chip Huyen | ML in production |

### Engineering Blogs
- Meta Engineering, Netflix Tech Blog, Uber Engineering
- Google AI Blog, OpenAI Blog, Anthropic Research
- vLLM Blog, LangChain Blog

### Key Papers
| Paper | Year | Topic |
|-------|------|-------|
| PagedAttention (vLLM) | 2023 | KV cache optimization |
| Speculative Decoding | 2022 | Inference acceleration |
| ReAct | 2022 | Agent planning |
| RAG Survey | 2023 | RAG taxonomy |

## License

This educational resource is provided for learning purposes. Feel free to use, modify, and share.

**Keywords:** system design, system design course, distributed systems, LLM system design, AI architecture, system design interview, microservices, caching, load balancing, RAG architecture, agent systems, vLLM, inference serving

---

**Happy Learning!**
