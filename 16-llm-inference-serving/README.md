# Module 16: LLM Inference Serving Architecture

> **How to serve LLMs at scale.** LLM inference is fundamentally different from traditional web serving — it's memory-bound, not compute-bound. The KV cache is the bottleneck, and every optimization revolves around managing it efficiently.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 15 | Observability | [../15-observability/](../15-observability/) |
| **Module 16** | **LLM Inference Serving Architecture** | **(current)** |
| Module 17 | RAG System Architecture at Scale | [../17-rag-at-scale/](../17-rag-at-scale/) |

---

## Learning Objectives

- Understand why LLM serving is memory-bound
- Master KV cache management (PagedAttention, RadixAttention)
- Compare batching strategies for throughput optimization
- Evaluate quantization methods for production deployment
- Design GPU clusters for LLM inference

---

## Table of Contents

1. [The LLM Serving Bottleneck](#the-llm-serving-bottleneck)
2. [KV Cache Management](#kv-cache-management)
3. [Batching Strategies](#batching-strategies)
4. [Disaggregated Prefill/Decode Serving](#disaggregated-prefilldecode-serving)
5. [Quantization](#quantization)
6. [Speculative Decoding](#speculative-decoding)
7. [Model Parallelism](#model-parallelism)
8. [GPU Cluster Design](#gpu-cluster-design)
9. [Case Study: How OpenAI Serves GPT-4](#case-study-how-openai-serves-gpt-4)
10. [Framework Comparison](#framework-comparison)
11. [Key References](#key-references)
12. [Practice Exercise](#practice-exercise)
13. [Common Mistakes](#common-mistakes)
14. [Discussion Questions](#discussion-questions)

---

## The LLM Serving Bottleneck

Traditional web servers are **compute-bound** (CPU is the bottleneck). LLM servers are **memory-bound** (GPU memory is the bottleneck).

```
  Traditional Web Server:         LLM Inference Server:

  CPU: ████████████ 95%           GPU Compute: ████░░░░░░ 40%
  RAM: ████░░░░░░░░ 35%           GPU Memory:  ████████████ 95%

  Bottleneck: CPU                 Bottleneck: GPU Memory (KV cache)
  Scale by: Adding CPU            Scale by: Managing memory efficiently
```

### Why Memory Is the Bottleneck

```
  LLaMA-13B inference for ONE sequence:

  Model weights:     ~26 GB (FP16)
  KV cache (2K ctx): ~1.7 GB
  KV cache (8K ctx): ~6.8 GB
  KV cache (32K ctx): ~27 GB (!)

  A single A100 GPU has 80GB memory.
  At 32K context, ONE user's KV cache fills 1/3 of the GPU.

  Conclusion: You can't afford to waste KV cache memory.
```

### Current-Generation Hardware: Blackwell

The A100 numbers above are still the right teaching baseline for the
memory-bottleneck concept, but they're no longer the frontier. NVIDIA's
Blackwell generation (B200) ships with 192GB of HBM3e memory at 8 TB/s of
bandwidth — roughly 4× the inference throughput of the H100, driven
substantially by native FP4 tensor support (half the storage footprint of
FP8, and roughly 2× its throughput where model accuracy holds up at that
precision).

The rack-scale building block is the GB200 NVL72: 72 B200 GPUs plus 36 Grace
CPUs in a single NVLink domain, delivering 720 petaFLOPS of FP4 compute — a
very different node shape than the 4× A100 boxes in the cluster diagram
later in this module. SemiAnalysis's InferenceX benchmarks (April 2026)
measured Blackwell-based systems serving GPT-OSS-120B via TensorRT-LLM at
roughly $0.02 per million tokens at 55 tokens/sec/user — about 4.5× cheaper
than equivalent Hopper (H100)-based systems on the same workload.

> **Caveat:** none of this changes the architecture taught in this module —
> it changes the constants. PagedAttention, continuous batching,
> RadixAttention, and quantization all still apply on Blackwell; the KV
> cache is still the bottleneck, just at a higher ceiling. Hardware access
> is the real constraint: as of mid-2026, Blackwell orders remain
> substantially backordered, so H100/H200 fleets remain the realistic
> capacity-planning baseline for most teams — treat these numbers as where
> the curve is heading, not as what you can provision this quarter.

---

## KV Cache Management

### What Is the KV Cache?

During autoregressive generation, the model computes Key and Value matrices for each token. These are cached to avoid recomputation.

```
  Token generation:

  Step 1: Input "The cat" → Compute K,V for all tokens → Generate "sat"
  Step 2: Input "The cat sat" → Reuse K,V from step 1, compute only for "sat" → Generate "on"
  Step 3: Input "The cat sat on" → Reuse K,V from steps 1-2, compute only for "on" → Generate "the"

  The KV cache stores K,V from all previous tokens.
  Without cache: O(n²) computation
  With cache: O(n) computation per new token
```

### Traditional KV Cache Problem

Traditional serving allocates contiguous GPU memory for each sequence:

```
  GPU Memory:
  ┌────────────────────────────────────────────────────┐
  │ Seq 1: [████████░░░░░░░░] (allocated 10K, used 5K) │ 50% wasted!
  │ Seq 2: [██████░░░░░░░░░░] (allocated 10K, used 3K) │ 70% wasted!
  │ Seq 3: [██░░░░░░░░░░░░░░] (allocated 10K, used 1K) │ 90% wasted!
  │ Free:  [░░░░░░░░░░░░░░░░] (no more room!)          │
  └────────────────────────────────────────────────────┘

  Problem: Pre-allocated blocks waste 60-80% of memory
```

### PagedAttention (vLLM)

PagedAttention borrows from OS virtual memory: KV cache is stored in non-contiguous "pages" (blocks).

```
  GPU Memory (PagedAttention):
  ┌───────────────────────────────────────────────────┐
  │ Page Table:                                       │
  │ Seq 1: [Page 0] → [Page 3] → [Page 7]             │
  │ Seq 2: [Page 1] → [Page 5]                        │
  │ Seq 3: [Page 2] → [Page 4] → [Page 6] → [Page 8]  │
  │                                                   │
  │ Physical Pages:                                   │
  │ [P0:cat] [P1:on] [P2:the] [P3:sat] [P4:is]        │
  │ [P5:big] [P6:red] [P7:and] [P8:fat]               │
  └───────────────────────────────────────────────────┘

  Benefits:
  - No memory waste (allocate only what's used)
  - Dynamic growth (pages added as needed)
  - Copy-on-write (shared prefixes across sequences)
  - 2-4× throughput improvement over naive allocation
```

### RadixAttention (SGLang)

Optimizes for shared prefixes (e.g., same system prompt across requests).

```
  Request 1: [System prompt] + [User question 1]
  Request 2: [System prompt] + [User question 2]
  Request 3: [System prompt] + [User question 3]

  Without RadixAttention:
  3 copies of system prompt in KV cache

  With RadixAttention (prefix tree):
  [System prompt] ──┬── [User question 1]
                    ├── [User question 2]
                    └── [User question 3]

  Only ONE copy of system prompt KV cache!
  Memory savings: proportional to system prompt length
```

---

## Batching Strategies

### Static Batching

```
  Batch size: 32 sequences

  Time 0: Wait for 32 requests → Process all 32 together
  Time 1: Wait for 32 more requests → Process next batch

  Problems:
  - Short sequences wait for long ones (wasted compute)
  - New requests wait for batch to fill
  - GPU utilization: 40-60%
```

### Continuous Batching

New requests join the batch as others complete.

```
  Time 0: [A, B, C, D, E, F, G, H]  (8 sequences)
  Time 1: [A, B, C, D, E, F]  (G, H completed, removed)
  Time 2: [A, B, C, D, E, F, I, J]  (I, J joined)
  Time 3: [A, B, C, I, J]  (D, E, F completed)

  ✓ No waiting for batch to fill
  ✓ Short sequences don't block long ones
  ✓ GPU utilization: 80-95%
  ✓ Now universal across all serving frameworks
```

### PagedAttention + Continuous Batching

```
  ┌───────────────────────────────────────────────────┐
  │  Modern LLM Serving Stack                         │
  │                                                   │
  │  Request Queue                                    │
  │  ┌───┬───┬───┬───┬───┬───┐                        │
  │  │ R1│ R2│ R3│ R4│ R5│ R6│                        │
  │  └───┴───┴───┴───┴───┴───┘                        │
  │       │                                           │
  │       ▼                                           │
  │  ┌────────────────────────────────────────────┐   │
  │  │  Scheduler (Continuous Batching)           │   │
  │  │  - Assigns sequences to GPU blocks         │   │
  │  │  - Manages preemption (swap out long seqs) │   │
  │  │  - Optimizes batch composition             │   │
  │  └────────────────────────────────────────────┘   │
  │       │                                           │
  │       ▼                                           │
  │  ┌───────────────────────────────────────────┐    │
  │  │  GPU Execution                            │    │
  │  │  - PagedAttention for KV cache            │    │
  │  │  - Continuous batching                    │    │
  │  │  - Tensor parallelism across GPUs         │    │
  │  └───────────────────────────────────────────┘    │
  │                                                   │
  └───────────────────────────────────────────────────┘
```

---

## Disaggregated Prefill/Decode Serving

Continuous batching and PagedAttention (above) still assume prefill and
decode share the same GPUs. The next architectural step is to question that
assumption.

### Why Prefill and Decode Fight Each Other

The two phases of generation have opposite hardware profiles:

```
  Prefill (processing the prompt):
    - Computes K/V for every input token at once → large matmuls
    - Bottleneck: GPU compute (FLOPs)

  Decode (generating one token at a time):
    - Reuses cached K/V, computes one new token per step → tiny matmuls
    - Bottleneck: GPU memory bandwidth (moving weights + KV cache per step)
```

Co-locating both phases on the same GPU pool means whichever phase is
momentarily dominant starves the other: a burst of long prompts consumes
the compute budget decode needs to keep tokens flowing, and a burst of long
decode sequences leaves compute idle while memory bandwidth saturates.
Continuous batching schedules around this contention — it can't remove it,
because the two phases want opposite things from the same silicon at the
same time.

### Splitting the GPU Pools

Disaggregated serving assigns prefill and decode to separate, independently
sized GPU pools, connected by a step that transfers the freshly computed KV
cache from the prefill worker to whichever decode worker continues the
sequence:

```
  Request ──▶ Prefill Pool ──▶ KV cache transfer ──▶ Decode Pool ──▶ Tokens
              (compute-heavy)                        (bandwidth-heavy)
```

- **vLLM** moves KV cache between pools through pluggable KV-transfer
  connectors — NIXL and Mooncake are the two in active use.
- **SGLang** exposes disaggregation via a `--disaggregation-mode` flag; a
  router process sits in front of both pools and directs each request to a
  prefill worker and then a decode worker.

### Evidence at Scale

SGLang's own benchmarks give a sense of what this buys, and at what scale it
starts to matter: DeepSeek-R1 served across 96 H100 GPUs, split into a
3-node prefill pool and a 9-node decode pool, and 2.7× higher decode
throughput on NVIDIA GB200 NVL72 clusters versus non-disaggregated serving
of the same model.

> **Caveat:** this is a scale-dependent optimization, not a default. A
> router and a KV-transfer connector are new moving parts with their own
> failure modes, and below roughly 96+ GPUs that operational cost usually
> exceeds the interference it removes. The "vLLM is the default" guidance
> in the Framework Comparison section still holds for teams running a
> handful of GPUs — disaggregate once you can actually measure
> prefill/decode interference capping your throughput, not before.

---

## Quantization

Reduce model size by using lower precision weights.

### Comparison

| Method | Bit Width | Size (70B model) | Speedup | Quality Loss |
|--------|-----------|-------------------|---------|--------------|
| **FP16** (baseline) | 16-bit | 140 GB | 1x | None |
| **GPTQ** | 3-4 bit | 25-35 GB | 3.25x | Minimal |
| **AWQ** | 4-bit | 35 GB | 3x | Minimal |
| **GGUF** | 2-8 bit | 35-140 GB | Varies | Varies |
| **FP8** | 8-bit | 70 GB | 1.5x | Very minimal |

### GPTQ (Post-Training Quantization)

```
  Process:
  1. Use calibration data (128 examples)
  2. Quantize weights layer by layer
  3. Minimize quantization error via Hessian information
  4. Result: 3-4 bit weights with minimal quality loss

  Trade-offs:
  ✓ Significant memory reduction (4× less memory)
  ✓ Significant speedup (3.25× faster inference)
  ✗ Requires calibration data
  ✗ Slight quality degradation on complex reasoning
```

### AWQ (Activation-Aware Weight Quantization)

```
  Key insight: Not all weights are equally important.
  Protect the 1% of "salient" weights that affect output most.

  Process:
  1. Run calibration data through model
  2. Identify salient weights (high activation magnitude)
  3. Keep salient weights at higher precision
  4. Quantize remaining weights aggressively

  Result: 3× speedup with only 1% quality loss (MLSys 2024 Best Paper)
```

### When to Quantize

| Scenario | Recommendation |
|----------|---------------|
| Production serving with cost constraints | Quantize (AWQ or GPTQ) |
| Research / maximum quality | Keep FP16 |
| Edge deployment (mobile, laptop) | GGUF with Q4_K_M |
| Fine-tuning | QLoRA (quantize base, fine-tune adapters) |

---

## Speculative Decoding

Use a small "draft" model to generate candidate tokens, then verify with the large "target" model in parallel.

```
  Traditional (3 forward passes of the LARGE model):
    pass 1 → "The"
    pass 2 → "cat"
    pass 3 → "sat"

  Speculative (1 forward pass of the large model):
    draft  → small model proposes "The cat sat"   (3 cheap passes)
    verify → large model scores all 3 positions in ONE pass
             all accepted → 3 tokens for the price of 1

  Speedup: 2-3× with ZERO quality loss.
  (Verification uses rejection sampling, so the output distribution is
   provably identical to running the large model alone — this is not an
   approximation.)
```

### Architecture

```
  ┌───────────────────────────────────────────────────┐
  │  Speculative Decoding                             │
  │                                                   │
  │  Draft Model (e.g., 1B params)                    │
  │  │                                                │
  │  │ Generate K candidate tokens                    │
  │  │ (fast, ~1ms per token)                         │
  │  ▼                                                │
  │  [The, cat, sat, on, the]                         │
  │                                                   │
  │  Target Model (e.g., 70B params)                  │
  │  │                                                │
  │  │ Verify all K tokens in ONE forward pass        │
  │  │ (same cost as generating 1 token)              │
  │  ▼                                                │
  │  [The✓, cat✓, sat✓, on✗]                          │
  │                                                   │
  │  Result: 3 accepted + 1 correction = 4 tokens     │
  │  from ONE target forward pass.                    │
  │                                                   │
  │  The rejected position isn't wasted — the target  │
  │  already computed its own distribution there, so  │
  │  it emits the right token for free. Everything    │
  │  after the first rejection is discarded.          │
  └───────────────────────────────────────────────────┘
```

### What Determines the Actual Speedup

The headline number rests on one variable: **how often the draft model agrees
with the target.**

```
  Expected tokens per target pass ≈ (1 - α^(K+1)) / (1 - α)

  α = per-token acceptance rate, K = draft length

  α = 0.9, K = 4  →  ~4.1 tokens/pass   (excellent)
  α = 0.7, K = 4  →  ~2.9 tokens/pass   (typical)
  α = 0.4, K = 4  →  ~1.6 tokens/pass   (marginal)
  α = 0.2, K = 4  →  ~1.2 tokens/pass   (draft cost exceeds the gain)
```

| Factor | Effect on α |
|--------|-------------|
| Draft and target from the same model family | Higher — shared tokenizer and training distribution |
| Predictable text (code, boilerplate, fixed formats) | Higher — easy next tokens |
| High sampling temperature | Lower — the target's own sampling diverges from the draft |
| Longer draft length K | Diminishing — later positions rarely survive |

**Practical consequence:** speculative decoding is a **latency** optimization for
low-to-moderate concurrency. Under heavy load, continuous batching already keeps
the GPU saturated, so draft compute competes with real work and the net gain
shrinks — sometimes to nothing. Measure the two together rather than assuming
they compose.

---

## Model Parallelism

When a model is too large for one GPU, split it across multiple GPUs.

### Tensor Parallelism

Split each layer across GPUs.

```
  Layer 1:
  GPU 0: [Weight rows 0-2047]    GPU 1: [Weight rows 2048-4095]
  │                                    │
  └───────────────┬────────────────────┘
                  │
                  ▼
            Layer 1 output

  ✓ Low latency (parallel computation)
  ✓ Fine-grained parallelism
  ✗ High communication overhead (all-reduce after each layer)
```

### Pipeline Parallelism

Split model into stages across GPUs.

```
  GPU 0: Layers 1-10    GPU 1: Layers 11-20    GPU 2: Layers 21-30
  │                         │                         │
  └──▶ Layer 1-10 ──▶ Layer 11-20 ──▶ Layer 21-30 ──▶ Output

  ✓ Lower communication overhead
  ✓ Coarse-grained (easy to implement)
  ✗ Pipeline bubbles (GPUs idle during pipeline fill/drain)
```

### Parallelism Strategy Selection

| Model Size | GPUs | Strategy |
|------------|------|----------|
| <10B | 1 | No parallelism needed |
| 10-30B | 2-4 | Tensor parallelism |
| 30-70B | 4-8 | Tensor + pipeline parallelism |
| >70B | 8+ | Full 3D parallelism (tensor + pipeline + data) |

---

## GPU Cluster Design

```
┌───────────────────────────────────────────────────────────┐
│              LLM Serving GPU Cluster                      │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Load Balancer (L7, routing by model)            │     │
│  └──────────────────────────────────────────────────┘     │
│                         │                                 │
│  ┌──────────────────────┼──────────────────────┐          │
│  │                      │                      │          │
│  ▼                      ▼                      ▼          │
│ ┌────────────┐    ┌────────────┐    ┌─────────────┐       │
│ │ vLLM Node  │    │ vLLM Node  │    │ vLLM Node   │       │
│ │ 4× A100    │    │ 4× A100    │    │ 2× A100     │       │
│ │ 70B, TP=4  │    │ 70B, TP=4  │    │ 8B, TP=1    │       │
│ │ (quality)  │    │ (quality)  │    │ (cheap/fast)│       │
│ └────────────┘    └────────────┘    └─────────────┘       │
│                                                           │
│  Only OPEN-WEIGHT models run on your own nodes. Hosted    │
│  models (GPT-4, Claude, Gemini) are reached over their    │
│  providers' APIs — you cannot self-host them, and the     │
│  router below treats them as a separate upstream.         │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Model Router                                     │    │
│  │  - Simple queries → Small model (7B, cheap)       │    │
│  │  - Complex queries → Large model (70B, expensive) │    │
│  │  - Reasoning tasks → Reasoning model              │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  KV Cache Offloading                              │    │
│  │  - Hot KV cache: GPU memory                       │    │
│  │  - Warm KV cache: CPU memory (NVMe SSD)           │    │
│  │  - Cold KV cache: Disk (for long contexts)        │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Case Study: How OpenAI Serves GPT-4

### Key Design Decisions

1. **Massive GPU clusters**: Tens of thousands of GPUs across multiple data centers. Custom networking (InfiniBand) for tensor parallelism.

2. **KV cache optimization**: Custom implementation beyond PagedAttention. Prefix caching for system prompts shared across millions of requests.

3. **Model routing**: Different models for different use cases. GPT-4o for general use, o1/o3 for reasoning, GPT-4o-mini for cost-sensitive workloads.

4. **Speculative decoding**: Draft models for faster time-to-first-token. Critical for chat UX.

5. **Global load balancing**: Requests routed to the least-loaded data center. Automatic failover if a data center goes down.

---

## Framework Comparison

| Framework | Key Innovation | Best For | Trade-off |
|-----------|---------------|----------|-----------|
| **vLLM** | PagedAttention, continuous batching | General-purpose serving; the default choice | Broadest model support, largest community |
| **SGLang** | RadixAttention (prefix-tree KV reuse) | Workloads with a large shared system prompt, or structured/multi-turn generation | Biggest wins need prefix overlap; narrower model coverage |
| **TensorRT-LLM** | Ahead-of-time compiled kernels, full 3D parallelism | Squeezing maximum throughput from NVIDIA hardware | Per-model compilation step; NVIDIA-only; heaviest ops burden |
| **llama.cpp / GGUF** | Aggressive quantization, CPU and Apple Silicon | Edge, laptops, single-user local inference | Not built for high-concurrency serving |

**How to choose:** start with vLLM. Move to SGLang if your requests share a long
prefix and you can measure the cache hit rate. Reach for TensorRT-LLM only when
you have a fixed model, NVIDIA hardware, and throughput matters enough to pay
the compilation and operational cost.

> Popularity metrics are deliberately omitted — star counts date a document
> within months and say nothing about fit. Check the projects' own benchmarks
> against *your* model and traffic shape before committing.

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| PagedAttention (SOSP 2023) | Paper | KV cache optimization |
| Speculative Decoding (ICML 2023) | Paper | Inference acceleration |
| vLLM Documentation | Docs | Serving framework |
| SGLang Documentation | Docs | Prefix caching |
| NVIDIA TensorRT-LLM | Docs | GPU optimization |
| vLLM Disaggregated Prefill/Decode (Blog) | Blog | KV-transfer connectors (NIXL, Mooncake) |
| SGLang Disaggregation Benchmarks | Blog | Prefill/decode pool scaling results |
| SemiAnalysis InferenceX Benchmarks (2026) | Benchmark | Cross-hardware inference cost/throughput |

---

## Practice Exercise

**25-minute design**: Design an LLM serving system:

- 1000 queries/second
- Average response: 200 tokens
- Must support 8K context window
- Cost budget: $10K/month

**Key decisions**:
1. How many GPUs do you need?
2. Which serving framework would you use?
3. What batching strategy would you implement?
4. How do you handle KV cache memory?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **Sizing GPUs from model weights alone** | The KV cache is the variable cost: 13B weights are 26GB, but 32K context adds ~27GB *per sequence* | Budget weights + (KV per token × context × concurrency) |
| **Planning capacity from average context length** | Concurrency is bounded by the *long* requests, and the scheduler preempts under memory pressure | Size for the p95 context you actually serve |
| **Assuming you can self-host GPT-4 or Claude** | They are API-only; no weights exist to deploy | Open-weight models on your own nodes; hosted models as a separate upstream |
| **Static batching in production** | Short requests wait for the longest in the batch; utilization sits at 40-60% | Continuous batching — universal in modern servers |
| **Quantizing before measuring** | You trade quality for memory you may not need, and the loss is task-dependent | Establish an FP16 baseline on *your* evals, then compare |
| **Treating all quantization as equivalent** | 4-bit weight-only, FP8, and 2-bit GGUF have very different quality/speed profiles | Match the method to the constraint; benchmark on your workload |
| **Expecting speculative decoding to always help** | The gain scales with draft acceptance rate and competes with batching for GPU time | Measure acceptance; expect little benefit at high concurrency |
| **Tensor parallelism across nodes** | Every layer needs an all-reduce; without NVLink/InfiniBand, interconnect dominates | TP within a node, pipeline parallelism across nodes |
| **Reaching for disaggregated prefill/decode by default** | The router and KV-transfer connector are new failure modes that only pay off once prefill/decode interference is actually capping throughput | Stay on continuous batching below ~96 GPUs; disaggregate once you can measure the interference |
| **One latency SLO for the whole request** | TTFT (prefill) and inter-token latency have different causes and different fixes | Track TTFT and TPOT separately |
| **Ignoring prefix cache hit rate** | A shared system prompt recomputed per request is pure waste | Measure it; if prefixes overlap heavily, prefix caching is the biggest single win |

---

## Discussion Questions

1. Why is LLM inference memory-bound rather than compute-bound? What implications does this have for system design?

2. Explain PagedAttention to a junior engineer. How does it improve throughput?

3. You're designing an LLM serving system for a chat application. Users send 1000 messages/second. The average response is 200 tokens. How many GPUs do you need, and how would you configure them?

4. Compare speculative decoding with continuous batching. Can they be combined?

5. You're choosing between vLLM and SGLang for your deployment. Your workload has many requests sharing the same system prompt. Which would you choose and why?

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 03: Caching Strategies](../03-caching/README.md) | KV cache management (PagedAttention, RadixAttention) is a caching and eviction problem applied to GPU memory instead of application data |
| [Module 04: Load Balancing and Networking](../04-load-balancing/README.md) | The GPU cluster's model router and cross-datacenter failover extend Module 04's L7 routing patterns to route by model instead of by endpoint |
| [Module 08: Distributed Systems Deep Dive](../08-distributed-systems/README.md) | Tensor parallelism, pipeline parallelism, and disaggregated prefill/decode all partition compute and state across GPUs and nodes — the same trade-offs as any distributed system |
| [Module 19: Production AI System Architecture](../19-production-ai-system/README.md) | Inference serving is the compute layer production AI systems are built on, alongside RAG and agents |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│             LLM Inference Serving — Key Takeaways              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Memory is the bottleneck, not compute — budget the KV cache│
│     like a scarce resource, because it runs out first          │
│  2. PagedAttention ended pre-allocated contiguous KV blocks —  │
│     page GPU memory the way an OS pages RAM                    │
│  3. Continuous batching is not optional — static batching      │
│     leaves 40-60% of the GPU idle waiting on the slowest       │
│     sequence                                                   │
│  4. Quantize after you measure, not before — an unevaluated    │
│     4-bit model is a guess, not a decision                     │
│  5. Speculative decoding buys latency, not throughput — its    │
│     gains shrink toward nothing under heavy concurrent load    │
│  6. Tensor parallelism needs NVLink or InfiniBand — cross a    │
│     slow interconnect and the all-reduce eats the speedup      │
│  7. Disaggregated prefill/decode is a scale unlock, not a      │
│     default — earn it by measuring interference above roughly  │
│     96 GPUs                                                    │
│  8. Blackwell raises the ceiling, not the architecture —       │
│     PagedAttention, RadixAttention, and quantization all still │
│     apply, just cheaper and faster                             │
│  9. You cannot self-host GPT-4 or Claude — design your router  │
│     around hosted APIs for closed models and your own fleet for│
│     open-weight ones                                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 15: Observability](../15-observability/README.md)

**Next:** [Module 17: RAG System Architecture at Scale](../17-rag-at-scale/README.md)

---

*Module 16 of 19 in the System Design Playground*
