# Module 24: Design Case — Ticket Booking and Reservations

> **When a million people want the same 70,000 seats.** Most systems fail
> under load gradually. Ticketing is harder: demand arrives at one announced
> second, every buyer wants the *same* rows, and selling one seat twice is
> unacceptable. This design case is about contention: who gets the seat,
> and how to keep the system up while everyone asks at once.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 23 | Design Case — Search Autocomplete and Proximity Search | [../23-case-search-proximity/](../23-case-search-proximity/) |
| **Module 24** | **Design Case — Ticket Booking and Reservations** | **(current)** |
| Module 25 | Design Case — Web Crawler and Notification System | [../25-case-crawler-notifications/](../25-case-crawler-notifications/) |

Like Module 23, this design case extends Modules 09-12 and was added after
them. It assumes Modules 01-05, and especially
[transaction isolation levels](../02-databases-storage/README.md#transaction-isolation-levels)
in Module 02, so it can be studied straight after Module 12.

---

## Learning Objectives

- Explain why check-then-write sells the same seat twice, and prevent it
  with a conditional update, a lock, or a constraint
- Model a hold with an expiry that needs no background job for correctness
- Design a virtual waiting room that turns an unbounded burst into a chosen
  admission rate
- Serve a live seat map to millions of viewers without touching the
  booking database
- Reconcile payment with expiring holds so that no one pays for a seat they
  didn't get
- Adapt the design to general admission and to hotel room-night inventory

---

## Table of Contents

1. [Requirements and Estimation](#requirements-and-estimation)
2. [The Booking Flow and Seat States](#the-booking-flow-and-seat-states)
3. [Preventing Double Booking](#preventing-double-booking)
4. [The Flash Crowd: A Virtual Waiting Room](#the-flash-crowd-a-virtual-waiting-room)
5. [The Seat Map: Reads at Scale](#the-seat-map-reads-at-scale)
6. [Payment Meets an Expiring Hold](#payment-meets-an-expiring-hold)
7. [Bots and Fairness](#bots-and-fairness)
8. [Variations: General Admission and Hotels](#variations-general-admission-and-hotels)
9. [Case Study: A Record Presale](#case-study-a-record-presale)
10. [What Each Level Is Expected to Cover](#what-each-level-is-expected-to-cover)
11. [Practice Exercise](#practice-exercise)
12. [Common Mistakes](#common-mistakes)
13. [Discussion Questions](#discussion-questions)
14. [Key References](#key-references)

---

## Requirements and Estimation

**Functional**
- Browse events; view a seat map with live availability
- Select specific seats (reserved seating) or a quantity (general admission)
- Hold the selection for a fixed time (10 minutes) while the buyer pays
- Confirm on payment; release on expiry or abandonment
- Enforce a per-buyer ticket limit

**Non-functional**
- **Never sell a seat twice.** This is the one correctness requirement that
  cannot bend; everything else can degrade.
- Survive an on-sale spike without falling over, and degrade *fairly*
- Seat map can be a few seconds stale; the booking decision cannot

**Estimation for a stadium on-sale**

| Quantity | Value | Reasoning |
|----------|-------|-----------|
| Seats | 70,000 | One stadium show |
| People arriving at on-sale | ~2,000,000 | Within the first few minutes |
| Orders needed to sell out | ~28,000 | 2.5 tickets per order |
| Seat-map polling if everyone is let in | ~400,000 req/s | 2M viewers refreshing every 5 s |
| Booking writes the database must accept | **whatever you admit** | The waiting room sets this, not the crowd |

The last row is the key to the whole design. A naive design treats demand as
the load. In a good design, demand waits outside, and the booking tier sees a
rate it chose.

---

## The Booking Flow and Seat States

```
  browse ──▶ select seats ──▶ HOLD (10 min) ──▶ pay ──▶ CONFIRM
                                  │                        │
                                  └── expiry / abandon ────┴──▶ released
```

Each seat is a row with a small state machine:

```
             hold (conditional)          confirm (hold still valid)
  AVAILABLE ───────────────────▶ HELD ───────────────────────────▶ SOLD
      ▲                           │
      └───── held_until passes ───┘   (no job needed: see below)
```

```sql
CREATE TABLE seats (
  event_id    bigint,
  seat_id     text,          -- 'SEC104-ROW12-SEAT7'
  status      text NOT NULL, -- 'available' | 'held' | 'sold'
  hold_id     uuid,          -- which checkout holds it
  held_until  timestamptz,
  order_id    uuid,
  PRIMARY KEY (event_id, seat_id)
);
```

A 70,000-row table for one event fits comfortably on one database primary.
**The scaling problem here is contention on a few hot rows, not data volume.**

---

## Preventing Double Booking

The tempting implementation reads, decides, then writes:

```
  SELECT status FROM seats WHERE event_id = ? AND seat_id = 'A1';   -- 'available'
  -- application: "it's free, take it"
  UPDATE seats SET status = 'held', hold_id = ? WHERE ... ;
```

Two buyers who both run the `SELECT` before either runs the `UPDATE` both see
`available`, and both believe they hold the seat. Under PostgreSQL's default
Read Committed isolation nothing stops this: it's the lost-update anomaly from
[Module 02](../02-databases-storage/README.md#the-anomalies). At an on-sale,
thousands of buyers aim at the same best seats within milliseconds, so this
race is the common case, not a rare one.

The fix is to make the *decision* part of the write. A **conditional update**
only succeeds if the seat is still free, and reports how many rows it changed:

```sql
UPDATE seats
   SET status = 'held', hold_id = :hold, held_until = now() + interval '10 minutes'
 WHERE event_id = :event
   AND seat_id = ANY(:seats)
   AND (status = 'available' OR (status = 'held' AND held_until < now()));
-- rows updated == number of seats requested → success, COMMIT
-- fewer → someone beat us to at least one seat; ROLLBACK and say so
```

The simulation below forces the worst interleaving (both buyers read before
either writes) and compares the two approaches:

```python
"""Two buyers, one seat: check-then-write vs a conditional update."""

import threading


class SeatTable:
    """Stands in for a database table. Each method is one SQL statement,
    and a single statement is atomic: `_lock` plays the row lock."""

    def __init__(self, seats):
        self.rows = {s: {"status": "available", "holder": None, "held_until": 0} for s in seats}
        self._lock = threading.Lock()

    def select_status(self, seat):                      # SELECT status FROM seats WHERE ...
        with self._lock:
            return self.rows[seat]["status"]

    def update_unconditional(self, seat, holder, until):  # UPDATE seats SET ... WHERE seat = ?
        with self._lock:
            self.rows[seat].update(status="held", holder=holder, held_until=until)
            return 1

    def update_if_free(self, seat, holder, until, now):
        # UPDATE seats SET status='held', holder=?, held_until=?
        #  WHERE seat = ? AND (status = 'available'
        #                      OR (status = 'held' AND held_until < now))
        with self._lock:
            row = self.rows[seat]
            free = row["status"] == "available" or (row["status"] == "held" and row["held_until"] < now)
            if not free:
                return 0                                 # 0 rows updated: someone else has it
            row.update(status="held", holder=holder, held_until=until)
            return 1


def race(strategy: str) -> list[str]:
    table = SeatTable(["A1"])
    both_have_read = threading.Barrier(2)               # force the worst-case interleaving
    winners = []

    def buyer(name):
        if strategy == "check-then-write":
            status = table.select_status("A1")
            both_have_read.wait()                       # the other buyer reads 'available' too
            if status == "available":
                table.update_unconditional("A1", name, until=600)
                winners.append(name)
        else:
            both_have_read.wait()
            if table.update_if_free("A1", name, until=600, now=0) == 1:
                winners.append(name)

    threads = [threading.Thread(target=buyer, args=(n,)) for n in ("alice", "bob")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return winners


print(f"check-then-write:   seat A1 sold to {len(race('check-then-write'))} buyers")
print(f"conditional update: seat A1 sold to {len(race('conditional update'))} buyer")

# Expiry needs no background job: an expired hold is simply 'free' to the WHERE clause.
table = SeatTable(["B7"])
table.update_if_free("B7", "carol", until=600, now=0)    # Carol holds B7 for 10 minutes
print("dave at t=300:", table.update_if_free("B7", "dave", until=900, now=300), "row updated")
print("dave at t=601:", table.update_if_free("B7", "dave", until=1201, now=601), "row updated")
```

```
check-then-write:   seat A1 sold to 2 buyers
conditional update: seat A1 sold to 1 buyer
dave at t=300: 0 row updated
dave at t=601: 1 row updated
```

**Expiry is a condition, not a job.** Holds don't need to be released on time
for correctness. An expired hold is simply treated as free by the `WHERE`
clause of the next buyer's update. A periodic sweeper that resets expired
holds to `available` is still worth running, so the seat map looks right, but
if it falls behind nobody is blocked and nothing is sold twice. Compare
[Module 12](../12-case-payment-ecommerce/README.md), where a Redis TTL that
silently deletes a reservation key is the trap: here the expiry lives in the
same row as the seat it guards.

### The Options Compared

| Approach | How | Strength | Weakness |
|----------|-----|----------|----------|
| **Conditional update** | `UPDATE ... WHERE status = 'available'`, check row count | One statement, no lock held across a round trip, works at any isolation level | Multi-seat holds need all-or-nothing handling (one transaction, compare counts) |
| **Pessimistic lock** | `SELECT ... FOR UPDATE`, decide, update | Easy to reason about; allows complex decision logic | Lock held for a round trip; under a stampede, buyers queue on the hot rows |
| **Distributed lock per seat** | Redis `SET seat:A1 <hold> NX PX 600000` | Absorbs contention away from the database | Two systems of record; the DB still needs a constraint as the final arbiter |
| **Unique constraint** | `UNIQUE (event_id, seat_id)` on a `tickets` table; insert to claim | The database guarantees it regardless of app bugs | Releasing a hold means deleting a row; expiry must be cleaned up |

The conditional update is the default answer. Whatever goes in front of it
(caches, Redis locks, queues) is an optimization; **the database row is where
the decision is made**.

**Lock ordering for multi-seat holds.** With `FOR UPDATE`, a buyer locking
seats A1 then A2 and another locking A2 then A1 can deadlock. Lock (or update)
seats in a canonical order, such as sorted by `seat_id`. PostgreSQL detects
the deadlock and aborts one transaction, but that is a failed checkout.

---

## The Flash Crowd: A Virtual Waiting Room

Even a perfect booking path collapses if 2 million browsers hit it in the same
second: connection pools fill, the database saturates, latency climbs, clients
retry, and real buyers time out mid-payment. The standard defence is to put
the crowd in a **queue outside the system** and admit people at a rate the
booking tier can handle.

```
                      ┌─────────────────────────────┐
  2M browsers  ─────▶ │  Waiting room (CDN + edge)  │  static page, cheap to serve
                      │  queue position, ETA        │
                      └──────────────┬──────────────┘
                                     │ admit N per minute
                                     │ + signed access token
                                     ▼
                      ┌─────────────────────────────┐
                      │  Gateway: verify token      │──▶ reject anyone without one
                      └──────────────┬──────────────┘
                                     ▼
                      ┌─────────────────────────────┐
                      │  Booking service + database │  sees only admitted users
                      └─────────────────────────────┘
```

How it works:

- **Joining.** The on-sale URL routes to a lightweight, edge-cached waiting
  page. Each visitor gets a queue entry. People who arrive *before* the sale
  opens are often placed in random order rather than by arrival time, so
  refreshing at exactly 10:00:00.000 (or running a bot that does) earns no
  advantage.
- **Admitting.** A controller admits users from the front of the queue at a
  fixed rate: the booking tier's measured capacity, minus headroom. Admitted
  users receive a short-lived signed token.
- **Enforcing.** Every booking-tier request must carry a valid token, checked
  at the edge or gateway with no database lookup. Without enforcement, anyone
  can skip the queue by calling the API directly.
- **Informing.** Positions and ETAs go out through polling or server-sent
  events. When inventory runs out, broadcast *sold out* to the whole queue at
  once. Most of the queue will never get in, and an hour of false hope is
  worse than an honest answer.

```python
"""Waiting-room admission tokens: signed, short-lived, checked at the edge."""

import base64
import hashlib
import hmac
import json

SECRET = b"rotate-me"           # shared by the waiting room and the edge/gateway


def issue(user_id: str, event_id: str, now: int, ttl_s: int = 900) -> str:
    claims = json.dumps({"u": user_id, "e": event_id, "exp": now + ttl_s}, separators=(",", ":")).encode()
    sig = hmac.new(SECRET, claims, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(claims).decode() + "." + base64.urlsafe_b64encode(sig).decode()


def verify(token: str, event_id: str, now: int) -> str | None:
    """Stateless check: no database or queue lookup on the hot path."""
    try:
        body, sig = (base64.urlsafe_b64decode(p) for p in token.split("."))
    except ValueError:
        return None
    if not hmac.compare_digest(sig, hmac.new(SECRET, body, hashlib.sha256).digest()):
        return None                                     # forged or tampered
    claims = json.loads(body)
    if claims["e"] != event_id or claims["exp"] < now:
        return None                                     # wrong event, or expired
    return claims["u"]


token = issue("user-42", "tour-2026-lon-1", now=1_000)
print(verify(token, "tour-2026-lon-1", now=1_100))      # user-42
print(verify(token, "tour-2026-lon-2", now=1_100))      # None: other event
print(verify(token, "tour-2026-lon-1", now=2_000))      # None: expired
forged = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
print(verify(forged, "tour-2026-lon-1", now=1_100))     # None: bad signature

# The admission rate is a choice: what the booking tier can absorb.
in_line, seats, tickets_per_order = 2_000_000, 70_000, 2.5
admit_per_min, completion_rate = 3_000, 0.6
orders = seats / tickets_per_order
minutes = orders / (admit_per_min * completion_rate)
admitted = minutes * admit_per_min
print(f"sold out after ~{minutes:.0f} min; {in_line - admitted:,.0f} people never get in")
```

```
user-42
None
None
None
sold out after ~16 min; 1,953,333 people never get in
```

The last line is the honest arithmetic of a stadium on-sale: **demand exceeds
supply by 25-30×, so the system's job is to say no quickly and fairly**, not to
let everyone try. Off-the-shelf waiting rooms exist (Cloudflare Waiting Room,
the Virtual Waiting Room on AWS solution); the design questions are the same
whether you build or buy.

---

## The Seat Map: Reads at Scale

The map is the most-requested page and the least critical. Never serve it from
the booking primary:

- **Snapshot availability per section** every 1-2 seconds from a replica or
  from the change stream, and serve the snapshot from a cache or CDN. A
  section-level bitmap of 2,000 seats is 250 bytes.
- **Let the map be stale.** A seat shown available may be gone; the
  conditional update catches that, and the UI says "just taken, pick
  another". **The read path is allowed to be wrong; the write path is not.**
- **Push deltas, optionally.** Server-sent events with "seats A1-A4 held"
  reduce polling, but a fan-out of every change to 100,000 viewers can cost
  more than the polling it replaces. Batch deltas per second.
- **Recommend, don't make people hunt.** "Best available 2 seats in section
  104" assigned by the server spreads demand across rows. A free-for-all map
  makes everyone click the same front-row seats.

---

## Payment Meets an Expiring Hold

Payment happens while the hold is ticking, and the two can cross:

```
  t=0:00   hold A1 (until 0:10)
  t=0:09   buyer submits card; payment provider is slow
  t=0:10   hold expires
  t=0:10   another buyer holds A1   ← legitimate: the hold had expired
  t=0:11   first buyer's payment succeeds   ← charged for a seat that is gone
```

Make **confirmation conditional on the hold**, and only capture money once it
succeeds:

```
  1. AUTHORIZE the card (reserves funds, charges nothing)
  2. UPDATE seats SET status = 'sold', order_id = ?
       WHERE hold_id = :hold AND status = 'held' AND held_until > now()
  3a. rows == seats in the order  →  CAPTURE the authorization
  3b. fewer                       →  VOID the authorization; "your hold expired"
```

Authorize-then-capture turns "refund a charge" into "release an
authorization", which is cleaner for the buyer and the books. Give the hold a
grace period that covers a slow provider (extend `held_until` once when payment
starts), and use idempotency keys on every provider call, exactly as in
[Module 12](../12-case-payment-ecommerce/README.md).

---

## Bots and Fairness

Bots turn a capacity problem into an adversarial one: they arrive first, retry
fastest, and buy to resell.

| Defence | Where | What it stops |
|---------|-------|---------------|
| Pre-registration / verified fan codes | Before the sale | Most bot accounts; also forecasts demand |
| Randomized pre-sale queue order | Waiting room | The refresh-at-the-exact-second advantage |
| Challenge on queue entry | Edge | Unsophisticated automation |
| Per-account and per-card ticket limits | **Database**, in the same transaction as the hold | Bulk buying, including from parallel sessions |
| Rate limits per account, IP and device | Gateway ([Module 04](../04-load-balancing/README.md#rate-limiting)) | Hammering the hold endpoint |

Enforce the purchase limit where the seats are claimed, not in the UI. "Max 4
tickets" checked in a browser session is bypassed by opening four sessions.

---

## Variations: General Admission and Hotels

**General admission** has no seat identity, only a count, so the conditional
update becomes a decrement:

```sql
UPDATE event_inventory
   SET remaining = remaining - :qty
 WHERE event_id = :event AND remaining >= :qty;      -- 0 rows → sold out
```

That single row is now the hottest row in the system. At extreme rates,
**split the counter**: pre-divide the inventory into, say, 16 buckets of 4,375
tickets and pick a bucket at random per request, moving on to another when
one empties. Contention falls 16×; the cost is slightly more complex
sold-out detection.

**Hotel reservations** are counts per room type *per night*, and a stay spans
several nights that must all succeed together:

```sql
-- One transaction: 3-night stay, check-in June 10
UPDATE room_inventory
   SET reserved = reserved + 1
 WHERE hotel_id = :h AND room_type = 'king'
   AND night >= '2027-06-10' AND night < '2027-06-13'
   AND reserved < total_rooms * 1.05;                 -- 5% deliberate overbooking
-- rows updated must be 3; otherwise ROLLBACK
```

Hotels **overbook on purpose** because a predictable share of bookings never
arrive. That makes the limit a business setting, not a hard capacity, but it
must still be enforced atomically. Hotel traffic is also far smoother than a
concert on-sale, so a waiting room is rarely needed; the hard parts move to
channel managers (the same room sold on many sites) and cancellation policies.

---

## Case Study: A Record Presale

In November 2022, the Verified Fan presale for Taylor Swift's Eras Tour
overwhelmed Ticketmaster. By the company's own account, more than 3.5 million
people had pre-registered (its largest registration ever), the site saw **3.5
billion total system requests, four times its previous peak**, and it blamed
much of the excess on bot attacks and on fans without invite codes. More than
2 million tickets still sold that day, the most for any artist in a single day,
but queues stalled, many buyers were kicked out mid-checkout, and the general
public sale was cancelled.

The lessons map directly onto this module:

- **Admission control has to be enforced.** Pre-registration was meant to
  limit who could buy. Traffic from people without codes still reached the
  system, so the gate was in the wrong place or not strict enough.
- **Plan for adversarial load, not just organic load.** The 4× peak was not
  4× more fans. Capacity plans built from registration numbers missed bots
  and retries.
- **Failing mid-checkout is the worst failure.** A buyer turned away at the
  queue is disappointed; a buyer who held seats, entered card details, and then
  lost them is furious. Protect the admitted users' path first, using
  [load shedding](../07-reliability/README.md#overload-backpressure-load-shedding-and-bulkheads)
  at the door, not inside the checkout.

---

## What Each Level Is Expected to Cover

| Level | A strong answer to "design a ticket booking system" |
|-------|------------------------------------------------------|
| **Mid-level** | Clear entities and API; recognizes double booking and fixes it with a transaction or lock; holds with expiry |
| **Senior** | Conditional update with row-count check; expiry as a condition rather than a job; waiting room with enforced tokens; seat map off the primary; payment vs hold race |
| **Staff** | Starts from "the admission rate is a design choice"; sizes the queue and sold-out broadcast; bot economics and where each defence sits; failure modes of the waiting room itself; what changes for GA or hotels |

The [general level rubric](../01-fundamentals/README.md#what-interviewers-expect-by-level)
is in Module 01.

---

## Practice Exercise

**30-minute design**: Design a booking system for a chain of 500 cinemas.

- 4,000 screens; each showing has 80-400 assigned seats
- Normal load is modest, but blockbuster premieres sell out across the
  country within minutes of opening sales
- Seats are held for 7 minutes; buyers can pick specific seats
- Loyalty members get a 30-minute early-access window

**Key decisions**:
1. Where does contention live: per showing, per cinema, or nationally? Do you
   need one waiting room or many?
2. How do you enforce early access so that non-members can't call the API
   directly during the member window?
3. Two friends try to book adjacent seats at the same moment for a group of
   6, overlapping on 2 seats. What does each one see?
4. A cinema's network drops during a premiere. What happens to holds and
   in-flight payments at that location?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Check availability, then update** | Two buyers both read "available" between the check and the write; the seat is sold twice | One conditional `UPDATE ... WHERE status = 'available'`, and check the row count |
| **Releasing holds only with a background job** | If the job lags or dies, seats stay locked, or worse, are released late after a sale | Store `held_until` in the row and treat expired holds as free in the `WHERE` clause |
| **A Redis lock as the only guard** | Lock expiry, failover, or a bug lets two holders through, and nothing downstream catches it | Use Redis to absorb contention if needed, but let the database row decide |
| **Letting the whole crowd reach the booking tier** | Overload makes *everyone* fail, including people mid-payment | A virtual waiting room that admits at the booking tier's capacity |
| **A waiting room without token enforcement** | Bots and savvy users call the booking API directly and skip the queue | Signed, short-lived, per-event tokens verified at the gateway on every booking request |
| **Serving the seat map from the primary** | Hundreds of thousands of reads per second compete with the writes that matter | Cached per-section snapshots refreshed every second or two |
| **Charging before confirming the seat** | A hold that expires during payment leaves a charge with no ticket | Authorize, confirm conditionally on the hold, then capture or void |
| **Ticket limits enforced in the UI** | Parallel sessions bypass a per-session check | Enforce per-account limits in the same transaction as the hold |
| **Locking multiple seats in arbitrary order** | Two overlapping multi-seat holds deadlock | Lock or update in a canonical order (sorted seat IDs) |
| **Letting the queue wait after sell-out** | Two million people wait for a sale that ended | Broadcast "sold out" to everyone queued the moment inventory is gone |

---

## Discussion Questions

1. Your conditional-update design is correct, but during an on-sale the database shows thousands of transactions waiting on locks for the same 200 front-row seats, and p99 hold latency is 8 seconds. What is happening, and what would you change?

   **Model answer**: Many buyers target the same few rows. Each conditional update takes a row lock, so buyers aiming at the same seat serialize, and the losers only find out after waiting their turn. Correctness holds; latency doesn't. Fixes, in order: reduce the contention at its source by recommending "best available" seats server-side, which spreads buyers across the section instead of everyone clicking row 1; lower the admission rate so fewer concurrent buyers compete; fail fast with `NOWAIT` or a short `lock_timeout` and return "seat just taken" immediately rather than queueing; and put a cheap pre-filter in front (a Redis `SET NX` per seat) so only one contender per seat reaches the database, while the database update remains the final decision.

2. Why is "the admission rate is a choice" the most important idea in this design?

   **Model answer**: Without a waiting room, the load on the booking tier equals the crowd, which is unknown, unbounded and partly adversarial, so no amount of provisioning is guaranteed to be enough. With a waiting room, load equals the admission rate, a number you set from a load test. The crowd's size then changes only *how long people wait*, not whether the system survives. It also decouples the problems: the waiting room must handle millions of cheap, cacheable requests (a CDN job), while the booking tier handles a few thousand expensive transactional ones (a database job). Each tier can be designed and scaled for the load it actually gets.

3. The waiting room's queue service (Redis) fails over and loses the last few seconds of queue state during an on-sale. What should happen?

   **Model answer**: Plan for it before it happens. Already-admitted users hold signed tokens that are verified statelessly, so they are unaffected; that is a big reason to use self-contained tokens rather than a session lookup. Users waiting in line lose their position. Mitigations: give each queued client a signed queue ticket recording its position and arrival time, so a client can re-present it and be reinserted where it was; or persist queue joins to a durable log so the queue can be rebuilt. Meanwhile the admission controller should pause rather than admit in an unknown order. The failure mode to avoid is the waiting room failing *open*, sending the whole crowd straight at the booking tier.

4. Product wants to allow "hold up to 8 seats, then pick which 4 to buy at checkout". What does that do to the system?

   **Model answer**: It doubles the inventory each buyer locks without increasing sales. During an on-sale, seats held but not bought are invisible to everyone else for up to 10 minutes, so the event looks sold out while half the seats are only held, and the final sell-out drags on as holds expire in waves. If the business insists, cap it: allow overholding only when demand is low (not during a queued on-sale), release unchosen seats the moment checkout starts rather than at hold expiry, and count held seats against the per-account limit. The general principle: a hold is a lock on scarce inventory, and lock duration and lock scope are the two numbers that set throughput under contention.

5. How would you test that the system never sells a seat twice before a real on-sale?

   **Model answer**: Three layers. First, a concurrency test against a real database (not mocks) that fires many parallel holds at a small set of seats and asserts each seat ends with at most one holder; run it at each isolation level you might deploy with. Second, a full on-sale rehearsal with a load generator at several times the expected admitted rate, including bots that bypass the UI and retry aggressively, then reconcile afterwards: count `sold` seats, orders, and captured payments and confirm they agree exactly. Third, inject the dangerous timings on purpose (payment slower than the hold, database failover mid-checkout, queue failover) and verify the invariants still hold. Keep the reconciliation as a production job too: a seat sold twice must page someone, not wait for two people to show up at the same seat.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview Vol. 2 (Ch. 7, Hotel Reservation System) — Alex Xu & Sahn Lam | Book | Room-night inventory, overbooking, concurrency |
| *Designing Data-Intensive Applications*, 2nd ed. (Ch. 8, Transactions) — Kleppmann & Riccomini | Book | Lost updates, write skew, and the fixes used here |
| [PostgreSQL: Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html) | Docs | Row locks, `NOWAIT`, `SKIP LOCKED`, deadlocks |
| [Cloudflare Waiting Room](https://developers.cloudflare.com/waiting-room/) | Docs | A production virtual waiting room, admission settings and queueing methods |
| [Ticketmaster breaks down what happened during Taylor Swift presale](https://www.nbcchicago.com/news/local/ticketmaster-breaks-down-what-happened-during-taylor-swift-presale-snafu/2999756/) | Article | The 2022 presale numbers quoted in the case study |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 02: Databases and Storage](../02-databases-storage/README.md) | Isolation levels and the lost-update and write-skew anomalies this module defends against |
| [Module 04: Load Balancing](../04-load-balancing/README.md) | Rate limiting at the gateway, and why autoscaling alone can't absorb an on-sale |
| [Module 07: Reliability Engineering](../07-reliability/README.md) | Load shedding and backpressure: the principles behind the waiting room |
| [Module 12: Payment System and E-commerce](../12-case-payment-ecommerce/README.md) | Idempotent payments and flash-sale inventory |
| [Module 13: Security](../13-security/README.md) | Signing tokens, and bot defence at the edge |

---

## Navigation

**Previous:** [Module 23: Design Case — Search Autocomplete and Proximity Search](../23-case-search-proximity/README.md)

**Next:** [Module 25: Design Case — Web Crawler and Notification System](../25-case-crawler-notifications/README.md)

---

*Module 24 of 25 in the System Design Playground*
