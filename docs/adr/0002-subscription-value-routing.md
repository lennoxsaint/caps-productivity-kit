# ADR 0002: Bounded subscription routing with recommendation-only learning

Status: accepted for implementation; activation and publication are separate gates.

## Decision

Use Astra Low for fresh interactive defaults and Luna Max for workers. Preserve
existing tasks and explicit owner settings on upgrade. Use a bounded correction
and escalation sequence, six workers per root excluding the lead, compact
packets, and one writer per overlapping file set. Extend existing receipts.
Learning recommends policy changes but never installs them automatically.

## Alternatives and consequences

Routing every task through the lead avoids coordination but loses useful
independent work. Unbounded escalation hides retry costs. Automatic promotion
from aggregate benchmarks confuses task difficulty and unobserved subscription
consumption. This policy instead counts acceptance, review, and later rework.
It remains a hypothesis, not a demonstrated allowance saving.

The planner is pure and emits no external effects. The capability-bound validator
remains responsible for spawn eligibility; the lead supplies fresh inventories
and preserves authority gates. Configuration plans are separate from activation
so exact diffs, drift checks, backup, and rollback can be verified per host.

The private transcript brief consumes redacted learning summaries separately;
its sources, transcripts, and account state never enter the public kit.
