# Module 19: Production AI System Architecture

> **Putting it all together — the full AI-native system.** This module is the capstone: it shows how inference serving, RAG, agents, guardrails, and observability compose into a production AI system.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 18 | Agent System Architecture | [../18-agent-architecture/](../18-agent-architecture/) |
| **Module 19** | **Production AI System Architecture** | **(current)** |
| Course Home | — | [../README.md](../README.md) |

---

## Learning Objectives

- Design end-to-end AI system architecture
- Implement model routing for cost-quality optimization
- Build production guardrails pipelines (input + output)
- Design observability and monitoring for AI systems
- Scale from prototype to 100M users

**This module synthesizes**: Module 16 (inference serving) + Module 17 (RAG) + Module 18 (agents) + Module 15 (observability) + Module 07 (reliability) + Module 03 (caching).

---

## Table of Contents

1. [End-to-End AI System Architecture](#end-to-end-ai-system-architecture)
2. [Model Routing](#model-routing)
3. [Prompt Management at Scale](#prompt-management-at-scale)
4. [Guardrails Architecture](#guardrails-architecture)
5. [Observability and Monitoring](#observability-and-monitoring)
6. [Scaling from Prototype to 100M Users](#scaling-from-prototype-to-100m-users)
7. [Security Considerations](#security-considerations)
8. [Case Study: ChatGPT-Scale Architecture](#case-study-chatgpt-scale-architecture)
9. [Practice Exercises](#practice-exercises)
10. [Key References](#key-references)
11. [Common Mistakes](#common-mistakes)
12. [Discussion Questions](#discussion-questions)

---

## End-to-End AI System Architecture

```
┌───────────────────────────────────────────────────────────┐
│              Production AI System Architecture            │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Client (Web/Mobile/API)                                  │
│  │                                                        │
│  ▼                                                        │
│  ┌───────────────────────────────────────────────────┐    │
│  │  API Gateway (Module 04)                          │    │
│  │  - Authentication (JWT, OAuth)                    │    │
│  │  - Rate limiting (per-user, per-tier)             │    │
│  │  - Request validation                             │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Semantic Cache (Module 03)                       │    │
│  │  - Embed query → check cache → hit? return cached │    │
│  │  - Miss? → continue to model router               │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Model Router (this module)                       │    │
│  │  - Classify query complexity                      │    │
│  │  - Route to appropriate model                     │    │
│  │  - Balance cost vs quality                        │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│         ┌───────────────┼───────────────┐                 │
│         ▼               ▼               ▼                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ Small Model│  │ Large Model│  │ Reasoning  │           │
│  │ (7B, fast) │  │ (70B,      │  │ Model      │           │
│  │            │  │  accurate) │  │ (o3, deep) │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│         │               │               │                 │
│         └───────────────┼───────────────┘                 │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  RAG Pipeline (Module 16)                         │    │
│  │  - Query → Retrieve → Rerank → Augment            │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Guardrails Pipeline (this module)                │    │
│  │  Input: Validation → PII Detection → Injection    │    │
│  │  Output: Hallucination → PII → Content Filter     │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Observability (this module)                      │    │
│  │  - Tracing (OpenTelemetry)                        │    │
│  │  - Cost tracking                                  │    │
│  │  - Quality monitoring                             │    │
│  │  - Drift detection                                │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Model Routing

Route queries to the right model based on complexity. This is the single biggest cost optimization lever.

```
┌───────────────────────────────────────────────────────────┐
│              Model Routing Decision Tree                  │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Query arrives                                            │
│  │                                                        │
│  ▼                                                        │
│  Simple query? (greeting, FAQ, simple lookup)             │
│  ├── Yes → Small model (7B, $0.001/query)                 │
│  │                                                        │
│  Medium query? (summarization, analysis, coding)          │
│  ├── Yes → Medium model (70B, $0.01/query)                │
│  │                                                        │
│  Complex query? (reasoning, math, multi-step)             │
│  ├── Yes → Reasoning model (o3, $0.10/query)              │
│  │                                                        │
│  Unknown complexity?                                      │
│  ├── Start with small model                               │
│  ├── If quality insufficient → escalate to larger         │
│  └── Track escalation rate for routing improvements       │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Routing Strategies

| Strategy | Description | Trade-off |
|----------|-------------|-----------|
| **Rule-based** | Keywords/patterns → model | Simple, misses edge cases |
| **Classifier** | ML model predicts complexity | More accurate, adds latency |
| **Cascade** | Start small, escalate if needed | Cost-efficient, variable latency |
| **A/B test** | Route randomly, measure quality | Data-driven, slow optimization |

### Cost Impact

```
  Without routing (all queries → GPT-4):
  1M queries/day × $0.03/query = $30,000/day = $900K/month

  With routing (70% small, 25% medium, 5% reasoning):
  700K × $0.001 + 250K × $0.01 + 50K × $0.10
  = $700 + $2,500 + $5,000 = $8,200/day = $246K/month

  Savings: $654K/month (73% cost reduction)
```

---

## Prompt Management at Scale

### Prompt Versioning

```
  Prompt registry:
  ┌──────────────────────────────────────────────────────┐
  │  prompts/                                            │
  │  ├── customer_support/                               │
  │  │   ├── v1.0.txt  (2024-01-15, baseline)            │
  │  │   ├── v1.1.txt  (2024-02-20, + examples)          │
  │  │   ├── v1.2.txt  (2024-03-10, + safety rules)      │
  │  │   └── current.txt → v1.2.txt (symlink)            │
  │  │                                                   │
  │  ├── code_review/                                    │
  │  │   ├── v1.0.txt                                    │
  │  │   └── current.txt → v1.0.txt                      │
  │  │                                                   │
  │  └── summarization/                                  │
  │      ├── v1.0.txt                                    │
  │      ├── v1.1.txt (shorter summaries)                │
  │      └── current.txt → v1.1.txt                      │
  └──────────────────────────────────────────────────────┘

  Each prompt version:
  - Has a unique ID (v1.2)
  - Tracks which model it works best with
  - Has evaluation scores
  - Can be rolled back if quality degrades
```

### A/B Testing for LLM Outputs

```
  ┌────────────────────────────────────────────────────────┐
  │  A/B Testing for Prompts                               │
  │                                                        │
  │  Traffic: 1000 queries/day                             │
  │                                                        │
  │  Control (50%): Prompt v1.1                            │
  │  Treatment (50%): Prompt v1.2                          │
  │                                                        │
  │  Metrics:                                              │
  │  - User satisfaction (thumbs up/down)                  │
  │  - Task completion rate                                │
  │  - Latency                                             │
  │  - Cost                                                │
  │                                                        │
  │  After 7 days:                                         │
  │  - v1.1: 78% satisfaction, $0.005/query                │
  │  - v1.2: 85% satisfaction, $0.006/query                │
  │                                                        │
  │  Decision: v1.2 wins (7% improvement, 20% cost increase│
  │  acceptable)                                           │
  └────────────────────────────────────────────────────────┘
```

---

## Guardrails Architecture

Guardrails are the safety layer between your users and the LLM. They protect against prompt injection, PII leakage, and harmful content.

### Input Guardrails

```
┌───────────────────────────────────────────────────────────┐
│              Input Guardrails Pipeline                    │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  User input                                               │
│  │                                                        │
│  ▼                                                        │
│  ┌────────────────────────────────────────────────────┐   │
│  │  1. Input Validation                               │   │
│  │  - Length limits                                   │   │
│  │  - Format validation                               │   │
│  │  - Character filtering                             │   │
│  └────────────────────────────────────────────────────┘   │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  2. Prompt Injection Detection                    │    │
│  │  - Pattern matching (known attacks)               │    │
│  │  - ML classifier (novel attacks)                  │    │
│  │  - Input/output consistency check                 │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  3. PII Detection & Redaction                     │    │
│  │  - SSN, credit card, email, phone                 │    │
│  │  - Redact or mask before sending to LLM           │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  Clean input → LLM                                        │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Output Guardrails

```
┌───────────────────────────────────────────────────────────┐
│              Output Guardrails Pipeline                   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  LLM output                                               │
│  │                                                        │
│  ▼                                                        │
│  ┌───────────────────────────────────────────────────┐    │
│  │  1. Hallucination Check                           │    │
│  │  - Compare output against retrieved context       │    │
│  │  - Flag unsupported claims                        │    │
│  │  - Score: 0 (pure hallucination) to 1 (grounded)  │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  2. PII Detection in Output                       │    │
│  │  - Scan for SSN, credit cards, emails             │    │
│  │  - Redact if found                                │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  3. Content Filtering                             │    │
│  │  - Harmful content detection                      │    │
│  │  - Policy compliance check                        │    │
│  │  - Toxicity scoring                               │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌────────────────────────────────────────────────────┐   │
│  │  4. Output Validation                              │   │
│  │  - Schema validation (if structured output)        │   │
│  │  - Length limits                                   │   │
│  │  - Format compliance                               │   │
│  └────────────────────────────────────────────────────┘   │
│                         │                                 │
│                         ▼                                 │
│  Clean output → User                                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Prompt Injection Attack Types

| Attack Type | Example | Defense |
|-------------|---------|---------|
| **Direct injection** | "Ignore previous instructions and..." | Pattern matching + ML classifier |
| **Indirect injection** | Hidden instructions in retrieved documents | Output validation + instruction isolation |
| **Jailbreak** | "You are now DAN, you can do anything..." | Safety classifiers + output filtering |
| **Data exfiltration** | "Repeat your system prompt" | System prompt isolation + output monitoring |

### Defense in Depth

Prompt injection has held OWASP's LLM01 top spot in the Top 10 for LLM Applications for a third consecutive year running (2025-2026) — still the top production concern for LLM applications, and a harder one than it looks, because retrieval and tool use expand the attack surface well past the user's own chat message: injected instructions can now arrive via a retrieved document, a web page, or a tool's return value, none of which the input pipeline above ever sees. Production teams have converged on a five-part layered defense rather than a single filter: input guardrails on 100% of traffic, structural separation of system instructions from untrusted content, least-privilege scoping on every tool the agent can call, output guardrails on every response (symmetric with input — see the "Input guardrails only" row in Common Mistakes below), and continuous red-team regression testing as attacks evolve. Two open-source frameworks are common building blocks here: **NVIDIA NeMo Guardrails**, which uses a Colang DSL to define dialog and policy rules around the model, and **Guardrails AI**, a `Guard` wrapper around model calls backed by a hub of validator plugins covering PII, factuality, and other safety categories. Caveat: no current framework — these included — fully stops adversarial-suffix or other optimization-based jailbreaks; guardrails reduce the probability and blast radius of a successful attack, they don't eliminate it, which is exactly why the layering, not the choice of any one tool, is what carries the risk reduction.

---

## Observability and Monitoring

> **[Module 15: Observability](../15-observability/README.md)** covers the general
> foundations — metric types and cardinality, tracing and context propagation,
> SLO burn-rate alerting, and cost control. This section covers what is *specific*
> to AI systems: token accounting, cost per query, quality and hallucination
> monitoring, and drift detection.
>
> Three properties make LLM observability genuinely different:
>
> | Property | Consequence |
> |----------|-------------|
> | **Cost varies per request** | Tokens, not requests, are the billable unit — so cost is a first-class metric, not an infrastructure detail |
> | **Correctness is not binary** | There is no status code for "confidently wrong", so quality needs sampled LLM-as-judge scoring and user feedback |
> | **The model is a moving dependency** | A provider-side update changes behavior with no deploy on your side — pin versions and re-evaluate before promoting |

By 2026 the "Observability (OpenTelemetry)" box above has an actual standard to instrument against, not just a generic aspiration. OpenTelemetry — which reached CNCF Graduated status in May 2026 — now ships **GenAI Semantic Conventions**: a standard schema for LLM and agent telemetry covering six areas — LLM client spans (per-call model, token counts, latency), agent spans, events (opt-in capture of prompt/completion content), metrics (token usage, cost, time-to-first-token), agent-orchestration spans, and MCP (Model Context Protocol) tool-calling spans. Because the schema is vendor-neutral and OTLP-based, the same instrumentation is readable by any OTLP-speaking backend — Google Cloud, AWS, Azure, and Datadog all consume it without a proprietary SDK. Caveat: several span and attribute names are still marked experimental and have shifted across releases, so pin the semconv version you instrument against and check the changelog before bumping it.

### The Observability Stack

```
┌───────────────────────────────────────────────────────────┐
│              AI Observability Stack                       │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Traces (OpenTelemetry)                           │    │
│  │  - Every LLM call traced end-to-end               │    │
│  │  - Latency per component                          │    │
│  │  - Token usage per call                           │    │
│  │  - Error rates                                    │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Metrics (Prometheus/Grafana)                     │    │
│  │  - Requests per second                            │    │
│  │  - P50/P95/P99 latency                            │    │
│  │  - Token usage (input/output)                     │    │
│  │  - Cost per query                                 │    │
│  │  - Error rate                                     │    │
│  │  - Cache hit ratio                                │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Quality Monitoring                               │    │
│  │  - LLM-as-judge scoring (sample of responses)     │    │
│  │  - User feedback (thumbs up/down)                 │    │
│  │  - Task completion rate                           │    │
│  │  - Hallucination rate                             │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Drift Detection                                  │    │
│  │  - Input distribution shift                       │    │
│  │  - Output quality degradation                     │    │
│  │  - Model performance drift                        │    │
│  │  - Cost drift                                     │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Key Metrics Dashboard

```
┌──────────────────────────────────────────────────────────┐
│              AI System Dashboard                         │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Requests: 1,234/min  │  Latency P95: 320ms              │
│  Errors: 0.12%        │  Cost: $0.003/query              │
│                                                          │
│  ┌───────────────────────────────────────────────────┐   │
│  │  Model Usage Distribution                         │   │
│  │  Small (7B):  ████████████████████ 65%            │   │
│  │  Medium (70B): ██████████ 30%                     │   │
│  │  Reasoning:    ██ 5%                              │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Quality Metrics (last 24h)                      │    │
│  │  User satisfaction: 87% (↑2% from yesterday)     │    │
│  │  Hallucination rate: 3.2% (↓0.5%)                │    │
│  │  Task completion: 92% (→ same)                   │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Cost Breakdown                                  │    │
│  │  LLM API: $1,234/day                             │    │
│  │  Vector DB: $45/day                              │    │
│  │  Compute: $234/day                               │    │
│  │  Total: $1,513/day                               │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Scaling from Prototype to 100M Users

```
┌───────────────────────────────────────────────────────────┐
│                    Scaling Stages                         │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Stage 1: Prototype (0-1K users)                          │
│  ┌───────────────────────────────────────────────────┐    │
│  │  - Single server (FastAPI + SQLite)               │    │
│  │  - Direct LLM API calls (no routing)              │    │
│  │  - Basic logging                                  │    │
│  │  Cost: ~$100/month                                │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  Stage 2: Growth (1K-100K users)                          │
│  ┌───────────────────────────────────────────────────┐    │
│  │  - Load balancer + 2-3 API servers                │    │
│  │  - PostgreSQL + Redis cache                       │    │
│  │  - Basic rate limiting                            │    │
│  │  - Model routing (small vs large)                 │    │
│  │  Cost: ~$5K/month                                 │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  Stage 3: Scale (100K-10M users)                          │
│  ┌───────────────────────────────────────────────────┐    │
│  │  - Kubernetes cluster                             │    │
│  │  - Multiple model endpoints                       │    │
│  │  - Full guardrails pipeline                       │    │
│  │  - Observability stack (OpenTelemetry)            │    │
│  │  - A/B testing framework                          │    │
│  │  - CDN for static assets                          │    │
│  │  Cost: ~$50K/month                                │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  Stage 4: Enterprise (10M-100M users)                     │
│  ┌──────────────────────────────────────────────────┐     │
│  │  - Multi-region deployment                       │     │
│  │  - Custom model hosting (vLLM clusters)          │     │
│  │  - Advanced caching (semantic cache)             │     │
│  │  - ML-based model routing                        │     │
│  │  - Full audit trail                              │     │
│  │  - SOC 2 compliance                              │     │
│  │  Cost: ~$500K/month                              │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### What Changes at Each Stage

| Component | Prototype | Growth | Scale | Enterprise |
|-----------|-----------|--------|-------|------------|
| **Load balancing** | None | Nginx | Kubernetes | Global LB |
| **Database** | SQLite | PostgreSQL | Sharded PostgreSQL | Distributed SQL |
| **Caching** | None | Redis | Redis cluster | Semantic cache |
| **LLM routing** | None | Rule-based | ML classifier | Custom routing |
| **Guardrails** | None | Basic rules | Full pipeline | Multi-layer |
| **Observability** | print() | Structured logs | OpenTelemetry | Full stack |
| **Deployment** | Single server | 2-3 servers | Kubernetes | Multi-region |

---

## Security Considerations

### Prompt Injection Defense

```
  Defense layers:
  1. Input validation (block known patterns)
  2. ML classifier (detect novel attacks)
  3. System prompt isolation (delimit user input)
  4. Output validation (check for instruction leakage)
  5. Rate limiting (prevent automated attacks)
```

### Data Privacy

```
  Data handling:
  - PII detection on input → redact before LLM
  - No logging of raw user inputs (or encrypt)
  - Data retention policies (delete after N days)
  - GDPR compliance (right to deletion)
  - Model provider data processing agreements
```

---

## Case Study: ChatGPT-Scale Architecture

### OpenAI's Design Decisions

1. **Massive GPU clusters**: Tens of thousands of GPUs. Custom networking for tensor parallelism.

2. **Multi-model routing**: GPT-4o for general use, o1/o3 for reasoning, GPT-4o-mini for cost-sensitive workloads.

3. **Global edge caching**: System prompts and common completions cached at edge locations.

4. **Content policy enforcement**: Multi-layer safety system (input filtering, output filtering, policy engine).

5. **A/B testing at scale**: Every feature change is A/B tested on a subset of users before full rollout.

---

## Practice Exercises

### Exercise 1: Architecture Design (30 min)

Design a customer support AI system that:
- Handles 10K queries/day
- Uses RAG to answer from a knowledge base of 50K articles
- Routes simple questions to a small model, complex ones to a large model
- Has guardrails for PII detection and harmful content

Draw the architecture diagram. List each component and its purpose.

### Exercise 2: Cost Optimization (20 min)

Your AI system costs $50K/month. Break down:
- 60% of queries are simple (could use 7B model)
- 30% are medium (need 70B model)
- 10% are complex (need reasoning model)

Currently all queries go to GPT-4 ($0.03/query). Design a routing strategy and calculate savings.

### Exercise 3: Guardrails Design (20 min)

Your AI system handles medical questions. Design the guardrails pipeline:
- What inputs should be blocked?
- What outputs should be filtered?
- How do you handle hallucinations in medical advice?

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| "Designing Machine Learning Systems" (Chip Huyen) | Book | ML in production |
| OpenAI Platform Documentation | Docs | API design, best practices |
| Anthropic Research | Blog | Safety, alignment |
| Google ML System Design | Paper | ML infrastructure |
| OpenTelemetry GenAI Semantic Conventions | Spec | Standard schema for LLM/agent telemetry |
| OWASP Top 10 for LLM Applications (2025) | Standard | Prompt injection and LLM-specific risks |
| NeMo Guardrails / Guardrails AI Documentation | Docs | Current guardrail framework examples |

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Routing everything to the largest model** | Usually a 5-10x overspend; most traffic is simple | Route by complexity; measure the escalation rate to tune it |
| **Cascading without a cost ceiling** | Small-then-large on every escalation costs *more* than going large directly | Track the crossover point; skip the cascade when the classifier is confident |
| **Semantic cache thresholds set too loose** | "How do I cancel?" returns the answer to "How do I upgrade?" | Tune the threshold on real query pairs; log near-misses |
| **Caching personalized or authorized responses** | One tenant's data served to another — a data breach, not a cache bug | Namespace cache keys by tenant and auth scope |
| **Input guardrails only** | The model can still emit PII, harmful content, or leak the system prompt | Guard both directions; output filtering is not optional |
| **Regex-only prompt injection detection** | Trivially bypassed by paraphrase, encoding, or translation | Layer classifiers with instruction/data separation and least-privilege tools |
| **Trusting retrieved documents** | Indirect injection arrives through your own RAG corpus | Treat retrieved text as untrusted data, never as instructions |
| **No per-request cost attribution** | You see the monthly bill but not which feature or tenant caused it | Tag every call with tenant, feature, and model; alert on anomalies |
| **Logging prompts and completions verbatim** | User PII lands in your observability stack, often outside your compliance boundary | Redact before logging; keep hashes and metrics, sample raw text narrowly |
| **Prompts edited in production** | An untracked change degrades quality with no diff to inspect and no way back | Version prompts like code: reviewed, evaluated, rollback-able |
| **Averaged quality metrics only** | A 4.2/5 mean hides the 5% of catastrophic answers that drive churn | Watch the tail: worst-case scores, refusal rate, hallucination rate |
| **Deploying a new model version without re-evaluating** | Provider updates shift behavior; prompts tuned for the old version silently regress | Pin versions; run the eval suite before promoting |

---

## Discussion Questions

1. You're building an AI-powered customer support system. Design the full architecture from request to response. What components do you need?

   **Model answer**: API Gateway → Semantic Cache → Model Router → (Small/Large/Reasoning model) → RAG Pipeline → Guardrails → Observability. Key components: cache for repeated queries, model routing for cost optimization, RAG for grounding, guardrails for safety, observability for monitoring.

2. Design a model routing system that balances cost and quality. How do you classify query complexity?

   **Model answer**: Start with rule-based routing (keywords, query length). Track escalation rates. If 20%+ of small model responses get escalated, retrain the classifier. Use A/B testing to validate routing decisions. Key metric: cost per successful resolution.

3. Your AI system serves 1M queries/day. The hallucination rate is 5%. Design a guardrails pipeline to reduce it to <1%.

   **Model answer**: Add citation requirements to prompt → output validation checks if claims are grounded in retrieved context → LLM-as-judge scores faithfulness → flag low-scored responses for human review. Expect 2-3% from citation validation, 1% from output filtering, 0.5% from human review.

4. You're scaling from 10K to 1M users. What changes in your architecture? What new components do you need?

   **Model answer**: Add load balancer, sharded database, Redis cache, model routing, full guardrails pipeline, observability stack. Key new components: semantic cache (saves 30-50% of LLM calls), model routing (saves 70% of LLM cost), distributed tracing.

5. Design an observability dashboard for an AI system. What metrics would you track, and how would you visualize them?

   **Model answer**: Track: requests/min, P95 latency, error rate, cost/query, model usage distribution, hallucination rate, user satisfaction, cache hit ratio. Visualize: time series for trends, heatmaps for latency distribution, pie charts for model usage, gauges for SLO compliance.

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 16: LLM Inference Serving Architecture](../16-llm-inference-serving/README.md) | Model Routing's small/medium/reasoning-model cascade is a direct application of the serving and batching architectures covered there |
| [Module 17: RAG System Architecture at Scale](../17-rag-at-scale/README.md) | The RAG Pipeline stage in the end-to-end architecture and the customer-support practice exercise assume the retrieval and reranking design covered there |
| [Module 15: Observability](../15-observability/README.md) | Observability and Monitoring builds directly on Module 15's tracing and SLO foundations, adding token cost, quality, and drift metrics specific to AI systems |
| [Module 03: Caching Strategies](../03-caching/README.md) | The semantic cache in the request path — and its failure modes in Common Mistakes — extends the caching patterns covered there |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│              Production AI System — Key Takeaways              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Route by complexity, not by default — flattening every     │
│     query to the biggest model is a 5-10x overspend            │
│  2. Semantic caching only pays off with tenant-scoped keys and │
│     a threshold tuned on real near-miss queries                │
│  3. Guardrails are symmetric — an input filter with no output  │
│     filter still lets PII and unsafe content through           │
│  4. Treat retrieved documents and tool results as untrusted    │
│     data, never as instructions                                │
│  5. Instrument against the OpenTelemetry GenAI Semantic        │
│     Conventions — portable traces and cost beat a vendor-locked│
│     SDK                                                        │
│  6. Defense in depth beats any single filter — prompt injection│
│     has held OWASP's LLM01 top spot three years running        │
│  7. Version and evaluate prompts like code — an unreviewed     │
│     production edit is risk with no rollback                   │
│  8. Watch tail quality, not the average — a 4.2/5 mean hides   │
│     the catastrophic 5% driving churn                          │
│  9. A production AI system is this whole course arriving at    │
│     once — caching, reliability, security, and observability   │
│     wrapped around an inference-and-retrieval core             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 18: Agent System Architecture](../18-agent-architecture/README.md)

**Next:** [Course Home](../README.md)

---

*Module 19 of 19 in the System Design Playground*

