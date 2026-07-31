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
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitOpenError(Exception):
    pass

@dataclass
class CircuitBreaker:
    """Circuit breaker with configurable thresholds and timeouts."""
    
    failure_threshold: int = 5       # Failures before opening
    recovery_timeout: int = 30       # Seconds before trying again
    half_open_max_calls: int = 1     # Probe calls in HALF_OPEN state
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    half_open_calls: int = 0
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through the circuit breaker."""
        self._check_state()
        
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit is OPEN. Retry after {self._time_until_half_open():.0f}s"
            )
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitOpenError("Circuit HALF_OPEN: max probe calls reached")
            self.half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _check_state(self):
        """Transition to HALF_OPEN if recovery timeout elapsed."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
    
    def _on_success(self):
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful → close circuit
            self.state = CircuitState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Probe failed → reopen circuit
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            # Too many failures → open circuit
            self.state = CircuitState.OPEN
    
    def _time_until_half_open(self) -> float:
        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)

# Usage:
breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

def call_external_api():
    return requests.get("https://api.example.com/data", timeout=5)

try:
    response = breaker.call(call_external_api)
    print(f"Success: {response.status_code}")
except CircuitOpenError as e:
    print(f"Circuit open: {e}")
    # Fallback: return cached data or default
except requests.RequestException as e:
    print(f"Request failed: {e}")
```

---

## Retry Strategies

### Exponential Backoff

```python
import time
import random
from typing import Callable, Any
from dataclasses import dataclass

@dataclass
class RetryConfig:
    max_retries: int = 5
    base_delay: float = 0.1      # 100ms
    max_delay: float = 10.0      # 10 seconds
    exponential_base: float = 2.0
    jitter: bool = True

def retry_with_backoff(
    func: Callable,
    config: RetryConfig = RetryConfig(),
    retryable_exceptions: tuple = (Exception,)
) -> Any:
    """Execute function with exponential backoff retry."""
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt == config.max_retries:
                break  # All retries exhausted
            
            # Calculate delay with exponential backoff
            delay = config.base_delay * (config.exponential_base ** attempt)
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = random.uniform(0, delay)
            
            # Cap at max delay
            delay = min(delay, config.max_delay)
            
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
            time.sleep(delay)
    
    raise last_exception  # All retries failed

# Usage:
def call_flaky_service():
    response = requests.get("https://api.example.com/data", timeout=5)
    response.raise_for_status()
    return response.json()

try:
    result = retry_with_backoff(call_flaky_service)
except Exception as e:
    print(f"All retries failed: {e}")
```

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

```python
def retry_with_jitter(
    func: Callable,
    max_retries: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 10.0
) -> Any:
    """Retry with jitter to prevent synchronized retries."""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries:
                raise
            
            # Exponential backoff + random jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jittered_delay = random.uniform(0, delay)
            
            print(f"Attempt {attempt + 1} failed. Retrying in {jittered_delay:.2f}s")
            time.sleep(jittered_delay)

# Different clients get different delays:
# Client A retry: 45ms
# Client B retry: 120ms
# Client C retry: 87ms
# → No thundering herd
```

The code above implements **full jitter** — the AWS-recommended default:

```
  cap   = min(base × 2^attempt, max_delay)
  sleep = random(0, cap)          ← the whole range, not a small nudge

  base = 100ms:
  Attempt 1: cap 100ms  → sleep 0-100ms
  Attempt 2: cap 200ms  → sleep 0-200ms
  Attempt 3: cap 400ms  → sleep 0-400ms
  Attempt 4: cap 800ms  → sleep 0-800ms
```

### Jitter Variants

Which one you pick changes how well retries de-correlate:

| Variant | Formula | Notes |
|---------|---------|-------|
| **None** | `cap` | Every client retries in lockstep — the thundering herd you were trying to avoid |
| **Full** | `random(0, cap)` | Best spread; AWS default. Some retries fire almost immediately |
| **Equal** | `cap/2 + random(0, cap/2)` | Guarantees a minimum wait, still spreads well |
| **Decorrelated** | `min(max, random(base, prev × 3))` | Lowest total completion time in AWS's simulations |

> **Watch for this mismatch:** a diagram that shows "wait 100-200ms, then
> 200-300ms" is describing *equal* jitter, but `random.uniform(0, delay)` in
> code is *full* jitter — the ranges start at 0. If your docs and code disagree
> here, the docs are usually the ones that are wrong.

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

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Timeout at every layer (seconds)
TIMEOUT_CONFIG = {
    "client": 30,      # Client gives up after 30s
    "gateway": 25,     # Gateway has 25s budget
    "service_a": 20,   # Service A has 20s budget
    "service_b": 15,   # Service B has 15s budget
    "database": 10,    # Database query has 10s budget
}

def call_with_timeout(url: str, timeout: int = 10) -> requests.Response:
    """Make HTTP call with explicit timeout."""
    return requests.get(url, timeout=(3.05, timeout))  # (connect, read)

def service_b_handler(request):
    """Service B calls database with shorter timeout."""
    try:
        result = call_with_timeout(
            f"{DATABASE_URL}/query",
            timeout=TIMEOUT_CONFIG["database"]
        )
        return result.json()
    except requests.Timeout:
        # Database is slow — fail fast, don't wait full timeout
        return {"error": "Database timeout"}

def service_a_handler(request):
    """Service A calls Service B with shorter timeout."""
    try:
        result = call_with_timeout(
            f"{SERVICE_B_URL}/process",
            timeout=TIMEOUT_CONFIG["service_b"]
        )
        return result.json()
    except requests.Timeout:
        return {"error": "Service B timeout"}

# Key principle: timeouts decrease downstream, so the innermost hop
# always fails first and the error propagates up without anyone waiting
# out their full budget.
# Client(30s) → Gateway(25s) → ServiceA(20s) → ServiceB(15s) → DB(10s)
```

```
  Client ──30s──▶ Gateway ──25s──▶ Service A ──20s──▶ Service B ──10s──▶ DB
                                                       (matches TIMEOUT_CONFIG above)

  Happy path — DB answers in 8s:
    Service B returns at ~8s, A at ~9s, Gateway at ~10s.
    Client sees ≈10s, well inside its 30s budget. ✓

  Sad path — DB hangs:
    Service B gives up at 10s (its DB timeout) and returns an error.
    Service A sees that error at ~10s — it does NOT wait out its own 20s.
    Client gets a response at ~11s instead of 30s.

  The point: because each timeout is SHORTER than its caller's, the innermost
  hop fails first and the error propagates up immediately. Nobody waits for
  the full 30s, and no service sits holding a connection it can't use.
```

**What goes wrong if you invert the order** — say the DB timeout is 30s while
the client's is 10s:

```
  Client gives up at 10s and disconnects.
  Gateway, Service A, Service B, and the DB all keep working for 20 more
  seconds on a response nobody will read — burning connections, threads,
  and DB time. Under load this is how a slow dependency turns into an
  outage: every abandoned request still costs you full capacity.
```

### Timeout Best Practices

| Principle | Description |
|-----------|-------------|
| **Set timeouts at every boundary** | Never make a call without a timeout |
| **Timeouts should decrease downstream** | Client > Gateway > Service > DB |
| **Combine with circuit breakers** | Timeouts trigger circuit breaker state changes |
| **Use deadline propagation** | Pass remaining time budget downstream |

### Deadline Propagation

```python
import time
from dataclasses import dataclass

@dataclass
class Deadline:
    """Propagate time budget through service calls."""
    start_time: float
    timeout_seconds: float
    
    @classmethod
    def from_timeout(cls, timeout: float) -> "Deadline":
        return cls(start_time=time.time(), timeout_seconds=timeout)
    
    def remaining(self) -> float:
        elapsed = time.time() - self.start_time
        return max(0, self.timeout_seconds - elapsed)
    
    def is_expired(self) -> bool:
        return self.remaining() <= 0
    
    def child_deadline(self, fraction: float = 0.8) -> "Deadline":
        """Create child deadline with fraction of remaining time."""
        remaining = self.remaining() * fraction
        return Deadline(start_time=time.time(), timeout_seconds=remaining)

# Usage in service chain:
def api_gateway_handler(request):
    deadline = Deadline.from_timeout(30.0)  # 30s total budget
    
    # Pass 80% of remaining time to Service A
    return call_service_a(request, deadline=deadline)

def call_service_a(request, deadline: Deadline):
    child_deadline = deadline.child_deadline(fraction=0.8)  # 24s
    
    # Pass 80% to Service B
    return call_service_b(request, deadline=child_deadline)

def call_service_b(request, deadline: Deadline):
    if deadline.is_expired():
        raise TimeoutError("Deadline expired before call")
    
    # Use remaining time for database query
    db_timeout = deadline.remaining() * 0.7  # 70% of remaining
    return query_database(request, timeout=db_timeout)
```

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

### Error Budget Calculator

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ErrorBudget:
    """Track and manage error budgets."""
    
    slo_target: float  # e.g., 0.999 for 99.9%
    window_days: int = 30
    
    @property
    def error_rate(self) -> float:
        return 1.0 - self.slo_target
    
    @property
    def total_minutes(self) -> float:
        return self.window_days * 24 * 60
    
    @property
    def budget_minutes(self) -> float:
        return self.error_rate * self.total_minutes
    
    def remaining_minutes(self, incidents_minutes: list) -> float:
        """Calculate remaining budget after incidents."""
        return self.budget_minutes - sum(incidents_minutes)
    
    def remaining_pct(self, incidents_minutes: list) -> float:
        """Calculate remaining budget percentage."""
        remaining = self.remaining_minutes(incidents_minutes)
        return max(0, remaining / self.budget_minutes * 100)
    
    def status(self, incidents_minutes: list) -> str:
        """Get deployment status based on remaining budget."""
        pct = self.remaining_pct(incidents_minutes)
        if pct > 50:
            return "SHIP_FREELY"
        elif pct > 20:
            return "EXTRA_REVIEW"
        elif pct > 0:
            return "RELIABILITY_FOCUS"
        else:
            return "FREEZE_DEPLOYS"

# Usage:
budget = ErrorBudget(slo_target=0.999)  # 99.9% SLO
print(f"Monthly budget: {budget.budget_minutes:.1f} minutes")

# Track incidents
incidents = [10, 15]  # Two incidents: 10 min + 15 min
remaining = budget.remaining_minutes(incidents)
status = budget.status(incidents)

print(f"Remaining: {remaining:.1f} minutes ({budget.remaining_pct(incidents):.0f}%)")
print(f"Status: {status}")
# Output:
# Monthly budget: 43.2 minutes
# Remaining: 18.2 minutes (42%)
# Status: EXTRA_REVIEW
```

Check the arithmetic yourself — this is the kind of thing to get right before
you wire it to a deploy gate:

```
budget  = (1 - 0.999) × 30 days × 24 h × 60 min = 43.2 min
spent   = 10 + 15                               = 25.0 min
left    = 43.2 - 25.0                           = 18.2 min
percent = 18.2 / 43.2                           = 42%

42% is in the 20-50% band → EXTRA_REVIEW (not RELIABILITY_FOCUS,
which starts below 20%).
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

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Retries without jitter** | Every client retries on the same schedule, so the herd hits again in lockstep | Full jitter: `sleep = random(0, min(base × 2^n, cap))` |
| **Retries at every layer** | 3 retries at 4 layers is 81 requests to a service already failing | Retry at one layer — usually the outermost that can act on failure |
| **Retrying without a circuit breaker** | Retries add load exactly when the dependency needs less | Breaker opens after N failures and sheds load until it recovers |
| **Timeouts that increase downstream** | The caller gives up while everything below keeps burning capacity on a response nobody reads | Timeouts strictly decrease downstream; propagate a deadline |
| **No timeout at all** | One hung dependency exhausts the connection pool and takes the service with it | Every network call gets an explicit timeout — no exceptions |
| **SLOs at 100%** | It leaves no error budget, so all change becomes unshippable | Pick a target users actually notice; spend the difference on velocity |
| **SLIs measured server-side only** | You miss DNS, TLS, and network failures — the ones users see | Measure client-side or at the edge |
| **Untested backups** | A backup you've never restored is a hypothesis, not a recovery plan | Restore drills on a schedule; measure against your RTO |
| **Chaos experiments without a hypothesis** | Breaking things at random produces incidents, not learning | State the steady-state expectation, inject one fault, bound the blast radius |
| **Health checks that fail on dependency outage** | All instances go unhealthy at once, converting partial failure into total | Separate liveness from readiness; degrade instead of disappearing |

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
