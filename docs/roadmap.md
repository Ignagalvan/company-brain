# Company Brain — Product & Technology Roadmap

## Purpose

This document defines the product vision, roadmap and priorities for Company Brain.

It is the source of truth for:

- what we are building
- why we are building it
- in which order
- what we explicitly avoid

This document MUST guide all development decisions.

---

## Vision

Company Brain is NOT a chatbot.

It is a knowledge operating system for companies.

The system must:

- provide answers grounded in real evidence
- never hallucinate
- be auditable and traceable
- reduce dependency on individuals
- evolve into an intelligent company layer

Evolution path:

1. Knowledge Layer (Company Brain)
2. Action Layer
3. Autonomous Operations
4. Company Intelligence

---

## Non-Negotiable Principles

- The system must NEVER fabricate information
- Every answer must include evidence
- If there is not enough information → explicitly say it
- Reliability > creativity
- Must be usable in real companies

---

## Current State

- Document ingestion (PDF → text → chunks → embeddings)
- Semantic retrieval
- Answer generation with sources
- FastAPI backend
- PostgreSQL + pgvector
- Multi-tenant (organization_id)
- Basic frontend with document upload and Q&A

The system already validates the core loop:

"Upload knowledge → process → query → receive grounded answers"

However, it is still transitioning from technical MVP to real SaaS product.

---

# Roadmap

---

## Short Term (0–3 months)

### Goal

Turn the MVP into a reliable SaaS knowledge workspace.

### Focus Areas

- Reliable ingestion pipeline
- Usable conversations
- Strong traceability
- Real multi-tenant security
- Observability of system behavior

### Expected Outcome

A company can:

- upload documents
- ask questions in persistent conversations
- see evidence clearly
- understand what the system knows and doesn’t know
- trust the system in daily use

---

## Short Term — By Area

### Frontend

- Persistent conversations
- Empty state for new conversations (only created after first message)
- Sidebar with conversations (rename/delete)
- Document panel usable and scalable
- Document processing status (indexing, ready, failed)
- Source viewer with highlighted snippets
- Feedback system (useful / not useful)
- Clear "insufficient information" states

---

### Backend

- Models:
  - conversations
  - messages
  - citations
  - document_versions
  - ingestion_jobs

- Asynchronous ingestion pipeline
- Document checksum (idempotency)
- Separation:
  - document metadata
  - indexed content

- Full traceability:
  - chunks used
  - document version
  - model used
  - timestamps

- Authentication + authorization
- Strong multi-tenant isolation
- Optional RLS enforcement
- Basic audit logging

---

### Product / UX

Core thesis:

We are NOT selling "AI answers".
We are selling "operational certainty over company knowledge".

Features:

- Answer + evidence
- Honest "I don’t know"
- Conversation memory
- Navigable sources
- Document management
- System transparency

---

### Architecture

- Keep modular monolith
- Introduce job queue for ingestion
- Move file storage out of local filesystem
- Clear separation:
  - storage
  - parsing
  - chunking
  - embeddings
  - retrieval

- Prepare schema for document versioning
- Structured logging
- Retrieval quality metrics

---

### AI / Reliability

- Answer classification:
  - answerable
  - partially_answerable
  - insufficient_evidence

- Evidence coverage scoring
- Mandatory citations for key claims
- Detection of weak grounding
- Retrieval + answer test suite
- Internal dataset of real questions
- Prompt + output tracing

Goal:
Reduce plausible but incorrect answers.

---

## Mid Term (3–6 months)

### Goal

Transform from Q&A system into knowledge management platform.

### Expected Outcome

The company can:

- detect knowledge gaps
- identify conflicting documents
- understand knowledge usage
- manage evolving documentation

---

## Mid Term — By Area

### Frontend

- Conversation timeline with memory
- Deep links to document fragments
- Conflict detection UI
- Knowledge gaps dashboard
- Suggested missing documents
- Copilots by area (scoped)

---

### Backend

- Document versioning
- Duplicate detection
- Conflict detection models
- Entity extraction + taxonomy
- Relations:
  - document ↔ entity ↔ topic

- Role-based permissions
- Conversation memory store
- Usage analytics

Separation of layers:

1. Raw documents
2. Knowledge artifacts
3. Interaction artifacts

---

### Product / UX

Core modules:

- Knowledge Gaps
- Source of Truth
- Team Copilots

Shift:
From answering → to governing knowledge

---

### Architecture

- Event-driven internal processing
- Workers:
  - parsing
  - embeddings
  - analysis

- Object storage
- Selective caching
- Offline evaluation pipelines
- Hybrid search + reranking

---

### AI / Reliability

- Reranking
- Hybrid retrieval
- Context-aware chunking
- Confidence scoring
- Contradiction detection
- Intent classification
- Routing by domain/copilot

Important:

Conversation memory ≠ source of truth

---

## Long Term (6–18 months)

### Goal

Evolve into knowledge execution and intelligence platform.

---

## Long Term — By Area

### Frontend

- Process-oriented workspaces
- Decision panels with justification
- Executive dashboards
- Domain assistants
- Knowledge health dashboards
- Action recommendations

---

### Backend

- Tool calling with permissions
- Workflow engine
- Action logs
- Policy engine
- Task orchestration
- External integrations (email, CRM, ERP)

---

### Product / UX

Evolution:

Company Brain → Knowledge Layer  
Company Brain + Action Layer  
Company Brain as Company Operating System

Start with low-risk actions:

- draft emails
- create tickets
- generate summaries
- fill templates

Then:

- propose actions
- human approval
- automated execution

---

### Architecture

- Knowledge graph layer
- Policy engine
- Planner / orchestrator
- Observability of actions
- Rollback mechanisms
- Specialized agents

---

### AI / Reliability

Agents require:

- grounding
- authorization
- auditing
- evaluation
- rollback
- strict action boundaries

Otherwise:
System becomes unsafe

---

# Priorities

1. Conversations + traceability
2. Robust ingestion pipeline
3. Security + multi-tenant isolation
4. Evidence UX (sources, highlights)
5. Knowledge gaps detection
6. Conflict detection + versioning
7. Copilots

---

# What NOT to Build Now

- No autonomous agents yet
- No microservices
- No "fancy AI features" without traceability
- No global memory mixing truth and conversation
- No complex integrations too early
- No large dashboards without real data
- No dependency on prompt-only logic

---

# Advanced Concepts (Future)

## 1. Knowledge Graph

- document relationships
- entity mapping
- reasoning navigation

---

## 2. Source of Truth Engine

Score documents based on:

- freshness
- authority
- usage
- internal validation
- contradictions

---

## 3. Decision Ledger

Track:

- decisions
- supporting evidence
- conversations
- users
- outcomes

---

## 4. Knowledge Health Score

Metrics:

- answer coverage
- document freshness
- unresolved conflicts
- knowledge concentration
- missing domains

---

## 5. Learning Loop

Detect:

- unanswered questions
- weak evidence responses
- unclear documents
- escalation patterns

Then:

- suggest missing docs
- generate drafts
- improve knowledge base

---

## 6. Domain Copilots

Each with:

- scoped knowledge
- custom behavior
- evidence thresholds
- permissions

---

## 7. Action Layer (with approval)

- propose action
- human validation
- execution
- audit log

---

## 8. Company Intelligence

Detect:

- risks
- inconsistencies
- knowledge gaps
- operational inefficiencies

---

## Final Principle

The system must evolve toward:

**Reliable → Traceable → Actionable → Intelligent**

NOT:

**Flashy → Uncontrolled → Unverifiable**