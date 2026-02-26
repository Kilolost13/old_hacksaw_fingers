# Kilo Guardian - Octopus Orchestration Model

**Document Version:** 1.0  
**Date:** February 8, 2026  
**Audience:** Kilo Guardian Engineering Team  
**Status:** Proposal

---

## Overview

This document proposes an "octopus" orchestration architecture for Kilo Guardian:

- **Brain (Center):** A single coordination core that routes intent, manages context, and controls policies.
- **Arms (Pods):** Independent execution pods/services that each own a focused domain capability.
- **Nervous System (Message Bus):** Event and command transport between the brain and arms.
- **Suction Cups (Adapters):** Small connectors at each arm for standard input/output, retries, and observability.

The goal is to make Kilo Guardian **more modular, more local-first, and easier to scale** while keeping core reasoning centralized and consistent.

---

## Line Diagram

```mermaid
flowchart TD
  User[User / UI] --> Brain[Brain (Central Orchestrator)]

  subgraph Arms[Arms (Domain Pods)]
    Rem[Reminder Arm]
    Hab[Habits Arm]
    Med[Meds Arm]
    Fin[Finance Arm]
    Cam[Camera Arm]
    Voi[Voice Arm]
    Lib[Library Arm]
    ML[ML Arm]
    USB[USB Arm]
    Sec[Security Arm]
  end

  subgraph Bus[Nervous System (Message Bus)]
    Cmd[Command]
    Res[Result]
    Evt[Event]
    Alr[Alert]
  end

  Brain --> Cmd
  Cmd --> Arms
  Arms --> Res
  Res --> Brain
  Arms --> Evt
  Evt --> Brain
  Arms --> Alr
  Alr --> Brain

  Brain --> User
```

---

## 1. Octopus Model - Roles

### 1.1 Brain (Central Orchestrator)
**Responsibilities**
- Intent detection and routing
- Global policy enforcement (security, privacy, offline rules)
- Session state and memory management
- Response aggregation and formatting
- Load balancing across arms
- Fallback logic (always local-first)

**Candidate Location**
- `kilo-unified-agent` (port 9200), extended to be the single orchestrator

**Key Capabilities**
- Request tracing and correlation ID
- Unified error formatting
- Policy gate for all actions

---

### 1.2 Arms (Domain Pods)
Each arm is a specialized pod or microservice. It executes a single domain skill:

| Arm | Pod/Service | Core Job |
|-----|-------------|----------|
| Reminder Arm | `kilo-reminder` | Scheduling + reminders |
| Habits Arm | `kilo-habits` | Habit tracking + streaks |
| Meds Arm | `kilo-meds` | Medication schedules |
| Finance Arm | `kilo-financial` | Spending + budgets |
| Camera Arm | `kilo-cam` | Activity, posture, safety |
| Voice Arm | `kilo-voice` | STT/TTS local only |
| Library Arm | `kilo-library` | Knowledge lookup |
| ML Arm | `kilo-ml-engine` | Local modeling + predictions |
| USB Arm | `kilo-usb-transfer` | File sync |
| Security Arm | `kilo-security-monitor` | Intrusion + audit |

Each arm is **independent**, **local-first**, and communicates only through the brain or a defined bus.

---

### 1.3 Nervous System (Message Bus)
A single internal transport layer for all messages:

**Options (Local First):**
- In-memory queue (fast, but non-persistent)
- Redis (persistent, local, low overhead)
- NATS (simple pub/sub, local cluster)

**Message Types**
- `Command`: brain -> arm (execute function)
- `Result`: arm -> brain (return response)
- `Event`: arm -> brain (background signal)
- `Alert`: arm -> brain (security or system alerts)

---

### 1.4 Suction Cups (Adapters)
Standard adapters at the edge of each arm:

**Purpose**
- Uniform input/output schema
- Retry/backoff
- Observability hooks
- Timeout control

**Example Adapter Contract**
```json
{
  "request_id": "uuid",
  "arm": "meds",
  "action": "add_medication",
  "payload": {
    "name": "Aspirin",
    "dosage": "500mg"
  }
}
```

**Uniform Response**
```json
{
  "request_id": "uuid",
  "status": "success",
  "result": {"message": "Medication added"}
}
```

---

## 2. How to Include All Required Functions

### 2.1 Core Function Groups

1. **Command Understanding (Brain)**
   - Intent parsing
   - Local LLM fallback
   - Routing to arm

2. **Domain Functions (Arms)**
   - Reminders, habits, meds, finance, camera, voice, library, ML

3. **Memory & User Context (Brain)**
   - Session memory
   - User preferences
   - Audit and logging

4. **Monitoring & Self-Healing (Arms + Brain)**
   - Health checks per arm
   - Central alert aggregation

5. **Security & Privacy (Brain)**
   - No external calls
   - Local LLM only
   - Explicit policy for every action

---

## 3. Orchestration Flow (Example)

### 3.1 Example: "Remind me to take meds at 9pm"

1. User request arrives at Brain
2. Brain parses intent = `reminder.create`
3. Brain constructs Command -> Reminder Arm
4. Reminder Arm executes and returns Result
5. Brain formats response to user

Sequence:
```
User -> Brain -> Reminder Arm -> Brain -> User
```

---

### 3.2 Example: "Analyze my spending"

1. Brain parses intent = `finance.analyze`
2. Brain dispatches to Finance Arm
3. Finance Arm calculates summary and returns
4. Brain formats response

---

## 4. Service Contract Standardization

Every arm must expose these endpoints:

- `GET /health` -> local health
- `POST /execute` -> execute an action
- `GET /capabilities` -> list of supported actions

**Example**
```json
{
  "capabilities": [
    "reminder.create",
    "reminder.list",
    "reminder.delete"
  ]
}
```

---

## 5. Brain Core Modules

Recommended brain internal modules:

1. **Intent Router**
2. **Policy Engine**
3. **Context Manager**
4. **Response Formatter**
5. **Message Bus Client**
6. **Observability Layer**

---

## 6. Local-First Enforcement

All arms must obey:

- No external API calls
- No cloud LLMs
- No remote telemetry
- No network dependency except local cluster

The brain enforces this by blocking any non-approved outbound domain in policy.

---

## 7. Migration Strategy

### Phase 1 (1-2 weeks)
- Define arm interfaces (`/execute`, `/health`, `/capabilities`)
- Add adapters to existing pods
- Centralize routing to brain

### Phase 2 (2-3 weeks)
- Move all form/flow logic into brain
- Make all arms stateless
- Add message bus for async work

### Phase 3 (3-4 weeks)
- Add parallel orchestration (multi-arm tasks)
- Add structured tracing
- Add caching in brain

---

## 8. Benefits

- Clean separation of concerns
- Local-first enforced by design
- Easy to scale or swap arms
- Faster debugging and testing
- Safer upgrades

---

## 9. Open Decisions

1. Which message bus (Redis vs NATS)?
2. Where to store global memory (Postgres vs local files)?
3. Should arms be fully stateless or allowed local caches?
4. What is the standard response contract across arms?

---

## 10. Next Steps

- Review this proposal with the team
- Pick a message bus
- Draft the arm API contract (OpenAPI)
- Prototype a single arm adapter

---

**End of Document**
