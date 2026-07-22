# Module 08: Distributed Systems Deep Dive

> **The hard problems in distributed computing.** When you split a system across multiple machines, you inherit fundamental challenges: consensus, ordering, consistency, and failure detection. These problems have well-studied solutions.

## Learning Objectives

- Understand consensus algorithms (Raft, Paxos)
- Design leader election and fencing
- Reason about logical clocks and event ordering
- Implement distributed transactions (2PC, sagas)
- Use CRDTs for conflict-free replication

---

## The Eight Fallacies of Distributed Systems

Peter Deutsch's famous list — every distributed system violates these at some point:

1. The network is reliable
2. Latency is zero
3. Bandwidth is infinite
4. The network is secure
5. Topology doesn't change
6. There is one administrator
7. Transport cost is zero
8. The network is homogeneous

**Design for the reality: the network WILL fail.**

---

## Consensus Algorithms

### The Consensus Problem

Multiple nodes must agree on a single value. All nodes must agree, and the value must be proposed by at least one node.

```
  Node A proposes: "Write X=5"
  Node B proposes: "Write X=7"
  Node C proposes: "Write X=3"

  Consensus: All nodes must agree on ONE value (e.g., X=5)
  Properties:
  - Agreement: All nodes decide the same value
  - Validity: The decided value was proposed by someone
  - Termination: All nodes eventually decide
```

### Raft (Understandable Consensus)

Raft is designed for understandability. Used by etcd, TiKV, CockroachDB.

```
  ┌─────────────────────────────────────────────────┐
  │              Raft Cluster                        │
  │                                                   │
  │  States: Leader, Follower, Candidate             │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
  │  │  Leader  │  │Follower  │  │Follower  │      │
  │  │  (Node 1)│  │ (Node 2) │  │ (Node 3) │      │
  │  └──────────┘  └──────────┘  └──────────┘      │
  │                                                   │
  │  Term: 1 → 2 → 3 (monotonically increasing)     │
  └─────────────────────────────────────────────────┘

  Leader election:
  1. Follower doesn't hear from leader → becomes Candidate
  2. Candidate requests votes from other nodes
  3. Majority votes → becomes Leader
  4. Leader sends heartbeats to maintain authority
```

### Raft Log Replication

```
  Leader receives write: X=5
  │
  ▼
  Append to Leader's log
  │
  ▼
  Replicate to Followers
  │
  ├──▶ Follower 1: Append to log → ACK
  ├──▶ Follower 2: Append to log → ACK
  │
  ▼
  Majority ACKed → Commit → Apply to state machine
  │
  ▼
  Notify followers of commit

  ┌─────────────────────────────────────────────┐
  │  Log Index:  1    2    3    4    5          │
  │  Leader:    [X=1][X=2][X=3][X=4][X=5] ✓    │
  │  Follower1: [X=1][X=2][X=3][X=4][X=5] ✓    │
  │  Follower2: [X=1][X=2][X=3][X=4]    (lagging)│
  └─────────────────────────────────────────────┘

  Leader catches up lagging follower in next heartbeat.
```

### Raft vs Paxos

| Factor | Raft | Paxos |
|--------|------|-------|
| **Understandability** | Designed for clarity | Notoriously hard to understand |
| **Leader** | Strong leader | Leaderless (Multi-Paxos) |
| **Log** | Strict ordering | May have gaps |
| **Use** | etcd, TiKV, CockroachDB | Google Chubby, Spanner |
| **Performance** | Good | Slightly better in some cases |

---

## Leader Election

### Why Leaders?

```
  Without leader:                With leader:
  ┌───┐ ┌───┐ ┌───┐            ┌───┐
  │ A │ │ B │ │ C │            │ A │ ← Leader (handles writes)
  └─┬─┘ └─┬─┘ └─┬─┘            └─┬─┘
    │     │     │                │
    │  All compete                │ Replicate to
    │  for writes                 │
    ▼     ▼     ▼                ▼
  Conflict!                  ┌───┐ ┌───┐
                             │ B │ │ C │ ← Followers
                             └───┘ └───┘

  Leader ensures single writer → no conflicts
```

### Fencing Tokens

Prevent stale leaders from acting on old data.

```python
import threading
from dataclasses import dataclass, field

@dataclass
class FencedResource:
    """Resource protected by fencing tokens."""
    
    _last_token: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _data: dict = field(default_factory=dict)
    
    def write(self, token: int, key: str, value: any) -> bool:
        """Write only if token is higher than last seen."""
        with self._lock:
            if token < self._last_token:
                print(f"REJECTED: token {token} < last token {self._last_token}")
                return False
            
            self._last_token = token
            self._data[key] = value
            print(f"ACCEPTED: token {token}, wrote {key}={value}")
            return True
    
    def read(self) -> dict:
        return self._data.copy()

@dataclass
class Leader:
    """Leader with fencing token."""
    
    node_id: str
    fence_token: int = 0
    
    def acquire_lock(self) -> int:
        """Increment token when acquiring lock."""
        self.fence_token += 1
        return self.fence_token

# Simulate the problem:
resource = FencedResource()
leader_a = Leader("A", fence_token=0)
leader_b = Leader("B", fence_token=0)

# 1. A becomes leader, acquires lock (token=1)
token_a = leader_a.acquire_lock()
resource.write(token_a, "counter", 100)  # ACCEPTED

# 2. Network partition: A can't reach others
# 3. B becomes new leader, acquires lock (token=2)
token_b = leader_b.acquire_lock()
resource.write(token_b, "counter", 200)  # ACCEPTED (token 2 > 1)

# 4. Partition heals: A thinks it's still leader
# 5. A tries to write with old token
resource.write(token_a, "counter", 300)  # REJECTED (token 1 < 2)
```

```
  Problem:
  1. Leader A holds lock on resource
  2. Network partition: A can't reach others
  3. B becomes new leader, acquires lock
  4. Partition heals: A thinks it's still leader
  5. A writes to resource (conflicting with B's write!)

  Solution: Fencing tokens
  - Each lock/leadership gets a monotonically increasing token
  - Resource server rejects writes with tokens ≤ last seen token

  Token 1: A acquires lock
  Token 2: B acquires lock (higher token)
  A tries to write with token 1 → REJECTED (token 2 is current)
```

---

## Logical Clocks

Physical clocks are unreliable in distributed systems (clock drift, NTP sync issues). Logical clocks provide causality ordering.

### Lamport Timestamps

```python
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class LamportClock:
    """Lamport logical clock for causality ordering."""
    
    counter: int = 0
    process_id: str = ""
    
    def tick(self) -> int:
        """Local event: increment counter."""
        self.counter += 1
        return self.counter
    
    def send(self) -> int:
        """Send message: include current timestamp."""
        self.counter += 1
        return self.counter
    
    def receive(self, received_ts: int) -> int:
        """Receive message: take max(local, received) + 1."""
        self.counter = max(self.counter, received_ts) + 1
        return self.counter

# Simulate the example:
a = LamportClock(process_id="A")
b = LamportClock(process_id="B")
c = LamportClock(process_id="C")

# Process A: local event
ts_a1 = a.tick()
print(f"A: event a1, ts={ts_a1}")  # A: event a1, ts=1

# Process A sends to C
ts_msg = a.send()
print(f"A: sends msg, ts={ts_msg}")  # A: sends msg, ts=2

# Process C receives
ts_c1 = c.receive(ts_msg)
print(f"C: receives msg, ts={ts_c1}")  # C: receives msg, ts=3

# Process C sends to B
ts_msg2 = c.send()

# Process B receives
ts_b1 = b.receive(ts_msg2)
print(f"B: receives msg, ts={ts_b1}")  # B: receives msg, ts=4

# Ordering: a1(1) < sends(2) < c_receives(3) < b_receives(4)
```

```
  Rule 1: Before each event, increment local counter
  Rule 2: When sending a message, include current counter
  Rule 3: When receiving a message, set counter = max(local, received) + 1

  Process A:    Process B:    Process C:
  │              │              │
  │ a1 (1)      │              │
  │ ─────────────│──msg────────▶│
  │              │              │ c1 (2)
  │              │ b1 (2)      │
  │              │◀──msg────────│
  │ a2 (3)      │              │

  Lamport ordering: a1 < b1 < c1 < a2 (but NOT total order — parallel events)
```

### Vector Clocks

Track causality more precisely than Lamport timestamps.

```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class VectorClock:
    """Vector clock for tracking causality across processes."""
    
    process_id: str
    clock: Dict[str, int] = field(default_factory=dict)
    
    def tick(self) -> Dict[str, int]:
        """Local event: increment own counter."""
        self.clock[self.process_id] = self.clock.get(self.process_id, 0) + 1
        return self.clock.copy()
    
    def send(self) -> Dict[str, int]:
        """Send message: include full vector."""
        self.clock[self.process_id] = self.clock.get(self.process_id, 0) + 1
        return self.clock.copy()
    
    def receive(self, received_clock: Dict[str, int]) -> Dict[str, int]:
        """Receive message: merge vectors (take max of each)."""
        for process, ts in received_clock.items():
            self.clock[process] = max(self.clock.get(process, 0), ts)
        self.clock[self.process_id] = self.clock.get(self.process_id, 0) + 1
        return self.clock.copy()
    
    @staticmethod
    def compare(a: Dict[str, int], b: Dict[str, int]) -> str:
        """Compare two vector clocks.
        Returns: 'before', 'after', or 'concurrent'
        """
        a_leq_b = all(a.get(k, 0) <= b.get(k, 0) for k in set(a) | set(b))
        b_leq_a = all(b.get(k, 0) <= a.get(k, 0) for k in set(a) | set(b))
        
        if a_leq_b and b_leq_a:
            return "equal"
        elif a_leq_b:
            return "before"  # a happened before b
        elif b_leq_a:
            return "after"   # a happened after b
        else:
            return "concurrent"  # neither caused the other

# Simulate:
va = VectorClock(process_id="A")
vb = VectorClock(process_id="B")

# A: local events
va.tick()
va.tick()
print(f"A: {va.clock}")  # A: {'A': 2}

# A sends to B
msg = va.send()
vb.receive(msg)
print(f"B after receive: {vb.clock}")  # B: {'A': 3, 'B': 1}

# Compare
print(VectorClock.compare(va.clock, vb.clock))  # 'before'
```

```
  Each process maintains a vector of counters (one per process):

  Process A: [A:3, B:2, C:1]  — "I've seen A's 3rd, B's 2nd, C's 1st event"
  Process B: [A:2, B:4, C:1]

  Comparison:
  - [A:3, B:2, C:1] < [A:3, B:4, C:1]  (B has seen more of B's events)
  - [A:3, B:2, C:1] ∥ [A:2, B:2, C:3]  (concurrent — neither caused the other)

  Use case: Detecting concurrent updates (CRDTs, conflict resolution)
```

---

## Distributed Transactions

### Two-Phase Commit (2PC)

```
  Coordinator                    Participants
      │                           │         │
      │── Phase 1: PREPARE ──────▶│         │
      │                           │ Vote:   │
      │◀── Vote: YES ────────────│ YES     │
      │                           │         │
      │── Phase 1: PREPARE ────────────────▶│
      │                           │ Vote:   │
      │◀── Vote: YES ──────────────────────│ YES
      │                           │         │
      │── Phase 2: COMMIT ───────▶│         │
      │                           │ Commit! │
      │── Phase 2: COMMIT ────────────────▶│
      │                           │         │ Commit!

  Problem: Coordinator crashes after Phase 1 but before Phase 2
  → Participants are stuck in "prepared" state (holding locks)

  ✓ Strong consistency
  ✗ Blocking (2PC is a blocking protocol)
  ✗ Coordinator is SPOF
  ✗ Performance: 2 round trips
```

### Saga Pattern (Already covered in Module 06)

Sagas avoid the blocking problem of 2PC by using compensating actions instead of locks.

### TCC (Try-Confirm/Cancel)

```
  Try:     Reserve resources (but don't commit)
  Confirm: Commit all reservations
  Cancel:  Release all reservations

  ┌──────────────────────────────────────┐
  │  Order Service:                       │
  │  1. Try: Reserve inventory            │
  │  2. Try: Reserve payment              │
  │  3. If all OK → Confirm both          │
  │  4. If any fail → Cancel both         │
  └──────────────────────────────────────┘

  ✓ No long-held locks
  ✓ Resources reserved atomically
  ✗ More complex than 2PC
  ✗ Try phase must be idempotent
```

---

## CRDTs (Conflict-Free Replicated Data Types)

Data structures that can be replicated across nodes and merged without conflicts.

### G-Counter (Grow-Only Counter)

```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class GCounter:
    """Grow-only counter CRDT. Can only increment."""
    
    node_id: str
    counts: Dict[str, int] = field(default_factory=dict)
    
    def increment(self, amount: int = 1):
        """Increment this node's counter."""
        self counts[self.node_id] = self.counts.get(self.node_id, 0) + amount
    
    def value(self) -> int:
        """Get total count across all nodes."""
        return sum(self.counts.values())
    
    def merge(self, other: "GCounter"):
        """Merge with another GCounter (take max of each component)."""
        for node, count in other.counts.items():
            self.counts[node] = max(self.counts.get(node, 0), count)

# Simulate distributed counters:
node_a = GCounter(node_id="A")
node_b = GCounter(node_id="B")

# Each node increments independently
node_a.increment(5)
node_a.increment(3)
node_b.increment(7)
node_b.increment(1)

print(f"Node A: {node_a.counts}")  # {'A': 8}
print(f"Node B: {node_b.counts}")  # {'B': 8}

# Merge: take max of each component
node_a.merge(node_b)
print(f"After merge: {node_a.counts}")  # {'A': 8, 'B': 8}
print(f"Total: {node_a.value()}")  # 16
```

```
  Each node maintains its own counter:
  Node A: {A: 5, B: 3, C: 2}
  Node B: {A: 3, B: 7, C: 1}

  Merge: Take max of each component
  {A: max(5,3), B: max(3,7), C: max(2,1)} = {A: 5, B: 7, C: 2}
  Total: 5 + 7 + 2 = 14

  ✓ Always converges
  ✓ No coordination needed
  ✗ Only counts UP (can't decrement)
```

### PN-Counter (Positive-Negative Counter)

```python
@dataclass
class PNCounter:
    """Positive-Negative counter CRDT. Can increment and decrement."""
    
    node_id: str
    inc: GCounter = field(default_factory=lambda: GCounter(""))
    dec: GCounter = field(default_factory=lambda: GCounter(""))
    
    def __post_init__(self):
        self.inc = GCounter(node_id=self.node_id)
        self.dec = GCounter(node_id=self.node_id)
    
    def increment(self, amount: int = 1):
        self.inc.increment(amount)
    
    def decrement(self, amount: int = 1):
        self.dec.increment(amount)
    
    def value(self) -> int:
        return self.inc.value() - self.dec.value()
    
    def merge(self, other: "PNCounter"):
        self.inc.merge(other.inc)
        self.dec.merge(other.dec)

# Usage:
node_a = PNCounter(node_id="A")
node_a.increment(10)
node_a.decrement(3)
print(f"Node A: {node_a.value()}")  # 7

node_b = PNCounter(node_id="B")
node_b.increment(5)
node_b.decrement(1)

node_a.merge(node_b)
print(f"After merge: {node_a.value()}")  # 11 (10-3) + (5-1) = 11
```

```
  Two G-counters: one for increments, one for decrements

  Node A: {inc: {A: 5}, dec: {A: 2}} = net 3
  Node B: {inc: {A: 3}, dec: {A: 1}} = net 2

  Merge: max of each component in each counter
  Total: (5+3) - (2+1) = 8 - 3 = 5
```

### LWW-Register (Last-Writer-Wins)

```python
import time
from dataclasses import dataclass

@dataclass
class LWWRegister:
    """Last-Writer-Wins register CRDT."""
    
    node_id: str
    value: any = None
    timestamp: float = 0
    
    def set(self, new_value: any):
        """Set value with current timestamp."""
        self.value = new_value
        self.timestamp = time.time() * 1000  # milliseconds
    
    def merge(self, other: "LWWRegister"):
        """Keep the value with the higher timestamp."""
        if other.timestamp > self.timestamp:
            self.value = other.value
            self.timestamp = other.timestamp

# Usage:
node_a = LWWRegister(node_id="A")
node_b = LWWRegister(node_id="B")

# Concurrent writes (in distributed system, timestamps differ)
time.sleep(0.001)
node_a.set("hello")
time.sleep(0.001)
node_b.set("world")

node_a.merge(node_b)
print(f"After merge: {node_a.value}")  # "world" (higher timestamp wins)
```

```
  Each value has a timestamp:
  (value="hello", timestamp=100)
  (value="world", timestamp=200)

  Merge: Keep the one with the higher timestamp
  → (value="world", timestamp=200)

  ✓ Simple
  ✗ May lose concurrent updates (last writer wins, ignoring others)
```

### CRDT Use Cases

| CRDT | Use Case | Real System |
|------|----------|-------------|
| G-Counter | Like counts, view counts | Facebook reactions |
| PN-Counter | Balance tracking | Distributed wallets |
| LWW-Register | Config updates | Feature flags |
| OR-Set | Collaborative editing | Google Docs, Figma |
| MV-Register | Multi-version values | Collaborative databases |

---

## Case Study: ZooKeeper / etcd

Coordination services that provide distributed primitives.

### What ZooKeeper/etcd Provide

| Primitive | Description | Use Case |
|-----------|-------------|----------|
| **Distributed Lock** | Only one client holds the lock at a time | Leader election, job scheduling |
| **Leader Election** | Automatically elect a leader from a group | Database replication, task assignment |
| **Configuration** | Store and watch for config changes | Dynamic configuration |
| **Service Discovery** | Register and discover services | Microservices |
| **Barrier** | Wait for all nodes to reach a point | Distributed synchronization |

### etcd Architecture (Raft-based)

```
  ┌─────────────────────────────────────────────────┐
  │                  etcd Cluster                     │
  │                                                   │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
  │  │  Leader  │  │Follower  │  │Follower  │      │
  │  │ (Node 1) │  │ (Node 2) │  │ (Node 3) │      │
  │  │          │  │          │  │          │      │
  │  │ Raft Log │  │ Raft Log │  │ Raft Log │      │
  │  │ [X=1]    │  │ [X=1]    │  │ [X=1]    │      │
  │  │ [X=2]    │  │ [X=2]    │  │ [X=2]    │      │
  │  │ [X=3] ✓  │  │ [X=3]    │  │ [X=3]    │      │
  │  └──────────┘  └──────────┘  └──────────┘      │
  │                                                   │
  │  Client reads from Leader (or any node with      │
  │  read consistency)                               │
  └─────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Linearizability**: Every read sees the latest committed write. This is achieved by reading from the leader or using a read index.

2. **Watch mechanism**: Clients can watch for changes to keys. When a key changes, all watchers are notified. This enables reactive architectures.

3. **Lease-based TTL**: Keys can have leases. If the lease holder crashes, the key is automatically deleted. This prevents stale registrations.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| DDIA Ch. 7-9 | Book | Replication, partitioning, transactions |
| "In Search of an Understandable Consensus Algorithm" (Raft paper) | Paper | Raft algorithm |
| ZooKeeper Documentation | Docs | Distributed coordination |
| etcd Documentation | Docs | Raft-based key-value store |
| "Designing Data-Intensive Applications" | Book | Comprehensive distributed systems |

---

## Practice Exercise

**20-minute design**: Design a distributed counter service:

- Count likes on social media posts
- 10K likes/second
- Must be eventually consistent
- Can tolerate brief inaccuracies

**Key decisions**:
1. Would you use CRDTs? Which type?
2. How do you handle concurrent updates?
3. How do you aggregate counts across nodes?
4. What's the trade-off between accuracy and performance?

---

## Discussion Questions

1. You're building a distributed lock service. What happens if the lock holder crashes? How do you prevent deadlock?

2. Explain the difference between Lamport timestamps and vector clocks. When would you use each?

3. Your team is debating between 2PC and sagas for a distributed transaction. What are the trade-offs?

4. How do CRDTs achieve conflict-free replication? What are their limitations?

5. Design a leader election system for a 5-node cluster. What happens when the leader crashes?

---

**Previous**: [Reliability Engineering](../07-reliability/README.md)
**Next**: [Design Case — URL Shortener and Rate Limiter](../09-case-url-shortener-rate-limiter/README.md)
