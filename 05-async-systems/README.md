# Module 05: Asynchronous Systems and Message Queues

> **Decouple services and handle work asynchronously.** Not everything needs a synchronous response. Async systems improve resilience, throughput, and user experience by offloading work to background processors.

## Learning Objectives

- Understand sync vs async communication patterns
- Design event-driven architectures with Kafka and RabbitMQ
- Implement event sourcing and CQRS patterns
- Handle delivery guarantees (at-least-once, exactly-once)
- Design dead letter queues for error handling

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
  ┌─────────────────────────────────────────────────┐
  │                  Kafka Cluster                    │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
  │  │ Broker 1 │  │ Broker 2 │  │ Broker 3 │      │
  │  └──────────┘  └──────────┘  └──────────┘      │
  │                                                   │
  │  Topic: "user-events" (3 partitions)             │
  │                                                   │
  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
  │  │Part. 0  │  │Part. 1  │  │Part. 2  │         │
  │  │msg0,msg3│  │msg1,msg4│  │msg2,msg5│         │
  │  │msg6,msg9│  │msg7     │  │msg8     │         │
  │  └─────────┘  └─────────┘  └─────────┘         │
  │                                                   │
  └─────────────────────────────────────────────────┘

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

```
  Traditional (current state):
  ┌──────────────────────────┐
  │  Account Balance: $500    │  ← Only the latest state
  └──────────────────────────┘

  Event Sourcing (event log):
  ┌──────────────────────────┐
  │  1. AccountCreated: $0   │
  │  2. Deposited: +$1000    │
  │  3. Withdrawn: -$300     │
  │  4. Deposited: -$200     │
  │  5. Balance = $500       │  ← Derived from events
  └──────────────────────────┘

  ✓ Complete audit trail
  ✓ Can reconstruct state at any point in time
  ✓ Natural fit for financial systems
  ✗ Query complexity (must replay events)
  ✗ Storage grows unbounded (need snapshots)
```

---

## CQRS (Command Query Responsibility Segregation)

Separate the write model from the read model.

```
  ┌──────────────────────────────────────────────┐
  │                                               │
  │   Commands (Writes)      Queries (Reads)     │
  │   ┌───────────┐         ┌───────────┐       │
  │   │  Command  │         │  Query    │       │
  │   │  Handler  │         │  Handler  │       │
  │   └─────┬─────┘         └─────┬─────┘       │
  │         │                      │             │
  │         ▼                      ▼             │
  │   ┌───────────┐         ┌───────────┐       │
  │   │  Write DB │──sync──▶│  Read DB  │       │
  │   │ (Normalized)│        │(Denormalized)│    │
  │   └───────────┘         └───────────┘       │
  │                                               │
  │   Write DB: Optimized for writes             │
  │   Read DB: Optimized for reads (pre-joined)  │
  └──────────────────────────────────────────────┘

  ✓ Independent scaling of reads and writes
  ✓ Optimized data models for each use case
  ✓ Read model can be eventually consistent
  ✗ Complexity (two databases, sync logic)
```

---

## Delivery Guarantees

### At-Most-Once

Message may be lost, never duplicated.

```
  Producer ──▶ Queue ──▶ Consumer (process, ACK immediately)
  
  If consumer crashes after ACK but before processing:
  → Message is LOST

  ✓ Simple
  ✗ Data loss
  Use case: Metrics, logs (loss is acceptable)
```

### At-Least-Once

Message is never lost, may be duplicated.

```
  Producer ──▶ Queue ──▶ Consumer (process, then ACK)
  
  If consumer crashes after processing but before ACK:
  → Queue redelivers → Message is DUPLICATED

  ✓ No data loss
  ✗ Duplicates possible
  Use case: Most applications (handle with idempotency)
```

### Exactly-Once

Message processed exactly once. The holy grail.

```
  Kafka achieves this via:
  1. Producer: idempotent writes (producer ID + sequence number)
  2. Consumer: transactional consumption (read + process + commit atomically)

  ✓ No duplicates, no loss
  ✗ Complex, performance overhead
  Use case: Financial transactions, inventory updates
```

---

## Dead Letter Queues (DLQ)

Messages that fail processing are sent to a DLQ for investigation.

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
┌─────────────────────────────────────────────────────────┐
│                Uber Event-Driven Architecture            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Event Sources:                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │Rider   │ │Driver  │ │Payment │ │GPS     │          │
│  │App     │ │App     │ │Service │ │Tracker │          │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘          │
│      │          │          │          │                 │
│      └──────────┼──────────┼──────────┘                 │
│                 │          │                            │
│         ┌───────▼──────────▼───────┐                   │
│         │    Kafka Cluster          │                   │
│         │    (millions of events/s) │                   │
│         └───────────┬───────────────┘                   │
│                     │                                   │
│    ┌────────────────┼────────────────┐                 │
│    │                │                │                  │
│    ▼                ▼                ▼                  │
│ ┌──────┐      ┌──────┐        ┌──────┐               │
│ │Pricing│      │Matching│      │Analytics│             │
│ │Engine │      │Engine  │      │Pipeline│              │
│ └──────┘      └──────┘        └──────┘               │
│                                                          │
└─────────────────────────────────────────────────────────┘
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

---

## Discussion Questions

1. You're building an e-commerce order system. When a user places an order, you need to: (a) charge their card, (b) update inventory, (c) send confirmation email, (d) update analytics. Design this with event-driven architecture.

2. What's the difference between at-least-once and exactly-once delivery? When is each acceptable?

3. Explain event sourcing to a junior engineer. What are the benefits and drawbacks compared to storing current state?

4. You're using Kafka and notice one partition has 10x more messages than others. What's happening and how do you fix it?

5. Design a dead letter queue workflow for a payment processing system. What happens after a message lands in the DLQ?

---

**Previous**: [Load Balancing and Networking](../04-load-balancing/README.md)
**Next**: [Microservices Architecture](../06-microservices/README.md)
