# Module 09: Design Case — URL Shortener and Rate Limiter

> **The canonical warm-up problems.** These two systems are the most common interview questions because they test fundamental skills: ID generation, read-heavy optimization, distributed counting, and algorithm choice.

## Learning Objectives

- Design a URL shortener end-to-end using the 9-step framework
- Implement rate limiting with appropriate algorithm choice
- Handle distributed ID generation at scale
- Design for read-heavy workloads

---

## Part 1: URL Shortener

### Requirements

- **Functional**: Create short URL, redirect to long URL, custom aliases, URL expiration, click analytics
- **Scale**: 100M new URLs/month, 100:1 read/write ratio
- **Latency**: <100ms for redirect
- **Availability**: 99.99%
- **Consistency**: Eventual OK for analytics, strong for URL creation

### Capacity Estimation

```
Write QPS:  100M / 30 days / 24h / 3600s ≈ 38 writes/sec
Read QPS:   38 × 100 = 3,800 reads/sec
Peak QPS:   38 × 3 = 114 writes/sec, 11,400 reads/sec

Storage per URL:
  short_code:  7 bytes (base62)
  long_url:    ~500 bytes average
  metadata:    ~100 bytes (user, timestamp, clicks)
  Total:       ~607 bytes

Per month: 100M × 607 bytes ≈ 60.7 GB
Per year:  ~728 GB
```

### API Design

```
POST /api/v1/urls
  Request:  { "long_url": "https://...", "custom_alias": "my-link", "expires_at": "2026-12-31" }
  Response: { "short_url": "https://short.ly/abc123", "created_at": "2026-07-21" }

GET /:short_code
  Response: 301 Redirect (or 302 for analytics)

DELETE /api/v1/urls/:short_code
  Response: 204 No Content

GET /api/v1/urls/:short_code/stats
  Response: { "clicks": 1234, "unique_visitors": 892, "last_accessed": "2026-07-21T10:30:00Z" }
```

### Data Model

Pick one dialect and stay in it — the two below are not interchangeable.

```sql
-- MySQL / MariaDB
CREATE TABLE urls (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    short_code  VARCHAR(10) NOT NULL,
    long_url    TEXT NOT NULL,
    user_id     BIGINT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NULL,
    click_count BIGINT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_short_code (short_code)   -- UNIQUE already creates the index
);

CREATE INDEX idx_user_id ON urls (user_id);
CREATE INDEX idx_expires ON urls (expires_at);   -- MySQL has no partial indexes
```

```sql
-- PostgreSQL
CREATE TABLE urls (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    short_code  VARCHAR(10) NOT NULL UNIQUE,
    long_url    TEXT NOT NULL,
    user_id     BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ,
    click_count BIGINT NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_user_id ON urls (user_id);
-- Partial index: only rows that can actually expire. Postgres-only.
CREATE INDEX idx_expires ON urls (expires_at) WHERE expires_at IS NOT NULL;
```

**Three things worth noticing:**

| Detail | Why |
|--------|-----|
| No separate index on `short_code` | `UNIQUE` already builds one. Adding `CREATE INDEX` on the same column duplicates the B-tree and slows every write. |
| `AUTO_INCREMENT` vs `GENERATED ... AS IDENTITY` | Dialect-specific. Mixing them (or adding a `WHERE` clause to a MySQL index) yields DDL that runs nowhere. |
| `TIMESTAMP` vs `TIMESTAMPTZ` | Store instants with a timezone. `TIMESTAMP` without one silently reinterprets on a server-timezone change. |

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    URL Shortener Architecture            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Client ────▶ Load Balancer ────▶ API Servers            │
│                                      │                   │
│                              ┌───────┼───────┐           │
│                              │       │       │           │
│                              ▼       ▼       ▼           │
│                           ┌─────┐ ┌─────┐ ┌─────┐        │
│                           │Redis│ │MySQL│ │Kafka│        │
│                           │cache│ │ DB  │ │     │        │
│                           └─────┘ └─────┘ └─────┘        │
│                                                          │
│  Write Path:                                             │
│  Client → API → Generate ID → Write DB → Invalidate      │
│                                  cache → Publish event   │
│                                                          │
│  Read Path:                                              │
│  Client → API → Check Redis → (miss: query DB,           │
│                                populate cache)           │
│                              → Return 301 redirect       │
│                              → Publish analytics event   │
└──────────────────────────────────────────────────────────┘
```

### Deep Dive: ID Generation Strategies

#### Strategy 1: Base62 Counter

```
  Alphabet (fix ONE and document it):
    "0123456789abcdef...xyzABCDEF...XYZ"   ← index 0 = '0'
     ^0        ^10                ^36

  Counter → base62:
     1 → "1"
    10 → "a"
    61 → "Z"
    62 → "10"     (1×62 + 0)
    63 → "11"
   3844 → "100"   (62²)

  Capacity: 62^7 ≈ 3.5 trillion codes — 2,900 years at 100M/month.

  Pros: Shortest possible codes, zero collisions by construction
  Cons: Sequential ⇒ enumerable (scrape every link); the shared counter
        is a coordination point and a single point of failure
```

> **Watch the alphabet.** `1 → "b"` and `62 → "10"` cannot both be true. The
> first assumes the alphabet starts at `a` (so `a`=0, `b`=1); the second assumes
> it starts at `0`. Mixing them produces codes that don't round-trip. Pick an
> ordering, write it down, and never change it — existing links depend on it.

**Making sequential IDs non-enumerable:** multiply the counter by a large
number coprime with 62^7 and take it mod 62^7. This is a bijection, so you keep
zero collisions, but consecutive counters land far apart in the output space.
Keep the multiplier secret and adjacent links stop being guessable.

#### Strategy 2: MD5 Hash

```
  hash("https://example.com/very/long/url") → "d41d8cd98f00b204e9800998ecf8427e"
  Take first 7 chars → base62 encode → "abc1234"

  Pros: Deterministic (same URL → same code)
  Cons: Collisions (need to check and retry), predictable
```

#### Strategy 3: Distributed ID Generator

```
  Pre-generate batches of unique IDs:
  Server 1: Gets IDs 1-1000
  Server 2: Gets IDs 1001-2000
  Server 3: Gets IDs 2001-3000

  Each server has a local counter. When exhausted, fetch next batch.
  No coordination needed for each request.

  Pros: High throughput, no single point of failure
  Cons: Slightly longer codes, need ID generation service
```

**Recommended**: Strategy 3 for production. Pre-generate IDs in batches, encode with base62.

### Deep Dive: Read Optimization

The read path must be fast (<100ms). Key optimizations:

```
  1. Redis cache (L2): Hot URLs cached with 24h TTL
  2. Local cache (L1): In-process LRU cache for extremely hot URLs
  3. Database indexing: Short code indexed for O(log n) lookup
  4. Connection pooling: Reuse DB connections

  Read path timing:
  L1 hit:  ~0.01ms (in-process)
  L2 hit:  ~0.5ms (Redis)
  DB hit:  ~3ms (MySQL with index)
  Total:   <5ms typical
```

### Deep Dive: Analytics

Click analytics are written asynchronously to avoid blocking the redirect.

```
  Redirect path:
  Client → GET /abc123 → 301 to long_url (fast, synchronous)

  Analytics path (async):
  API → Publish "ClickEvent" to Kafka
  → Analytics consumer → Write to analytics DB (ClickHouse)
  → Update click_count in Redis (atomic INCR)
  → Batch update MySQL every 1000 clicks
```

---

## Part 2: Rate Limiter

### Requirements

- **Functional**: Limit requests per client/IP/API key
- **Scale**: 10M requests/second globally
- **Latency**: <1ms overhead per request
- **Algorithm**: Token bucket (flexible burst)
- **Distributed**: Must work across multiple servers

### Algorithm Selection

```
  ┌───────────────────────────────────────────────────────┐
  │  Algorithm Choice Matrix                              │
  │                                                       │
  │  Need burst tolerance? ──Yes──▶ Token Bucket          │
  │       │                       (allows controlled      │
  │       No                        bursts)               │
  │       │                                               │
  │       ▼                                               │
  │  Need smooth rate? ────Yes──▶ Leaky Bucket            │
  │       │                       (constant output)       │
  │       No                                              │
  │       │                                               │
  │       ▼                                               │
  │  Need simplicity? ─────Yes──▶ Fixed Window            │
  │       │                       (simple counting)       │
  │       No                                              │
  │       │                                               │
  │       ▼                                               │
  │  Need accuracy? ───────Yes──▶ Sliding Window          │
  │                               (no boundary issues)    │
  └───────────────────────────────────────────────────────┘
```

### Token Bucket Implementation

```python
import time

class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
    
    def allow(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

# Usage: 100 requests/minute, burst of 10
limiter = TokenBucket(capacity=10, refill_rate=100/60)
```

### Distributed Rate Limiting with Redis

```
  ┌───────────────────────────────────────────────────┐
  │  Distributed Rate Limiter                         │
  │                                                   │
  │  API Server 1 ──┐                                 │
  │  API Server 2 ──┼──▶ Redis Cluster                │
  │  API Server 3 ──┘    (centralized counters)       │
  │                                                   │
  │  Redis INCR rate:{client_id}:{window}             │
  │  Redis EXPIRE rate:{client_id}:{window} 60        │
  │                                                   │
  │  If INCR > limit → REJECT (429 Too Many Requests) │
  └───────────────────────────────────────────────────┘
```

### Rate Limiter Response

```
  HTTP/1.1 429 Too Many Requests
  Retry-After: 30
  X-RateLimit-Limit: 100
  X-RateLimit-Remaining: 0
  X-RateLimit-Reset: 1690000000
```

### Rate Limiting Architecture

```
┌───────────────────────────────────────────────────────────┐
│              Rate Limiting Architecture                   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Client ────▶ API Gateway ────▶ Rate Limiter              │
│                                      │                    │
│                              ┌───────▼────────┐           │
│                              │  Redis Cluster │           │
│                              │  (counters)    │           │
│                              └────────────────┘           │
│                                      │                    │
│                              ┌───────▼────────┐           │
│                              │  Rules Engine  │           │
│                              │  - Per IP      │           │
│                              │  - Per User    │           │
│                              │  - Per API     │           │
│                              │  - Per Plan    │           │
│                              └────────────────┘           │
│                                                           │
│  Tiers:                                                   │
│  Free:      100 req/min                                   │
│  Pro:       1000 req/min                                  │
│  Enterprise: 10000 req/min                                │
│  Internal:  Unlimited                                     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Design Comparison: URL Shortener vs Rate Limiter

| Aspect | URL Shortener | Rate Limiter |
|--------|--------------|--------------|
| **Read-heavy** | Yes (100:1) | Yes (every request) |
| **Write pattern** | Batch inserts | Atomic increments |
| **Consistency** | Eventual for analytics | Strong for counting |
| **Cache** | Redis (hot URLs) | Redis (counters) |
| **Database** | MySQL (URLs) | Redis (primary) |
| **Key challenge** | ID generation | Distributed counting |

---

## Practice Exercise

**15-minute design**: Design a URL shortener from scratch.

1. (2 min) Clarify requirements
2. (3 min) Estimate capacity
3. (3 min) Define API
4. (2 min) Design data model
5. (5 min) Sketch architecture and deep dive on ID generation

**Follow-up questions**:
- How do you handle URL expiration?
- How do you prevent abuse (spam URLs)?
- How do you implement custom aliases?
- How do you scale to 1B URLs/month?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Using sequential IDs for short URLs** | Predictable, allows enumeration | Use base62 encoding or hash-based IDs |
| **No custom alias support** | Users want memorable links | Check uniqueness before inserting |
| **Synchronous analytics on redirect** | Adds latency to every request | Write analytics events to Kafka asynchronously |
| **Fixed window for rate limiting** | Boundary burst problem (2x limit in 2 seconds) | Use sliding window or token bucket |
| **No rate limiting fallback** | Redis down = no rate limiting | Fail open (allow) or fail closed (block) based on policy |

---

## Discussion Questions

1. Your URL shortener is live and a competitor is scraping every link by walking short codes sequentially. The codes came from a base62 counter. How do you stop it without breaking existing links?

   **Model answer**: Existing links must keep resolving, so you cannot re-issue codes. Two moves: (1) For *new* codes, keep the counter but pass it through a secret bijection — multiply by a constant coprime with 62⁷ and take the modulus. Still collision-free, but consecutive counters land far apart, so enumeration stops working. (2) Independently, rate-limit and bot-detect on the redirect path — an attacker who has already harvested the low range can keep replaying it. Note what this does *not* fix: the already-leaked codes stay guessable. If confidentiality actually matters, short codes were the wrong primitive — you want an unguessable random token, accepting a longer code and a collision check.

2. Redis, which holds both your hot URL cache and your rate limit counters, goes down. What happens to each, and what should happen?

   **Model answer**: They should fail in opposite directions. The **cache** should fail open: fall back to the database, accept the latency hit and the load spike, keep serving redirects. Guard the origin with request coalescing so 3,800 QPS of misses becomes one query per key. The **rate limiter** is a policy decision, and the honest answer is per-endpoint: fail open on cheap read paths (better to serve some abuse than to go dark), fail closed on expensive or destructive ones (link creation, auth). A single global choice is the mistake — "fail open everywhere" invites an attack timed to a Redis restart, "fail closed everywhere" turns a cache outage into a total outage.

3. You need 99.99% availability for redirects but only 99.9% for link creation. How does that asymmetry change the architecture?

   **Model answer**: It splits the system in two. Redirects are read-only, idempotent, and cacheable — replicate them to multiple regions, serve from edge caches, and they survive a primary database outage entirely (a stale mapping is still correct, since mappings are immutable). Creation needs uniqueness, which needs coordination, so it stays regional and accepts lower availability. Concretely: reads served from any region with an eventually-consistent replica; writes routed to a primary region with pre-allocated ID batches so a brief coordination outage doesn't block creation. The asymmetry is what lets you hit four nines cheaply — you would never get there if every redirect needed the write path.

4. A single link goes viral: 500K requests/second to one short code. Everything else is normal. What breaks and what do you do?

   **Model answer**: The hot-key problem. Consistent hashing sends one key to exactly one cache node, so that node saturates while the rest idle — sharding does not help, because the load is one key. Fixes, in order of preference: (1) In-process L1 cache on every API server — an immutable mapping with a short TTL means each server hits Redis once per TTL, and 500K QPS collapses to (server count / TTL). (2) Replicate the hot key across N cache nodes with a suffix and read from a random replica. (3) If it is HTTP-cacheable, let the CDN absorb it — a 301 with a long `Cache-Control` never reaches you at all. L1 caching is the right first answer because URL mappings are immutable, which makes cache invalidation a non-problem.

5. Your token bucket allows a burst of 10 with a 100/minute refill. A client sends 10 requests instantly, then 1 request every 600ms forever. Are they within their limit? Is that what you wanted?

   **Model answer**: Yes, they are compliant — and yes, that is the intended behaviour, which is the point of the question. Refill is 100/60 ≈ 1.67 tokens/second, so one request per 600ms consumes exactly the refill rate and sustains indefinitely. The initial burst of 10 is the bucket capacity, granted once. Sustained throughput is 100/minute as specified. If you *don't* want the burst — say each request triggers expensive work — token bucket is the wrong algorithm; use a leaky bucket, which shapes output to a constant rate and queues rather than admitting spikes. The general lesson: "100 requests per minute" is underspecified until you say what burst behaviour you accept.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview (Ch. 1-3) | Book | URL shortener, rate limiter |
| ByteByteGo | Video | Visual explanations |
| "System Design Canon" | Blog | Twitter, URL shortener, rate limiter |
| Redis Documentation | Docs | INCR, EXPIRE, sorted sets |

---

**Previous**: [Distributed Systems Deep Dive](../08-distributed-systems/README.md)
**Next**: [Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md)
