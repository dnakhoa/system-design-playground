# Module 03: Caching Strategies

> **The fastest way to improve system performance.** Caching reduces latency from 100ms to 1ms and can cut database load by 90%+. But cache invalidation is one of the two hard problems in computer science.

## Learning Objectives

- Understand cache-aside, write-through, write-back, and write-around patterns
- Design Redis caching layers with appropriate eviction policies
- Implement CDN caching with proper cache headers
- Prevent cache stampede and thundering herd problems
- Know when NOT to cache

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
  Read path:
  ┌────────┐     1. Check cache     ┌────────┐
  │  App   │────────────────────────▶│ Cache  │
  │        │◀── 2. Cache HIT ────────│(Redis) │
  │        │                         └────────┘
  │        │     3. Cache MISS
  │        │───────────────────────────────────▶┌────────┐
  │        │◀── 4. Return data ────────────────│   DB   │
  │        │     5. Populate cache              └────────┘
  │        │────────────────▶ Cache
  └────────┘

  Write path:
  ┌────────┐     1. Write to DB     ┌────────┐
  │  App   │────────────────────────▶│   DB   │
  │        │     2. Invalidate cache └────────┘
  │        │────────────────▶ Cache (DELETE key)
  └────────┘
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
  ┌────────┐     1. Write to cache  ┌────────┐
  │  App   │────────────────────────▶│ Cache  │
  └────────┘     (fast!)            └───┬────┘
                                        │
                                   2. Async flush
                                   (batched, delayed)
                                        │
                                        ▼
                                   ┌────────┐
                                   │   DB   │
                                   └────────┘
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
  ┌─────────────────────────────────────┐
  │              Redis                   │
  ├─────────────────────────────────────┤
  │  Single-threaded event loop          │
  │  ┌─────────────────────────────┐    │
  │  │  Accept → Parse → Execute   │    │
  │  │       → Respond             │    │
  │  │  (all in one thread)        │    │
  │  └─────────────────────────────┘    │
  │                                      │
  │  In-memory data store                │
  │  No disk I/O on hot path             │
  │  Efficient data structures           │
  └─────────────────────────────────────┘

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
                        ┌──────────────────┐
                        │    Origin Server  │
                        │    (your app)     │
                        └────────┬─────────┘
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
    
    # Bump version (old key expires naturally)
    r.incr(f"user:{user_id}:version")
    
    # Optional: explicitly delete old version
    old_version = r.get(f"user:{user_id}:version")
    if old_version:
        r.delete(f"user:{user_id}:v{old_version}")
```

| Pros | Cons |
|------|------|
| No race conditions, old versions serve stale but valid data | Key management complexity |

---

## Cache Stampede (Thundering Herd)

When a popular cache key expires, 1000+ simultaneous requests all miss and hit the origin.

```
  BEFORE:                         AFTER EXPIRY:
  ┌──────────┐                    ┌──────────┐
  │   Cache  │ ◄── All hit       │   Cache  │ ◄── All MISS
  │  (warm)  │                    │ (expired)│
  └──────────┘                    └────┬─────┘
                                       │
                              ┌────────┼────────┐
                              │        │        │
                              ▼        ▼        ▼
                           ┌─────┐ ┌─────┐ ┌─────┐
                           │ DB  │ │ DB  │ │ DB  │  ← 1000 requests hit DB!
                           └─────┘ └─────┘ └─────┘
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

# Global lock map for request coalescing
_inflight = {}
_lock = threading.Lock()

def get_with_coalescing(key: str, ttl: int = 3600) -> str:
    """Deduplicate concurrent requests for the same key."""
    value = r.get(key)
    if value:
        return value
    
    with _lock:
        if key in _inflight:
            # Another request is already fetching: wait for it
            return _inflight[key].wait()
        
        # We're the first: create an event for others to wait on
        event = threading.Event()
        _inflight[key] = event
    
    try:
        # Fetch from DB (only ONE request does this)
        data = db.query(key)
        r.setex(key, ttl, data)
        event.set()  # Wake up all waiting requests
        return data
    finally:
        with _lock:
            del _inflight[key]
```

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
┌─────────────────────────────────────────────────────────┐
│                    Netflix Caching Stack                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  CDN (Open Connect)                              │    │
│  │  - 10,000+ edge servers worldwide                │    │
│  │  - Caches video content (adaptive bitrate)       │    │
│  │  - 95%+ of traffic served from edge              │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Application Cache (EVCache / Memcached)         │    │
│  │  - User profiles, viewing history, preferences   │    │
│  │  - Per-device personalization                    │    │
│  │  - TTL: 10 minutes to 24 hours (varies)          │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Pre-computation Cache                           │    │
│  │  - Recommendation results (personalized rows)    │    │
│  │  - Pre-rendered homepage layout                  │    │
│  │  - Updated every few minutes via background jobs │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Database Layer                                  │    │
│  │  - Cassandra (user data, viewing history)        │    │
│  │  - MySQL (billing, subscriptions)                │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
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

**Previous**: [Databases and Storage](../02-databases-storage/README.md)
**Next**: [Load Balancing and Networking](../04-load-balancing/README.md)
