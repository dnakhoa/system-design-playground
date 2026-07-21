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

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| System Design Interview (Ch. 6-7) | Book | File storage, video streaming |
| Dropbox Technical Blog | Blog | Sync protocol, chunking |
| Netflix Tech Blog | Blog | CDN, transcoding, recommendations |
| YouTube Engineering Blog | Blog | Adaptive bitrate, scale |

---

**Previous**: [Design Case — Chat System and News Feed](../10-case-chat-newsfeed/README.md)
**Next**: [Design Case — Payment System and E-commerce](../12-case-payment-ecommerce/README.md)
