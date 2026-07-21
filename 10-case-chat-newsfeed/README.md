# Module 10: Design Case — Chat System and News Feed

> **Real-time communication at scale.** These systems test your ability to handle persistent connections, message ordering, fan-out patterns, and ranking algorithms.

## Learning Objectives

- Design a chat system with WebSocket connections
- Implement fan-out strategies for news feeds
- Handle the celebrity problem in social media
- Design real-time presence and read receipts

---

## Part 1: Chat System (WhatsApp/Telegram)

### Requirements

- **Functional**: 1-on-1 chat, group chat (up to 100 members), message history, presence, read receipts
- **Scale**: 500M messages/day, 50M daily active users
- **Latency**: <200ms message delivery
- **Ordering**: Messages within a conversation must be ordered
- **Persistence**: Messages stored for 30 days (free) or forever (paid)

### Capacity Estimation

```
Messages per second: 500M / 86400 ≈ 5,800 msg/sec
Peak (3x): ~17,400 msg/sec

Storage per message:
  message_id:  8 bytes
  chat_id:     8 bytes
  sender_id:   8 bytes
  content:     ~100 bytes (text), ~100KB (image)
  timestamp:   8 bytes
  Total:       ~132 bytes (text)

Per day: 500M × 132 bytes ≈ 66 GB
Per year: ~24 TB (text only)
```

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Chat System Architecture                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Connection Layer (WebSocket Gateway)             │    │
│  │  ┌──────┐  ┌──────┐  ┌──────┐                   │    │
│  │  │ WS   │  │ WS   │  │ WS   │  (stateful)       │    │
│  │  │Server│  │Server│  │Server│                   │    │
│  │  └──┬───┘  └──┬───┘  └──┬───┘                   │    │
│  │     └─────────┼─────────┘                       │    │
│  └───────────────┼─────────────────────────────────┘    │
│                  │                                       │
│  ┌───────────────▼─────────────────────────────────┐    │
│  │  Chat Service                                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │    │
│  │  │ Message  │  │ Presence │  │  Group   │     │    │
│  │  │ Service  │  │ Service  │  │  Service │     │    │
│  │  └──────────┘  └──────────┘  └──────────┘     │    │
│  └───────────────┬─────────────────────────────────┘    │
│                  │                                       │
│  ┌───────────────▼─────────────────────────────────┐    │
│  │  Data Layer                                       │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │    │
│  │  │ Cassandra│  │  Redis   │  │  Kafka   │     │    │
│  │  │(messages)│  │(presence,│  │(message  │     │    │
│  │  │          │  │  sessions)│  │ events)  │     │    │
│  │  └──────────┘  └──────────┘  └──────────┘     │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### WebSocket Gateway

The connection layer is the most critical component. Each user maintains a persistent WebSocket connection.

```
  Client ──── WebSocket ────▶ WS Server
                              │
  Connection state:           │
  - user_id                   │
  - server_id (which WS server)│
  - connection_id             │
  - last_active               │
                              │
  Stored in Redis:            │
  user:{user_id} → {server_id, connection_id, last_active}
```

### Message Flow

```
  Alice sends message to Bob:

  1. Alice → WS Server A: { chat_id: "chat_123", content: "Hello" }
  2. WS Server A → Chat Service: Process message
  3. Chat Service:
     a. Assign message_id (Snowflake or similar)
     b. Write to Cassandra (async)
     c. Write to Kafka (for analytics)
     d. Check Bob's connection:
        - If Bob connected to WS Server B:
          Route message to WS Server B → Deliver to Bob
        - If Bob offline:
          Store in pending messages queue (Redis)
          Send push notification
  4. Alice receives ACK: { message_id: "msg_456", status: "sent" }
```

### Message Ordering

```
  Challenge: Multiple messages from Alice may arrive out of order
  
  Solution: Sequence numbers per conversation

  Chat 123:
  Alice → msg_seq=1 → Bob receives msg_seq=1 ✓
  Alice → msg_seq=2 → Bob receives msg_seq=2 ✓
  Alice → msg_seq=3 → Bob receives msg_seq=3 ✓

  If Bob receives msg_seq=3 before msg_seq=2:
  → Buffer msg_seq=3, wait for msg_seq=2
  → Deliver in order: 1, 2, 3
```

### Presence System

```
  ┌─────────────────────────────────────────────────┐
  │  Presence System                                  │
  │                                                   │
  │  User connects:                                   │
  │  Redis SET presence:{user_id} EX 60              │
  │  (expires after 60 seconds if no heartbeat)      │
  │                                                   │
  │  Heartbeat:                                       │
  │  Every 30 seconds: Redis EXPIRE presence:{user} 60│
  │                                                   │
  │  User goes offline:                               │
  │  Redis DEL presence:{user_id}                     │
  │  Publish "user_offline" event to chat members     │
  │                                                   │
  │  Check presence:                                  │
  │  Redis GET presence:{user_id} → EXISTS = online   │
  └─────────────────────────────────────────────────┘
```

### Read Receipts

```
  Two states: Sent ✓, Delivered ✓✓, Read ✓✓ (blue)

  Alice sends message to Bob:
  1. Message sent: status = "sent"
  2. Bob's device receives: status = "delivered"
  3. Bob opens chat: status = "read"

  Storage:
  message_read_status: { message_id, user_id, status, timestamp }

  Optimization: Batch read receipts (don't send per-message)
  Bob reads 50 messages → send one "read up to message X" event
```

---

## Part 2: News Feed (Twitter/Instagram)

### Requirements

- **Functional**: Create posts, follow users, view feed, like/comment
- **Scale**: 500M tweets/day, 200M DAU, 100:1 read/write
- **Latency**: Feed loads in <200ms
- **Ranking**: Chronological or algorithmic (engagement-based)

### The Fan-Out Problem

When a user posts, their content must appear in all followers' feeds.

```
  Fan-out on Write (Push):
  ┌─────────────────────────────────────────────────┐
  │  User posts tweet                                 │
  │  │                                                │
  │  ├──▶ Follower 1's feed (write to their feed)    │
  │  ├──▶ Follower 2's feed                          │
  │  ├──▶ Follower 3's feed                          │
  │  └──▶ Follower 10,000's feed                     │
  │                                                   │
  │  ✓ Feed read is fast (pre-computed)               │
  │  ✗ Write amplification (1 post → 10K writes)     │
  │  ✗ Celebrity problem (1 post → 10M writes!)      │
  └─────────────────────────────────────────────────┘

  Fan-out on Read (Pull):
  ┌─────────────────────────────────────────────────┐
  │  User opens feed                                  │
  │  │                                                │
  │  ├──▶ Check: Who does this user follow?           │
  │  ├──▶ Fetch recent posts from each followed user  │
  │  ├──▶ Merge and sort                              │
  │  └──▶ Return feed                                 │
  │                                                   │
  │  ✓ No write amplification                         │
  │  ✗ Feed read is slow (multiple DB queries)       │
  │  ✗ High latency for users following many people  │
  └─────────────────────────────────────────────────┘
```

### Hybrid Fan-Out (The Real Solution)

```
  ┌─────────────────────────────────────────────────┐
  │           Hybrid Fan-Out Strategy                 │
  │                                                   │
  │  Regular users ( <10K followers):                 │
  │  → Push on write (fan-out to followers' feeds)   │
  │                                                   │
  │  Celebrity users ( >10K followers):              │
  │  → Pull on read (fetch during feed generation)   │
  │                                                   │
  │  Feed generation:                                 │
  │  1. Start with pre-computed feed (pushed posts)  │
  │  2. Merge in real-time posts from celebrities    │
  │  3. Sort by ranking algorithm                     │
  │  4. Return top N posts                            │
  └─────────────────────────────────────────────────┘
```

### Feed Architecture

```
┌─────────────────────────────────────────────────────────┐
│              News Feed Architecture                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User posts → Post Service → Fan-out Service             │
│                              │                           │
│                    ┌─────────┼─────────┐                │
│                    │         │         │                │
│                    ▼         ▼         ▼                │
│              ┌─────────┐ ┌─────┐ ┌─────────┐          │
│              │Feed Cache│ │Feed │ │Analytics│          │
│              │(Redis)   │ │DB   │ │(Kafka)  │          │
│              │per-user  │ │     │ │         │          │
│              │sorted set│ │     │ │         │          │
│              └─────────┘ └─────┘ └─────────┘          │
│                                                          │
│  Feed read:                                              │
│  1. ZREVRANGE feed:{user_id} 0 19 (top 20 posts)       │
│  2. For each post, hydrate with content/user info        │
│  3. Apply ranking algorithm                              │
│  4. Return to client                                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Feed Storage in Redis

```
  Redis Sorted Set for each user's feed:

  Key: feed:{user_id}
  Score: timestamp (or ranking score)
  Value: post_id

  ZADD feed:alice 1690000001 "post_123"
  ZADD feed:alice 1690000002 "post_456"
  ZADD feed:alice 1690000003 "post_789"

  ZREVRANGE feed:alice 0 19  # Latest 20 posts

  Cleanup: Remove posts older than 7 days
  ZREMRANGEBYRANK feed:alice 0 -1  (with time-based filtering)
```

### Ranking Algorithm

```
  Simple engagement-based ranking:

  score = (likes × 1.0) + (comments × 2.0) + (shares × 3.0) + recency_bonus

  recency_bonus = max(0, 1.0 - (hours_since_post / 24))

  Example:
  Post A: 100 likes, 20 comments, 10 shares, posted 2 hours ago
  score = 100×1 + 20×2 + 10×3 + (1 - 2/24) = 100 + 40 + 30 + 0.92 = 170.92

  Post B: 500 likes, 5 comments, 0 shares, posted 20 hours ago
  score = 500×1 + 5×2 + 0×3 + (1 - 20/24) = 500 + 10 + 0 + 0.17 = 510.17

  Post B ranks higher (more engagement despite being older)
```

---

## Design Comparison

| Aspect | Chat System | News Feed |
|--------|------------|-----------|
| **Data flow** | Bidirectional (sender ↔ receiver) | One-to-many (author → followers) |
| **Ordering** | Strict (messages in order) | Approximate (feed ranking) |
| **Storage** | Cassandra (time-series) | Redis (sorted sets) + MySQL |
| **Real-time** | WebSocket (persistent) | Polling or push notifications |
| **Fan-out** | N/A (point-to-point) | Push + pull hybrid |

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview (Ch. 4-5) | Book | Chat system, news feed |
| WhatsApp Engineering Blog | Blog | Message delivery at scale |
| Twitter Engineering Blog | Blog | Fan-out, timeline ranking |
| "Building Microservices" (Ch. 5) | Book | Real-time communication |

---

**Previous**: [Design Case — URL Shortener and Rate Limiter](../09-case-url-shortener-rate-limiter/README.md)
**Next**: [Design Case — Distributed File Storage and Video Streaming](../11-case-storage-streaming/README.md)
