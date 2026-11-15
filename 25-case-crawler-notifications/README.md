# Module 25: Design Case — Web Crawler and Notification System

> **Systems whose bottleneck is someone else.** A crawler must not overload
> the websites it reads; a notification system must not exceed its providers'
> quotas or its users' patience. Both are *outbound* systems: the hard part is
> not your own capacity, it is being a well-behaved client of everyone else's.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 24 | Design Case — Ticket Booking and Reservations | [../24-case-ticket-booking/](../24-case-ticket-booking/) |
| **Module 25** | **Design Case — Web Crawler and Notification System** | **(current)** |
| — | Course Home | [../README.md](../README.md) |

Like Modules 23-24, this design case extends Modules 09-12 and was added
after them. It assumes Modules 01-05; the
[Bloom filter](../02-databases-storage/README.md#storage-engines-b-tree-vs-lsm-tree)
and [rate limiting](../04-load-balancing/README.md#rate-limiting) sections are
used directly.

---

## Learning Objectives

- Design a URL frontier that enforces per-host politeness and crawl priority
- Size and choose a "seen URL" structure for billions of URLs
- Detect exact and near-duplicate pages with hashes and SimHash
- Recognize crawler traps and budget a crawl per host
- Design a multi-channel notification system with priority lanes, dedupe,
  user preferences and frequency caps
- Isolate third-party providers so one outage or quota does not stall the rest

---

## Table of Contents

1. [Part 1: Web Crawler](#part-1-web-crawler)
2. [Part 2: Notification System](#part-2-notification-system)
3. [Design Comparison](#design-comparison)
4. [What Each Level Is Expected to Cover](#what-each-level-is-expected-to-cover)
5. [Practice Exercise](#practice-exercise)
6. [Common Mistakes](#common-mistakes)
7. [Discussion Questions](#discussion-questions)
8. [Key References](#key-references)

---

## Part 1: Web Crawler

### Requirements

- **Functional**: starting from seed URLs, fetch pages, extract links, and
  keep going; store page content for an indexer downstream; revisit pages
  so the copy stays fresh
- **Scale**: 1 billion pages per month
- **Politeness**: obey `robots.txt`; never hit one website hard enough to hurt it
- **Robustness**: survive malformed HTML, slow and hostile servers, and
  infinite link spaces
- **Out of scope**: ranking and indexing (see [Module 23](../23-case-search-proximity/README.md#part-2-full-text-search-and-the-inverted-index))

### Capacity Estimation

```
  Pages:      1B / month ÷ 2.6M s/month      ≈ 390 pages/s   (peak ~800)
  Page size:  ~100 KB of HTML (assumption)
  Bandwidth:  390 × 100 KB                   ≈ 39 MB/s       ≈ 310 Mbit/s
  Storage:    1B × 100 KB                    = 100 TB / month (before compression)
  Known URLs: links outnumber pages ~10:1    → ~10 billion URLs to deduplicate
```

None of these numbers is hard for a modern cluster. A crawler is
difficult because of politeness, duplicates and traps, not throughput.

### Architecture

```
  ┌───────────┐     ┌────────────────┐     ┌───────────────┐
  │ Seed URLs │────▶│  URL frontier  │────▶│   Fetchers    │──▶ DNS cache
  └───────────┘     │ priority +     │     │ robots.txt    │
        ▲           │ per-host queue │     │ cache, HTTP   │
        │           └────────────────┘     └───────┬───────┘
        │                                          ▼
  ┌─────┴──────────┐   ┌──────────────┐    ┌───────────────┐
  │  URL filter +  │◀──│ Link extract │◀───│  Content      │──▶ content
  │  seen? (Bloom) │   │ + normalize  │    │  dedupe       │    store
  └────────────────┘   └──────────────┘    └───────────────┘
```

The loop is simple: take a URL, fetch it, extract links, add the new ones.
Every interesting decision is inside one of the boxes.

### The URL Frontier: What Next, and When

The frontier answers two different questions, and the classic Mercator design
(Heydon & Najork, 1999) gives each its own set of queues:

- **Priority (front queues).** Which URLs matter most? Home pages, frequently
  changing pages, and pages with many inbound links go first.
- **Politeness (back queues).** One queue *per host*, and a host is contacted
  only after its delay has passed since the last request. A fetcher works on
  many hosts at once and none of them sees more than one request at a time.

```python
"""A polite URL frontier: priority decides WHAT to crawl, per-host timers decide WHEN."""

import heapq
from collections import deque
from urllib.parse import urlsplit


class Frontier:
    def __init__(self, delay_s: float = 1.0):
        self.delay_s = delay_s
        self.per_host = {}           # host -> deque of URLs (one "back queue" per host)
        self.ready = []              # heap of (next_allowed_time, host)

    def add(self, url: str, now: float = 0.0) -> None:
        host = urlsplit(url).hostname
        if host not in self.per_host:
            self.per_host[host] = deque()
            heapq.heappush(self.ready, (now, host))
        self.per_host[host].append(url)

    def next_url(self, now: float):
        """Return a URL whose host may be contacted now, or None."""
        if not self.ready or self.ready[0][0] > now:
            return None
        _, host = heapq.heappop(self.ready)
        url = self.per_host[host].popleft()
        if self.per_host[host]:
            heapq.heappush(self.ready, (now + self.delay_s, host))   # host rests
        else:
            del self.per_host[host]
        return url


f = Frontier(delay_s=1.0)
for u in ["https://big.example/a", "https://big.example/b", "https://big.example/c",
          "https://small.example/x", "https://other.example/y"]:
    f.add(u)

t = 0.0
while f.per_host:
    url = f.next_url(t)
    if url:
        print(f"t={t:.1f}s  fetch {url}")
    else:
        t += 0.5                                   # nothing allowed yet: wait
```

```
t=0.0s  fetch https://big.example/a
t=0.0s  fetch https://other.example/y
t=0.0s  fetch https://small.example/x
t=1.0s  fetch https://big.example/b
t=2.0s  fetch https://big.example/c
```

The other hosts don't wait behind `big.example`; `big.example` gets one request
per second however many of its URLs are queued. One consequence matters for
sizing: at 1 request per second per host, **800 pages per second means at least
800 different hosts in flight at any moment**. A crawl dominated by a few huge
sites runs slowly no matter how many machines you add.

**Distributing the frontier.** Partition URLs by a hash of the *host*, not of
the full URL. Then each host's queue and rate timer live on exactly one
worker, and politeness needs no coordination between workers.

### robots.txt and DNS

- **robots.txt** is fetched once per host and cached. RFC 9309 (2022), which
  standardized the protocol, says a crawler should not use a cached copy for
  more than 24 hours unless the file is unreachable. Honour `Disallow` and,
  where present, `Crawl-delay`. Python's standard library parses it
  (`urllib.robotparser`).
- **DNS** becomes a bottleneck at hundreds of new hosts per second. Use a
  local caching resolver; lookups can take tens to hundreds of
  milliseconds, and a fetcher blocked on DNS is wasted.

### Have We Seen This URL?

The same page has many spellings. Normalize before checking:

```python
"""Different spellings, same page: normalize before the seen-check."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "fbclid", "gclid"}
DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if parts.port and parts.port != DEFAULT_PORTS.get(scheme):
        host = f"{host}:{parts.port}"
    path = parts.path or "/"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING))
    return urlunsplit((scheme, host, path, query, ""))          # fragment dropped


for u in ["HTTPS://Example.com:443/shoes?size=9&color=red#reviews",
          "https://example.com/shoes?color=red&size=9&utm_source=newsletter",
          "https://example.com:8443/shoes"]:
    print(normalize(u))
```

```
https://example.com/shoes?color=red&size=9
https://example.com/shoes?color=red&size=9
https://example.com:8443/shoes
```

The first two URLs collapse to one; the third keeps its non-default port.
The path is deliberately left case-sensitive, because servers treat it that
way. Sorting query parameters is a heuristic: it is safe for most sites, but
a crawler should be able to turn it off per host.

Then the seen-check itself, over ~10 billion URLs:

| Structure | Memory for 10B URLs | Error |
|-----------|---------------------|-------|
| Exact set of 8-byte URL hashes | ~80 GB, plus hash-table overhead | Collisions only (negligible at 64 bits) |
| Bloom filter, 1% false positives | ~12 GB (~9.6 bits/URL) | 1% of *new* URLs wrongly skipped |

A false positive here means "we think we've seen it, so we skip it". For a
crawler, missing 1% of new URLs on this pass is acceptable: important pages
have many inbound links and will be found again. That's why the Bloom filter
from [Module 02](../02-databases-storage/README.md#storage-engines-b-tree-vs-lsm-tree)
is the standard answer. Note the direction of the error: a Bloom filter can
never make you crawl a URL twice.

### Have We Seen This Content?

Different URLs often serve the same page: mirrors, print versions, session IDs
in URLs, syndicated articles. Studies of large crawls have found a large share
of pages are exact or near duplicates.

- **Exact duplicates**: hash the page body (SHA-256) and keep a set of hashes.
- **Near duplicates** (same article, different ads, date or footer): exact
  hashes fail, because one changed byte changes the whole hash. **SimHash**
  (Charikar, 2002) produces fingerprints where similar documents differ in
  only a few bits. Google's crawler used 64-bit SimHash and treated pages
  within 3 bits as near-duplicates (Manku, Jain & Das Sarma, 2007).

```python
"""SimHash: similar documents get fingerprints that differ in only a few bits."""

import hashlib


def simhash(text: str, bits: int = 64) -> int:
    words = text.lower().split()
    shingles = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]   # 3-word shingles
    weights = [0] * bits
    for s in shingles:
        h = int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")
        for i in range(bits):
            weights[i] += 1 if (h >> i) & 1 else -1        # each shingle votes on each bit
    return sum(1 << i for i in range(bits) if weights[i] > 0)


def distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")                           # Hamming distance


import random

rng = random.Random(7)
vocab = [f"w{i}" for i in range(5000)]
page = [rng.choice(vocab) for _ in range(1000)]              # a 1,000-word article

with_ad_footer = page + "subscribe now for unlimited access advertisement".split()
edited = page.copy()
for i in (100, 400, 700):                                    # three words changed
    edited[i] = "changed"
rewritten = page.copy()
for i in range(0, 1000, 10):                                 # every 10th word replaced
    rewritten[i] = rng.choice(vocab)
unrelated = [rng.choice(vocab) for _ in range(1000)]

base = simhash(" ".join(page))
for name, words in [("same + ad footer", with_ad_footer), ("3 words edited", edited),
                    ("10% rewritten", rewritten), ("unrelated page", unrelated)]:
    print(f"{name:<17} differs in {distance(base, simhash(' '.join(words))):>2} of 64 bits")
```

```
same + ad footer  differs in  0 of 64 bits
3 words edited    differs in  0 of 64 bits
10% rewritten     differs in 12 of 64 bits
unrelated page    differs in 30 of 64 bits
```

Each shingle (3-word window) votes on every bit, so small changes to a long
page barely move the result, while unrelated pages differ in about half the
bits. Finding all fingerprints within 3 bits of a new one, among billions,
uses the same paper's trick: split the 64 bits into blocks and index by each
block, since two fingerprints within 3 bits must agree exactly on at least one
of 4 blocks.

### Traps and Budgets

Some sites generate infinite URL spaces, by accident or on purpose:

| Trap | Example | Defence |
|------|---------|---------|
| Calendars | `/calendar?month=2099-12`, `next` forever | Max depth per host; ignore far-future dates |
| Session IDs in URLs | `/page;jsessionid=8F3A...` on every link | Strip known session parameters when normalizing |
| Faceted search | `?color=red&size=9&sort=...` combinations | Per-host page budget; parameter allowlists |
| Endless paths | `/a/b/a/b/a/b/...` from relative-link bugs | Max URL length and repeated-segment detection |
| Slow servers | 1 byte per second (tarpits) | Total-time timeout per fetch, not just connect timeout |

The general defence is a **per-host budget** (pages per crawl cycle, scaled
by the host's importance), so a trap can waste a bounded amount of effort and
no more.

### Freshness: Recrawling

A page fetched once goes stale. Recrawl at a rate matched to how often each
page changes: estimate change frequency from past fetches (did the content
hash change?), recrawl news home pages within minutes and an archived page
monthly. Use conditional requests (`If-Modified-Since`, `ETag`) so unchanged
pages cost a `304 Not Modified` instead of a full download.

---

## Part 2: Notification System

### Requirements

- **Channels**: mobile push (Apple's APNs, Google's FCM), SMS through a
  provider, and email
- **Volume** (assumption): 10M push, 1M SMS and 5M email per day, with
  marketing campaigns that target 50M users at once
- **Kinds**: transactional (one-time passcodes, receipts, password resets),
  social ("Ana liked your photo"), marketing
- **Rules**: respect each user's opt-outs, quiet hours and frequency limits;
  never send a duplicate one-time code; never let a campaign delay a passcode
- **Delivery**: soft real-time; at-least-once with deduplication

### Architecture

```
  ┌──────────────┐    ┌─────────────────────┐
  │ Services     │───▶│ Notification API    │  validate, idempotency key,
  │ (orders,     │    │                     │  render template
  │ auth, social)│    └──────────┬──────────┘
  └──────────────┘               ▼
                      ┌─────────────────────┐
                      │ Preferences + caps  │  opted out? quiet hours?
                      │ (per user)          │  over the daily cap?
                      └──────────┬──────────┘
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
     │ push queues │      │ SMS queues  │      │ email queues│  one set per
     │ hi / lo     │      │ hi / lo     │      │ hi / lo     │  channel AND
     └──────┬──────┘      └──────┬──────┘      └──────┬──────┘  priority
            ▼                    ▼                    ▼
     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
     │ push workers│      │ SMS workers │      │email workers│
     │ ──▶ APNs/FCM│      │ ──▶ provider│      │ ──▶ ESP     │
     └─────────────┘      └─────────────┘      └─────────────┘
         retries with backoff → DLQ;  delivery events → analytics
```

Two separations do most of the work:

- **Per channel.** When the SMS provider has an outage, SMS queues back up and
  push keeps flowing. This is the
  [bulkhead pattern](../07-reliability/README.md#overload-backpressure-load-shedding-and-bulkheads)
  applied to third parties.
- **Per priority.** A 50M-user campaign queued at 10:00 must not put a login
  code at position 50,000,001. Transactional messages get their own queues
  and workers, and are never throttled by marketing.

### Dispatch: Priority, Dedupe, Caps

```python
"""Notification dispatch: priority lanes, dedupe, and a per-user frequency cap."""

import heapq
from collections import defaultdict

PRIORITY = {"transactional": 0, "social": 1, "marketing": 2}   # lower = sent first
DAILY_CAP = {"marketing": 2}                                    # per user, per day


class Dispatcher:
    def __init__(self):
        self.queue = []                      # (priority, seq, notification)
        self.seq = 0
        self.sent_keys = set()               # in production: a KV store with TTL
        self.sent_today = defaultdict(int)   # (user, kind) -> count

    def submit(self, n: dict) -> None:
        heapq.heappush(self.queue, (PRIORITY[n["kind"]], self.seq, n))
        self.seq += 1

    def drain(self, budget: int) -> None:
        """Send up to `budget` messages: what the provider allows this second."""
        while self.queue and budget:
            _, _, n = heapq.heappop(self.queue)
            if n["key"] in self.sent_keys:
                print(f"  skip   {n['key']}: duplicate (producer retried)")
                continue
            cap = DAILY_CAP.get(n["kind"])
            if cap is not None and self.sent_today[(n["user"], n["kind"])] >= cap:
                print(f"  drop   {n['key']}: {n['user']} hit the {n['kind']} cap")
                continue
            self.sent_keys.add(n["key"])
            self.sent_today[(n["user"], n["kind"])] += 1
            budget -= 1
            print(f"  SEND   {n['key']}")


d = Dispatcher()
for i in range(4):                                   # a marketing blast queued first
    d.submit({"key": f"promo-{i}:u1", "user": "u1", "kind": "marketing"})
d.submit({"key": "otp-8812:u1", "user": "u1", "kind": "transactional"})
d.submit({"key": "otp-8812:u1", "user": "u1", "kind": "transactional"})  # retried
d.submit({"key": "like-77:u1", "user": "u1", "kind": "social"})

print("second 1 (provider allows 2/s):")
d.drain(budget=2)
print("second 2:")
d.drain(budget=2)
print("second 3:")
d.drain(budget=2)
```

```
second 1 (provider allows 2/s):
  SEND   otp-8812:u1
  skip   otp-8812:u1: duplicate (producer retried)
  SEND   like-77:u1
second 2:
  SEND   promo-0:u1
  SEND   promo-1:u1
second 3:
  drop   promo-2:u1: u1 hit the marketing cap
  drop   promo-3:u1: u1 hit the marketing cap
```

The passcode was queued after four promotions and went out first; its
retried copy was dropped; the user received two promotions, not four.

### Exactly Once Is Not Available

A worker calls the provider, the provider accepts the message, and the worker
crashes before recording "sent". On restart it sends again. No design closes
that window completely, because the provider call and your database write
cannot share a transaction (the same dual-write problem as
[Module 05](../05-async-systems/README.md#the-dual-write-problem-outbox-and-cdc)).
What you can do:

- **Idempotency key per notification** (`event_id` + user + channel) checked
  before sending, so producer retries and queue redeliveries are dropped
- **Record intent before sending**, then mark the outcome, so the crash window
  is milliseconds rather than a whole batch
- **Pass the key to the provider** where it supports idempotency (some email and
  SMS APIs do), which closes the window on their side
- **Make the message tolerate a repeat**: a duplicate "your order shipped" is
  harmless; a duplicate charge notice is alarming, so phrase it with an ID

### Providers Are Part of the Design

| Concern | What to build |
|---------|---------------|
| **Quotas and throttling** | Token-bucket rate limiter per provider account; spread campaigns over time instead of bursting |
| **Dead tokens** | APNs answers `410 Unregistered`, FCM `UNREGISTERED`: delete the token, or you pay to send to nobody and look like a spammer |
| **Failover** | A second SMS and email provider for transactional traffic, with health-based routing |
| **Email reputation** | SPF, DKIM and DMARC; process bounces and complaints. Since 2024 Gmail and Yahoo require bulk senders to support one-click unsubscribe and keep spam complaints under 0.3% |
| **SMS cost and fraud** | SMS costs real money per message. Attackers trigger passcode SMS to premium-rate numbers they profit from ("SMS pumping"): rate-limit per phone number, prefix and country |
| **Delivery tracking** | "Accepted by provider" is not "delivered", and neither is "seen". Ingest provider callbacks and open events separately |

### User-Facing Rules

- **Preferences** per user, channel and kind ("no marketing email, yes push
  for messages"), checked at send time and cached; changes take effect
  immediately for opt-outs, which can be a legal requirement.
- **Quiet hours** in the *user's* time zone. A worker that defers a
  notification puts it on a scheduled queue, not back on the hot queue.
- **Frequency caps** per kind, as in the code above. Collapse bursts too:
  "Ana and 14 others liked your photo" is one notification, not 15.

---

## Design Comparison

| Aspect | Web crawler | Notification system |
|--------|-------------|---------------------|
| Who limits you | Each website's capacity and robots.txt | Provider quotas, and users' attention |
| Core queue | Frontier: priority × per-host politeness | Per channel × per priority |
| Dedupe | URLs (Bloom filter) and content (hash, SimHash) | Idempotency key per notification |
| Rate limiting | Per host, at the frontier | Per provider account, and per user (caps) |
| Failure isolation | One slow host must not stall a fetcher | One provider outage must not stall other channels |
| Classic trap | Infinite URL spaces | Marketing blast delaying passcodes |

---

## What Each Level Is Expected to Cover

| Level | Web crawler | Notification system |
|-------|-------------|---------------------|
| **Mid-level** | The fetch-parse-enqueue loop; a seen-set; robots.txt | Queue between producers and senders; channels; retries |
| **Senior** | Mercator-style frontier; host-hash partitioning; Bloom filter sizing; content dedupe; traps | Per-channel and per-priority queues; idempotency keys; caps and quiet hours; dead-token cleanup |
| **Staff** | Recrawl scheduling by change rate; near-dup index; what limits throughput (distinct hosts, not machines) | Exactly-once impossibility and the residual window; provider failover; SMS fraud and email reputation as design constraints |

---

## Practice Exercise

**30-minute design**: Design a price-monitoring crawler for an e-commerce
comparison site.

- 5,000 retailer sites, 200 million product pages in total
- Prices must be no more than 6 hours stale for the top 1 million products,
  and no more than 7 days for the rest
- Retailers' sites vary from huge (tolerating 10 requests per second) to tiny
  (1 request every 10 seconds)
- When a tracked price drops, notify users who set an alert, within 15
  minutes, by push or email

**Key decisions**:
1. Compute the fetch rate needed for the top 1M products. Does it fit
   inside the politeness budget of the sites that host them?
2. How does the frontier prioritize a top product on a slow site against an
   ordinary product on a fast one?
3. How do you avoid sending 40,000 alerts in one burst when a popular TV's
   price drops, and what if the price goes back up 10 minutes later?
4. How do you detect that a retailer changed its page layout and your price
   extractor is now returning garbage?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **One global FIFO queue of URLs** | A big site's thousand URLs come out together and hammer one host | Per-host back queues with a delay; priority in separate front queues |
| **Partitioning crawl work by URL hash** | Pages from one host land on many workers, and politeness needs global coordination | Partition by host hash so each host lives on one worker |
| **Checking "seen" before normalizing** | `HTTP://A.com/x#top` and `http://a.com/x` are crawled twice | Normalize first: case, default port, fragment, tracking parameters |
| **An exact in-memory set for 10B URLs** | Tens of GB of RAM with overhead, hard to shard and rebuild | Bloom filter; accept skipping a small share of new URLs |
| **Only exact-hash content dedupe** | Same article with different ads or timestamps looks unique | SimHash fingerprints with a small Hamming threshold |
| **No per-host page budget** | A calendar or faceted-search trap absorbs the whole crawl | Cap pages and depth per host per cycle |
| **One queue for all notification kinds** | A campaign delays passcodes and password resets by hours | Separate queues and workers per priority and per channel |
| **Assuming exactly-once delivery** | Provider accepts, worker crashes, message is sent again | Idempotency keys, intent-then-outcome records, provider-side idempotency where offered |
| **Never removing dead device tokens** | Money and provider reputation wasted on uninstalled apps | Delete tokens on `410` / `UNREGISTERED` responses |
| **Quiet hours in server time** | Users in other time zones are woken at 3am | Store each user's time zone; defer to a scheduled queue |
| **Unlimited passcode SMS** | SMS-pumping fraud runs up large bills | Rate-limit by number, prefix and country; challenge suspicious traffic |

---

## Discussion Questions

1. Your crawler runs on 50 machines and fetches only 120 pages per second, far below the 800 you sized for. CPU and bandwidth are mostly idle. What is the likely cause?

   **Model answer**: Politeness, not hardware. If most queued URLs belong to a few large hosts, each host allows only about one request per second, so throughput is capped by the number of *distinct hosts with ready URLs*, not by machines. Check how many hosts are ready at any moment and how deep the largest per-host queues are. Fixes: broaden the frontier so it holds URLs from many more hosts (prioritize discovering new hosts, and cap per-host queue depth so one site can't fill it); negotiate higher rates where site owners allow it; and confirm DNS isn't the real stall, since slow uncached lookups look exactly like idle machines.

2. A Bloom filter for the seen-set has grown to its designed capacity and the false-positive rate is climbing. What are your options?

   **Model answer**: A Bloom filter can't be resized in place, because items aren't stored, only their bits. Options: build a new, larger filter and send new insertions to it while checking both (a scalable Bloom filter chains filters of growing size this way); or rebuild from the durable URL store, which you need anyway since the filter is a cache of "seen", not the record. Separately, ask whether every URL needs to be remembered forever: partition the filter by time or by host so old or low-value portions can be dropped and rebuilt. The cost of doing nothing is silent: more and more new URLs are skipped, and coverage decays without any error.

3. Marketing wants to send a push notification to all 50M users at 9:00am in their local time. Walk through how the system should execute it.

   **Model answer**: It is a scheduled fan-out, not one burst. Expand the audience in batches from a snapshot of eligible users (respecting opt-outs and caps at expansion and again at send time), group by time zone, and enqueue each group on the low-priority push queue shortly before its local 9:00am. Within each group, a rate limiter paces sends to the provider quota and to downstream capacity, because users who open the app create a second wave of API load. Transactional queues are untouched throughout. Track progress per batch so a failure mid-campaign resumes rather than restarts, and use idempotency keys per user and campaign so a resumed batch doesn't double-send.

4. Users report receiving the same "Your order has shipped" push twice. Logs show the shipping service published the event once. Where can the duplicate come from, and how do you find it?

   **Model answer**: Several places downstream: the queue redelivered the message because a worker processed it but crashed before acknowledging; a worker timed out waiting for APNs or FCM, retried, and both attempts went through; or the user has two registered tokens for the same device (an app reinstall created a new token while the old one is still active). Find it by logging the idempotency key and attempt number on every send: two sends with the same key show a missing or late dedupe check; two different tokens show token hygiene. Fixes follow the cause: check the key before sending and record intent first; dedupe tokens per device ID; delete tokens the provider reports as unregistered.

5. Should the notification system call SMS providers synchronously from the API that services call, or always go through a queue? Is there any exception?

   **Model answer**: Through a queue by default. It decouples services from provider latency and outages, and enables retries, rate limiting and priority, which a synchronous call can't. The exception worth discussing is the one-time passcode: the user is waiting on screen, so it needs a fast path. That is still a queue, but a dedicated high-priority one with its own workers and a failover provider, and the API returns "sent" promptly while the client offers "resend" after a delay. Calling the provider inline would tie login latency to a third party's worst moment.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview Vol. 1 (Ch. 9 Web Crawler, Ch. 10 Notification System) — Alex Xu | Book | Both designs, interview framing |
| "Mercator: A Scalable, Extensible Web Crawler" — Heydon & Najork (1999) | Paper | Frontier with front (priority) and back (politeness) queues |
| "Detecting Near-Duplicates for Web Crawling" — Manku, Jain & Das Sarma (WWW 2007) | Paper | 64-bit SimHash and the 3-bit threshold |
| [RFC 9309: Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309) | Standard | robots.txt semantics and caching |
| [Apple: Handling notification responses from APNs](https://developer.apple.com/documentation/usernotifications/handling-notification-responses-from-apns) | Docs | Status codes including `410 Unregistered` |
| [Firebase Cloud Messaging: error codes](https://firebase.google.com/docs/reference/fcm/rest/v1/ErrorCode) | Docs | `UNREGISTERED` and other send errors |
| [Google: Email sender guidelines](https://support.google.com/a/answer/81126) | Docs | Bulk-sender authentication, unsubscribe and spam-rate rules |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 02: Databases and Storage](../02-databases-storage/README.md) | Bloom filters for the seen-URL set |
| [Module 04: Load Balancing](../04-load-balancing/README.md) | Token buckets for per-host and per-provider rate limits |
| [Module 05: Async Systems](../05-async-systems/README.md) | Queues, DLQs, and why exactly-once delivery is impossible |
| [Module 07: Reliability Engineering](../07-reliability/README.md) | Bulkheads per channel; retries with backoff and jitter |
| [Module 23: Search Autocomplete and Proximity Search](../23-case-search-proximity/README.md) | The indexer that consumes what the crawler fetches |

---

## Navigation

**Previous:** [Module 24: Design Case — Ticket Booking and Reservations](../24-case-ticket-booking/README.md)

**Next:** [Course Home](../README.md)

---

*Module 25 of 25 in the System Design Playground*
