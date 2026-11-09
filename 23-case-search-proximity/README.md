# Module 23: Design Case — Search Autocomplete and Proximity Search

> **Finding things fast.** Two of the most common design questions — "build
> the search box's suggestions" and "find what's near me" — share one idea:
> you cannot afford to scan, so you precompute a structure that turns the
> question into a lookup.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 22 | Production AI System Architecture | [../22-production-ai-system/](../22-production-ai-system/) |
| **Module 23** | **Design Case — Search Autocomplete and Proximity Search** | **(current)** |
| — | Course Home | [../README.md](../README.md) |

This module extends the design cases in Modules 09-12. It sits at the end
of the course only because it was added after the others; it assumes
Modules 01-05 and nothing after them, so it can be studied straight after
Module 12.

---

## Learning Objectives

- Design a typeahead service that answers in well under 100 ms
- Choose between a trie and a precomputed prefix table, and shard either one
- Explain the inverted index behind full-text search, and how it is partitioned
- Explain why a two-column latitude/longitude index cannot serve "nearby" queries
- Use geohashes and quadtrees, including the boundary problem every
  geohash design must handle
- Design a location service for moving objects at hundreds of thousands of
  updates per second

---

## Table of Contents

1. [Part 1: Search Autocomplete](#part-1-search-autocomplete)
2. [Part 2: Full-Text Search and the Inverted Index](#part-2-full-text-search-and-the-inverted-index)
3. [Part 3: Proximity Search](#part-3-proximity-search)
4. [Design Comparison](#design-comparison)
5. [Practice Exercise](#practice-exercise)
6. [Common Mistakes](#common-mistakes)
7. [Discussion Questions](#discussion-questions)
8. [Key References](#key-references)

---

## Part 1: Search Autocomplete

### Requirements

- **Functional**: as the user types, show the top 5-10 completions for the
  current prefix, ranked by popularity; exclude blocked terms
- **Scale**: 10M daily active users, ~10 searches each per day
- **Latency**: suggestions must keep pace with typing — under 100 ms end to
  end, so the server budget is a few tens of milliseconds
- **Freshness**: popularity can lag by hours; *trending* terms should appear
  within minutes

### Capacity Estimation

```
Requests: a request per keystroke would be ~20 per search. Debouncing
          (wait ~100 ms after the last keystroke) cuts that to ~6.

  10M users × 10 searches × 6 requests = 600M requests/day
  600M / 86,400 s                      ≈ 7,000 QPS average
  Peak (×3)                            ≈ 21,000 QPS

Data: suggestions come from a log of past queries, aggregated to
      (query, count). Keep the top ~10M distinct queries.

  Prefixes: every prefix of every kept query, deduplicated. Queries
  share prefixes heavily, so this is far fewer than 10M × avg length.
  Budget ~100 bytes per prefix entry (key + 10 suggestion IDs).
  Even at 100M prefix entries that is ~10 GB — memory-resident on a
  handful of machines.
```

The shape that matters: **read-heavy, latency-critical, and tolerant of
slightly stale data.** That combination says precompute everything offline
and make serving a single lookup.

### The Data Structure: A Trie With Cached Top-K

A trie stores strings by shared prefix. Finding the node for a prefix takes
one step per character — but finding the *most popular completions* under
that node would mean walking its whole subtree on every keystroke. The fix
is to store the answer at every node when the trie is built:

```
                 (root)
                   │
                   s      top-3: system design, system design interview, ...
                   │
                   y      top-3: (same — every query here starts with "sy")
                   │
                   s
              ┌────┴─────┐
              t          a
              │          │
              e          d ── ... "sysadmin"
              │
              m      top-3: system design, system design interview,
           ┌──┴──┐          system of a down
          " "    d ── "systemd"
           │
          ...

  Lookup "sys" = walk 3 nodes, read the cached list. No subtree scan.
```

```python
import heapq


class TrieNode:
    __slots__ = ("children", "top")

    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.top: list[tuple[int, str]] = []   # best (count, query) pairs


class AutocompleteTrie:
    """Each node caches its top-k completions, so a lookup is O(prefix length).

    Built offline from aggregated query counts and served read-only;
    rebuilding beats updating a shared structure under live traffic.
    """

    def __init__(self, k: int = 5):
        self.root = TrieNode()
        self.k = k

    def build(self, query_counts: dict[str, int]) -> None:
        for query, count in query_counts.items():
            node = self.root
            for ch in query:
                node = node.children.setdefault(ch, TrieNode())
                self._offer(node, count, query)

    def _offer(self, node: TrieNode, count: int, query: str) -> None:
        # Keep the k most popular completions; a min-heap evicts the weakest.
        if len(node.top) < self.k:
            heapq.heappush(node.top, (count, query))
        elif count > node.top[0][0]:
            heapq.heapreplace(node.top, (count, query))

    def suggest(self, prefix: str) -> list[str]:
        node = self.root
        for ch in prefix.lower():
            node = node.children.get(ch)
            if node is None:
                return []
        return [q for _, q in sorted(node.top, reverse=True)]


trie = AutocompleteTrie(k=3)
trie.build({
    "system design": 9_000, "system design interview": 7_500,
    "systemd": 4_000, "system of a down": 6_000, "sysadmin": 2_000,
})
print(trie.suggest("sys"))
# ['system design', 'system design interview', 'system of a down']
```

The trade is memory for latency: every node stores *k* entries, so a query
of length 20 appears in up to 20 nodes' lists. That is affordable because
the trie is built once and read millions of times.

### Trie Service or Prefix Table?

In production the trie is often flattened into a key-value table:

| | Trie service | Precomputed prefix table |
|---|---|---|
| Storage | Custom in-memory structure | Any KV store: `prefix → [top-k]` |
| Lookup | Walk the trie | One `GET` |
| Sharding | Must split the tree by subtree | Hash or range-partition keys like any KV data |
| Rebuild | Build new trie, swap atomically | Bulk-load a new table version, flip a pointer |
| When it wins | Fuzzy matching, typo tolerance, walking alternatives | Exact-prefix suggestions at scale — the common case |

Both are built the same way offline; the difference is only how the result
is served.

### Sharding: Prefix Popularity Is Skewed

Splitting by first letter fails the same way range sharding does in
Module 02: far more queries start with "s" than with "x", so one shard runs
hot. Two fixes:

- **Hash the prefix** to choose a shard — even load, and an exact-prefix
  lookup never needs to visit more than one shard.
- **Range-partition with data-driven split points** chosen from the actual
  query distribution ("s" might be split into "sa-sh", "si-sm", "sn-sz").
  Use this if a request must scan adjacent prefixes.

Very short prefixes ("a", "s", "th") are the hottest keys of all, and their
answers barely change. Cache them in the application tier and at the CDN
edge (Module 03), and most of the peak never reaches the shards.

### Freshness: Two Pipelines

```
  ┌─────────────┐   daily/hourly batch    ┌──────────────────┐
  │  Query log  │ ──────────────────────▶ │ Aggregate counts │
  │  (Kafka)    │                         │ with time decay  │
  └──────┬──────┘                         └────────┬─────────┘
         │                                         │ build + swap
         │ streaming                               ▼
         │                                ┌──────────────────┐
         │                                │ Prefix table v42 │──┐
         ▼                                └──────────────────┘  │
  ┌─────────────────┐                                           │ merged
  │ Trending window │  count-min sketch +                       │ at read
  │  (last ~15 min) │  heap of heavy hitters ───────────────────┤ time
  └─────────────────┘                                           ▼
                                                     suggestions to user
```

- **Batch** recomputes popularity from the full log with **time decay** (a
  count from last month weighs less than one from today), then bulk-loads a
  new table version and switches atomically. No live structure is ever
  mutated under traffic.
- **Streaming** catches what batch cannot: a term that didn't exist this
  morning. A count-min sketch tracks frequencies in fixed memory, and a
  small heap keeps the heaviest hitters (both from
  [Module 02](../02-databases-storage/README.md#related-approximate-structures)).
  Trending terms are blended into the batch results at read time.

### The Client Is Half the Design

| Technique | Effect |
|-----------|--------|
| **Debounce** keystrokes (~100 ms) | Cuts request volume by roughly 3×, as in the estimate above |
| **Cache responses in the browser** (`Cache-Control: max-age=…`) | Backspacing and retyping cost nothing |
| **Filter the previous result locally** | Typing "syst" after "sys" can often be answered from "sys"'s list without a request |
| **Cancel in-flight requests** when a newer keystroke arrives | Stale responses can't overwrite fresh ones |

### Filtering and Safety

Suggestions are the search engine putting words in the user's mouth, so
filter them *at build time*: blocklists for abusive or dangerous terms,
removal of personal data that leaked into the query log (people search for
their own phone numbers and addresses), and a manual takedown path that
takes effect without waiting for the next rebuild — an override list
checked at read time.

---

## Part 2: Full-Text Search and the Inverted Index

Autocomplete finds *queries* by prefix. Full-text search finds *documents*
containing words — anywhere in the text, in any order. The structure behind
it is the **inverted index**: a map from each term to the documents that
contain it.

```
  Documents                      Inverted index (term → posting list)
  ─────────                      ────────────────────────────────────
  d1: "cache invalidation"       cache        → d1, d3
  d2: "consistent hashing"       consistent   → d2, d3
  d3: "consistent cache reads"   hashing      → d2
                                 invalidation → d1
                                 reads        → d3

  Query "consistent cache" → intersect {d2, d3} ∩ {d1, d3} = {d3}
```

**Building it** means tokenizing (split into terms, lowercase, strip
punctuation), optionally stemming ("caching" → "cach"), and appending each
document ID to every term's posting list. Posting lists are kept sorted, so
intersecting them is a linear merge, and they compress very well because
consecutive IDs differ by small amounts.

**Ranking** usually starts with BM25, which scores a document higher when a
query term appears often in it but rarely across the collection. Modern
systems combine it with embedding similarity — the hybrid search in
[Module 19](../19-rag-at-scale/README.md#hybrid-search).

**Updates** reuse the LSM idea from
[Module 02](../02-databases-storage/README.md#lsm-tree-append-then-merge-later):
new documents go into small immutable index *segments* that are merged in
the background. A document becomes searchable when its segment is
published — Elasticsearch's default refresh interval is 1 second, which is
why it is described as *near* real-time.

### Partitioning an Index

| | Document-partitioned | Term-partitioned |
|---|---|---|
| Each shard holds | A complete index of a subset of documents | All posting lists for a subset of terms |
| A query touches | **Every** shard (scatter-gather), then merges each shard's top results | Only the shards owning its terms |
| Multi-term queries | Intersection happens locally on each shard | Posting lists must be shipped between shards to intersect |
| Hot spots | Even — documents spread uniformly | A common term's shard takes most of the traffic |
| Used by | Elasticsearch, OpenSearch, Solr, most engines | Rare in practice |

Document partitioning wins despite asking every shard, because each shard's
work is independent and local. Its cost is tail latency: a query is as slow
as its slowest shard, so p99 rises with shard count (the fan-out effect in
[Module 15](../15-observability/README.md#23-why-you-cannot-average-percentiles)).
Replicas, hedged requests, and a per-shard timeout that returns partial
results keep it in check.

---

## Part 3: Proximity Search

### Requirements

Two very different products hide behind "find what's near me":

| | Places (restaurants, shops) | Moving objects (drivers, couriers) |
|---|---|---|
| Data changes | Rarely — a business moves once in years | Constantly — every few seconds |
| Workload | Read-heavy | **Write-heavy** |
| Typical query | "Coffee within 2 km, sorted by rating" | "Nearest available drivers to this pickup" |
| Freshness needed | Hours | Seconds — a 30-second-old position is wrong |

Same geometry, opposite data path. Design them separately.

### Why a Normal Index Fails

The first instinct:

```sql
SELECT * FROM places
WHERE lat BETWEEN 37.76 AND 37.79
  AND lng BETWEEN -122.43 AND -122.40;
```

A B-tree on `(lat, lng)` narrows by latitude only. Every place in that
latitude band — a stripe running all the way around the planet — still
has to be checked against the longitude condition. Two separate indexes
produce two huge candidate sets to intersect. A one-dimensional index
cannot answer a two-dimensional question efficiently. The fix is to map
2-D locations onto a 1-D key that preserves nearness, then use an ordinary
index on that key.

### Geohash

A geohash divides the world into a grid by repeatedly halving it —
alternating longitude and latitude — and writes the sequence of halves as a
base-32 string. **Places that share a prefix are in the same cell**, so a
cell lookup is a prefix lookup on an ordinary B-tree or sorted set.

```
  Precision (chars)   Cell size at the equator
        4             ~39 km  × 19.5 km
        5             ~4.9 km × 4.9 km
        6             ~1.2 km × 0.6 km
        7             ~153 m  × 153 m

  Away from the equator, cells get narrower east-west in proportion to
  cos(latitude). Pick the precision from the search radius:
  "within 2 km" → precision 5 or 6.
```

**The boundary problem.** Two cafés 10 m apart on opposite sides of a cell
edge can have completely different geohashes — the prefix property only
works one way (shared prefix ⇒ near, but near ⇏ shared prefix). Searching
just the user's cell silently misses results across the border. The fix
is to always search the cell **plus its 8 neighbours**, then filter by
exact distance:

```
                 north
  ┌────────┬────────┬────────┐
  │ 9q8yyj │ 9q8yym │ 9q8yyt │
  ├────────┼────────┼────────┤      ● = user in downtown San Francisco
  │ 9q8yyh │●9q8yyk │ 9q8yys │        (37.7749, -122.4194), precision 6
  ├────────┼────────┼────────┤
  │ 9q8yy5 │ 9q8yy7 │ 9q8yye │      search all 9 cells, then compute
  └────────┴────────┴────────┘      real distances and keep those
                                    within the radius

  These are the real cells, computed with the code below. Note the
  last characters: k's neighbours are j, m, t, h, s, 5, 7, e — no
  simple pattern, which is exactly why you compute them.
```

```python
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"   # no a, i, l, o


def encode(lat: float, lng: float, precision: int = 7) -> str:
    """Interleave longitude and latitude bisection bits, 5 bits per char."""
    lat_range, lng_range = [-90.0, 90.0], [-180.0, 180.0]
    bits, bit_count, out = 0, 0, []
    use_lng = True                       # geohash starts with longitude
    while len(out) < precision:
        rng, value = (lng_range, lng) if use_lng else (lat_range, lat)
        mid = (rng[0] + rng[1]) / 2
        if value >= mid:
            bits = (bits << 1) | 1
            rng[0] = mid
        else:
            bits <<= 1
            rng[1] = mid
        use_lng = not use_lng
        bit_count += 1
        if bit_count == 5:
            out.append(BASE32[bits])
            bits, bit_count = 0, 0
    return "".join(out)


def bounds(cell: str) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) of a geohash cell."""
    lat_range, lng_range = [-90.0, 90.0], [-180.0, 180.0]
    use_lng = True
    for ch in cell:
        idx = BASE32.index(ch)
        for shift in range(4, -1, -1):
            rng = lng_range if use_lng else lat_range
            mid = (rng[0] + rng[1]) / 2
            if (idx >> shift) & 1:
                rng[0] = mid
            else:
                rng[1] = mid
            use_lng = not use_lng
    return lat_range[0], lat_range[1], lng_range[0], lng_range[1]


def cells_to_search(lat: float, lng: float, precision: int) -> set[str]:
    """The point's own cell plus its 8 neighbours.

    Searching only the point's cell misses results just across a border:
    two places 10 m apart can sit in different cells with different
    prefixes. Re-encoding points one cell-width away in each direction
    finds the neighbours. (Near the poles and the ±180° meridian this
    needs wrap-around handling; real libraries do that for you.)
    """
    min_lat, max_lat, min_lng, max_lng = bounds(encode(lat, lng, precision))
    d_lat, d_lng = max_lat - min_lat, max_lng - min_lng
    c_lat, c_lng = (min_lat + max_lat) / 2, (min_lng + max_lng) / 2
    return {
        encode(c_lat + i * d_lat, c_lng + j * d_lng, precision)
        for i in (-1, 0, 1) for j in (-1, 0, 1)
    }


print(encode(57.64911, 10.40744, 11))   # u4pruydqqvj (standard test vector)
print(len(cells_to_search(37.7749, -122.4194, 6)))   # 9
```

Tested against the standard published test vector, and over 20,000
random points: every point within one cell-width of the query landed in
the 9-cell set.

### Quadtree: Adapting to Density

A fixed-precision grid is wasteful when density varies wildly: a precision-6
cell in Manhattan holds thousands of places, the same cell in the Sahara
holds none. A **quadtree** splits a cell into four only when it holds too
many items:

```
  ┌───────────────┬───────────────┐
  │               │       │       │
  │   rural:      │───────┼───────│   dense area keeps
  │   one big     │   │   │       │   splitting until
  │   leaf        │───┼───│       │   each leaf holds
  │               │   │   │       │   ≤ N places
  ├───────────────┼───────────────┤
  │               │               │
  │   empty       │    sparse     │
  │               │               │
  └───────────────┴───────────────┘
```

Every leaf then holds a bounded number of places, so a "nearby" query does
similar work everywhere. Quadtrees are usually built in memory per server
from the places table and rebuilt periodically — fine for places that
rarely move. Memory is modest: 100M places × ~24 bytes (ID plus
coordinates) ≈ 2.4 GB, so every replica can hold the whole tree.

### Choosing a Spatial Index

| | Geohash | Quadtree | S2 / H3 |
|---|---|---|---|
| Structure | Fixed grid, string prefix | Adaptive tree | Hierarchical cells on a sphere (S2: squares; H3: hexagons) |
| Storage | Any sorted index: B-tree, Redis sorted set | Custom in-memory structure | Integer cell IDs in any index |
| Uneven density | Poor — cells fixed size | Good — splits where needed | Good — choose the level per region |
| Neighbours | Compute 8 cells | Walk the tree | Library call; H3 hexagons have 6 equidistant neighbours |
| Best for | Simple, database-backed designs | Static places, in memory | Large geo platforms (S2: Google; H3: Uber) |

In an interview, geohash plus the 9-cell search is the expected baseline.
Naming quadtrees for uneven density, and S2/H3 for production scale, shows
you know where it stops working.

### Moving Objects: A Driver Location Service

```
Estimate:
  1M active drivers, each reporting position every 4 s
  1M / 4                         = 250,000 location writes/sec
  Live state: 1M × ~100 bytes    ≈ 100 MB

  The data fits in memory on one machine. The WRITE RATE does not:
  shard by region (city or geohash prefix), so each shard takes a
  fraction of the writes and a rider's query hits one shard.
```

```
  ┌──────────┐  every 4 s   ┌──────────────────┐   ┌───────────────────┐
  │  Driver  │ ───────────▶ │ Location service │──▶│ Redis GEO, sharded│
  │   app    │              │ (stateless)      │   │ by region         │
  └──────────┘              └────────┬─────────┘   └─────────┬─────────┘
                                     │ sampled               │ GEOSEARCH
                                     ▼                       ▼
                            ┌──────────────────┐   ┌───────────────────┐
                            │ Kafka → trip     │   │ Matching service  │
                            │ history, ETAs    │   │ (rider requests)  │
                            └──────────────────┘   └───────────────────┘
```

Redis has geospatial commands built on exactly this idea — positions are
stored in a sorted set whose score is a 52-bit geohash:

```
GEOADD drivers:sf -122.4194 37.7749 driver:42
GEOSEARCH drivers:sf FROMLONLAT -122.4183 37.7751 BYRADIUS 2 km ASC COUNT 10 WITHDIST
```

Three design decisions carry this system:

1. **Don't write every ping to the database.** Current position is
   ephemeral, high-volume state: keep it in memory. Stream pings to Kafka
   for history and analytics, sampled if needed, off the hot path.
2. **Handle disappearance explicitly.** Members of a sorted set do not
   expire individually — a TTL applies only to the whole key. A driver
   whose phone dies would stay "available" forever. Keep a per-driver
   heartbeat key with a short TTL (`SET driver:42:alive 1 EX 15`), or run
   a sweeper that removes members whose last update is too old.
3. **Re-shard drivers who cross regions.** A driver crossing from one
   shard's region into another's must be removed from the old shard and
   added to the new one; otherwise they show up in both, or in neither.

Matching then runs `GEOSEARCH` on the rider's region (and its neighbours,
if the rider is near a region edge — the boundary problem again), filters
by availability and vehicle type, and ranks by ETA rather than straight-line
distance, because a driver 500 m away across a river may be the furthest
in time.

---

## Design Comparison

| Aspect | Autocomplete | Full-text search | Places nearby | Drivers nearby |
|--------|-------------|------------------|---------------|----------------|
| Key insight | Precompute top-k per prefix | Invert documents into term → postings | Map 2-D to a 1-D key | Keep live state in memory |
| Read/write | Read-heavy | Read-heavy, batched writes | Read-heavy | **Write-heavy** |
| Freshness | Hours (+ trending in minutes) | ~1 s (near real-time) | Hours | Seconds |
| Core structure | Trie / prefix table | Inverted index segments | Geohash / quadtree | Geo sorted set (Redis) |
| Sharding | Hash of prefix | By document | By geohash prefix or replicate | By region |
| Classic trap | Hot short prefixes | Tail latency of scatter-gather | Cell boundary | Stale positions |

---

## Practice Exercise

**30-minute design**: Design a "restaurants near me" feature.

- 50M restaurants worldwide; 20M daily active users
- Query: restaurants within a chosen radius (500 m to 20 km), filtered by
  cuisine and "open now", sorted by a mix of rating and distance
- Restaurant owners edit their details; new restaurants appear within an hour
- p99 latency under 200 ms

**Key decisions**:
1. Geohash, quadtree, or S2? Justify it against the uneven density between
   cities and rural areas.
2. How do you choose the cell precision when the radius varies from 500 m to
   20 km?
3. Where do the "open now" and cuisine filters run — in the spatial index,
   or after it? What happens to latency if a query matches 50,000 restaurants?
4. How do edits propagate to the index within an hour without rebuilding it?

**Follow-up**: Add a "drivers nearby" view for delivery. What changes, and
what stays the same?

---

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Walking the trie subtree on every keystroke** | Cost grows with the number of completions, on the hottest path in the product | Cache the top-k at every node when building |
| **Mutating the live trie as queries arrive** | Concurrent writes on a read-optimized structure, and popularity flaps with every request | Build offline, swap atomically; blend a streaming trending layer at read time |
| **Sharding autocomplete by first letter** | "s" carries far more traffic than "x" — one shard runs hot | Hash the prefix, or range-split using the measured distribution |
| **No debounce on the client** | ~20 requests per search instead of ~6 — triple the fleet for no benefit | Debounce, cache locally, and cancel stale in-flight requests |
| **Filtering suggestions only at display time** | Abusive or personal-data suggestions still reach caches and logs | Filter at build time, with a fast override list for takedowns |
| **Term-partitioning a search index** | Multi-term queries ship posting lists between shards; common terms create hot shards | Partition by document; control tail latency with replicas and per-shard timeouts |
| **A `(lat, lng)` B-tree for nearby search** | It narrows by one dimension, leaving a planet-wide stripe to scan | Geohash, quadtree, or S2/H3 cells |
| **Searching only the user's geohash cell** | Results just across a cell edge vanish — near does not imply a shared prefix | Search the cell plus its 8 neighbours, then filter by exact distance |
| **One geohash precision for every radius** | Too coarse scans thousands of irrelevant places; too fine needs hundreds of cells | Pick precision from the radius, or use an adaptive structure |
| **Writing every driver ping to the database** | 250,000 writes/sec of data that is stale in four seconds | Hold current positions in memory; stream history to Kafka off the hot path |
| **Relying on a key TTL to expire individual drivers** | A sorted set's TTL applies to the whole set, not its members | Per-driver heartbeat keys with a TTL, or a sweeper |
| **Ranking drivers by straight-line distance** | Rivers, highways, and one-way streets make distance a poor proxy for arrival time | Shortlist by distance, then rank by routed ETA |

---

## Discussion Questions

1. Your autocomplete p99 jumped from 30 ms to 400 ms after a celebrity trended, but only for prefixes starting with that name. What happened, and how do you fix it?

   **Model answer**: A hot-key problem. Every user typing the trending name hits the same few prefix keys, which hash to one shard, and that shard saturates while the rest stay idle. Load-balancing the cluster can't help, because the load is concentrated on specific keys rather than spread across servers. Immediate fix: cache the hottest prefixes in-process on the application tier with a short TTL — the answers barely change minute to minute, so even a 10-second cache absorbs nearly all of it. Structural fix: detect hot keys automatically (a count-min sketch on request keys) and replicate them to several shards, picking a replica at random per read — the hot-key techniques from Module 03.

2. Product wants suggestions personalised to each user's own search history. What does that do to the architecture?

   **Model answer**: It breaks the property that made the design cheap: one answer per prefix, shared by everyone, cacheable at the edge. Don't build a per-user trie. Keep the global prefix table as the base, fetch a small per-user list of recent searches (tens of items, in a KV store keyed by user), and blend the two at request time — prefix-match the user's own list, then fill the remaining slots from the global list. The global part stays cacheable; only a small, bounded lookup is per user. Note the privacy implication too: a user's history must never leak into the global table, which aggregates across users precisely so that no individual query is exposed.

3. A rider is standing 20 m from the edge of a geohash cell, and the only nearby driver is 50 m away on the other side. Walk through what a naive design returns and what a correct one returns.

   **Model answer**: The naive design looks up the rider's cell, finds no drivers, and reports "no cars available" — while a car is 50 m away. The rider and driver share no prefix because they're in adjacent cells, and geohash only guarantees that a shared prefix means near, not the reverse. The correct design computes the rider's cell and its 8 neighbours, collects drivers from all 9, computes exact distances, and filters to the radius. That finds the driver at 50 m. The 9-cell search must also cover shard boundaries: if regions are sharded, a rider near a region edge needs a query to the neighbouring shard as well.

4. Why do Elasticsearch-style engines partition by document even though every query must visit every shard?

   **Model answer**: Because each shard's work is self-contained. A multi-term query intersects posting lists locally on each shard, and the coordinator only merges small per-shard top-k lists. Term partitioning would let a query visit fewer shards, but intersecting "consistent" and "cache" would mean shipping one term's posting list — possibly millions of IDs — across the network to the other's shard, and the shard owning a very common term would carry a large share of all queries. The cost of document partitioning is tail latency: a query waits for its slowest shard, so p99 worsens as shard count grows. That cost is manageable with replicas, hedged requests, and per-shard timeouts that return partial results. Term partitioning's costs are structural and hard to manage.

5. You need "drivers near me" for 1M drivers updating every 4 seconds. A colleague proposes Postgres with PostGIS. Evaluate it.

   **Model answer**: PostGIS has excellent spatial indexes and is the right tool for *places* — data that changes rarely and needs rich queries. For live driver positions the issue is the write path, not the geometry: 250,000 updates per second, each rewriting an indexed row and generating WAL and replication traffic, for data that is obsolete four seconds later. That is a heavy durable-write workload for state nobody needs to keep. The better split: current positions in an in-memory store (Redis GEO, sharded by region), where an update is a cheap overwrite, and position history streamed to Kafka and on to analytical storage, sampled if needed. PostGIS stays in the design for what it's good at: the places themselves, service-area polygons, and offline analysis of trips.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview Vol. 1 (Ch. 13) & Vol. 2 (Ch. 1-2) — Alex Xu | Book | Search autocomplete; proximity service; nearby friends |
| *Introduction to Information Retrieval* — Manning, Raghavan, Schütze | Book (free online) | Inverted indexes, posting-list compression, ranking |
| [Elasticsearch: near real-time search](https://www.elastic.co/guide/en/elasticsearch/reference/current/near-real-time.html) | Docs | Segments and the refresh interval |
| [Redis geospatial commands](https://redis.io/docs/latest/develop/data-types/geospatial/) | Docs | `GEOADD`, `GEOSEARCH`, the geohash-scored sorted set |
| [Uber H3](https://h3geo.org/) | Docs | Hexagonal hierarchical spatial index |
| [S2 Geometry](https://s2geometry.io/) | Docs | Hierarchical cells on the sphere |
| [Geohash (Wikipedia)](https://en.wikipedia.org/wiki/Geohash) | Reference | Encoding algorithm and the standard test vector |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 02: Databases and Storage](../02-databases-storage/README.md) | B-trees, LSM segments, and the approximate structures used for trending terms |
| [Module 03: Caching](../03-caching/README.md) | Hot keys and edge caching for short prefixes |
| [Module 05: Async Systems](../05-async-systems/README.md) | Query logs and location streams through Kafka |
| [Module 09: URL Shortener and Rate Limiter](../09-case-url-shortener-rate-limiter/README.md) | The same read-heavy, precompute-then-look-up shape |
| [Module 19: RAG at Scale](../19-rag-at-scale/README.md) | Hybrid search — BM25 over an inverted index combined with embeddings |

---

## Navigation

**Previous:** [Module 22: Production AI System Architecture](../22-production-ai-system/README.md)

**Next:** [Course Home](../README.md)

---

*Module 23 of 23 in the System Design Playground*
