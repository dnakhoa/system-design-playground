# Module 05: Asynchronous Systems and Message Queues

> **Decouple services and handle work asynchronously.** Not everything needs a synchronous response. Async systems improve resilience, throughput, and user experience by offloading work to background processors.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 04 | Load Balancing and Networking | [../04-load-balancing/](../04-load-balancing/) |
| **Module 05** | **Asynchronous Systems and Message Queues** | **(current)** |
| Module 06 | Microservices Architecture | [../06-microservices/](../06-microservices/) |

---

## Learning Objectives

- Understand sync vs async communication patterns
- Design event-driven architectures with Kafka and RabbitMQ
- Implement event sourcing and CQRS patterns
- Handle delivery guarantees (at-least-once, exactly-once)
- Compute over streams with event-time windows, watermarks and a late-data policy
- Evolve event schemas without breaking old data or independently deployed consumers
- Design dead letter queues for error handling

---

## Table of Contents

1. [Sync vs Async Communication](#sync-vs-async-communication)
2. [Message Queue Patterns](#message-queue-patterns)
3. [Message Queue Comparison](#message-queue-comparison)
4. [Kafka Deep Dive](#kafka-deep-dive)
5. [Event-Driven Architecture](#event-driven-architecture)
6. [Event Sourcing](#event-sourcing)
7. [CQRS (Command Query Responsibility Segregation)](#cqrs-command-query-responsibility-segregation)
8. [Delivery Guarantees](#delivery-guarantees)
9. [The Dual-Write Problem: Outbox and CDC](#the-dual-write-problem-outbox-and-cdc)
10. [Stream Processing: Windows, Watermarks, and Late Data](#stream-processing-windows-watermarks-and-late-data)
11. [Schema Evolution: Events Outlive Code](#schema-evolution-events-outlive-code)
12. [Dead Letter Queues (DLQ)](#dead-letter-queues-dlq)
13. [Case Study: Uber's Event-Driven Architecture](#case-study-ubers-event-driven-architecture)
14. [Key References](#key-references)
15. [Practice Exercise](#practice-exercise)
16. [Common Mistakes](#common-mistakes)
17. [Discussion Questions](#discussion-questions)

---

## Sync vs Async Communication

### Synchronous

Client waits for the server to respond.

```
  Client ──── Request ────▶ Server
  Client ◀─── Response ─── Server

  ✓ Simple to implement
  ✓ Immediate feedback
  ✗ Client blocked during processing
  ✗ Cascading failures (server down → client stuck)
```

### Asynchronous

Client sends a message and continues. Processing happens in the background.

```
  Client ──── Message ────▶ Queue
  Client ◀─── ACK ─────── Queue (immediate)
  Client continues...

  Worker ◀──── Poll ───── Queue
  Worker ──── Process ──▶ Queue
  Worker ◀─── Done ──────
```

### When to Use Which

| Factor | Synchronous | Asynchronous |
|--------|------------|--------------|
| **Response time** | < 200ms required | Can tolerate seconds/minutes |
| **User experience** | Needs immediate feedback | Background processing OK |
| **Coupling** | Tight (caller depends on callee) | Loose (queue buffers) |
| **Failure isolation** | Cascading failures | Failures contained |
| **Throughput** | Limited by slowest service | Queue absorbs bursts |
| **Example** | Login, search, payment confirmation | Email sending, image processing, analytics |

---

## Message Queue Patterns

### Point-to-Point (Queue)

One message consumed by exactly one consumer.

```
  Producer ────▶ [Queue] ────▶ Consumer 1
                           ────▶ Consumer 2 (competing consumers)

  Use case: Task distribution, work queues
```

### Publish-Subscribe (Topic)

One message delivered to all subscribers.

```
  Publisher ────▶ [Topic]
                  ├──▶ Subscriber 1 (receives all messages)
                  ├──▶ Subscriber 2 (receives all messages)
                  └──▶ Subscriber 3 (receives all messages)

  Use case: Event broadcasting, notifications, fan-out
```

---

## Message Queue Comparison

| Feature | Kafka | RabbitMQ | SQS |
|---------|-------|----------|-----|
| **Model** | Distributed log | Smart broker | Managed queue |
| **Throughput** | Millions/sec | 50K+/sec | 3K+ (standard), 30K+ (FIFO) |
| **Ordering** | Per partition | Per queue | FIFO queue only |
| **Persistence** | Disk (retention-based) | Disk (optional) | Managed (4-14 days) |
| **Consumer model** | Pull (polling) | Push (broker delivers) | Long polling |
| **Complexity** | High (topics, partitions, offsets) | Medium (exchanges, bindings) | Low (managed) |
| **Use case** | Event streaming, logs, analytics | Task queues, RPC, routing | Simple async workflows |
| **Real systems** | LinkedIn, Netflix, Uber | Pivotal, many startups | AWS-native apps |

---

## Kafka Deep Dive

Kafka is the dominant message queue for high-throughput event streaming.

### Architecture

```
  ┌───────────────────────────────────────────────────┐
  │                  Kafka Cluster                    │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐         │
  │  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │         │
  │  └──────────┘  └──────────┘  └──────────┘         │
  │                                                   │
  │  Topic: "user-events" (3 partitions)              │
  │                                                   │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
  │  │Part. 0  │  │Part. 1  │  │Part. 2  │            │
  │  │msg0,msg3│  │msg1,msg4│  │msg2,msg5│            │
  │  │msg6,msg9│  │msg7     │  │msg8     │            │
  │  └─────────┘  └─────────┘  └─────────┘            │
  │                                                   │
  └───────────────────────────────────────────────────┘

  Producer ────▶ Topic (partitioned by key)
                    │
                    ▼
  Consumer Group:
  ┌─────────┐  ┌─────────┐
  │Consumer1│  │Consumer2│
  │Part. 0,1│  │Part. 2  │
  └─────────┘  └─────────┘
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Topic** | A category/feed of messages (like a table) |
| **Partition** | A topic is split into partitions for parallelism |
| **Offset** | Sequential ID for each message in a partition |
| **Consumer Group** | A set of consumers that share partitions |
| **Replication** | Each partition is replicated across brokers |

### Kafka vs RabbitMQ

| Factor | Kafka | RabbitMQ |
|--------|-------|----------|
| **Message retention** | Retained (hours/days) | Deleted after consumption |
| **Replay** | Yes (re-read from offset) | No (message gone after ACK) |
| **Ordering** | Per partition | Per queue |
| **Routing** | Consumer-side filtering | Broker-side (exchanges) |
| **Best for** | Event streaming, log aggregation | Task queues, RPC |

---

## Event-Driven Architecture

### Event Notification

Events describe what happened. Consumers decide what to do.

```
  Order Service ──── "OrderPlaced" ────▶ Event Bus
                    { order_id: 123,
                      user_id: 456,
                      total: 99.99 }

  Consumers:
  ├── Email Service: Sends confirmation email
  ├── Inventory Service: Reserves stock
  ├── Analytics Service: Records metric
  ├── Fraud Service: Checks for fraud
```

### Event-Carried State Transfer

Events carry the full state, not just the event type.

```
  "OrderPlaced" event:
  {
    order_id: 123,
    user_id: 456,
    items: [...],
    total: 99.99,
    shipping_address: {...},
    payment_method: {...}
  }

  Consumers don't need to call back to the order service.
  They have all the data they need.
```

---

## Event Sourcing

Store every state change as an immutable event, not just the current state.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import json

@dataclass
class Event:
    event_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1

class BankAccount:
    """Event-sourced bank account. State is derived from events."""

    def __init__(self, account_id: str):
        self.account_id = account_id
        self.balance = 0.0
        self.events: List[Event] = []

    def deposit(self, amount: float):
        event = Event("Deposited", {"amount": amount})
        self._apply(event)
        self.events.append(event)

    def withdraw(self, amount: float):
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        event = Event("Withdrawn", {"amount": amount})
        self._apply(event)
        self.events.append(event)

    def _apply(self, event: Event):
        if event.event_type == "Deposited":
            self.balance += event.data["amount"]
        elif event.event_type == "Withdrawn":
            self.balance -= event.data["amount"]

    @classmethod
    def from_events(cls, account_id: str, events: List[Event]) -> "BankAccount":
        """Reconstruct account state from event history."""
        account = cls(account_id)
        for event in events:
            account._apply(event)
            account.events.append(event)
        return account

    def snapshot(self) -> dict:
        """Save current state as a snapshot (optimization)."""
        return {
            "account_id": self.account_id,
            "balance": self.balance,
            "event_count": len(self.events),
            "last_event_timestamp": self.events[-1].timestamp if self.events else None
        }

# Usage:
account = BankAccount("acc_123")
account.deposit(1000)
account.withdraw(300)
account.deposit(200)
print(account.balance)  # 900

# Reconstruct from events:
reconstructed = BankAccount.from_events("acc_123", account.events)
print(reconstructed.balance)  # 900
```

```
  Traditional (current state):
  ┌───────────────────────────┐
  │  Account Balance: $900    │  ← Only the latest state.
  └───────────────────────────┘     How did it get here? No idea.

  Event Sourcing (event log):
  ┌──────────────────────────┐
  │  1. AccountCreated: $0   │
  │  2. Deposited:   +$1000  │  →  running balance $1000
  │  3. Withdrawn:    -$300  │  →  running balance  $700
  │  4. Deposited:    +$200  │  →  running balance  $900
  ├──────────────────────────┤
  │  Balance = $900          │  ← Derived by replaying events
  └──────────────────────────┘     (matches the code above)

  ✓ Complete audit trail
  ✓ Can reconstruct state at any point in time
  ✓ Natural fit for financial systems
  ✗ Query complexity (must replay events)
  ✗ Storage grows unbounded (need snapshots)
```

---

## CQRS (Command Query Responsibility Segregation)

Separate the write model from the read model.

```python
from dataclasses import dataclass
from typing import List
import json

# --- Write Model (Normalized) ---
@dataclass
class Order:
    id: str
    user_id: str
    items: List[dict]
    status: str = "pending"
    total: float = 0.0

class OrderWriteDB:
    """Write-optimized: normalized, supports transactions."""

    def __init__(self):
        self.orders = {}

    def create_order(self, order: Order):
        self.orders[order.id] = order
        # Publish event for read model sync
        self._publish_event("OrderCreated", order)

    def update_status(self, order_id: str, status: str):
        self.orders[order_id].status = status
        self._publish_event("OrderUpdated", self.orders[order_id])

    def _publish_event(self, event_type: str, order: Order):
        # In production: publish to Kafka/message queue.
        # Caution: writing the DB and then publishing separately is a
        # "dual write" — a crash between the two loses the event. See
        # "The Dual-Write Problem" below for the outbox pattern.
        print(f"EVENT: {event_type} -> {order.id}")

# --- Read Model (Denormalized) ---
class OrderReadDB:
    """Read-optimized: pre-joined, denormalized for fast queries."""

    def __init__(self):
        self.orders = {}  # Denormalized view

    def sync_from_events(self, event_type: str, order_data: dict):
        """Update read model from events (eventual consistency)."""
        if event_type == "OrderCreated":
            self.orders[order_data["id"]] = {
                "id": order_data["id"],
                "user_name": order_data.get("user_name", "Unknown"),
                "items_summary": f"{len(order_data['items'])} items",
                "total": order_data["total"],
                "status": order_data["status"],
            }
        elif event_type == "OrderUpdated":
            self.orders[order_data["id"]]["status"] = order_data["status"]

    def get_order(self, order_id: str) -> dict:
        """Fast read — no JOINs needed."""
        return self.orders.get(order_id)

    def get_user_orders(self, user_id: str) -> List[dict]:
        """Fast query — pre-joined data."""
        return [o for o in self.orders.values() if o.get("user_id") == user_id]

# Usage:
write_db = OrderWriteDB()
read_db = OrderReadDB()

# Write path (normalized)
order = Order(id="o1", user_id="u1", items=[{"name": "Widget"}], total=29.99)
write_db.create_order(order)

# Read path (denormalized, eventually consistent)
read_db.sync_from_events("OrderCreated", {"id": "o1", "user_name": "Alice",
                                           "items": [{"name": "Widget"}],
                                           "total": 29.99, "status": "pending"})
print(read_db.get_order("o1"))  # Fast read, no JOINs
```

```
  ┌───────────────────────────────────────────────────────┐
  │                                                       │
  │    Commands (writes)            Queries (reads)       │
  │                                                       │
  │   ┌────────────────┐         ┌────────────────┐       │
  │   │    Command     │         │     Query      │       │
  │   │    Handler     │         │    Handler     │       │
  │   └───────┬────────┘         └───────┬────────┘       │
  │           │                          │                │
  │           ▼                          ▼                │
  │   ┌────────────────┐         ┌────────────────┐       │
  │   │    Write DB    │ ──sync─▶│    Read DB     │       │
  │   │  (normalized)  │         │ (denormalized) │       │
  │   └────────────────┘         └────────────────┘       │
  │                                                       │
  │   Optimized for                 Optimized for         │
  │   correctness and               fast reads —          │
  │   transactions                  pre-joined, no        │
  │                                 JOINs at query time   │
  └───────────────────────────────────────────────────────┘

  ✓ Independent scaling of reads and writes
  ✓ Optimized data models for each use case
  ✓ Read model can be eventually consistent
  ✗ Complexity (two databases, sync logic)
```

---

## Delivery Guarantees

### At-Most-Once

```python
# At-most-once: ACK before processing (message may be lost)
def consume_at_most_once(message):
    # ACK first — if we crash, message is lost
    kafka_consumer.commit()

    # Process (if we crash here, message is gone)
    process_message(message)
```

```
  Producer ──▶ Queue ──▶ Consumer (process, ACK immediately)

  If consumer crashes after ACK but before processing:
  → Message is LOST

  ✓ Simple
  ✗ Data loss
  Use case: Metrics, logs (loss is acceptable)
```

### At-Least-Once

```python
# At-least-once: process first, then ACK (may duplicate)
def consume_at_least_once(message):
    # Process first
    process_message(message)

    # ACK after processing — if we crash before ACK, message redelivers
    kafka_consumer.commit()

# Handle duplicates with idempotency
def process_message(message):
    idempotency_key = message["id"]
    if redis.exists(f"processed:{idempotency_key}"):
        return  # Already processed, skip
    # ... do work ...
    redis.setex(f"processed:{idempotency_key}", 86400, "1")
```

```
  Producer ──▶ Queue ──▶ Consumer (process, then ACK)

  If consumer crashes after processing but before ACK:
  → Queue redelivers → Message is DUPLICATED

  ✓ No data loss
  ✗ Duplicates possible
  Use case: Most applications (handle with idempotency)
```

### Exactly-Once

```python
# Exactly-once via Kafka transactions
from confluent_kafka import Producer, Consumer, KafkaException

def consume_exactly_once(message):
    """Process + commit atomically via Kafka transactions."""
    # Start transaction
    producer.begin_transaction()

    try:
        # Process message
        result = process_message(message)

        # Produce output to another topic (within transaction)
        producer.produce("output-topic", value=json.dumps(result))

        # Commit transaction (atomic: process + produce + offset commit)
        producer.commit_transaction(offsets)
    except KafkaException:
        producer.abort_transaction()
        raise
```

```
  Kafka achieves this via:
  1. Producer: idempotent writes (producer ID + sequence number)
  2. Consumer: transactional consumption (read + process + commit atomically)

  ✓ No duplicates, no loss
  ✗ Complex, performance overhead
  Use case: Financial transactions, inventory updates
```

---

## The Dual-Write Problem: Outbox and CDC

Almost every event-driven example — including the CQRS one above — has the
same hidden bug. The service writes to its database, then publishes an
event:

```python
def place_order(order):
    db.insert(order)                         # 1. commit to the database
    kafka.send("orders", order_placed(order))  # 2. tell everyone else
```

These are two separate systems with no shared transaction, so every
failure mode between them leaves them disagreeing:

| What happens | Result |
|--------------|--------|
| Crash after step 1, before step 2 | Order exists; **no event**. Inventory never reserves, email never sends — silently, forever |
| Kafka is down at step 2 | Same, unless you fail the request — and then the order exists but the user saw an error |
| Publish first, then the DB write fails | Downstream services act on an order **that doesn't exist** |
| Retry step 2 after a timeout that actually succeeded | Duplicate event (handled by idempotent consumers — the easy case) |

Retries cannot fix the first row: the process that would retry is the one
that crashed. Wrapping both in a "transaction" does not work either, because
the database and the broker cannot commit atomically together.

### The Transactional Outbox

Write the event **into the same database, in the same transaction** as the
business change. A separate relay then publishes it:

```
  ┌──────────────────── one DB transaction ────────────────────┐
  │                                                            │
  │   INSERT INTO orders (...)          ──┐                     │
  │   INSERT INTO outbox (id, topic,    ──┤ both commit,        │
  │                       payload)        │ or neither does     │
  │                                                            │
  └──────────────────────────┬─────────────────────────────────┘
                             │
                ┌────────────▼────────────┐       ┌──────────┐
                │  Relay                  │       │          │
                │  read unpublished rows  │──────▶│  Kafka   │
                │  publish, mark as sent  │       │          │
                └─────────────────────────┘       └──────────┘
```

```python
def place_order(order):
    with db.transaction() as tx:
        tx.insert("orders", order)
        tx.insert("outbox", {
            "id": new_uuid(),            # doubles as the idempotency key
            "topic": "orders",
            "payload": order_placed(order),
        })
    # No Kafka call here. The request succeeds as soon as the DB commits.


def relay_once():
    """Run in a loop or on a schedule; safe to run more than one copy."""
    rows = db.query(
        "SELECT * FROM outbox WHERE sent_at IS NULL "
        "ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED"
    )
    for row in rows:
        kafka.send(row["topic"], row["payload"], key=row["id"])
        db.execute("UPDATE outbox SET sent_at = now() WHERE id = %s", row["id"])
```

The guarantee is **at-least-once**: if the relay crashes after publishing
but before marking the row, it publishes again on restart. That is why the
outbox row's `id` travels with the message — consumers deduplicate on it
(see Delivery Guarantees above). What the outbox removes is the *lost*
event, which no consumer-side technique can recover.

### Change Data Capture (CDC)

Instead of polling an outbox table, read the database's own replication
log — the Postgres WAL, the MySQL binlog — and turn committed changes into
events. Debezium is the common open-source tool.

| | Polling outbox | CDC (log-based) |
|---|---|---|
| Latency | Poll interval (typically 100 ms - 1 s) | Near real-time |
| Load on the database | A query every poll | Reads the log the DB already writes |
| Event shape | Exactly what you wrote — designed for consumers | Raw row changes, unless you CDC an outbox table |
| Operational cost | A loop in your service | A connector cluster to run and monitor |
| Good default for | Most teams, most services | High volume, or many tables feeding many consumers |

**The common combination:** use an outbox table for the event's *shape* and
CDC on that table for *delivery*. Consumers get deliberately designed
events, not leaked internal column names, and you avoid the polling query.

> **When you don't need any of this:** if losing an event is acceptable —
> analytics clicks, view counters — a direct publish is fine. Use the outbox
> where a missing event means a missing side effect someone will notice:
> payments, orders, inventory, notifications a user is waiting for.

---

## Stream Processing: Windows, Watermarks, and Late Data

A queue moves events from A to B. **Stream processing** computes over them while
they move: clicks per minute, fraud scores over the last hour, a dashboard
that is 5 seconds behind reality instead of a day. Kafka Streams, Apache Flink
and Spark Structured Streaming are the common engines; the concepts below
apply to all of them.

### Batch vs Stream

| | Batch | Stream |
|---|---|---|
| Input | Bounded: yesterday's files | Unbounded: events keep arriving |
| Latency | Minutes to hours | Milliseconds to seconds |
| Completeness | Easy: all the data is there when the job starts | Hard: when is "the 3pm minute" finished? |
| Reprocessing | Re-run the job | Replay the log from an offset |
| Typical use | Billing, training data, reports | Alerting, fraud, live dashboards, feature freshness |

Two architectures dominate. **Lambda** (Nathan Marz) runs a batch layer for
correct results and a speed layer for fresh approximate results, then merges
them. It works, but every metric is implemented twice and the two drift.
**Kappa** (Jay Kreps, 2014) keeps one streaming code path and reprocesses by
replaying the retained Kafka log into a new version of the job. Most teams
starting today choose Kappa unless a batch system already exists.

### Event Time vs Processing Time

Every event has two timestamps: when it **happened** (event time) and when the
processor **saw** it (processing time). They diverge constantly: a phone
buffers clicks in a tunnel, a consumer restarts and catches up, a partition lags.

```
  event time:      12:00:05   12:00:20   12:00:58      12:00:15
  arrival order:   ────●──────────●──────────●─────────────●────▶
                                                           ▲
                    this click happened at 12:00:15 but arrived after 12:00:58
```

Count by processing time and a consumer restart moves an hour of traffic into
one spike. Count by event time and results are correct, but you must decide
how long to wait for stragglers.

### Window Types

```
  Tumbling (fixed, non-overlapping): "clicks per minute"
  |── 0-60 ──|── 60-120 ──|── 120-180 ──|

  Sliding / hopping (overlapping): "clicks in the last 5 min, updated every min"
  |────── 0-300 ──────|
       |────── 60-360 ──────|
            |────── 120-420 ──────|

  Session (gap-based, per key): "one browsing session = activity with < 30 min gaps"
  |─●─●──●─|            |─●──●─|         |─●─|
           └── 30 min gap closes the session
```

### Watermarks: Deciding a Window Is Done

A **watermark** is the processor's running assertion: "I don't expect any more
events with event time earlier than *W*." When the watermark passes a window's
end, the window is emitted. The common heuristic is *bounded
out-of-orderness*: watermark = newest event time seen − allowed delay.

```python
"""Event-time tumbling windows with a watermark: count clicks per minute."""

from collections import defaultdict

WINDOW = 60          # seconds per tumbling window
MAX_DELAY = 10       # watermark lags the newest event time by this much


class TumblingWindowCounter:
    def __init__(self):
        self.open_windows = defaultdict(int)   # window start -> count
        self.max_event_time = 0
        self.late = []                          # side output: too late to count

    def watermark(self) -> int:
        """'No event older than this should still arrive.' A heuristic, not a promise."""
        return self.max_event_time - MAX_DELAY

    def on_event(self, event_time: int) -> list[str]:
        start = event_time - event_time % WINDOW
        if start + WINDOW <= self.watermark():
            self.late.append(event_time)        # its window was already emitted
            return []
        self.open_windows[start] += 1
        self.max_event_time = max(self.max_event_time, event_time)
        return self._emit_closed()

    def _emit_closed(self) -> list[str]:
        out = []
        for start in sorted(self.open_windows):
            if start + WINDOW <= self.watermark():   # window end has passed the watermark
                out.append(f"[{start:>3}, {start + WINDOW:>3})  clicks={self.open_windows.pop(start)}")
        return out


# Event times in ARRIVAL order. Mobile clients buffer offline, so order is not guaranteed.
arrivals = [5, 20, 61, 15, 58, 75, 66, 130, 50, 140]

counter = TumblingWindowCounter()
for t in arrivals:
    for line in counter.on_event(t):
        print(f"after event t={t:>3}: emit {line}")
print(f"late, sent to side output: {counter.late}")
```

```
after event t= 75: emit [  0,  60)  clicks=4
after event t=130: emit [ 60, 120)  clicks=3
late, sent to side output: [50]
```

Event `15` arrived after event `61` and was still counted, because the
watermark (51) hadn't yet passed its window's end (60). Event `50` arrived after
the watermark reached 120, so its window had already been emitted. The delay
setting is a **direct trade between latency and completeness**: a larger delay
emits later but drops less.

Late events need a deliberate policy, never silent loss:

| Policy | When to use it |
|--------|----------------|
| **Drop and count** | Dashboards where 0.01% loss is acceptable; still *measure* the drop rate |
| **Side output** | Route late events to a separate topic for a correcting batch job |
| **Allowed lateness / updates** | Keep window state longer and emit a corrected result; downstream must accept updates (upserts, not appends) |

### State and Exactly-Once

Windows, joins and aggregations are **stateful**: a crash must not lose the
counts accumulated so far. Engines checkpoint state together with the input
offsets it reflects, so recovery resumes from a consistent point. Flink takes
periodic distributed snapshots by flowing barrier markers through the job;
Kafka Streams keeps state in local stores backed by changelog topics and
commits offsets and outputs in one Kafka transaction. This gives
**exactly-once effects inside the engine**. Writes to external systems (a
database, an email API) are still at-least-once unless the sink is
transactional or idempotent, which brings back the rules from
[Delivery Guarantees](#delivery-guarantees).

### Worked Example: Ad-Click Aggregation

A classic design question ("count ad clicks per minute, for billing and live
dashboards") puts every idea in this section to work.

**Requirements**: 10 billion clicks per day (≈116,000 per second on average,
several times that at peak); clicks per ad per minute queryable within a minute;
top 100 ads over the last minute; counts used for billing, so they must be
exactly right eventually.

```
  ad servers ──▶ click log ──▶ Kafka "clicks"      ──▶ raw clicks to object
                              (partition by ad_id)     storage (source of truth)
                                    │
                                    ▼
                    stream job: dedupe by click_id; tumbling 1-min
                    event-time windows per ad_id; watermark + late output
                                    │
                                    ▼
                    OLAP store: upsert (ad_id, minute) → count
                    serves dashboards and top-K queries
                                    ▲
  nightly batch over raw clicks ────┘  recomputes yesterday exactly;
                                       billing uses this, not the live counts
```

The decisions worth defending:

- **Event time with a watermark.** Billing counts a click in the minute it
  happened, not when it arrived; late clicks go to a side output that the
  batch job folds in.
- **Deduplicate by click ID.** Retries from ad servers, and click fraud,
  produce repeats. Keep recent click IDs per partition (a keyed state with a
  TTL longer than the maximum lateness).
- **Upsert, don't increment, in the sink.** If the job restarts from a
  checkpoint and replays a minute, writing `count = 4,812` for `(ad_id,
  minute)` is idempotent; `count += 4,812` double-counts. This one choice
  turns at-least-once delivery into exactly-once *results*.
- **Batch reconciliation.** The stream gives fresh numbers; a nightly job over
  the raw clicks gives the final ones. Same logic, one codebase (Kappa-style
  replay), with the batch result overwriting the streaming one.

**Hot keys.** A viral ad can carry a large share of all clicks, and
partitioning by `ad_id` sends all of them to one worker. The fix is **two-phase
aggregation**: add a random salt to the key so partial counts spread across
workers, then merge the partials (at most one per salt) in a second step:

```python
"""Two-phase aggregation: spread a hot ad across workers, then merge partial counts."""

import random
import zlib
from collections import Counter

WORKERS = 8
rng = random.Random(3)


def worker_for(key: str) -> int:
    return zlib.crc32(key.encode()) % WORKERS          # stable across runs


# 1M clicks in one minute; one viral ad gets 40% of them.
clicks = ["ad-viral" if rng.random() < 0.4 else f"ad-{rng.randrange(50_000)}"
          for _ in range(1_000_000)]

# Phase 0 (naive): partition by ad_id. Every viral click lands on one worker.
naive = Counter(worker_for(ad) for ad in clicks)

# Phase 1: partition by (ad_id, random salt) and count partially on each worker.
SALTS = 8
partial = [Counter() for _ in range(WORKERS)]
for ad in clicks:
    salt = rng.randrange(SALTS)
    partial[worker_for(f"{ad}#{salt}")][ad] += 1
salted = [sum(c.values()) for c in partial]

# Phase 2: merge the partial counts per ad (at most SALTS partials per ad).
totals = Counter()
for c in partial:
    totals.update(c)

print(f"busiest worker, partitioned by ad_id:    {max(naive.values()):>7,} clicks")
print(f"busiest worker, partitioned by ad + salt: {max(salted):>7,} clicks")
print(f"merged count for ad-viral: {totals['ad-viral']:,} "
      f"(exact: {clicks.count('ad-viral'):,})")
```

```
busiest worker, partitioned by ad_id:    474,537 clicks
busiest worker, partitioned by ad + salt: 125,546 clicks
merged count for ad-viral: 399,873 (exact: 399,873)
```

The busiest worker goes from almost half of all traffic to its fair share
(1M ÷ 8), and the merged count is exact. **Top-K** then works per window:
because each ad's final count lives in one place after the merge, each worker's
local top 100 can be merged into an exact global top 100. When exact counts
aren't required, a count-min sketch
([Module 02](../02-databases-storage/README.md#storage-engines-b-tree-vs-lsm-tree))
finds heavy hitters in fixed memory.

---

## Schema Evolution: Events Outlive Code

A database migration changes data in one place at one time. Events don't work
that way: a topic holds messages written by every producer version from the
retention period, and a consumer replaying from the beginning reads all of
them. Producers and consumers deploy independently, so **every schema change
must work with versions written before it and readers deployed after it**.

| Compatibility | Meaning | Safe change | Deploy order |
|---------------|---------|-------------|--------------|
| **Backward** | New readers can read old data | Add a field *with a default*; remove a field | Consumers first |
| **Forward** | Old readers can read new data | Add a field; remove a field *that had a default* | Producers first |
| **Full** | Both | Add or remove only fields with defaults | Either |

Confluent Schema Registry, the common enforcement point for Kafka, defaults to
backward compatibility and rejects incompatible schemas at publish time,
before a bad producer can write anything. Note that the default checks a new
schema only against the *previous* version. For topics that consumers replay
from the beginning, use the transitive mode (`BACKWARD_TRANSITIVE`), which
checks against every version still in the topic.

The mechanism is **schema resolution**: the reader compares the writer's
schema with its own, fills defaults for fields the writer didn't have, and
ignores fields it doesn't know:

```python
"""Schema resolution: how a reader handles records written with another schema version."""

V1 = {"fields": [{"name": "order_id"}, {"name": "amount"}]}
V2 = {"fields": [{"name": "order_id"}, {"name": "amount"},
                 {"name": "currency", "default": "USD"}]}   # added WITH a default


def read(record: dict, reader_schema: dict) -> dict:
    out = {}
    for f in reader_schema["fields"]:
        if f["name"] in record:
            out[f["name"]] = record[f["name"]]
        elif "default" in f:
            out[f["name"]] = f["default"]          # old data, new field: use default
        else:
            raise ValueError(f"missing field {f['name']!r} with no default")
    return out                                      # fields unknown to the reader are ignored


old_event = {"order_id": "o-1", "amount": 30}                     # written by v1
new_event = {"order_id": "o-2", "amount": 45, "currency": "EUR"}  # written by v2

print("v2 reader, v1 data:", read(old_event, V2))   # backward compatible
print("v1 reader, v2 data:", read(new_event, V1))   # forward compatible

V3_BAD = {"fields": [{"name": "order_id"}, {"name": "amount"}, {"name": "region"}]}
try:
    read(old_event, V3_BAD)                         # added WITHOUT a default
except ValueError as e:
    print("v3 reader, v1 data: ERROR", e)
```

```
v2 reader, v1 data: {'order_id': 'o-1', 'amount': 30, 'currency': 'USD'}
v1 reader, v2 data: {'order_id': 'o-2', 'amount': 45}
v3 reader, v1 data: ERROR missing field 'region' with no default
```

Rules per format:

- **Avro**: the writer's schema travels with the data (or as a registry ID),
  and resolution works as above. Renames need an alias; type changes only
  along allowed promotions such as `int` → `long`.
- **Protobuf**: fields are identified by **number**, not name. Adding fields is
  safe; never reuse or renumber a field, and mark removed numbers `reserved` so
  no one reuses them later. Proto3 has no `required`, deliberately.
- **JSON**: nothing is enforced unless you add it (JSON Schema plus a registry).
  Consumers must be tolerant readers, and the risky changes (changing a
  field's meaning, unit or type) are the ones no tool catches.

The same expand/contract discipline applies to events as to APIs and database
columns ([Module 06](../06-microservices/README.md#deploying-safely-rollouts-flags-and-schema-migrations)):
add, migrate readers, then remove, never all at once.

---

## Dead Letter Queues (DLQ)

Messages that fail processing are sent to a DLQ for investigation.

```python
import json
import time
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class DLQConsumer:
    """Consumer with retry logic and dead letter queue."""

    max_retries: int = 3
    dlq_topic: str = "dead-letter-queue"

    def consume(self, message: dict, handler: Callable):
        for attempt in range(self.max_retries):
            try:
                handler(message)
                return  # Success
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s")
                time.sleep(wait_time)

        # All retries exhausted → send to DLQ
        self._send_to_dlq(message, "Max retries exceeded")

    def _send_to_dlq(self, message: dict, reason: str):
        dlq_message = {
            "original_message": message,
            "error_reason": reason,
            "timestamp": time.time(),
            "retries_exhausted": True
        }
        # In production: produce to DLQ topic
        kafka_producer.produce(self.dlq_topic, json.dumps(dlq_message))
        print(f"Message sent to DLQ: {message.get('id')}")
        alert_engineering_team(dlq_message)

# Usage:
def process_payment(message):
    # May fail due to external API errors
    response = payment_api.charge(message["amount"])
    if response.status != "success":
        raise PaymentFailedError(response.error)

consumer = DLQConsumer(max_retries=3)
consumer.consume({"id": "pay_123", "amount": 99.99}, process_payment)
```

```
  ┌────────┐     ┌──────────┐     ┌──────────┐
  │Producer│────▶│  Queue   │────▶│ Consumer │
  └────────┘     └──────────┘     └────┬─────┘
                                       │
                                  Failed (3 retries)
                                       │
                                       ▼
                                ┌──────────┐
                                │   DLQ    │
                                │(manual   │
                                │ review)  │
                                └──────────┘
```

**DLQ workflow**:
1. Message fails processing
2. Retry 3 times with exponential backoff
3. After 3 failures, send to DLQ
4. Alert engineering team
5. Manually inspect, fix, and replay

---

## Case Study: Uber's Event-Driven Architecture

Uber processes millions of events per second across ride matching, pricing, driver tracking, and payments.

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                Uber Event-Driven Architecture                 │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  EVENT SOURCES                                                │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Rider   │  │  Driver  │  │ Payment  │  │   GPS    │       │
│  │   App    │  │   App    │  │ Service  │  │ Tracker  │       │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘       │
│        │             │             │             │            │
│        └─────────────┴──────┬──────┴─────────────┘            │
│                             │                                 │
│              ┌──────────────▼──────────────┐                  │
│              │        Kafka Cluster        │                  │
│              │  millions of events/second  │                  │
│              │  partitioned by ride_id     │                  │
│              └──────────────┬──────────────┘                  │
│                             │                                 │
│        ┌────────────────────┼────────────────────┐            │
│        │                    │                    │            │
│  ┌─────▼──────┐      ┌──────▼─────┐      ┌───────▼────┐       │
│  │  Pricing   │      │  Matching  │      │ Analytics  │       │
│  │   Engine   │      │   Engine   │      │  Pipeline  │       │
│  └────────────┘      └────────────┘      └────────────┘       │
│                                                               │
│  Consumers are independent: Analytics falling behind does     │
│  not slow Matching, because each consumer group tracks its    │
│  own offsets.                                                 │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Kafka as the backbone**: All inter-service communication goes through Kafka. Services are fully decoupled — they don't know about each other, only about event topics.

2. **Event ordering by ride ID**: Each ride's events are in the same Kafka partition (partitioned by ride_id). This ensures events for the same ride are processed in order.

3. **Separate read and write paths**: Write-heavy services (GPS tracking at 1000+ updates/second per driver) write to Kafka. Read-optimized services consume and build materialized views.

4. **Schema evolution**: Kafka Schema Registry ensures backward compatibility as event schemas evolve. New fields are added with defaults; old consumers ignore new fields.

5. **Exactly-once processing**: Critical for payments. Uber uses Kafka transactions to ensure payment events are processed exactly once, even with consumer failures.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Designing Data-Intensive Applications (Ch. 11) | Book | Event-driven architecture |
| "Designing Event-Driven Systems" (Ben Stopford) | Book | Kafka architecture patterns |
| Kafka Documentation | Docs | Partitions, consumer groups |
| RabbitMQ Tutorials | Docs | Exchange types, routing |
| Uber Engineering Blog | Blog | Kafka at scale |
| "Streaming 101" and "Streaming 102" (Tyler Akidau, O'Reilly Radar) | Article | Event time, windows, watermarks |
| "Questioning the Lambda Architecture" (Jay Kreps, 2014) | Article | The case for Kappa |
| System Design Interview Vol. 2 (Ch. 6, Ad Click Event Aggregation) — Alex Xu & Sahn Lam | Book | The worked example's full interview treatment |
| Designing Data-Intensive Applications (Ch. 4, Encoding and Evolution) | Book | Avro, Protobuf and compatibility |
| [Confluent: Schema evolution and compatibility](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) | Docs | Compatibility types and upgrade order |

---

## Practice Exercise

**20-minute design**: Design an event-driven order system:

When a user places an order:
1. Charge their card (payment service)
2. Update inventory (inventory service)
3. Send confirmation email (email service)
4. Update analytics (analytics service)

**Key decisions**:
1. Which events do you need?
2. What happens if the email service is down?
3. How do you handle duplicate events?
4. How do you track the order's progress through the pipeline?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Believing "exactly-once delivery" exists** | Over a network it's impossible; Kafka gives exactly-once *processing* within its own transaction boundary | At-least-once delivery plus idempotent consumers |
| **At-least-once without idempotency** | Redelivery is normal, not exceptional — duplicate charges and double-sent emails follow | Deduplicate on a stable business key before doing work |
| **Writing the DB, then publishing the event** | Two systems, no shared transaction: a crash between them loses the event permanently, and no retry can recover it | Transactional outbox — write the event in the same DB transaction, relay it afterwards (or CDC) |
| **Partitioning by a random key when order matters** | Kafka orders within a partition only; a ride's events land on different partitions and process out of order | Partition by the entity whose order matters (`ride_id`, `account_id`) |
| **Partitioning by a hot key** | One partition takes 10x the traffic; a single consumer becomes the bottleneck | Choose a high-cardinality key, or add a salt and re-aggregate downstream |
| **No dead letter queue** | A permanently-bad message retries forever and blocks its partition | DLQ after bounded retries, with an alert and a replay path |
| **Retrying non-retryable errors** | A malformed payload will fail identically 1,000 times | Split transient (network, 5xx) from permanent (validation) and DLQ the latter at once |
| **Async for work the user is waiting on** | "Queued" isn't "done" — a checkout that returns before payment clears misleads the user | Keep the user-blocking path synchronous; make only side effects async |
| **Windowing by processing time** | A consumer restart or lag spike moves hours of events into one window | Window by event time, with a watermark and an explicit late-data policy |
| **Incrementing counters in the sink of a stream job** | A replay after a restart adds the same window twice | Upsert the window's final value keyed by (key, window) |
| **Adding a required event field without a default** | Old events in the topic, and replays, can no longer be read | Add fields with defaults; enforce compatibility in a schema registry |
| **Event sourcing with no snapshots** | Replay time grows without bound; a 10-year account takes minutes to load | Snapshot periodically and replay only events since the snapshot |
| **Events carrying only IDs when consumers need data** | Every consumer calls back to the producer, recreating the coupling the queue removed | Event-carried state transfer for the fields consumers actually read |

---

## Discussion Questions

1. You're building an e-commerce order system. When a user places an order, you need to: (a) charge their card, (b) update inventory, (c) send confirmation email, (d) update analytics. Design this with event-driven architecture.

2. What's the difference between at-least-once and exactly-once delivery? When is each acceptable?

3. Explain event sourcing to a junior engineer. What are the benefits and drawbacks compared to storing current state?

4. You're using Kafka and notice one partition has 10x more messages than others. What's happening and how do you fix it?

5. Design a dead letter queue workflow for a payment processing system. What happens after a message lands in the DLQ?

6. A real-time dashboard counts ad clicks per minute by event time with a 10-second watermark delay. Finance reports that the dashboard total is 2% lower than the next day's billing batch. Where did the 2% go, and what would you change?

   **Model answer**: Most likely late events: clicks buffered on mobile devices or delayed by a lagging partition arrive after the watermark has closed their window and are dropped. First measure it: count late events per window instead of discarding them silently. Then pick a policy per consumer. The dashboard can keep its short delay, because freshness matters more than the last 2% there. Billing must not depend on it, so route late events to a side output that a correcting job merges, or allow lateness and emit updated window results to an upsert sink. Raising the delay to cover the long tail would fix completeness at the cost of a dashboard minutes behind. A Kappa design also lets you replay the log to recompute any window exactly.


7. A team wants to rename the `amount` field in the `OrderPlaced` event to `amount_cents` and change it from dollars (float) to cents (integer). The topic has 30 days of retention and five consuming services. How do you roll this out?

   **Model answer**: It is two breaking changes at once, a rename and a change of meaning, and no compatibility checker catches the unit change. Expand/contract instead: add `amount_cents` as a new optional field and have producers write both fields; migrate each consumer to read `amount_cents` and fall back to converting `amount` when it is absent, because events up to 30 days old (and any replay) won't have it; once every consumer is migrated and old events have aged out of retention (or a replay path is confirmed to handle the fallback), stop writing `amount` and remove it with a forward-compatible schema change. Never reuse the old name with a new meaning: a consumer you forgot would read cents as dollars and be off by 100× without any error.
---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 07: Reliability Engineering](../07-reliability/README.md) | Exponential backoff, circuit breakers, and retry budgets are the reliability primitives that make the DLQ and delivery-guarantee patterns here actually survive production |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Exactly-once processing and per-partition ordering both lean on the same consensus and ordering guarantees covered there in depth |
| [Module 12: Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md) | Walks through the exact charge-inventory-notify pipeline used in this module's practice exercise, with a full idempotency implementation for payment events |
| [Module 14: API Design](../14-api-design/README.md) | Stripe's Idempotency-Key header is the request/response mirror of the idempotent-consumer pattern used here for at-least-once message processing |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│                 Async Systems — Key Takeaways                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. "Exactly-once delivery" doesn't exist over a network —     │
│     design for at-least-once plus idempotent consumers, always │
│  2. Ack after processing, not before — acking early is how     │
│     messages get lost, not how they get processed twice        │
│  3. Partition by the entity whose order matters (`ride_id`,    │
│     `account_id`) — a random or hot key either scrambles       │
│     ordering or bottlenecks one consumer                       │
│  4. Every retry loop needs a DLQ at the far end — unbounded    │
│     retries just block the partition forever                   │
│  5. Split transient failures from permanent ones before you    │
│     retry — a malformed payload will fail the 1,000th attempt  │
│     exactly like the first                                     │
│  6. Async is for side effects, not for what the user is waiting│
│     on — "queued" is not the same promise as "done"            │
│  7. Event-carried state transfer beats event notification once │
│     consumers start calling back for details — that call-back  │
│     recreates the coupling the queue was supposed to remove    │
│  8. Snapshot event-sourced aggregates — without one, replay    │
│     time grows with the account's entire history               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 04: Load Balancing and Networking](../04-load-balancing/README.md)

**Next:** [Module 06: Microservices Architecture](../06-microservices/README.md)

---

*Module 05 of 26 in the System Design Playground*
