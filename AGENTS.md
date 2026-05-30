# CAPS Kit Agent Instructions

This repo is a public install kit. Keep it practical, copyable, and safe for people who are not expert programmers.

## Priorities

1. Make the kit easy to clone, inspect, and install.
2. Keep instructions plain and action-oriented.
3. Prefer templates and examples over abstract explanation.
4. Avoid private workspace details, secrets, customer data, or claims that depend on Lennox's local environment.

## Editing Rules

- Use ASCII text unless a file already requires otherwise.
- Keep commands shell-portable for macOS and Linux where practical.
- Do not add dependencies unless the repo truly needs them.
- If a workflow is risky, add an explicit stop condition.
- Test the installer and verification script after changes.

## Done Definition

A change is done when:

- The relevant templates or docs are updated.
- The README still gives a clean clone-to-install path.
- `./scripts/verify.sh` passes.
- Any changed shell scripts run without syntax errors.
