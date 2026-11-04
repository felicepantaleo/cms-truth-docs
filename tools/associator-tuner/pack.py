#!/usr/bin/env python3
"""Closure and packing of a candidates.jsonl file from TruthAdaptiveCandidateDumper.

Implements the rule of BranchHitAssociator::bestAdaptiveBranch in float arithmetic,
checks it against the AdaptiveTight and AdaptiveNominal maps of the same job, checks that
the reduced candidate list gives the same pick as the full list on a scan of working
points, and writes the data file of the page.
"""
import argparse
import json
import os
import sys

import numpy as np


def short(x):
    """Four digits are enough for a displayed quantity. The scores keep nine: the check needs them."""
    return float("%.4g" % x)


def pick(cands, w, ceiling):
    """Index in cands of the adaptive answer, with the float arithmetic of the C++ rule."""
    w = np.float32(w)
    best, best_obj, fallback, fallback_obj = -1, np.inf, -1, np.inf
    for i, c in enumerate(cands):
        obj = np.float32(c[1]) + np.float32(w * np.float32(c[2]))
        if c[2] <= ceiling and obj < best_obj:
            best, best_obj = i, obj
        if obj < fallback_obj:
            fallback, fallback_obj = i, obj
    return best if best >= 0 else fallback


def reduce_front(cands):
    """Drops a candidate when an earlier one has both scores lower or equal.

    The earlier candidate passes every ceiling the later one passes and has an objective
    lower or equal at every weight >= 0, and the argmin keeps the first of equal values.
    """
    kept = []
    for c in cands:
        if not any(k[1] <= c[1] and k[2] <= c[2] for k in kept):
            kept.append(c)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--name", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip", nargs="*", default=[], help="collections checked but not written")
    ap.add_argument("--display-per-event", type=int, default=12, help="tracksters per event that keep every candidate")
    args = ap.parse_args()

    stats = {}
    mismatches = {"tight": 0, "nominal": 0, "reduced": 0, "ceiling1": 0}
    checks = {"tight": 0, "nominal": 0, "reduced": 0}
    scan = [(w, c) for w in (0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0) for c in (0.1, 0.3, 0.6, 0.9, 1.0)]
    collections = {}
    particles_out = []
    nevents = 0
    examples = []

    for line in open(args.input):
        event = json.loads(line)
        evid = event["event"]
        particles = event["particles"]
        evindex = nevents
        nevents += 1
        for name, tracksters in event["collections"].items():
            col = collections.setdefault(name, {"tracksters": [], "display": []})
            st = stats.setdefault(name, {"tracksters": 0, "full": 0, "assignable": 0, "front": 0})
            order = sorted(range(len(tracksters)), key=lambda i: -tracksters[i][0])
            display = set(order[: args.display_per_event])
            for t, tr in enumerate(tracksters):
                raw, em, eta, phi, tight, nominal, cands = tr
                st["tracksters"] += 1
                st["full"] += len(cands)
                assignable = [c for c in cands if c[5]]
                st["assignable"] += len(assignable)
                front = reduce_front(assignable)
                st["front"] += len(front)
                if assignable:
                    got_tight = assignable[pick(assignable, 1.0, 0.6)][0]
                    got_nominal = assignable[pick(assignable, 1.0, 1.0)][0]
                    checks["tight"] += 1
                    checks["nominal"] += 1
                    if got_tight != tight:
                        mismatches["tight"] += 1
                    if got_nominal != nominal:
                        mismatches["nominal"] += 1
                    # A sparse scan is enough: this runs on every trackster.
                    for w, c in scan[(t % len(scan)) :: 11]:
                        checks["reduced"] += 1
                        if assignable[pick(assignable, w, c)][0] != front[pick(front, w, c)][0]:
                            mismatches["reduced"] += 1
                elif tight != -1 or nominal != -1:
                    mismatches["tight"] += tight != -1
                    mismatches["nominal"] += nominal != -1
                col["tracksters"].append(
                    {
                        "e": evindex,
                        "E": round(raw, 3),
                        "eta": eta,
                        "t": tight,
                        "n": nominal,
                        "f": [[c[0], c[1], c[2], short(c[3]), short(c[4])] for c in front],
                        "all": [[c[0], c[1], c[2], short(c[3]), short(c[4]), c[5]] for c in cands] if t in display else None,
                    }
                )
        particles_out.append(particles)
        examples.append(evid)

    # One file per collection, holding only the particle fields and particles the page reads.
    os.makedirs(args.out, exist_ok=True)
    closure = {"checks": checks, "mismatches": mismatches}
    for name, col in collections.items():
        if name in args.skip:
            continue
        used = [set() for _ in particles_out]
        for tr in col["tracksters"]:
            used[tr["e"]].update(str(c[0]) for c in tr["f"])
            used[tr["e"]].update(str(c[0]) for c in tr["all"] or [])
        particles = []
        for i, table in enumerate(particles_out):
            particles.append({k: [table[k][0], table[k][1], table[k][5], table[k][6], table[k][7]] for k in used[i]})
        data = {
            "name": args.name,
            "label": args.label,
            "events": examples,
            "particles": particles,
            "collections": {name: col["tracksters"]},
            "stats": {name: stats[name]},
            "closure": closure,
        }
        with open(os.path.join(args.out, name + ".json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))

    print(json.dumps({"events": nevents, "stats": stats, "checks": checks, "mismatches": mismatches}, indent=1))
    bad = mismatches["tight"] + mismatches["nominal"] + mismatches["reduced"]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
