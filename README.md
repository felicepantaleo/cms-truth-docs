# cms-truth-docs

Documentation for the CMS **MC-truth graph** prototype (`PhysicsTools/TruthInfo`),
built with [MkDocs](https://www.mkdocs.org/) + Material.

## Build locally

```bash
pip install -r requirements.txt
mkdocs serve          # live preview at http://127.0.0.1:8000
mkdocs build          # static site into site/
```

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
