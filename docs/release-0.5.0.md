# CAPS 0.5.0

This release adds Astra routes while preserving the selected conductor model
and reasoning effort. Sol remains useful for complex bounded work, Luna for
repeatable tasks, and Terra for safely retryable trials or evidence-backed routes.

The automatic limit is three concurrent workers across the root task. Routing
decisions must include the active worker count. Larger teams and nested workers
require an explicit owner request; existing limits and authority gates remain.
Refresh worker inventory before dispatch: a declared count alone is not runtime
enforcement.

Trials require deterministic verification, reversible scope, and a distinct,
available escalation route. High-risk work and external side effects cannot
enter trials. Existing receipts and promotion evidence retain their meaning.
Runtime capability checks still gate every requested model and reasoning level;
unavailable models require explicit substitution reporting.

## Upgrade and rollback

The 0.4.0 updater can consume this release. Clean installation, upgrade using
the actual 0.4.0 updater, local override preservation, and rollback are covered
by the mandatory verification suite. Stable metadata retains 0.4.0 as the
rollback release and 0.3.3 as the minimum compatible updater.

Review the complete diff, run ./scripts/verify.sh, and build with
scripts/build-release.py before publishing. After explicit publication
approval, verify GitHub assets against SHA-256 hashes, stable-channel metadata,
and an updater installation from the published assets.

Experimental context management is a separate, opt-in client/account feature.
This public release does not modify account settings or enable that experiment.
