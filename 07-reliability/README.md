# Module 07: Reliability Engineering

> **Build systems that survive failures.** In distributed systems, failure is not an edge case — it's the default. Reliability engineering is about designing for failure, not preventing it.

## Learning Objectives

- Understand failure modes and their frequency
- Implement circuit breakers, retries, and timeouts
- Design disaster recovery strategies (RPO, RTO)
- Define and measure SLOs, SLAs, and error budgets
- Apply chaos engineering principles

---

## Failure Is the Default

In any distributed system, things will fail. The question is not "if" but "when" and "how gracefully."

### Failure Modes

| Failure | Frequency | Impact |
|---------|-----------|--------|
| **Network partition** | Daily | Services can't communicate |
| **Server crash** | Weekly | One instance goes down |
| **Disk failure** | Monthly | Data loss risk |
| **DNS failure** | Rare | Service unreachable |
| **Data center outage** | Rare | Major disruption |
| **Cascading failure** | Common under load | Whole system collapse |

### The Bathtub Curve

```
  Failure Rate
  │
  │  ╲                              ╱
  │   ╲                            ╱
  │    ╲                          ╱
  │     ╲________________________╱
  │
  └──────────────────────────────────▶ Time
    Early       Useful Life       Wear-out
    failures    (constant rate)   (increasing)
```

Most systems operate in the "useful life" phase with a relatively constant failure rate. The goal is to survive individual failures without cascading.

---

## Circuit Breaker Pattern

Prevent cascading failures by stopping calls to a failing service.

```
  ┌─────────────────────────────────────────┐
  │           Circuit Breaker States          │
  │                                           │
  │  ┌──────────┐    failure    ┌──────────┐ │
  │  │  CLOSED  │──────────────▶│   OPEN   │ │
  │  │ (normal) │               │(rejected)│ │
  │  └────▲─────┘               └────┬─────┘ │
  │       │                          │        │
  │       │    success               │        │
  │       │◀─────────────────────────│        │
  │       │                  timeout │        │
  │       │                          ▼        │
  │       │                     ┌──────────┐  │
  │       └─────────────────────│HALF-OPEN │  │
  │         success             │(testing) │  │
  │                             └──────────┘  │
  └─────────────────────────────────────────┘

  CLOSED: Requests flow normally. Counter tracks failures.
  OPEN: All requests fail fast (no call to downstream).
  HALF-OPEN: Allow one probe request. Success → CLOSED, Failure → OPEN.
```

### Implementation

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"
        self.last_failure_time = None
    
    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitOpenError("Circuit is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

---

## Retry Strategies

### Exponential Backoff

```
  Attempt 1: Wait 100ms
  Attempt 2: Wait 200ms
  Attempt 3: Wait 400ms
  Attempt 4: Wait 800ms
  Attempt 5: Wait 1600ms
  Attempt 6: Give up

  ✓ Prevents hammering a failing service
  ✓ Gives time for recovery
  ✗ Total wait time grows exponentially
```

### Exponential Backoff with Jitter

Add randomness to prevent synchronized retries (thundering herd).

```
  Wait time = min(base × 2^attempt + random(0, 100ms), max_wait)

  Attempt 1: Wait 100-200ms  (random)
  Attempt 2: Wait 200-300ms
  Attempt 3: Wait 400-500ms
  Attempt 4: Wait 800-900ms
```

### Retry Decision Matrix

| Error Type | Retry? | Strategy |
|------------|--------|----------|
| **5xx (server error)** | Yes | Exponential backoff + jitter |
| **429 (rate limit)** | Yes | Respect Retry-After header |
| **408 (timeout)** | Maybe | Once, with shorter timeout |
| **400 (bad request)** | No | Client error, won't fix on retry |
| **401/403 (auth)** | No | Re-authenticate, don't retry |
| **Connection refused** | Yes | Exponential backoff |

---

## Timeout Design

Timeouts prevent indefinite waiting. But what timeout should you set?

### Cascading Timeout Problem

```
  Client ──30s timeout──▶ API Gateway ──25s timeout──▶ Service A
                                                       │
                                                  ──20s timeout──▶ Service B
                                                                      │
                                                                 ──15s timeout──▶ Database

  If DB takes 14s: Service B waits 14s + some processing
  Total: Client sees 14s + 2s + 1s + processing ≈ 18s (under 30s) ✓

  If DB takes 16s: Service B times out at 15s
  Service A times out at 20s (after waiting for Service B)
  Client times out at 30s (after waiting for Service A)

  Total: 30s timeout, but 3 services wasted resources
```

### Timeout Best Practices

| Principle | Description |
|-----------|-------------|
| **Set timeouts at every boundary** | Never make a call without a timeout |
| **Timeouts should decrease downstream** | Client > Gateway > Service > DB |
| **Combine with circuit breakers** | Timeouts trigger circuit breaker state changes |
| **Use deadline propagation** | Pass remaining time budget downstream |

### Deadline Propagation

```
  Client sets deadline: T+30s
  │
  ▼
  Gateway receives with 29.5s remaining. Sets own timeout: 25s.
  │
  ▼
  Service A receives with 24s remaining. Sets own timeout: 20s.
  │
  ▼
  Service B receives with 19s remaining. Sets own timeout: 15s.
  │
  ▼
  Database receives with 14s remaining.

  If DB takes 16s, Service B times out at 15s, NOT at 30s.
  Resources are freed early.
```

---

## Disaster Recovery

### RPO and RTO

```
  ┌──────────────────────────────────────────────┐
  │                                               │
  │  RPO (Recovery Point Objective)               │
  │  = How much data can you afford to lose?      │
  │                                               │
  │  RTO (Recovery Time Objective)                │
  │  = How quickly must you recover?              │
  │                                               │
  │  ─────────────────────────────────────────── │
  │  Timeline:                                    │
  │                                               │
  │  Last Backup    Disaster    Recovery         │
  │      │            │            │              │
  │      ▼            ▼            ▼              │
  │  ────●────────────●────────────●────▶         │
  │      │←── RPO ──→│←── RTO ──→│              │
  │      │  (data loss)│  (downtime)│              │
  └──────────────────────────────────────────────┘
```

| RPO | RTO | Strategy | Cost |
|-----|-----|----------|------|
| 24 hours | 24 hours | Daily backup, restore from backup | Low |
| 1 hour | 1 hour | Hourly backup, standby server | Medium |
| 0 (no data loss) | Minutes | Synchronous replication, hot standby | High |
| 0 | Seconds | Multi-active, automatic failover | Very high |

### Multi-Region Strategies

```
  Active-Passive:                 Active-Active:
  ┌──────────┐                   ┌──────────┐
  │  US East │ ◄── Primary       │  US East │ ◄── Traffic
  │ (Active) │                   │ (Active) │
  └────┬─────┘                   └────┬─────┘
       │ replication                   │ replication
       ▼                               ▼
  ┌──────────┐                   ┌──────────┐
  │  EU West │ ◄── Standby       │  EU West │ ◄── Traffic
  │(Passive) │   (cold/warm)     │ (Active) │
  └──────────┘                   └──────────┘

  ✓ Simple failover             ✓ No failover needed
  ✗ Standby is idle             ✓ Better latency globally
  ✗ Failover takes minutes      ✗ Conflict resolution
```

---

## SLOs, SLAs, and Error Budgets

### Definitions

| Term | Definition | Example |
|------|-----------|---------|
| **SLI** (Service Level Indicator) | What you measure | 99.9% of requests < 200ms |
| **SLO** (Service Level Objective) | What you promise internally | 99.9% availability target |
| **SLA** (Service Level Agreement) | What you promise customers | 99.9% uptime, or credit |
| **Error Budget** | How much failure is acceptable | 0.1% = 43 minutes/month |

### Error Budget Calculation

```
  SLO: 99.9% availability
  Error budget: 0.1% = 0.001

  Per month: 0.001 × 30 days × 24 hours × 60 minutes = 43.2 minutes

  Usage:
  - Month starts: budget = 43.2 minutes
  - Incident costs 10 minutes: budget = 33.2 minutes
  - Another incident costs 15 minutes: budget = 18.2 minutes
  - Budget exhausted: freeze deployments until next month
```

### Error Budget Policy

```
  Budget remaining > 50%:  Ship freely, experiment
  Budget remaining 20-50%: Extra testing, code review
  Budget remaining < 20%:  No risky deploys, focus on reliability
  Budget exhausted:        FREEZE all feature deployments
```

---

## Chaos Engineering

Deliberately inject failures to find weaknesses before they cause outages.

### Chaos Engineering Principles

```
  1. Steady state hypothesis
     "The system works normally under current load"

  2. Introduce real-world events
     Kill a server, inject network latency, fill a disk

  3. Observe the difference
     Did the system meet its SLO? Did users notice?

  4. Minimize blast radius
     Start small (one server), then expand
```

### Chaos Engineering Practice

```
  ┌─────────────────────────────────────────────────┐
  │           Chaos Engineering Process               │
  │                                                   │
  │  ┌──────────┐                                    │
  │  │Define    │ "The system should handle           │
  │  │hypothesis│  server failure without user impact"│
  │  └────┬─────┘                                    │
  │       │                                           │
  │  ┌────▼─────┐                                    │
  │  │Plan      │ "Kill one server in US-East        │
  │  │experiment│  during business hours"             │
  │  └────┬─────┘                                    │
  │       │                                           │
  │  ┌────▼─────┐                                    │
  │  │Run       │ Execute the failure injection       │
  │  │experiment│                                    │
  │  └────┬─────┘                                    │
  │       │                                           │
  │  ┌────▼─────┐                                    │
  │  │Analyze   │ Compare metrics before/during/      │
  │  │results   │ after. Did SLO hold?                │
  │  └────┬─────┘                                    │
  │       │                                           │
  │  ┌────▼─────┐                                    │
  │  │Fix       │ Address any weaknesses found        │
  │  │weaknesses│                                    │
  │  └──────────┘                                    │
  └─────────────────────────────────────────────────┘
```

### Chaos Tools

| Tool | Description |
|------|-------------|
| **Chaos Monkey** (Netflix) | Randomly kills instances in production |
| **Gremlin** | Controlled failure injection platform |
| **Litmus** | Kubernetes-native chaos engineering |
| **ToxiProxy** | Network fault injection proxy |

---

## Case Study: Google's Reliability Engineering

Google's SRE practices are the gold standard for reliability engineering.

### Key Practices

1. **SLOs for everything**: Every service has an SLO. No SLO = no deployment. This forces teams to think about reliability upfront.

2. **Error budgets drive deployment speed**: If you have budget, ship fast. If you don't, stop and fix reliability first. This creates natural tension between velocity and reliability.

3. **Multi-region by default**: Every production service runs in at least 2 regions. Traffic is automatically routed away from unhealthy regions.

4. **Binary Authorization**: Every deployment is authorized by a binary authorization service. Only tested, reviewed, and approved code reaches production.

5. **Automated rollbacks**: If error rate exceeds SLO, the system automatically rolls back. No human intervention needed.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| "Site Reliability Engineering" (Google) | Book | SLOs, error budgets, incident response |
| "Release It!" (Michael Nygard) | Book | Circuit breakers, timeouts, stability patterns |
| DDIA Ch. 8 | Book | Replication, consistency |
| Google SRE Workbook | Book | Practical SRE implementation |
| Chaos Engineering (Netflix) | Blog | Chaos Monkey, fault injection |

---

## Practice Exercise

**20-minute design**: Design reliability for a payment system:

- 99.99% availability required
- Payments must not be lost
- Must survive data center failure

**Key decisions**:
1. What SLOs would you set?
2. How do you handle payment service failures?
3. What's your disaster recovery strategy?
4. How do you prevent cascading failures?

---

## Discussion Questions

1. You're designing an e-commerce checkout. What happens if the payment service is down? How do you handle this gracefully?

2. Explain the difference between a timeout and a circuit breaker. When would you use each?

3. You're setting SLOs for a food delivery app. What SLIs would you measure? What SLO targets would you set?

4. Design a disaster recovery strategy for a banking system with RPO=0 and RTO<5 minutes. What infrastructure do you need?

5. Your team has exhausted its error budget. What do you do? How do you communicate this to stakeholders?

---

**Previous**: [Microservices Architecture](../06-microservices/README.md)
**Next**: [Distributed Systems Deep Dive](../08-distributed-systems/README.md)
