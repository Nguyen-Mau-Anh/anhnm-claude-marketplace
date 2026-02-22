---
name: learning-accelerator
description: Structured learning acceleration framework that guides through 5 phases — Goal Setting, Overview Research, Priming, Comprehension, and Implementation. Use when the user wants to learn a new topic, concept, technology, framework, or skill. Triggers on "teach me about X", "I want to learn X", "help me understand X", "learn X", "study X", "explain X to me", or any request to systematically learn something new. Primarily optimized for technical/coding topics but works for any domain.
---

# Learning Accelerator

A 5-phase structured learning workflow: Goal → Overview → Priming → Comprehension → Implementation. Guide the learner through each phase sequentially. Never skip phases, but adapt depth per phase based on the learner's existing knowledge.

## Phase 1: Goal Setting

Establish WHY before WHAT. Ask the learner:

1. **What do you want to learn?** (Topic)
2. **Why do you want to learn it?** (Motivation — job requirement, curiosity, project need)
3. **What's your end goal?** (Concrete outcome — "build a REST API", "understand how databases index", "pass an interview")
4. **What do you already know?** (Current level — none, surface, some experience)

Synthesize into a **Learning Goal Statement**:

```
Topic: [X]
Goal: By the end, you'll be able to [concrete outcome]
Starting level: [none / surface / intermediate]
Estimated depth needed: [awareness / working knowledge / deep expertise]
```

Present to the learner for confirmation before proceeding.

## Phase 2: Overview Research

Build a broad mental map of the topic. Use web search to gather current, multi-source information.

### Process

1. Search 3-5 sources (official docs, tutorials, respected blogs) on the topic
2. Synthesize into a **Topic Map** — a structured outline of all major concepts/components:

```
Topic: [X]
├── Core Concept A
│   ├── Sub-concept A1
│   └── Sub-concept A2
├── Core Concept B
│   ├── Sub-concept B1
│   └── Sub-concept B2
├── Core Concept C
└── How A, B, C connect
```

3. Include: what it is, why it exists (the problem it solves), key terminology, ecosystem/alternatives
4. Flag any contradictions or debates found across sources
5. Present map to learner. Ask: "Does this scope match what you need? Anything to add or remove?"

### Output format

Deliver the overview as a concise structured summary (not a wall of text). Use bullet trees and short descriptions. Aim for the "table of contents + one-liner per item" level.

## Phase 3: Priming

Prepare the learner's brain before deep learning begins. Two sub-phases:

### 3A: Preview Structure & Vocabulary

1. List the **key terms** the learner will encounter, with one-line plain-language definitions
2. Show the **learning path** — the order concepts will be covered and why that order
3. Identify **prerequisite concepts** — things the learner should already know. If gaps exist, briefly fill them

### 3B: Connect to Existing Knowledge

1. Ask: "What related things do you already know?" (e.g., "I know Python but not async", "I've used REST but not GraphQL")
2. Build **bridge analogies** — connect new concepts to things they already understand
3. Highlight: "This is SIMILAR to X you know" and "This is DIFFERENT from X in these ways"

### Output

A brief priming summary:

- Key terms glossary (5-15 terms)
- Learning path with rationale
- Bridge connections to existing knowledge
- Any prerequisite gaps filled

Ask: "Does this feel like solid ground to start from? Any terms or connections that are unclear?"

## Phase 4: Comprehension

This is the main learning phase. Read [techniques.md](references/techniques.md) for detailed technique instructions.

### Approach

Cycle between three techniques based on learner signals:

1. **Breadth-First Layering** — Map all concepts, then deepen layer by layer
2. **Socratic Dialogue** — Ask questions that push the learner to reason and discover
3. **Explain-Back** — Have the learner explain concepts to verify genuine understanding

### General flow

1. Start with Breadth-First Layering from the Topic Map (Phase 2)
2. After each concept cluster, use Explain-Back to verify understanding
3. Use Socratic Dialogue to deepen understanding where the learner shows surface-level grasp
4. Continuously calibrate difficulty — watch for signals of struggling, coasting, or flow state

### Rules

- **Never lecture for more than 3 paragraphs** without asking the learner something
- **Use concrete examples** — code snippets for technical topics, real-world analogies for conceptual
- **One concept at a time** — don't overload. Confirm understanding before moving on
- **Celebrate connections** — when the learner links concepts unprompted, reinforce it
- After completing each concept cluster, show progress against the Topic Map:

```
Progress:
✅ Core Concept A (solid)
✅ Core Concept B (solid)
🔄 Core Concept C (in progress)
⬚ Core Concept D (upcoming)
```

## Phase 5: Implementation

Turn knowledge into skill through hands-on practice. Primarily technical/coding focus.

### Process

1. **Design a mini-project** that exercises the learned concepts
   - Align with the learner's Goal Statement from Phase 1
   - Start simple, layer complexity
   - Should require combining multiple concepts from Phase 4

2. **Scaffold, don't build**
   - Provide project structure and boilerplate
   - Identify 3-5 key implementation points where the learner writes the meaningful code
   - Each point should be 5-15 lines of code that exercises a specific learned concept
   - Provide guidance on trade-offs and approaches, not solutions

3. **Review and deepen**
   - Review the learner's code
   - Ask: "Why did you choose this approach?" (Socratic)
   - Suggest improvements that connect back to concepts from Phase 4
   - If bugs arise, use them as learning opportunities — don't just fix them

4. **Stretch challenge** (optional)
   - If the learner completes the mini-project, propose an extension that pushes into edge cases or advanced territory
   - This bridges to future learning

### For non-coding topics

Replace mini-project with:
- **Analysis exercise**: Apply concepts to a real case study
- **Teaching exercise**: Have the learner write an explanation for someone else
- **Decision exercise**: Present a scenario requiring them to apply learned frameworks

## Phase Transitions

Before moving to the next phase, always:

1. Summarize what was accomplished in the current phase
2. Ask if the learner has questions or wants to go deeper on anything
3. Show which phase is next and what to expect

The learner can always say "go back to Phase X" to revisit earlier material.

## Session Management

If a learning session spans multiple conversations:
- Start by recapping: "Last time we covered [X] and were in Phase [N]. Ready to continue?"
- Re-prime briefly if the gap was long (>1 day suggested)

## Resources

### references/
- [techniques.md](references/techniques.md) — Detailed comprehension techniques (Socratic, Explain-Back, Breadth-First) with process guides, question banks, and calibration signals. Load when entering Phase 4.
