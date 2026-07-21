# Module 06: Microservices Architecture

> **Design for team scale and deployment independence.** Microservices let teams own their services end-to-end, deploy independently, and scale separately — but they introduce distributed systems complexity.

## Learning Objectives

- Decide between monolith and microservices
- Decompose systems using domain-driven design
- Implement distributed transactions with the saga pattern
- Design service discovery and API versioning
- Understand observability in microservices

---

## Monolith vs Microservices

### The Monolith

All code in one deployable unit.

```
  ┌──────────────────────────────────┐
  │           Monolith                │
  │  ┌──────┐ ┌──────┐ ┌──────┐    │
  │  │User  │ │Order │ │Payment│    │
  │  │Module│ │Module│ │Module│    │
  │  └──────┘ └──────┘ └──────┘    │
  │  ┌──────┐ ┌──────┐ ┌──────┐    │
  │  │Email │ │Search│ │Report│    │
  │  │Module│ │Module│ │Module│    │
  │  └──────┘ └──────┘ └──────┘    │
  └──────────────────────────────────┘

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
            │  / API GW  │
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
  ┌─────────────────────────────────────────────┐
  │              E-Commerce Domain               │
  │                                               │
  │  ┌─────────────┐  ┌─────────────┐           │
  │  │   Catalog   │  │   Ordering  │           │
  │  │  Context    │  │   Context   │           │
  │  │             │  │             │           │
  │  │ Product     │  │ Order       │           │
  │  │ Category    │  │ LineItem    │           │
  │  │ Price       │  │ Cart        │           │
  │  └─────────────┘  └─────────────┘           │
  │                                               │
  │  ┌─────────────┐  ┌─────────────┐           │
  │  │  Inventory  │  │  Payment    │           │
  │  │  Context    │  │  Context    │           │
  │  │             │  │             │           │
  │  │ Stock       │  │ Transaction │           │
  │  │ Warehouse   │  │ PaymentMethod│          │
  │  │ Shipment    │  │ Invoice     │           │
  │  └─────────────┘  └─────────────┘           │
  └─────────────────────────────────────────────┘

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

```
  ┌──────────────────────────────────────────┐
  │           Order Saga Orchestrator          │
  │                                            │
  │  1. Create order (Order Service)          │
  │  2. Reserve stock (Inventory Service)     │
  │  3. Charge payment (Payment Service)      │
  │  4. Confirm order (Order Service)         │
  │                                            │
  │  Compensation chain:                       │
  │  If step 3 fails → release stock → cancel │
  └──────────────────────────────────────────┘
```

**Pros**: Clear flow, easy to track, centralized logic.
**Cons**: Single point of failure, orchestration logic complexity.

---

## Service Discovery

Services need to find each other in a dynamic environment.

### Client-Side Discovery

```
  Service A ──▶ Service Registry ──▶ Get list of Service B instances
                    │
                    ▼
  Service A picks one (load balancing) ──▶ Service B
```

### Server-Side Discovery

```
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

### URL Versioning

```
/api/v1/users
/api/v2/users

✓ Simple, explicit
✗ URL pollution
```

### Header Versioning

```
Accept: application/vnd.myapp.v2+json

✓ Clean URLs
✗ Less discoverable
```

### Content Negotiation

```
GET /api/users
Accept: application/json; version=2

✓ RESTful
✗ Complex implementation
```

---

## Observability in Microservices

### The Three Pillars

```
  ┌─────────────────────────────────────────────────┐
  │              Observability Stack                  │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
  │  │  Logs    │  │  Metrics │  │   Traces     │  │
  │  │          │  │          │  │              │  │
  │  │ What     │  │ How much │  │ Where did    │  │
  │  │ happened │  │ / how    │  │ the request  │  │
  │  │          │  │ fast     │  │ go?          │  │
  │  └──────────┘  └──────────┘  └──────────────┘  │
  │                                                   │
  │  Tools: ELK, Prometheus, Jaeger, Zipkin          │
  └─────────────────────────────────────────────────┘
```

### Distributed Tracing

```
  Request: GET /api/orders/123

  ┌──────────────────────────────────────────────────────┐
  │ Trace ID: abc-123-def                                 │
  │                                                       │
  │ ┌─────────────────────────────────────────────────┐  │
  │ │ API Gateway (2ms)                                │  │
  │ │ ┌────────────────────────────────────────────┐  │  │
  │ │ │ Order Service (5ms)                         │  │  │
  │ │ │ ┌──────────────────────────────────────┐   │  │  │
  │ │ │ │ Database Query (3ms)                  │   │  │  │
  │ │ │ └──────────────────────────────────────┘   │  │  │
  │ │ │ ┌──────────────────────────────────────┐   │  │  │
  │ │ │ │ User Service Call (8ms)               │   │  │  │
  │ │ │ └──────────────────────────────────────┘   │  │  │
  │ │ └────────────────────────────────────────────┘  │  │
  │ └─────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────┘

  Total: 15ms (but user service was the bottleneck at 8ms)
```

---

## Case Study: Netflix Microservices

Netflix runs 1000+ microservices serving 230M+ subscribers.

### Architecture

```
┌────────────────────────────────────────────────────────┐
│               Netflix Microservices Architecture        │
├────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  API Gateway (Zuul)                              │   │
│  │  - Request routing                               │   │
│  │  - Authentication                                │   │
│  │  - Rate limiting                                 │   │
│  │  - Load balancing                                │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│  ┌──────────────────────┼──────────────────────┐       │
│  │                      │                      │       │
│  ▼                      ▼                      ▼       │
│ ┌──────┐          ┌──────┐              ┌──────┐      │
│ │User  │          │Catalog│             │Streaming│    │
│ │Service│          │Service│             │Service  │    │
│ │      │          │       │             │         │    │
│ │-Auth │          │-Movies│             │-Playback│    │
│ │-Profile│         │-Shows │             │-CDN     │    │
│ │-Preferences│    │-Genres│             │-Quality │    │
│ └──────┘          └──────┘              └──────┘      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Data Stores                                      │   │
│  │  Cassandra (user data) + MySQL (billing)          │   │
│  │  EVCache (caching) + Elasticsearch (search)       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Observability                                    │   │
│  │  Atlas (metrics) + Zuul (tracing) + ELK (logs)   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└────────────────────────────────────────────────────────┘
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

---

## Discussion Questions

1. You're building a food delivery app. Start with a monolith. At what point would you split into microservices? What would be the first service to extract?

2. Explain the saga pattern to a junior engineer. What problem does it solve, and what are the trade-offs?

3. You have 5 microservices that need to communicate. Design the communication patterns. Which calls are synchronous, which are asynchronous?

4. How do you handle a failure in a downstream service? What patterns prevent cascading failures?

5. You're migrating from a monolith to microservices. What's your strategy? Big bang or strangler fig?

---

**Previous**: [Asynchronous Systems and Message Queues](../05-async-systems/README.md)
**Next**: [Reliability Engineering](../07-reliability/README.md)
