# ADR 0001: Public Routing Engine, Private Profile

## Status

Accepted

## Context

CAPS needs reusable GPT-5.6 routing rules, while real operators may calibrate
those rules with private tasks, timings, costs, and work history. Publishing the
profile would leak context; keeping the engine private would prevent reuse.

## Decision

CAPS publishes the generic routing schema, matrix, authority-envelope contract,
sanitized examples, and installer support. Personalized fixtures, thresholds,
receipts, identities, paths, and source material live in a separate private
profile. The public engine may consume a profile but never vendors its contents.

## Consequences

Public installs remain useful without private data. Personalized routing needs a
separate versioned profile and an explicit host-install verification step.
