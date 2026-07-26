# CMS MC-Truth Graph

A prototype **MC-truth graph** for CMS: a single, navigable, event-level graph of
the generator + simulation truth history, with calorimeter/tracker hit indices
layered on top. The goal is to let reconstruction and validation code reason about
truth in terms of **stable physics abstractions** — particles, vertices, decay
branches, hits — instead of depending directly on the storage details of
`GenParticle`, `SimTrack`, `GenVertex`, `SimVertex`, `PCaloHit`/`PSimHit`, and the
legacy truth objects (`TrackingParticle`, `CaloParticle`, `SimCluster`).

!!! warning "Status: under active development"
    The packages are in `CMSSW_20_1_X`. It is **Phase-2 only**. The chain is gated
    behind the `enableTruth` process modifier, which the Run4 eras apply from
    `Phase2C17I13M9` onwards, so the truth graph is built at DIGI and persisted in
    the standard Run4 workflows; Run3 and Run2 workflows are unaffected. The one
    ungated change is the `g4SimHits` `ReconnectDroppedAncestors` default, a
    detector-neutral SimVertex connectivity fix applied to every sample. See
    [Pileup](pileup.md) for the default-for-Run4 wiring. Interfaces are still
    evolving: check a signature against the headers before relying on it.

## What this adds

Two packages, `SimDataFormats/TruthInfo` for the data model and
`PhysicsTools/TruthInfo` for the analysis layer, plus a `SimHitToRecHitMap`
producer, the `enableTruth` modifier and a validation sequence. The pre-existing
files that are touched are listed below.

| Area | What |
|---|---|
| New package | `SimDataFormats/TruthInfo`: the data model (`TruthGraph`, `truth::Graph`, `truth::LogicalGraphHitIndex` and their payload types) |
| New package | `PhysicsTools/TruthInfo`: producers, dumpers, flat tables, the `Branch` view, hit associator, selector, tests |
| New producer | `SimCalorimetry/HGCalAssociatorProducers`: `SimHitToRecHitMapProducer` + `DetIdRecHitMap` (not HGCal-specific) |
| New modifier | `Configuration/ProcessModifiers/enableTruth_cff` |
| New sequence | `Validation/Configuration/truthPrevalidation_cff` |
| Modified: default-on wiring | `Configuration/Eras` (`enableTruth` on `Phase2C17I13M9`, excluded by `Util_fastSimPhase2_cff`), `Digi_cff.py` (build after mixing), `digitizers_cfi.py` (the accumulator), `EventContent_cff.py` (the truth keeps) |
| Modified: validation | `globalValidation_cff.py`, `postValidation_cff.py`, `upgradeWorkflowComponents.py` (`.88` workflow variant) |
| Modified: ungated | `g4SimHits_cfi.py` + `SimTrackManager` (`ReconnectDroppedAncestors`) |

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
