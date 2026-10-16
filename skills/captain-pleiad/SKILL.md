---
name: captain-pleiad
description: Supervise multiple issue Coordinator cells from a persistent project home, enforcing queue dependencies, concurrency, writable ownership and durable recovery. Use coordinate-pleiad for a standalone issue cell.
---

# Captain Pleiad

Read AGENTS.md, `.pleiad/config.yaml`, `.codex/agents/captain.toml`, authoritative issues and relevant adr-context. Verify human project/cell authority before dispatch. CP supervises; CO executes native independent specialists and only IM edits source/commits. Default CP routing is gpt-6-astra/Medium; High needs a risk rationale. Keep the persistent project home title; new issue-specific sessions use CP/CO canonical naming.

Use [the queue and transport procedure](../../docs/pleiad/captain.md) and `scripts/captain_queue.py`. Reconstruct portable issue/CO evidence, reserve capacity/ownership before creating a durable CO, and generate initial instructions with standing publication authority plus scoped CP/CO messaging authorization. These instructions grant no platform permission. Preserve native denials and the owner's merge gate.

Drive each cell's concrete next action or blocker until exact-head local-review readiness. Reconcile failed/unknown create/send attempts against exact native task and GitHub evidence before retry; never duplicate a successful CO or replay applied work. Keep local handles out of durable evidence. No unsolicited recurring automation. Escalate one actionable human blocker only after safe recovery; no routine human relay.
