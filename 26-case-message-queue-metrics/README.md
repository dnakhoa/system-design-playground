# Module 26: Design Case — Distributed Message Queue and Metrics Monitoring System

> **Building the infrastructure everyone else depends on.** Earlier modules
> *use* Kafka and *read* dashboards. This one designs them. Both are
> append-heavy systems built on the same insight: write sequentially, index
> sparsely, and let time order do most of the work.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 25 | Design Case — Web Crawler and Notification System | [../25-case-crawler-notifications/](../25-case-crawler-notifications/) |
| **Module 26** | **Design Case — Distributed Message Queue and Metrics Monitoring System** | **(current)** |
| — | Course Home | [../README.md](../README.md) |

Like Modules 23-25, this design case was added after the main sequence. It
builds on [Module 05](../05-async-systems/README.md) (how to *use* a log-based
queue), [Module 08](../08-distributed-systems/README.md) (replication and
quorums) and [Module 15](../15-observability/README.md) (how to *use*
metrics). Read those first.

---

## Learning Objectives

- Design a partition as a segmented append-only log with a sparse index,
  and explain why that makes both writes and reads fast
- Explain leader/follower replication with in-sync replicas and a high
  watermark, and what `acks=1` and `acks=all` actually guarantee
- Design consumer groups, offset commits and rebalancing
- Choose between pull and push metric collection
- Store time series compactly with delta-of-delta and XOR encoding, and
  index them by label
- Design downsampling, alert evaluation, and monitoring for the monitoring
  system itself

---

## Table of Contents

1. [Part 1: Distributed Message Queue](#part-1-distributed-message-queue)
2. [Part 2: Metrics Monitoring System](#part-2-metrics-monitoring-system)
3. [Design Comparison](#design-comparison)
4. [What Each Level Is Expected to Cover](#what-each-level-is-expected-to-cover)
5. [Practice Exercise](#practice-exercise)
6. [Common Mistakes](#common-mistakes)
7. [Discussion Questions](#discussion-questions)
8. [Key References](#key-references)

---

## Part 1: Distributed Message Queue

### Requirements

- **Functional**: producers write messages to named topics; consumers read
  them, in order per partition, at their own pace; messages are retained for
  a configured time and can be re-read (replayed)
- **Scale**: 1 GB/s of incoming messages at peak; 7-day retention
- **Durability**: an acknowledged message survives the loss of any one broker
- **Delivery**: at-least-once by default; exactly-once processing as an option

```
  Retained data:  1 GB/s × 604,800 s × 3 replicas  ≈ 1.8 PB
```

The retention line is the one that shapes the hardware: **a log-based queue is
a storage system first**. A traditional queue deletes a message once consumed
and holds little; a log keeps everything for its retention period whether
anyone has read it or not.

### Topics, Partitions and Ordering

```
  topic "orders" (3 partitions)

  partition 0:  [0][1][2][3][4][5][6] ──▶ next write at offset 7
  partition 1:  [0][1][2][3]          ──▶ next write at offset 4
  partition 2:  [0][1][2][3][4]       ──▶ next write at offset 5

  key "order-42" ─ hash ─▶ always partition 1  →  ordered relative to itself
```

A **partition** is the unit of ordering, parallelism and replication. Order is
guaranteed only within a partition, so messages that must stay in order share
a key. Throughput scales with partitions: if one consumer can process 10 MB/s,
1 GB/s needs at least 100 partitions.

### The Storage Engine: A Segmented Log

Each partition is a directory of **segment files**. Writes only ever append
to the newest segment. Each segment has a **sparse index**: one entry every
few KB mapping an offset to a byte position, small enough to keep in memory.

```python
"""A partition as a segmented, append-only log with a sparse offset index."""

from bisect import bisect_right


class Segment:
    def __init__(self, base_offset: int, index_every: int):
        self.base_offset = base_offset
        self.data = bytearray()        # the .log file: records back to back
        self.index = []                # the .index file: (offset, byte position), sparse
        self.count = 0
        self.index_every = index_every

    def append(self, offset: int, value: bytes) -> None:
        if self.count % self.index_every == 0:
            self.index.append((offset, len(self.data)))
        self.data += offset.to_bytes(8, "big") + len(value).to_bytes(4, "big") + value
        self.count += 1

    def read(self, offset: int) -> tuple[bytes, int]:
        # Binary-search the sparse index, then scan forward a few records.
        i = bisect_right(self.index, (offset, float("inf"))) - 1
        pos, scanned = self.index[i][1], 0
        while True:
            rec_offset = int.from_bytes(self.data[pos:pos + 8], "big")
            size = int.from_bytes(self.data[pos + 8:pos + 12], "big")
            if rec_offset == offset:
                return bytes(self.data[pos + 12:pos + 12 + size]), scanned
            pos += 12 + size
            scanned += 1


class PartitionLog:
    def __init__(self, segment_records: int = 1000, index_every: int = 50):
        self.segment_records = segment_records
        self.index_every = index_every
        self.segments = [Segment(0, index_every)]
        self.next_offset = 0

    def append(self, value: bytes) -> int:
        seg = self.segments[-1]
        if seg.count == self.segment_records:          # roll a new segment
            seg = Segment(self.next_offset, self.index_every)
            self.segments.append(seg)
        seg.append(self.next_offset, value)
        self.next_offset += 1
        return self.next_offset - 1

    def read(self, offset: int):
        bases = [s.base_offset for s in self.segments]
        seg = self.segments[bisect_right(bases, offset) - 1]   # which file?
        return seg.read(offset)

    def delete_before(self, offset: int) -> int:
        """Retention: drop whole segments, never rewrite one."""
        keep = [s for s in self.segments if s.base_offset + s.count > offset]
        dropped = len(self.segments) - len(keep)
        self.segments = keep
        return dropped


log = PartitionLog()
for i in range(10_000):
    log.append(f"event-{i}".encode())

value, scanned = log.read(7_321)
print(f"offset 7321 -> {value.decode()} ({len(log.segments)} segments, "
      f"scanned {scanned} records after the index lookup)")
print(f"retention dropped {log.delete_before(5_000)} whole segments")
```

```
offset 7321 -> event-7321 (10 segments, scanned 21 records after the index lookup)
retention dropped 5 whole segments
```

Why this design is fast:

- **Sequential writes.** Appending is the fastest thing a disk does: no seeks,
  no in-place updates, no B-tree page splits.
- **Reads served from the page cache.** Consumers that keep up read data that
  was just written and is still in the OS page cache, so most reads never touch
  the disk. The broker leaves caching to the OS instead of keeping its own copy
  of the data.
- **Zero-copy transfer.** For plaintext connections the broker can hand file
  bytes straight from the page cache to the socket (`sendfile`) without copying
  them into its own memory. TLS mostly removes this benefit, because data must
  be encrypted in user space.
- **Batching everywhere.** Producers batch and compress many messages per
  request; consumers fetch large batches. Per-message overhead disappears.
- **Retention is a file delete.** Old data is removed by deleting whole
  segments, never by rewriting.

**Log compaction** is the other retention mode: keep only the latest value for
each key, and drop a key entirely after a tombstone (a null value). A compacted
topic is a durable, replayable table, which is how stream processors and CDC
pipelines store state.

### Replication: ISR and the High Watermark

Each partition has one **leader** and some **followers**, which continuously
fetch from the leader. The **in-sync replicas (ISR)** are the replicas that
are caught up (a follower that falls too far behind drops out). The **high
watermark** is the highest offset present on every ISR member: consumers only
see messages below it, and only those are safe from a leader failure.

```python
"""Leader, followers, ISR and the high watermark: what acks=1 vs acks=all really promise."""


class Replica:
    def __init__(self, name):
        self.name, self.log = name, []

    @property
    def leo(self):                          # log end offset
        return len(self.log)


class Partition:
    def __init__(self, min_insync: int = 2):
        self.replicas = [Replica("broker-1"), Replica("broker-2"), Replica("broker-3")]
        self.leader = self.replicas[0]
        self.isr = list(self.replicas)      # in-sync replicas
        self.min_insync = min_insync

    def high_watermark(self) -> int:
        """Offsets below this exist on every ISR member: safe to expose and to ack."""
        return min(r.leo for r in self.isr)

    def produce(self, msg: str, acks: str) -> str:
        if acks == "all" and len(self.isr) < self.min_insync:
            return f"{msg}: REJECTED (ISR {len(self.isr)} < min.insync.replicas {self.min_insync})"
        self.leader.log.append(msg)
        if acks == "1":
            return f"{msg}: acked by leader"
        self.replicate()                    # acks=all waits until the HW covers it
        return f"{msg}: acked after ISR replicated (HW={self.high_watermark()})"

    def replicate(self, only=None):
        for r in self.isr:
            if r is not self.leader and (only is None or r.name in only):
                r.log = list(self.leader.log)

    def fail_leader(self):
        self.isr.remove(self.leader)
        # Elect from the ISR; the new leader's log is the truth. Others truncate to it.
        self.leader = max(self.isr, key=lambda r: r.leo)
        for r in self.isr:
            r.log = r.log[:self.leader.leo]


p = Partition()
print(p.produce("m1", acks="all"))
print(p.produce("m2", acks="1"))
print(p.produce("m3", acks="1"))         # followers have not fetched m2, m3 yet
p.fail_leader()                           # broker-1 dies before followers fetch
print(f"new leader {p.leader.name} has {p.leader.log}: m2 and m3 were acked, then lost")

p = Partition()
for m in ("m1", "m2", "m3"):
    print(p.produce(m, acks="all"))
p.fail_leader()
print(f"new leader {p.leader.name} has {p.leader.log}: nothing acked was lost")
p.fail_leader()                           # a second broker dies: ISR is now 1
print(p.produce("m4", acks="all"))
```

```
m1: acked after ISR replicated (HW=1)
m2: acked by leader
m3: acked by leader
new leader broker-2 has ['m1']: m2 and m3 were acked, then lost
m1: acked after ISR replicated (HW=1)
m2: acked after ISR replicated (HW=2)
m3: acked after ISR replicated (HW=3)
new leader broker-2 has ['m1', 'm2', 'm3']: nothing acked was lost
m4: REJECTED (ISR 1 < min.insync.replicas 2)
```

| Producer setting | Acknowledged when | Can lose acked data? |
|------------------|-------------------|----------------------|
| `acks=0` | Sent | Yes, freely |
| `acks=1` | Leader wrote it | Yes, if the leader dies before followers fetch |
| `acks=all` + `min.insync.replicas=2` | Every ISR member has it, and there are at least 2 | No, unless every ISR replica is lost |

The last line of the output is the trade-off made visible: with too few
in-sync replicas, `acks=all` **refuses writes rather than risk losing them**.
That is the CP choice from [Module 01](../01-fundamentals/README.md#cap-theorem).
The opposite setting, *unclean leader election*, lets an out-of-sync replica
become leader to restore availability, losing whatever it was missing. It is
off by default for good reason.

Leadership itself needs consensus: which broker leads each partition, and who
is in each ISR. Kafka originally kept this in ZooKeeper; it now uses its own
Raft-based controller quorum (KRaft), and since Kafka 4.0 (March 2025)
ZooKeeper mode is gone entirely.

### Consumers: Groups, Offsets and Rebalancing

```
  topic with 4 partitions, consumer group "billing" with 2 consumers

  P0 ─┐                      Each partition goes to exactly one consumer
  P1 ─┴──▶ consumer A        in the group, so order per partition holds.
  P2 ─┐
  P3 ─┴──▶ consumer B        A 5th consumer would sit idle: parallelism
                             is capped by the partition count.
```

- **Pull, not push.** Consumers fetch at their own pace (long-polling while
  idle). A slow consumer falls behind without overwhelming anyone, and a
  consumer can rewind to any retained offset to reprocess.
- **Offsets are the consumer's progress**, committed back to the broker (in
  Kafka, to an internal topic). Commit *after* processing for at-least-once;
  committing *before* processing risks losing messages if the consumer crashes.
- **Consumer lag** (latest offset minus committed offset, per partition) is
  the single most useful health metric for any consumer.
- **Rebalancing** reassigns partitions when consumers join, leave or crash.
  The original *eager* protocol stopped the whole group during a rebalance;
  *cooperative incremental* rebalancing moves only the partitions that must
  move, and Kafka 4.0 made a broker-coordinated group protocol (KIP-848)
  generally available to shorten rebalances further.

### Delivery Semantics

At-least-once is the baseline: producers retry, so the broker can receive a
message twice. The **idempotent producer** (on by default in modern Kafka)
attaches a producer ID and a per-partition sequence number, so the broker drops
retried duplicates. **Transactions** extend this so that a consume-transform-
produce step commits its output messages and its input offsets atomically:
exactly-once *within* the log. Side effects outside it still need the
idempotency techniques from
[Module 05](../05-async-systems/README.md#delivery-guarantees).

---

## Part 2: Metrics Monitoring System

### Requirements

- **Functional**: collect numeric metrics from every server and service;
  store them; answer queries for dashboards; evaluate alert rules and notify
- **Scale**: 10,000 hosts × 500 series each = **5 million active series**,
  collected every 15 seconds
- **Retention**: full resolution for 15 days; downsampled for 1 year
- **Reliability**: alerting must keep working when other systems are failing,
  which is exactly when it matters

```
  Ingest:   5M series ÷ 15 s                   ≈ 333,000 samples/s
  Raw:      16 bytes/sample                    → ~460 GB/day
  Encoded:  ~1.5 bytes/sample                  → ~43 GB/day
  15 days at full resolution                   ≈ 650 GB
  1 year at full resolution                    ≈ 16 TB  (so: downsample)
```

### Data Model

A **time series** is a metric name plus a set of labels, holding a sequence of
`(timestamp, float64)` samples:

```
  http_requests_total{service="checkout", method="POST", code="500"}
      (1700000000, 1042)  (1700000015, 1047)  (1700000030, 1055) ...
```

Every distinct label combination is a separate series, which is why
[cardinality](../15-observability/README.md#25-cardinality-the-cost-multiplier)
is the cost driver of the whole system, and why the ingest path must enforce
per-tenant series limits.

### Collection: Pull or Push?

| | Pull (Prometheus scrapes `/metrics`) | Push (agents send, e.g. StatsD, OTLP) |
|---|---|---|
| Discovering targets | Required: service discovery lists what to scrape | Not needed: whatever sends, exists |
| "Is it down or just quiet?" | A failed scrape *is* a signal (`up == 0`) | Silence is ambiguous |
| Load control | Collector sets the pace | A misbehaving client can flood the collector |
| Short-lived jobs, firewalled hosts | Awkward: may finish before a scrape | Natural |
| Typical home | Server fleets, Kubernetes | Serverless, edge devices, batch jobs |

Most large deployments run both: pull for long-lived services, push via a
gateway or OpenTelemetry collector for everything else.

### Storage: A Time-Series Database

The write pattern is extreme but friendly: millions of series, each
appended to in time order, almost never updated. The design that follows from
it (Facebook's Gorilla, and Prometheus's storage, which documents two-hour
blocks at 1-2 bytes per sample) looks like this:

```
  incoming samples ──▶ write-ahead log (durability)
                   └─▶ in-memory head block: one compressed chunk per series
                              │  every 2 hours
                              ▼
                       immutable on-disk block: chunks + label index
                              │  background
                              ▼
                       compaction into larger blocks; old blocks deleted
```

**Compression** is what makes memory and disk affordable. Timestamps arrive at
a regular interval, so store the *change in the interval* (delta-of-delta),
which is usually zero. Values change slowly, so XOR each one with the previous
value and store only the differing bits:

```python
"""Gorilla-style compression (Facebook, VLDB 2015): count the bits per sample."""

import random
import struct


def timestamp_bits(timestamps: list[int]) -> int:
    """Delta-of-delta: regular scrape intervals cost 1 bit per sample."""
    bits, prev, prev_delta = 64, timestamps[0], 0         # first timestamp in full
    for t in timestamps[1:]:
        delta = t - prev
        dod = delta - prev_delta
        if dod == 0:
            bits += 1
        elif -63 <= dod <= 64:
            bits += 2 + 7
        elif -255 <= dod <= 256:
            bits += 3 + 9
        elif -2047 <= dod <= 2048:
            bits += 4 + 12
        else:
            bits += 4 + 32
        prev, prev_delta = t, delta
    return bits


def value_bits(values: list[float]) -> int:
    """XOR with the previous value: unchanged costs 1 bit, small changes few bits."""
    as_int = [struct.unpack(">Q", struct.pack(">d", v))[0] for v in values]
    bits, prev = 64, as_int[0]
    prev_lead, prev_trail = 65, 65                         # no previous window yet
    for x in as_int[1:]:
        xor = x ^ prev
        if xor == 0:
            bits += 1
        else:
            lead = min(64 - xor.bit_length(), 31)
            trail = (xor & -xor).bit_length() - 1
            if lead >= prev_lead and trail >= prev_trail and prev_lead <= 64:
                bits += 2 + (64 - prev_lead - prev_trail)  # reuse previous window
            else:
                bits += 2 + 5 + 6 + (64 - lead - trail)    # new window
                prev_lead, prev_trail = lead, trail
        prev = x
    return bits


rng = random.Random(1)
n = 240                                                    # 1 hour at 15 s
ts = [1_700_000_000 + 15 * i + (1 if rng.random() < 0.05 else 0) for i in range(n)]

series = {
    "constant gauge (memory limit)": [8.0e9] * n,
    "counter (requests_total)": [float(sum(rng.randint(90, 110) for _ in range(i))) for i in range(n)],
    "noisy gauge (CPU %, 1 decimal)": [round(rng.uniform(20, 80), 1) for _ in range(n)],
}
print("raw: 16 bytes/sample (8-byte timestamp + 8-byte float)")
for name, vals in series.items():
    total = timestamp_bits(ts) + value_bits(vals)
    print(f"{name:<31} {total / 8 / n:5.2f} bytes/sample")
```

```
raw: 16 bytes/sample (8-byte timestamp + 8-byte float)
constant gauge (memory limit)    0.53 bytes/sample
counter (requests_total)         2.47 bytes/sample
noisy gauge (CPU %, 1 decimal)   7.51 bytes/sample
```

The result depends on the data: a flat gauge compresses about 30×, a jittery
value with many significant bits barely 2×. Real fleets are dominated by
slow-moving series, which is why the Gorilla paper reported an average of 1.37
bytes per sample on Facebook's production data.

**The label index** is an inverted index, the same structure as full-text
search in [Module 23](../23-case-search-proximity/README.md#part-2-full-text-search-and-the-inverted-index):
each `label=value` pair maps to a sorted list of series IDs, and a query like
`{service="checkout", code="500"}` intersects two lists.

### Downsampling and Queries

A year of 15-second data is 2.1 million points per series; no dashboard needs
them. Downsample old data to 5-minute and then 1-hour resolution, but keep
**sum, count, min and max** per interval, not just the average, so that
averages stay correct when combined and spikes stay visible. For latency, keep
the histogram buckets, never precomputed percentiles: percentiles cannot be
averaged across hosts or time
([Module 15](../15-observability/README.md#23-why-you-cannot-average-percentiles)),
while bucket counts can be summed and the percentile computed afterwards.

Queries scale with how much data they touch. Precompute expensive, frequently
used aggregations as **recording rules** (a new series evaluated every
interval), so a fleet-wide dashboard reads one series instead of 10,000.

### Alerting

```
  rule evaluator (every 15-60 s)
      expr:  error_ratio > 0.02   for: 5m      ← must hold for 5 minutes
        │ firing alerts
        ▼
  alert manager: deduplicate (HA pairs fire twice), group (one page for
                 200 hosts, not 200 pages), silence, inhibit, route
        │
        ▼
  pager / chat / email
```

- **`for:` durations** stop one bad scrape from paging anyone.
- **Run evaluators in pairs.** Both fire; the alert manager deduplicates. One
  evaluator crashing silently must not mean no alerts.
- **Watch the watcher.** An always-firing *watchdog* alert is sent to an
  external dead man's switch service, which pages if the heartbeat stops. The
  failure you must detect is "the monitoring system is down", and it cannot
  report its own death.
- Alert design itself (burn rates, symptoms over causes) is
  [Module 16](../16-incident-response/README.md)'s subject.

### Scaling Beyond One Server

A single Prometheus server scales vertically to millions of series. Beyond
that, the standard progression:

1. **Functional sharding**: separate servers per team or cluster.
2. **HA pairs**: two identical servers scrape the same targets.
3. **Global view and long-term storage**: servers stream samples
   (`remote_write`) to a horizontally scalable backend (Thanos, Cortex, Grafana
   Mimir) that shards series by hash, stores blocks in object storage, and
   fans queries out across them.

Keep alerting close to the data. A rule evaluated in each cluster still works
when the global backend or the network between regions is down.

---

## Design Comparison

| Aspect | Message queue | Metrics system |
|--------|---------------|----------------|
| Write pattern | Append-only per partition | Append-only per series |
| Unit of order | Partition | Series |
| Index | Sparse offset index per segment | Inverted label index per block |
| Retention | Delete whole segments; or compact by key | Delete whole blocks; downsample older data |
| Read pattern | Sequential from an offset | Time-range scans over many series |
| Durability | Replicated log, `acks=all` | WAL + replicated blocks; some loss often acceptable |
| Classic trap | `acks=1` losing acked data | Label cardinality explosion |

---

## What Each Level Is Expected to Cover

| Level | Message queue | Metrics system |
|-------|---------------|----------------|
| **Mid-level** | Topics, partitions, consumer groups; at-least-once | Agents, a time-series store, dashboards, alert rules |
| **Senior** | Segmented log and sparse index; ISR, high watermark, `acks`; offset commit timing; rebalancing | Pull vs push; compression; label index; downsampling with sum/count; HA alerting |
| **Staff** | Retention as the storage cost driver; unclean election trade-off; partition count limits and re-partitioning; KRaft vs external consensus | Cardinality governance; what must keep working during an outage; meta-monitoring; global vs local alerting |

---

## Practice Exercise

**30-minute design**: Design the metrics pipeline for a company running
2,000 Kubernetes clusters across 6 regions.

- 50,000 nodes; ~800 active series per node, plus application metrics
  totalling another 60 million series
- Engineers need a global dashboard and 13 months of history
- Each team should be billed for the series it creates
- Alerting for a region must work when that region is cut off from the others

**Key decisions**:
1. Compute the ingest rate at a 30-second interval. Where do samples go first?
2. What runs inside each cluster, what runs per region, and what is global?
3. How do you stop one team's deploy of a `user_id` label from taking down
   ingestion for everyone?
4. How do you prove, every few minutes, that alerting in every region is
   alive?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **`acks=1` for data that must not be lost** | The leader acknowledges before followers copy; a leader crash loses acked messages | `acks=all` with `min.insync.replicas=2` and a replication factor of 3 |
| **Enabling unclean leader election to "fix" an outage** | An out-of-sync replica becomes leader and the missing messages are gone for good | Keep it off for important topics; restore an in-sync replica instead |
| **Committing offsets before processing** | A crash after commit and before processing loses those messages | Process, then commit; make processing idempotent |
| **Too few partitions** | Consumer parallelism is capped at the partition count; adding partitions later changes key-to-partition mapping | Size for peak throughput per consumer, with headroom |
| **Assuming retention is free** | Retained data multiplies by the replication factor and dominates cost | Size storage as rate × retention × replicas; tier old segments to object storage |
| **Precomputing p99 per host and averaging it** | Percentiles can't be averaged; the result is meaningless | Store histogram buckets; compute percentiles after aggregation |
| **Downsampling to averages only** | Combined averages are wrong and spikes disappear | Keep sum, count, min and max per interval |
| **Unbounded label values** | Each user or request ID creates a new series; memory and ingest explode | Enforce per-tenant series limits at ingest; keep high-cardinality data in logs and traces |
| **A single alert evaluator** | If it dies silently, nothing alerts | Evaluator pairs, alert-manager dedupe, and an external dead man's switch |
| **Only global alerting** | A region cut off from the global backend loses its alerts exactly when it is failing | Evaluate alerts close to the data, inside each region |

---

## Discussion Questions

1. A consumer group processing payments has 12 partitions and 12 consumers, and lag keeps growing. The team adds 12 more consumers. What happens?

   **Model answer**: Nothing improves. Each partition is assigned to one consumer in the group, so the 12 new consumers sit idle, and the rebalance they trigger briefly pauses processing on top. Parallelism is capped by the partition count. Real options: find out why each consumer is slow (usually a slow downstream call per message, so batch it or make it concurrent *within* a consumer while preserving per-key order); increase the partition count, which changes which partition each key maps to, so drain or carefully migrate if per-key ordering matters; or move slow work off the hot path. Always check whether the lag is on all partitions or one: a single lagging partition means a hot key, not a capacity shortage.

2. Why does Kafka hand caching to the operating system's page cache instead of caching messages in the broker's own memory?

   **Model answer**: Because the access pattern is exactly what the page cache is good at: recently written data is read by consumers shortly afterwards. Keeping a second copy in the JVM heap would double memory use, add garbage-collection pressure, and be lost on every broker restart, whereas the page cache survives a process restart. Using the page cache also enables zero-copy sends from file to socket. The cost is less control: a consumer reading far behind (a replay from days ago) pulls cold data from disk and can evict hot data that live consumers need, which is one reason for tiered storage and separate clusters for heavy replay workloads.

3. Your metrics system's memory doubled in a week with no increase in host count. How do you investigate?

   **Model answer**: Memory in a time-series database tracks *active series*, so look for a cardinality increase, not a traffic increase. Query the number of series per metric name and per label, and compare with last week; one metric whose series count jumped by orders of magnitude is the usual culprit, typically from a deploy that added a label like `user_id`, `request_path` with IDs in it, or a pod name that changes on every restart. Fix the instrumentation (drop the label or bucket its values), add relabelling at ingest to drop it immediately, and put per-tenant series limits in place so the next mistake is rejected at the door instead of degrading the whole system.

4. Should the monitoring system's own data path go through the company's Kafka cluster?

   **Model answer**: It's tempting, because Kafka is already there and buffers well. The risk is a dependency loop: when Kafka has an incident, the system that would tell you about it degrades at the same moment. A common compromise: let bulk, delay-tolerant telemetry (logs, long-term metric storage) go through Kafka, but keep the alerting path independent: scrape, evaluate and notify locally within each cluster, with no dependency on the shared infrastructure being monitored. And monitor Kafka itself from outside, including from the external dead man's switch.

5. Kafka removed ZooKeeper in favour of KRaft. What problem does an external coordination service create, and what does folding it into the brokers change?

   **Model answer**: Metadata (partition leaders, ISR membership, configs) must be agreed on by consensus, and with ZooKeeper that consensus lived in a second distributed system with its own deployment, security, monitoring and failure modes. Controller failover also required reloading all metadata from ZooKeeper, which grew slow as partition counts climbed into the hundreds of thousands. KRaft stores metadata as a Raft-replicated log inside a quorum of Kafka controllers, using the same log abstraction as the data. Standby controllers already hold the metadata, so failover is fast; there is one system to operate; and partition limits rise. The cost is that Kafka now implements consensus itself, the "don't build consensus yourself" warning from Module 08, accepted because the project has the expertise and testing to do it.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview Vol. 2 (Ch. 4 Distributed Message Queue, Ch. 5 Metrics Monitoring) — Alex Xu & Sahn Lam | Book | Both designs, interview framing |
| "Kafka: a Distributed Messaging System for Log Processing" — Kreps, Narkhede & Rao (NetDB 2011) | Paper | The original log-based broker design |
| [Apache Kafka documentation: Design](https://kafka.apache.org/documentation/#design) | Docs | Persistence, replication, ISR, delivery semantics |
| [Apache Kafka 4.0.0 release announcement](https://kafka.apache.org/blog/2025/03/18/apache-kafka-4.0.0-release-announcement/) | Release notes | KRaft-only operation, new consumer group protocol |
| "Gorilla: A Fast, Scalable, In-Memory Time Series Database" — Pelkonen et al. (VLDB 2015) | Paper | Delta-of-delta and XOR compression |
| [Prometheus: Storage](https://prometheus.io/docs/prometheus/latest/storage/) | Docs | Head block, two-hour blocks, WAL, bytes per sample |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 05: Async Systems](../05-async-systems/README.md) | Using the queue designed here: partitioning, delivery guarantees, stream processing |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Raft, quorums and fencing behind controller and leader election |
| [Module 15: Observability](../15-observability/README.md) | Metric types, histograms and cardinality from the user's side |
| [Module 16: Incident Response](../16-incident-response/README.md) | Burn-rate alerting and paging policy on top of this system |
| [Module 23: Search Autocomplete and Proximity Search](../23-case-search-proximity/README.md) | The inverted index reused for label lookup |

---

## Navigation

**Previous:** [Module 25: Design Case — Web Crawler and Notification System](../25-case-crawler-notifications/README.md)

**Next:** [Course Home](../README.md)

---

*Module 26 of 26 in the System Design Playground*
