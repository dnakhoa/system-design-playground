# Module 06: Microservices Architecture

> **Design for team scale and deployment independence.** Microservices let teams own their services end-to-end, deploy independently, and scale separately — but they introduce distributed systems complexity.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 05 | Asynchronous Systems and Message Queues | [../05-async-systems/](../05-async-systems/) |
| **Module 06** | **Microservices Architecture** | **(current)** |
| Module 07 | Reliability Engineering | [../07-reliability/](../07-reliability/) |

---

## Learning Objectives

- Decide between monolith and microservices
- Decompose systems using domain-driven design
- Implement distributed transactions with the saga pattern
- Design service discovery and API versioning
- Roll out changes safely with canaries, feature flags and expand/contract schema migrations
- Understand observability in microservices

---

## Table of Contents

1. [Monolith vs Microservices](#monolith-vs-microservices)
2. [Domain-Driven Decomposition](#domain-driven-decomposition)
3. [Inter-Service Communication](#inter-service-communication)
4. [Saga Pattern](#saga-pattern)
5. [Service Discovery](#service-discovery)
6. [API Versioning](#api-versioning)
7. [Deploying Safely: Rollouts, Flags, and Schema Migrations](#deploying-safely-rollouts-flags-and-schema-migrations)
8. [Observability in Microservices](#observability-in-microservices)
9. [Case Study: Netflix Microservices](#case-study-netflix-microservices)
10. [Key References](#key-references)
11. [Practice Exercise](#practice-exercise)
12. [Common Mistakes](#common-mistakes)
13. [Discussion Questions](#discussion-questions)

---

## Monolith vs Microservices

### The Monolith

All code in one deployable unit.

```
  ┌───────────────────────────────────┐
  │           Monolith                │
  │  ┌──────┐ ┌──────┐ ┌───────┐      │
  │  │User  │ │Order │ │Payment│      │
  │  │Module│ │Module│ │Module │      │
  │  └──────┘ └──────┘ └───────┘      │
  │  ┌──────┐ ┌──────┐ ┌──────┐       │
  │  │Email │ │Search│ │Report│       │
  │  │Module│ │Module│ │Module│       │
  │  └──────┘ └──────┘ └──────┘       │
  └───────────────────────────────────┘

  ✓ Simple deployment (one artifact)
  ✓ Simple debugging (one codebase)
  ✓ Strong consistency (shared database)
  ✗ All-or-nothing deployment
  ✗ Scaling everything together (wasteful)
  ✗ Team coupling (everyone steps on each other)
```

### Microservices

Each service is independently deployable and scalable.

```
  ┌─────────┐ ┌─────────┐ ┌─────────┐
  │  User   │ │  Order  │ │ Payment │
  │ Service │ │ Service │ │ Service │
  │ ┌─────┐ │ │ ┌─────┐ │ │ ┌─────┐ │
  │ │ DB  │ │ │ │ DB  │ │ │ │ DB  │ │
  │ └─────┘ │ │ └─────┘ │ │ └─────┘ │
  └────┬────┘ └────┬────┘ └────┬────┘
       │           │           │
       └───────────┼───────────┘
                   │
            ┌──────▼──────┐
            │Service Mesh │
            │  / API GW   │
            └─────────────┘

  ✓ Independent deployment
  ✓ Independent scaling
  ✓ Team ownership (you build it, you run it)
  ✗ Distributed system complexity
  ✗ Network latency between services
  ✗ Data consistency challenges
```

### Decision Framework

| Factor | Stay Monolith | Go Microservices |
|--------|--------------|------------------|
| **Team size** | < 10 engineers | > 20 engineers |
| **Deployment frequency** | Weekly | Multiple times/day |
| **Scale requirements** | Uniform | Different per component |
| **Domain complexity** | Simple, cohesive | Complex, multiple bounded contexts |
| **Organizational structure** | Single team | Multiple teams |
| **Maturity** | Early stage | Established, well-understood domain |

**Start with a monolith. Split when you feel the pain.** — Martin Fowler

---

## Domain-Driven Decomposition

### Bounded Contexts

Each microservice owns a specific business domain with its own language and model.

```
  ┌───────────────────────────────────────────────┐
  │              E-Commerce Domain                │
  │                                               │
  │  ┌─────────────┐  ┌─────────────┐             │
  │  │   Catalog   │  │   Ordering  │             │
  │  │  Context    │  │   Context   │             │
  │  │             │  │             │             │
  │  │ Product     │  │ Order       │             │
  │  │ Category    │  │ LineItem    │             │
  │  │ Price       │  │ Cart        │             │
  │  └─────────────┘  └─────────────┘             │
  │                                               │
  │  ┌─────────────┐  ┌──────────────┐            │
  │  │  Inventory  │  │  Payment     │            │
  │  │  Context    │  │  Context     │            │
  │  │             │  │              │            │
  │  │ Stock       │  │ Transaction  │            │
  │  │ Warehouse   │  │ PaymentMethod│            │
  │  │ Shipment    │  │ Invoice      │            │
  │  └─────────────┘  └──────────────┘            │
  └───────────────────────────────────────────────┘

  Each context = one microservice
  Each service has its own data model (no shared database)
```

### Decomposition Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **By business capability** | Each service = one business function | User Service, Order Service, Payment Service |
| **By subdomain** | Each service = one bounded context | Catalog, Inventory, Shipping, Billing |
| **By use case** | Each service = one user journey | Checkout Service, Search Service |
| **By data ownership** | Each service owns its data exclusively | User DB owned by User Service only |

---

## Inter-Service Communication

### REST (Synchronous)

```
  Order Service ──── HTTP GET ────▶ User Service
  Order Service ◀─── JSON Response ─ User Service

  ✓ Simple, widely understood
  ✓ Cacheable (HTTP caching)
  ✗ Synchronous (blocking)
  ✗ Tight coupling (caller depends on callee availability)
```

### gRPC (Synchronous, Binary)

```protobuf
  service UserService {
    rpc GetUser(GetUserRequest) returns (User);
    rpc ListUsers(ListUsersRequest) returns (stream User);
  }

  Order Service ──── gRPC call ────▶ User Service
  Order Service ◀─── Protobuf ────── User Service

  ✓ Binary protocol (fast, compact)
  ✓ Streaming support
  ✓ Strongly typed (protobuf)
  ✗ Browser support limited
  ✗ Harder to debug than REST
```

### Message Queue (Asynchronous)

```
  Order Service ──── "OrderCreated" ────▶ Kafka
                                            │
                              ┌──────────────┼──────────────┐
                              │              │              │
                              ▼              ▼              ▼
                         Inventory      Email         Analytics
                         Service        Service       Service

  ✓ Loose coupling
  ✓ Fault tolerant (queue buffers failures)
  ✗ Eventual consistency
  ✗ Complexity (ordering, idempotency)
```

### Communication Pattern Selection

| Factor | REST | gRPC | Message Queue |
|--------|------|------|---------------|
| **Latency** | Medium | Low | Variable |
| **Coupling** | Tight | Tight | Loose |
| **Streaming** | No | Yes | N/A |
| **Complexity** | Low | Medium | High |
| **Use case** | Public APIs | Internal services | Event-driven, async |

---

## Saga Pattern

Distributed transactions across multiple services. No 2PC (two-phase commit) — use compensating actions instead.

### Choreography-Based Saga

Each service listens for events and decides what to do next.

```python
from dataclasses import dataclass
from typing import Callable
import json

# Event bus (simplified in-memory version)
class EventBus:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event_type: str, handler: Callable):
        self.handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, data: dict):
        for handler in self.handlers.get(event_type, []):
            handler(data)

bus = EventBus()

# --- Order Service ---
def create_order(order_id: str, items: list):
    # Save order to DB
    db.save_order({"id": order_id, "items": items, "status": "created"})
    bus.publish("OrderCreated", {"order_id": order_id, "items": items})

def on_order_confirmed(data):
    db.update_order_status(data["order_id"], "confirmed")

def on_order_cancelled(data):
    db.update_order_status(data["order_id"], "cancelled")

bus.subscribe("OrderConfirmed", on_order_confirmed)
bus.subscribe("OrderCancelled", on_order_cancelled)

# --- Inventory Service ---
def on_order_created_reserve_stock(data):
    try:
        reserve_stock(data["items"])
        bus.publish("StockReserved", {"order_id": data["order_id"]})
    except OutOfStockError:
        bus.publish("StockReservationFailed", {"order_id": data["order_id"]})

def on_payment_failed_release_stock(data):
    release_stock(data["order_id"])
    bus.publish("StockReleased", {"order_id": data["order_id"]})

bus.subscribe("OrderCreated", on_order_created_reserve_stock)
bus.subscribe("PaymentFailed", on_payment_failed_release_stock)

# --- Payment Service ---
def on_stock_reserved_charge(data):
    try:
        charge_customer(data["order_id"])
        bus.publish("PaymentCompleted", {"order_id": data["order_id"]})
    except PaymentError:
        bus.publish("PaymentFailed", {"order_id": data["order_id"]})

bus.subscribe("StockReserved", on_stock_reserved_charge)

# --- Flow ---
# OrderCreated → StockReserved → PaymentCompleted → OrderConfirmed
# If PaymentFailed → StockReleased → OrderCancelled
```

```
  Order Service
  │
  ▼
  "OrderCreated" ──▶ Inventory Service
                     │ (reserve stock)
                     ▼
                     "StockReserved" ──▶ Payment Service
                                        │ (charge card)
                                        ▼
                                        "PaymentCompleted" ──▶ Order Service
                                                               │ (confirm order)
                                                               ▼
                                                              "OrderConfirmed"

  If payment fails:
  "PaymentFailed" ──▶ Inventory Service
                     │ (release stock)
                     ▼
                     "StockReleased" ──▶ Order Service
                                        │ (cancel order)
                                        ▼
                                       "OrderCancelled"
```

**Pros**: Simple, no central coordinator, loose coupling.
**Cons**: Hard to track overall progress, cyclic dependencies possible.

### Orchestration-Based Saga

A central orchestrator coordinates the saga.

```python
from dataclasses import dataclass, field
from typing import List, Callable
from enum import Enum

class StepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"

@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Callable
    status: StepStatus = StepStatus.PENDING

class OrderSagaOrchestrator:
    """Centralized orchestrator for the order saga."""

    def __init__(self):
        self.steps: List[SagaStep] = []

    def add_step(self, name: str, action: Callable, compensation: Callable):
        self.steps.append(SagaStep(name=name, action=action, compensation=compensation))

    def execute(self, order_data: dict) -> dict:
        completed_steps = []

        for step in self.steps:
            try:
                print(f"Executing: {step.name}")
                step.action(order_data)
                step.status = StepStatus.COMPLETED
                completed_steps.append(step)
            except Exception as e:
                print(f"Failed: {step.name} — {e}")
                step.status = StepStatus.FAILED

                # Compensate in reverse order
                for completed in reversed(completed_steps):
                    try:
                        print(f"Compensating: {completed.name}")
                        completed.compensation(order_data)
                        completed.status = StepStatus.COMPENSATED
                    except Exception as comp_error:
                        print(f"Compensation failed: {completed.name} — {comp_error}")

                return {"status": "failed", "failed_step": step.name}

        return {"status": "completed"}

# Usage:
saga = OrderSagaOrchestrator()
saga.add_step("Reserve Stock", reserve_stock, release_stock)
saga.add_step("Charge Payment", charge_customer, refund_customer)
saga.add_step("Confirm Order", confirm_order, cancel_order)

result = saga.execute({"order_id": "o123", "amount": 99.99})
```

```
  ┌────────────────────────────────────────────┐
  │           Order Saga Orchestrator          │
  │                                            │
  │  1. Create order (Order Service)           │
  │  2. Reserve stock (Inventory Service)      │
  │  3. Charge payment (Payment Service)       │
  │  4. Confirm order (Order Service)          │
  │                                            │
  │  Compensation chain:                       │
  │  If step 3 fails → release stock → cancel  │
  └────────────────────────────────────────────┘
```

**Pros**: Clear flow, easy to track, centralized logic.
**Cons**: Single point of failure, orchestration logic complexity.

---

## Service Discovery

Services need to find each other in a dynamic environment.

```python
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List
import threading

@dataclass
class ServiceInstance:
    host: str
    port: int
    health: str = "healthy"
    last_heartbeat: float = field(default_factory=time.time)

class ServiceRegistry:
    """Simple in-memory service registry (production: use Consul, etcd, or K8s DNS)."""

    def __init__(self):
        self.services: Dict[str, List[ServiceInstance]] = {}
        self._lock = threading.Lock()

    def register(self, service_name: str, instance: ServiceInstance):
        with self._lock:
            self.services.setdefault(service_name, []).append(instance)

    def deregister(self, service_name: str, host: str, port: int):
        with self._lock:
            if service_name in self.services:
                self.services[service_name] = [
                    i for i in self.services[service_name]
                    if not (i.host == host and i.port == port)
                ]

    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """Return healthy instances only."""
        with self._lock:
            return [
                i for i in self.services.get(service_name, [])
                if i.health == "healthy"
            ]

    def discover(self, service_name: str) -> ServiceInstance:
        """Client-side discovery: pick a random healthy instance."""
        instances = self.get_instances(service_name)
        if not instances:
            raise ServiceUnavailable(f"No healthy instances for {service_name}")
        return random.choice(instances)

# --- Client-side discovery ---
registry = ServiceRegistry()
registry.register("order-service", ServiceInstance("10.0.1.1", 8080))
registry.register("order-service", ServiceInstance("10.0.1.2", 8080))

def call_order_service():
    instance = registry.discover("order-service")
    return requests.get(f"http://{instance.host}:{instance.port}/orders")

# --- Server-side discovery (via load balancer) ---
# Load balancer queries registry, routes traffic automatically
# Service A → Load Balancer → Service B (any healthy instance)
```

```
  Client-Side Discovery:
  Service A ──▶ Service Registry ──▶ Get list of Service B instances
                    │
                    ▼
  Service A picks one (load balancing) ──▶ Service B

  Server-Side Discovery:
  Service A ──▶ Load Balancer ──▶ Service B (any instance)
                    │
                    ▼
              Service Registry (keeps LB updated)
```

### Registry Options

| Tool | Model | Use Case |
|------|-------|----------|
| **Consul** | DNS + HTTP API | General service discovery |
| **etcd** | Key-value store | Kubernetes internal |
| **Eureka** | REST-based | Netflix OSS, Spring Cloud |
| **Kubernetes DNS** | DNS-based | Kubernetes-native |

---

## API Versioning

Versioning *strategies* — URL, header, content negotiation, deprecation
lifecycles — are covered in
[Module 14](../14-api-design/README.md#4-api-versioning-strategies). Between
your own microservices the problem is different, and in some ways harder:
there is no "v2 release day". Services deploy independently, so for some
window **old and new versions of a service run side by side**, talking to
old and new versions of their callers.

### The Rule: Every Change Must Survive Mixed Versions

```
  Deploy timeline for a field rename (customer_name → full_name)

  WRONG — one step                RIGHT — expand, migrate, contract
  ─────────────────────           ──────────────────────────────────
  deploy producer: sends          1. producer sends BOTH fields
    only full_name                2. deploy every consumer to read
  consumers still read               full_name (fall back to
    customer_name → null            customer_name if absent)
  → outage until every            3. confirm no consumer reads the
    consumer is redeployed           old field (logs / contract tests)
                                  4. producer stops sending the old one

  Each step is safe to deploy, and safe to roll back, on its own.
```

### Three Practices That Make This Routine

| Practice | What it means | Why it matters |
|----------|---------------|----------------|
| **Tolerant reader** | Consumers ignore fields they don't recognise and treat optional fields as optional | A producer can add a field without coordinating with anyone |
| **Consumer-driven contract tests** | Each consumer publishes the fields it actually depends on; the producer's CI fails if a change would break one (e.g. Pact) | You learn about a breaking change in the producer's PR, not in production |
| **Schema registry for events** | Event schemas are versioned centrally and checked for compatibility on publish (Module 05) | Events outlive deployments — a consumer may replay a message written months ago |

**What counts as breaking** is narrower than it seems: adding an optional
field, adding an endpoint, or adding an enum value a tolerant reader ignores
are all safe. Removing or renaming a field, tightening validation, changing
a type, or changing a field's *meaning* while keeping its name are not — and
the last one is the one no tooling catches.

---

## Deploying Safely: Rollouts, Flags, and Schema Migrations

Most outages start with a change: a deploy, a config push, a migration.
Independent deploys are the point of microservices, so each team needs a
rollout process that limits how much damage one bad change can do and how long
it lasts.

### Rollout Strategies

| Strategy | How it works | Extra capacity | Rollback | Watch out for |
|----------|--------------|----------------|----------|---------------|
| **Recreate** | Stop all old instances, start new ones | None | Redeploy the old version | Downtime; only for dev or batch jobs |
| **Rolling** | Replace instances in batches (e.g. 25% at a time) | 0–1 batch | Roll forward again with the old version | Old and new run side by side for the whole rollout |
| **Blue-green** | Stand up a full new environment, switch the load balancer | 2× during the switch | Instant: switch back | Both colours share the database, so the schema must suit both |
| **Canary** | Send 1% → 5% → 25% → 100% of traffic to the new version, checking metrics at each step | Small | Fast: route traffic away | Needs automated analysis; a 1% canary can't see rare errors |
| **Shadow (dark launch)** | Mirror real traffic to the new version and discard its responses | Up to 2× | Nothing to roll back | Side effects (emails, charges, writes) must be suppressed |

**Canary analysis compares like with like.** Comparing new instances against
the old fleet mixes in uptime, warm caches and JIT state. Netflix's Kayenta
(in Spinnaker) instead starts a fresh *baseline* of the current version
alongside the canary, same size and same age, and compares the two
statistically on error rate, latency percentiles and saturation. Promotion
and rollback should be automatic: a human watching dashboards at 2am is the
failure mode [Module 16](../16-incident-response/README.md) dissects.

### Feature Flags: Separate Deploy from Release

A **deploy** puts code on servers; a **release** exposes behaviour to users.
Feature flags make them separate steps: ship dark, enable for employees, then
1% of users, then everyone, and turn it off in seconds without a redeploy.
That same switch is the fastest incident mitigation there is.

Two costs. **Flag changes are production changes**: a flag flipped to 100% at
once is a big-bang deploy without a canary, so roll flags out gradually and
log every flip next to deploys. And **flags rot**: every flag doubles the
states your code can be in. Give each release flag an owner and an expiry, and
delete it once it is fully on.

### Zero-Downtime Schema Migrations

During any rolling, blue-green or canary deploy, **two versions of your code
run against one database**. So the rule from [API Versioning](#api-versioning)
applies to schemas too: never change code and schema in a single step, and
make every schema state work with both the code before it and the code after
it. Renaming `users.name` to `users.full_name` takes six deploys:

```
  1. EXPAND     ALTER TABLE users ADD COLUMN full_name text;   (nullable, no default)
  2. DUAL-WRITE app writes name AND full_name; still reads name
  3. BACKFILL   copy name → full_name in small batches
  4. SWITCH     app reads full_name (falls back to name if NULL)
  5. STOP       app stops writing name
  6. CONTRACT   ALTER TABLE users DROP COLUMN name;            (days later)

  Rollback is a redeploy at every step, because
  no step removes anything the previous code needs.
```

**Backfill in batches**, never one giant `UPDATE`. A single statement over 200
million rows holds locks for its whole run, generates one enormous WAL burst
that replicas must replay (replication lag), and if it fails at 90%, rolls
everything back:

```sql
-- Repeat until 0 rows updated; pause between batches if replicas lag.
UPDATE users SET full_name = name
WHERE id IN (
  SELECT id FROM users
  WHERE full_name IS NULL AND id > :last_id
  ORDER BY id LIMIT 5000
);
```

**DDL can take the whole table offline.** These are the PostgreSQL traps; MySQL
has equivalents, usually solved with online tools such as gh-ost or
pt-online-schema-change:

| Operation | The trap | The safe version |
|-----------|----------|------------------|
| Any `ALTER TABLE` | Needs an exclusive lock; while it waits behind one long-running query, **every new query on the table queues behind it** | `SET lock_timeout = '2s'` and retry, so a blocked migration fails fast instead of stalling traffic |
| `CREATE INDEX` | Blocks writes for the whole build | `CREATE INDEX CONCURRENTLY` (can't run inside a transaction; a failed build leaves an `INVALID` index to drop) |
| `ADD COLUMN ... DEFAULT` | Before PostgreSQL 11, rewrote the whole table | On 11+ a constant default is metadata-only; volatile defaults (`random()`) still rewrite |
| `SET NOT NULL` | Scans the whole table under the exclusive lock | Add `CHECK (col IS NOT NULL) NOT VALID`, then `VALIDATE CONSTRAINT` (weaker lock); on 12+ `SET NOT NULL` then skips the scan |

> **The contract step is the dangerous one.** Expand steps are additive and
> easy to undo; a dropped column is gone. Wait until logs confirm nothing reads
> the old column, and take a backup first. Many teams keep it for a full
> release cycle before dropping it.

---

## Observability in Microservices

> This section is the overview. **[Module 15: Observability](../15-observability/README.md)**
> covers it in depth: metric cardinality, why percentiles cannot be averaged,
> context propagation across queues and thread pools, sampling strategies, and
> SLO burn-rate alerting.

### The Three Pillars

```
  ┌───────────────────────────────────────────────────┐
  │              Observability Stack                  │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │
  │  │  Logs    │  │  Metrics │  │   Traces     │     │
  │  │          │  │          │  │              │     │
  │  │ What     │  │ How much │  │ Where did    │     │
  │  │ happened │  │ / how    │  │ the request  │     │
  │  │          │  │ fast     │  │ go?          │     │
  │  └──────────┘  └──────────┘  └──────────────┘     │
  │                                                   │
  │  Tools: ELK, Prometheus, Jaeger, Zipkin           │
  └───────────────────────────────────────────────────┘
```

### Distributed Tracing

```
  Request: GET /api/orders/123

  ┌───────────────────────────────────────────────────────┐
  │ Trace ID: abc-123-def                                 │
  │                                                       │
  │ ┌──────────────────────────────────────────────────┐  │
  │ │ API Gateway (2ms)                                │  │
  │ │ ┌─────────────────────────────────────────────┐  │  │
  │ │ │ Order Service (5ms)                         │  │  │
  │ │ │ ┌───────────────────────────────────────┐   │  │  │
  │ │ │ │ Database Query (3ms)                  │   │  │  │
  │ │ │ └───────────────────────────────────────┘   │  │  │
  │ │ │ ┌───────────────────────────────────────┐   │  │  │
  │ │ │ │ User Service Call (8ms)               │   │  │  │
  │ │ │ └───────────────────────────────────────┘   │  │  │
  │ │ └─────────────────────────────────────────────┘  │  │
  │ └──────────────────────────────────────────────────┘  │
  └───────────────────────────────────────────────────────┘

  Total: 15ms (but user service was the bottleneck at 8ms)
```

---

## Case Study: Netflix Microservices

Netflix runs 1000+ microservices serving 230M+ subscribers.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               Netflix Microservices Architecture             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────┐        │
│  │  API Gateway (Zuul)                              │        │
│  │  - Request routing                               │        │
│  │  - Authentication                                │        │
│  │  - Rate limiting                                 │        │
│  │  - Load balancing                                │        │
│  └──────────────────────────────────────────────────┘        │
│                         │                                    │
│      ┌──────────────────┼──────────────────┐                 │
│      │                  │                  │                 │
│      ▼                  ▼                  ▼                 │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    User    │  │   Catalog    │  │  Streaming   │          │
│  │  Service   │  │   Service    │  │   Service    │          │
│  │            │  │              │  │              │          │
│  │ - Auth     │  │ - Movies     │  │ - Playback   │          │
│  │ - Profile  │  │ - Shows      │  │ - CDN        │          │
│  │ - Prefs    │  │ - Genres     │  │ - Quality    │          │
│  └────────────┘  └──────────────┘  └──────────────┘          │
│                                                              │
│  ┌───────────────────────────────────────────────────┐       │
│  │  Data Stores                                      │       │
│  │  Cassandra (user data) + MySQL (billing)          │       │
│  │  EVCache (caching) + Elasticsearch (search)       │       │
│  └───────────────────────────────────────────────────┘       │
│                                                              │
│  ┌───────────────────────────────────────────────────┐       │
│  │  Observability                                    │       │
│  │  Atlas (metrics) + Zuul (tracing) + ELK (logs)    │       │
│  └───────────────────────────────────────────────────┘       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Key Decisions

1. **Chaos engineering**: Netflix intentionally kills services in production (Chaos Monkey) to ensure resilience. If a service can't survive a random failure, it's not ready for production.

2. **Polyglot persistence**: Different data stores for different needs. User data in Cassandra (write-optimized), billing in MySQL (ACID), search in Elasticsearch, caching in EVCache.

3. **Zuul as the edge service**: All external traffic goes through Zuul, which handles routing, auth, and canary deployments. Internal service-to-service calls bypass Zuul.

4. **Conductor for orchestration**: Long-running workflows (e.g., content processing pipeline) are orchestrated by Conductor, a workflow engine that manages retries, timeouts, and compensation.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| "Building Microservices" (Sam Newman) | Book | Decomposition, communication, deployment |
| "Microservices Patterns" (Chris Richardson) | Book | Saga, CQRS, API patterns |
| Netflix Tech Blog | Blog | Chaos engineering, microservices at scale |
| Domain-Driven Design (Eric Evans) | Book | Bounded contexts, decomposition |
| "Automated Canary Analysis at Netflix with Kayenta" (Netflix Tech Blog, 2018) | Blog | Baseline-vs-canary comparison |
| "ParallelChange" (Martin Fowler / Danilo Sato) | Article | The expand/contract pattern |
| PostgreSQL docs: `ALTER TABLE`, `CREATE INDEX CONCURRENTLY` | Docs | Lock levels for online schema changes |

---

## Practice Exercise

**20-minute design**: Decompose a food delivery app into microservices:

- Features: User registration, restaurant browsing, ordering, payment, delivery tracking, reviews
- 100K daily active users
- 3 engineering teams

**Key decisions**:
1. What bounded contexts do you identify?
2. How many microservices would you create?
3. Which services communicate synchronously vs asynchronously?
4. How do you handle the order saga across services?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Shipping code and schema change together** | During the rollout old code meets the new schema (or the reverse) and fails | Expand/contract: additive schema first, code next, removal last, each step deployable and reversible alone |
| **Microservices before the domain is understood** | You cement the wrong boundaries, and moving them later costs far more than in a monolith | Start modular-monolith; extract once boundaries stop moving |
| **A shared database between services** | The schema becomes an unversioned public API — nobody can migrate independently | One datastore per service; integrate over APIs or events |
| **Splitting by technical layer** | An "API service" plus a "DB service" means every feature touches both — distributed, but not decoupled | Split by business capability so a change lands in one service |
| **Synchronous call chains for everything** | Availability multiplies: five 99.9% hops give 99.5%, and latency accumulates | Async events where the caller doesn't need an answer now |
| **Distributed transactions via 2PC** | The coordinator is a SPOF and participants hold locks while blocked | Saga with compensating actions, or TCC for reservations |
| **Sagas without idempotent compensations** | Compensation runs at least once; a double refund is its own incident | Make every compensation idempotent and safe out of order |
| **Assuming compensation always succeeds** | The refund can fail too, leaving the saga half-undone | Persist saga state, retry compensations, escalate to human review |
| **Versioning by breaking `/v1`** | Clients you don't control break silently | Additive changes in place; a new version only for genuine breaks, with a sunset window |
| **No distributed tracing** | With 20 services, "it's slow" is unfalsifiable | Propagate a trace ID from the edge through every hop, from day one |
| **Shared libraries as the reuse strategy** | A bump requires redeploying every service — that's a monolith with extra steps | Duplicate small things; share via APIs, not compile-time coupling |

---

## Discussion Questions

1. You're building a food delivery app. Start with a monolith. At what point would you split into microservices? What would be the first service to extract?

2. Explain the saga pattern to a junior engineer. What problem does it solve, and what are the trade-offs?

3. You have 5 microservices that need to communicate. Design the communication patterns. Which calls are synchronous, which are asynchronous?

4. How do you handle a failure in a downstream service? What patterns prevent cascading failures?

5. You're migrating from a monolith to microservices. What's your strategy? Big bang or strangler fig?

6. A migration runs `ALTER TABLE orders ADD COLUMN note text;` on PostgreSQL. It is a metadata-only change that should take milliseconds, yet the site goes down for four minutes. What happened?

   **Model answer**: The `ALTER` needed an `ACCESS EXCLUSIVE` lock and queued behind a long-running query or idle-in-transaction session holding a lock on `orders` (an analytics report, a stuck worker). Lock requests queue in order, so every ordinary `SELECT` and `INSERT` on `orders` then queued behind the waiting `ALTER`. The migration itself was cheap; the wait made the table unavailable. Fixes: set `lock_timeout` (a few seconds) so the migration gives up and retries instead of blocking traffic; set `idle_in_transaction_session_timeout` and statement timeouts so stray sessions can't hold locks for minutes; and check for long-running transactions before migrating.

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/) | The saga pattern and service discovery here are concrete applications of the distributed transaction and consensus problems this module covers in depth |
| [Module 12: Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/) | The bounded-context and saga examples here (catalog, ordering, inventory, payment) design the same e-commerce domain this case study builds end-to-end |
| [Module 14: API Design](../14-api-design/) | REST vs. gRPC communication and API versioning are introduced here for inter-service use, then covered in full depth for public-facing APIs |
| [Module 15: Observability](../15-observability/) | The Observability in Microservices section is explicitly the overview; this module covers metric cardinality, tracing, and SLO burn-rate alerting in depth |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│                 Microservices — Key Takeaways                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Start with a monolith — split when the pain of coupling    │
│     outweighs the pain of distribution, not before             │
│  2. A shared database between services is just a monolith      │
│     wearing a microservices costume                            │
│  3. There's no 2PC — sagas trade atomicity for availability,   │
│     and every compensation must be idempotent                  │
│  4. Choreography stays loosely coupled but gets hard to trace; │
│     orchestration is easy to trace but becomes a single point  │
│     of failure — choose on purpose                             │
│  5. Service discovery is the unglamorous plumbing that makes   │
│     "just call the other service" possible at scale            │
│  6. Every synchronous hop multiplies unavailability — five     │
│     99.9% services chained together give you 99.5%             │
│  7. Version additively and publish a real sunset window —      │
│     breaking `/v1` silently breaks clients you don't control   │
│  8. Without distributed tracing, "it's slow" is a guess, not a │
│     diagnosis                                                  │
│  9. Each new service is a new network call, a new failure mode,│
│     and a new thing somebody has to get paged for              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 05: Asynchronous Systems and Message Queues](../05-async-systems/README.md)

**Next:** [Module 07: Reliability Engineering](../07-reliability/README.md)

---

*Module 06 of 23 in the System Design Playground*
