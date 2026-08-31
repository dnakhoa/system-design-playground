# Module 03: Caching Strategies

> **The fastest way to improve system performance.** Caching reduces latency from 100ms to 1ms and can cut database load by 90%+. But cache invalidation is one of the two hard problems in computer science.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 02 | Databases and Storage | [../02-databases-storage/](../02-databases-storage/) |
| **Module 03** | **Caching Strategies** | **(current)** |
| Module 04 | Load Balancing and Networking | [../04-load-balancing/](../04-load-balancing/) |

---

## Learning Objectives

- Understand cache-aside, write-through, write-back, and write-around patterns
- Design Redis caching layers with appropriate eviction policies
- Implement CDN caching with proper cache headers
- Prevent cache stampede and thundering herd problems
- Know when NOT to cache

---

## Table of Contents

1. [Why Caching Matters](#why-caching-matters)
2. [Cache Patterns](#cache-patterns)
3. [Pattern Comparison](#pattern-comparison)
4. [Redis Architecture](#redis-architecture)
5. [CDN Caching](#cdn-caching)
6. [Cache Invalidation Strategies](#cache-invalidation-strategies)
7. [Cache Stampede (Thundering Herd)](#cache-stampede-thundering-herd)
8. [Hot Keys](#hot-keys)
9. [When NOT to Cache](#when-not-to-cache)
10. [Case Study: Netflix Caching Architecture](#case-study-netflix-caching-architecture)
11. [Key References](#key-references)
12. [Practice Exercise](#practice-exercise)
13. [Common Mistakes](#common-mistakes)
14. [Discussion Questions](#discussion-questions)

---

## Why Caching Matters

The numbers tell the story:

```
  Request without cache:          Request with cache:

  Client ──100ms──▶ DB           Client ──1ms──▶ Cache (HIT)
       ◀──100ms──                        ◀──1ms──

  1000 requests:                  1000 requests:
  1000 × 100ms = 100 seconds     200 × 100ms + 800 × 1ms = 20.8 seconds

  Database handles 1000 QPS       Database handles only 200 QPS (80% offloaded)
```

### Cache Hit Ratio

The **cache hit ratio** determines caching effectiveness:

```
Hit Ratio = Cache Hits / (Cache Hits + Cache Misses)

  50% hit ratio:  Database still handles 50% of traffic
  80% hit ratio:  Database handles 20% of traffic  ← minimum target
  95% hit ratio:  Database handles 5% of traffic   ← excellent
  99% hit ratio:  Database handles 1% of traffic   ← near-perfect
```

**The 80/20 rule applies**: 20% of data receives 80% of traffic. Cache that 20%.

---

## Cache Patterns

### Cache-Aside (Lazy Loading)

The most common pattern. The application manages the cache explicitly.

```
  READ PATH

  ┌─────────┐                              ┌─────────┐
  │         │ ──① check cache────────────▶ │  Cache  │
  │   App   │ ◀─② HIT: return value─────── │ (Redis) │
  │         │                              └─────────┘
  │         │
  │         │ ──③ MISS: query DB─────────▶ ┌─────────┐
  │         │ ◀─④ return rows──────────────│   DB    │
  │         │                              └─────────┘
  │         │ ──⑤ SET key (populate)─────▶ ┌─────────┐
  │         │                              │  Cache  │
  └─────────┘                              └─────────┘

  WRITE PATH

  ┌─────────┐                              ┌─────────┐
  │         │ ──① write───────────────────▶│   DB    │
  │   App   │                              └─────────┘
  │         │ ──② DEL key (invalidate)────▶┌─────────┐
  │         │                              │  Cache  │
  └─────────┘                              └─────────┘

  Note step ② deletes rather than updates. Writing the new value into
  the cache looks tidier but races: two concurrent writers can leave the
  cache holding the older of the two values. Deleting is safe because the
  next reader repopulates from the database.
```

| Pros | Cons |
|------|------|
| Only requested data is cached | Cache miss = 3 round trips (app→cache→DB→cache→app) |
| Fail-safe (cache down → DB still works) | First request always slow (cold start) |
| Easy to implement | Stale data possible (between write and invalidation) |

### Write-Through

Cache and database are updated simultaneously.

```
  ┌────────┐     1. Write to cache  ┌────────┐
  │  App   │────────────────────────▶│ Cache  │
  │        │                         └───┬────┘
  │        │     2. Synchronous write    │
  │        │                             ▼
  │        │                         ┌────────┐
  │        │                         │   DB   │
  │        │                         └────────┘
  └────────┘

  Read path: Same as cache-aside (cache always has fresh data)
```

| Pros | Cons |
|------|------|
| Cache is always consistent with DB | Write latency = cache + DB latency |
| Read after write is fast | Most data written is never read (wasted cache) |
| Simple to reason about | |

### Write-Back (Write-Behind)

Writes go to cache first, then asynchronously flushed to DB.

```
  ┌─────────┐                              ┌─────────┐
  │   App   │ ──① write (returns now)────▶ │  Cache  │
  └─────────┘                              └────┬────┘
                                                │
                                         ② async flush
                                        (batched, delayed)
                                                │
                                                ▼
                                           ┌─────────┐
                                           │   DB    │
                                           └─────────┘

  The write returns as soon as the cache accepts it, so latency is
  cache-only. The gap between ① and ② is the exposure window: a cache
  crash in that window loses every unflushed write.
```

| Pros | Cons |
|------|------|
| Very fast writes (only cache latency) | Data loss risk (cache crash before flush) |
| Write batching reduces DB load | Complexity (queue, retry logic) |
| | Read-after-write may show stale DB data |

**When to use**: Write-heavy workloads where brief data loss is acceptable (analytics, counters, logs).

### Write-Around

Writes go directly to DB, bypassing cache. Only reads populate cache.

```
  Write: App → DB (bypasses cache)
  Read:  App → Cache → (miss) → DB → populate cache
```

| Pros | Cons |
|------|------|
| Prevents cache pollution (only requested data cached) | First read always slow |
| Write amplification avoided | |

**When to use**: Large objects that are rarely read after writing (video uploads, document storage).

---

## Pattern Comparison

| Pattern | Read Latency | Write Latency | Data Freshness | Complexity | Cache Pollution |
|---------|-------------|---------------|----------------|------------|-----------------|
| Cache-Aside | Slow on miss | Medium | Eventual | Low | Low |
| Write-Through | Fast | Slow | Strong | Medium | High |
| Write-Back | Fast | Very fast | Eventual | High | Medium |
| Write-Around | Slow on miss | Fast | Strong | Low | None |

---

## Redis Architecture

Redis is the most popular caching system. Understanding its internals is critical.

### Why Redis Is Fast

```
  ┌──────────────────────────────────────┐
  │              Redis                   │
  ├──────────────────────────────────────┤
  │  Single-threaded event loop          │
  │  ┌─────────────────────────────┐     │
  │  │  Accept → Parse → Execute   │     │
  │  │       → Respond             │     │
  │  │  (all in one thread)        │     │
  │  └─────────────────────────────┘     │
  │                                      │
  │  In-memory data store                │
  │  No disk I/O on hot path             │
  │  Efficient data structures           │
  └──────────────────────────────────────┘

  Why single-threaded is fast:
  - No context switching
  - No locking overhead
  - No race conditions
  - CPU cache-friendly
```

### Key Data Structures

| Data Structure | Use Case | Commands |
|---------------|----------|----------|
| **Strings** | Simple key-value, counters, session tokens | GET, SET, INCR, MGET |
| **Hashes** | Objects with multiple fields (user profiles) | HGET, HSET, HMGET |
| **Lists** | Message queues, activity feeds, recent items | LPUSH, RPOP, LRANGE |
| **Sets** | Tags, unique items, membership checks | SADD, SINTER, SUNION |
| **Sorted Sets** | Leaderboards, time-series, priority queues | ZADD, ZRANGE, ZRANK |
| **Streams** | Event sourcing, message queues (Kafka-like) | XADD, XREAD, XACK |

### Eviction Policies

When Redis memory is full, it evicts keys:

| Policy | Behavior | Best For |
|--------|----------|----------|
| **allkeys-lru** | Evict least recently used (any key) | General caching |
| **volatile-lru** | Evict LRU among keys with expiry | When some keys must never expire |
| **allkeys-lfu** | Evict least frequently used | When frequency matters more than recency |
| **volatile-ttl** | Evict keys with shortest TTL | Short-lived cache entries |
| **noeviction** | Return errors on write | When data must not be lost |

---

## CDN Caching

Content Delivery Networks cache static assets at edge locations worldwide.

### CDN Topology

```
                        ┌───────────────────┐
                        │    Origin Server  │
                        │    (your app)     │
                        └────────┬──────────┘
                                 │
                        ┌────────▼─────────┐
                        │  Origin Shield   │
                        │  (mid-tier cache)│
                        └────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼─────────┐ ┌─────▼────────┐ ┌──────▼───────┐
     │  Edge Server     │ │ Edge Server  │ │ Edge Server  │
     │  (New York)      │ │ (London)     │ │ (Tokyo)      │
     └────────┬─────────┘ └─────┬────────┘ └──────┬───────┘
              │                  │                  │
         ┌────▼────┐       ┌────▼────┐        ┌────▼────┐
         │ Users   │       │ Users   │        │ Users   │
         │ (US)    │       │ (EU)    │        │ (Asia)  │
         └─────────┘       └─────────┘        └─────────┘
```

### Cache-Control Headers

```
Cache-Control: max-age=3600          # Cache for 1 hour
Cache-Control: no-cache              # Must revalidate with origin
Cache-Control: no-store              # Never cache
Cache-Control: public, max-age=86400 # Cache publicly for 24h
Cache-Control: private, no-cache     # Cache privately, must revalidate
ETag: "abc123"                       # Version identifier for revalidation
Last-Modified: Wed, 21 Jul 2026 ...  # Timestamp for revalidation
```

### Stale-While-Revalidate

Serves cached content immediately while refreshing in the background.

```
  Cache-Control: max-age=60, stale-while-revalidate=3600

  Timeline:
  0s:    Serve fresh cache (fast)
  60s:   Cache expires
  60-3060s: Serve stale cache (fast) + revalidate in background
  3061s: Fresh cache available
```

**When to use**: Content that can be briefly stale (search results, product listings, social feeds).

---

## Cache Invalidation Strategies

### TTL (Time-To-Live)

```redis
# Set key with 1-hour expiry
SET user:123 '{"name": "Alice", "email": "..."}' EX 3600

# Check remaining TTL
TTL user:123    # Returns: 3542 (seconds remaining)

# Refresh TTL on access (extend by 1 hour)
EXPIRE user:123 3600
```

```python
# Application-level TTL with Redis
import redis
import json

r = redis.Redis()

def get_user(user_id: int) -> dict:
    key = f"user:{user_id}"
    
    # Try cache first
    cached = r.get(key)
    if cached:
        r.expire(key, 3600)  # Refresh TTL on access
        return json.loads(cached)
    
    # Cache miss: query DB
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    
    # Populate cache with 1-hour TTL
    r.setex(key, 3600, json.dumps(user))
    return user
```

| Pros | Cons |
|------|------|
| Simple, automatic cleanup | Data may be stale for up to TTL duration |

### Event-Driven Invalidation

```python
# Write-through invalidation
def update_user(user_id: int, name: str):
    # 1. Update database
    db.execute("UPDATE users SET name = %s WHERE id = %s", name, user_id)
    
    # 2. Invalidate cache (delete, don't update)
    r.delete(f"user:{user_id}")
    
    # Next read will repopulate cache with fresh data

# Problem: Race condition
# Thread A: UPDATE users SET name = 'Alice' WHERE id = 123
# Thread B: SELECT * FROM users WHERE id = 123  (reads OLD name)
# Thread A: DEL cache:user:123
# Thread B: SET cache:user:123 '{"name": "Bob"}'  (caches OLD data!)
# 
# Solution: Use a version column or lock
```

```sql
-- Version-based invalidation (safe)
UPDATE users SET name = 'Alice', version = version + 1 WHERE id = 123;
-- Cache key includes version: user:123:v5
-- Old key user:123:v4 naturally expires
```

| Pros | Cons |
|------|------|
| Cache is always fresh (eventual consistency) | Race conditions (concurrent writes), missed invalidations |

### Versioned Keys

```python
# Versioned key pattern
def get_user(user_id: int) -> dict:
    # Get current version from metadata
    version = r.get(f"user:{user_id}:version") or "1"
    key = f"user:{user_id}:v{version}"
    
    cached = r.get(key)
    if cached:
        return json.loads(cached)
    
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    r.setex(key, 3600, json.dumps(user))
    return user

def update_user(user_id: int, name: str):
    db.execute("UPDATE users SET name = %s WHERE id = %s", name, user_id)
    
    # Bump version. INCR returns the NEW version, so the key we want to
    # evict is new_version - 1. Reading the counter again here would give
    # us the new version and delete the key we are about to populate.
    new_version = r.incr(f"user:{user_id}:version")
    
    # Optional: reclaim the superseded key immediately instead of
    # waiting for its TTL to lapse.
    if new_version > 1:
        r.delete(f"user:{user_id}:v{new_version - 1}")
```

> **Why not read the version back?** `INCR` is the only race-free way to learn
> the version you just created. A separate `GET` can observe another writer's
> increment, and subtracting from *that* value evicts a live key.

| Pros | Cons |
|------|------|
| No race conditions, old versions serve stale but valid data | Key management complexity |

---

## Cache Stampede (Thundering Herd)

When a popular cache key expires, 1000+ simultaneous requests all miss and hit the origin.

```
  BEFORE EXPIRY                    AFTER EXPIRY

  1000 req/s                       1000 req/s
      │                                │
      ▼                                ▼
  ┌──────────┐                     ┌──────────┐
  │  Cache   │                     │  Cache   │
  │  (warm)  │ ── all HIT          │(expired) │ ── all MISS
  └──────────┘                     └────┬─────┘
                                        │
                                  ┌─────┴─────┐
                                  │ 1000 req  │
                                  │ stampede  │
                                  └─────┬─────┘
                                        │
                                        ▼
                                   ┌──────────┐
                                   │    DB    │ ← built for 200 req/s
                                   └──────────┘

  One key expiring converts a fully-cached workload into an unthrottled
  flood. The database was sized for the MISS rate, not the request rate.
```

### Solutions

**1. Mutex / Locking**

```python
import redis
import time

r = redis.Redis()

def get_with_lock(key: str, ttl: int = 3600) -> str:
    """Cache-aside with distributed lock to prevent stampede."""
    # Try cache first
    value = r.get(key)
    if value:
        return value
    
    lock_key = f"lock:{key}"
    
    # Try to acquire lock (NX = only if not exists, EX = auto-expire)
    if r.set(lock_key, "1", nx=True, ex=10):  # Lock for 10 seconds
        try:
            # We won the lock: fetch from DB and populate cache
            data = db.query(key)
            r.setex(key, ttl, data)
            return data
        finally:
            r.delete(lock_key)
    else:
        # Another request is fetching: wait and retry
        time.sleep(0.05)  # 50ms
        return r.get(key) or get_with_lock(key, ttl)  # Retry
```

**2. Probabilistic Early Expiration**

```python
import random
import time

def get_with_early_expiration(key: str, ttl: int = 3600) -> str:
    """Serve stale data before actual expiration to prevent stampede."""
    value = r.get(key)
    if not value:
        return populate_cache(key, ttl)
    
    # Check remaining TTL
    remaining_ttl = r.ttl(key)
    if remaining_ttl < 0:
        return populate_cache(key, ttl)
    
    # Probabilistic early expiration
    # As TTL approaches 0, probability of "soft miss" increases
    expiration_probability = 1 - (remaining_ttl / ttl)
    
    if random.random() < expiration_probability:
        # Soft miss: serve stale data + async refresh
        import threading
        threading.Thread(target=populate_cache, args=(key, ttl)).start()
    
    return value
```

**3. Request Coalescing**

```python
import threading

# Global map of in-flight fetches, one Future per key.
_inflight: dict[str, "Future"] = {}
_lock = threading.Lock()

class Future:
    """Minimal result-carrying handle. concurrent.futures.Future works too."""

    def __init__(self):
        self._event = threading.Event()
        self._value = None
        self._error = None

    def set_result(self, value):
        self._value = value
        self._event.set()

    def set_error(self, error):
        self._error = error
        self._event.set()

    def result(self, timeout: float = 5.0):
        if not self._event.wait(timeout):
            raise TimeoutError("leader did not publish a result in time")
        if self._error:
            raise self._error
        return self._value

def get_with_coalescing(key: str, ttl: int = 3600) -> str:
    """Deduplicate concurrent requests for the same key."""
    value = r.get(key)
    if value:
        return value

    with _lock:
        existing = _inflight.get(key)
        if existing is not None:
            leader = False
            future = existing
        else:
            # We're the first: publish a Future for others to wait on.
            leader = True
            future = Future()
            _inflight[key] = future

    if not leader:
        # Followers block on the Future and receive the leader's VALUE.
        return future.result()

    try:
        # Fetch from DB (only ONE request does this).
        data = db.query(key)
        r.setex(key, ttl, data)
        future.set_result(data)
        return data
    except Exception as exc:
        # Never leave followers blocked forever on a failed fetch.
        future.set_error(exc)
        raise
    finally:
        # Remove the entry only AFTER the result is published, so a late
        # follower either sees the Future or re-reads the now-warm cache.
        with _lock:
            _inflight.pop(key, None)
```

> **The bug this avoids:** `threading.Event.wait()` returns a **bool**, not the
> fetched value. A coalescing implementation that does `return event.wait()`
> hands every follower `True` instead of the data. The waiter needs a handle
> that carries a result — and the leader must publish an error on the failure
> path, or followers block until their timeout.

---

## Hot Keys

A single key receiving disproportionate traffic can overwhelm one cache node.

```
  Normal distribution:        Hot key problem:
  ┌───┐ ┌───┐ ┌───┐ ┌───┐   ┌───┐ ┌───┐ ┌───┐ ┌───────┐
  │ ██│ │██ │ │██ │ │██ │   │ ██│ │██ │ │██ │ │███████│
  │ ██│ │██ │ │██ │ │██ │   │ ██│ │██ │ │██ │ │███████│
  └───┘ └───┘ └───┘ └───┘   └───┘ └───┘ └───┘ └───────┘
  Shard 1  2    3    4       Shard 1  2    3    4 (overloaded!)
```

### Solutions

**1. Local caching (L1)**

```python
from cachetools import TTLCache

# In-process LRU cache (per application instance)
_local_cache = TTLCache(maxsize=10000, ttl=60)  # 10K items, 60s TTL

def get_with_local_cache(key: str) -> str:
    """Two-layer cache: local (in-process) + Redis."""
    # L1: Check local cache (fastest, ~0.01ms)
    if key in _local_cache:
        return _local_cache[key]
    
    # L2: Check Redis (~0.5ms)
    value = r.get(key)
    if value:
        _local_cache[key] = value  # Populate L1
        return value
    
    # L3: Check DB (~3ms)
    value = db.query(key)
    r.setex(key, 3600, value)  # Populate L2
    _local_cache[key] = value  # Populate L1
    return value
```

**2. Key replication**

```python
import random

REPLICAS = 3  # Number of replicas per hot key

def set_hot_key(key: str, value: str, ttl: int = 3600):
    """Store hot key across multiple Redis shards."""
    for i in range(REPLICAS):
        replica_key = f"{key}:replica{i}"
        r.setex(replica_key, ttl, value)

def get_hot_key(key: str) -> str:
    """Read from random replica to distribute load."""
    replica = random.randint(0, REPLICAS - 1)
    replica_key = f"{key}:replica{replica}"
    
    value = r.get(replica_key)
    if value:
        return value
    
    # Fallback: try all replicas
    for i in range(REPLICAS):
        value = r.get(f"{key}:replica{i}")
        if value:
            return value
    
    return None
```

**3. Cache hierarchy**

```python
class CacheHierarchy:
    """Three-layer cache: L1 (local) → L2 (Redis) → L3 (CDN)."""
    
    def __init__(self):
        self.l1 = TTLCache(maxsize=10000, ttl=60)   # In-process
        self.l2 = redis.Redis()                       # Redis cluster
        # L3 is handled by CDN (nginx/cloudflare)
    
    def get(self, key: str) -> str:
        # L1: In-process (fastest)
        if key in self.l1:
            return self.l1[key]
        
        # L2: Redis (shared, sub-millisecond)
        value = self.l2.get(key)
        if value:
            self.l1[key] = value
            return value
        
        # L3: Origin (CDN misses go here)
        value = origin_fetch(key)
        self.l2.setex(key, 3600, value)
        self.l1[key] = value
        return value
```

---

## When NOT to Cache

| Scenario | Why Not |
|----------|---------|
| **Strong consistency required** | Banking, inventory — stale data = lost money |
| **Frequently changing data** | Real-time stock prices — cache expires before useful |
| **Unique per-user data** | "Show me MY orders" — low hit ratio, waste of cache |
| **Write-heavy workloads** | Cache invalidation overhead exceeds benefit |
| **Small datasets** | If DB serves it in <5ms, caching adds complexity for minimal gain |
| **Cold data** | Data accessed once then never again — no reuse to cache |

---

## Case Study: Netflix Caching Architecture

Netflix serves 230M+ subscribers with a sophisticated multi-layer caching strategy.

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Netflix Caching Stack                  │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  CDN (Open Connect)                              │     │
│  │  - 10,000+ edge servers worldwide                │     │
│  │  - Caches video content (adaptive bitrate)       │     │
│  │  - 95%+ of traffic served from edge              │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Application Cache (EVCache / Memcached)         │     │
│  │  - User profiles, viewing history, preferences   │     │
│  │  - Per-device personalization                    │     │
│  │  - TTL: 10 minutes to 24 hours (varies)          │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Pre-computation Cache                           │     │
│  │  - Recommendation results (personalized rows)    │     │
│  │  - Pre-rendered homepage layout                  │     │
│  │  - Updated every few minutes via background jobs │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Database Layer                                  │     │
│  │  - Cassandra (user data, viewing history)        │     │
│  │  - MySQL (billing, subscriptions)                │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Content is CDN-cached at massive scale**: Video segments are pre-positioned at edge locations based on popularity predictions. 95%+ of video traffic never touches Netflix's origin servers.

2. **Personalization is pre-computed**: Your "Top 10" row is not computed in real-time. It's pre-computed and cached. When you open Netflix, the app fetches your pre-rendered homepage from cache.

3. **Per-device cache invalidation**: Your phone and TV have different cached states. When you watch something on one device, the other device's cache is invalidated asynchronously.

4. **Graceful degradation**: If the recommendation cache is down, Netflix falls back to generic popular content. The service degrades but never goes fully offline.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Designing Data-Intensive Applications (Ch. 5) | Book | Caching patterns, consistency |
| Redis Documentation | Docs | Data structures, eviction policies |
| Netflix Tech Blog | Blog | EVCache, multi-layer caching |
| Cloudflare Blog | Blog | CDN caching strategies |
| HTTP Caching (MDN) | Docs | Cache-Control headers |

---

## Practice Exercise

**15-minute design**: Design a caching strategy for a news website:

- Articles are published once, read millions of times
- 100M page views/day, 80% on homepage
- Articles have images (200KB each)
- CDN already serves static assets

**Key decisions**:
1. What cache layers would you use?
2. What's the TTL for article content?
3. How do you handle cache invalidation when an article is updated?
4. How do you prevent cache stampede when a breaking news story goes viral?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Caching everything** | Low hit ratio wastes memory, adds complexity | Cache only hot data (20% that gets 80% traffic) |
| **No cache invalidation strategy** | Stale data, inconsistent state | Choose TTL, event-driven, or versioned keys upfront |
| **Ignoring cache stampede** | Popular key expiry causes thundering herd | Use locking, probabilistic early expiration, or request coalescing |
| **Caching strong-consistency data** | Banking/inventory can't tolerate staleness | Don't cache data that requires strong consistency |
| **Forgetting about cold start** | First request always slow | Pre-warm cache for critical data |

---

## Discussion Questions

1. You're building a social media app. Users have a "following feed" that shows posts from people they follow. What cache pattern would you use, and what invalidation strategy?

2. Explain cache stampede to a junior engineer. What are three ways to prevent it?

3. You're designing a real-time auction system. Bid data updates every second. Would you cache bid amounts? Why or why not?

4. Your Redis cluster is running out of memory. You have 10M cached user profiles, but only 1M are accessed daily. What eviction policy would you choose, and why?

5. You're building a news website. Articles are published once and read millions of times. What caching strategy would you use for article content?

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 09: Design Case — URL Shortener and Rate Limiter](../09-case-url-shortener-rate-limiter/README.md) | Works through the hot-key problem (L1 cache, key replication) and a Redis-outage fail-open/fail-closed decision in a concrete system |
| [Module 10: Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md) | The celebrity fan-out problem is this module's hot-key problem by another name, fixed with the same pre-computation-and-cache approach |
| [Module 11: Design Case — Distributed File Storage and Video Streaming](../11-case-storage-streaming/README.md) | Extends CDN Caching into origin shields and edge hit-ratio math for video — the engineering behind this module's Netflix case study |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Logical clocks and consensus generalize the write-ordering race this module patches locally with a version column |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│               Caching Strategies — Key Takeaways               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Cache the hot 20% of data, not everything — a low hit ratio│
│     just adds memory cost and invalidation complexity for      │
│     nothing                                                    │
│  2. Delete on write, don't overwrite the cache — two racing    │
│     writers can otherwise leave stale data cached indefinitely │
│  3. Never cache data that must be exactly right — banking      │
│     balances and inventory counts don't get to be stale        │
│  4. Sharding does not fix a hot key — the traffic is           │
│     concentrated on one key no matter how many shards exist, so│
│     fix it with an L1 cache, replication, or the CDN instead   │
│  5. A single popular key expiring can flood a database sized   │
│     for the miss rate, not the request rate — guard it with    │
│     locking, coalescing, or early expiration before it happens,│
│     not after                                                  │
│  6. Write-back trades durability for speed — only use it where │
│     losing the last few seconds of writes is genuinely         │
│     acceptable                                                 │
│  7. `INCR` is the only race-free way to read the version you   │
│     just wrote — a separate `GET` can always lose to someone   │
│     else's increment                                           │
│  8. A coalescing cache must hand every follower the leader's   │
│     actual value, errors included — a bare `Event.wait()`      │
│     return value is not a result                               │
│  9. Design the degraded mode before the outage, not during it —│
│     Netflix falls back to generic recommendations rather than  │
│     going dark when its cache fails                            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 02: Databases and Storage](../02-databases-storage/README.md)

**Next:** [Module 04: Load Balancing and Networking](../04-load-balancing/README.md)

---

*Module 03 of 22 in the System Design Playground*
