# Flashcards

103 question-and-answer cards covering all 26 modules, for
spaced-repetition review. Each answer restates what its module teaches; the
module link takes you to the full explanation.

**Two ways to use them:**

- **Here on GitHub**: read each question, answer it out loud or on paper,
  then click it to reveal the answer.
- **In Anki** (or any spaced-repetition app that imports text): download
  [`cards.tsv`](cards.tsv), choose *File → Import*, set the separator to
  *Tab*, and map the three fields to *Front*, *Back* and *Tags*. Anki then
  schedules each card for you.

Contributing a card? Add a line to `cards.tsv` and run
`python3 tools/build_flashcards.py`; this page is generated from it.

## Modules

- [Module 1: System Design Fundamentals](#module-1-system-design-fundamentals) — 5 cards
- [Module 2: Databases and Storage](#module-2-databases-and-storage) — 6 cards
- [Module 3: Caching Strategies](#module-3-caching-strategies) — 4 cards
- [Module 4: Load Balancing and Networking](#module-4-load-balancing-and-networking) — 5 cards
- [Module 5: Asynchronous Systems and Message Queues](#module-5-asynchronous-systems-and-message-queues) — 6 cards
- [Module 6: Microservices Architecture](#module-6-microservices-architecture) — 5 cards
- [Module 7: Reliability Engineering](#module-7-reliability-engineering) — 5 cards
- [Module 8: Distributed Systems Deep Dive](#module-8-distributed-systems-deep-dive) — 7 cards
- [Module 9: Design Case — URL Shortener and Rate Limiter](#module-9-design-case--url-shortener-and-rate-limiter) — 3 cards
- [Module 10: Design Case — Chat System and News Feed](#module-10-design-case--chat-system-and-news-feed) — 3 cards
- [Module 11: Design Case — Distributed File Storage and Video Streaming](#module-11-design-case--distributed-file-storage-and-video-streaming) — 4 cards
- [Module 12: Design Case — Payment System and E-commerce](#module-12-design-case--payment-system-and-e-commerce) — 4 cards
- [Module 13: Security](#module-13-security) — 3 cards
- [Module 14: API Design](#module-14-api-design) — 3 cards
- [Module 15: Observability](#module-15-observability) — 3 cards
- [Module 16: Incident Response and On-Call](#module-16-incident-response-and-on-call) — 3 cards
- [Module 17: Machine Learning System Design](#module-17-machine-learning-system-design) — 3 cards
- [Module 18: LLM Inference Serving Architecture](#module-18-llm-inference-serving-architecture) — 4 cards
- [Module 19: RAG System Architecture at Scale](#module-19-rag-system-architecture-at-scale) — 3 cards
- [Module 20: Agent System Architecture](#module-20-agent-system-architecture) — 3 cards
- [Module 21: AI Evaluation and Quality](#module-21-ai-evaluation-and-quality) — 3 cards
- [Module 22: Production AI System Architecture](#module-22-production-ai-system-architecture) — 3 cards
- [Module 23: Design Case — Search Autocomplete and Proximity Search](#module-23-design-case--search-autocomplete-and-proximity-search) — 3 cards
- [Module 24: Design Case — Ticket Booking and Reservations](#module-24-design-case--ticket-booking-and-reservations) — 4 cards
- [Module 25: Design Case — Web Crawler and Notification System](#module-25-design-case--web-crawler-and-notification-system) — 4 cards
- [Module 26: Design Case — Distributed Message Queue and Metrics Monitoring System](#module-26-design-case--distributed-message-queue-and-metrics-monitoring-system) — 4 cards

---

## Module 1: System Design Fundamentals

[Read the module](../01-fundamentals/README.md)

<details>
<summary>Roughly how many requests per second is 1 million requests per day?</summary>

About 12 per second. Divide daily volume by ~10^5 (86,400 seconds per day), then multiply by 2-3 for the peak.

</details>

<details>
<summary>What does the CAP theorem actually force you to choose?</summary>

During a network partition, a system must give up either consistency (linearizability) or availability. Partition tolerance is not optional, so “pick 2 of 3” is a misstatement.

</details>

<details>
<summary>What does PACELC add to CAP?</summary>

The normal case: if Partitioned, choose Availability or Consistency; Else, choose Latency or Consistency. Most of the time the real trade-off is latency vs consistency.

</details>

<details>
<summary>List the 9 steps of the design framework.</summary>

Clarify requirements, estimate capacity, define the API, design the data model, sketch the high-level design, deep dive, discuss trade-offs, address bottlenecks, handle follow-ups.

</details>

<details>
<summary>What separates a staff-level design answer from a senior one?</summary>

Staff answers question the requirements, find the one or two things that decide the design, choose deep dives by risk, and tie trade-offs to business and operational cost.

</details>

---

## Module 2: Databases and Storage

[Read the module](../02-databases-storage/README.md)

<details>
<summary>Which anomaly does snapshot isolation still allow?</summary>

Write skew: two transactions read the same data and each writes a different row, together breaking a rule neither broke alone.

</details>

<details>
<summary>What is PostgreSQL's default isolation level, and what does it let through?</summary>

Read Committed. Each statement sees a fresh snapshot, so read-then-write logic can suffer lost updates and write skew.

</details>

<details>
<summary>Name three fixes for a lost update.</summary>

An atomic UPDATE (SET n = n + 1), SELECT ... FOR UPDATE before writing, or an optimistic version column checked in the WHERE clause.

</details>

<details>
<summary>B-tree vs LSM-tree: which favours writes, and why?</summary>

LSM-tree. It appends to an in-memory memtable and flushes sorted immutable files that are merged later; a B-tree updates pages in place.

</details>

<details>
<summary>What can a Bloom filter answer with certainty?</summary>

“Definitely not present.” “Present” may be a false positive. About 10 bits per key gives roughly a 1% false-positive rate.

</details>

<details>
<summary>Why do column stores beat row stores for analytics?</summary>

A query reads only the columns it needs, similar values stored together compress far better (dictionary, run-length), and min/max statistics let it skip blocks.

</details>

---

## Module 3: Caching Strategies

[Read the module](../03-caching/README.md)

<details>
<summary>When data changes, should you update or delete the cached copy?</summary>

Delete it. Two racing writers that overwrite the cache can leave stale data cached indefinitely.

</details>

<details>
<summary>Why doesn't sharding fix a hot key?</summary>

All the traffic is on one key, so it lands on one shard however many shards exist. Use an in-process L1 cache, replicate the key, or serve it from the CDN.

</details>

<details>
<summary>Cache penetration vs cache avalanche?</summary>

Penetration: requests for keys that exist nowhere bypass the cache every time (cache negative results or use a Bloom filter). Avalanche: many keys expire at once (add jitter to TTLs).

</details>

<details>
<summary>What data should never be cached?</summary>

Data that must be exactly right at read time, such as bank balances or inventory counts used to make decisions.

</details>

---

## Module 4: Load Balancing and Networking

[Read the module](../04-load-balancing/README.md)

<details>
<summary>What are a token bucket's two parameters, and what behaviour do they allow?</summary>

Capacity (burst size) and refill rate. Short bursts up to capacity are allowed while the long-run rate is enforced.

</details>

<details>
<summary>L4 vs L7 load balancing?</summary>

L4 routes by IP and port without reading the request; L7 reads HTTP (paths, headers, cookies) and can route by content, at more CPU cost.

</details>

<details>
<summary>Why must INCR and EXPIRE for a rate limiter be atomic?</summary>

A crash between two separate calls leaves a counter with no TTL, which becomes a permanent ban. Pipeline them or use a Lua script.

</details>

<details>
<summary>What is the Kubernetes HPA scaling rule?</summary>

desired = ceil(current x metric / target), skipped within a +-10% tolerance. Scale-down uses the highest recommendation of the last 5 minutes; scale-up is immediate.

</details>

<details>
<summary>Why isn't autoscaling overload protection?</summary>

New capacity takes minutes to detect, boot and warm up. Spikes faster than that hit existing capacity, so you also need headroom and load shedding.

</details>

---

## Module 5: Asynchronous Systems and Message Queues

[Read the module](../05-async-systems/README.md)

<details>
<summary>Is exactly-once delivery possible over a network?</summary>

No. You get at-least-once delivery plus idempotent processing, or exactly-once processing inside one system's transaction boundary (e.g. Kafka transactions).

</details>

<details>
<summary>What problem does the transactional outbox solve?</summary>

The dual write: a database update and an event publish can't share a transaction. Write the event to an outbox table in the same transaction and relay it afterwards (or use CDC).

</details>

<details>
<summary>Kafka guarantees ordering within what unit?</summary>

A partition. Messages that must stay in order need the same key, so they land on the same partition.

</details>

<details>
<summary>What is a watermark in stream processing?</summary>

The processor's assertion that no more events older than time W are expected. Windows that end before W are emitted; later arrivals are late data.

</details>

<details>
<summary>How do you make a stream job's output exactly-once in effect?</summary>

Upsert each window's final value keyed by (key, window) instead of incrementing, so a replay overwrites rather than double-counts.

</details>

<details>
<summary>Backward vs forward schema compatibility?</summary>

Backward: new readers can read old data (add fields with defaults; upgrade consumers first). Forward: old readers can read new data (upgrade producers first).

</details>

---

## Module 6: Microservices Architecture

[Read the module](../06-microservices/README.md)

<details>
<summary>What is a saga?</summary>

A sequence of local transactions, each with a compensating action that undoes it if a later step fails. It replaces a distributed transaction across services.

</details>

<details>
<summary>How do you rename a database column with zero downtime?</summary>

Expand/contract: add the new column, dual-write, backfill in batches, switch reads, stop writing the old column, then drop it later. Each step is deployable and reversible alone.

</details>

<details>
<summary>Why can a metadata-only ALTER TABLE take a PostgreSQL site down?</summary>

It queues for an exclusive lock behind a long-running query, and every new query on the table queues behind it. Set lock_timeout and retry.

</details>

<details>
<summary>What should a canary be compared against?</summary>

A fresh baseline of the current version, started at the same time and size, not the old fleet, which differs in uptime and warm caches.

</details>

<details>
<summary>What is the difference between deploy and release?</summary>

Deploy puts code on servers; release exposes behaviour to users. Feature flags separate the two, so a release can be rolled out gradually or turned off in seconds.

</details>

---

## Module 7: Reliability Engineering

[Read the module](../07-reliability/README.md)

<details>
<summary>Why add jitter to retries?</summary>

Clients that failed together otherwise retry together in synchronized waves. Full jitter waits a random time between 0 and the backoff cap.

</details>

<details>
<summary>What does a circuit breaker do?</summary>

After repeated failures it opens and fails fast without calling the dependency, then lets a trial request through (half-open) to test recovery.

</details>

<details>
<summary>State Little's Law.</summary>

Requests in flight = throughput x latency. For example, 1,000 req/s at 200 ms means 200 concurrent requests.

</details>

<details>
<summary>How much downtime does a 99.9% monthly SLO allow?</summary>

About 43 minutes per month: 0.1% of 43,200 minutes.

</details>

<details>
<summary>Backpressure vs load shedding?</summary>

Backpressure rejects work early when a bounded queue is full, so callers slow down. Load shedding deliberately drops the least valuable work first when demand exceeds capacity.

</details>

---

## Module 8: Distributed Systems Deep Dive

[Read the module](../08-distributed-systems/README.md)

<details>
<summary>How many failures can a 5-node Raft cluster tolerate?</summary>

Two. A majority (3) is needed. Even sizes add nothing: 4 nodes tolerate 1 failure, the same as 3.

</details>

<details>
<summary>What is a fencing token, and who issues it?</summary>

A monotonically increasing number issued by the lock service with each grant. Storage rejects writes carrying a lower token than the highest it has seen.

</details>

<details>
<summary>Lamport clocks vs vector clocks?</summary>

Lamport timestamps give an order consistent with causality but can't detect concurrency. Vector clocks can tell “happened before” from “concurrent”.

</details>

<details>
<summary>What does a phi accrual failure detector output?</summary>

A suspicion level, phi = -log10(probability a heartbeat would arrive even later), that adapts to observed jitter instead of using a fixed timeout.

</details>

<details>
<summary>How fast does gossip spread news through N nodes?</summary>

In about O(log N) rounds, roughly log2 N + ln N with fanout 1: around 17 rounds for 1,000 nodes.

</details>

<details>
<summary>Does W + R &gt; N give linearizable reads?</summary>

No. It guarantees that read and write quorums overlap, but sloppy quorums, partially failed writes and concurrent updates still allow stale or conflicting reads.

</details>

<details>
<summary>Why use Merkle trees for anti-entropy?</summary>

Replicas compare root hashes and descend only into subtrees that differ, finding a few stale keys among millions with tens of hash comparisons.

</details>

---

## Module 9: Design Case — URL Shortener and Rate Limiter

[Read the module](../09-case-url-shortener-rate-limiter/README.md)

<details>
<summary>How many codes do 7 base62 characters give?</summary>

62^7, about 3.5 trillion.

</details>

<details>
<summary>Why not expose a sequential counter directly as the short code?</summary>

Sequential codes are trivial to enumerate. Run the counter through a secret bijection before making it public.

</details>

<details>
<summary>Why is caching a URL shortener nearly free?</summary>

Mappings are immutable, so there is no invalidation problem; an in-process cache and long CDN TTLs absorb most reads.

</details>

---

## Module 10: Design Case — Chat System and News Feed

[Read the module](../10-case-chat-newsfeed/README.md)

<details>
<summary>Fan-out on write vs fan-out on read?</summary>

Write: push each post into followers' feeds when posted (fast reads, explodes for celebrities). Read: assemble the feed at read time (cheap writes, slow reads). Production systems use a hybrid.

</details>

<details>
<summary>What ordering should a chat system guarantee?</summary>

Order within a conversation, assigned server-side with sequence numbers. Global ordering is unnecessary, and client clocks can't be trusted.

</details>

<details>
<summary>How does a chat server deliver a message to a user connected elsewhere?</summary>

Through a connection registry that maps each user to the server holding their WebSocket; no server can reach a user it doesn't know about.

</details>

---

## Module 11: Design Case — Distributed File Storage and Video Streaming

[Read the module](../11-case-storage-streaming/README.md)

<details>
<summary>Why does a sync client split files into chunks?</summary>

Only changed chunks are uploaded (delta sync), uploads resume chunk by chunk, and identical chunks deduplicate by content hash.

</details>

<details>
<summary>What is adaptive bitrate streaming?</summary>

Video is encoded at several bitrates and cut into short segments; the player picks each segment's quality from measured bandwidth (HLS, DASH).

</details>

<details>
<summary>Why upload large files with presigned URLs?</summary>

The client uploads straight to object storage, so application servers never hold the bytes; the URL grants one operation on one key until it expires.

</details>

<details>
<summary>RS(10,4) erasure coding vs 3x replication?</summary>

1.4x vs 3x storage. RS(10,4) survives any 4 lost fragments vs 2 lost copies, but repairing one fragment reads 10 others.

</details>

---

## Module 12: Design Case — Payment System and E-commerce

[Read the module](../12-case-payment-ecommerce/README.md)

<details>
<summary>Who should mint the idempotency key for a payment, client or server?</summary>

The client. A key the server generates on each retry defeats the mechanism.

</details>

<details>
<summary>Why claim the idempotency key with SET NX before charging?</summary>

Check-then-set lets two concurrent retries both pass the check and double-charge. An atomic claim lets only one through.

</details>

<details>
<summary>How should money be stored?</summary>

As integer minor units (cents), never floats, and totals recomputed server-side from authoritative prices.

</details>

<details>
<summary>Why is reconciliation required in a payment system?</summary>

It is the only backstop for a charge that succeeded at the gateway but never reached your ledger (or the reverse).

</details>

---

## Module 13: Security

[Read the module](../13-security/README.md)

<details>
<summary>Authentication vs authorization?</summary>

Authentication proves who you are; authorization decides what that identity may do.

</details>

<details>
<summary>How should passwords be stored?</summary>

With a slow, salted, memory-hard hash such as Argon2id. Never encrypted, and never with a fast hash like SHA-256.

</details>

<details>
<summary>What is envelope encryption?</summary>

Data is encrypted with a data key (DEK), and the DEK is encrypted by a key held in a KMS, so keys can be rotated and access audited without re-encrypting everything.

</details>

---

## Module 14: API Design

[Read the module](../14-api-design/README.md)

<details>
<summary>REST, gRPC or GraphQL: what should decide?</summary>

The consumer: REST for broad public APIs, gRPC for internal service-to-service calls, GraphQL for clients that need flexible, aggregated reads.

</details>

<details>
<summary>Why prefer cursor pagination over offset pagination?</summary>

Offsets get slower as they grow and skip or repeat items when data changes; a cursor continues from a stable position.

</details>

<details>
<summary>What makes an API change breaking?</summary>

Removing or renaming a field, tightening validation, changing a type, or changing a field's meaning. Adding an optional field or endpoint is safe.

</details>

---

## Module 15: Observability

[Read the module](../15-observability/README.md)

<details>
<summary>Why can't you average percentiles?</summary>

The p99 of several hosts is not the average of their p99s. Aggregate histogram buckets (distributions), then compute the percentile.

</details>

<details>
<summary>What drives the cost of a metrics system?</summary>

Cardinality: the product of label values. Unbounded dimensions such as user IDs belong in traces and logs.

</details>

<details>
<summary>Metrics, traces, logs: what does each do best?</summary>

Metrics detect, traces localize, logs explain, in that order.

</details>

---

## Module 16: Incident Response and On-Call

[Read the module](../16-incident-response/README.md)

<details>
<summary>Mitigate or diagnose first during an incident?</summary>

Mitigate. A rollback or a flag flip ends user harm far faster than understanding the cause.

</details>

<details>
<summary>What should a page be triggered by?</summary>

User-facing symptoms and error-budget burn rates, not causes or fixed thresholds such as CPU &gt; 80%.

</details>

<details>
<summary>What does the Incident Commander do?</summary>

Coordinates and decides, but fixes nothing; one other person makes changes to production, announcing each one.

</details>

---

## Module 17: Machine Learning System Design

[Read the module](../17-ml-system-design/README.md)

<details>
<summary>What is training/serving skew?</summary>

Features computed differently in training and in serving drift apart. Use one feature definition, or log the exact features served and train on them.

</details>

<details>
<summary>How must features be joined for training data?</summary>

As of the prediction time (point-in-time correct), never as of query time, or future information leaks into training.

</details>

<details>
<summary>Why does retrieval optimize recall in a ranking funnel?</summary>

Nothing downstream can recover a candidate that retrieval dropped; later stages trade recall for precision.

</details>

---

## Module 18: LLM Inference Serving Architecture

[Read the module](../18-llm-inference-serving/README.md)

<details>
<summary>What usually limits LLM serving throughput: compute or memory?</summary>

Memory, specifically the KV cache, which grows with batch size and sequence length.

</details>

<details>
<summary>How do you size the KV cache per token?</summary>

2 x layers x KV heads x head dimension x bytes per value.

</details>

<details>
<summary>What does PagedAttention change?</summary>

It stores the KV cache in fixed-size pages allocated on demand, like OS virtual memory, instead of contiguous pre-allocated blocks.

</details>

<details>
<summary>Why is continuous batching standard?</summary>

Static batching waits for the slowest sequence while finished slots idle; continuous batching swaps in new requests every step.

</details>

---

## Module 19: RAG System Architecture at Scale

[Read the module](../19-rag-at-scale/README.md)

<details>
<summary>Why rerank retrieved results?</summary>

A cross-encoder reranker over the top candidates is the cheapest, highest-leverage retrieval quality improvement.

</details>

<details>
<summary>Why does reciprocal rank fusion beat weighted score fusion?</summary>

It combines ranks, which are comparable across retrievers, instead of raw scores, which are not.

</details>

<details>
<summary>Does a bigger context window remove the need for retrieval?</summary>

No. Cost, latency and lost-in-the-middle effects remain; more context is not more accuracy.

</details>

---

## Module 20: Agent System Architecture

[Read the module](../20-agent-architecture/README.md)

<details>
<summary>What is the main design surface of an agent?</summary>

The harness: tools, middleware and context management, more than the choice of model.

</details>

<details>
<summary>How should agent tools be designed?</summary>

Fewer, larger, orthogonal tools at the level of the agent's intent, with errors that say what to do next.

</details>

<details>
<summary>Why treat the context window as a budget?</summary>

Quality degrades long before the hard limit, so context must be written, selected, compressed and isolated deliberately.

</details>

---

## Module 21: AI Evaluation and Quality

[Read the module](../21-ai-evaluation/README.md)

<details>
<summary>Why report Cohen's kappa instead of raw agreement for an LLM judge?</summary>

Raw agreement is inflated by the base rate; kappa measures agreement beyond chance.

</details>

<details>
<summary>Binary rubric questions or 1-5 scales?</summary>

Binary questions: they are more reliable and easier to validate against human labels.

</details>

<details>
<summary>Why must eval results carry a confidence interval?</summary>

Small samples hide large differences: at n=50 an 80% pass rate has a 95% interval about +-11 points.

</details>

---

## Module 22: Production AI System Architecture

[Read the module](../22-production-ai-system/README.md)

<details>
<summary>Why route queries by complexity?</summary>

Sending every query to the largest model overspends severalfold; simple queries can go to cheaper models.

</details>

<details>
<summary>How should retrieved documents and tool results be treated?</summary>

As untrusted data, never as instructions, because they are a prompt-injection vector.

</details>

<details>
<summary>Why must guardrails cover both input and output?</summary>

An input filter alone still lets PII and unsafe content out through the model's responses.

</details>

---

## Module 23: Design Case — Search Autocomplete and Proximity Search

[Read the module](../23-case-search-proximity/README.md)

<details>
<summary>How does a trie serve autocomplete fast?</summary>

Each node caches the top-k completions for its prefix, so a keystroke is one lookup instead of a subtree walk.

</details>

<details>
<summary>Why search 9 geohash cells for “nearby”?</summary>

Near points can sit in adjacent cells with no shared prefix; search the cell and its 8 neighbours, then filter by exact distance.

</details>

<details>
<summary>Why partition a search index by document rather than by term?</summary>

Each shard answers multi-term queries locally and returns a small top-k; term partitioning ships large posting lists between shards.

</details>

---

## Module 24: Design Case — Ticket Booking and Reservations

[Read the module](../24-case-ticket-booking/README.md)

<details>
<summary>How do you stop a seat being sold twice?</summary>

A conditional update: UPDATE ... WHERE status = 'available' (or the hold expired), then check that the number of rows updated is what you asked for.

</details>

<details>
<summary>Why does a hold expiry need no background job for correctness?</summary>

Expired holds are treated as free in the next buyer's WHERE clause; a sweeper only tidies the seat map.

</details>

<details>
<summary>What does a virtual waiting room change?</summary>

The booking tier's load becomes a chosen admission rate instead of the size of the crowd; signed tokens enforce it at the gateway.

</details>

<details>
<summary>How do you handle payment racing an expiring hold?</summary>

Authorize the card, confirm the seat conditionally on the hold, then capture, or void the authorization if the hold expired.

</details>

---

## Module 25: Design Case — Web Crawler and Notification System

[Read the module](../25-case-crawler-notifications/README.md)

<details>
<summary>What limits a polite crawler's throughput?</summary>

The number of distinct hosts with URLs ready, because each host gets about one request per second, not the number of machines.

</details>

<details>
<summary>Why partition a crawl by host hash rather than URL hash?</summary>

Each host's queue and rate timer then live on one worker, so politeness needs no coordination.

</details>

<details>
<summary>What is SimHash used for?</summary>

Near-duplicate detection: similar pages get 64-bit fingerprints that differ in a few bits (Google used a 3-bit threshold).

</details>

<details>
<summary>Why give transactional notifications their own queues?</summary>

So a marketing blast can never delay a one-time passcode or a password reset.

</details>

---

## Module 26: Design Case — Distributed Message Queue and Metrics Monitoring System

[Read the module](../26-case-message-queue-metrics/README.md)

<details>
<summary>What does acks=all with min.insync.replicas=2 guarantee in Kafka?</summary>

An acknowledged write is on every in-sync replica, and on at least 2, so a leader failure can't lose it; with fewer in-sync replicas, writes are refused.

</details>

<details>
<summary>What is the high watermark?</summary>

The highest offset present on every in-sync replica; consumers only see messages below it.

</details>

<details>
<summary>Why does Gorilla compression work so well on metrics?</summary>

Regular scrape intervals make delta-of-delta timestamps usually zero (1 bit), and slowly changing values XOR to few differing bits.

</details>

<details>
<summary>What should downsampling keep per interval?</summary>

Sum, count, min and max (and histogram buckets), so averages and percentiles can still be computed correctly.

</details>
