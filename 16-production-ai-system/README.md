# Module 16: Production AI System Architecture

> **Putting it all together — the full AI-native system.** This module synthesizes everything from the course into a complete production architecture for AI-powered applications.

## Learning Objectives

- Design end-to-end AI system architecture
- Implement model routing for cost-quality optimization
- Build production guardrails pipelines
- Design observability and monitoring for AI systems
- Scale from prototype to 100M users

---

## End-to-End AI System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Production AI System Architecture            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Client (Web/Mobile/API)                                │
│  │                                                       │
│  ▼                                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  API Gateway                                       │   │
│  │  - Authentication (JWT, OAuth)                    │   │
│  │  - Rate limiting (per-user, per-tier)             │   │
│  │  - Request validation                             │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Model Router                                     │   │
│  │  - Classify query complexity                      │   │
│  │  - Route to appropriate model                     │   │
│  │  - Balance cost vs quality                        │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│         ┌───────────────┼───────────────┐              │
│         ▼               ▼               ▼              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐      │
│  │ Small Model│  │ Large Model│  │ Reasoning  │      │
│  │ (7B, fast, │  │ (70B,      │  │ Model      │      │
│  │  cheap)    │  │  accurate) │  │ (o3, deep) │      │
│  └────────────┘  └────────────┘  └────────────┘      │
│         │               │               │              │
│         └───────────────┼───────────────┘              │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  RAG Pipeline (optional)                          │   │
│  │  - Query → Retrieve → Rerank → Augment           │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Guardrails Pipeline                              │   │
│  │  Input: Validation → PII Detection → Injection   │   │
│  │  Output: Hallucination → PII → Content Filter    │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Observability                                    │   │
│  │  - Tracing (OpenTelemetry)                       │   │
│  │  - Cost tracking                                  │   │
│  │  - Quality monitoring                             │   │
│  │  - Drift detection                                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Model Routing

Route queries to the right model based on complexity.

```
┌─────────────────────────────────────────────────────────┐
│              Model Routing Decision Tree                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Query arrives                                          │
│  │                                                       │
│  ▼                                                       │
│  Simple query? (greeting, FAQ, simple lookup)           │
│  ├── Yes → Small model (7B, $0.001/query)              │
│  │                                                       │
│  Medium query? (summarization, analysis, coding)        │
│  ├── Yes → Medium model (70B, $0.01/query)             │
│  │                                                       │
│  Complex query? (reasoning, math, multi-step)           │
│  ├── Yes → Reasoning model (o3, $0.10/query)           │
│  │                                                       │
│  Unknown complexity?                                     │
│  ├── Start with small model                             │
│  ├── If quality insufficient → escalate to larger       │
│  └── Track escalation rate for routing improvements     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Routing Strategies

| Strategy | Description | Trade-off |
|----------|-------------|-----------|
| **Rule-based** | Keywords/patterns → model | Simple, misses edge cases |
| **Classifier** | ML model predicts complexity | More accurate, adds latency |
| **Cascade** | Start small, escalate if needed | Cost-efficient, variable latency |
| **A/B test** | Route randomly, measure quality | Data-driven, slow optimization |

---

## Prompt Management at Scale

### Prompt Versioning

```
  Prompt registry:
  ┌─────────────────────────────────────────────────────┐
  │  prompts/                                            │
  │  ├── customer_support/                              │
  │  │   ├── v1.0.txt  (2024-01-15, baseline)         │
  │  │   ├── v1.1.txt  (2024-02-20, + examples)       │
  │  │   ├── v1.2.txt  (2024-03-10, + safety rules)   │
  │  │   └── current.txt → v1.2.txt (symlink)          │
  │  │                                                   │
  │  ├── code_review/                                   │
  │  │   ├── v1.0.txt                                   │
  │  │   └── current.txt → v1.0.txt                     │
  │  │                                                   │
  │  └── summarization/                                 │
  │      ├── v1.0.txt                                   │
  │      ├── v1.1.txt (shorter summaries)               │
  │      └── current.txt → v1.1.txt                     │
  └─────────────────────────────────────────────────────┘

  Each prompt version:
  - Has a unique ID (v1.2)
  - Tracks which model it works best with
  - Has evaluation scores
  - Can be rolled back if quality degrades
```

### A/B Testing for LLM Outputs

```
  ┌─────────────────────────────────────────────────────┐
  │  A/B Testing for Prompts                             │
  │                                                       │
  │  Traffic: 1000 queries/day                           │
  │                                                       │
  │  Control (50%): Prompt v1.1                         │
  │  Treatment (50%): Prompt v1.2                       │
  │                                                       │
  │  Metrics:                                            │
  │  - User satisfaction (thumbs up/down)               │
  │  - Task completion rate                              │
  │  - Latency                                           │
  │  - Cost                                              │
  │                                                       │
  │  After 7 days:                                       │
  │  - v1.1: 78% satisfaction, $0.005/query             │
  │  - v1.2: 85% satisfaction, $0.006/query             │
  │                                                       │
  │  Decision: v1.2 wins (7% improvement, 20% cost increase│
  │  acceptable)                                         │
  └─────────────────────────────────────────────────────┘
```

---

## Guardrails Architecture

### Input Guardrails

```
┌─────────────────────────────────────────────────────────┐
│              Input Guardrails Pipeline                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User input                                             │
│  │                                                       │
│  ▼                                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  1. Input Validation                              │   │
│  │  - Length limits                                   │   │
│  │  - Format validation                               │   │
│  │  - Character filtering                             │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  2. Prompt Injection Detection                    │   │
│  │  - Pattern matching (known attacks)               │   │
│  │  - ML classifier (novel attacks)                  │   │
│  │  - Input/output consistency check                 │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  3. PII Detection & Redaction                     │   │
│  │  - SSN, credit card, email, phone                 │   │
│  │  - Redact or mask before sending to LLM          │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  Clean input → LLM                                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Output Guardrails

```
┌─────────────────────────────────────────────────────────┐
│              Output Guardrails Pipeline                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  LLM output                                             │
│  │                                                       │
│  ▼                                                       │
│  ┌─────────────────────────────────────────────────┐   │
│  │  1. Hallucination Check                           │   │
│  │  - Compare output against retrieved context       │   │
│  │  - Flag unsupported claims                        │   │
│  │  - Score: 0 (pure hallucination) to 1 (grounded) │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  2. PII Detection in Output                       │   │
│  │  - Scan for SSN, credit cards, emails             │   │
│  │  - Redact if found                                │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  3. Content Filtering                             │   │
│  │  - Harmful content detection                      │   │
│  │  - Policy compliance check                        │   │
│  │  - Toxicity scoring                               │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  4. Output Validation                             │   │
│  │  - Schema validation (if structured output)       │   │
│  │  - Length limits                                   │   │
│  │  - Format compliance                              │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  Clean output → User                                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Observability and Monitoring

### The Observability Stack

```
┌─────────────────────────────────────────────────────────┐
│              AI Observability Stack                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Traces (OpenTelemetry)                          │   │
│  │  - Every LLM call traced end-to-end              │   │
│  │  - Latency per component                         │   │
│  │  - Token usage per call                          │   │
│  │  - Error rates                                    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Metrics (Prometheus/Grafana)                    │   │
│  │  - Requests per second                           │   │
│  │  - P50/P95/P99 latency                           │   │
│  │  - Token usage (input/output)                    │   │
│  │  - Cost per query                                 │   │
│  │  - Error rate                                     │   │
│  │  - Cache hit ratio                                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Quality Monitoring                               │   │
│  │  - LLM-as-judge scoring (sample of responses)   │   │
│  │  - User feedback (thumbs up/down)                │   │
│  │  - Task completion rate                           │   │
│  │  - Hallucination rate                             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Drift Detection                                  │   │
│  │  - Input distribution shift                      │   │
│  │  - Output quality degradation                    │   │
│  │  - Model performance drift                       │   │
│  │  - Cost drift                                    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Key Metrics Dashboard

```
┌─────────────────────────────────────────────────────────┐
│              AI System Dashboard                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Requests: 1,234/min  │  Latency P95: 320ms            │
│  Errors: 0.12%        │  Cost: $0.003/query            │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Model Usage Distribution                        │   │
│  │  Small (7B):  ████████████████████ 65%           │   │
│  │  Medium (70B): ██████████ 30%                    │   │
│  │  Reasoning:    ██ 5%                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Quality Metrics (last 24h)                      │   │
│  │  User satisfaction: 87% (↑2% from yesterday)     │   │
│  │  Hallucination rate: 3.2% (↓0.5%)                │   │
│  │  Task completion: 92% (→ same)                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Cost Breakdown                                  │   │
│  │  LLM API: $1,234/day                            │   │
│  │  Vector DB: $45/day                              │   │
│  │  Compute: $234/day                               │   │
│  │  Total: $1,513/day                               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Scaling from Prototype to 100M Users

### Stage 1: Prototype (0-1K users)

```
  Architecture:
  - Single server (FastAPI + SQLite)
  - Direct LLM API calls (no routing)
  - Basic logging

  Cost: ~$100/month
```

### Stage 2: Growth (1K-100K users)

```
  Architecture:
  - Load balancer + 2-3 API servers
  - PostgreSQL + Redis cache
  - Basic rate limiting
  - Model routing (small vs large)

  Cost: ~$5K/month
```

### Stage 3: Scale (100K-10M users)

```
  Architecture:
  - Kubernetes cluster
  - Multiple model endpoints
  - Full guardrails pipeline
  - Observability stack (OpenTelemetry)
  - A/B testing framework
  - CDN for static assets

  Cost: ~$50K/month
```

### Stage 4: Enterprise (10M-100M users)

```
  Architecture:
  - Multi-region deployment
  - Custom model hosting (vLLM clusters)
  - Advanced caching (semantic cache)
  - ML-based model routing
  - Full audit trail
  - SOC 2 compliance

  Cost: ~$500K/month
```

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

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| "Designing Machine Learning Systems" (Chip Huyen) | Book | ML in production |
| OpenAI Platform Documentation | Docs | API design, best practices |
| Anthropic Research | Blog | Safety, alignment |
| Google ML System Design | Paper | ML infrastructure |

---

## Discussion Questions

1. You're building an AI-powered customer support system. Design the full architecture from request to response. What components do you need?

2. Design a model routing system that balances cost and quality. How do you classify query complexity?

3. Your AI system serves 1M queries/day. The hallucination rate is 5%. Design a guardrails pipeline to reduce it to <1%.

4. You're scaling from 10K to 1M users. What changes in your architecture? What new components do you need?

5. Design an observability dashboard for an AI system. What metrics would you track, and how would you visualize them?

---

**Previous**: [Agent System Architecture](../15-agent-architecture/README.md)
**Next**: [Course Home](../README.md)
