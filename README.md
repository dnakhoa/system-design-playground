# System Design: From Fundamentals to LLM AI Systems

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Modules](https://img.shields.io/badge/modules-18-blue.svg)]()
[![Theory](https://img.shields.io/badge/type-theory%20%2B%20design-orange.svg)]()

> **The most comprehensive open-source system design course** — 18 modules covering distributed systems fundamentals, classic design cases, core infrastructure, and LLM AI system architecture. Theory-first with diagrams, trade-off tables, real-world case studies, and hands-on exercises.

## What You'll Learn

This course takes you from system design fundamentals to designing production LLM AI systems:

| Phase | Topics | Modules |
|-------|--------|---------|
| **Foundations** | Scalability, databases, caching, load balancing | 01-04 |
| **Intermediate** | Async systems, microservices, reliability, distributed systems | 05-08 |
| **Design Cases** | URL shortener, chat, payments, file storage, video streaming | 09-12 |
| **Core Infrastructure** | Security, API design | 13-14 |
| **LLM AI Systems** | Inference serving, RAG at scale, agents, production AI | 15-18 |

## Why This Course?

| Feature | Traditional SD Courses | **This Course** |
|---------|----------------------|-----------------|
| LLM system design | ❌ | ✅ Modules 15-18 |
| RAG architecture at scale | ❌ | ✅ Module 16 |
| Agent system architecture | ❌ | ✅ Module 17 |
| Production AI observability | ❌ | ✅ Module 18 |
| Classic fundamentals | ✅ | ✅ Modules 01-08 |
| Security and API design | Partial | ✅ Modules 13-14 |
| Real-world case studies | Partial | ✅ Every module |
| Hands-on exercises | Partial | ✅ Every module |
| ASCII diagrams | Rare | ✅ Every module |
| **Total coverage** | 10-12 modules | **18 modules** |

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
Module 15 (Inference Serving) → Module 16 (RAG at Scale)
    → Module 17 (Agent Architecture) → Module 18 (Production AI)
```

| Priority | Module | Why |
|----------|--------|-----|
| **Must** | 15 | How to serve LLMs at scale (PagedAttention, batching) |
| **Must** | 16 | RAG is the most common LLM pattern |
| **Should** | 17 | Agents are the future of LLM applications |
| **Should** | 18 | Putting it all together in production |
| Nice to have | 01 | Foundation concepts still apply |

### Path C: Full Curriculum (~36 hours)

Work through all 18 modules in order. Each builds on the previous.

### Path D: Fill Your Gaps

| Your Gap | Go to |
|----------|-------|
| Can't estimate QPS/storage | Module 01 (Fundamentals) |
| Don't know when to use SQL vs NoSQL | Module 02 (Databases) |
| Cache invalidation keeps breaking | Module 03 (Caching) |
| Need to design a chat system | Module 10 (Chat/News Feed) |
| Auth, encryption, or OWASP gaps | Module 13 (Security) |
| APIs keep breaking clients | Module 14 (API Design) |
| Need to serve LLMs at scale | Module 15 (Inference Serving) |
| Building a RAG system | Module 16 (RAG at Scale) |
| Building autonomous agents | Module 17 (Agent Architecture) |
| Don't know how to monitor AI systems | Module 18 (Production AI) |

---

## Curriculum

### Phase 1: Foundations (Modules 01-04)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [01](01-fundamentals/README.md) | [System Design Fundamentals](01-fundamentals/README.md) | 9-step framework, CAP theorem, estimation | ⭐ Beginner | ~2h |
| [02](02-databases-storage/README.md) | [Databases and Storage](02-databases-storage/README.md) | SQL vs NoSQL, sharding, replication, ACID | ⭐ Beginner | ~2h |
| [03](03-caching/README.md) | [Caching Strategies](03-caching/README.md) | Cache patterns, Redis, CDN, cache stampede | ⭐⭐ Intermediate | ~2h |
| [04](04-load-balancing/README.md) | [Load Balancing](04-load-balancing/README.md) | Algorithms, L4/L7, rate limiting, API gateway | ⭐⭐ Intermediate | ~2h |

### Phase 2: Intermediate (Modules 05-08)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [05](05-async-systems/README.md) | [Async Systems](05-async-systems/README.md) | Kafka, event-driven, CQRS, delivery guarantees | ⭐⭐ Intermediate | ~2h |
| [06](06-microservices/README.md) | [Microservices](06-microservices/README.md) | DDD, saga pattern, service mesh, observability | ⭐⭐ Intermediate | ~2h |
| [07](07-reliability/README.md) | [Reliability Engineering](07-reliability/README.md) | Circuit breakers, chaos engineering, SLOs | ⭐⭐ Intermediate | ~2h |
| [08](08-distributed-systems/README.md) | [Distributed Systems](08-distributed-systems/README.md) | Raft, consensus, CRDTs, leader election | ⭐⭐⭐ Advanced | ~2h |

### Phase 3: Design Cases (Modules 09-12)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [09](09-case-url-shortener-rate-limiter/README.md) | [URL Shortener & Rate Limiter](09-case-url-shortener-rate-limiter/README.md) | ID generation, token bucket, distributed counting | ⭐⭐ Intermediate | ~2h |
| [10](10-case-chat-newsfeed/README.md) | [Chat System & News Feed](10-case-chat-newsfeed/README.md) | WebSocket, fan-out, presence, ranking | ⭐⭐ Intermediate | ~2h |
| [11](11-case-storage-streaming/README.md) | [File Storage & Video Streaming](11-case-storage-streaming/README.md) | Chunking, sync, transcoding, adaptive bitrate | ⭐⭐ Intermediate | ~2h |
| [12](12-case-payment-ecommerce/README.md) | [Payment System & E-commerce](12-case-payment-ecommerce/README.md) | Idempotency, inventory, flash sales, reconciliation | ⭐⭐⭐ Advanced | ~2h |

### Phase 4: Core Infrastructure (Modules 13-14)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [13](13-security/README.md) | [Security](13-security/README.md) | Auth, encryption, OWASP, prompt injection | ⭐⭐ Intermediate | ~2h |
| [14](14-api-design/README.md) | [API Design](14-api-design/README.md) | REST, gRPC, GraphQL, versioning, pagination | ⭐⭐ Intermediate | ~2h |

### Phase 5: LLM AI Systems (Modules 15-18)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [15](15-llm-inference-serving/README.md) | [LLM Inference Serving](15-llm-inference-serving/README.md) | PagedAttention, batching, quantization, GPU clusters | ⭐⭐⭐ Advanced | ~2h |
| [16](16-rag-at-scale/README.md) | [RAG at Scale](16-rag-at-scale/README.md) | Chunking, two-stage retrieval, hybrid search, evaluation | ⭐⭐⭐ Advanced | ~2h |
| [17](17-agent-architecture/README.md) | [Agent Architecture](17-agent-architecture/README.md) | ReAct, middleware stack, multi-agent, cost control | ⭐⭐⭐ Advanced | ~2h |
| [18](18-production-ai-system/README.md) | [Production AI System](18-production-ai-system/README.md) | Model routing, guardrails, observability, scaling | ⭐⭐⭐ Advanced | ~2h |

---

## Complementary Courses

This course pairs with the **[LLM Engineering Course](https://github.com/dnakhoa/llm-engineering-playground)**:

| System Design (This Course) | LLM Engineering |
|---------------------------|-----------------|
| Module 15: LLM Inference Serving | Module 05-06: Deployment & Optimization |
| Module 16: RAG at Scale | Module 02: RAG Systems |
| Module 17: Agent Architecture | Module 07: Agentic Workflows |
| Module 18: Production AI | Module 08-10: LLM Ops, EvalOps, Guardrails |

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
3. Review Phase 5 (LLM AI Systems) for AI/ML system design questions
4. Practice the 9-step framework from Module 01
5. Time yourself: 45 minutes per design problem

### For Teams
1. Use as training material for new team members
2. Reference architecture decisions in design docs
3. Share the LLM modules (15-18) with AI/ML teams
4. Establish common vocabulary and patterns

---

## Glossary

### Distributed Systems Fundamentals (Modules 01-12)

| Term | Definition |
|------|-----------|
| **CAP Theorem** | A distributed system can guarantee only 2 of 3: Consistency, Availability, Partition tolerance |
| **Consensus** | Agreement among distributed nodes on a single value (e.g., Raft, Paxos) |
| **CRDT** | Conflict-Free Replicated Data Type — data structure that merges without conflicts |
| **CQRS** | Command Query Responsibility Segregation — separate write and read models |
| **Circuit Breaker** | Pattern that stops calls to a failing service to prevent cascading failures |
| **Consistent Hashing** | Hash ring that minimizes reshuffling when nodes are added/removed |
| **DLQ** | Dead Letter Queue — queue for messages that fail processing |
| **Error Budget** | The failure allowance implied by an SLO (99.9% ⇒ ~43 min/month) |
| **Event Sourcing** | Store every state change as an immutable event, not just current state |
| **Fan-out** | Distributing one message to multiple consumers |
| **Fencing Token** | Monotonically increasing token that prevents stale leaders from acting |
| **G-Counter** | Grow-only counter CRDT — can only increment |
| **Idempotency** | Property where doing an operation multiple times has the same effect as once |
| **Kafka** | Distributed event streaming platform for high-throughput message queues |
| **Lamport Timestamp** | Logical clock that tracks causality in distributed systems |
| **Leader Election** | Process of selecting one node to coordinate actions |
| **Load Balancer** | Distributes incoming traffic across multiple servers |
| **Quorum** | Read/write overlap rule (W + R > N) that guarantees a read sees the latest write |
| **Raft** | Understandable consensus algorithm used by etcd, TiKV, CockroachDB |
| **RPO / RTO** | Recovery Point Objective (tolerable data loss) / Recovery Time Objective (tolerable downtime) |
| **SAGA** | Distributed transaction pattern using compensating actions instead of locks |
| **SLI** | Service Level Indicator — what you measure (e.g., latency, error rate) |
| **SLO** | Service Level Objective — what you promise internally (e.g., 99.9% availability) |
| **Token Bucket** | Rate limiting algorithm that allows controlled bursts |
| **Vector Clock** | Logical clock that tracks causality more precisely than Lamport timestamps |
| **WebSocket** | Persistent bidirectional connection for real-time communication |
| **2PC** | Two-Phase Commit — blocking distributed transaction protocol with a coordinator |

### Security and API Design (Modules 13-14)

| Term | Definition |
|------|-----------|
| **ABAC** | Attribute-Based Access Control — policy decisions from subject/resource/environment attributes |
| **DEK / KMS** | Data Encryption Key / Key Management Service — envelope encryption hierarchy |
| **JWT** | JSON Web Token — signed, self-contained bearer token (RFC 7519) |
| **mTLS** | Mutual TLS — both client and server authenticate with certificates |
| **OAuth 2.0** | Delegated authorization framework for third-party access (RFC 6749) |
| **OWASP Top 10** | The ten most critical web application security risks |
| **Problem Details** | Standard JSON error format for HTTP APIs (RFC 9457, formerly RFC 7807) |
| **RBAC** | Role-Based Access Control — permissions granted via roles |
| **Cursor Pagination** | Opaque-token paging that stays consistent under concurrent writes |
| **gRPC** | HTTP/2 + Protobuf RPC framework with native streaming |
| **GraphQL** | Query language where clients request exactly the fields they need |
| **HATEOAS** | Hypermedia links in responses — Level 3 of the Richardson Maturity Model |
| **N+1 Problem** | One query per related record instead of one batched query; fixed with DataLoader |
| **SSRF** | Server-Side Request Forgery — tricking a server into making attacker-chosen requests |

### LLM AI Systems (Modules 15-18)

| Term | Definition |
|------|-----------|
| **Continuous Batching** | Sequences join and leave the GPU batch as they finish — raises utilization to 80-95% |
| **Contextual Chunking** | Prepending LLM-generated context to each chunk before embedding |
| **Cross-encoder** | Scores a query and document together — slow but precise; used for reranking |
| **Guardrails** | Input/output safety layer: injection detection, PII redaction, content filtering |
| **Hybrid Search** | Combining dense (vector) and sparse (BM25) retrieval |
| **KV Cache** | Cached Key/Value tensors from prior tokens — the memory bottleneck in LLM serving |
| **Lost in the Middle** | LLMs recall information at the start and end of long contexts better than the middle |
| **Model Routing** | Sending each query to the cheapest model that can answer it |
| **PagedAttention** | KV cache paging (vLLM) that cuts allocation waste from 60-80% to under 4% |
| **Prompt Injection** | Attacker input that overrides system instructions (direct or via retrieved documents) |
| **Quantization** | Storing weights at lower precision (FP8, 4-bit) to cut memory and raise throughput |
| **RadixAttention** | Prefix-tree KV cache sharing (SGLang) for requests with a common system prompt |
| **RAG** | Retrieval-Augmented Generation — grounding LLMs in external knowledge |
| **ReAct** | Agent pattern interleaving Reasoning (thoughts) and Acting (tool calls) |
| **Reranking** | Second-stage precision pass over first-stage candidates |
| **RRF** | Reciprocal Rank Fusion — merges rankings via Σ 1/(k + rank), typically k=60 |
| **Semantic Cache** | Cache keyed by query embedding similarity rather than exact string match |
| **Speculative Decoding** | Small draft model proposes tokens, large model verifies — 2-3x speedup, no quality loss |
| **Tensor Parallelism** | Splitting each layer's weights across GPUs (low latency, high communication) |

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
