# Working Rules for AI Agents (Claude / GPT)

## Purpose

This document defines how AI agents must behave when working on Company Brain.

It ensures:

- consistency
- code quality
- alignment with roadmap
- avoidance of bad decisions

These rules are STRICT.

---

## Core Rule

ALWAYS follow:

- docs/roadmap.md
- docs/architecture.md

If something is not aligned → DO NOT IMPLEMENT IT.

---

## Product Understanding

Company Brain is:

- NOT a chatbot
- NOT a generic RAG tool

It is:

→ a knowledge operating system for companies

Key principle:

Reliability > Intelligence

---

## Non-Negotiable Rules

- NEVER fabricate logic or assumptions
- NEVER introduce features outside the roadmap phase
- ALWAYS prioritize traceability over complexity
- ALWAYS make answers explainable
- ALWAYS preserve multi-tenant isolation
- ALWAYS think in production terms

---

## Development Rules

### 1. Simplicity First

- Prefer simple, maintainable solutions
- Avoid overengineering
- Do NOT introduce unnecessary abstractions

---

### 2. Modular Monolith

- DO NOT create microservices
- Keep structure:

  - api/
  - services/
  - models/
  - schemas/

- Respect separation of concerns

---

### 3. Backend Rules

- All business logic → services/
- API routes must be thin
- No logic inside controllers
- Use async patterns consistently
- Always validate inputs

---

### 4. Data Integrity

- Never break multi-tenant isolation
- Always include organization_id filters
- Prefer database-level guarantees when possible
- Prepare for future RLS

---

### 5. Traceability First

Every feature must allow:

- knowing what happened
- knowing why it happened
- knowing which data was used

---

### 6. No Magic Behavior

- Do NOT hide logic inside prompts only
- Do NOT rely only on LLM responses
- Always support behavior with system design

---

### 7. AI / LLM Rules

- Never answer without evidence
- If evidence is weak → explicitly say it
- If no answer → say "insufficient information"
- Always return sources
- Prefer grounded responses over complete ones

---

### 8. Conversations

- Conversations must be persistent
- Memory must NOT replace real knowledge
- Memory is context, NOT source of truth

---

### 9. Ingestion Pipeline

- Must be asynchronous
- Must be idempotent
- Must support retries
- Must be observable (status tracking)

---

### 10. Logging & Debugging

- Log key operations
- Avoid silent failures
- Make debugging easy

---

## What NOT to Do

- Do NOT implement agents yet
- Do NOT introduce microservices
- Do NOT create complex infra prematurely
- Do NOT add UI features without backend support
- Do NOT build dashboards without real data
- Do NOT mix conversation memory with knowledge base

---

## Decision Framework

Before implementing anything, ask:

1. Is this in roadmap.md?
2. Does this improve reliability?
3. Does this improve traceability?
4. Is this production-ready?
5. Is this the simplest possible solution?

If any answer is NO → rethink.

---

## Output Expectations

When generating code:

- Be concise
- Be correct
- Be production-ready
- Include necessary imports
- Specify file paths
- Avoid unnecessary explanations

---

## Final Rule

You are not here to experiment.

You are here to build a reliable, scalable SaaS product.

Act like a senior engineer in a high-stakes startup.