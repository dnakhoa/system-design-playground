# Module 18: Agent System Architecture

> **Designing autonomous LLM agent systems.** An agent is not just an LLM with tools — it's a system with planning, execution, memory, and guardrails. The harness (not the model) is the design surface.

## Learning Objectives

- Understand the Agent = Model + Harness architecture
- Implement the ReAct planning pattern
- Design multi-agent orchestration systems
- Implement state management and durable execution
- Design cost control mechanisms for agents

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

  ┌──────────────────────────────────────────────────────┐
  │  Journal (JSONL):                                    │
  │  {"step": "research", "input": "topic", "result": "...", "ts": "..."} │
  │  {"step": "analyze", "input": "...", "result": "...", "ts": "..."}    │
  │  {"step": "write", "input": "...", "result": "...", "ts": "..."}      │
  └──────────────────────────────────────────────────────┘

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

2. **Subagent isolation**: Subagents run in their own context windows. They don't pollute the parent's context. Results are synthesized by the parent.

3. **Checkpointing**: Long-running tasks are periodically checkpointed. If the session crashes, work resumes from the last checkpoint.

4. **Memory hierarchy**: Project memory (durable across sessions), session memory (current conversation), global memory (user preferences).

---

## Key References

| Resource | Type | Focus |
|----------|------|-------|
| ReAct Paper (ICLR 2023) | Paper | Foundational agent pattern |
| Anthropic "Building Effective Agents" | Blog | Agent architecture patterns |
| LangGraph Documentation | Docs | Agent orchestration |
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
| **Multi-agent when one agent suffices** | Every handoff loses context and multiplies cost and failure modes | Single agent with good tools first; delegate only for genuine parallelism or context isolation |
| **Sharing one context across subagents** | The isolation that makes delegation useful disappears | Fresh context per subagent; return only the synthesized result |
| **No checkpointing on long runs** | A crash at step 9 of 10 redoes everything, including the expensive parts | Journal completed steps; resume from the last good state |
| **Evaluating only the final answer** | An agent can reach the right answer via a broken, unrepeatable path | Evaluate trajectories: tool choice, step count, recovery behaviour |
| **Non-idempotent tools** | A retried "create ticket" opens three | Idempotency keys on side-effecting tools |

---

## Discussion Questions

1. You're building a coding agent that can read files, run commands, and write code. Design the harness architecture. What middleware concerns do you need?

2. Explain the difference between the supervisor and swarm patterns. When would you use each?

3. Your agent costs $5 per run but sometimes wastes tokens on unnecessary exploration. Design a cost control mechanism.

4. How do you handle agent failures? Design a retry mechanism that doesn't repeat successful steps.

5. You're building a multi-agent system where agents need to share information. Design the communication protocol.

---

**Previous**: [RAG System Architecture at Scale](../17-rag-at-scale/README.md)
**Next**: [Production AI System Architecture](../19-production-ai-system/README.md)

