# System Design: From Fundamentals to LLM AI Systems

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Modules](https://img.shields.io/badge/modules-19-blue.svg)]()
[![Theory](https://img.shields.io/badge/type-theory%20%2B%20design-orange.svg)]()

A free, self-paced course in 19 written modules. It starts at "what is a QPS
estimate" and ends at "how would you architect an LLM agent platform for a
hundred million users" — and it explains the reasoning at every step, not just
the conclusions.

**New here? [Start with Module 01](01-fundamentals/README.md).** It takes about
two hours and teaches the framework every later module assumes.

---

## What you'll be able to do

Not "what topics are covered" — what you should actually be able to do when
you're finished:

- Take a vague prompt like *"design Twitter"* and turn it into a concrete,
  defensible architecture in 45 minutes, using a repeatable 9-step framework.
- Do back-of-the-envelope math out loud — QPS, storage, bandwidth, cost — and
  explain which number drives the design.
- Say *why* you picked Postgres over Cassandra, write-through over
  write-behind, gRPC over REST, in terms of the trade-off you accepted rather
  than the technology you like.
- Recognize the failure modes before they happen: cache stampedes, hot keys,
  retry storms, split brain, unbounded metric cardinality.
- Design an LLM system that survives contact with production — inference
  serving, retrieval, agents, guardrails, and the observability to run them.

**Prerequisites:** you can read code and you know roughly what a database and
an HTTP request are. No distributed systems background needed.

## What this is, and what it isn't

Being clear about this up front will save you time:

| This course **is** | This course **is not** |
|---|---|
| Written modules you read and think about | Video lectures |
| Architecture, trade-offs, and reasoning | A coding bootcamp — the code is illustrative, not a project you build |
| Runnable, checked Python snippets that show a mechanism | A framework tutorial (no Spring, no Django) |
| Interview-oriented *and* practice-oriented | Interview-question memorisation |
| Opinionated, with the reasoning shown so you can disagree | Neutral encyclopedia coverage |

The code blocks exist to make an idea concrete — a token bucket, a saga, a
circuit breaker in ~30 lines. They're checked for syntax by the linter, but
they are teaching aids, not libraries to deploy.

## Who it's for

- **Engineers preparing for system design interviews** — Path A below.
- **ML/AI engineers** who can build a model but haven't had to run one at
  scale — Path B below.
- **Backend engineers** who want the theory behind patterns they already use.
- **Teams** who want a shared vocabulary for design reviews.

---

## How to actually learn this

Reading a system design course front to back and retaining nothing is the
default outcome. A few things that make the difference:

**1. Answer before you read on.** Every module has a Case Study. When you hit
it, stop and spend two minutes sketching your own answer first. Being wrong
and then reading the right answer sticks; reading the right answer first
doesn't.

**2. The exercises are the course.** Each module ends with a Practice Exercise
and Discussion Questions. They're where the learning happens — the prose is
setup. Many exercises include a model answer; write yours down *before*
you look.

**3. Read the Common Mistakes table twice.** Once when you get to it, and
again a week later. It's a distilled list of the specific things people get
wrong under pressure, which makes it the highest-value-per-word section in
every module.

**4. Say it out loud.** System design is assessed verbally, in interviews and
in design reviews alike. Explaining a diagram to an empty room — or a
colleague — surfaces the parts you only *think* you understand.

**5. Don't skip the estimation math.** It feels like busywork and it is the
single most common thing candidates fumble. Do it by hand until 100M/month →
~38 QPS is instant.

### What every module looks like

Every module follows the same shape, so you can navigate one you've never
opened:

| Section | What it's for |
|---|---|
| **Learning Objectives** | Check these first — if you can already do all of them, skim |
| **Table of Contents** | Jump straight to a topic when you're using this as a reference |
| Core sections | Concepts, ASCII diagrams, trade-off tables, short code examples |
| **Case Study** | A real system (Netflix, Stripe, Uber, Dapper) applying the concepts |
| **Practice Exercise** | A design problem, usually with a model answer |
| **Common Mistakes** | Mistake → why it's wrong → what to do instead |
| **Discussion Questions** | Open-ended prompts for interview practice |
| **Related Modules** | How this connects to the rest of the course |
| **Summary** | Key takeaways, worth re-reading before an interview |

---

## Learning Paths

Choose your path based on your goals:

### Path A: System Design Interview Prep (~12 hours)

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
Module 16 (Inference Serving) → Module 17 (RAG at Scale)
    → Module 18 (Agent Architecture) → Module 19 (Production AI)
```

| Priority | Module | Why |
|----------|--------|-----|
| **Must** | 16 | How to serve LLMs at scale (PagedAttention, batching) |
| **Must** | 17 | RAG is the most common LLM pattern |
| **Should** | 18 | Agents are the future of LLM applications |
| **Should** | 19 | Putting it all together in production |
| **Should** | 15 | You cannot operate an AI system you cannot observe |
| Nice to have | 01 | Foundation concepts still apply |

### Path C: Full Curriculum (~41 hours)

Work through all 19 modules in order. Each builds on the previous.

### Path D: Fill Your Gaps

Modules are written to be readable on their own. If you have a specific hole,
go straight at it:

| Your Gap | Go to |
|----------|-------|
| Can't estimate QPS/storage | [Module 01 — Fundamentals](01-fundamentals/README.md) |
| Confused by CAP, or by "eventual consistency" | [Module 01 — Fundamentals](01-fundamentals/README.md) |
| Don't know when to use SQL vs NoSQL | [Module 02 — Databases](02-databases-storage/README.md) |
| Cache invalidation keeps breaking | [Module 03 — Caching](03-caching/README.md) |
| One key is melting one cache node | [Module 03 — Caching](03-caching/README.md) |
| Retries make outages worse, not better | [Module 07 — Reliability](07-reliability/README.md) |
| Need to design a chat system | [Module 10 — Chat/News Feed](10-case-chat-newsfeed/README.md) |
| Auth, encryption, password storage, or OWASP gaps | [Module 13 — Security](13-security/README.md) |
| APIs keep breaking clients | [Module 14 — API Design](14-api-design/README.md) |
| Outages take hours to diagnose | [Module 15 — Observability](15-observability/README.md) |
| Alerts are noisy and everyone ignores them | [Module 15 — Observability](15-observability/README.md) |
| Need to serve LLMs at scale | [Module 16 — Inference Serving](16-llm-inference-serving/README.md) |
| Building a RAG system | [Module 17 — RAG at Scale](17-rag-at-scale/README.md) |
| Building autonomous agents | [Module 18 — Agent Architecture](18-agent-architecture/README.md) |
| Don't know how to monitor AI systems | [Module 19 — Production AI](19-production-ai-system/README.md) |

---

## Curriculum

### Phase 1: Foundations (Modules 01-04)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [01](01-fundamentals/README.md) | [System Design Fundamentals](01-fundamentals/README.md) | 9-step framework, CAP theorem, estimation | ⭐ Beginner | ~2h |
| [02](02-databases-storage/README.md) | [Databases and Storage](02-databases-storage/README.md) | SQL vs NoSQL, sharding, replication, ACID | ⭐ Beginner | ~1.5h |
| [03](03-caching/README.md) | [Caching Strategies](03-caching/README.md) | Cache patterns, Redis, CDN, cache stampede | ⭐⭐ Intermediate | ~2.5h |
| [04](04-load-balancing/README.md) | [Load Balancing](04-load-balancing/README.md) | Algorithms, L4/L7, rate limiting, API gateway | ⭐⭐ Intermediate | ~2.5h |

### Phase 2: Intermediate (Modules 05-08)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [05](05-async-systems/README.md) | [Async Systems](05-async-systems/README.md) | Kafka, event-driven, CQRS, delivery guarantees | ⭐⭐ Intermediate | ~2h |
| [06](06-microservices/README.md) | [Microservices](06-microservices/README.md) | DDD, saga pattern, service mesh, observability | ⭐⭐ Intermediate | ~2h |
| [07](07-reliability/README.md) | [Reliability Engineering](07-reliability/README.md) | Circuit breakers, chaos engineering, SLOs | ⭐⭐ Intermediate | ~2.5h |
| [08](08-distributed-systems/README.md) | [Distributed Systems](08-distributed-systems/README.md) | Raft, consensus, CRDTs, leader election | ⭐⭐⭐ Advanced | ~2.5h |

### Phase 3: Design Cases (Modules 09-12)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [09](09-case-url-shortener-rate-limiter/README.md) | [URL Shortener & Rate Limiter](09-case-url-shortener-rate-limiter/README.md) | ID generation, token bucket, distributed counting | ⭐⭐ Intermediate | ~1.5h |
| [10](10-case-chat-newsfeed/README.md) | [Chat System & News Feed](10-case-chat-newsfeed/README.md) | WebSocket, fan-out, presence, ranking | ⭐⭐ Intermediate | ~1.5h |
| [11](11-case-storage-streaming/README.md) | [File Storage & Video Streaming](11-case-storage-streaming/README.md) | Chunking, sync, transcoding, adaptive bitrate | ⭐⭐ Intermediate | ~1.5h |
| [12](12-case-payment-ecommerce/README.md) | [Payment System & E-commerce](12-case-payment-ecommerce/README.md) | Idempotency, inventory, flash sales, reconciliation | ⭐⭐⭐ Advanced | ~2h |

### Phase 4: Core Infrastructure (Modules 13-15)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [13](13-security/README.md) | [Security](13-security/README.md) | Auth, encryption, OWASP, prompt injection | ⭐⭐ Intermediate | ~2.5h |
| [14](14-api-design/README.md) | [API Design](14-api-design/README.md) | REST, gRPC, GraphQL, versioning, pagination | ⭐⭐ Intermediate | ~2.5h |
| [15](15-observability/README.md) | [Observability](15-observability/README.md) | Metrics, tracing, cardinality, burn-rate alerting | ⭐⭐ Intermediate | ~4h |

### Phase 5: LLM AI Systems (Modules 16-19)

| Module | Topic | Key Concepts | Difficulty | Time |
|--------|-------|-------------|------------|------|
| [16](16-llm-inference-serving/README.md) | [LLM Inference Serving](16-llm-inference-serving/README.md) | PagedAttention, batching, quantization, GPU clusters | ⭐⭐⭐ Advanced | ~2h |
| [17](17-rag-at-scale/README.md) | [RAG at Scale](17-rag-at-scale/README.md) | Chunking, two-stage retrieval, hybrid search, evaluation | ⭐⭐⭐ Advanced | ~2h |
| [18](18-agent-architecture/README.md) | [Agent Architecture](18-agent-architecture/README.md) | ReAct, middleware stack, multi-agent, cost control | ⭐⭐⭐ Advanced | ~2h |
| [19](19-production-ai-system/README.md) | [Production AI System](19-production-ai-system/README.md) | Model routing, guardrails, observability, scaling | ⭐⭐⭐ Advanced | ~2h |

---

## Complementary Courses

This course pairs with the **[LLM Engineering Course](https://github.com/dnakhoa/llm-engineering-playground)**:

| System Design (This Course) | LLM Engineering |
|---------------------------|-----------------|
| Module 16: LLM Inference Serving | Module 05-06: Deployment & Optimization |
| Module 17: RAG at Scale | Module 02: RAG Systems |
| Module 18: Agent Architecture | Module 07: Agentic Workflows |
| Module 19: Production AI | Module 08-10: LLM Ops, EvalOps, Guardrails |

**System Design** teaches you *how to think about architecture*.  
**LLM Engineering** teaches you *how to build the implementations*.

**Recommended order**: Take LLM Engineering first (build the skills), then System Design (learn to architect at scale). Or take them in parallel — each System Design module links to the relevant LLM Engineering module.

---

## Preparing for an interview specifically

The general study advice above still applies, but interviews reward a few
things that self-study doesn't naturally build:

1. **Run the clock.** Set a 45-minute timer and design out loud, on a
   whiteboard or blank doc, with no reference material. The constraint is the
   point — you're practicing the 9-step framework under the pressure it was
   designed for.
2. **Practise the first five minutes hardest.** Requirements clarification and
   estimation are the part candidates rush and interviewers weight heavily.
   Get those to the point of boredom.
3. **Rehearse the trade-off sentence.** "I'd choose X because Y, and the cost
   is Z." If you can't finish that sentence for a component, you don't
   understand it yet.
4. **Do Phase 3 twice.** The four design cases (Modules 09–12) map onto most
   commonly asked questions. Second pass, do them from memory first.
5. **Expect the follow-up.** Interviewers push on scale ("now 100×") and
   failure ("now that region is gone"). The Discussion Questions in each
   module are written in that voice on purpose.

## Using this with a team

- Onboarding: assign Phases 1–2 as a reading track for new backend hires.
- Design reviews: the Glossary below is a ready-made shared vocabulary — much
  of the friction in a review is two people using "consistency" differently.
- Reference: link a specific module section from an architecture decision
  record instead of re-explaining the trade-off each time.
- AI teams: Modules 15–19 stand alone reasonably well for an ML group that
  already has backend fundamentals.

---

## Glossary

### Distributed Systems Fundamentals (Modules 01-12)

| Term | Definition |
|------|-----------|
| **CAP Theorem** | During a network partition, a distributed system must give up either consistency or availability. Partition tolerance is not optional — "pick 2 of 3" is the common misstatement |
| **PACELC** | CAP plus the normal case: if Partitioned, choose A or C; Else, choose Latency or Consistency |
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

### Security, API Design, and Observability (Modules 13-15)

| Term | Definition |
|------|-----------|
| **ABAC** | Attribute-Based Access Control — policy decisions from subject/resource/environment attributes |
| **Argon2id** | Memory-hard password hashing function; OWASP's first recommendation for storing passwords |
| **Salt** | Per-user random value stored with a password hash so identical passwords hash differently |
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
| **Burn Rate** | How fast you're consuming error budget; 1× exactly exhausts it over the SLO window |
| **Cardinality** | Distinct time series for a metric — the *product* of its label value counts, and what you pay for |
| **Exemplar** | A trace ID attached to a metric observation, linking "p99 spiked" to an actual slow request |
| **Four Golden Signals** | Latency, traffic, errors, saturation — the baseline for any user-facing service |
| **Head/Tail Sampling** | Deciding to keep a trace at ingress (cheap, blind to outcome) vs after completion (keeps all errors, needs stateful collectors) |
| **Histogram vs Summary** | Bucket counts aggregate across instances; client-side quantiles do not |
| **OpenTelemetry** | Vendor-neutral standard for metrics, logs, and traces (API, SDK, OTLP wire format) |
| **RED / USE** | Rate-Errors-Duration for services; Utilization-Saturation-Errors for resources |
| **Span** | One unit of work in a trace, carrying trace ID, span ID, parent ID, and duration |
| **Structured Logging** | Stable event name plus queryable fields, instead of an interpolated sentence |
| **Trace Context** | W3C `traceparent` header that carries trace ID and sampling decision across hops |

### LLM AI Systems (Modules 16-19)

| Term | Definition |
|------|-----------|
| **A2A (Agent2Agent Protocol)** | Linux Foundation standard for cross-framework agent-to-agent task delegation and peer discovery |
| **Continuous Batching** | Sequences join and leave the GPU batch as they finish — raises utilization to 80-95% |
| **Contextual Chunking** | Prepending LLM-generated context to each chunk before embedding |
| **Cross-encoder** | Scores a query and document together — slow but precise; used for reranking |
| **Disaggregated Prefill/Decode** | Separate GPU pools for prompt processing vs. token generation, linked by KV-cache transfer |
| **GenAI Semantic Conventions** | OpenTelemetry's standard schema for LLM and agent spans, events, and metrics |
| **Guardrails** | Input/output safety layer: injection detection, PII redaction, content filtering |
| **Hybrid Search** | Combining dense (vector) and sparse (BM25) retrieval |
| **KV Cache** | Cached Key/Value tensors from prior tokens — the memory bottleneck in LLM serving |
| **Late Chunking** | Embedding the full document first, then splitting into per-chunk vectors — no extra tokens |
| **Lost in the Middle** | LLMs recall information at the start and end of long contexts better than the middle |
| **MCP (Model Context Protocol)** | Standard for how an agent discovers and calls external tools, data, and prompts |
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
| **Trajectory-Aware Evaluation** | Scoring an agent's tool calls, steps, and recovery behavior — not just its final answer |

---

## References

Each module has its own Key References section pointing at the primary sources
for that topic. The list below is the general reading behind the course.

### Essential Books

If you read only one, read *Designing Data-Intensive Applications* — it is the
depth this course points toward.

| Book | Author | Focus |
|------|--------|-------|
| Designing Data-Intensive Applications | Martin Kleppmann | Distributed systems depth |
| System Design Interview (Vol 1 & 2) | Alex Xu | Interview prep, breadth |
| Site Reliability Engineering | Google | Reliability practices, golden signals |
| The Site Reliability Workbook | Google | Practical SLO and burn-rate alerting |
| Observability Engineering | Majors, Fong-Jones, Miranda | High-cardinality debugging |
| Building Microservices | Sam Newman | Service architecture |
| Designing Machine Learning Systems | Chip Huyen | ML in production |

### Engineering Blogs
- Meta Engineering, Netflix Tech Blog, Uber Engineering
- Google AI Blog, OpenAI Blog, Anthropic Research
- vLLM Blog, LangChain Blog, Honeycomb Blog

### Key Papers and Standards
| Reference | Year | Topic |
|-----------|------|-------|
| Dapper (Google) | 2010 | Distributed tracing foundations |
| PACELC (Abadi) | 2012 | Consistency/latency trade-off beyond CAP |
| CAP Twelve Years Later (Brewer) | 2012 | Why "pick two of three" is a misreading |
| OWASP Password Storage Cheat Sheet | Living | Argon2id parameters and rationale |
| W3C Trace Context | 2021 | Interoperable trace propagation |
| PagedAttention (vLLM) | 2023 | KV cache optimization |
| Speculative Decoding | 2022 | Inference acceleration |
| ReAct | 2022 | Agent planning |
| RAG Survey | 2023 | RAG taxonomy |

## Contributing

Corrections and additions are welcome. Before opening a pull request, run:

```bash
python3 tools/lint.py
```

It checks four things that are easy to break and hard to spot in review:

| Check | Catches |
|-------|---------|
| Python blocks parse | Typos that make an example non-runnable |
| Diagram geometry | Box borders that drift out of alignment — invisible while editing, obvious once rendered |
| Relative links | Broken cross-module references, especially after renumbering |
| Anchor fragments | Table-of-contents and `#heading` links that point at nothing |

Corrections to technical claims are especially welcome — please include a
primary source (paper, spec, or vendor docs) rather than a blog summary.

## License

[MIT](LICENSE) — use, modify, and share freely, including in commercial training material. Attribution is appreciated but not required.

---

## Ready?

[**Start with Module 01: System Design Fundamentals →**](01-fundamentals/README.md)

Take your time, do the exercises, and argue with the trade-off tables. Good luck.

<sub>**Keywords:** system design, system design course, distributed systems, LLM system design, AI architecture, system design interview, microservices, caching, load balancing, observability, distributed tracing, OpenTelemetry, SLO alerting, API design, security, RAG architecture, agent systems, vLLM, inference serving</sub>
