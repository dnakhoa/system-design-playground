# Module 18: Agent System Architecture

> **Designing autonomous LLM agent systems.** An agent is not just an LLM with tools — it's a system with planning, execution, memory, and guardrails. The harness (not the model) is the design surface.

## Navigation

| Module | Title | Link |
|--------|-------|------|
| Module 17 | RAG System Architecture at Scale | [../17-rag-at-scale/](../17-rag-at-scale/) |
| **Module 18** | **Agent System Architecture** | **(current)** |
| Module 19 | Production AI System Architecture | [../19-production-ai-system/](../19-production-ai-system/) |

---

## Learning Objectives

- Understand the Agent = Model + Harness architecture
- Implement the ReAct planning pattern
- Design multi-agent orchestration systems
- Apply tool- and agent-interoperability standards (MCP, A2A) where they earn their keep
- Implement state management and durable execution
- Design cost control mechanisms for agents
- Evaluate agents on trajectory, not just final-answer accuracy

---

## Table of Contents

1. [Agent = Model + Harness](#agent--model--harness)
2. [The ReAct Pattern](#the-react-pattern)
3. [Six Middleware Concerns](#six-middleware-concerns)
4. [Tool Standardization: MCP](#tool-standardization-mcp)
5. [Multi-Agent Orchestration](#multi-agent-orchestration)
6. [Agent-to-Agent Communication: A2A](#agent-to-agent-communication-a2a)
7. [State Management](#state-management)
8. [Cost Control](#cost-control)
9. [Evaluating Agents](#evaluating-agents)
10. [Case Study: Claude Code Architecture](#case-study-claude-code-architecture)
11. [Key References](#key-references)
12. [Practice Exercise](#practice-exercise)
13. [Common Mistakes](#common-mistakes)
14. [Discussion Questions](#discussion-questions)

---

## Agent = Model + Harness

The modern mental model: the harness is what makes agents reliable and production-ready.

```
┌───────────────────────────────────────────────────────────┐
│                    Agent Architecture                     │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  HARNESS (the design surface)                     │    │
│  │                                                   │    │
│  │  ┌───────────┐  ┌──────────┐  ┌──────────────┐    │    │
│  │  │  Prompt   │  │  Tools   │  │  Middleware  │    │    │
│  │  │  (system  │  │  (APIs,  │  │  (guardrails,│    │    │
│  │  │   prompt, │  │   code,  │  │   memory,    │    │    │
│  │  │   context)│  │   search)│  │   routing)   │    │    │
│  │  └───────────┘  └──────────┘  └──────────────┘    │    │
│  │                                                   │    │
│  └───────────────────────────────────────────────────┘    │
│                         │                                 │
│                         ▼                                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  MODEL (the LLM)                                  │    │
│  │  - Reasoning                                      │    │
│  │  - Planning                                       │    │
│  │  - Tool selection                                 │    │
│  │  - Response generation                            │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘

  Key insight: You don't change the model. You change the harness.
  Better prompts, better tools, better middleware = better agent.
```

---

## The ReAct Pattern

ReAct (Reasoning + Acting) interleaves thinking with action.

```
┌───────────────────────────────────────────────────────────┐
│                    ReAct Loop                             │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  User: "What's the weather in Tokyo and New York?"        │
│                                                           │
│  Thought: I need to check weather for two cities.         │
│  I'll call the weather API for each.                      │
│                                                           │
│  Action: get_weather(city="Tokyo")                        │
│  Observation: 28°C, sunny                                 │
│                                                           │
│  Thought: Got Tokyo. Now I need New York.                 │
│                                                           │
│  Action: get_weather(city="New York")                     │
│  Observation: 22°C, cloudy                                │
│                                                           │
│  Thought: I have both results. Let me formulate the       │
│  final answer.                                            │
│                                                           │
│  Answer: Tokyo is 28°C and sunny. New York is 22°C        │
│  and cloudy.                                              │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### ReAct vs Other Patterns

| Pattern | Description | Best For |
|---------|-------------|----------|
| **ReAct** | Interleave reasoning + actions | Most agent tasks |
| **Plan-and-Execute** | Plan all steps first, then execute | Complex multi-step tasks |
| **Chain-of-Thought** | Reason step-by-step without tools | Pure reasoning tasks |
| **Reflexion** | Self-reflect on mistakes and retry | Tasks requiring self-correction |

---

## Six Middleware Concerns

Production agents need six layers of middleware.

```
┌────────────────────────────────────────────────────────────┐
│              Agent Middleware Stack                        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. EXECUTION ENVIRONMENT                                  │
│     - Sandboxed code execution                             │
│     - Tool access control                                  │
│     - Resource limits (CPU, memory, time)                  │
│                                                            │
│  2. CONTEXT MANAGEMENT                                     │
│     - Context window budgeting                             │
│     - Observation masking (compress tool outputs)          │
│     - Summarization of long conversations                  │
│                                                            │
│  3. PLANNING & DELEGATION                                  │
│     - Task decomposition                                   │
│     - Subagent spawning                                    │
│     - Parallel execution                                   │
│                                                            │
│  4. FAULT TOLERANCE                                        │
│     - Retry with backoff                                   │
│     - Error recovery (feed errors back to LLM)             │
│     - Checkpointing (resume from last good state)          │
│                                                            │
│  5. GUARDRAILS                                             │
│     - Input validation (prompt injection detection)        │
│     - Output filtering (PII, harmful content)              │
│     - Tool call validation                                 │
│                                                            │
│  6. HUMAN-IN-THE-LOOP                                      │
│     - Approval for irreversible actions                    │
│     - Steering (user can redirect agent)                   │
│     - Escalation (agent asks for help)                     │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Tool Standardization: MCP

The "Tools" box in the harness diagram above used to mean a pile of hand-written
API wrappers, one per integration, N agents × M tools = N×M bespoke integrations.
The **Model Context Protocol (MCP)** collapses that to N + M: any MCP-speaking
agent can call any MCP-speaking tool server without custom glue code.

```
  BEFORE MCP — every agent × every tool needs its own adapter

    Agent A ──▶ custom code ──▶ Search API
    Agent A ──▶ custom code ──▶ File System
    Agent A ──▶ custom code ──▶ Database
    Agent B ──▶ custom code ──▶ Search API
    Agent B ──▶ custom code ──▶ File System
    Agent B ──▶ custom code ──▶ Database
    (3 agents × 3 tools = 9 bespoke integrations)

  AFTER MCP — one schema-based protocol in the middle

    Agent A ──╮              ╭──▶ Search MCP Server
    Agent B ──┼──▶  MCP  ────┼──▶ File System MCP Server
    Agent C ──╯              ╰──▶ Database MCP Server
    (3 agents + 3 tool servers, no per-pair adapters)
```

MCP servers expose **tools** (callable functions with a JSON schema), **resources**
(readable data, like files or query results), and **prompts** (reusable templates)
over a standard transport (stdio for local processes, HTTP+SSE for remote ones).
The harness discovers what's available at connection time instead of hardcoding it.

Adoption has been fast: MCP shipped from Anthropic in November 2024, crossed
100,000 monthly SDK downloads within weeks, and reached 97 million monthly SDK
downloads by February 2026 — with every major lab (Anthropic, OpenAI, Google,
Microsoft, Amazon) shipping MCP clients or servers. In December 2025 it moved to
neutral governance under the Linux Foundation's new **Agentic AI Foundation
(AAIF)**, the same body that now stewards A2A (below).

> **Caveat: a protocol is not a trust boundary.** MCP standardizes *how* a tool
> is discovered and invoked — it says nothing about whether the tool's output is
> safe to feed back into the model. A malicious or compromised MCP server can
> return attacker-controlled text just as easily as a scraped web page can. Apply
> the same rule as everywhere else in this module: **never grant fetched content
> authority** just because it arrived over a standard protocol instead of a
> hand-rolled one.

---

## Multi-Agent Orchestration

### Subagent Delegation

The dominant pattern: main agent spawns ephemeral child agents.

```
┌───────────────────────────────────────────────────────────┐
│              Subagent Delegation Pattern                  │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Main Agent                                               │
│  │                                                        │
│  ├──▶ Spawn Subagent A (research task)                    │
│  │    │                                                   │
│  │    │  Isolated context window                          │
│  │    │  Own tool access                                  │
│  │    │  Fresh system prompt                              │
│  │    │                                                   │
│  │    └──▶ Return: "Research findings..."                 │
│  │                                                        │
│  ├──▶ Spawn Subagent B (code writing task)                │
│  │    │                                                   │
│  │    └──▶ Return: "Code implementation..."               │
│  │                                                        │
│  └──▶ Synthesize results → Final answer                   │
│                                                           │
│  Benefits:                                                │
│  - Fresh context (no pollution from parent)               │
│  - Autonomous execution (no micromanagement)              │
│  - Parallel subagents (independent tasks)                 │
│  - Stateless messaging (fire-and-forget)                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Orchestration Patterns

```
  Supervisor Pattern:
  ┌───────────────────────────────────────────────┐
  │  Supervisor Agent                             │
  │  │                                            │
  │  ├── Worker A (research)                      │
  │  ├── Worker B (analysis)                      │
  │  └── Worker C (writing)                       │
  │                                               │
  │  Supervisor assigns tasks, collects results   │
  └───────────────────────────────────────────────┘

  Swarm Pattern:
  ┌───────────────────────────────────────────────┐
  │  Agent A ◄──────▶ Agent B                     │
  │     │                  │                      │
  │     └──────▶ Agent C ◄┘                       │
  │                                               │
  │  Agents communicate directly, no central      │
  │  coordinator. Emergent behavior.              │
  └───────────────────────────────────────────────┘

  Pipeline Pattern:
  ┌───────────────────────────────────────────────┐
  │  Agent A ──▶ Agent B ──▶ Agent C ──▶ Output   │
  │  (research)  (analysis)  (writing)            │
  │                                               │
  │  Sequential, each agent builds on previous    │
  └───────────────────────────────────────────────┘
```

---

## Agent-to-Agent Communication: A2A

MCP solves agent → tool. A shipping product usually also needs agent → agent —
often across a vendor or framework boundary, where "just call the function"
isn't available. That's what the **Agent2Agent protocol (A2A)** standardizes:
peer discovery, task delegation, and streaming results between agents that
weren't built on the same SDK.

| | MCP | A2A |
|---|---|---|
| **Connects** | Agent ↔ tool | Agent ↔ agent |
| **Direction** | One-way invoke-and-return | Peer-to-peer, long-running |
| **Discovery** | Tool schema at connection time | "Agent Card" describing capabilities |
| **Shape of a call** | Function call with typed args | Task with a lifecycle (submitted → working → completed) |

A2A reached v1.0 in April 2026 under Linux Foundation governance (originated at
Google), with 150+ adopting organizations at launch, including Salesforce,
PayPal, Atlassian, and several large consultancies. The orchestration patterns
above (supervisor, swarm, pipeline) describe the *logical* topology; A2A is one
*wire-level* way to implement the messages between agents when they don't share
a runtime.

> **Most multi-agent systems don't need it.** If every subagent runs on the same
> SDK in the same process — the common case for the subagent-delegation pattern
> above — a structured function return is simpler and faster than a network
> protocol. Reach for A2A specifically when agents cross an organizational or
> vendor boundary: your refund agent calling a partner's shipping agent, not your
> own research subagent calling your own writing subagent.

---

## State Management

### Durable Execution

Agent runs can be long (minutes to hours). They must survive crashes.

```
┌──────────────────────────────────────────────────────────┐
│              Durable Execution with Checkpointing        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Agent Run:                                              │
│  Step 1: Research → ✓ (checkpoint saved)                 │
│  Step 2: Analyze  → ✓ (checkpoint saved)                 │
│  Step 3: Write    → ✗ CRASH!                             │
│                                                          │
│  Restart:                                                │
│  Step 1: Research → ✓ (loaded from checkpoint)           │
│  Step 2: Analyze  → ✓ (loaded from checkpoint)           │
│  Step 3: Write    → ✓ (re-executed)                      │
│  Step 4: Review   → ✓                                    │
│                                                          │
│  Only step 3 re-executed. Steps 1-2 skipped.             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Journal-Based Execution

```
  Append-only log of completed steps:

  ┌─────────────────────────────────────────────────────────────┐
  │  journal.jsonl — one line appended per completed step       │
  │                                                             │
  │  {"step":"research","input":"topic","result":"…","ts":"…"}  │
  │  {"step":"analyze", "input":"…",    "result":"…","ts":"…"}  │
  │  {"step":"write",   "input":"…",    "result":"…","ts":"…"}  │
  │                                                             │
  │  Append-only: a step is written AFTER it succeeds, so a     │
  │  crash mid-step leaves no entry and the step re-runs.       │
  └─────────────────────────────────────────────────────────────┘

  On restart:
  1. Load journal
  2. Check: which steps are already completed?
  3. Skip completed steps, re-execute remaining
```

---

## Cost Control

### Budget-Aware Loops

Inject remaining budget into the agent's prompt for self-regulation.

```
  System prompt:
  "You have 50,000 tokens remaining. Be proportionally thorough —
   deeper analysis for complex items, brief notes for simple ones.
   Stop gracefully if nearly exhausted."

  Budget tracker:
  spent = 0
  while spent < budget:
      response = llm_call(prompt, ...)
      spent += response.usage.total_tokens
      
      if spent > budget * 0.8:
          log("80% budget consumed — wrapping up")
```

### Token Injection Pattern

```
  Each iteration of the agent loop:

  1. Check remaining budget
  2. Inject into system prompt:
     "Budget remaining: {remaining} tokens ({pct}% used)"
  3. Agent self-regulates based on remaining budget
  4. If budget exhausted → graceful stop
```

---

## Evaluating Agents

"It got the right answer" is a different question from "would you trust it in
production." Two agents can reach an identical final answer through very
different paths:

```
  Trajectory A (efficient)                 Trajectory B (wasteful)
  1. search("refund policy")               1. search("refund policy")
  2. read(top result)                      2. search("refund policy 2024")
  3. answer                                3. search("company refund rules")
                                            4. read(3 results, 2 duplicates)
                                            5. read(1 more)
                                            6. answer

  3 steps, no redundant calls              6 steps, 3 overlapping searches
```

Same final answer, roughly 3x the tokens and latency, and a trajectory that
would have failed outright if any one of those redundant searches had hit a
rate limit instead of returning results. Final-answer accuracy scores both
of these identically — which is exactly the gap behind the "evaluating only
the final answer" mistake below.

**What to score instead of just the destination:**

| Dimension | What it catches |
|----------|-----------------|
| Task success | Did it actually solve the problem, not just answer confidently |
| Tool-call accuracy | Right tool, right arguments, no redundant calls |
| Step efficiency | Steps taken vs. the minimum the task required |
| Recovery behavior | Does it change approach after a failure, or repeat it unchanged |
| Cost per resolution | Tokens and latency, not just pass/fail |

This is a real shift in how the field evaluates agents. 2026 benchmarks
increasingly score the *trajectory*, not just the destination: tau-bench and
tau2-bench simulate multi-turn tool-use conversations against a policy, TRACE
(Trajectory-Aware Comprehensive Evaluation) scores the whole problem-solving
path rather than the final message, and ATBench targets safety failures that
only appear mid-trajectory. Public leaderboards still matter for comparing raw
model capability, but they saturate and get gamed — most production teams end
up writing task-specific trajectory rubrics scored by an LLM judge, rather than
relying on a public benchmark alone.

> **Caveat:** an LLM judging another LLM's trajectory inherits the judge's own
> biases — a preference for verbose explanations, or for its own phrasing
> style. Treat automated trajectory scoring as a fast filter that lets you
> triage at scale, not a substitute for periodically reading real transcripts.

---

## Case Study: Claude Code Architecture

Claude Code is an autonomous coding agent that demonstrates production agent architecture.

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│              Claude Code Architecture                     │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Agent Harness                                    │    │
│  │                                                   │    │
│  │  ┌───────────┐  ┌──────────┐  ┌──────────────┐    │    │
│  │  │ Permission│  │ Tool     │  │ Context      │    │    │
│  │  │ System    │  │ Registry │  │ Management   │    │    │
│  │  │           │  │          │  │              │    │    │
│  │  │ allow/    │  │ read,    │  │ token budget,│    │    │
│  │  │ ask/deny  │  │ edit,    │  │ compaction,  │    │    │
│  │  │           │  │ bash,    │  │ checkpointing│    │    │
│  │  │           │  │ grep...  │  │              │    │    │
│  │  └───────────┘  └──────────┘  └──────────────┘    │    │
│  │                                                   │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐     │    │
│  │  │ Subagent │  │ Task     │  │ Memory       │     │    │
│  │  │ System   │  │ Tracking │  │ System       │     │    │
│  │  │          │  │          │  │              │     │    │
│  │  │ explore, │  │ T1, T2,  │  │ project,     │     │    │
│  │  │ general, │  │ T3...    │  │ session,     │     │    │
│  │  │ compose  │  │          │  │ global       │     │    │
│  │  └──────────┘  └──────────┘  └──────────────┘     │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
│  ┌───────────────────────────────────────────────────┐    │
│  │  Safety Layer                                     │    │
│  │  - Permission evaluation (allow/ask/deny)         │    │
│  │  - Tool validation (prevent destructive ops)      │    │
│  │  - User confirmation for risky actions            │    │
│  └───────────────────────────────────────────────────┘    │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Permission model**: Every tool call goes through a permission evaluator. Some actions are auto-allowed (reads), some require confirmation (writes), some are denied (dangerous ops).

2. **Subagent isolation**: each subagent is a declarative definition — a description (when to use it), a prompt (how it behaves), an optional restricted tool set, and an optional model override. It runs in its own fresh context window, so it never inherits the parent's history, and it cannot spawn subagents of its own: nesting stops at one level, which bounds how far a runaway fan-out can go. Only the subagent's final, synthesized result returns to the parent — not its intermediate tool calls.

3. **Dynamic fan-out**: the lead agent doesn't have to pick a fixed number of subagents up front. It can plan and spawn anywhere from a handful to dozens in one session for genuinely parallel, independent work — for example, applying the same structural edit across a dozen independent files — then synthesize their results.

4. **Checkpointing**: long-running tasks are periodically checkpointed. If the session crashes, work resumes from the last checkpoint.

5. **Memory hierarchy**: project memory (durable across sessions), session memory (current conversation), global memory (user preferences).

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| ReAct Paper (ICLR 2023) | Paper | Foundational agent pattern |
| Anthropic "Building Effective Agents" | Blog | Agent architecture patterns |
| Model Context Protocol Specification | Spec | Agent-to-tool interoperability |
| Agent2Agent (A2A) Protocol Specification | Spec | Cross-framework agent-to-agent communication |
| tau-bench / tau2-bench | Benchmark | Multi-turn, tool-use agent evaluation |
| LangGraph Documentation | Docs | Stateful graph-based agent orchestration |
| OpenAI Agents SDK Documentation | Docs | Lightweight agent handoff chains |
| Google Agent Development Kit (ADK) Documentation | Docs | Multi-language, enterprise agent orchestration |
| CrewAI Documentation | Docs | Multi-agent systems |

---

## Practice Exercise

**25-minute design**: Design a coding agent:

- Can read files, run commands, write code
- Must handle errors gracefully
- Must not delete user files without confirmation
- Must track progress on multi-step tasks

**Key decisions**:
1. What middleware concerns do you need?
2. How do you implement the permission model?
3. How do you handle long-running tasks?
4. How do you control costs?

## Common Mistakes

| Mistake | Why It's Wrong | What to Do Instead |
|---------|---------------|-------------------|
| **No step or token ceiling** | A looping agent burns budget until someone notices the bill | Hard caps on steps, tokens, wall-clock, and cost — enforced in the harness |
| **Unbounded tool output into context** | One `cat` of a large file evicts the actual task from the window | Truncate, summarize, or write to disk and pass a reference |
| **Swallowing tool errors** | The model can't correct what it can't see, so it repeats the failing call | Feed the error text back as an observation |
| **Retrying a failing tool call unchanged** | Identical input yields an identical failure | Change something — arguments, tool, or approach — or escalate |
| **Irreversible actions without confirmation** | `rm -rf`, sending email, moving money: a wrong tool call is unrecoverable | Classify tools by reversibility; gate the destructive ones behind approval |
| **Trusting retrieved content as instructions** | Indirect prompt injection: a fetched page says "ignore previous instructions" and the agent complies | Keep data and instructions structurally separate; never grant fetched text authority |
| **Treating MCP/A2A as a trust boundary** | These protocols standardize discovery and invocation, not safety — a compromised MCP server returns attacker-controlled text like any other untrusted source | Apply the same guardrails to protocol-delivered content as to any other tool output |
| **Multi-agent when one agent suffices** | Every handoff loses context and multiplies cost and failure modes | Single agent with good tools first; delegate only for genuine parallelism or context isolation |
| **Sharing one context across subagents** | The isolation that makes delegation useful disappears | Fresh context per subagent; return only the synthesized result |
| **No checkpointing on long runs** | A crash at step 9 of 10 redoes everything, including the expensive parts | Journal completed steps; resume from the last good state |
| **Evaluating only the final answer** | An agent can reach the right answer via a broken, unrepeatable path | Evaluate trajectories: tool choice, step count, recovery behavior |
| **Non-idempotent tools** | A retried "create ticket" opens three | Idempotency keys on side-effecting tools |

---

## Discussion Questions

1. You're building a coding agent that can read files, run commands, and write code. Design the harness architecture. What middleware concerns do you need?

2. Explain the difference between the supervisor and swarm patterns. When would you use each?

3. Your agent costs $5 per run but sometimes wastes tokens on unnecessary exploration. Design a cost control mechanism.

4. How do you handle agent failures? Design a retry mechanism that doesn't repeat successful steps.

5. You're building a multi-agent system where agents need to share information. Design the communication protocol.

6. Your agent needs to call tools owned by three internal teams. Would you standardize on MCP, or is a hand-rolled integration layer good enough? What changes if two of those tools are actually agents run by an external partner company?

7. Two coding agents both solve 80% of a benchmark suite. How would trajectory-aware evaluation help you choose between them, beyond the raw pass rate? What would you look for in the 20% they both fail?

---

## Related Modules

| Module | Connection |
|--------|-----------|
| [Module 13: Security](../13-security/README.md) | Guardrails and prompt-injection defense are security controls applied to an autonomous, tool-calling caller |
| [Module 07: Reliability Engineering](../07-reliability/README.md) | Checkpointed durable execution and retry-with-backoff are reliability patterns applied to a long-running agent loop |
| [Module 16: LLM Inference Serving Architecture](../16-llm-inference-serving/README.md) | Inference-serving latency and cost directly bound how much an agent loop can afford to do per step |
| [Module 15: Observability](../15-observability/README.md) | Trajectory evaluation and cost tracking apply this module's metrics, logs, and traces to a multi-step agent run |

---

## Summary

```
┌────────────────────────────────────────────────────────────────┐
│           Agent System Architecture — Key Takeaways            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. The harness — not the model — is the design surface; better│
│     tools and middleware beat a bigger model                   │
│  2. ReAct covers most agent tasks; save Plan-and-Execute for   │
│     work that truly needs upfront decomposition                │
│  3. Six middleware concerns are non-negotiable in production:  │
│     execution sandboxing, context budgeting, delegation, fault │
│     tolerance, guardrails, human-in-the-loop                   │
│  4. MCP and A2A standardize discovery and invocation, not trust│
│     — a compromised server is just another untrusted source    │
│  5. Reach for multi-agent only for genuine parallelism or      │
│     context isolation; one agent with good tools is the default│
│  6. Journal every completed step so a crash costs you one step,│
│     not the whole run                                          │
│  7. Inject remaining budget into the prompt so the agent self- │
│     regulates instead of spending until someone notices the    │
│     bill                                                       │
│  8. Evaluate trajectories, not just final answers — the same   │
│     answer can hide a 3x-more-expensive, unrepeatable path     │
│  9. Gate irreversible tool calls behind approval — a wrong `rm │
│     -rf` or wire transfer doesn't undo itself                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Navigation

**Previous:** [Module 17: RAG System Architecture at Scale](../17-rag-at-scale/README.md)

**Next:** [Module 19: Production AI System Architecture](../19-production-ai-system/README.md)

---

*Module 18 of 19 in the System Design Playground*

