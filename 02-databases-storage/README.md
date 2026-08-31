# Module 02: Databases and Storage

> **Choose the right data layer for your system.** The database choice is often the hardest decision in system design — it's expensive to change later and affects everything from query patterns to scaling strategy.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 01 | System Design Fundamentals | [../01-fundamentals/](../01-fundamentals/) |
| **Module 02** | **Databases and Storage** | **(current)** |
| Module 03 | Caching Strategies | [../03-caching/](../03-caching/) |

---

## Learning Objectives

- Choose between SQL and NoSQL with a clear decision framework
- Understand sharding, replication, and partitioning strategies
- Reason about ACID vs BASE trade-offs
- Evaluate NewSQL options for modern applications
- Design data models that scale

---

## Table of Contents

1. [SQL vs NoSQL: The Decision Matrix](#sql-vs-nosql-the-decision-matrix)
2. [Indexing Strategies](#indexing-strategies)
3. [Sharding Strategies](#sharding-strategies)
4. [Replication Strategies](#replication-strategies)
5. [ACID vs BASE](#acid-vs-base)
6. [NewSQL: When You Need Both](#newsql-when-you-need-both)
7. [Case Study: Instagram's Data Layer](#case-study-instagrams-data-layer)
8. [Data Modeling Patterns](#data-modeling-patterns)
9. [Key References](#key-references)
10. [Practice Exercise](#practice-exercise)
11. [Common Mistakes](#common-mistakes)
12. [Discussion Questions](#discussion-questions)

---

## SQL vs NoSQL: The Decision Matrix

The choice isn't "SQL is old, NoSQL is new." It's about **what your data looks like and how you query it**.

```
              Do you need multi-row ACID transactions?
                       │
            ┌──── Yes ─┴─ No ─────────────┐
            │                             │
     ┌──────▼───────┐        Is your data relational,
     │     SQL      │        with queries that JOIN?
     │  PostgreSQL  │                     │
     │    MySQL     │          ┌─── Yes ──┴── No ───┐
     │ CockroachDB  │          │                    │
     └──────────────┘   ┌──────▼──────┐      ┌──────▼──────┐
                        │  Document   │      │  Key-Value  │
                        │   MongoDB   │      │  DynamoDB   │
                        │  Firestore  │      │    Redis    │
                        └─────────────┘      └─────────────┘

  Caveat: this tree is a starting point, not a verdict. MongoDB has had
  multi-document transactions since 4.0 and DynamoDB has TransactWriteItems,
  so "needs ACID" no longer rules out every NoSQL store. Decide on your
  actual query patterns and consistency needs, not the SQL/NoSQL label.
```

### Comparison Table

| Factor | SQL (PostgreSQL, MySQL) | Document (MongoDB) | Key-Value (DynamoDB, Redis) | Wide-Column (Cassandra) |
|--------|------------------------|-------------------|----------------------------|------------------------|
| **Schema** | Rigid, predefined | Flexible, JSON | Minimal (key→value) | Column families |
| **ACID** | Full support | Limited (transactions since 4.0) | None (eventual) | Light-weight transactions |
| **Scaling** | Vertical, plus read replicas; sharding is manual | Horizontal (sharding) | Horizontal (built-in) | Horizontal (ring topology) |
| **Query power** | JOINs, aggregations, subqueries | Embedding, limited joins | Get/Set only | Range scans on partition keys |
| **Best for** | Financial, inventory, relationships | Content management, catalogs | Session data, caching, leaderboards | Time-series, IoT, event logs |
| **Real systems** | Instagram (MySQL), Stripe | Uber (Schemaless), eBay | Twitter (Redis), Facebook (Memcached) | Netflix (Cassandra), Apple |

### When to Use What

| Use Case | Recommendation | Why |
|----------|---------------|-----|
| E-commerce orders | PostgreSQL | ACID for payments, relational integrity |
| Social media feed | Cassandra or MongoDB | High write throughput, flexible schema |
| Session store | Redis | Sub-millisecond reads, TTL support |
| User profiles | PostgreSQL or MongoDB | Depends on schema flexibility needed |
| Real-time analytics | ClickHouse or Druid | Columnar storage, fast aggregations |
| Chat messages | Cassandra | High write throughput, time-series data |
| Product catalog | MongoDB | Flexible attributes per product category |
| Financial ledger | PostgreSQL or CockroachDB | Strong consistency, ACID compliance |

---

## Indexing Strategies

Indexes speed up reads at the cost of write performance and storage.

### B-Tree Index (Most Common)

```
           ┌──────────────┐
           │    30, 60    │
           └──┬───────┬───┘
          ┌───▼──┐ ┌──▼────┐
          │10,20 │ │40, 50 │
          └┬──┬──┘ └┬───┬──┘
           │  │     │   │
          [1][2]  [3] [4][5]

  Range queries:  WHERE age BETWEEN 20 AND 50  ✓ fast
  Equality:       WHERE id = 42               ✓ fast
  Prefix:         WHERE name LIKE 'John%'     ✓ fast
  Wildcard:       WHERE name LIKE '%ohn'      ✗ full scan
```

### Hash Index

```
  hash(key) → bucket → value

  Equality:  WHERE id = 42    ✓ O(1)
  Range:     WHERE id > 42    ✗ full scan
```

### Composite Index

```
  CREATE INDEX idx_user_date ON orders(user_id, order_date);

  ✓ WHERE user_id = 1 AND order_date > '2024-01-01'  (uses index)
  ✓ WHERE user_id = 1                                 (uses index)
  ✗ WHERE order_date > '2024-01-01'                   (ignores index)

  Rule: Put the most selective/equality column first.
```

### Index Trade-offs

| Factor | Effect of Indexing |
|--------|-------------------|
| **Read speed** | Dramatically faster (O(log n) vs O(n)) |
| **Write speed** | Slower (must update index on every write) |
| **Storage** | 10-30% more disk space |
| **Memory** | Indexes must fit in memory for best performance |

---

## Sharding Strategies

Sharding splits data across multiple database instances. Each shard holds a subset of the data.

### Hash-Based Sharding

```
  shard_id = hash(key) % num_shards

  Example with 4 shards:
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ Shard 0  │  │ Shard 1  │  │ Shard 2  │  │ Shard 3  │
  │ user 0,4 │  │ user 1,5 │  │ user 2,6 │  │ user 3,7 │
  │ user 8,12│  │ user 9,13│  │ user 10  │  │ user 11  │
  └──────────┘  └──────────┘  └──────────┘  └──────────┘

  ✓ Even distribution
  ✓ Simple implementation
  ✗ Range queries require scanning all shards
  ✗ Adding shards requires resharding (consistent hashing helps)
```

### Range-Based Sharding

```
  shard_id = range(key)

  Example:
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │  Shard A     │  │  Shard B     │  │  Shard C     │
  │  user 1-1000 │  │  user 1001-  │  │  user 2001-  │
  │              │  │       2000   │  │       3000   │
  └──────────────┘  └──────────────┘  └──────────────┘

  ✓ Range queries are fast (single shard)
  ✓ Easy to understand
  ✗ Hotspots (new users all go to Shard C)
  ✗ Uneven distribution over time
```

### Geo-Based Sharding

```
  shard_id = region(user_location)

  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ US East  │  │ EU West  │  │ Asia Pac │
  │ shard    │  │ shard    │  │ shard    │
  └──────────┘  └──────────┘  └──────────┘

  ✓ Low latency (data near user)
  ✓ Compliance (data residency laws)
  ✗ Cross-region queries are expensive
  ✗ Uneven distribution (more users in US/EU)
```

### Consistent Hashing

When you add or remove a shard, only ~1/N keys need to move (vs all keys with modulo hashing).

```
  Hash ring, 4 nodes. Positions are hash(node_id) mod 2^32.

              0 / 2^32
                  ▲
          ╭───── Node A ─────╮
         ╱                    ╲
        ╱    k1 ●              ╲
   Node D           ⟳          Node B
        ╲              ● k2    ╱
         ╲                    ╱
          ╰───── Node C ─────╯

              clockwise ⟳

  Each key walks CLOCKWISE to the first node it meets:
    k1 sits between A and B  →  owned by Node B
    k2 sits between B and C  →  owned by Node C

  Adding node E between A and B:
  - Only keys that were on B and fall between A and E move to E
  - All other keys stay in place — that is the whole point

  Contrast with `hash(key) % N`: changing N from 4 to 5 remaps roughly
  4/5 of ALL keys. On a cache that means a near-total miss storm; on a
  sharded database it means moving most of your data.

  In practice each physical node is placed at many points on the ring
  ("virtual nodes", typically 100-256). Without them, four nodes land at
  four arbitrary positions and the arcs between them differ wildly in
  size, so load is uneven no matter how good the hash is.
```

---

## Replication Strategies

### Leader-Follower (Primary-Replica)

```
  ┌───────────┐
  │  Leader   │ ◄─── All writes
  │ (Primary) │
  └─────┬─────┘
        │ replication log
   ┌────┼────┐
   │    │    │
   ▼    ▼    ▼
┌────┐┌────┐┌────┐
│ F1 ││ F2 ││ F3 │ ◄─── Reads (can scale horizontally)
└────┘└────┘└────┘

  ✓ Read scaling (multiple replicas)
  ✓ Simple failover (promote a replica)
  ✗ Write bottleneck (single leader)
  ✗ Replication lag (eventual consistency)
  ✗ Failover complexity (split-brain risk)
```

**Used by**: PostgreSQL, MySQL, MongoDB (replica sets)

### Multi-Leader

```
  ┌──────────┐     ┌──────────┐
  │ Leader 1 │◄───▶│ Leader 2 │   Writes to both
  │ (US East)│     │ (EU West)│
  └─────┬────┘     └─────┬────┘
        │                │
        ▼                ▼
  ┌──────────┐     ┌──────────┐
  │ Follower │     │ Follower │
  └──────────┘     └──────────┘

  ✓ Multi-region writes (low latency globally)
  ✓ Continued writes during partition
  ✗ Conflict resolution (last-write-wins, CRDTs)
  ✗ Complex replication logic
```

**Used by**: MySQL Group Replication (multi-primary mode), CouchDB, BDR for
PostgreSQL, and offline-first mobile sync (each device is effectively a leader).

> **CockroachDB and Spanner are *not* multi-leader.** They shard data into
> ranges and run a **Raft/Paxos group per range**, each with a single elected
> leader. The cluster accepts writes in every region, but any given *row* has
> exactly one leader at a time — which is precisely how they avoid the
> write-conflict resolution that real multi-leader systems must handle. They
> are best understood as **many single-leader groups**, not multi-leader.

### Leaderless (Dynamo-Style)

```
  ┌─────┐  ┌─────┐  ┌─────┐
  │Node1│  │Node2│  │Node3│
  └──┬──┘  └──┬──┘  └──┬──┘
     │        │        │
     └────────┼────────┘
              │
           Client

  Client sends write to ALL nodes (or W of N)
  Client reads from ALL nodes (or R of N)
  Quorum: W + R > N ensures consistency
```

**Used by**: Cassandra, DynamoDB, Riak

### Replication Trade-offs

| Strategy | Write Throughput | Read Throughput | Consistency | Complexity |
|----------|-----------------|-----------------|-------------|------------|
| Leader-Follower | Low (single leader) | High (multiple readers) | Eventual | Low |
| Multi-Leader | High (multiple writers) | High | Eventual (conflict-prone) | High |
| Leaderless | High | High | Tunable (quorum) | High |

---

## ACID vs BASE

### ACID (Traditional SQL)

```
Atomicity    — All or nothing (a transaction either fully commits
               or fully rolls back — never halfway)
Consistency  — Data always valid (constraints always enforced)
Isolation    — Concurrent transactions don't interfere
Durability   — Committed data survives crashes
```

> **Note on the "C" in ACID:** it means *integrity constraints hold*, which is
> not the same "consistency" as in CAP (where it means *all replicas agree*).
> Two different words spelled the same way — a frequent source of confusion.

**When ACID matters**: Banking, payments, inventory, booking systems

### BASE (Distributed NoSQL)

```
Basically Available — System always responds (possibly with stale data)
Soft state         — State may change over time (without input)
Eventual consistency — All replicas converge eventually
```

**When BASE is OK**: Social media likes, analytics, caching, read-heavy content

### The Trade-off

```
  Strong Consistency ◄──────────────► High Availability
            │                              │
     Latency: Higher                 Latency: Lower
     Throughput: Lower               Throughput: Higher
     Use case: Payments              Use case: Social feeds
```

---

## NewSQL: When You Need Both

NewSQL systems promise SQL interfaces with horizontal scalability.

| System | Key Innovation | Use Case |
|--------|---------------|----------|
| **CockroachDB** | Distributed SQL, Geo-partitioning | Global applications needing ACID |
| **Google Spanner** | TrueTime (GPS + atomic clocks) | Global consistency with low latency |
| **TiDB** | MySQL-compatible, HTAP | MySQL apps that need horizontal scaling |
| **YugabyteDB** | PostgreSQL-compatible, distributed | PostgreSQL apps needing scale |

---

## Case Study: Instagram's Data Layer

Instagram serves 2B+ users with a complex data architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    Instagram Stack                      │
├─────────────────────────────────────────────────────────┤
│  Application Layer                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐       │
│  │ Django   │  │ Celery   │  │ Custom Services  │       │
│  │ (Python) │  │ (async)  │  │ (Go, C++)        │       │
│  └──────────┘  └──────────┘  └──────────────────┘       │
├─────────────────────────────────────────────────────────┤
│  Data Layer                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐       │
│  │  MySQL   │  │  Redis   │  │  Cassandra       │       │
│  │ (users,  │  │ (cache,  │  │ (time-series,    │       │
│  │  posts,  │  │  sessions│  │  feeds, events)  │       │
│  │  follows)│  │  counts) │  │                  │       │
│  └──────────┘  └──────────┘  └──────────────────┘       │
│  ┌──────────┐  ┌──────────┐                             │
│  │memcached │  │ Elastic- │                             │
│  │(objects) │  │ search   │                             │
│  └──────────┘  └──────────┘                             │
└─────────────────────────────────────────────────────────┘
```

**Why this mix?**

| Store | Purpose | Why This Choice |
|-------|---------|----------------|
| **MySQL** | Users, posts, follows, comments | ACID for core data, relational queries (JOINs for feeds) |
| **Redis** | Session cache, counters, feed sorting | Sub-millisecond reads, atomic counters, sorted sets |
| **Cassandra** | Time-series data, activity feeds | Write-optimized, linearly scalable, no single point of failure |
| **Memcached** | Object caching (photos, profiles) | Simple key-value, high throughput |
| **Elasticsearch** | Search, hashtag search, user search | Full-text search, faceted queries |

**Key insight**: Instagram doesn't use one database — they use the **right database for each workload**.

---

## Data Modeling Patterns

### Denormalization for Read Performance

```
NORMALIZED (3NF)                    DENORMALIZED
┌─────────┐  ┌─────────┐          ┌───────────────────────┐
│ users   │  │ posts   │          │ user_posts (wide)     │
│─────────│  │─────────│          │────────────────────── │
│ id      │  │ id      │          │ user_id               │
│ name    │  │ user_id │──FK──▶   │ user_name             │
│ email   │  │ content │          │ user_avatar_url       │
└─────────┘  │ created │          │ post_id               │
             └─────────┘          │ post_content          │
  ✓ No duplication                │ post_created          │
  ✓ JOINs needed                  └───────────────────────┘
                                  ✓ No JOINs needed
                                  ✓ Fast reads
                                  ✗ Data duplication
                                  ✗ Write amplification
```

**When to denormalize**: Read-heavy workloads, when JOINs are too expensive at scale, when you need sub-millisecond reads.

### Materialized Views

Pre-computed query results stored as tables. Updated periodically or on write.

```sql
CREATE MATERIALIZED VIEW user_feed AS
SELECT u.name, p.content, p.created_at
FROM posts p
JOIN users u ON p.user_id = u.id
ORDER BY p.created_at DESC;

-- Refresh periodically
REFRESH MATERIALIZED VIEW CONCURRENTLY user_feed;
```

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Designing Data-Intensive Applications (Ch. 5-9) | Book | Database internals, replication, partitioning |
| Database Internals (Alex Petrov) | Book | Storage engines, distributed database internals |
| PostgreSQL Documentation | Docs | Indexing, query optimization |
| Cassandra Documentation | Docs | Wide-column data modeling |
| DynamoDB Developer Guide | Docs | Key-value design patterns |

---

## Practice Exercise

**20-minute design**: Choose the right database for these scenarios:

1. **Social media platform**: User profiles, posts, followers. Write-heavy, eventual consistency OK. Which database? Why?
2. **E-commerce inventory**: Product stock counts. Strong consistency required, high read throughput. Which database? Why?
3. **Session store**: User login sessions. Sub-millisecond reads, TTL support. Which database? Why?
4. **Time-series metrics**: Server metrics (CPU, memory) at 1-second intervals. Write-heavy, range queries. Which database? Why?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **"NoSQL doesn't do transactions"** | MongoDB has had multi-document ACID since 4.0; DynamoDB has `TransactWriteItems` | Decide on query patterns and consistency needs, not the SQL/NoSQL label |
| **Calling Spanner/CockroachDB multi-leader** | They run a Raft group *per range*, each with one leader — that's how they avoid write conflicts | Reserve "multi-leader" for systems that genuinely need conflict resolution |
| **Sharding before you need to** | Cross-shard JOINs and transactions disappear; resharding is a migration project | Exhaust read replicas and vertical scaling first — most workloads never need shards |
| **Choosing a shard key by convenience** | `created_at` sends every new write to one shard; low-cardinality keys create permanent hotspots | Shard on something high-cardinality and evenly accessed, usually a tenant or user ID |
| **Adding an index per query** | Every index taxes all writes and competes for buffer-pool memory | Design composite indexes for query *patterns*; verify with `EXPLAIN` before adding |
| **Composite index in the wrong order** | `(user_id, date)` can't serve a `date`-only filter — an index is usable left-to-right only | Put equality columns first, range columns last |
| **Reading from a replica right after writing** | Replication lag means the write may not be visible yet | Route read-your-writes to the primary, or pin the session until the replica catches up |
| **Confusing the two "consistency"s** | ACID's C means constraints hold; CAP's C means replicas agree | Say "integrity constraints" or "linearizable" and skip the ambiguous word |

---

## Discussion Questions

1. You're building an e-commerce platform. Products have varying attributes (electronics have wattage, clothing has sizes). Would you use SQL or NoSQL for the product catalog? Why?

2. Explain the trade-off between leader-follower and leaderless replication to a non-technical stakeholder. When would you recommend each?

3. You're designing a chat application. Messages need to be stored and retrieved in chronological order. Which database would you choose, and how would you shard it?

4. What is consistent hashing, and why is it better than simple modulo hashing for sharding? When does it matter?

5. You're migrating from a single PostgreSQL database to a sharded setup. What are the biggest challenges, and how would you approach the migration?

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Goes deeper on the consensus algorithms and leader election that make single-leader replication (and Raft-per-range systems like CockroachDB) actually work |
| [Module 06: Microservices Architecture](../06-microservices/README.md) | The Saga pattern is how you get transactional guarantees once sharding or service boundaries put data behind more than one database |
| [Module 10: Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md) | Applies this module's Cassandra and denormalization advice to a real fan-out and feed-ranking design |
| [Module 12: Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md) | Turns the ACID-for-payments guidance here into a concrete ledger design with gateway reconciliation |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│             Databases and Storage — Key Takeaways              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. SQL vs NoSQL is a query-pattern decision, not an age       │
│     contest — decide on transactions and joins, not on what    │
│     feels modern                                               │
│  2. Exhaust vertical scaling and read replicas before you shard│
│     — resharding later is a migration project, not a config    │
│     flag                                                       │
│  3. Pick shard keys for cardinality and access pattern, not    │
│     convenience — `created_at` sends every new write to one    │
│     shard forever                                              │
│  4. Consistent hashing earns its complexity the day you add or │
│     remove a node — plain modulo hashing remaps almost         │
│     everything                                                 │
│  5. CockroachDB and Spanner are not multi-leader — they're many│
│     single-leader Raft groups, one per range, and the          │
│     distinction matters when you design around them            │
│  6. ACID's "C" and CAP's "C" are different words spelled the   │
│     same — say "integrity constraints" or "linearizable"       │
│     instead and skip the confusion                             │
│  7. Composite indexes read left-to-right — equality columns    │
│     first, range columns last, or the index quietly stops      │
│     helping                                                    │
│  8. Instagram's stack isn't one database, it's five, each      │
│     earning its place — polyglot persistence is a deliberate   │
│     operational trade, not a mess                              │
│  9. Denormalize for reads once joins get expensive, but budget │
│     for the write amplification and staleness it buys you      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 01: System Design Fundamentals](../01-fundamentals/README.md)

**Next:** [Module 03: Caching Strategies](../03-caching/README.md)

---

*Module 02 of 22 in the System Design Playground*
