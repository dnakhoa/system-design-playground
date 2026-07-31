# Module 15: Observability

> "Debugging is a process of elimination. Observability is what lets you eliminate things quickly."

Every system in this course fails eventually. Modules 07 and 13 told you how to
*survive* failure; this module is about how you **find out what happened**. A
distributed system you cannot inspect is a system you cannot operate — and by
the time you have twenty services, "it's slow" is not a bug report, it's a
research project.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 14 | API Design | [../14-api-design/](../14-api-design/) |
| **Module 15** | **Observability** | **(current)** |
| Module 16 | LLM Inference Serving | [../16-llm-inference-serving/](../16-llm-inference-serving/) |

---

## Learning Objectives

By the end of this module, you will be able to:

1. **Distinguish** monitoring from observability, and explain why dashboards alone cannot answer novel questions
2. **Choose** metric types correctly, and predict the cardinality cost of a label before you ship it
3. **Explain** why percentiles cannot be averaged, and aggregate latency correctly across instances
4. **Design** structured logging with trace correlation, sampling, and PII controls
5. **Implement** distributed tracing with context propagation, and choose between head- and tail-based sampling
6. **Build** SLO burn-rate alerts that page on symptoms rather than causes
7. **Control** observability cost, which routinely reaches 10-30% of infrastructure spend
8. **Debug** a latency regression using metrics, traces, and logs in the right order

---

## Table of Contents

1. [Monitoring vs Observability](#1-monitoring-vs-observability)
2. [Metrics](#2-metrics)
3. [Logs](#3-logs)
4. [Distributed Tracing](#4-distributed-tracing)
5. [Correlation: Making the Pillars One System](#5-correlation-making-the-pillars-one-system)
6. [SLO-Based Alerting](#6-slo-based-alerting)
7. [Dashboards and Runbooks](#7-dashboards-and-runbooks)
8. [Cost Control](#8-cost-control)
9. [Case Study: Google Dapper](#9-case-study-google-dapper)
10. [Worked Incident: A p99 Regression](#10-worked-incident-a-p99-regression)
11. [Practice Exercise](#11-practice-exercise)
12. [Common Mistakes](#12-common-mistakes)
13. [Discussion Questions](#13-discussion-questions)
14. [Key References](#14-key-references)

---

## 1. Monitoring vs Observability

These get used interchangeably. They are not the same thing, and the difference
determines whether you can debug a novel outage.

**Monitoring** answers questions you knew to ask. You predicted a failure mode,
built a dashboard and an alert for it, and now you watch it. Monitoring handles
**known unknowns**: you know CPU can saturate, you just don't know when.

**Observability** is the property of being able to answer questions you *didn't*
anticipate, without shipping new code. It handles **unknown unknowns**: "requests
from Android clients in Brazil on app version 4.2 fail, but only when they hit
the shard that was rebalanced on Tuesday." Nobody builds that dashboard in
advance.

```
  MONITORING                       │  OBSERVABILITY
  ─────────────────────────────────┼──────────────────────────────────
                                   │
  "Is the error rate above 1%?"    │  "What do the failing requests
                                   │   have in common?"
   ┌───────────────────┐           │
   │        ███        │           │   ┌──────────────────────────┐
   │      ███████      │           │   │ user_tier=free     12%   │
   │   █████████████   │           │   │ region=sa-east-1   89%  ←│
   └───────────────────┘           │   │ app_version=4.2    91%  ←│
                                   │   │ endpoint=/checkout  8%   │
   One question, fixed when the    │   └──────────────────────────┘
   dashboard was built.            │
                                   │   Questions formed AFTER the
   Pre-aggregated. Cheap. Fast.    │   incident started.
   Blind to anything nobody        │
   thought to ask in advance.      │   Needs high-cardinality,
                                   │   high-dimensionality data.
```

### The Practical Test

Ask this of your current setup:

> A user reports a slow request and gives you a timestamp. Can you find *that
> specific request*, see every service it touched, and see how long each one
> took — in under five minutes, without deploying anything?

If no, you have monitoring, not observability.

### The "Three Pillars" Frame Is Useful but Leaky

You will see observability described as three pillars: **logs**, **metrics**, and
**traces**. It is a useful teaching taxonomy and this module follows it. But be
aware of what it gets wrong in practice:

| The pillar model implies | Reality |
|--------------------------|---------|
| Three separate systems is the natural design | Three systems means three query languages, three bills, and manual correlation during an incident |
| Each pillar answers its own questions | Real debugging bounces between them constantly: metric shows *that* something broke, trace shows *where*, logs show *why* |
| More pillars is better | An unqueryable pillar is a cost centre. Coverage without correlation does not shorten an outage |

The underlying goal is one **wide structured event** per unit of work — a record
with every dimension you might later want to filter on — from which metrics,
traces, and logs are all derived views. Section 5 covers how to approximate this
even with three separate backends.

---

## 2. Metrics

Metrics are numeric measurements aggregated over time. They are cheap, they
compress well, and they are what you alert on. They are also the pillar people
most often misuse.

### 2.1 The Four Metric Types

| Type | Semantics | Example | Never use it for |
|------|-----------|---------|------------------|
| **Counter** | Monotonically increasing; only goes up (or resets to 0 on restart) | `http_requests_total`, `bytes_sent_total` | Anything that can decrease |
| **Gauge** | A value that goes up and down | `queue_depth`, `memory_bytes`, `active_connections` | Rates — you'll miss everything between scrapes |
| **Histogram** | Counts observations into configurable buckets | `request_duration_seconds` | High-cardinality labels (each bucket multiplies series) |
| **Summary** | Client-side computed quantiles | Legacy latency reporting | **Aggregating across instances** — see below |

The counter/gauge distinction matters more than it looks. Counters are
**restart-safe**: a consumer computes `rate()` over the difference, so a reset to
zero is detectable and handled. A gauge sampled every 15 seconds silently misses
every spike that begins and ends between scrapes.

```
  COUNTER — correct for events     │  GAUGE — wrong for events
  ─────────────────────────────────┼──────────────────────────────────
  requests_total (cumulative)      │  requests_in_last_15s (sampled)
                                   │
  1000 ┤            ╱              │   40 ┤  ╷        ╷
   800 ┤       ╱                   │   30 ┤  │        │
   600 ┤   ╱                       │   20 ┤  │   ╷    │
   400 ┤╱                          │   10 ┤  │   │    │
       └──────────────             │    0 ┴──┴───┴────┴────────
                                   │         ▲
  rate() reconstructs throughput   │         └─ everything between two
  exactly, and a restart to 0 is   │            samples is invisible —
  detectable and handled.          │            including the outage.
```

### 2.2 Histogram vs Summary: The Aggregation Trap

This is the single most common metrics mistake, and it is subtle because
summaries look *more* precise.

A **summary** computes quantiles inside each process. Instance A reports
"my p99 is 50ms", instance B reports "my p99 is 800ms". You now have two
numbers and **no valid way to combine them** — quantiles are not additive, and
the raw observations they were computed from are already gone.

A **histogram** reports bucket counts: "412 requests under 10ms, 900 under
50ms, 1000 under 100ms…". Bucket counts *are* additive. Sum them across
instances, then compute the quantile from the merged distribution.

```promql
# WRONG — averages per-instance quantiles. Mathematically meaningless.
avg(http_request_duration_seconds{quantile="0.99"})

# RIGHT — merge bucket counts across instances, then take the quantile.
histogram_quantile(
  0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)
```

### 2.3 Why You Cannot Average Percentiles

Make this concrete, because "avg of p99" appears on a great many real dashboards:

```
  Instance A:  1,000,000 requests/sec,  p99 =   50ms
  Instance B:          1 request/sec,   p99 = 5000ms

  avg(p99) = (50 + 5000) / 2 = 2525ms          ← what the dashboard shows
  true fleet p99            ≈ 50ms             ← what users experience

  Instance B contributes 1 of 1,000,001 requests. It cannot move the 99th
  percentile of the combined distribution at all. The dashboard is off by
  a factor of 50, and it is off in the ALARMING direction — so you will
  chase a latency problem that does not exist.
```

The reverse error is just as common: `max(p99)` across instances *overstates*
fleet latency, because it reports the worst instance as though it were typical.

**Three rules:**

1. Percentiles are computed from a distribution, so aggregate the
   **distribution** (buckets), never the percentiles.
2. A percentile of a percentile is meaningless. `p99` of hourly `p99` values is
   not a daily `p99`.
3. Percentiles do not compose across a request path. A request touching five
   services each at p99=10ms does **not** take 50ms at p99 — it is far more
   likely to take ~10ms plus four typical latencies. But the chance of hitting
   *at least one* slow hop grows with fan-out, which is why tail latency gets
   worse as you add services.

### 2.4 What to Measure: Three Frameworks

These overlap and that is fine — use the one that fits what you're measuring.

**Four Golden Signals** (Google SRE) — for any user-facing system:

| Signal | Question | Typical metric |
|--------|----------|----------------|
| **Latency** | How long do requests take? | Histogram, split by success/failure |
| **Traffic** | How much demand? | Requests/sec, by endpoint |
| **Errors** | What fraction fail? | Error rate, by class |
| **Saturation** | How full is the system? | Queue depth, connection pool use, memory headroom |

**RED** (Tom Wilkie) — for request-driven *services*: **R**ate, **E**rrors,
**D**uration. A tighter subset of the golden signals; good default for every
microservice dashboard.

**USE** (Brendan Gregg) — for *resources* (CPU, disk, network, pools):
**U**tilization, **S**aturation, **E**rrors. This is where you find the cause
after RED tells you there's a problem.

> **Split latency by outcome.** A fast 500 and a slow 200 are different events,
> but a single latency histogram averages them together. During an outage where
> requests fail fast, your p99 will *improve* while users see nothing but
> errors. Always record `duration` labelled by status class.

### 2.5 Cardinality: The Cost Multiplier

Every unique combination of label values creates a separate time series. Series
count is the **product** of label cardinalities, not the sum:

```
  http_requests_total{method, status, endpoint, pod}

    method:     5  (GET, POST, PUT, PATCH, DELETE)
    status:     8  (200, 201, 400, 401, 403, 404, 429, 500)
    endpoint: 200
    pod:       50

  series = 5 × 8 × 200 × 50 = 400,000        ← already substantial

  Now add user_id (1,000,000 users):

  series = 400,000 × 1,000,000 = 4 × 10^11   ← 400 billion series
```

That does not degrade gracefully; it takes the metrics backend down. The
offending label is usually added with the best intentions ("we should be able to
see per-user latency").

**Labels that are almost always wrong in metrics:**

```
  ✗ user_id, session_id, request_id, trace_id  (unbounded)
  ✗ email, IP address                          (unbounded + PII)
  ✗ full URL path with IDs: /orders/8a3f-...   (unbounded)
  ✗ error message text                         (unbounded, and mutates
                                                 whenever someone edits a string)
  ✗ timestamp                                  (unbounded by construction)

  ✓ endpoint TEMPLATE: /orders/{id}            (bounded by route count)
  ✓ status_class: 2xx/4xx/5xx                  (5 values)
  ✓ error_code: enum from your own taxonomy    (bounded, stable)
  ✓ region, tier, model_name                   (small, known sets)
```

**Where per-request detail belongs:** traces and logs, which are designed for
high cardinality. That is the actual division of labour between the pillars —
metrics for bounded dimensions you aggregate, traces/logs for unbounded
dimensions you filter.

```python
"""Estimate series count before shipping a label — cheaper than an outage."""

from dataclasses import dataclass, field


@dataclass
class MetricSpec:
    name: str
    # label name -> estimated distinct values
    labels: dict[str, int] = field(default_factory=dict)

    def series_count(self) -> int:
        total = 1
        for cardinality in self.labels.values():
            total *= cardinality
        return total

    def worst_label(self) -> tuple[str, int] | None:
        """The label whose removal saves the most series."""
        if not self.labels:
            return None
        return max(self.labels.items(), key=lambda kv: kv[1])


# Rough industry figures: ~1-3 KB of RAM per active series in a
# Prometheus-style TSDB. Use your own backend's number.
BYTES_PER_SERIES = 2_000
SERIES_BUDGET = 1_000_000


def review(spec: MetricSpec) -> None:
    count = spec.series_count()
    ram_mb = count * BYTES_PER_SERIES / 1_048_576
    verdict = "OK" if count <= SERIES_BUDGET else "REJECT"

    print(f"{spec.name}: {count:,} series, ~{ram_mb:,.0f} MB  [{verdict}]")
    if verdict == "REJECT":
        label, card = spec.worst_label()
        remaining = count // card
        print(f"  Dominant label {label!r} ({card:,} values).")
        print(f"  Dropping it leaves {remaining:,} series.")
        print("  Move that dimension to traces or logs instead.")


review(MetricSpec("http_requests_total", {
    "method": 5, "status": 8, "endpoint": 200, "pod": 50,
}))

review(MetricSpec("http_requests_by_user", {
    "method": 5, "status": 8, "endpoint": 200, "pod": 50,
    "user_id": 1_000_000,
}))
```

> **Watch for silent cardinality growth.** A label that is bounded today can
> become unbounded later: `error_code` is fine until someone interpolates a
> record ID into it. Alert on *series count per metric*, not just total, so you
> catch the specific metric that started growing.

---

## 3. Logs

Logs are timestamped records of discrete events. They carry the most detail per
event and cost the most per byte — usually the largest line on an observability
bill.

### 3.1 Structured, Not Prose

```python
# Unstructured — human-readable, machine-hostile.
log.info(f"User {user_id} checkout failed after {elapsed}ms: {err}")
# To count failures by error type you now need a regex, and the regex
# breaks the moment anyone rewords the message.

# Structured — every field queryable without parsing.
log.info("checkout_failed", extra={
    "event":      "checkout_failed",
    "user_id":    user_id,
    "duration_ms": elapsed,
    "error_code": err.code,
    "cart_value": cart.total_cents,
    "trace_id":   current_trace_id(),
})
```

Structured logging turns "grep and hope" into an actual query:

```
  event="checkout_failed" AND cart_value > 10000 AND region="eu-west-1"
  | count by error_code
```

The rule: **the message is an identifier, not a sentence.** Keep it a stable
event name so it can be grouped; put the variables in fields.

### 3.2 A Production Logging Setup

```python
import contextvars
import json
import logging
import time
import uuid

# Request-scoped context, propagated automatically to every log line
# emitted while handling the request — including from deep library code
# that has no idea a request exists.
_request_context: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "request_context", default={}
)

# Fields that must never reach the log pipeline. Redaction belongs HERE,
# at the formatter, not at each call site — one missed call site is a
# compliance incident.
REDACT = frozenset({
    "password", "token", "authorization", "api_key", "secret",
    "card_number", "cvv", "ssn", "email", "phone",
})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }
        payload.update(_request_context.get())

        # Merge per-call fields passed via extra={...}
        standard = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
        standard |= {"message", "asctime"}
        for key, value in record.__dict__.items():
            if key not in standard:
                payload[key] = value

        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
            payload["stack"] = self.formatException(record.exc_info)

        redacted = {
            k: ("[REDACTED]" if k.lower() in REDACT else v)
            for k, v in payload.items()
        }
        return json.dumps(redacted, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def begin_request(trace_id: str | None = None, **fields) -> str:
    """Bind request-scoped fields. Call once per request at the edge."""
    trace_id = trace_id or uuid.uuid4().hex
    _request_context.set({"trace_id": trace_id, **fields})
    return trace_id


configure_logging()
log = logging.getLogger("checkout")

begin_request(user_tier="premium", region="eu-west-1")
log.info("checkout_started", extra={"cart_value": 24999})
log.warning("payment_retry", extra={"attempt": 2, "error_code": "gateway_timeout"})
# => {"ts": "...", "level": "INFO", "event": "checkout_started",
#     "logger": "checkout", "trace_id": "9f2c...", "user_tier": "premium",
#     "region": "eu-west-1", "cart_value": 24999}
```

Two design points worth copying:

- **`contextvars`, not a global.** It is coroutine- and thread-safe, so
  concurrent requests do not leak each other's context. A module-level dict
  would interleave fields under load.
- **Redaction at the formatter.** Every log line passes through one function, so
  there is exactly one place to audit. Redacting at call sites guarantees that
  eventually somebody forgets.

### 3.3 Levels That Mean Something

Levels are only useful if they map to *actions*. Most codebases degrade into
everything being INFO or everything being ERROR.

| Level | Meaning | Who reads it |
|-------|---------|--------------|
| **ERROR** | The request failed and a human should eventually look | Alerts, on-call |
| **WARN** | Degraded but handled — a retry succeeded, a fallback fired | Trend dashboards; a *rising* WARN rate is a leading indicator |
| **INFO** | A significant state change: request completed, job started | Post-hoc investigation |
| **DEBUG** | Developer detail, off in production (or sampled) | Local dev, targeted debugging |

> **A caught exception is not automatically an ERROR.** If your code retried and
> succeeded, the user experienced success — that is WARN. Logging it as ERROR
> trains on-call to ignore ERROR, which is how you miss the real one.

### 3.4 Sampling and Retention

At scale you cannot keep every log line. Sample by *value*, not uniformly:

```
  Keep 100%:  errors, and anything on a failed trace
              (rare, and exactly what you need during an incident)

  Keep 100%:  audit and security events
              (compliance requirement, not an optimization target)

  Keep 1-10%: successful request logs
              (high volume, low information — the interesting ones
               are already captured by metrics)

  Keep 0%:    health checks, readiness probes, static asset hits
              (pure noise; often 30-60% of raw log volume)
```

Retention should be tiered, because the value of a log line drops off a cliff
after a few days:

| Age | Tier | Why |
|-----|------|-----|
| 0-7 days | Hot, fully indexed | Active incident investigation |
| 7-30 days | Warm, slower queries | Trend analysis, "did this start last week?" |
| 30 days-1 year | Cold object storage | Compliance, rare forensics |
| Beyond | Deleted, or aggregated to metrics | Storing it is a liability, not an asset |

**Consistent sampling matters.** If service A keeps a request's log and service
B drops it, you get a trace with holes. Make the sampling decision **once, at
the edge**, propagate it in the trace context, and have every service honour it.
That way a sampled request is sampled end-to-end.

---

## 4. Distributed Tracing

A trace follows one request across every service it touches. It is the only
pillar that answers "where did the time go?" in a system you cannot hold in
your head.

### 4.1 Traces, Spans, and Context

```
  Trace: one request. Spans: units of work within it.

  trace_id = 4bf92f3577b34da6a3ce929d0e0e4736

  ├─ POST /checkout ─────────────────────────────────── 847ms  [gateway]
  │  ├─ auth.verify ──── 12ms                                  [auth-svc]
  │  ├─ cart.get ─────────── 34ms                              [cart-svc]
  │  │  └─ redis.GET ── 2ms                                    [redis]
  │  ├─ inventory.reserve ────────── 61ms                      [inv-svc]
  │  │  └─ postgres.UPDATE ──── 48ms                           [postgres]
  │  ├─ payment.charge ──────────────────────────── 718ms  ←   [pay-svc]
  │  │  ├─ fraud.score ──── 41ms                               [fraud-svc]
  │  │  └─ stripe.POST ────────────────────── 665ms  ←         [external]
  │  └─ notify.enqueue ── 8ms                                  [kafka]
  │
  Total 847ms, of which 665ms is one external call.
  No metric would have told you that. Every metric would have
  told you /checkout is slow.
```

Each span carries: a `trace_id` shared by the whole request, its own `span_id`,
its `parent_span_id`, a start time and duration, plus attributes and events.

### 4.2 Context Propagation

Tracing works only if the identifiers survive every network hop. The
interoperable standard is **W3C Trace Context**, a header every major vendor
now accepts:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             │  │                                │                │
             │  │                                │                └─ flags (01 = sampled)
             │  │                                └─ parent span id (16 hex)
             │  └─ trace id (32 hex, globally unique)
             └─ version

tracestate: vendor1=value1,vendor2=value2      (optional vendor data)
```

**Propagation is where tracing breaks in practice.** The failure is always the
same shape: a boundary that drops the header, producing two disconnected traces
instead of one. Usual suspects:

| Boundary | What goes wrong |
|----------|-----------------|
| Message queues | Headers aren't part of the payload — you must inject them into message metadata explicitly |
| Thread pools / executors | Context is thread-local; submitting work loses it unless you copy context across |
| Async / callbacks | Same problem, different mechanism — the continuation runs without the context |
| Batch jobs | A batch handling 1,000 messages has 1,000 parent traces; use span **links**, not a fake parent |
| Third-party SDKs | Some strip unknown headers. Verify rather than assume |

```python
"""OpenTelemetry: instrument a service and propagate across a queue."""

from opentelemetry import trace
from opentelemetry.propagate import extract, inject

tracer = trace.get_tracer(__name__)


def handle_checkout(request) -> dict:
    # Continue the caller's trace by extracting context from inbound headers.
    # Without this, this service starts a NEW trace and the connection to
    # everything upstream is lost.
    context = extract(request.headers)

    with tracer.start_as_current_span("checkout", context=context) as span:
        # Attributes are high-cardinality-safe — unlike metric labels, this
        # is exactly where per-request identifiers belong.
        span.set_attribute("user.id", request.user_id)
        span.set_attribute("user.tier", request.user_tier)
        span.set_attribute("cart.value_cents", request.cart.total_cents)

        try:
            reservation = reserve_inventory(request.cart)
            payment = charge_payment(request.cart, request.user_id)
        except PaymentDeclined as exc:
            # record_exception captures the stack; set_status marks the span
            # as failed so it surfaces in error-filtered views and tail sampling.
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR, "declined"))
            raise

        span.set_attribute("payment.id", payment.id)
        return {"reservation": reservation.id, "payment": payment.id}


def reserve_inventory(cart):
    with tracer.start_as_current_span("inventory.reserve") as span:
        span.set_attribute("cart.item_count", len(cart.items))
        return inventory_client.reserve(cart)


def charge_payment(cart, user_id):
    with tracer.start_as_current_span("payment.charge") as span:
        span.set_attribute("payment.amount_cents", cart.total_cents)
        return payment_client.charge(cart.total_cents, user_id)


def publish_order_event(order) -> None:
    """Crossing a queue: inject context into message headers by hand."""
    with tracer.start_as_current_span("order.publish") as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination", "orders")

        headers: dict[str, str] = {}
        inject(headers)  # writes traceparent/tracestate into `headers`

        kafka_producer.send(
            "orders",
            value=order.serialize(),
            # Kafka headers want bytes.
            headers=[(k, v.encode()) for k, v in headers.items()],
        )


def consume_order_event(message) -> None:
    """The consumer extracts context, so the trace spans the queue."""
    carrier = {k: v.decode() for k, v in (message.headers or [])}
    context = extract(carrier)

    with tracer.start_as_current_span("order.process", context=context) as span:
        span.set_attribute("messaging.system", "kafka")
        process_order(message.value)
```

### 4.3 Sampling: Head vs Tail

Tracing every request at scale costs more than the system being traced. You must
sample — and *when* you decide changes what you can debug.

```
  HEAD-BASED SAMPLING
  Decide at the first service, propagate the decision.

    ingress ──► "keep this one" (1%) ──► all downstream services honour it
                       │
                       └─► consistent, complete traces
                           BUT: the decision predates knowing the
                           outcome, so you keep 1% of errors too —
                           and errors are what you actually need.

  TAIL-BASED SAMPLING
  Buffer all spans, decide after the trace completes.

    all services ──► collector buffers the full trace ──► policy decides
                                                            │
      keep 100% of: errors, traces slower than p99,          │
                    anything touching a new deploy    ◄──────┘
      keep 1% of:   fast successful traces

                           BUT: the collector must hold every span for the
                           trace-completion window (typically 10-60s), and
                           all spans of a trace must reach the SAME
                           collector instance — which needs trace-aware
                           load balancing, not round-robin.
```

| | Head-based | Tail-based |
|---|-----------|-----------|
| **Decision point** | Request start | After trace completes |
| **Cost** | Low — unsampled spans never generated | Higher — all spans transmitted and buffered |
| **Keeps all errors** | No | Yes |
| **Infrastructure** | Trivial | Stateful collectors, trace-aware routing |
| **Good for** | Getting started; uniform high-volume traffic | Mature setups where debugging errors matters most |

**The pragmatic default:** head-based sampling at a low rate for baseline
traffic, plus a rule that forces `sampled=1` on anything already known to be
interesting at ingress — requests from internal test accounts, requests with a
debug header, and requests that have already errored at the edge. This gets most
of the benefit of tail sampling without the stateful collector tier.

---

## 5. Correlation: Making the Pillars One System

Three backends only shorten an outage if you can move between them in one hop.
Correlation is what makes that possible, and it is mostly an *identifier
discipline* problem rather than a tooling problem.

```
  THE PATH YOU WANT DURING AN INCIDENT

  1. ALERT fires        "checkout p99 > 2s, burn rate 14x"
         │              (metrics: something is wrong, and how badly)
         ▼
  2. EXEMPLAR           metric data point carries a trace_id from a
         │              request that landed in that slow bucket
         ▼
  3. TRACE              "665ms of 847ms is stripe.POST"
         │              (traces: WHERE the time went)
         ▼
  4. LOGS               filter by that trace_id
         │              "gateway_timeout, attempt 2, region eu-west-1"
         ▼
  5. CAUSE              (logs: WHY it happened)

  Four clicks, no guessing. Without correlation, step 2 becomes
  "search logs for the same time window and hope" — which during an
  incident means scanning millions of lines for the right needle.
```

### 5.1 The Three Requirements

**1. One `trace_id` everywhere.** Every log line, every span, and — via
exemplars — every latency histogram observation carries the same identifier.
This is the single highest-leverage thing in this module: it is cheap, and it
collapses the correlation problem to a filter.

**2. Exemplars on histograms.** An exemplar attaches a trace ID to a histogram
bucket, so "p99 spiked" links directly to a request that *was* slow. Without
exemplars you know the p99 moved but have no way to find an example of it.

```python
# Prometheus client: attach an exemplar when observing latency.
REQUEST_DURATION.labels(endpoint="/checkout", status_class="2xx").observe(
    elapsed_seconds,
    exemplar={"trace_id": current_trace_id()},
)
```

**3. Consistent resource attributes.** `service.name`, `service.version`,
`deployment.environment`, and region must be spelled identically across all
three pillars. If metrics say `svc="checkout"` and logs say
`service_name="checkout-service"`, no tool can join them — and you will discover
this at 3am.

### 5.2 Which Pillar Answers Which Question

| Question | Pillar | Why |
|----------|--------|-----|
| Is something wrong right now? | Metrics | Cheap, pre-aggregated, alertable |
| How bad, and is it getting worse? | Metrics | Trends and rates over time |
| Which component is slow? | Traces | Per-hop timing within one request |
| Is this one user or everyone? | Traces / wide events | High-cardinality filtering |
| Why did this specific request fail? | Logs | Full detail, stack traces |
| Did this start with the 14:03 deploy? | Metrics + version attribute | Compare before/after by `service.version` |
| What do all the failures have in common? | Wide events / high-cardinality | Group by every dimension at once |

Note the ordering implied here: **metrics to detect, traces to localize, logs to
explain.** Starting in logs is the most common time sink in an incident — you
are searching for a needle without first learning which haystack it is in.

---

## 6. SLO-Based Alerting

Most alerting is bad in a specific, diagnosable way: it pages on **causes**
instead of **symptoms**, and it fires at fixed thresholds instead of on
user-visible harm.

### 6.1 Alert on Symptoms

```
  CAUSE-BASED (page-generating, mostly ignorable)

    "CPU > 80% on web-07"        → Does anyone care? Auto-scaling may
                                   already be handling it. Maybe that box
                                   is doing legitimate work.
    "Disk 85% full"              → On a log volume that rotates? Noise.
    "Pod restarted"              → Kubernetes restarts pods. That's the job.
    "Memory > 90%"               → JVM heap sits at 90% by design.

  SYMPTOM-BASED (worth waking someone)

    "Checkout success rate < 99% for 5 minutes"
    "p99 latency > 2s, burning error budget 14x"
    "Order queue depth growing for 15 minutes with no drain"

  Symptoms describe what USERS experience. Causes belong on dashboards
  and in runbooks — you look at them AFTER a symptom alert fires, to
  find out why.
```

The test for any alert: **if this fires and nobody does anything, does a user
notice?** If no, it should not page. Demote it to a ticket or a dashboard panel.

### 6.2 Burn-Rate Alerts

Module 07 introduced error budgets. Burn-rate alerting is what turns a budget
into a paging policy that is neither too twitchy nor too slow.

**Burn rate** = how fast you are consuming budget relative to the rate that
would exactly exhaust it over the whole window. Burn rate 1 means you finish the
30-day window with exactly zero budget left. Burn rate 14.4 means you exhaust
30 days of budget in about 50 hours.

```
  30-day window = 720 hours

  budget_fraction_consumed = burn_rate × hours_elapsed / 720
  error_rate_threshold     = burn_rate × (1 − SLO)
  time_to_exhaustion       = 720 / burn_rate   hours

  For a 99.9% SLO (allowed error rate 0.1%):

  ┌────────────┬───────┬──────────────┬───────────────┬──────────┐
  │ Budget     │ In    │ Burn rate    │ Error rate    │ Action   │
  │ consumed   │       │              │ that triggers │          │
  ├────────────┼───────┼──────────────┼───────────────┼──────────┤
  │ 2%         │ 1 h   │ 14.4×        │ 1.44%         │ PAGE     │
  │ 5%         │ 6 h   │  6×          │ 0.60%         │ PAGE     │
  │ 10%        │ 3 d   │  1×          │ 0.10%         │ TICKET   │
  └────────────┴───────┴──────────────┴───────────────┴──────────┘

  Check: 2% in 1h → burn = 0.02 × 720 / 1  = 14.4  ✓
         5% in 6h → burn = 0.05 × 720 / 6  =  6    ✓
        10% in 3d → burn = 0.10 × 720 / 72 =  1    ✓
```

**Why multiple windows?** A single window is wrong in one direction or the
other. A 1-hour window alone is slow to fire on a small-but-steady leak. A
5-minute window alone fires on every blip. Two burn rates cover both: the fast
one catches acute outages, the slow one catches chronic degradation.

**Why pair each long window with a short one?** Without it, an alert keeps
firing long after the problem is resolved — the 1-hour average stays elevated
for an hour after recovery. Requiring the short window (1/12 of the long one) to
*also* be breaching means the alert clears promptly.

```python
"""Multi-window multi-burn-rate SLO alert evaluation."""

from dataclasses import dataclass

WINDOW_HOURS = 720  # 30-day SLO window


@dataclass(frozen=True)
class BurnRatePolicy:
    name: str
    budget_fraction: float   # e.g. 0.02 for "2% of budget"
    long_window_hours: float
    severity: str

    @property
    def burn_rate(self) -> float:
        return self.budget_fraction * WINDOW_HOURS / self.long_window_hours

    @property
    def short_window_hours(self) -> float:
        # One twelfth of the long window: long enough to be statistically
        # meaningful, short enough that the alert resolves quickly.
        return self.long_window_hours / 12

    def error_rate_threshold(self, slo: float) -> float:
        return self.burn_rate * (1 - slo)


POLICIES = (
    BurnRatePolicy("fast_burn",   0.02, 1,  "page"),
    BurnRatePolicy("medium_burn", 0.05, 6,  "page"),
    BurnRatePolicy("slow_burn",   0.10, 72, "ticket"),
)


def evaluate(slo: float, error_rate_over) -> list[str]:
    """`error_rate_over(hours)` returns the observed error rate for a window.

    Both the long AND short window must breach. The long window establishes
    that the problem is real; the short window establishes that it is still
    happening.
    """
    firing = []
    for policy in POLICIES:
        threshold = policy.error_rate_threshold(slo)
        long_breach = error_rate_over(policy.long_window_hours) > threshold
        short_breach = error_rate_over(policy.short_window_hours) > threshold

        if long_breach and short_breach:
            firing.append(
                f"[{policy.severity.upper()}] {policy.name}: "
                f"burn {policy.burn_rate:.1f}x "
                f"(>{threshold:.2%} errors); "
                f"budget gone in {WINDOW_HOURS / policy.burn_rate:.0f}h"
            )
    return firing


# A sustained 2% error rate against a 99.9% SLO.
def steady_two_percent(_hours: float) -> float:
    return 0.02


for alert in evaluate(0.999, steady_two_percent):
    print(alert)
# [PAGE] fast_burn: burn 14.4x (>1.44% errors); budget gone in 50h
# [PAGE] medium_burn: burn 6.0x (>0.60% errors); budget gone in 120h
# [TICKET] slow_burn: burn 1.0x (>0.10% errors); budget gone in 720h
```

Equivalent alerting rule in PromQL form:

```promql
# Fast burn: 14.4x over 1h AND still burning over the last 5m.
(
  (
    sum(rate(http_requests_total{status_class="5xx"}[1h]))
    / sum(rate(http_requests_total[1h]))
  ) > (14.4 * 0.001)
)
and
(
  (
    sum(rate(http_requests_total{status_class="5xx"}[5m]))
    / sum(rate(http_requests_total[5m]))
  ) > (14.4 * 0.001)
)
```

### 6.3 Alert Fatigue Is a Reliability Problem

An ignored alert is worse than no alert: it consumes attention and it teaches the
team that alerts are noise. Treat the alert set as something you actively curate.

| Symptom | Fix |
|---------|-----|
| More than ~2 pages per on-call shift | Raise thresholds, or fix what keeps firing |
| Alerts routinely resolve themselves | The threshold is too tight, or the window too short |
| A recurring alert with a known manual fix | Automate the fix, then delete the alert |
| An alert nobody can act on | Delete it. Undeletable-but-unactionable means it belongs on a dashboard |
| Alert with no runbook | Write one, or accept that the responder starts from zero at 3am |

> **Every paging alert needs a runbook link in the payload.** Not in a wiki
> someone has to find — in the alert itself. The responder is half-awake and
> under time pressure; make the next step unambiguous.

---

## 7. Dashboards and Runbooks

### 7.1 A Dashboard Per Question, Not Per Metric

The failure mode is the 60-panel dashboard that nobody reads because no panel
answers a question anyone is asking.

```
  ┌─────────────────────────────────────────────────────────────┐
  │  SERVICE: checkout          env: prod    version: 4.2.1     │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │  TOP ROW — "is it healthy?"  (the four golden signals)      │
  │  ┌───────────┬───────────┬───────────┬───────────┐         │
  │  │ Requests  │ Error     │ Latency   │ Saturation│         │
  │  │ /sec      │ rate %    │ p50/95/99 │ (pool %)  │         │
  │  └───────────┴───────────┴───────────┴───────────┘         │
  │                                                             │
  │  SECOND ROW — "how much budget is left?"                    │
  │  ┌─────────────────────────┬─────────────────────────┐     │
  │  │ SLO: 99.9%  ███████░░░  │ Burn rate (1h / 6h)     │     │
  │  │ 68% budget remaining    │ 0.4x / 0.9x             │     │
  │  └─────────────────────────┴─────────────────────────┘     │
  │                                                             │
  │  THIRD ROW — "where is it going wrong?"                     │
  │  ┌─────────────────────────┬─────────────────────────┐     │
  │  │ Errors by endpoint      │ Latency by dependency   │     │
  │  │ (which route is broken) │ (which hop is slow)     │     │
  │  └─────────────────────────┴─────────────────────────┘     │
  │                                                             │
  │  Deploy markers on every time axis ──┤ 14:03 v4.2.1        │
  └─────────────────────────────────────────────────────────────┘
```

**Deploy annotations are the highest-value, lowest-effort thing on a dashboard.**
Most incidents correlate with a change. A vertical line at each deploy turns
"when did this start?" from an investigation into a glance.

### 7.2 Rules That Keep Dashboards Useful

| Rule | Reason |
|------|--------|
| Golden signals in the top row, always | The responder should not scroll to learn whether it's broken |
| One screen, no scrolling, for the primary view | Anything below the fold is not read during an incident |
| p50 **and** p99 on the same axis | p50 shows the typical user; the gap between them shows the tail |
| Annotate deploys, config changes, feature flags | Change correlation is the fastest hypothesis generator |
| Link straight to traces and logs | A dashboard that dead-ends forces the responder to start over |
| Delete panels nobody looks at | Every unread panel dilutes attention on the ones that matter |

### 7.3 Runbooks

A runbook is not documentation; it is a decision procedure for someone with no
context at 3am.

```
  RUNBOOK: checkout error rate high

  1. IMPACT — how bad?
     Dashboard: <link>. Check error rate and burn rate.
     Under 1% with burn < 2x → ticket, not a page. Stop here.

  2. CHANGE — did we do this?
     Recent deploys: <link>. Feature flags: <link>.
     If a deploy landed within 30 min → roll back FIRST, diagnose after.

  3. LOCALIZE — where?
     Traces filtered to errors: <link>.
     Is one dependency responsible, or is it broad?

  4. MITIGATE — options in order of preference:
     a. Roll back the recent deploy
     b. Disable the feature flag <name>
     c. Shed load: enable degraded mode <link>
     d. Scale up: <command>

  5. ESCALATE — if not mitigated in 15 minutes:
     Payments: @payments-oncall. Infra: @infra-oncall.

  6. AFTER — file an incident, link the trace, schedule a review.
```

Note the ordering: **mitigate before diagnose.** Rolling back a suspicious
deploy takes two minutes; understanding why it broke takes an hour. Users care
about the first number.

---

## 8. Cost Control

Observability commonly runs 10-30% of total infrastructure spend, and it grows
super-linearly with traffic if nobody is watching. It is also the easiest budget
to cut badly — teams disable the thing that would have explained the next
outage.

### 8.1 Where the Money Goes

```
  Typical breakdown at moderate scale:

  Logs      ████████████████████████████  55%   ← volume × retention × indexing
  Metrics   ████████████                  25%   ← series count (cardinality)
  Traces    ████████                      15%   ← span volume × sampling rate
  Other     ██                             5%   ← synthetic checks, RUM, profiling

  The dominant cost driver differs per pillar:
    logs    → bytes ingested and how long they stay indexed
    metrics → ACTIVE SERIES, not data points
    traces  → spans retained after sampling
```

That metrics point surprises people: scraping the same series more often is
cheap; adding one high-cardinality label is not. Series count is the bill.

### 8.2 Reduction Ladder

Work top-down. The first three cost nothing in debugging power; the last is a
real trade-off.

| Step | Action | Typical saving | Debugging cost |
|------|--------|----------------|----------------|
| 1 | Drop health-check and static-asset logs | 30-60% of log volume | None — pure noise |
| 2 | Tier retention (7d hot, 30d warm, 1y cold) | 40-70% of log cost | Almost none |
| 3 | Delete unused metrics and dashboards | 10-30% of series | None — nobody queried them |
| 4 | Convert high-cardinality metrics to logs/traces | Can be 10x+ | None — better fit anyway |
| 5 | Sample successful request logs at 1-10% | 50-80% of remaining | Low — keep 100% of errors |
| 6 | Reduce trace sampling | Proportional | Real — fewer examples to debug with |
| 7 | Shorten hot retention below 7 days | Moderate | **High** — you lose week-over-week comparison |

**Find unused metrics before cutting blindly.** Most backends can report which
series were never queried:

```promql
# Series that exist but no dashboard or alert reads them.
# High-churn, never-queried metrics are the best deletion candidates.
count by (__name__) ({__name__=~".+"})
```

### 8.3 What Never to Cut

Some data pays for itself the first time you need it:

- **Error logs and failed traces.** Rare by volume, and they are the entire
  point of the system.
- **Audit and security events.** Compliance requirement, not an optimization
  target.
- **SLI metrics backing your SLOs.** Cutting these means you can no longer tell
  whether you are meeting commitments.
- **The `trace_id` on every log line.** Nearly free, and it is what makes
  correlation possible.

> **The asymmetry to keep in mind:** over-instrumenting wastes money linearly and
> visibly. Under-instrumenting costs you one long outage — and you discover the
> gap precisely when you can least afford to fix it. When uncertain, keep the
> data and cut retention rather than coverage.

---

## 9. Case Study: Google Dapper

Dapper is the system distributed tracing descends from — Zipkin, Jaeger, and
OpenTelemetry all trace their lineage to the 2010 paper. It is worth studying
because its constraints were unusually hostile and its answers are still the
answers.

### 9.1 The Constraints

| Requirement | Consequence |
|-------------|-------------|
| **Ubiquitous deployment** | Any service not instrumented becomes a blind spot that breaks the trace. Coverage had to be near-total. |
| **Continuous monitoring** | The interesting failures are unpredictable, so tracing must always be on — you cannot enable it after the fact. |
| **Negligible overhead** | Google would not accept a measurable latency cost on production serving paths. |
| **No developer effort** | Requiring per-team instrumentation work guarantees uneven, incomplete coverage. |

### 9.2 The Design Answers

**1. Instrument the shared infrastructure, not the applications.** Google's
services already shared RPC, threading, and control-flow libraries. Dapper
instrumented *those*. Almost every service got tracing without its team writing
any code — which is how "ubiquitous" became achievable at all.

**This is the transferable lesson.** The modern equivalent is
auto-instrumentation and service-mesh tracing: instrument the framework, the
HTTP client, and the sidecar. Reserve manual spans for business-meaningful
operations the framework cannot see.

**2. Aggressive sampling, and the realisation that it barely hurts.** Dapper
sampled a small fraction of requests. The insight was that for *performance*
analysis, high-volume paths reach statistical significance almost immediately —
a path served a million times a minute yields plenty of examples at 0.01%.

The caveat Dapper's authors noted, and which shapes modern practice: sampling
that low makes **rare** events hard to catch. This tension is exactly what
tail-based sampling (Section 4.3) exists to resolve — keep a little of the
common case, all of the exceptional case.

**3. Out-of-band collection.** Spans were written to local logs and shipped
asynchronously, never inline with the request. Trace collection therefore could
not add latency to, or fail, the request being traced.

**A rule worth adopting verbatim:** observability must never be on the critical
path. If your tracing backend goes down, requests should keep succeeding. A
blocking, unbuffered export turns a monitoring outage into a customer outage —
and it is a surprisingly common way to build one.

**4. A trace tree of spans with a shared ID.** Trace ID, span ID, parent span
ID — the model in Section 4.1 is Dapper's, essentially unchanged fifteen years
later.

### 9.3 What Changed Since

| Dapper (2010) | Today |
|---------------|-------|
| Proprietary, Google-internal | OpenTelemetry: vendor-neutral APIs and wire format |
| Head-based sampling only | Tail-based sampling widely available |
| Traces as a separate system | Correlation with metrics and logs via shared IDs and exemplars |
| Sampling rates in the 0.01% range | Higher rates common; tail sampling keeps 100% of errors |
| Custom propagation format | W3C Trace Context as an interoperable standard |

The architecture was right. What improved is that you no longer have to build it.

---

## 10. Worked Incident: A p99 Regression

Theory is easier to retain attached to a concrete investigation. Here is the
order the pillars actually get used.

**The page:**

```
  [PAGE] fast_burn: checkout SLO 99.9%, burn 14.4x (>1.44% errors)
         Runbook: https://runbooks/checkout-error-rate
```

### Step 1 — Metrics: how bad, and since when?

```
  Error rate, checkout                     Deploy markers
  3% ┤                    ╭──────────      │
  2% ┤                    │                ┤ 14:03  v4.2.1
  1% ┤                    │                ┤ 09:15  v4.2.0
  0% ┼────────────────────╯
     └──────────────────────────────
      13:00   13:30   14:00   14:30

  Onset: ~14:05. A deploy landed at 14:03.
```

Two minutes in and you have a prime suspect. **Per the runbook, this is already
enough to roll back** — you do not need to understand the bug to stop the
bleeding. Diagnosis continues in parallel.

### Step 2 — Metrics: is it everything, or one thing?

```
  Errors by endpoint:              Errors by region:
    /checkout      3.1%   ←          us-east-1   0.1%
    /cart          0.1%              eu-west-1   9.4%   ←
    /orders        0.1%              ap-south-1  0.1%

  Narrow: one endpoint, one region. Not a global failure.
```

This immediately rules out whole categories of cause. A code path that broke for
everyone would not be region-specific; a regional network fault would not be
endpoint-specific. Something about `/checkout` interacts with something regional.

### Step 3 — Traces: where is the time going?

Filter to failed `/checkout` traces in `eu-west-1`, and compare against a
successful trace from before the deploy:

```
  BEFORE (v4.2.0, 190ms)          AFTER (v4.2.1, 30s timeout)
  ├─ auth.verify        12ms      ├─ auth.verify        12ms
  ├─ cart.get           34ms      ├─ cart.get           34ms
  ├─ inventory.reserve  61ms      ├─ inventory.reserve  61ms
  ├─ payment.charge     78ms      ├─ payment.charge  ← 30s TIMEOUT
  │  ├─ fraud.score     41ms      │  ├─ fraud.score     41ms
  │  └─ stripe.POST     33ms      │  └─ (never started)
  └─ notify.enqueue      5ms      └─ (never reached)

  The failure is inside payment.charge, AFTER fraud.score returns
  and BEFORE the Stripe call is issued.
```

Traces have localized it to a few lines of code. Notice what metrics could not
have told you: the endpoint was slow, but not *which hop*, and not that the hop
failed *between* two of its own children.

### Step 4 — Logs: why?

Filter logs by `trace_id` from one failed trace:

```json
{"event":"payment_charge_started","trace_id":"4bf9...","region":"eu-west-1"}
{"event":"fraud_score_ok","trace_id":"4bf9...","score":0.02}
{"event":"secret_fetch","trace_id":"4bf9...","key":"stripe_api_key",
 "backend":"vault-eu-west-1"}
{"event":"secret_fetch_timeout","trace_id":"4bf9...","elapsed_ms":30000,
 "error_code":"deadline_exceeded","level":"ERROR"}
```

**Cause found.** v4.2.1 moved the Stripe API key from an environment variable to
a per-request Vault fetch. The `eu-west-1` Vault replica was overloaded by the
new request volume, so the fetch timed out — before the Stripe call could be
made.

### Step 5 — The fixes

| Horizon | Fix |
|---------|-----|
| **Immediate** | Roll back v4.2.1 (already done at step 1) |
| **Short term** | Cache the secret in-process with a TTL instead of fetching per request |
| **Medium term** | Timeout on the secret fetch measured in *milliseconds*, not 30s — and a fallback to the last known-good value |
| **Systemic** | The 30s timeout was inherited from a default nobody set deliberately. Audit timeout defaults across all clients (Module 07) |

### What Made This Fast

```
  Metrics  → detected it, dated it, and narrowed it to endpoint + region
  Traces   → localized it to one hop, and to a gap between two child spans
  Logs     → explained it, via trace_id correlation

  Total: minutes.

  Without correlation, step 4 would have been "search eu-west-1 logs
  around 14:05" — millions of lines, no way to isolate one request's
  path through them.

  Without traces, you would know /checkout was slow in one region and
  would be reading the v4.2.1 diff hoping something jumped out.

  Note also what the FIRST action was: roll back, at step 1, before
  any of the diagnosis. Mitigation and diagnosis are separate tracks.
```

---

## 11. Practice Exercise

### Design Observability for the Checkout Flow

You own the checkout path from Module 12: API gateway → checkout service →
inventory service → payment service → external payment gateway, plus a Kafka
topic for order events.

**Given:**

- 5,000 checkouts/minute at peak, 30 services total
- SLO: 99.9% success, p99 under 1s
- Budget ceiling: 15% of the platform's infrastructure spend
- PCI DSS applies — card data must never reach the log pipeline

**Deliverables:**

1. **Metrics.** Name the metrics for each of the four golden signals. For each,
   list its labels *and* compute the resulting series count. Stay under 100,000
   series for the checkout path.

2. **Cardinality decisions.** You want to answer "are premium users seeing more
   failures?" and "which specific user hit this error?" Which goes in a metric
   label and which does not? Justify with the series arithmetic.

3. **Traces.** Draw the span tree for one checkout. Mark where context
   propagation could break, and state how you'd preserve it across the Kafka
   boundary.

4. **Sampling.** Choose head- or tail-based and defend it at this volume. Give
   the sampling rate and state what you keep at 100%.

5. **Alerts.** Write the burn-rate policy: windows, burn rates, error-rate
   thresholds, and which page vs ticket. Show the arithmetic.

6. **PII.** Card numbers pass through the payment service. Where do you enforce
   redaction so a new call site cannot leak? Which pillar is riskiest and why?

7. **Cost.** Estimate monthly volume for each pillar. If you came in 40% over
   budget, list your cuts in order and name what debugging power each costs.

**Follow-ups:**

- p99 rises from 400ms to 900ms over two weeks with no deploy and no error-rate
  change. Which pillar do you reach for, and what do you look for?
- The tracing backend goes down. What must keep working, and what did you have
  to build to guarantee that?
- A dependency starts returning 200 with an error in the body. Which of your
  signals catches it? If none do, what do you add?

---

## 12. Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Averaging percentiles across instances** | Quantiles are not additive; `avg(p99)` can be off by orders of magnitude and usually in the alarming direction | Aggregate histogram buckets, then compute the quantile: `histogram_quantile(0.99, sum(rate(..._bucket[5m])) by (le))` |
| **Summaries when you need fleet-wide quantiles** | Client-side quantiles cannot be merged, and the raw observations are already discarded | Histograms — bucket counts sum across instances |
| **`user_id` (or any unbounded value) as a metric label** | Series count is the *product* of label cardinalities; one unbounded label takes the backend down | Bounded labels only. Unbounded dimensions go in traces and logs, which are built for them |
| **One latency histogram for successes and failures** | During an outage, fast failures make p99 *improve* while users see only errors | Label duration by status class; alert on them separately |
| **Alerting on causes** | CPU, memory, and pod restarts fire constantly without user impact, and train the team to ignore alerts | Page on symptoms; keep causes on dashboards and in runbooks |
| **Fixed-threshold alerts** | "Error rate > 1%" is either too twitchy at low traffic or too slow at high traffic | Multi-window burn-rate alerts tied to the SLO |
| **Single-window burn-rate alerts** | One window is either slow to detect acute failures or noisy on blips, and it keeps firing after recovery | Pair a long window with a short one; use both a fast and a slow burn rate |
| **Unstructured log messages** | Counting by error type needs a regex, and the regex breaks when someone rewords the message | Stable event name plus structured fields |
| **No `trace_id` on log lines** | Correlation degrades to "search the same time window and hope" — millions of lines during an incident | Propagate one trace ID into every log line and span; add exemplars to histograms |
| **Redacting PII at call sites** | One forgotten call site is a compliance incident, and there are hundreds of them | Redact in the log formatter — one place to audit |
| **Inconsistent resource attributes** | `svc="checkout"` in metrics and `service_name="checkout-service"` in logs cannot be joined by any tool | One naming convention (OpenTelemetry semantic conventions) across all three pillars |
| **Tracing on the critical path** | A blocking, unbuffered export turns a monitoring outage into a customer outage | Export asynchronously with a bounded buffer; drop spans before dropping requests |
| **Dropping trace context at async boundaries** | Queues, thread pools, and callbacks lose thread-local context, yielding two disconnected traces | Inject/extract explicitly at every boundary; use span links for batches |
| **Sampling inconsistently across services** | Service A keeps the request, B drops it, and you get traces with holes | Decide once at the edge, propagate the decision, honour it everywhere |
| **Dashboards with 60 panels** | Nobody reads them, and the important signal is buried among the noise | Golden signals in the top row, one screen, no scrolling; delete unread panels |
| **No deploy annotations** | "When did this start?" becomes an investigation instead of a glance | Mark deploys, config changes, and flag flips on every time axis |
| **Paging alerts with no runbook** | The responder starts from zero, half-awake and under time pressure | Runbook link in the alert payload, with mitigation ordered before diagnosis |
| **Cutting cost by shortening hot retention first** | You lose week-over-week comparison, which is how you spot slow regressions | Cut noise first: health-check logs, unused metrics, unqueried series |

---

## 13. Discussion Questions

1. Your dashboard shows `avg(p99_latency)` across 50 instances at 800ms, and the team has spent a day chasing it. One instance is a canary taking 1% of traffic and is genuinely slow. What is the real fleet p99, roughly, and what should the dashboard have shown?

   **Model answer**: The real fleet p99 is close to the p99 of the 49 healthy instances — the canary contributes 1% of requests, so it can influence but not dominate the 99th percentile of the merged distribution. `avg(p99)` weights the canary at 1/50 = 2% of the *metric* regardless of its 1% of *traffic*, and worse, it treats a percentile as an averageable quantity, which it isn't. The dashboard should show `histogram_quantile(0.99, sum(rate(bucket[5m])) by (le))` — bucket counts merged first, quantile computed second. Keeping a per-instance p99 panel *alongside* it is still useful for spotting a single bad host, but it must not be labelled as the fleet number. Worth noting the day was not entirely wasted: there *is* a slow canary worth investigating. The error was in the magnitude and in believing it affected all users.

2. A developer wants `user_id` as a label on `http_requests_total` so support can answer "how many requests did this customer make?". You have 2M users, and the metric already has 400,000 series. Walk through your response.

   **Model answer**: Do the arithmetic out loud: 400,000 × 2,000,000 = 8×10^11 series, at roughly 2KB each, which is far past what any TSDB survives — this doesn't degrade, it takes metrics down for everyone. But the request behind it is legitimate, so don't just refuse. The right home for per-user data is the pillar built for high cardinality: log a structured event per request with `user_id`, and query it there — which also answers richer questions ("which endpoints, what latency, which errors") that a counter never could. If they need it aggregated and fast, a nightly rollup into a database table gives per-user counts without touching the metrics system. The general principle: metrics are for bounded dimensions you aggregate across; logs and traces are for unbounded dimensions you filter by. This is the actual division of labour between the pillars, not an arbitrary limit.

3. Your team gets 15 pages per on-call shift. Most resolve themselves within minutes. What is happening, and how do you fix it without going blind?

   **Model answer**: This is alert fatigue, and it is a reliability problem rather than an annoyance — at 15 pages a shift, responders start acknowledging without reading, so the one real page gets missed. Self-resolving alerts diagnose the cause: thresholds are too tight or windows too short, so normal variance trips them. The fix, in order: (1) Audit every alert against "if this fires and nobody acts, does a user notice?" — everything failing that becomes a ticket or a dashboard panel. (2) Replace fixed thresholds with multi-window burn-rate alerts, which by construction only fire when the SLO is genuinely threatened. (3) Pair long windows with short ones so alerts clear on recovery instead of ringing for an hour afterwards. (4) Any alert with a known manual fix gets automated, then deleted. Crucially, this doesn't reduce coverage: SLO-based alerting still catches everything users experience. What disappears is the alerts about *causes* that had no user impact.

4. During an incident an engineer opens the log search first and spends 20 minutes scrolling. What order should they have used, and why does starting with logs cost time?

   **Model answer**: Metrics → traces → logs. Metrics tell you *whether* something is wrong, how bad, when it started, and which dimensions it's confined to — cheap, pre-aggregated queries that narrow the search space enormously (one endpoint, one region). Traces then localize it to a specific hop within a request. Only then do logs explain *why*, and by that point you have a `trace_id` to filter on, which turns millions of lines into a handful. Starting with logs means searching without knowing which haystack: no time bound beyond "recently", no service narrowed down, no identifier to filter by. It also biases toward whatever error happens to be loudest in the logs, which is frequently a pre-existing warning unrelated to this incident. The exception worth acknowledging: if you already know the failing request — a customer handed you a trace ID or an order number — you can skip straight to logs, because the narrowing is already done.

5. You are 40% over your observability budget. Rank your cuts, and name the one cut you would refuse to make even under pressure.

   **Model answer**: Cut in order of debugging-power-lost-per-dollar-saved. First, pure noise: health-check, readiness-probe, and static-asset logs, often 30-60% of log volume for zero information. Second, retention tiering: 7 days hot, 30 warm, a year cold in object storage — most of the cost is in indexing, and week-old logs are rarely queried interactively. Third, delete metrics and dashboards nobody queries; most backends can report unqueried series. Fourth, move high-cardinality metrics to logs or traces, which is both cheaper and a better fit. Fifth, sample successful request logs at 1-10% while keeping 100% of errors. These five usually clear 40% without meaningfully hurting an investigation. The cut to refuse: SLI metrics backing the SLOs, and error logs and failed traces. Errors are rare by volume — cutting them saves almost nothing — and they are the entire reason the system exists. I'd also refuse to drop `trace_id` from log lines, which is nearly free and is what makes correlation possible at all. The asymmetry is the argument: over-instrumenting wastes money linearly and visibly, while under-instrumenting costs one long outage discovered exactly when you can least afford it.

---

## 14. Key References

### Books

| Resource | Focus |
|----------|-------|
| *Site Reliability Engineering* (Google), Ch. 6 "Monitoring Distributed Systems" | The four golden signals; symptom-based alerting |
| *The Site Reliability Workbook* (Google), Ch. 5 "Alerting on SLOs" | Multi-window multi-burn-rate alerting — the source of Section 6.2 |
| *Observability Engineering* (Majors, Fong-Jones, Miranda) | The high-cardinality wide-event argument, and the critique of the three-pillar model |
| *Systems Performance* (Brendan Gregg) | The USE method; resource-level analysis |
| *Distributed Systems Observability* (Cindy Sridharan) | Concise overview of the three pillars and their interaction |

### Papers and Specifications

| Resource | Focus |
|----------|-------|
| [Dapper (Google, 2010)](https://research.google/pubs/pub36356/) | The foundational distributed tracing paper — Section 9 |
| [W3C Trace Context](https://www.w3.org/TR/trace-context/) | The `traceparent`/`tracestate` propagation standard |
| [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/) | Vendor-neutral API, SDK, and OTLP wire format |
| [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) | Standard attribute names — the fix for inconsistent resource attributes |

### Documentation

| Resource | Focus |
|----------|-------|
| [Prometheus: Metric Types](https://prometheus.io/docs/concepts/metric_types/) | Counter, gauge, histogram, summary semantics |
| [Prometheus: Histograms and Summaries](https://prometheus.io/docs/practices/histograms/) | Why summaries cannot be aggregated |
| [Prometheus: Instrumentation Best Practices](https://prometheus.io/docs/practices/instrumentation/) | Naming, labels, cardinality guidance |
| [Grafana Tempo: Tail Sampling](https://grafana.com/docs/tempo/latest/) | Tail-based sampling architecture and trade-offs |
| [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/) | Pipeline architecture, processors, sampling policies |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 06: Microservices](../06-microservices/README.md) | Introduces the three pillars; this module is the depth behind that section |
| [Module 07: Reliability](../07-reliability/README.md) | Defines SLIs, SLOs, and error budgets — Section 6 turns them into alerts |
| [Module 13: Security](../13-security/README.md) | Audit logging, PII handling, and why redaction belongs at the formatter |
| [Module 14: API Design](../14-api-design/README.md) | Error taxonomies and `request_id` propagation feed the log pipeline |
| [Module 19: Production AI](../19-production-ai-system/README.md) | Applies all of this to LLM systems, plus token cost and quality monitoring |

---

## Summary

```
┌─────────────────────────────────────────────────────────────┐
│                  Observability Principles                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Monitoring answers known questions; observability       │
│     answers new ones without a deploy                       │
│  2. Metrics detect, traces localize, logs explain —          │
│     in that order                                           │
│  3. Aggregate distributions, never percentiles               │
│  4. Cardinality is the product of label values, and it       │
│     is what you pay for                                     │
│  5. Unbounded dimensions belong in traces and logs           │
│  6. One trace_id in everything, or correlation is guesswork  │
│  7. Page on symptoms and burn rates, not causes and         │
│     fixed thresholds                                        │
│  8. Observability must never sit on the critical path        │
│  9. Every page needs a runbook; mitigate before diagnose     │
│ 10. Cut noise before coverage — under-instrumenting costs    │
│     one outage, discovered at the worst moment              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 14: API Design](../14-api-design/README.md)

**Next:** [Module 16: LLM Inference Serving Architecture](../16-llm-inference-serving/README.md)

---

*Module 15 of 19 in the System Design Playground*
