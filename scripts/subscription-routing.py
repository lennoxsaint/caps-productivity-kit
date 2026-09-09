#!/usr/bin/env python3
"""Bounded routing planner. Produces decisions; never spawns or changes policy.

The caller must bind availability to a fresh capability snapshot with
verify-routing.py before spawn. An accepted attempt means both task checks and
lead review passed, not merely that a worker returned an answer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

TIERS = (('gpt-5.6-luna', 'max'), ('gpt-5.6-sol', 'xhigh'), ('gpt-6-astra', 'medium'))
BLOCKERS = frozenset({'credentials', 'permission', 'source_evidence', 'infrastructure'})
MAX_WORKERS = 6


def unavailable_reason(capabilities, route):
    model = next((m for m in capabilities.get('models', []) if m.get('id') == route[0]), None)
    if model is None:
        return 'unsupported_model'
    if route[1] not in model.get('reasoning_levels', []):
        return 'unsupported_effort'
    for key, reason in [('live', 'not_live'), ('entitled', 'not_entitled'),
                        ('allowed_by_policy', 'policy_blocked')]:
        if model.get(key) is not True:
            return reason
    return None


def next_attempt(attempts, capabilities, *, correction_useful=False, blocker=None,
                 sol_first=False, reason=None):
    """Return the next approved tier, or a terminal state. History is per task."""
    if blocker is not None:
        if blocker not in BLOCKERS:
            raise ValueError('unknown blocker; classify before routing')
        return {'status': 'blocked', 'reason': blocker}
    if sol_first and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError('Sol-first requires a concrete recorded reason')
    counts = [0, 0, 0]
    previous = -1
    for index, attempt in enumerate(attempts):
        tier = attempt.get('tier')
        if type(tier) is not int or tier not in range(3) or tier < previous:
            raise ValueError('invalid or regressive attempt history')
        if attempt.get('outcome') not in {'failed', 'accepted'}:
            raise ValueError('attempt needs failed or verified accepted outcome')
        counts[tier] += 1
        if counts[tier] > (2 if tier == 0 else 1):
            raise ValueError('attempt budget exceeded')
        if attempt['outcome'] == 'accepted':
            if index != len(attempts) - 1:
                raise ValueError('attempts cannot follow accepted completion')
            return {'status': 'complete'}
        previous = tier
    if not attempts:
        tier = 1 if sol_first else 0
        route_reason = reason if sol_first else 'default_worker'
    elif previous == 0 and counts[0] == 1 and correction_useful:
        tier, route_reason = 0, 'targeted_correction'
    else:
        tier, route_reason = previous + 1, 'failed_acceptance'
    skipped = []
    while tier < len(TIERS):
        limitation = unavailable_reason(capabilities, TIERS[tier])
        if limitation is None:
            return {'status': 'ready', 'tier': tier, 'route': list(TIERS[tier]),
                    'reason': route_reason, 'skipped': skipped,
                    'separate_worker': tier == 2, 'fork_turns': 'none'}
        skipped.append({'tier': tier, 'route': list(TIERS[tier]), 'reason': limitation})
        tier += 1
    return {'status': 'unavailable' if skipped else 'exhausted', 'skipped': skipped}


def check_lanes(file_sets, *, active_workers=0, active_file_sets=()):
    """Check declared root-relative write sets, including already active writers.

    Empty sets are read-only. Paths must be resolved by the lead to the same
    workspace (including symlink aliases) before this lexical collision check.
    """
    errors = []
    if type(active_workers) is not int or active_workers < 0:
        return ['active_workers must be a non-negative integer']
    if not isinstance(file_sets, (list, tuple)) or not isinstance(active_file_sets, (list, tuple)):
        return ['write sets must be lists of file lists']
    if len(active_file_sets) > active_workers:
        errors.append('active writer sets exceed declared active workers')
    if len(file_sets) + active_workers > MAX_WORKERS:
        errors.append('six-worker ceiling exceeded (lead excluded)')
    normalized = []
    for files in [*active_file_sets, *file_sets]:
        if not isinstance(files, (list, tuple)) or not all(isinstance(p, str) for p in files):
            errors.append('each write set must be a list of paths')
            continue
        lane = []
        for value in files:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or '..' in path.parts or any(c in value for c in '*?['):
                errors.append('write ownership needs exact root-relative files or directories')
                continue
            lane.append(path)
        normalized.append(lane)
    for index, lane in enumerate(normalized):
        for other in normalized[:index]:
            if any(a == b or a in b.parents or b in a.parents for a in lane for b in other):
                errors.append('overlapping write sets require one writer')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True,
                        help='JSON containing attempts, capabilities, and optional routing arguments')
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text())
    try:
        result = next_attempt(**packet)
    except (TypeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
