# Module 01: System Design Fundamentals

> **The mental models every system designer needs.** Before you can design a chat system or an LLM inference pipeline, you need a shared vocabulary for reasoning about requirements, trade-offs, and architecture.

## Learning Objectives

- Understand what system design is and why it matters
- Estimate capacity from vague requirements (QPS, storage, bandwidth)
- Apply the 9-step framework to any design problem
- Reason about the CAP theorem and consistency models
- Choose between scalability strategies

---

## What Is System Design?

System design is the process of defining the architecture, components, modules, interfaces, and data flows of a system to satisfy specified requirements. It answers three questions:

1. **What** are we building? (functional requirements)
2. **How big** must it be? (non-functional requirements: scale, latency, availability)
3. **How** do we build it? (architecture and trade-offs)

```
   Requirements                  Architecture                Trade-offs
  ┌─────────────┐              ┌─────────────┐            ┌─────────────┐
  │ Functional   │   ──────►   │ Services    │   ──────►  │ Cost vs     │
  │ Non-functional│            │ Data stores │            │ Performance │
  │ Constraints  │            │ Interfaces  │            │ Simplicity  │
  └─────────────┘              └─────────────┘            │ vs Flexibility│
                                                          └─────────────┘
```

The hardest part is not drawing boxes and arrows — it's making **explicit trade-offs** and defending them.

---

## Key System Properties

### Scalability

The ability to handle increased load by adding resources.

```
  VERTICAL SCALING              HORIZONTAL SCALING
  (Scale Up)                    (Scale Out)

  ┌──────────┐                  ┌───┐ ┌───┐ ┌───┐
  │          │                  │   │ │   │ │   │
  │  BIGGER  │                  │ S │ │ S │ │ S │
  │  SERVER  │                  │   │ │   │ │   │
  │          │                  └───┘ └───┘ └───┘
  └──────────┘                     │     │     │
                                   └─────┴─────┘
                                        │
                                   Load Balancer
```

| Factor | Vertical | Horizontal |
|--------|----------|------------|
| **Complexity** | Low | Higher (distributed state) |
| **Limits** | Hardware ceiling | Near-infinite |
| **Fault tolerance** | Single point of failure | Redundant |
| **Cost curve** | Exponential | Linear |
| **When to use** | Simple apps, databases | Most production systems |

**Stateless services** enable horizontal scaling trivially. **Stateful services** (databases, caches) require sharding, replication, or consistent hashing.

### Availability

Measured in "nines":

| SLA | Downtime/Year | Downtime/Month |
|-----|---------------|----------------|
| 99% | 3.65 days | 7.31 hours |
| 99.9% | 8.76 hours | 43.8 minutes |
| 99.99% | 52.6 minutes | 4.38 minutes |
| 99.999% | 5.26 minutes | 26.3 seconds |

**Availability formula for serial components:**

```
A_system = A_component1 × A_component2 × ... × A_componentN

Example: 2 nines components in series = 99% × 99% = 98.01% (LESS available)
```

**Availability formula for parallel (redundant) components:**

```
A_system = 1 - (1 - A_component)^N

Example: 2 nines components in parallel = 1 - (1-0.99)^2 = 99.99% (MORE available)
```

### Reliability vs Availability vs Fault Tolerance

| Property | Definition | Example |
|----------|-----------|---------|
| **Reliability** | System works correctly over time | A database that never loses data |
| **Availability** | System is accessible when needed | A website with 99.99% uptime |
| **Fault Tolerance** | System works despite failures | A service that survives a node crash |

### Durability

Data survives hardware failures. The metric is **Mean Time To Data Loss
(MTTDL)** — how long until you lose a piece of data you cannot recover.

With N-way replication you only lose data if **all N copies fail before any of
them is rebuilt**. So the two levers are the failure rate and the *repair* time,
and replication helps super-linearly — not linearly.

```
Step 1: How often does SOME drive in the fleet fail?

  MTTF_fleet = MTTF_drive / drive_count
             = 1,000,000 h / 1,000 drives
             = 1,000 h  (≈ one failure every 6 weeks)

Step 2: For 3-way replication, data is lost only if two MORE copies die
        inside the repair window (MTTR). Roughly:

  MTTDL ≈ MTTF_drive³ / (drive_count × (N-1)! × MTTR² × ... )

  With MTTF = 1e6 h, 1,000 drives, MTTR = 10 h:
  MTTDL ≈ (1e6)³ / (1000 × 2 × 10²)  ≈ 5e12 h  (astronomically safe)
```

**Two takeaways that matter more than the formula:**

| Lever | Effect |
|-------|--------|
| **More replicas** | Each extra copy multiplies MTTDL by roughly `MTTF/MTTR` — a huge factor |
| **Faster repair** | Halving MTTR raises 3-way MTTDL ~4× (it enters squared) |

**The trap:** the naive formula `MTTDL = MTTF × replicas` is wrong in both
magnitude and shape. It suggests replication helps *linearly* and ignores
repair time entirely — yet repair time is the variable operators actually
control. It also assumes failures are independent, which they are not: a bad
batch, a shared power rail, or a rack switch takes out correlated copies.
This is why S3-class systems quote 11 nines *and* spread replicas across
availability zones.

---

## Back-of-the-Envelope Estimation

Every system design interview starts here. You must convert vague requirements into concrete numbers.

### The Key Numbers to Memorize

| Resource | Typical Value |
|----------|---------------|
| SSD random read | ~0.1ms |
| HDD random read | ~10ms |
| Memory random read | ~100ns |
| Network round trip (same region) | ~0.5ms |
| Network round trip (cross-continent) | ~150ms |
| Redis GET | ~0.5ms |
| MySQL simple query | ~1-5ms |
| LLM inference (per token) | ~20-50ms |

### Estimation Walkthrough: URL Shortener

**Requirement**: "Build a URL shortener that handles 100M URLs created per month"

**Step 1: QPS Estimation**

```
Write QPS: 100M / 30 days / 24 hours / 3600 seconds
         = 100,000,000 / 2,592,000
         ≈ 38 writes/sec

Read QPS (assume 100:1 read-to-write ratio):
         = 38 × 100
         ≈ 3,800 reads/sec
```

**Step 2: Storage Estimation**

```
short_code:  7 bytes   (base62)
long_url:    ~500 bytes (the actual URL — the bulk of every row)
metadata:    ~100 bytes (user_id, timestamps, click count)
Total/URL:   ~607 bytes

Per month:   100M × 607 bytes ≈ 60.7 GB
Per year:    ≈ 728 GB
5 years:     ≈ 3.6 TB  → still one well-provisioned server
```

> **The most common estimation mistake** is budgeting for the short code and
> forgetting the long URL. The short code is 7 bytes; the URL you are storing
> it *for* is ~500. Get that backwards and you'll under-size storage by ~6×.

**Step 3: Bandwidth Estimation**

```
Read bandwidth:  3,800 QPS × 607 bytes ≈ 2.3 MB/s ≈ 18 Mbps
Write bandwidth:    38 QPS × 607 bytes ≈  23 KB/s

Well within a single server's capacity — this system is not
bandwidth-constrained, it is latency- and lookup-constrained.
```

**Step 4: Cache Estimation (for hot URLs)**

Cache sizing is about the **working set of distinct keys**, not the request
count. A URL fetched a million times still occupies one cache entry.

```
Pareto: 20% of URLs receive ~80% of traffic.

Distinct URLs in the hot set (assume ~1 month of links stay hot):
  20% × 100M = 20M distinct URLs

Memory needed:
  20M × 607 bytes ≈ 12 GB  → one Redis node, or two for headroom

Expected hit ratio ≈ 80%, which cuts DB reads from 3,800 to ~760 QPS.
```

> **Why not "20% of daily reads"?** Multiplying 66M *reads* by the row size
> counts the same hot URL thousands of times and inflates the estimate. Size
> caches by **distinct keys × entry size**, then use the request distribution
> to predict the *hit ratio* — two different questions.

---

## The 9-Step Framework

This framework works for **any** system design problem, from URL shorteners to LLM inference platforms.

```
 Step 1          Step 2          Step 3          Step 4
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Clarify  │   │ Estimate │   │ Define   │   │ Design   │
│ Require- │──▶│ Capacity │──▶│ API      │──▶│ Data     │
│ ments    │   │ (QPS,    │   │ (REST    │   │ Model    │
│          │   │  Storage)│   │ endpoints)│  │ (tables, │
│ 2-3 min  │   │ 3-5 min  │   │ 2-3 min  │   │  schema) │
│          │   │          │   │          │   │ 3-5 min  │
└──────────┘   └──────────┘   └──────────┘   └────┬─────┘
                                                   │
 Step 9          Step 8          Step 7          Step 6│ Step 5
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────▼───┐
│ Handle   │   │ Address  │   │ Discuss  │   │ Sketch     │
│ Follow-  │◀──│ Bottle-  │◀──│ Trade-   │◀──│ High-Level │
│ ups      │   │ necks    │   │ offs     │   │ Design     │
│ 2-3 min  │   │ 3 min    │   │ 2 min    │   │ 5 min      │
└──────────┘   └──────────┘   └──────────┘   └────────────┘
                                    ▲
                          Step 6: deep dive on 2-3
                          components (10-15 min)

  Budget check: 3+5+3+5+5+15+2+3+3 ≈ 44 min — one 45-minute interview.
```

### Step 1: Clarify Requirements (2-3 min)

Ask questions to scope the problem. Always distinguish:

| Category | Questions |
|----------|-----------|
| **Functional** | What features? What's in scope vs out? |
| **Scale** | How many users? How many requests? Read/write ratio? |
| **Latency** | Real-time or batch? What's acceptable response time? |
| **Availability** | 99.9% or 99.999%? Can we tolerate brief outages? |
| **Consistency** | Strong or eventual? Can users see stale data? |

**Example for URL Shortener:**
- Functional: Create short URL, redirect, custom aliases, expiration, click analytics
- Scale: 100M URLs/month, 100:1 read/write ratio
- Latency: <100ms for redirect
- Availability: 99.99%
- Consistency: Eventual OK for analytics, strong for URL creation

### Step 2: Estimate Capacity (3-5 min)

Do the math. Convert requirements to:
- **QPS** (queries per second) — average and peak
- **Storage** — total data volume
- **Bandwidth** — data transfer rate
- **Memory** — caching needs

**Peak vs average**: Multiply by 2-3x for peak traffic.

### Step 3: Define API (2-3 min)

Design 3-5 core endpoints:

```
POST /urls
  Body: { "long_url": "...", "custom_alias": "...", "expires_at": "..." }
  Response: { "short_url": "abc123", "created_at": "..." }

GET /:short_url
  Response: 301 redirect to long_url (or 302 for analytics)

DELETE /urls/:short_url
  Response: 204 No Content

GET /urls/:short_url/stats
  Response: { "clicks": 1234, "last_accessed": "..." }
```

### Step 4: Design Data Model (3-5 min)

```sql
-- Core table
CREATE TABLE urls (
    id          BIGINT PRIMARY KEY,
    short_code  VARCHAR(10) UNIQUE NOT NULL,
    long_url    TEXT NOT NULL,
    user_id     BIGINT,
    created_at  TIMESTAMP,
    expires_at  TIMESTAMP,
    click_count BIGINT DEFAULT 0
);

-- Indexes
CREATE INDEX idx_short_code ON urls(short_code);
CREATE INDEX idx_user_id ON urls(user_id);
```

### Step 5: Sketch High-Level Design (5 min)

```
Client → Load Balancer → API Servers → Cache (Redis) → Database (MySQL)
                                     → Message Queue → Analytics DB
```

### Step 6: Deep Dive (10-15 min)

Pick 2-3 components to design in detail. Common deep-dive topics:
- ID generation strategy (base62, Snowflake, UUID trade-offs)
- Caching strategy (which URLs to cache, invalidation)
- Database sharding (how to partition by short_code)

### Step 7: Discuss Trade-offs Explicitly

Always say: "I'd use X because Y, but the trade-off is Z."

### Step 8: Address Scalability Bottlenecks

Ask yourself: "What breaks at 10x traffic?"

### Step 9: Handle Follow-ups

Be ready for:
- "How do you handle URL expiration?"
- "How do you prevent abuse?"
- "How do you handle analytics at scale?"

---

## CAP Theorem

In a distributed system, you can only guarantee **two** of three properties:

```
                    Consistency (C)
                         ▲
                        / \
                       /   \
          pick C + P  /     \  pick C + A
            = CP     /       \    = CA
       (ZooKeeper)  /         \  (single-node
                   /           \   Postgres)
                  /             \
                 ▼───────────────▼
   Availability (A)               Partition tolerance (P)
                  \             /
                   pick A + P
                     = AP
                  (Cassandra, DNS)

  Each EDGE is a viable system; the CENTER (all three) is unreachable.
```

| System Type | Guarantee | Real Example |
|------------|-----------|--------------|
| **CP** | Consistent + Partition-tolerant | ZooKeeper, HBase, MongoDB (default) |
| **AP** | Available + Partition-tolerant | Cassandra, DynamoDB, DNS |
| **CA** | Consistent + Available (no partitions) | Single-node PostgreSQL |

**In practice, you always need P** (network partitions happen), so the real choice is:

- **CP**: Sacrifice availability during partitions (reject requests)
- **AP**: Sacrifice consistency during partitions (serve stale data)

**Real-world example**: When a Cassandra node goes down, other nodes continue serving (AP). When a ZooKeeper node goes down, the cluster may reject writes until quorum is restored (CP).

---

## Consistency Models

Not all "consistent" systems are the same. The spectrum from strongest to weakest:

```
Strongest ◄──────────────────────────────────────────────► Weakest

     ▼            ▼            ▼            ▼            ▼
  Strict      Lineariz-      Causal     Read-your-    Eventual
Serializable   able        Consistency    Writes    Consistency

     │            │            │            │            │
  Multi-object  Single-object  Cause-      You see    Replicas
  txns, in      ops appear    effect      your own    converge
  real-time     atomic and    order       writes      eventually
  order         globally      preserved
                ordered

  Strict serializability = serializability + real-time order.
  It is linearizability generalised from single objects to transactions,
  so it is STRICTLY STRONGER than linearizability — not weaker.
```

| Model | Guarantee | Scope | Use Case |
|-------|-----------|-------|----------|
| **Strict Serializable** | Serializable **and** respects real-time order | Multi-object transactions | Banking, inventory, Spanner/CockroachDB |
| **Linearizable** | Every op appears atomic at a single point in time | One object at a time | Leader election, distributed locks, etcd |
| **Serializable** | Some serial order exists — but it need not match wall clock | Multi-object transactions | Classic SQL `SERIALIZABLE` isolation |
| **Causal** | Preserves cause-effect ordering; concurrent ops may differ per replica | Related operations | Collaborative editing, social feeds |
| **Read-your-writes** | A session observes its own prior writes | One session | Profile updates, "post then view" |
| **Eventual** | Replicas converge if writes stop | Whole system | DNS, like counts, CDN caches |

> **The distinction people get wrong:** serializability is about *some* valid
> serial order; linearizability is about the *real-time* order of single-object
> operations. Neither implies the other. Strict serializability is what you get
> when you demand both — which is why it is the most expensive and why systems
> like Spanner need synchronised clocks (TrueTime) to offer it.

---

## Case Study: Designing a URL Shortener

Let's walk through the 9-step framework for this classic problem.

### Step 1: Clarify Requirements

**In scope**: Create short URL, redirect, custom aliases, expiration
**Out of scope**: User authentication, analytics dashboard
**Scale**: 100M new URLs/month, 100:1 read:write
**Latency**: <100ms redirect
**Availability**: 99.99%

### Step 2: Estimate Capacity

```
Write QPS:  100M / 2.6M seconds ≈ 38 writes/sec   (peak ≈ 114)
Read QPS:   38 × 100 = 3,800 reads/sec            (peak ≈ 11,400)
Storage:    100M × 607 bytes ≈ 60.7 GB/month ≈ 728 GB/year
Cache:      20M distinct hot URLs × 607 bytes ≈ 12 GB
```

### Step 3: Define API

```
POST /api/urls   → Create short URL
GET  /:code      → Redirect to long URL
```

### Step 4: Design Data Model

```
urls table:
  short_code (PK, VARCHAR(7))
  long_url   (TEXT)
  created_at (TIMESTAMP)
  expires_at (TIMESTAMP, nullable)
```

### Step 5: High-Level Design

```
                    ┌──────────────┐
                    │   Client     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Load Balancer│
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │ API Server│ │ API    │ │ API      │
        │     1     │ │Server 2│ │ Server 3 │
        └─────┬─────┘ └───┬────┘ └────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │   Redis   │ │ MySQL  │ │ Kafka    │
        │  (cache)  │ │  (DB)  │ │(analytics)│
        └───────────┘ └────────┘ └──────────┘
```

### Step 6: Deep Dive — ID Generation

**Option A: Base62 Counter**
- Sequential counter → base62 encode (a-z, A-Z, 0-9)
- Pros: Short, predictable, no collisions
- Cons: Predictable (security risk), single point of failure for counter

**Option B: MD5/SHA256 Hash**
- Hash the long URL → take first 7 chars → base62
- Pros: Deterministic (same URL → same short code)
- Cons: Collisions possible, need to check and retry

**Option C: Snowflake-like Distributed ID**
- Pre-generate unique IDs across multiple servers
- Pros: No coordination, highly available
- Cons: Slightly longer codes, need ID generation service

**Recommended**: Pre-generate a batch of unique IDs (e.g., 1000 at a time per server) using a counter with base62 encoding. This avoids database contention while keeping codes short.

### Step 7: Trade-offs

| Decision | Choice | Trade-off |
|----------|--------|-----------|
| 301 vs 302 redirect | 302 | 301 is cached by browsers, so repeat clicks never reach you — cheap, but you lose analytics and can't revoke a link. 302 keeps every click observable at the cost of serving all of them. |
| Cache expiration | 24h TTL | Stale data possible but fast |
| Database choice | MySQL + Redis | Strong consistency + fast reads |
| Sharding | Hash on short_code | Even distribution, range queries impossible |

> **Why "302 adds a hop" is wrong:** both 301 and 302 are exactly one round trip
> on a cold client. The difference is *caching*. A browser that cached a 301 skips
> your server entirely on subsequent clicks — which is why 301 is faster for users
> and why it makes click analytics and link revocation impossible.

### Step 8: Scalability Bottlenecks

At 10x traffic (380 writes/sec, 38K reads/sec):
- **Cache hit ratio**: Target 80%+ to keep DB load manageable
- **Database writes**: Consider write-ahead buffer or batch inserts
- **Single Redis**: May need to shard across multiple Redis instances

### Step 9: Follow-up Questions

- **URL expiration**: Background job scans for expired URLs, moves to archive table
- **Custom aliases**: Check uniqueness before inserting, reject if taken
- **Abuse prevention**: Rate limiting per IP, CAPTCHA for bulk creation

---

## Trade-off Thinking

Every design decision involves trade-offs. The best engineers make these **explicit**.

### Common Trade-offs

| Dimension A | Dimension B | When to Choose A |
|-------------|-------------|------------------|
| Consistency | Availability | Financial, inventory |
| Latency | Durability | Real-time gaming, analytics |
| Simplicity | Flexibility | MVP, rapidly changing requirements |
| Cost | Performance | Early stage, budget constrained |
| Read optimization | Write optimization | Read-heavy workloads |
| Normalization | Denormalization | Complex queries vs simple reads |

### The Art of Trade-off Discussion

Never say "I'd use a relational database." Say:

> "I'd use PostgreSQL because we need strong consistency for the payment system, and the query patterns are relational. The trade-off is that horizontal scaling is harder, but at our current scale (10K QPS), a single primary with read replicas is sufficient. If we grow to 100K QPS, we'd consider sharding or migrating to a distributed SQL system like CockroachDB."

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Designing Data-Intensive Applications (Ch. 1-2) | Book | Foundational concepts |
| System Design Interview (Ch. 1) | Book | 9-step framework |
| ByteByteGo | Blog/Video | Visual system design |
| System Design Primer (GitHub) | Open Source | Comprehensive overview |
| High Scalability | Blog | Real-world architecture case studies |

---

## Practice Exercise

**20-minute design**: Using the 9-step framework, design a URL shortener.

1. (2 min) Clarify requirements — what's in scope?
2. (3 min) Estimate capacity — QPS, storage, bandwidth
3. (3 min) Design API — 3-5 endpoints
4. (2 min) Design data model — tables, indexes
5. (5 min) Sketch architecture — services, data stores
6. (5 min) Deep dive — ID generation strategy

**Follow-up**: At what scale do you need to shard the database? What's the caching strategy?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Jumping to architecture before requirements** | You might solve the wrong problem | Spend 2-3 min clarifying requirements first |
| **Ignoring the read/write ratio** | Caches, databases, and scaling depend on it | Always estimate read vs write QPS |
| **Saying "I'd use MySQL" without justification** | Every choice has trade-offs | Say "I'd use X because Y, but the trade-off is Z" |
| **Forgetting about availability** | 99.9% vs 99.99% changes everything | Ask: "What availability do we need?" |
| **Over-engineering at small scale** | Adds complexity without benefit | Design for 10x current, not 1000x |

---

## Discussion Questions

1. You're designing a URL shortener. Your manager says "we need 99.999% availability." What does this imply about your architecture? What trade-offs does it force?

   **Model answer**: 99.999% = 5.26 minutes downtime per year. This requires: multi-region deployment, automatic failover, no single point of failure, redundant everything (databases, caches, load balancers). Trade-offs: higher cost (3x+ more infrastructure), increased complexity (data consistency across regions), slower development (every component needs redundancy).

2. Why can't you use a single PostgreSQL database for a social media platform with 1B users? At what point does a single database become insufficient, and what are your options?

   **Model answer**: A single PostgreSQL handles ~10K QPS reads, ~1K QPS writes. With 1B users, even 1% daily active = 10M users, each making 10 requests = 100M queries/day = ~1K QPS average, but peak could be 10K+. At this scale: add read replicas (vertical scaling), then shard by user_id (horizontal scaling), or migrate to distributed SQL (CockroachDB).

3. Explain the difference between horizontal and vertical scaling to a junior engineer. When would you choose one over the other?

   **Model answer**: Vertical = bigger server (more CPU/RAM). Simple, but has hardware ceiling and single point of failure. Horizontal = more servers. Requires load balancing and state management, but nearly infinite scale. Choose vertical for simple apps, databases (until sharding needed). Choose horizontal for stateless services, high availability requirements.

4. You're building a news feed system. Users post content, followers see it. The requirement is "users should see new posts within 5 seconds." What consistency model do you choose, and why?

   **Model answer**: Read-your-writes consistency for the author (they see their own post immediately), eventual consistency for followers (posts appear within 5 seconds). Why: Strong consistency is too expensive for fan-out. Eventual consistency with bounded staleness (<5 seconds) is the standard for social feeds.

5. Walk through the CAP theorem for a payment processing system. Is it CP or AP? What happens during a network partition?

   **Model answer**: Payment systems are CP (Consistent + Partition-tolerant). During a network partition, the system rejects requests rather than process payments with stale data. Why: A double charge (inconsistency) is worse than a temporary outage. Users can retry; lost money is hard to recover.

---

**Previous**: [Course Home](../README.md)
**Next**: [Databases and Storage](../02-databases-storage/README.md) — choosing the right data layer for your system.
