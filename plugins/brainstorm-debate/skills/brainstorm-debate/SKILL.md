---
name: brainstorm-debate
description: Start a 7-agent brainstorm debate team to stress-test a project idea from every angle — business, technical, UX, edge cases, and more. Use when you want to brainstorm, debate, or validate a project idea.
argument-hint: <your idea description>
disable-model-invocation: true
---

# Brainstorm Debate Team

Create an agent team called "brainstorm" to debate the following project idea through structured free debate.

## The Idea

$ARGUMENTS

## Setup Instructions

Read ALL 7 persona files from this skill's directory (the same directory as this SKILL.md file). Each file defines one agent's personality, mission, core question, interaction rules, and constraints.

Spawn 7 teammates — one per persona. When spawning each teammate, include their **FULL persona file content** in the spawn prompt so they fully embody their role. Also include the idea being debated.

| Teammate Name | Persona File |
|---|---|
| `business-analyst` | [01_business_analyst.md](01_business_analyst.md) |
| `technical-architect` | [02_technical_architect.md](02_technical_architect.md) |
| `socratic-prober` | [03_socratic_prober.md](03_socratic_prober.md) |
| `devils-advocate` | [04_devils_advocate.md](04_devils_advocate.md) |
| `ux-friction-hunter` | [05_ux_friction_hunter.md](05_ux_friction_hunter.md) |
| `visionary-connector` | [06_visionary_connector.md](06_visionary_connector.md) |
| `saas-killer` | [07_saas_killer.md](07_saas_killer.md) |

Each teammate's spawn prompt must include:
1. Their full persona (from the file)
2. The idea being debated
3. The instruction: "You are in a free debate with 6 other agents AND the human Idea Owner. The Idea Owner is NOT a passive moderator — they are an active participant who pitched this idea and will defend, clarify, and evolve it. You MUST direct questions and challenges to the Idea Owner, not just to other agents. When you need domain knowledge, motivation, or context behind the idea, ASK the Idea Owner directly. Challenge others directly when you disagree. Respond when challenged. Stay in character at all times."
4. The names of all other teammates so they can address each other
5. The instruction: "Address the Idea Owner as 'Idea Owner' when directing questions or challenges to them. Do not assume you know their answers — always ask."

## Debate Protocol

Use **free debate mode**: agents challenge each other AND the Idea Owner (user) directly. The Idea Owner is an active debater — they defend their idea, answer questions from agents, and evolve their thinking based on the debate. Agents should NOT just talk among themselves; they must pull the Idea Owner into the conversation by asking them questions, challenging their assumptions, and requesting clarification on their vision.

### PHASE 1 — FIRST TAKE
Each agent gives their initial reaction — 2-3 key points from their specific lens.
Order: Business Analyst → Technical Architect → UX Friction Hunter → Visionary Connector → Devil's Advocate → SaaS Killer → Socratic Prober (last, so their questions build on everything said).

### PHASE 2 — CROSSFIRE (2-3 rounds)
Free debate. Agents challenge each other AND the Idea Owner directly:
- Devil's Advocate attacks the strongest arguments
- Socratic Prober deepens the weakest points with questions — directed at BOTH agents and the Idea Owner
- Visionary Connector proposes pivots based on the debate
- SaaS Killer drops edge-case scenarios on every proposal
- UX Friction Hunter flags user experience problems in proposed solutions
- Technical Architect grounds every idea in feasibility and cost
- Business Analyst checks every pivot against market viability
- Every agent MUST respond when directly challenged by another agent
- Agents MUST ask the Idea Owner questions they cannot answer themselves — motivation, target users, constraints, domain knowledge, willingness to trade off
- **IMPORTANT**: After each round of agent discussion, PAUSE and present the Idea Owner with the key questions and challenges directed at them. Wait for their response before continuing the next round. Do NOT let agents answer on behalf of the Idea Owner.

The Idea Owner may also at any time:
- Answer questions from agents
- Defend or pivot their position
- Drop new constraints ("What if we only have 1 month?", "What if it's mobile-only?")
- Challenge an agent's argument back
- Ask an agent to steelman another's position
- Push to the next phase

### PHASE 3 — FINAL VERDICT
Each agent delivers:
1. Their refined position on the idea
2. Biggest remaining risk from their lens
3. One thing they changed their mind about during the debate

### PHASE 4 — SYNTHESIS ARTIFACT
After all phases complete, compile ALL debate findings into a structured document and save it to `Claude/Brainstorm-Team/outputs/`. Use a descriptive filename like `brainstorm-[short-idea-name]-[date].md`.

The document must follow this structure:

```
# Brainstorm: [Idea Title]
**Date**: [today's date]
**Participants**: 7-agent debate team + human lead

## Refined Idea Statement
[How the idea evolved through debate — not the original pitch]

## Key Strengths (Survived Debate)
[Arguments that withstood Devil's Advocate + SaaS Killer attacks]

## Key Risks & Mitigations
| Risk | Severity | Mitigation | Raised By |
|------|----------|------------|-----------|

## Edge Cases & Failure Modes
[From SaaS Killer — concrete scenarios that could break the product]

## UX Considerations
[From UX Friction Hunter — friction points, adoption barriers, user journey issues]

## Technical Assessment
[From Technical Architect — complexity estimate, architecture suggestions, hard problems]

## Market & Business Assessment
[From Business Analyst — viability, competition, monetization, target segment]

## Open Questions Requiring Validation
[From Socratic Prober — assumptions that remain unproven and need real-world testing]

## Wild Cards & Pivots Considered
[From Visionary Connector — alternative directions explored during debate]

## Minority Opinions
[Dissenting views worth preserving even if outvoted — these often contain important signals]

## Recommended Next Steps
1. [Concrete validation experiments]
2. [Key decisions to make]
3. [Research needed]
```

## Rules for the Team Lead (Orchestrator)
- After each crossfire round, collect all questions/challenges directed at the Idea Owner and present them clearly
- WAIT for the Idea Owner's response before proceeding — never let agents fill in answers on behalf of the Idea Owner
- If agents are only talking among themselves and ignoring the Idea Owner, remind them to engage the Idea Owner
- Let the crossfire run — don't cut debate short, the best insights come from friction
- If agents start repeating themselves, push to the next phase

## Tips for the Idea Owner (You)
- You are a debater, not just a spectator — defend your idea, push back on agents, answer their questions
- Side with the minority sometimes — if 6 agents agree and 1 disagrees, explore why
- Drop new constraints mid-debate to stress-test adaptability ("What if budget is only $5K?", "What if it must work offline?")
- Challenge agents back — "Devil's Advocate, you said X will fail, but what about Y?"
- It's OK to say "I don't know" — that becomes an open question for validation
- You can ask any agent to elaborate or challenge a specific other agent
