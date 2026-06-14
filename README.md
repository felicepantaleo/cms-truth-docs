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

- `docs/index.md` — overview & PR summary
- `docs/data-model.md` — the three-layer model, `Branch`, associator, selector
- `docs/findings.md` — discovered behavior & the changes made
- `docs/replacing-truth-objects.md` — `Branch` vs `TrackingParticle`/`CaloParticle`/`SimCluster`, with validation
- `docs/validation.md` — relval workflows, topology audits, gallery (with data)
- `docs/pileup.md` — pileup investigation and the Phase-A/B mixing work
- `docs/optimization.md` — CPU/memory/storage/readability review
- `docs/roadmap.md` — next steps
