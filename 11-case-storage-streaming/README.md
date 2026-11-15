# Module 11: Design Case — Distributed File Storage and Video Streaming

> **Storage-intensive systems.** These systems test your ability to handle large files, efficient storage, content delivery, and media processing pipelines.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 10 | Design Case — Chat System and News Feed | [../10-case-chat-newsfeed/](../10-case-chat-newsfeed/) |
| **Module 11** | **Design Case — Distributed File Storage and Video Streaming** | **(current)** |
| Module 12 | Design Case — Payment System and E-commerce | [../12-case-payment-ecommerce/](../12-case-payment-ecommerce/) |

---

## Learning Objectives

- Design a distributed file storage system (Dropbox/Google Drive)
- Design a video streaming platform (YouTube/Netflix)
- Implement chunking, deduplication, and sync protocols
- Design transcoding pipelines and adaptive bitrate streaming
- Upload and serve large objects with presigned URLs and multipart uploads, and choose between replication and erasure coding

---

## Table of Contents

1. [Part 1: Distributed File Storage (Dropbox/Google Drive)](#part-1-distributed-file-storage-dropboxgoogle-drive)
2. [Part 2: Video Streaming (YouTube/Netflix)](#part-2-video-streaming-youtubenetflix)
3. [Design Comparison](#design-comparison)
4. [Deep Dive: Dropbox Sync Protocol](#deep-dive-dropbox-sync-protocol)
5. [Deep Dive: Video Streaming Details](#deep-dive-video-streaming-details)
6. [Deep Dive: Large Objects — Uploads, Downloads, and Durability](#deep-dive-large-objects--uploads-downloads-and-durability)
7. [Practice Exercises](#practice-exercises)
8. [Common Mistakes](#common-mistakes)
9. [Discussion Questions](#discussion-questions)
10. [Key References](#key-references)

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
  ┌───────────────────────────────────────────────────┐
  │              Sync Protocol                        │
  │                                                   │
  │  Device A uploads new file:                       │
  │  1. Split into chunks (4MB each)                  │
  │  2. Hash each chunk (SHA-256)                     │
  │  3. Check server: "Do you have this hash?"        │
  │  4. Server: "Yes" → Skip upload (dedup)           │
  │     Server: "No" → Upload chunk                   │
  │  5. Server creates file metadata                  │
  │  6. Server notifies other devices                 │
  │                                                   │
  │  Device B syncs:                                  │
  │  1. Server pushes notification: "new file"        │
  │  2. Device B checks which chunks it needs         │
  │  3. Downloads only missing chunks                 │
  │  4. Reassembles file locally                      │
  └───────────────────────────────────────────────────┘
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
┌───────────────────────────────────────────────────────────┐
│              File Storage Architecture                    │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Client ────▶ Load Balancer ────▶ API Servers             │
│                                      │                    │
│  ┌───────────────────────────────────┼───────────────┐    │
│  │                                   │               │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──▼──────┐       │       │
│  │  │ Metadata │  │  Chunk   │  │  Sync   │       │       │
│  │  │ Service  │  │ Storage  │  │ Service │       │       │
│  │  │(MySQL)   │  │ (S3)     │  │         │       │       │
│  │  └──────────┘  └──────────┘  └─────────┘       │       │
│  │                                                  │     │
│  │  Metadata: file_id, owner, path, chunks,         │     │
│  │            versions, sharing permissions          │    │
│  │                                                  │     │
│  │  Chunk Storage: S3/GCS (11 nines durability)    │      │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  Notification: Kafka → Push Service → Device              │
│                                                           │
└───────────────────────────────────────────────────────────┘
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

  ┌────────────────────────────────────────────────────┐
  │           Video Transcoding Pipeline               │
  │                                                    │
  │  Original video (4K, 60fps, 50GB)                  │
  │  │                                                 │
  │  ▼                                                 │
  │  ┌────────────────────────────────────────────┐    │
  │  │  Transcoding Service (parallelized)        │    │
  │  │                                            │    │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │    │
  │  │  │ 4K/60fps │ │ 1080p/30 │ │ 720p/30  │    │    │
  │  │  │ (20Mbps) │ │ (5Mbps)  │ │ (2.5Mbps)│    │    │
  │  │  └──────────┘ └──────────┘ └──────────┘    │    │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │    │
  │  │  │ 480p/30  │ │ 360p/30  │ │ Audio    │    │    │
  │  │  │ (1Mbps)  │ │ (0.5Mbps)│ │ only     │    │    │
  │  │  └──────────┘ └──────────┘ └──────────┘    │    │
  │  └────────────────────────────────────────────┘    │
  │  │                                                 │
  │  ▼                                                 │
  │  Store all variants in CDN (edge locations)        │
  └────────────────────────────────────────────────────┘
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
┌──────────────────────────────────────────────────────────┐
│                Video CDN Architecture                    │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Origin Server (S3/GCS)                                  │
│  │  All video variants stored here                       │
│  │                                                       │
│  ▼                                                       │
│  Origin Shield (mid-tier)                                │
│  │  Protects origin from direct requests                 │
│  │                                                       │
│  ▼                                                       │
│  Edge Servers (10,000+ locations)                        │
│  │  Cache popular videos close to users                  │
│  │  Serve 95%+ of requests                               │
│  │                                                       │
│  ▼                                                       │
│  User's Device                                           │
│  │  Downloads segments, plays video                      │
│  │  Adjusts quality based on bandwidth                   │
│                                                          │
└──────────────────────────────────────────────────────────┘

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
  ┌───────────────────────────────────────────────────┐
  │  Recommendation Pipeline                          │
  │                                                   │
  │  1. Candidate generation (1000s of videos)        │
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
  └───────────────────────────────────────────────────┘
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
┌───────────────────────────────────────────────────────────┐
│              Dropbox Sync Architecture                    │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Client-side                                     │     │
│  │  - Filesystem watcher (inotify/FSEvents)         │     │
│  │  - Chunking engine (4MB blocks)                  │     │
│  │  - Local metadata DB (SQLite)                    │     │
│  │  - Deduplication (content-addressable)           │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Block Server                                    │     │
│  │  - Receives chunks from clients                  │     │
│  │  - Deduplicates by content hash                  │     │
│  │  - Stores in Magic Pocket (custom storage)       │     │
│  │  - Replicates across data centers                │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Metadata Server                                 │     │
│  │  - File tree (folder → files → chunks)           │     │
│  │  - Version history (append-only)                 │     │
│  │  - Sharing permissions                           │     │
│  │  - Consensus (Paxos) for consistency             │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│                         ▼                                 │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Notification Service                            │     │
│  │  - Long polling / WebSocket                      │     │
│  │  - Push notifications to clients                 │     │
│  │  - Delta sync (only changed chunks)              │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
└───────────────────────────────────────────────────────────┘
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
  ┌───────────────────────────────────────────────────────┐
  │  Video Format Comparison                              │
  │                                                       │
  │  H.264 (AVC):                                         │
  │  - Most widely supported                              │
  │  - Good compression                                   │
  │  - Hardware encoding on most devices                  │
  │                                                       │
  │  H.265 (HEVC):                                        │
  │  - 50% better compression than H.264                  │
  │  - Licensing issues                                   │
  │  - Limited device support                             │
  │                                                       │
  │  AV1:                                                 │
  │  - Royalty-free                                       │
  │  - 30% better than H.265                              │
  │  - Slow encoding (improving)                          │
  │  - Future-proof                                       │
  └───────────────────────────────────────────────────────┘
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

## Deep Dive: Large Objects — Uploads, Downloads, and Durability

### Upload Directly to Object Storage

Routing a 4 GB video through your application servers ties up a connection and
a worker for minutes, and multiplies bandwidth costs. Instead, the app server
hands out permission and gets out of the way:

```
  1. client ──▶ API: "I want to upload video.mp4, 4 GB"
                API: create metadata row (status = 'pending'),
                     return a presigned URL for key uploads/u42/abc123
  2. client ──▶ object storage: PUT bytes directly (or multipart, below)
  3. object storage ──▶ event: "object created: uploads/u42/abc123"
  4. worker: verify size and type, virus-scan, start transcoding;
             metadata status = 'ready'
```

A **presigned URL** is a URL signed with the server's credentials that grants
one operation (PUT to this key, or GET of this object) until it expires. S3's
signature version 4 allows at most 7 days, but minutes are the right default.
Restrict what it allows: a fixed key the server chose (never a client-supplied
path), and where supported, an exact content type and a maximum content length.

Two clean-up rules follow from the flow: a background job deletes `pending`
rows (and their objects) that never completed, and a bucket lifecycle rule
aborts incomplete multipart uploads after a few days. **Parts of an abandoned
multipart upload are stored, and billed, until aborted.**

### Multipart and Resumable Uploads

Large objects are uploaded in independent parts, then assembled with a final
"complete" call. For S3:

| Limit | Value |
|-------|-------|
| Single `PUT` | Up to 5 GB |
| Part size | 5 MiB to 5 GiB (the last part may be smaller) |
| Parts per upload | Up to 10,000 |
| Maximum object size | 48.8 TiB (10,000 × 5 GiB) |

Parts upload in parallel, which fills a fast link that one TCP stream can't,
and each part is retried on its own. A phone that loses signal at 80% asks the
service which parts already arrived and sends only the rest. Choose the part
size from the object size: a 200 GB file needs parts of at least 20 MB to stay
under 10,000 parts. Include a checksum per part so corruption is caught
per part rather than after the whole upload.

The same idea, done by the client instead of the storage service, is the
[chunking](#file-chunking) that sync clients like Dropbox use.

### Downloads

Serve public objects through a CDN, and private ones with short-lived presigned
`GET` URLs (or signed CDN URLs/cookies), so your servers again never stream
bytes. Support HTTP **range requests**: video players, resumable downloads and
parallel download tools all fetch byte ranges rather than whole files.

### Durability: Replication vs Erasure Coding

Storing three full copies costs 3× the raw storage. **Erasure coding**
(Reed-Solomon) splits an object into *k* data fragments, computes *m* parity
fragments, and can rebuild the object from any *k* of the *k + m*:

```python
"""Replication vs erasure coding: storage overhead and chance of losing an object."""

from math import comb

# Chance that one disk fails before a lost fragment is rebuilt:
# 2% annual failure rate, 1-day repair window, failures independent.
p = 0.02 / 365


def loss_probability(total: int, tolerated: int) -> float:
    """P(more than `tolerated` of `total` fragments fail in one repair window)."""
    return sum(comb(total, k) * p**k * (1 - p)**(total - k)
               for k in range(tolerated + 1, total + 1))


schemes = [("3x replication", 1, 2),          # 1 data fragment + 2 copies
           ("RS(6,3) erasure code", 6, 3),    # 6 data + 3 parity fragments
           ("RS(10,4) erasure code", 10, 4)]
print(f"{'scheme':<22}{'storage':>9}{'survives':>10}   P(loss) per repair window")
for name, data, parity in schemes:
    overhead = (data + parity) / data
    print(f"{name:<22}{overhead:>8.1f}x{parity:>6} lost   {loss_probability(data + parity, parity):.1e}")
```

```
scheme                  storage  survives   P(loss) per repair window
3x replication             3.0x     2 lost   1.6e-13
RS(6,3) erasure code       1.5x     3 lost   1.1e-15
RS(10,4) erasure code      1.4x     4 lost   9.9e-19
```

Erasure coding is both cheaper and, under this simple model, more durable,
because it survives more simultaneous losses. HDFS ships RS(6,3) as a standard
policy, and Facebook's f4 warm-BLOB store used RS(10,4). The costs are why hot
data is often still replicated:

- **Repair is expensive**: rebuilding one lost fragment reads *k* others over
  the network, not one copy.
- **Small objects and hot reads suffer**: a read may touch several servers,
  and every write pays the encoding CPU.

The model's biggest assumption is *independent* failures. Real data loss comes
from correlated ones (a rack's power, a bad firmware batch, a whole zone), so
fragments must be spread across failure domains, and repair speed matters as
much as the coding scheme, as [Module 01](../01-fundamentals/README.md#durability)
explains.

---

## Practice Exercises

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

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Proxying uploads through application servers** | Workers and bandwidth are tied up for minutes per large file | Presigned URLs: the client uploads straight to object storage |
| **Never aborting incomplete multipart uploads** | Abandoned parts stay stored and billed indefinitely | A bucket lifecycle rule that aborts incomplete uploads after a few days |
| **Confusing viewer count with origin requests** | 800K viewers of one video fetch the *same* segments; the CDN collapses them into one origin pull per edge | Size origin load by distinct objects, not concurrent users |
| **Storing files as single blobs** | A failed upload restarts from zero, and a one-byte edit re-uploads gigabytes | Fixed-size chunks (~4MB) with per-chunk hashes |
| **Hashing whole files for deduplication** | Any change alters the whole-file hash, so nothing dedupes | Content-address each *chunk*; identical chunks dedupe across files and users |
| **Metadata in the same store as chunk data** | Access patterns are opposite: metadata is small/transactional, chunks are large/immutable | Metadata in a database, chunks in object storage, referenced by hash |
| **Last-write-wins for offline file edits** | One device's work vanishes with no trace | Conflict copies (Dropbox) or CRDT/OT merge (Docs) — never silent discard |
| **Transcoding whole files serially** | A 4K feature blocks the queue for hours and restarts from scratch on failure | Split into segments, transcode in parallel, reassemble; retry per segment |
| **One bitrate per video** | Mobile users buffer; fast connections get needlessly poor quality | Adaptive bitrate ladder plus HLS/DASH manifests |
| **Segments too long or too short** | Long segments make quality switches sluggish; short ones multiply request overhead | 2-6 seconds is the practical range |
| **Serving video from the origin** | Bandwidth cost and latency both become untenable | CDN, with origin shield behind it and popular titles pre-positioned |
| **Ignoring egress cost in the design** | At video scale, bandwidth dominates the bill — often above compute and storage | Model egress explicitly; it drives CDN and peering decisions |

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


6. Users upload videos up to 50 GB from phones on unreliable networks. Today uploads go through your API servers and about 30% of large uploads fail. Redesign the upload path.

   **Model answer**: Take the API servers out of the data path. The client asks the API for an upload; the API creates a `pending` metadata row, starts a multipart upload on a server-chosen key, and returns presigned URLs for the parts (generated in batches as the upload progresses, each valid for minutes). The client uploads parts of, say, 64 MB in parallel, each with a checksum, and retries failed parts individually. After a dropped connection it asks which parts already arrived and sends only the rest. The client then calls "complete", and the storage event triggers validation and transcoding. Add a sweeper for `pending` uploads that never complete and a lifecycle rule that aborts incomplete multipart uploads. Failure is now per part rather than per file, so on unreliable networks most uploads can finish.
---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview (Ch. 6-7) | Book | File storage, video streaming |
| Dropbox Technical Blog | Blog | Sync protocol, chunking, Magic Pocket |
| Netflix Tech Blog | Blog | CDN, transcoding, recommendations |
| YouTube Engineering Blog | Blog | Adaptive bitrate, scale |
| HLS RFC 8216 | Spec | HTTP Live Streaming protocol |
| [Amazon S3: multipart upload limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html) | Docs | Part sizes, part counts, maximum object size |
| "f4: Facebook's Warm BLOB Storage System" (OSDI 2014) | Paper | Moving warm data from replication to Reed-Solomon (10,4) |

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 02: Databases and Storage](../02-databases-storage/README.md) | Metadata services and chunk-storage durability build on the storage engine and replication trade-offs covered there |
| [Module 03: Caching Strategies](../03-caching/README.md) | The CDN's origin-shield-plus-edge-cache design is a direct application of cache hierarchies and hit-ratio reasoning |
| [Module 05: Asynchronous Systems and Message Queues](../05-async-systems/README.md) | The Kafka-backed notification service that pushes sync events to devices is a concrete message-queue use case |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Paxos-based metadata consensus and the strong-within-device/eventual-across-devices model draw on the consistency models covered there |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│            File Storage & Streaming — Key Takeaways            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Chunk everything — fixed-size blocks, not whole files, are │
│     what make resumable uploads, delta sync, and dedup possible│
│     at the same time                                           │
│  2. Hash the chunk, not the file — whole-file hashes break the │
│     moment one byte changes, so content-addressable storage has│
│     to live at the chunk level                                 │
│  3. Metadata and blob data want different homes — small and    │
│     transactional versus large and immutable — don't force them│
│     into the same store                                        │
│  4. Never let "last write wins" silently discard a user's work │
│     — conflict copies or CRDT/OT merges, no exceptions         │
│  5. Viewer count is not origin request count — a CDN turns 800K│
│     concurrent viewers of one video into a handful of origin   │
│     fetches                                                    │
│  6. Ship a bitrate ladder, not a single quality — let the      │
│     player adapt to real bandwidth instead of guessing once at │
│     upload time                                                │
│  7. Transcode in parallel segments — a serial per-file pipeline│
│     means one slow 4K upload backs up the queue for everyone   │
│  8. At streaming scale, egress bandwidth is often the line item│
│     that blows the budget — model it before you model compute  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 10: Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md)

**Next:** [Module 12: Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md)

---

*Module 11 of 26 in the System Design Playground*
