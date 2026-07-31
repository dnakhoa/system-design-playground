# Module 11: Design Case — Distributed File Storage and Video Streaming

> **Storage-intensive systems.** These systems test your ability to handle large files, efficient storage, content delivery, and media processing pipelines.

## Learning Objectives

- Design a distributed file storage system (Dropbox/Google Drive)
- Design a video streaming platform (YouTube/Netflix)
- Implement chunking, deduplication, and sync protocols
- Design transcoding pipelines and adaptive bitrate streaming

---

## Part 1: Distributed File Storage (Dropbox/Google Drive)

### Requirements

- **Functional**: Upload/download files, sync across devices, folder hierarchy, sharing, version history
- **Scale**: 500M files/day, 100M users, 10GB free storage per user
- **Latency**: Upload starts in <500ms, download in <2s
- **Consistency**: Strong consistency within a device, eventual across devices
- **Durability**: 99.999999999% (11 nines)

### File Chunking

Large files are split into chunks for efficient upload and deduplication.

```
  File: 100MB video

  Without chunking:              With chunking (4MB chunks):
  ┌──────────────────┐          ┌──────┐┌──────┐┌──────┐┌──────┐
  │                  │          │Chunk1││Chunk2││Chunk3││ ...  │
  │    100MB file    │          │ 4MB  ││ 4MB  ││ 4MB  ││      │
  │                  │          └──────┘└──────┘└──────┘└──────┘
  └──────────────────┘          25 chunks total

  Benefits:
  - Resume interrupted uploads (only re-upload failed chunk)
  - Deduplication (same chunk across files stored once)
  - Parallel upload (all chunks upload simultaneously)
  - Delta sync (only changed chunks uploaded)
```

### Sync Protocol

```
  ┌─────────────────────────────────────────────────┐
  │              Sync Protocol                        │
  │                                                   │
  │  Device A uploads new file:                       │
  │  1. Split into chunks (4MB each)                 │
  │  2. Hash each chunk (SHA-256)                    │
  │  3. Check server: "Do you have this hash?"       │
  │  4. Server: "Yes" → Skip upload (dedup)          │
  │     Server: "No" → Upload chunk                  │
  │  5. Server creates file metadata                 │
  │  6. Server notifies other devices                │
  │                                                   │
  │  Device B syncs:                                  │
  │  1. Server pushes notification: "new file"       │
  │  2. Device B checks which chunks it needs        │
  │  3. Downloads only missing chunks                │
  │  4. Reassembles file locally                     │
  └─────────────────────────────────────────────────┘
```

### Conflict Resolution

When two devices edit the same file offline:

```
  Device A edits "doc.txt" offline
  Device B edits "doc.txt" offline
  Both come online and sync

  Resolution strategies:
  1. Last-write-wins (simple, may lose data)
  2. Create conflict copy ("doc (Conflict 1).txt")
  3. Merge (for structured data like Google Docs)
  4. Version tree (keep all versions, let user choose)

  Dropbox approach: Conflict copies + version history
  Google Docs approach: Real-time collaborative editing (OT/CRDT)
```

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│              File Storage Architecture                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Client ────▶ Load Balancer ────▶ API Servers           │
│                                      │                   │
│  ┌───────────────────────────────────┼───────────────┐  │
│  │                                   │               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──▼──────┐       │  │
│  │  │ Metadata │  │  Chunk   │  │  Sync   │       │  │
│  │  │ Service  │  │ Storage  │  │ Service │       │  │
│  │  │(MySQL)   │  │ (S3)     │  │         │       │  │
│  │  └──────────┘  └──────────┘  └─────────┘       │  │
│  │                                                  │  │
│  │  Metadata: file_id, owner, path, chunks,         │  │
│  │            versions, sharing permissions          │  │
│  │                                                  │  │
│  │  Chunk Storage: S3/GCS (11 nines durability)    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  Notification: Kafka → Push Service → Device            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Part 2: Video Streaming (YouTube/Netflix)

### Requirements

- **Functional**: Upload videos, transcode, stream with adaptive bitrate, recommendations
- **Scale**: 500 hours of video uploaded per minute, 1B hours watched per day
- **Latency**: Video starts playing in <2s
- **Quality**: Adaptive bitrate (adjust quality based on bandwidth)

### Video Transcoding Pipeline

```
  Upload → Transcode → Store → Distribute → Stream

  ┌─────────────────────────────────────────────────┐
  │           Video Transcoding Pipeline              │
  │                                                   │
  │  Original video (4K, 60fps, 50GB)                │
  │  │                                                │
  │  ▼                                                │
  │  ┌──────────────────────────────────────────┐    │
  │  │  Transcoding Service (parallelized)       │    │
  │  │                                            │    │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
  │  │  │ 4K/60fps │ │ 1080p/30 │ │ 720p/30  │ │    │
  │  │  │ (20Mbps) │ │ (5Mbps)  │ │ (2.5Mbps)│ │    │
  │  │  └──────────┘ └──────────┘ └──────────┘ │    │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
  │  │  │ 480p/30  │ │ 360p/30  │ │ Audio    │ │    │
  │  │  │ (1Mbps)  │ │ (0.5Mbps)│ │ only     │ │    │
  │  │  └──────────┘ └──────────┘ └──────────┘ │    │
  │  └──────────────────────────────────────────┘    │
  │  │                                                │
  │  ▼                                                │
  │  Store all variants in CDN (edge locations)       │
  └─────────────────────────────────────────────────┘
```

### Adaptive Bitrate Streaming (HLS/DASH)

```
  Client bandwidth: 10 Mbps
  │
  ▼
  Player detects bandwidth → selects appropriate quality
  │
  ├── 4K (20Mbps) → Too slow, skip
  ├── 1080p (5Mbps) → Fits, start playing
  ├── 720p (2.5Mbps) → Backup if bandwidth drops
  ├── 480p (1Mbps) → Fallback
  └── 360p (0.5Mbps) → Last resort

  How it works:
  1. Video is split into 2-10 second segments
  2. Each segment is available at multiple qualities
  3. Player downloads segments one at a time
  4. Player switches quality between segments based on bandwidth

  HLS (HTTP Live Streaming): Apple format, .m3u8 playlist
  DASH (Dynamic Adaptive Streaming): Open standard, .mpd manifest
```

### CDN Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Video CDN Architecture                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Origin Server (S3/GCS)                                 │
│  │  All video variants stored here                      │
│  │                                                      │
│  ▼                                                      │
│  Origin Shield (mid-tier)                               │
│  │  Protects origin from direct requests                │
│  │                                                      │
│  ▼                                                      │
│  Edge Servers (10,000+ locations)                       │
│  │  Cache popular videos close to users                 │
│  │  Serve 95%+ of requests                              │
│  │                                                      │
│  ▼                                                      │
│  User's Device                                          │
│  │  Downloads segments, plays video                     │
│  │  Adjusts quality based on bandwidth                  │
│                                                          │
└─────────────────────────────────────────────────────────┘

  Netflix Open Connect:
  - 10,000+ custom servers in ISPs worldwide
  - Pre-positioned based on popularity predictions
  - 95%+ of traffic served from edge
```

### Recommendation System

```
  User watch history + Metadata + Collaborative filtering
  │
  ▼
  ┌─────────────────────────────────────────────────┐
  │  Recommendation Pipeline                         │
  │                                                   │
  │  1. Candidate generation (1000s of videos)       │
  │  - Collaborative filtering (users like you)       │
  │  - Content-based (similar to what you watched)    │
  │                                                   │
  │  2. Ranking (100s of videos)                      │
  │  - ML model predicts engagement                   │
  │  - Features: watch time, completion rate, likes   │
  │                                                   │
  │  3. Filtering (10s of videos)                     │
  │  - Remove already watched                         │
  │  - Remove blocked content                         │
  │  - Diversity constraints                          │
  │                                                   │
  │  4. Presentation (rows of 10-20)                  │
  │  - Group by category                              │
  │  - Personalize row order                          │
  └─────────────────────────────────────────────────┘
```

---

## Design Comparison

| Aspect | File Storage | Video Streaming |
|--------|-------------|-----------------|
| **File size** | 1KB - 10GB | 100MB - 100GB |
| **Upload pattern** | User-initiated | User-initiated |
| **Download pattern** | Random access | Sequential streaming |
| **Deduplication** | Critical (chunk-level) | Less important |
| **CDN** | Optional (for sharing) | Critical (for streaming) |
| **Processing** | Minimal | Transcoding pipeline |

---

## Deep Dive: Dropbox Sync Protocol

Dropbox's sync protocol is one of the most well-documented file sync systems.

### The Magic Pocket Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Dropbox Sync Architecture                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Client-side                                     │   │
│  │  - Filesystem watcher (inotify/FSEvents)        │   │
│  │  - Chunking engine (4MB blocks)                 │   │
│  │  - Local metadata DB (SQLite)                   │   │
│  │  - Deduplication (content-addressable)          │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Block Server                                    │   │
│  │  - Receives chunks from clients                  │   │
│  │  - Deduplicates by content hash                 │   │
│  │  - Stores in Magic Pocket (custom storage)      │   │
│  │  - Replicates across data centers               │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Metadata Server                                 │   │
│  │  - File tree (folder → files → chunks)          │   │
│  │  - Version history (append-only)                │   │
│  │  - Sharing permissions                           │   │
│  │  - Consensus (Paxos) for consistency            │   │
│  └─────────────────────────────────────────────────┘   │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Notification Service                            │   │
│  │  - Long polling / WebSocket                      │   │
│  │  - Push notifications to clients                │   │
│  │  - Delta sync (only changed chunks)             │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Delta Sync

Only changed chunks are transferred, not the entire file.

```
  Original file: [Chunk A][Chunk B][Chunk C][Chunk D]
  
  User edits Chunk C:
  
  Before: [A][B][C_old][D]
  After:  [A][B][C_new][D]
  
  Delta sync: Only upload C_new (4MB instead of 16MB)
  
  Server stores:
  Version 1: [hash_A][hash_B][hash_C_old][hash_D]
  Version 2: [hash_A][hash_B][hash_C_new][hash_D]
  
  Only hash_C_new is new storage. hash_A, hash_B, hash_D are shared.
```

### Content-Addressable Storage

```
  Each chunk is identified by its content hash:
  
  chunk_hash = SHA-256(chunk_content)
  
  Deduplication:
  - User A uploads "report.pdf" → chunks [H1, H2, H3]
  - User B uploads same "report.pdf" → chunks [H1, H2, H3]
  - Server already has H1, H2, H3 → skip upload
  - Both users reference same physical chunks
  
  Storage savings: 5-10x for typical workloads
```

---

## Deep Dive: Video Streaming Details

### Transcoding Formats

```
  ┌─────────────────────────────────────────────────────┐
  │  Video Format Comparison                              │
  │                                                       │
  │  H.264 (AVC):                                        │
  │  - Most widely supported                             │
  │  - Good compression                                   │
  │  - Hardware encoding on most devices                 │
  │                                                       │
  │  H.265 (HEVC):                                       │
  │  - 50% better compression than H.264                 │
  │  - Licensing issues                                  │
  │  - Limited device support                            │
  │                                                       │
  │  AV1:                                                │
  │  - Royalty-free                                       │
  │  - 30% better than H.265                             │
  │  - Slow encoding (improving)                         │
  │  - Future-proof                                      │
  └─────────────────────────────────────────────────────┘
```

### HLS Playlist Structure

```
  Master playlist (master.m3u8):
  #EXTM3U
  #EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080
  1080p/playlist.m3u8
  #EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
  720p/playlist.m3u8
  #EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=854x480
  480p/playlist.m3u8
  
  Quality playlist (1080p/playlist.m3u8):
  #EXTM3U
  #EXTINF:6.0,
  segment0.ts
  #EXTINF:6.0,
  segment1.ts
  #EXTINF:6.0,
  segment2.ts
```

---

## Exercises

### Exercise 1: File Storage Design (25 min)

Design a simplified Google Drive that supports:
- Upload files up to 5GB
- Sync across 3 devices
- Share files with other users
- Version history (last 10 versions)

**Requirements to estimate:**
- 100M users, 10% daily active
- Average file size: 5MB
- 5 files uploaded per user per day

Draw the architecture. How many chunks per file? What's the storage per day?

### Exercise 2: Video Streaming Pipeline (25 min)

Design a video streaming service that:
- Accepts 4K uploads
- Transcodes to 5 qualities (360p to 4K)
- Streams via HLS
- Serves 1M concurrent viewers

**Key decisions:**
- How many transcoding workers do you need?
- How do you handle the CDN?
- What's the storage per hour of video?

### Exercise 3: Conflict Resolution (15 min)

Two users edit the same document offline:
- User A changes paragraph 1
- User B changes paragraph 2

Design a conflict resolution strategy. What happens when both come online? How do you preserve both changes?

---

## Discussion Questions

1. You're designing a file sync system. A user has a 10GB video file and changes 1 second in the middle. How do you minimize the upload size?

   **Model answer**: Use chunking (4MB blocks). Only the changed chunk needs re-upload. With delta sync, the 10GB file becomes a 4MB upload. Content-addressable storage means if the chunk already exists (another user uploaded it), skip upload entirely.

2. Your video streaming service has 1M concurrent viewers. 80% watch the same popular video. How do you optimize CDN usage?

   **Model answer**: Pre-position the popular video at edge locations before the expected spike, and put an origin shield in front of the origin so edge misses collapse into a mid-tier cache rather than hitting storage directly.

   The key insight is that **origin load scales with distinct segments, not with viewers**. 800K people watching the same video request the same segment files, so each segment is fetched from origin at most once per edge location — then served from cache for everyone else. A 2-hour video at 6-second segments across 5 quality levels is only ~6,000 objects. Even with 100 edge locations pulling independently, that is ~600K one-time fetches spread over two hours, and pre-positioning drops it to near zero.

   The remaining 20% (200K viewers) are spread across a long tail of less popular videos. Those *do* miss more often, because unpopular content gets evicted between requests — the tail is where your origin traffic actually comes from, not the hit. Steady-state hit ratio ends up >99% overall, and it is worth being precise about why: the popular video is ~100% cached, and the tail is what pulls the average down.

   **Watch the reasoning trap:** ">99% hit ratio" and "200K streams reach the origin" cannot both be true — 200K of 1M is a 20% miss rate. Viewer count is not request count once a CDN is in the path.

3. Compare Dropbox and Google Drive's sync approaches. What are the trade-offs?

   **Model answer**: Dropbox uses block-level sync (4MB chunks, delta sync, content-addressable storage). Google Drive uses file-level sync (entire file uploaded on change). Dropbox is more efficient for large files; Google Drive is simpler. Google Docs uses real-time collaborative editing (OT/CRDT) for documents, which Dropbox doesn't natively support.

4. Your transcoding pipeline is backed up. Videos are taking 10 hours to process instead of 1 hour. How do you diagnose and fix this?

   **Model answer**: Check: (1) Is the queue depth growing? (2) Are workers failing? (3) Is input video resolution higher than expected? (4) Are workers CPU/GPU bound? Fix: Scale up workers, prioritize shorter videos, use hardware-accelerated transcoding (NVENC), implement adaptive bitrate (skip 4K for low-engagement videos).

5. Design a content-addressable storage system. What happens when two users upload the same file?

   **Model answer**: Hash the file content (SHA-256). If hash exists, create a reference (not a copy). Both users point to the same physical storage. Deduplication ratio for typical workloads: 5-10x. Challenge: finding duplicate chunks requires indexing all hashes. Solution: Bloom filter for fast negative checks, hash index for positive checks.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview (Ch. 6-7) | Book | File storage, video streaming |
| Dropbox Technical Blog | Blog | Sync protocol, chunking, Magic Pocket |
| Netflix Tech Blog | Blog | CDN, transcoding, recommendations |
| YouTube Engineering Blog | Blog | Adaptive bitrate, scale |
| HLS RFC 8216 | Spec | HTTP Live Streaming protocol |

---

**Previous**: [Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md)
**Next**: [Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md)
