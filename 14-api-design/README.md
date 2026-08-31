# Module 14: API Design

> "A well-designed API is a joy to use; a poorly designed API is a source of endless frustration."

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 13 | Security | [../13-security/](../13-security/) |
| **Module 14** | **API Design** | **(current)** |
| Module 15 | Observability | [../15-observability/](../15-observability/) |

---

## Learning Objectives

By the end of this module, you will be able to:

1. Design RESTful APIs using resource naming conventions, HTTP semantics, and status codes
2. Choose between REST, gRPC, and GraphQL based on system requirements
3. Implement API versioning and deprecation strategies that balance stability with evolution
4. Structure consistent error responses following RFC 9457 (Problem Details)
5. Apply rate limiting and throttling to protect backend services
6. Analyze real-world API designs (Stripe) for patterns worth adopting

---

## Table of Contents

1. [REST API Design](#1-rest-api-design)
2. [gRPC](#2-grpc)
3. [GraphQL](#3-graphql)
4. [API Versioning Strategies](#4-api-versioning-strategies)
5. [Error Handling](#5-error-handling)
6. [Rate Limiting & Throttling](#6-rate-limiting--throttling)
7. [Case Study: Stripe's API Design](#7-case-study-stripes-api-design)
8. [Practice Exercise](#8-practice-exercise)
9. [Common Mistakes](#9-common-mistakes)
10. [Discussion Questions](#10-discussion-questions)
11. [Key References](#11-key-references)

---

## 1. REST API Design

### Resource Naming Conventions

REST (Representational State Transfer) is an architectural style where URLs represent **resources** (nouns), and HTTP methods represent **operations** (verbs).

```
Bad:  POST /createUser
Good: POST /users

Bad:  GET /getUser?id=42
Good: GET /users/42

Bad:  GET /user/42/posts
Good: GET /users/42/posts          (hierarchical)
```

**Rules for resource naming:**

| Rule | Correct | Incorrect |
|------|---------|-----------|
| Use nouns, not verbs | `/users`, `/orders` | `/getUsers`, `/fetchOrders` |
| Use plural nouns | `/users/42` | `/user/42` |
| Use hyphens for multi-word | `/user-profiles` | `/user_profiles`, `/userProfiles` |
| Use hierarchical nesting | `/users/42/orders/7` | `/orders/7?userId=42` |
| Use query params for filtering | `/users?status=active` | `/active-users` |

### HTTP Methods

Each HTTP method has strict semantics. Violating them breaks caching, proxies, and client expectations.

```
┌─────────┬────────────┬─────────────┬────────┬──────────┐
│ Method  │ Idempotent │ Safe        │ Body?  │ Cachable │
├─────────┼────────────┼─────────────┼────────┼──────────┤
│ GET     │ Yes        │ Yes         │ No     │ Yes      │
│ POST    │ No         │ No          │ Yes    │ No       │
│ PUT     │ Yes        │ No          │ Yes    │ No       │
│ PATCH   │ No*        │ No          │ Yes    │ No       │
│ DELETE  │ Yes        │ No          │ Varies │ No       │
└─────────┴────────────┴─────────────┴────────┴──────────┘
 * PATCH can be idempotent if designed carefully (e.g., JSON Merge Patch)
```

**When to use each:**

- **GET** — Retrieve a resource or collection. Must not mutate state.
- **POST** — Create a new resource, or trigger a non-idempotent operation.
- **PUT** — Replace a resource entirely. Client must send the full representation.
- **PATCH** — Partial update. Client sends only the fields to change.
- **DELETE** — Remove a resource. Safe to retry (idempotent).

### Status Codes

Using the right status code is part of the API contract. Clients and proxies depend on these.

```
2xx Success
├── 200 OK                    — Request succeeded (GET, PUT, PATCH, DELETE)
├── 201 Created               — Resource created (POST). Include Location header.
├── 202 Accepted              — Async operation accepted, not yet complete
├── 204 No Content            — Success with no response body (DELETE, PUT)
└── 206 Partial Content       — Range request fulfilled

3xx Redirection
├── 301 Moved Permanently     — Resource moved (update bookmarks)
├── 304 Not Modified          — Cached response is still valid
└── 307 Temporary Redirect    — Redirect preserving HTTP method

4xx Client Errors
├── 400 Bad Request           — Malformed syntax, missing required fields
├── 401 Unauthorized          — Missing or invalid authentication
├── 403 Forbidden             — Authenticated but not authorized
├── 404 Not Found             — Resource does not exist
├── 409 Conflict              — State conflict (e.g., duplicate creation)
├── 422 Unprocessable Entity  — Semantically invalid (valid JSON, bad values)
├── 429 Too Many Requests     — Rate limit exceeded
└── 451 Unavailable For Legal Reasons

5xx Server Errors
├── 500 Internal Server Error — Unexpected failure
├── 502 Bad Gateway           — Upstream service returned invalid response
├── 503 Service Unavailable   — Temporary overload or maintenance
└── 504 Gateway Timeout       — Upstream service too slow
```

### HATEOAS and Richardson Maturity Model

The Richardson Maturity Model grades API design on a 0–3 scale:

```
Level 0: Swamp of POX
  Single endpoint, custom verbs in body or URL
  POST /api {"action": "getUser", "id": 42}

Level 1: Resources
  Multiple endpoints, but still verb-heavy
  POST /users/get/42
  POST /orders/list

Level 2: HTTP Verbs
  Proper use of HTTP methods and status codes
  GET /users/42
  POST /orders

Level 3: HATEOAS
  Responses include hypermedia links for discoverability
  {
    "id": 42,
    "name": "Alice",
    "links": [
      {"rel": "self", "href": "/users/42", "method": "GET"},
      {"rel": "orders", "href": "/users/42/orders", "method": "GET"},
      {"rel": "update", "href": "/users/42", "method": "PATCH"}
    ]
  }
```

Most production APIs target **Level 2**. HATEOAS (Level 3) is powerful for discoverability but adds complexity — few teams reach it.

### Pagination

When listing resources, you **must** paginate. Unbounded collections will kill your database and your clients.

**Offset-based pagination:**

```
GET /orders?page=3&page_size=50

{
  "data": [...],
  "pagination": {
    "page": 3,
    "page_size": 50,
    "total_items": 1247,
    "total_pages": 25
  }
}
```

**Cursor-based pagination:**

```
GET /orders?cursor=eyJpZCI6MTAwfQ==&limit=50

{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTUwfQ==",
    "has_more": true
  }
}
```

**Trade-off table:**

| Aspect | Offset-Based | Cursor-Based |
|--------|-------------|--------------|
| Simplicity | Simple, intuitive | More complex |
| Random page access | Yes | No |
| Consistency under writes | Gaps/duplicates on insert/delete | Consistent |
| Performance at depth | Degrades (OFFSET scan) | Constant |
| Recommended for | Admin dashboards | Feeds, APIs, high-volume |

### Filtering and Sorting

```
# Filtering
GET /users?status=active&role=admin
GET /orders?created_after=2025-01-01&total_gte=100

# Sorting — prefix convention: "-" descending, bare ascending
GET /users?sort=-created_at,name
GET /orders?sort=-total,created_at
```

Use one convention: `-field` for descending, `field` for ascending. Document the
supported filters and sortable fields explicitly.

> **Avoid the `sort=total desc` form.** Spaces are not legal in a URL and must be
> percent-encoded (`sort=total%20desc`), so the readable version only appears to
> work — and it needs a second parser for the direction keyword. The `-field`
> prefix has neither problem.

**Two rules that prevent real outages:**

- **Only allow sorting on indexed columns.** `?sort=-description` on a
  10M-row table is a full scan an anonymous caller can trigger at will.
  Keep an allowlist and return `400` for anything else.
- **Always append a unique tiebreaker** (`sort=-created_at,id`). Two rows with
  identical timestamps have no defined order, so a paginated scan can show one
  row twice and skip another.

---

## 2. gRPC

gRPC is a high-performance RPC framework built on HTTP/2 and Protocol Buffers.

### Protocol Buffers (proto3)

```protobuf
syntax = "proto3";

package userservice;

service UserService {
  rpc GetUser (GetUserRequest) returns (User);
  rpc ListUsers (ListUsersRequest) returns (stream User);
  rpc CreateUser (CreateUserRequest) returns (CreateUserResponse);
}

message GetUserRequest {
  int32 id = 1;
}

message User {
  int32 id = 1;
  string name = 2;
  string email = 3;
  UserType type = 4;
}

enum UserType {
  UNSPECIFIED = 0;  // proto3 requires zero value
  ADMIN = 1;
  MEMBER = 2;
}
```

### Streaming

gRPC supports four communication patterns:

```
Unary (Request/Response)
Client ──────── Request ────────▶ Server
Client ◀────── Response ◀──────── Server

Server Streaming
Client ──────── Request ────────▶ Server
Client ◀── Response 1 ◀──────── Server
Client ◀── Response 2 ◀──────── Server
Client ◀── Response 3 ◀──────── Server

Client Streaming
Client ──────── Request 1 ──────▶ Server
Client ──────── Request 2 ──────▶ Server
Client ──────── Request 3 ──────▶ Server
Client ◀────── Response ◀──────── Server

Bidirectional Streaming
Client ──────── Request 1 ──────▶ Server
Client ◀── Response 1 ◀──────── Server
Client ──────── Request 2 ──────▶ Server
Client ◀── Response 2 ◀──────── Server
```

### When to Use gRPC vs REST

| Criteria | gRPC | REST |
|----------|------|------|
| Performance | HTTP/2 + binary protobuf = faster | HTTP/1.1 + JSON = slower |
| Schema enforcement | Compiled from .proto files | Documented (OpenAPI), not enforced |
| Streaming | Native support | Workarounds (SSE, WebSocket) |
| Browser support | Requires gRPC-Web proxy | Native |
| Tooling maturity | Growing, less ecosystem | Huge ecosystem |
| Internal microservices | Ideal | Adequate |
| Public API | Harder for third parties | Standard choice |
| Inter-service comms | Strongly typed, fast | Simpler but looser |

### gRPC-gateway

REST compatibility layer for gRPC services:

```protobuf
import "google/api/annotations.proto";

service UserService {
  rpc GetUser (GetUserRequest) returns (User) {
    option (google.api.http) = {
      get: "/v1/users/{id}"
    };
  }
}
```

This generates a reverse proxy serving REST endpoints that translate to gRPC calls — giving you the internal performance of gRPC with a REST-facing API.

---

## 3. GraphQL

GraphQL is a query language for APIs where the client specifies exactly what data it needs.

### Schema Definition

```graphql
type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: ID!
  title: String!
  body: String!
  author: User!
}

type Query {
  user(id: ID!): User
  users(filter: UserFilter): [User!]!
}

type Mutation {
  createUser(input: CreateUserInput!): User!
  updateUser(id: ID!, input: UpdateUserInput!): User!
}

input CreateUserInput {
  name: String!
  email: String!
}
```

### The N+1 Problem

When resolving related data, naive resolvers cause N+1 database queries:

```python
# Naive resolver — N+1 problem
def resolve_posts(user):
    # Called once per user, then once per post for author...
    return db.query("SELECT * FROM posts WHERE author_id = ?", user.id)
```

**Solution: DataLoader** batches and deduplicates within a single request:

```python
from strawberry.dataloader import DataLoader

async def load_posts(user_ids: list[int]) -> list[list[Post]]:
    posts = await db.query("SELECT * FROM posts WHERE author_id IN (?)", user_ids)
    grouped = {uid: [] for uid in user_ids}
    for post in posts:
        grouped[post.author_id].append(post)
    return [grouped[uid] for uid in user_ids]

post_loader = DataLoader(load_fn=load_posts)
```

### When to Use GraphQL vs REST

| Criteria | GraphQL | REST |
|----------|---------|------|
| Multiple related resources | One query, exact fields | Multiple endpoints |
| Over-fetching / under-fetching | Eliminated | Common problem |
| Client-driven schema evolution | Add fields freely | Breaking version changes |
| Caching | Harder (POST queries) | HTTP caching built-in |
| File uploads | Clunky | Native multipart |
| Real-time | Subscriptions | WebSockets/SSE (external) |
| Rate limiting complexity | Query complexity analysis | Simple per-endpoint |

### Federation

GraphQL Federation lets you compose a single graph from multiple microservices:

```graphql
# users service
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}

# orders service
type Order @key(fields: "id") {
  id: ID!
  total: Float!
  user: User!  # references User from users service
}
```

Each team owns its slice of the graph. The gateway merges them into a unified API.

---

## 4. API Versioning Strategies

APIs evolve. Versioning lets you introduce breaking changes without disrupting existing consumers.

### URL Versioning

```
GET /v1/users/42
GET /v2/users/42
```

**Pros:** Explicit, easy to route, simple caching.
**Cons:** URL proliferation, encourages "version everything."

### Header Versioning

```
GET /users/42
Accept: application/vnd.myapp.v2+json
```

**Pros:** Clean URLs, content-type negotiation.
**Cons:** Less visible, harder to test in browser.

### Content Negotiation

```
GET /users/42
Accept: application/json; version=2
```

Similar to header versioning but uses a structured media type.

### Deprecation Strategy

A responsible deprecation lifecycle:

```
v2 released ──▶ Sunset header added ──▶ Migration docs ──▶ v1 sunset

Timeline:
  Month 0:    v2 released, both versions supported
  Month 0+3:  Deprecation warnings in response headers
  Month 0+9:  Sunset date announced
  Month 0+12: v1 removed
```

**Deprecation headers:**

```http
Deprecation: true
Sunset: Sat, 01 Mar 2026 00:00:00 GMT
Link: <https://docs.myapp.com/v2-migration>; rel="deprecation"
```

### Comparison

| Strategy | Complexity | Client Impact | Best For |
|----------|-----------|---------------|----------|
| URL versioning | Low | Explicit migration | Public APIs, many consumers |
| Header versioning | Medium | Transparent | Internal APIs, fewer consumers |
| Content negotiation | Medium | Transparent | REST purists |
| No versioning (evolution) | Low | Additive changes only | Stable, well-designed APIs |

---

## 5. Error Handling

### RFC 9457 Problem Details

RFC 9457 defines a standard JSON error format. It obsoleted RFC 7807 in 2023 —
the field names are unchanged, so existing 7807 payloads remain valid; cite 9457
as the current reference.

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "The 'email' field must be a valid email address",
  "instance": "/users/create-req-abc123",
  "errors": [
    {
      "field": "email",
      "code": "INVALID_FORMAT",
      "message": "Expected format: user@example.com"
    }
  ]
}
```

**Content-Type for error responses:**

```http
Content-Type: application/problem+json
```

### Consistent Error Response Format

Every API should return errors in a consistent structure:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Account balance is $45.00, but transfer requires $100.00",
    "details": {
      "current_balance": 4500,
      "required_amount": 10000,
      "currency": "USD"
    },
    "request_id": "req_7f3a2b4c",
    "documentation_url": "https://docs.myapp.com/errors/insufficient-funds"
  }
}
```

### Error Logging and Alerting

```python
import structlog

logger = structlog.get_logger()

def handle_error(error, request_id, user_id):
    log = logger.bind(
        error_code=error.code,
        request_id=request_id,
        user_id=user_id,
        status_code=error.status,
    )

    if error.status >= 500:
        log.error("server_error", detail=error.message)
        alert_on_call(error)  # page someone
    elif error.status == 429:
        log.warning("rate_limited", retry_after=error.retry_after)
    elif error.status >= 400:
        log.info("client_error", detail=error.message)
```

Never log secrets, tokens, or PII. Log enough to debug, not enough to violate privacy.

---

## 6. Rate Limiting & Throttling

Rate limiting protects services from abuse, ensures fair usage, and maintains availability.

> See [Module 04: Load Balancing](../04-load-balancing/) for how rate limiting interacts with load distribution.

### Limit Dimensions

```
┌──────────────────────────────────────────────────┐
│              Rate Limiting Layers                │
├──────────────┬──────────────┬─────────────────── ┤
│  Per-User    │  Per-API     │  Per-Tier          │
├──────────────┼──────────────┼─────────────────── ┤
│ 100 req/min  │ 10k req/min  │ Free: 100/min      │
│ per user     │ per endpoint │ Pro: 1000/min      │
│              │              │ Enterprise: 10k/min│
└──────────────┴──────────────┴────────────────────┘
```

### Response Headers

Always include rate limit headers so clients can self-regulate:

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1704067200
```

When exceeded:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704067230
```

### Implementation Patterns

**Token Bucket:**
- Tokens added at a fixed rate up to a bucket capacity
- Each request consumes one token
- Allows bursts up to bucket size

**Sliding Window:**
- Counts requests in a rolling time window
- More precise than fixed windows
- Higher memory cost (store timestamps per user)

```python
import time

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = {}

    def allow(self, key: str) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - self.window_seconds

        if key not in self.requests:
            self.requests[key] = []

        self.requests[key] = [
            ts for ts in self.requests[key] if ts > window_start
        ]

        remaining = self.max_requests - len(self.requests[key])

        if remaining > 0:
            self.requests[key].append(now)
            return True, {"remaining": remaining, "reset": window_start + self.window_seconds}

        reset_at = self.requests[key][0] + self.window_seconds
        return False, {"remaining": 0, "reset": reset_at}
```

### Retry Logic

Clients should respect `Retry-After` and use exponential backoff:

```python
import httpx
import asyncio

async def call_with_retry(url: str, max_retries: int = 3):
    for attempt in range(max_retries + 1):
        response = await httpx.AsyncClient().get(url)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            await asyncio.sleep(retry_after)
            continue

        return response

    raise Exception("Max retries exceeded")
```

---

## 7. Case Study: Stripe's API Design

Stripe's API is widely regarded as a gold standard for API design. Here's what makes it exceptional.

### Idempotency Keys

Every mutating request can include an idempotency key. If a request fails (network timeout, 5xx), the client can safely retry with the same key without creating a duplicate:

```
POST /v1/charges
Idempotency-Key: abc123

{
  "amount": 2000,
  "currency": "usd",
  "source": "tok_visa"
}
```

**Server behavior:**
- First request: processed normally, response cached for 24 hours
- Retry with same key: returns cached response, no re-execution
- Different key: treated as a new request

### Versioning Strategy

Stripe uses **date-based versioning**:

```
Stripe-Version: 2025-01-01
```

This is passed as a header. Each version is stable — old versions keep working indefinitely. New API changes are opt-in via the version header.

### Error Response Format

```json
{
  "error": {
    "type": "card_error",
    "code": "card_declined",
    "decline_code": "insufficient_funds",
    "message": "Your card has insufficient funds.",
    "param": "source",
    "charge": "ch_3N2x..."
  }
}
```

Notice the `decline_code` — Stripe provides granular, machine-readable error reasons that map to business logic, not just HTTP status codes.

### API Explorer and SDKs

Stripe provides:
- **Interactive API Explorer** — test requests in the browser with real credentials
- **Official SDKs** in 7+ languages, all auto-generated from their OpenAPI spec
- **Idempotency** baked into every SDK method
- **Type hints** and auto-complete in every supported language

### What You Can Learn from Stripe

| Stripe Practice | Why It Works |
|----------------|-------------|
| Idempotency keys by default | Safe retries over unreliable networks |
| Date-based versioning | No version arms race, stable over years |
| Granular error codes | Clients can handle specific failure modes |
| Machine-readable + human-readable errors | Debugging + automation |
| Auto-generated SDKs | Consistency across languages |
| Interactive docs with live testing | Reduced friction for integration |

---

## 8. Practice Exercise

### Design an API for a Book Library

Design a REST API for a library management system with these requirements:

1. **Books**: CRUD operations, search by title/author/genre
2. **Members**: Registration, profile management
3. **Loans**: Borrow/return books, track due dates
4. **Overdue fines**: Calculate and apply fines for late returns

**Your deliverables:**

1. Resource naming scheme with endpoints
2. Request/response JSON schemas for at least 3 endpoints
3. Error response format for 3 different error cases
4. Pagination strategy for listing books
5. Rate limiting plan (which endpoints, what limits)

**Starter template:**

```
Base URL: https://api.library.example.com/v1

Endpoints to design:
- GET    /books
- GET    /books/{id}
- POST   /loans
- GET    /members/{id}/loans
- POST   /members/{id}/payments
```

**Hints to consider:**
- How do you represent the relationship between Books, Members, and Loans?
- What status codes should POST /loans return for success, already-borrowed, and not-found?
- How do you handle overdue fine calculation — eagerly or on-read?

## 9. Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Verbs in resource paths** | `/getUser`, `/createOrder` discard the meaning HTTP methods already carry | Nouns for resources; methods for operations |
| **200 OK with an error in the body** | Clients, proxies, and monitoring all read the status code — a 200 error is invisible to every one of them | Correct status code plus a machine-readable body |
| **Unpaginated list endpoints** | The first large tenant takes down the endpoint, and removing it later is a breaking change | Paginate from day one, with a default *and* maximum page size |
| **Offset pagination over a live dataset** | Inserts and deletes shift rows between pages, so items are duplicated and skipped | Cursor pagination keyed on a stable sort |
| **Sorting without a unique tiebreaker** | Rows with equal sort keys have no defined order, so pages overlap | Always append a unique column: `sort=-created_at,id` |
| **Sorting on arbitrary columns** | `?sort=-description` on 10M rows is a full scan any caller can trigger | Allowlist sortable (indexed) fields; 400 on anything else |
| **Breaking changes without a version** | Clients you don't control fail silently in production | Additive changes in place; new version for real breaks, with `Deprecation`/`Sunset` headers |
| **Inconsistent error shapes** | Every client writes bespoke parsing per endpoint | One envelope everywhere — RFC 9457 Problem Details is a good default |
| **Leaking internals in error messages** | Stack traces and SQL fragments are reconnaissance for an attacker | Generic message plus a `request_id`; keep detail in your logs |
| **No rate limit headers** | Clients can't back off intelligently, so they retry blindly into the limit | `X-RateLimit-*` on success, `Retry-After` on 429 |
| **PATCH that replaces the resource** | Clients lose fields they never mentioned | PATCH merges; PUT replaces. Honour the distinction |
| **`allow_origins=["*"]` with credentials** | Any site can act as the logged-in user; browsers reject the combination for good reason | Explicit origin allowlist |

---

## 10. Discussion Questions

### Q1: Your team is building a mobile app and a web dashboard that consume the same backend. Which API style would you choose and why?

**Model Answer:**

REST is likely the best choice. Mobile and web clients both benefit from HTTP caching, simple JSON payloads, and broad tooling support. GraphQL could be justified if the clients have very different data needs (mobile needs minimal payloads, web needs rich data) — but adds complexity with schema management, caching challenges, and a learning curve. gRPC is unnecessary here since both clients are browser-based and benefit from REST's simplicity. If you need real-time features (chat, notifications), add WebSockets alongside your REST API rather than switching the entire architecture.

### Q2: A client reports they're getting 409 Conflict when creating a resource. Is this a bug in your API or the client?

**Model Answer:**

Neither, necessarily. A 409 Conflict means the request is valid in structure but violates a state constraint — typically a duplicate. The API should include enough detail in the error response for the client to understand and resolve the conflict. Common causes: creating a resource that already exists (email already registered, order already placed). The client should handle 409 by either retrying with different data, checking if the resource already exists first, or using an idempotency key. The API's job is to make the conflict reason clear enough for the client to act on.

### Q3: Should all your microservices use gRPC internally, or should some use REST?

**Model Answer:**

It depends on the service's characteristics. Use gRPC for high-throughput, latency-sensitive internal communication where you need streaming or strong typing. Use REST for services that need to support external consumers, browser clients, or where simplicity outweighs performance. A mixed approach is common and healthy: gRPC for the internal mesh, REST for the public-facing gateway. The key is having a consistent boundary protocol — if your API gateway exposes REST, internal services can use whatever makes sense.

### Q4: How do you handle API breaking changes when you have thousands of clients?

**Model Answer:**

Layer your strategy: (1) Never break existing versions — once released, a version must keep working. (2) For additive changes, just add them without a version bump (new fields, new endpoints). (3) For breaking changes, release a new version with a long sunset window (6-12 months minimum). (4) Communicate proactively — deprecation headers, email notifications, migration guides. (5) Monitor usage of old versions to see who's still on them. (6) Consider tools like API linters to catch accidental breaking changes. Stripe's date-based versioning model is a good reference — each change is opt-in via a header, and old versions never break.

### Q5: Your rate limiter is returning 429s but your monitoring shows the server isn't under load. What's happening?

**Model Answer:**

Several possibilities: (1) The rate limit configuration is too restrictive for the actual usage pattern — review the limits per tier. (2) A single client is hammering the API legitimately — check per-user limits. (3) The rate limiter is counting requests across all endpoints when it should be per-endpoint. (4) Distributed rate limiting has sync issues — Redis keys might be expiring at different times across nodes. (5) The rate limiter is counting health checks or background requests. (6) Clock skew in a distributed system is causing premature resets. Check the rate limit headers in the 429 response to understand which limit is being hit.

---

## 11. Key References

- **REST**: [RFC 7231 — HTTP/1.1 Semantics](https://tools.ietf.org/html/rfc7231), Roy Fielding's [dissertation](https://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm)
- **gRPC**: [grpc.io documentation](https://grpc.io/docs/), [Protocol Buffers Language Guide](https://developers.google.com/protocol-buffers/docs/proto3)
- **GraphQL**: [graphql.org specification](https://graphql.org/learn/), [Apollo GraphQL docs](https://www.apollographql.com/docs/)
- **RFC 9457**: [Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457) (obsoletes RFC 7807)
- **Stripe API**: [stripe.com/docs/api](https://stripe.com/docs/api)
- **Richardson Maturity Model**: Leonard Richardson's [presentation at QCon](https://martinfowler.com/articles/richardsonMaturityModel.html)

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 04: Load Balancing](../04-load-balancing/) | Rate limiting works alongside load balancing to distribute and throttle traffic |
| [Module 13: Security](../13-security/) | API security covers authentication, authorization, and input validation |
| [Module 06: Microservices](../06-microservices/) | API design is the contract layer for inter-service communication |

---

## Summary

```
┌──────────────────────────────────────────────────────────┐
│                   API Design Principles                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Resources are nouns, not verbs                       │
│  2. HTTP methods are your vocabulary — use them right    │
│  3. Status codes are a contract — be precise             │
│  4. Version explicitly, deprecate responsibly            │
│  5. Errors should be machine-readable AND human-friendly │
│  6. Rate limit everything — your future self will thank  │
│  7. Pick REST, gRPC, or GraphQL based on the consumer    │
│  8. Study great APIs (Stripe, GitHub) — steal patterns   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 13: Security](../13-security/README.md)

**Next:** [Module 15: Observability](../15-observability/README.md)

---

*Module 14 of 22 in the System Design Playground*
