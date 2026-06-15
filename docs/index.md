# CMS MC-Truth Graph

A prototype **MC-truth graph** for CMS: a single, navigable, event-level graph of
the generator + simulation truth history, with calorimeter/tracker hit indices
layered on top. The goal is to let reconstruction and validation code reason about
truth in terms of **stable physics abstractions** — particles, vertices, decay
branches, hits — instead of depending directly on the storage details of
`GenParticle`, `SimTrack`, `GenVertex`, `SimVertex`, `PCaloHit`/`PSimHit`, and the
legacy truth objects (`TrackingParticle`, `CaloParticle`, `SimCluster`).

!!! warning "Status: prototype, under heavy development"
    This documents work in progress on the branch
    `felicepantaleo:truthGraph_CMSSW_20` (developed on `CMSSW_20_0_0_pre1`, also
    validated on `CMSSW_17_0_0_pre2`). It is **Phase-2 only**. Everything is gated
    behind a new `enableTruth` process modifier, so standard workflows are
    unaffected.

## What this adds

A new package `PhysicsTools/TruthInfo` (plus a `SimHitToRecHitMap` producer, an
`enableTruth` modifier, and a validation sequence). The work is purely additive:
only a handful of pre-existing files are touched, all behind `enableTruth`.

| Area | What |
|---|---|
| New package | `PhysicsTools/TruthInfo`: data model, producers, dumpers, flat tables, the `Branch` view, hit associator, selector, tests |
| New producer | `SimCalorimetry/HGCalAssociatorProducers`: `SimHitToRecHitMapProducer` + `DetIdRecHitMap` (not HGCal-specific) |
| New modifier | `Configuration/ProcessModifiers/enableTruth_cff` |
| New sequence | `Validation/Configuration/truthPrevalidation_cff` |
| Modified (gated) | `globalValidation_cff.py`, `g4SimHits_cfi.py` (`PersistencyEmin=0`), `upgradeWorkflowComponents.py` (`.88` workflow variant) |

## The three-layer model at a glance

```
HepMC2/HepMC3 + SimTrack/SimVertex
        │  TruthGraphProducer
        ▼
1. TruthGraph        (raw)      compact typed-node CSR: GenEvent/GenVertex/
        │                       GenParticle/SimVertex/SimTrack + GenToSim edges
        │  TruthLogicalGraphProducer
        ▼
2. truth::Graph      (logical)  bipartite Particle <-> Vertex CSR; GEN+SIM merged,
        │                       intermediate GEN copies collapsible; navigation API
        │  LogicalGraphHitIndexProducer (+ SimHitToRecHitMapProducer)
        ▼
3. truth::LogicalGraphHitIndex   per-particle calo/tracker hit spans
                                 (direct hits + aggregated subgraph hits)
```

On top of the graph:

- **`truth::Branch`** — a recomputed-on-demand subgraph / decay-branch view with
  configurable closures, kinematics, heavy-flavor tagging, pile-up provenance, and
  relations.
- **`truth::BranchHitAssociator`** — generic hit-based reco↔truth matching for any
  object that exposes a `truthHits()` method.
- **`truth::BranchSelector`** — kinematic / pdgId / charge / signal-only selection.

## Read next

- [Data model](data-model.md) — the layers, the `Branch` view, the associator and selector.
- [How to use the graph](usage.md) — enabling the producers and a worked tour of the navigation, selection, and hit-matching API.
- [Worked examples](examples.md) — guided walkthroughs of two real events (Tau and Z→μμ).
- [Findings & changes](findings.md) — the existing behavior we discovered and what we changed (and why).
- [Replacing truth objects](replacing-truth-objects.md) — how `Branch` can stand in for `TrackingParticle` / `CaloParticle` / `SimCluster`, with validation.
- [Validation](validation.md) — the relval workflows, topology audits, the DOT gallery, and the reco-side validators, with data.
- [Pileup](pileup.md) — the pileup investigation and the Phase-A/B mixing work.
- [Implementation characteristics](optimization.md) — the applied performance/layout design choices.
- [Roadmap](roadmap.md) — what's next.

## Contact

This is a prototype and is **not yet open to external contributions**. Questions and
feedback are welcome and go to the author: **Felice Pantaleo** (CERN),
[felice.pantaleo@cern.ch](mailto:felice.pantaleo@cern.ch).
