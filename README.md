# cms-truth-docs

Documentation for the CMS **MC-truth graph** prototype (`PhysicsTools/TruthInfo`),
built with [MkDocs](https://www.mkdocs.org/) + Material.

## Build locally

The `Makefile` bootstraps a self-contained virtualenv (with a known-good
Python 3.12) and installs the pinned requirements, so the build never depends on
whatever `mkdocs`/`pip` happen to be on `PATH`:

```bash
make serve            # live preview at http://127.0.0.1:8000 (auto-bootstraps .venv)
make build            # strict static build into site/
make deploy           # build + push to the gh-pages branch
make clean            # remove .venv and site/
```

Override the interpreter if the default cvmfs path is unavailable:
`make serve PYTHON=/path/to/python3`.

## Contents

- `docs/index.md` — overview & contact
- `docs/data-model.md` — the three-layer model, `Branch`, associator, selector
- `docs/usage.md` — enabling the producers and a worked tour of the API
- `docs/examples.md` — guided walkthroughs of two real events (Tau and Z→μμ)
- `docs/findings.md` — discovered behavior & the changes made
- `docs/replacing-truth-objects.md` — `Branch` vs `TrackingParticle`/`CaloParticle`/`SimCluster`, with validation
- `docs/validation.md` — relval workflows, topology audits, gallery, reco-side validators (with data)
- `docs/pileup.md` — pileup investigation and the Phase-A/B mixing work
- `docs/optimization.md` — implementation characteristics (applied performance/layout design)
- `docs/roadmap.md` — not-yet-done work
