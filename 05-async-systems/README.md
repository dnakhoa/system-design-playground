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
        # In production: publish to Kafka/message queue
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
