# Module 12: Design Case — Payment System and E-commerce

> **High-stakes transactional systems.** Payment systems demand strong consistency, idempotency, and audit trails. E-commerce adds inventory management, flash sales, and complex order lifecycles.

## Learning Objectives

- Design a payment system with idempotency and exactly-once processing
- Implement inventory management with race condition prevention
- Design flash sale architectures that handle traffic spikes
- Handle order lifecycle state machines

---

## Part 1: Payment System

### Requirements

- **Functional**: Process payments, refunds, reconciliation, support multiple payment methods
- **Scale**: 10K transactions/second, $1B daily volume
- **Latency**: <500ms for payment confirmation
- **Consistency**: Strong (no double charges, no lost payments)
- **Compliance**: PCI DSS, SOC 2

### Payment Flow

```
┌─────────────────────────────────────────────────────────┐
│                Payment Processing Flow                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Client → Payment Service → Payment Gateway → Bank       │
│                                                          │
│  1. Client submits payment                               │
│     { card: "4242...", amount: 99.99, order_id: "123" } │
│                                                          │
│  2. Payment Service:                                     │
│     a. Validate input                                    │
│     b. Check idempotency (order_id already processed?)   │
│     c. Create payment record (status: PENDING)          │
│     d. Call payment gateway (Stripe, Adyen, etc.)       │
│                                                          │
│  3. Payment Gateway:                                     │
│     a. Tokenize card                                     │
│     b. fraud check                                       │
│     c. Route to card network (Visa, Mastercard)          │
│     d. Bank approves/declines                           │
│     e. Return result                                    │
│                                                          │
│  4. Payment Service:                                     │
│     a. Update payment status (COMPLETED / FAILED)       │
│     b. Notify order service                              │
│     c. Publish event to Kafka (for analytics)           │
│                                                          │
│  5. Client receives confirmation                         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Idempotency

The most critical property in payment systems. Each payment must be processed exactly once.

```
  Problem:
  1. Client sends payment request
  2. Payment succeeds at bank
  3. Response lost (network timeout)
  4. Client retries (thinks it failed)
  5. DOUBLE CHARGE!

  Solution: Idempotency keys

  Client sends: { order_id: "123", amount: 99.99, idempotency_key: "abc-123" }
  
  Payment Service:
  1. Check: Has idempotency_key "abc-123" been processed?
  2. No → Process payment, store {key: "abc-123", result: SUCCESS}
  3. Yes → Return stored result (don't process again)

  Storage: Redis with TTL (24 hours)
  SET idempotency:abc-123 EX 86400
```

### Exactly-Once Processing

```
  ┌─────────────────────────────────────────────────┐
  │  Exactly-Once Payment Processing                  │
  │                                                   │
  │  1. Begin transaction                            │
  │  2. Check idempotency key in DB                   │
  │  3. If exists → return cached result             │
  │  4. Process payment with gateway                  │
  │  5. Store result with idempotency key             │
  │  6. Commit transaction                            │
  │                                                   │
  │  If crash at any point:                           │
  │  - Before commit: Transaction rolled back         │
  │  - After commit: Idempotency key prevents retry  │
  └─────────────────────────────────────────────────┘
```

### Reconciliation

Daily reconciliation ensures all systems agree on transaction state.

```
  ┌─────────────────────────────────────────────────┐
  │  Reconciliation Process                           │
  │                                                   │
  │  End of day:                                      │
  │  1. Fetch all transactions from our DB           │
  │  2. Fetch all transactions from payment gateway  │
  │  3. Match by transaction_id                       │
  │                                                   │
  │  Match status:                                    │
  │  ✓ Matched: Both systems agree                   │
  │  ⚠ Mismatch: Amount or status differs            │
  │  ✗ Missing in gateway: Payment we think succeeded│
  │  ✗ Missing in our DB: Payment we missed          │
  │                                                   │
  │  Auto-resolve: 95%+ match automatically          │
  │  Manual review: Remaining 5% flagged for review  │
  └─────────────────────────────────────────────────┘
```

---

## Part 2: E-commerce System

### Order Lifecycle

```
  ┌─────────────────────────────────────────────────┐
  │              Order State Machine                   │
  │                                                   │
  │  ┌──────────┐  payment  ┌──────────┐            │
  │  │  PENDING │──────────▶│  PAID    │            │
  │  └──────────┘           └────┬─────┘            │
  │       │                      │                   │
  │  cancel│               fulfill│                   │
  │       ▼                      ▼                   │
  │  ┌──────────┐          ┌──────────┐             │
  │  │CANCELLED │          │ FULFILLING│             │
  │  └──────────┘          └────┬─────┘             │
  │                              │                    │
  │                        ship│                      │
  │                              ▼                    │
  │                         ┌──────────┐             │
  │                         │ SHIPPED  │             │
  │                         └────┬─────┘             │
  │                              │                    │
  │                        deliver│                    │
  │                              ▼                    │
  │                         ┌──────────┐             │
  │                         │ DELIVERED│             │
  │                         └────┬─────┘             │
  │                              │                    │
  │                        refund│                    │
  │                              ▼                    │
  │                         ┌──────────┐             │
  │                         │ REFUNDED │             │
  │                         └──────────┘             │
  └─────────────────────────────────────────────────┘
```

### Inventory Management

The classic race condition problem:

```
  Problem: Two users buy the last item simultaneously

  User A: Check stock → 1 remaining → Buy → Stock = 0 ✓
  User B: Check stock → 1 remaining → Buy → Stock = -1 ✗ (oversold!)

  Solution 1: Pessimistic locking
  SELECT stock FROM inventory WHERE product_id = 123 FOR UPDATE;
  -- Now locked, other transactions wait
  UPDATE inventory SET stock = stock - 1 WHERE product_id = 123 AND stock > 0;

  Solution 2: Optimistic locking
  UPDATE inventory SET stock = stock - 1, version = version + 1
  WHERE product_id = 123 AND stock > 0 AND version = 5;
  -- If affected_rows = 0, version changed → retry

  Solution 3: Atomic operation
  UPDATE inventory SET stock = stock - 1
  WHERE product_id = 123 AND stock >= 1;
  -- Database ensures atomicity
```

### Flash Sale Architecture

Flash sales create massive traffic spikes (100x normal).

```
┌─────────────────────────────────────────────────────────┐
│              Flash Sale Architecture                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Before sale:                                           │
│  1. Pre-warm cache with product details                 │
│  2. Pre-compute inventory in Redis (atomic DECR)       │
│  3. Queue-based entry (virtual waiting room)           │
│                                                          │
│  During sale:                                           │
│  1. User enters virtual queue                           │
│  2. Queue assigns position: "You are #1,234 in line"   │
│  3. As users ahead complete/fail, position advances    │
│  4. When it's your turn: 15-minute window to purchase  │
│                                                          │
│  Purchase flow:                                         │
│  1. Redis DECR inventory:{product_id}                   │
│  2. If result >= 0: Reserve item (TTL: 10 minutes)     │
│  3. Process payment                                     │
│  4. If payment succeeds: Confirm reservation            │
│  5. If payment fails: INCR inventory back               │
│                                                          │
│  Key optimizations:                                     │
│  - All reads from Redis (no DB until payment)           │
│  - Payment processed async (queue)                      │
│  - Rate limiting per user (1 purchase per user)         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Cart Design

```
  ┌─────────────────────────────────────────────────┐
  │  Cart Storage Strategy                            │
  │                                                   │
  │  Logged-in users:                                 │
  │  Redis: cart:{user_id} → Hash of product:quantity │
  │  MySQL: carts table (durable backup)              │
  │                                                   │
  │  Guest users:                                     │
  │  Redis: cart:{session_id} → Hash of product:qty  │
  │  TTL: 7 days                                      │
  │  On login: Merge guest cart with user cart        │
  │                                                   │
  │  Cart operations:                                 │
  │  HSET cart:123 product_456 2  (add 2 of product) │
  │  HGET cart:123 product_456     (get quantity)     │
  │  HDEL cart:123 product_456     (remove product)  │
  │  HGETALL cart:123              (get all items)   │
  └─────────────────────────────────────────────────┘
```

---

## Design Comparison

| Aspect | Payment System | E-commerce |
|--------|--------------|------------|
| **Consistency** | Strong (financial) | Strong (inventory) |
| **Idempotency** | Critical | Important |
| **Latency** | <500ms | <200ms (browsing) |
| **Peak traffic** | Steady | Flash sales (100x) |
| **Compliance** | PCI DSS | Less strict |

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| Stripe Documentation | Docs | Payment processing best practices |
| System Design Interview (Ch. 8-9) | Book | Payment system, e-commerce |
| "Building Microservices" | Book | Order lifecycle, saga pattern |
| AWS Architecture Blog | Blog | Flash sale patterns |

---

**Previous**: [Design Case — Distributed File Storage and Video Streaming](../11-case-storage-streaming/README.md)
**Next**: [LLM Inference Serving Architecture](../13-llm-inference-serving/README.md)
