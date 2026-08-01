# Module 04: Load Balancing and Networking

> **Distribute traffic intelligently and keep systems healthy.** A load balancer is the front door of your system — it determines which server handles each request, and its design affects latency, availability, and fault tolerance.

## Learning Objectives

- Understand load balancing algorithms and when to use each
- Compare L4 vs L7 load balancing
- Design rate limiting with appropriate algorithms
- Implement health checks and failover
- Understand API gateway patterns

---

## Why Load Balancing Matters

A single server can handle ~1,000-10,000 concurrent connections. Beyond that, you need multiple servers and a way to distribute traffic.

```
  Without load balancing:           With load balancing:

  ┌──────────┐                     ┌──────────┐
  │  Client  │                     │  Client  │
  └─────┬────┘                     └─────┬────┘
        │                                │
  ┌─────▼───────┐                     ┌─────▼─────┐
  │  Server     │ ◄── SPOF           │    LB     │ ◄── Distributes
  │ (overloaded)│                  └──┬───┬───┬┘     traffic
  └─────────────┘                     ┌──▼─┐┌▼──┐┌▼──┐
                                   │ S1 ││ S2 ││ S3 │
                                   └────┘└────┘└────┘
```

### Benefits

| Benefit | Description |
|---------|-------------|
| **Scalability** | Add servers to handle more traffic |
| **Availability** | If one server dies, others continue |
| **Flexibility** | Rolling deployments, A/B testing |
| **Performance** | Route to the least-loaded server |

---

## Load Balancing Algorithms

### Round Robin

Each request goes to the next server in rotation.

```
  Requests: R1, R2, R3, R4, R5, R6
  Servers:  [S1, S2, S3]

  R1 → S1
  R2 → S2
  R3 → S3
  R4 → S1
  R5 → S2
  R6 → S3

  ✓ Simple, no state needed
  ✓ Even distribution (if servers are equal)
  ✗ Ignores server load and response time
```

### Weighted Round Robin

Servers get proportional traffic based on capacity.

```
  S1 (weight 5) gets 5/8 of traffic
  S2 (weight 2) gets 2/8 of traffic
  S3 (weight 1) gets 1/8 of traffic

  ✓ Accounts for heterogeneous servers
  ✗ Weights must be manually configured
```

### Least Connections

Route to the server with fewest active connections.

```
  S1: 50 active connections
  S2: 30 active connections  ◄── Next request goes here
  S3: 45 active connections

  ✓ Adapts to real-time load
  ✓ Handles slow requests well
  ✗ Requires tracking connection counts
```

### IP Hash

Hash the client IP to determine which server handles all their requests.

```
  hash(client_ip) % num_servers = server_index

  Client 1.2.3.4 → hash → server 0  (always)
  Client 5.6.7.8 → hash → server 2  (always)

  ✓ Sticky sessions (same client → same server)
  ✓ No session replication needed
  ✗ Uneven distribution (popular IPs)
  ✗ Server failure loses all sessions
```

### Consistent Hashing

Minimize reshuffling when servers are added or removed.

```
  Hash ring with servers at positions:

       ┌─────── S1 ───────┐
      /                     \
    S4                       S2
      \                     /
       └─────── S3 ───────┘

  Request → hash(key) → clockwise to nearest server

  Adding S5 between S1 and S2:
  - Only requests between S1 and S5 need to move
  - All other requests stay with their server

  ✓ Minimal disruption on scale events
  ✓ Even distribution with virtual nodes
  ✓ Used by: DynamoDB, Cassandra, CDN caches
```

---

## L4 vs L7 Load Balancing

### L4 (Transport Layer)

Operates at TCP/UDP level. Routes based on IP + port.

```
  ┌────────────────────────────────────┐
  │         L4 Load Balancer           │
  │                                    │
  │  Client IP:Port ──▶ Server IP:Port │
  │  (no inspection of content)        │
  └────────────────────────────────────┘

  ✓ Very fast (no packet inspection)
  ✓ Low latency (~microseconds)
  ✓ Handles millions of connections
  ✗ Can't route based on URL/header
  ✗ No TLS termination (unless configured)
```

### L7 (Application Layer)

Operates at HTTP level. Routes based on URL, headers, cookies.

```
  ┌────────────────────────────────────────┐
  │         L7 Load Balancer               │
  │                                        │
  │  /api/users    → Server Pool A         │
  │  /api/orders   → Server Pool B         │
  │  /static/*     → CDN/Cache             │
  │  Host: admin.* → Admin Servers         │
  └────────────────────────────────────────┘

  ✓ Content-based routing
  ✓ TLS termination (SSL offloading)
  ✓ HTTP header inspection
  ✓ WebSocket support
  ✗ Slower than L4 (packet inspection)
  ✗ More complex configuration
```

### Comparison

| Factor | L4 | L7 |
|--------|----|----|
| **Speed** | Faster (no content inspection) | Slower (inspects HTTP) |
| **Routing** | IP + port only | URL, headers, cookies |
| **TLS** | Passthrough | Terminate & re-encrypt |
| **Health checks** | TCP connect | HTTP 200 check |
| **Use case** | Internal service communication | Public-facing web apps |

---

## DNS-Based Load Balancing

### GeoDNS

Resolve domain to the nearest data center.

```
  User in New York:
    api.example.com → 198.51.100.10 (US East)

  User in London:
    api.example.com → 203.0.113.10 (EU West)

  User in Tokyo:
    api.example.com → 192.0.2.10 (Asia Pacific)
```

### Weighted DNS

Return multiple IPs with weighted probabilities.

```
  api.example.com:
    60% → 10.0.0.1 (primary region)
    30% → 10.0.1.1 (secondary region)
    10% → 10.0.2.1 (disaster recovery)
```

### DNS Limitations

| Limitation | Impact |
|------------|--------|
| TTL propagation | Changes take minutes to hours |
| No health checks | DNS keeps returning dead IPs |
| Client caching | Clients may ignore TTL changes |

---

## Rate Limiting

Protect your system from abuse and overload.

### Token Bucket

```python
import time

class TokenBucket:
    """Token bucket rate limiter. Allows controlled bursts."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket (burst size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
    
    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def allow(self) -> bool:
        self._refill()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

# Usage: 100 requests/minute, burst of 10
limiter = TokenBucket(capacity=10, refill_rate=100/60)

# In request handler:
if limiter.allow():
    process_request()
else:
    return 429, "Too Many Requests"
```

```
  Bucket capacity: 10 tokens
  Refill rate: 5 tokens/second

  Time 0:  [■■■■■■■■■■] 10 tokens
  Request: [■■■■■■■■■ ] 9 tokens (1 consumed)
  Time 1:  [■■■■■■■■■■] 10 tokens (refilled)
  Request: [■■■■■■■■■ ] 9 tokens
  Burst:   [■■■■■     ] 5 tokens (5 consumed at once)

  ✓ Allows bursts (up to bucket capacity)
  ✓ Smooth rate over time
  ✓ Simple to implement
```

### Leaky Bucket

```python
import time
from collections import deque

class LeakyBucket:
    """Leaky bucket rate limiter. Smooths traffic to constant rate."""
    
    def __init__(self, capacity: int, leak_rate: float):
        """
        Args:
            capacity: Maximum queue size
            leak_rate: Requests processed per second
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.queue = deque()
        self.last_leak = time.time()
    
    def _leak(self):
        now = time.time()
        elapsed = now - self.last_leak
        leaked = int(elapsed * self.leak_rate)
        for _ in range(min(leaked, len(self.queue))):
            self.queue.popleft()
        if leaked:
            self.last_leak = now
    
    def allow(self) -> bool:
        self._leak()
        if len(self.queue) < self.capacity:
            self.queue.append(time.time())
            return True
        return False  # Queue full, drop request

# Usage: Queue up to 100, process 10/second
limiter = LeakyBucket(capacity=100, leak_rate=10)
```

```
  Queue capacity: 10
  Process rate: 5/second

  Requests:  R1 R2 R3 R4 R5 R6 R7 R8 R9 R10 R11
  Queue:     [R1 R2 R3 R4 R5 R6 R7 R8 R9 R10] ← R11 REJECTED
  Output:    R1 R2 R3 R4 R5 (one per 200ms)

  ✓ Smooth, constant output rate
  ✓ Predictable latency
  ✗ Bursts are queued (added latency)
  ✗ Queue overflow = request drop
```

### Fixed Window

```python
import time
from collections import defaultdict

class FixedWindow:
    """Fixed window rate limiter. Simple but has boundary burst problem."""
    
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.counters = defaultdict(int)
    
    def _get_window_key(self) -> str:
        window_start = int(time.time()) // self.window_seconds
        return str(window_start)
    
    def allow(self, client_id: str) -> bool:
        key = f"{client_id}:{self._get_window_key()}"
        self.counters[key] += 1
        return self.counters[key] <= self.limit

# Usage: 100 requests per minute
limiter = FixedWindow(limit=100, window_seconds=60)
```

```
  Window: 1 minute
  Limit: 100 requests

  12:00:00 - 12:01:00: [████████░░] 80/100  ✓
  12:01:00 - 12:02:00: [██████████] 100/100 ✓ (at limit)
  12:01:45: Request → REJECTED (over limit)

  ✓ Simple to implement
  ✗ Boundary problem: 100 requests at 12:00:59 + 100 at 12:01:01 = 200 in 2 seconds
```

### Sliding Window

```python
import time
from collections import defaultdict

class SlidingWindow:
    """Sliding window rate limiter. No boundary burst problem."""
    
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self.prev_counts = defaultdict(int)
        self.curr_counts = defaultdict(int)
        self.window_start = int(time.time())
    
    def _rotate_if_needed(self):
        now = int(time.time())
        if now >= self.window_start + self.window_seconds:
            self.prev_counts = self.curr_counts
            self.curr_counts = defaultdict(int)
            self.window_start = now
    
    def allow(self, client_id: str) -> bool:
        self._rotate_if_needed()
        now = time.time()
        elapsed = now - self.window_start
        
        # Weighted count: prev window's contribution decays over time
        prev_weight = 1 - (elapsed / self.window_seconds)
        count = self.prev_counts[client_id] * prev_weight + self.curr_counts[client_id]
        
        if count < self.limit:
            self.curr_counts[client_id] += 1
            return True
        return False

# Usage: 100 requests per minute
limiter = SlidingWindow(limit=100, window_seconds=60)
```

```
  Sliding window: 1 minute
  Limit: 100 requests

  Current window: 80 requests
  Previous window: 60 requests
  Elapsed in current: 30 seconds

  Weighted count = 80 + 60 × (30/60) = 80 + 30 = 110

  110 > 100 → REJECTED

  ✓ No boundary problem
  ✓ More accurate than fixed window
  ✗ More complex to implement
```

### Algorithm Comparison

| Algorithm | Burst Handling | Memory | Accuracy | Use Case |
|-----------|---------------|--------|----------|----------|
| Token Bucket | Allows controlled bursts | O(1) | High | API rate limiting |
| Leaky Bucket | Smooths bursts | O(n) queue | High | Traffic shaping |
| Fixed Window | Boundary burst risk | O(1) | Low | Simple limits |
| Sliding Window | No boundary issues | O(n) | High | Precise limiting |

### Distributed Rate Limiting

```python
import time

import redis

class DistributedRateLimiter:
    """Rate limiter using Redis for distributed coordination."""
    
    def __init__(self, redis_client: redis.Redis, limit: int, window: int = 60):
        self.r = redis_client
        self.limit = limit
        self.window = window
    
    def allow(self, client_id: str) -> bool:
        # Bucket the key by window so each window gets a fresh counter and
        # its own independent expiry.
        window_id = int(time.time()) // self.window
        key = f"rate:{client_id}:{window_id}"

        pipe = self.r.pipeline()
        pipe.incr(key)
        # NX = only set a TTL if the key has none. Without NX, every request
        # pushes the expiry forward, the window never closes, and a client
        # that keeps retrying stays blocked indefinitely.
        pipe.expire(key, self.window, nx=True)
        count = pipe.execute()[0]

        return count <= self.limit

    def allow_with_tier(self, client_id: str, tier: str) -> bool:
        """Multi-tier rate limiting (free/pro/enterprise)."""
        limits = {"free": 100, "pro": 1000, "enterprise": 10000}
        limit = limits.get(tier, 100)

        window_id = int(time.time()) // self.window
        key = f"rate:{client_id}:{tier}:{window_id}"

        pipe = self.r.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window, nx=True)
        count = pipe.execute()[0]

        return count <= limit

# Usage
r = redis.Redis(host='redis-cluster', port=6379)
limiter = DistributedRateLimiter(r, limit=100, window=60)

# In request handler:
if limiter.allow("user:123"):
    process_request()
else:
    return 429, "Rate limit exceeded"
```

**Two traps in distributed counters:**

| Trap | Symptom | Fix |
|------|---------|-----|
| `EXPIRE` on every request | Window never closes; an actively-retrying client is locked out permanently | `EXPIRE ... NX`, or set the TTL only when `INCR` returns 1 |
| `INCR` then `EXPIRE` as separate round trips | A crash between the two leaves a key with no TTL — a permanent ban | Pipeline them, or use a Lua script for true atomicity |

This is a **fixed window**, so it inherits the boundary-burst problem: a client
can send `limit` requests at the end of one window and `limit` more at the start
of the next. For a sliding window, store timestamps in a sorted set
(`ZADD` + `ZREMRANGEBYSCORE` + `ZCARD`) inside one Lua script.

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  LB 1    │     │  LB 2    │     │  LB 3    │
  └────┬─────┘     └────┬─────┘     └────┬─────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                 ┌──────▼───────┐
                 │ Redis Cluster│ ◄── Centralized counters
                 │ (atomic incr)│
                 └──────────────┘

  Problem: Each LB has partial view → need centralized counter
  Solution: Redis INCR with TTL (atomic, fast)

  GET /api/resource → INCR rate:user:123 → EXPIRE rate:user:123 60
  If INCR > 100 → REJECT
```

---

## Health Checks

### Active Health Checks

```python
import requests
import time
from dataclasses import dataclass, field
from enum import Enum

class ServerStatus(Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class HealthChecker:
    """Active health checker with configurable thresholds."""
    
    check_interval: int = 10      # seconds between checks
    failure_threshold: int = 3    # failures before marking DOWN
    success_threshold: int = 3    # successes before marking UP
    
    # Track state per server
    _failure_counts: dict = field(default_factory=dict)
    _success_counts: dict = field(default_factory=dict)
    _status: dict = field(default_factory=dict)
    
    def check(self, server_url: str) -> ServerStatus:
        """Probe server and update status."""
        try:
            resp = requests.get(f"{server_url}/health", timeout=5)
            if resp.status_code == 200:
                self._on_success(server_url)
            else:
                self._on_failure(server_url)
        except requests.RequestException:
            self._on_failure(server_url)
        
        return self._status.get(server_url, ServerStatus.UNKNOWN)
    
    def _on_success(self, server_url: str):
        self._failure_counts[server_url] = 0
        self._success_counts[server_url] = self._success_counts.get(server_url, 0) + 1
        if self._success_counts[server_url] >= self.success_threshold:
            self._status[server_url] = ServerStatus.UP
    
    def _on_failure(self, server_url: str):
        self._success_counts[server_url] = 0
        self._failure_counts[server_url] = self._failure_counts.get(server_url, 0) + 1
        if self._failure_counts[server_url] >= self.failure_threshold:
            self._status[server_url] = ServerStatus.DOWN

# Usage
checker = HealthChecker(failure_threshold=3, success_threshold=3)

# In background thread:
while True:
    for server in ["http://s1:8080", "http://s2:8080", "http://s3:8080"]:
        status = checker.check(server)
        if status == ServerStatus.DOWN:
            remove_from_load_balancer(server)
    time.sleep(checker.check_interval)
```

```
  Every 10 seconds:
  LB → Server 1: GET /health → 200 OK ✓
  LB → Server 2: GET /health → 503 Error ✗ → REMOVE from pool
  LB → Server 3: GET /health → timeout ✗ → REMOVE from pool

  After 3 consecutive failures → mark as DOWN
  After 3 consecutive successes → mark as UP
```

### Passive Health Checks

```python
from collections import defaultdict
import time

class PassiveHealthChecker:
    """Detect failures from actual request traffic (no extra probes)."""
    
    def __init__(self, failure_threshold: int = 3, window: int = 60):
        self.failure_threshold = failure_threshold
        self.window = window
        self.failures = defaultdict(list)  # server -> [timestamps]
    
    def record_failure(self, server: str):
        now = time.time()
        self.failures[server].append(now)
        # Clean old failures outside window
        self.failures[server] = [t for t in self.failures[server] if now - t < self.window]
    
    def is_healthy(self, server: str) -> bool:
        return len(self.failures[server]) < self.failure_threshold

# Usage in request handler:
checker = PassiveHealthChecker(failure_threshold=3, window=60)

def handle_request(server):
    try:
        response = proxy_to_server(server)
        if response.status_code >= 500:
            checker.record_failure(server)
        return response
    except Timeout:
        checker.record_failure(server)
        return fallback_to_next_server()
```

```
  If server returns 5xx or times out 3 times in 1 minute → mark as DOWN
  No extra probes needed
```

### Readiness vs Liveness Probes

| Probe | Purpose | Failure Action |
|-------|---------|----------------|
| **Readiness** | Can the server handle traffic? | Remove from load balancer pool |
| **Liveness** | Is the server alive? | Restart the server (Kubernetes) |

---

## API Gateway Pattern

An API gateway is a single entry point that handles cross-cutting concerns.

```
  ┌─────────────────────────────────────────────────────┐
  │                   API Gateway                       │
  │                                                     │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐       │
  │  │  Auth    │  │  Rate    │  │   Routing    │       │
  │  │ (JWT,    │  │  Limit   │  │  /api/v1/*   │       │
  │  │  OAuth)  │  │          │  │  /api/v2/*   │       │
  │  └──────────┘  └──────────┘  └──────────────┘       │
  │                                                     │
  │  ┌───────────┐  ┌───────────┐  ┌──────────────┐     │
  │  │  Logging  │  │  TLS      │  │  Request     │     │
  │  │  & Tracing│  │  Terminate│  │  Transform   │     │
  │  └───────────┘  └───────────┘  └──────────────┘     │
  └─────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
     ┌────▼────┐    ┌─────▼────┐    ┌────▼────┐
     │ User    │    │ Order    │    │ Payment │
     │ Service │    │ Service  │    │ Service │
     └─────────┘    └──────────┘    └─────────┘
```

### API Gateway Responsibilities

| Concern | Description |
|---------|-------------|
| **Authentication** | Verify JWT tokens, OAuth flows |
| **Rate Limiting** | Per-user, per-IP, per-API limits |
| **Routing** | Direct requests to correct microservice |
| **TLS Termination** | Handle SSL/TLS encryption |
| **Request Transformation** | Protocol conversion, field mapping |
| **Response Caching** | Cache frequent responses |
| **Logging & Tracing** | Centralized observability |
| **API Versioning** | Route v1/v2 requests |

---

## Service Mesh

A service mesh adds transparent networking to microservices.

```
  Without service mesh:            With service mesh:

  ┌─────────┐                     ┌─────────┐
  │ Service │◄── Manual retry,    │ Service │
  │    A    │    timeout, mTLS    │    A    │
  └─────────┘                     └────┬────┘
                                       │ sidecar proxy
  ┌─────────┐                     ┌────▼────┐
  │ Service │                     │ Envoy   │
  │    B    │                     │ proxy   │
  └─────────┘                     └────┬────┘
                                       │
  Applications handle               Proxy handles
  networking logic                   retries, mTLS,
                                     load balancing
```

**Popular service meshes**: Istio, Linkerd, Consul Connect

---

## Case Study: Cloudflare at Scale

Cloudflare handles 40M+ HTTP requests per second across 310+ cities.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  Cloudflare Architecture                 │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Anycast Network (IP routing)                    │    │
│  │  - Same IP address in 310+ cities                │    │
│  │  - BGP routes to nearest data center             │    │
│  │  - Automatic failover if DC goes down            │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Load Balancing Layer                            │    │
│  │  - Maglev (consistent hashing) for internal LB   │    │
│  │  - L7 routing (URL, header, cookie-based)        │    │
│  │  - Rate limiting (token bucket, per-IP)          │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Edge Compute (Workers)                          │    │
│  │  - Run customer code at the edge                 │    │
│  │  - DDoS mitigation                               │    │
│  │  - WAF (Web Application Firewall)                │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌───────────────────────────────────────────────────┐   │
│  │  Origin Shield                                    │   │
│  │  - Caches responses before reaching origin        │   │
│  │  - Reduces origin load by 60-80%                  │   │
│  └───────────────────────────────────────────────────┘   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Anycast for global load balancing**: Same IP address announced from 310+ locations. BGP routes users to the nearest data center. No DNS-based routing needed.

2. **Consistent hashing for internal load balancing**: Maglev (Google's consistent hashing) ensures minimal reshuffling when servers are added/removed. Handles millions of connections per second.

3. **Edge-first architecture**: 95%+ of requests are served from the edge. Only cache misses reach origin servers. This reduces latency and origin load.

4. **DDoS mitigation at the network layer**: Volumetric attacks are absorbed by the Anycast network itself (each data center absorbs its share). Application-layer attacks are mitigated by WAF rules.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Designing Data-Intensive Applications (Ch. 6) | Book | Replication, partitioning |
| Cloudflare Blog | Blog | Anycast, Maglev, edge computing |
| Nginx Documentation | Docs | Load balancing configuration |
| "Understanding Distributed Systems" | Book | Networking fundamentals |

---

## Practice Exercise

**15-minute design**: Design a rate limiting system for an API:

- 3 tiers: Free (100 req/min), Pro (1000 req/min), Enterprise (10000 req/min)
- 10 API servers behind a load balancer
- Must be accurate (no double-counting)
- Redis available for centralized counters

**Key decisions**:
1. Which rate limiting algorithm would you use?
2. How do you handle distributed counting across 10 servers?
3. What happens when Redis is unavailable?
4. How do you handle clock skew across servers?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **`EXPIRE` on every rate-limit request** | The window never closes, so an actively-retrying client is locked out permanently | `EXPIRE ... NX`, or set the TTL only when `INCR` returns 1 |
| **`INCR` and `EXPIRE` as separate round trips** | A crash between them leaves a key with no TTL — a permanent ban | Pipeline them, or use a Lua script for real atomicity |
| **Round-robin to servers with long-lived connections** | Request *count* is balanced while actual load is not; WebSocket servers drift badly out of balance | Least-connections for stateful traffic; round-robin only for uniform short requests |
| **No health checks, or checking only the port** | A TCP listener can accept while the app is deadlocked or its DB is unreachable | Application-level `/health` that exercises real dependencies |
| **Health check that fails on a dependency outage** | Every instance reports unhealthy at once and the LB has nowhere to route — a total outage from a partial one | Separate liveness from readiness; degrade rather than removing every node |
| **DNS as the failover mechanism** | Clients and resolvers ignore TTLs; propagation takes minutes to hours | Anycast or an LB with health checks; treat DNS as coarse geo-routing only |
| **No rate-limiter fallback** | Redis down means either no limiting at all or a total outage | Decide fail-open vs fail-closed *per endpoint* and make it explicit |
| **Rate limiting without response headers** | Clients can't self-regulate, so they hammer you and retry blindly | Always return `X-RateLimit-*` and `Retry-After` |
| **Sticky sessions as the scaling plan** | Losing one server logs out every user on it, and load never rebalances | Externalize session state; keep servers stateless |

---

## Discussion Questions

1. You're designing a URL shortener. At what scale do you need a load balancer? What happens if the single server dies before that?

2. Compare L4 and L7 load balancing. You're building a gRPC-based microservice. Which would you choose and why?

3. Design a rate limiting system for an API with 3 tiers: free (100 req/min), pro (1000 req/min), enterprise (10000 req/min). How would you implement this across multiple servers?

4. Explain consistent hashing to a non-technical person. Why is it better than simple round-robin for a CDN?

5. You're designing a health check system. What would you check beyond "is the server responding"? What's the difference between readiness and liveness probes?

---

**Previous**: [Caching Strategies](../03-caching/README.md)
**Next**: [Asynchronous Systems and Message Queues](../05-async-systems/README.md)
