# CAPS Glossary

## Routing decision

A machine-readable record that selects the GPT-5.6 model and thinking level for
one worker lane, explains the choice, and includes its authority envelope.

## Operational route

The GPT-5.6 worker route that can perform the assigned lane within its authority
envelope and proof requirements.

## Advisory fallback

A narrow, non-executing planner, reviewer, or council exception. It requires a
specific reason and never replaces the GPT-5.6 operational worker.

## Authority envelope

The action-time guardrail for a worker: allowed actions, prohibited actions,
required proof, and stop conditions.

## Escalation

The stated condition that requires the worker to stop, report evidence, or ask
the conductor to reroute or expand authority.

## Task state snapshot

A redacted conductor-owned description of the objective, scope, acceptance
criteria, risk, side effects, evidence references, and stop conditions that is
complete enough to route a worker without forwarding raw conversation history.

## Title coordination metadata

A pinned-thread label that helps the user find current work. It can describe
the evidence-supported task state, but it never proves execution or completion.

## Manual title override

An owner-selected title or emoji that automatic title synchronization preserves
until the owner changes or clears it.

## Update channel

A named stream of versioned CAPS release manifests. Each manifest declares the
artifact digest, compatibility range, disruption state, release notes, and
rollback version.
