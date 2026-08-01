# Module 16: LLM Inference Serving Architecture

> **How to serve LLMs at scale.** LLM inference is fundamentally different from traditional web serving — it's memory-bound, not compute-bound. The KV cache is the bottleneck, and every optimization revolves around managing it efficiently.

## Learning Objectives

- Understand why LLM serving is memory-bound
- Master KV cache management (PagedAttention, RadixAttention)
- Compare batching strategies for throughput optimization
- Evaluate quantization methods for production deployment
- Design GPU clusters for LLM inference

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

**Previous**: [Observability](../15-observability/README.md)
**Next**: [RAG System Architecture at Scale](../17-rag-at-scale/README.md)

