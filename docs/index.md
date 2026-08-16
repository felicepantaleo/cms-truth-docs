# CMS MC-Truth Graph

This is a prototype **MC-truth graph** for CMS. The truth graph is one navigable,
event-level graph of the generator and simulation truth history. It carries
calorimeter and tracker hit indices on top. The goal is to let reconstruction and
validation code reason about truth in terms of **stable physics abstractions**:
particles, vertices, decay branches, and hits. That code then does not depend
directly on the storage details of the underlying types. Those types are
`GenParticle`, `SimTrack`, `GenVertex`, `SimVertex`, `PCaloHit`/`PSimHit`, and
the legacy truth objects (`TrackingParticle`, `CaloParticle`, `SimCluster`).

!!! warning "Status: under active development"
    The packages are in `CMSSW_20_1_X`. The work is **Phase-2 only**. The
    `enableTruth` process modifier gates the chain. The Run4 eras apply that
    modifier from `Phase2C17I13M9` onwards. The standard Run4 workflows therefore
    build the truth graph at DIGI and persist it. Run3 and Run2 workflows are
    unaffected. One change is not gated: the `g4SimHits`
    `ReconnectDroppedAncestors` default. That change is a detector-neutral
    SimVertex connectivity fix, and it applies to every sample. See
    [Pileup](pileup.md) for the default-for-Run4 wiring. The interfaces are still
    changing. Check a signature against the headers before you rely on it.

## What this adds

The work adds two packages. `SimDataFormats/TruthInfo` holds the data model.
`PhysicsTools/TruthInfo` holds the analysis layer. The work also adds a
`DetIdToRecHitMap` producer, the `enableTruth` modifier, and a validation
sequence. The table below lists the pre-existing files that the work touches.

| Area | What |
|---|---|
| New package | `SimDataFormats/TruthInfo`: the data model (`TruthGraph`, `truth::Graph`, `truth::LogicalGraphHitIndex` and their payload types) |
| New package | `PhysicsTools/TruthInfo`: producers, dumpers, flat tables, the `Branch` view, hit associator, selector, tests |
| New producer | `SimCalorimetry/HGCalAssociatorProducers`: `DetIdToRecHitMapProducer` + `DetIdRecHitMap` (not HGCal-specific) |
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
        │  LogicalGraphHitIndexProducer (+ DetIdToRecHitMapProducer)
        ▼
3. truth::LogicalGraphHitIndex   per-particle calo/tracker hit spans
                                 (direct hits + aggregated subgraph hits)
```

On top of the truth graph:

- **`truth::Branch`** is a subgraph or decay-branch view that the code recomputes
  on demand. It offers configurable closures, kinematics, heavy-flavor tagging,
  pile-up provenance, and relations.
- **`truth::BranchHitAssociator`** does generic hit-based reco↔truth matching. It
  works for any object that exposes a `truthHits()` method.
- **`truth::BranchSelector`** does kinematic, pdgId, charge, and signal-only
  selection.

## Read next

- [Data model](data-model.md): the layers, the `Branch` view, the associator and selector.
- [How to use the graph](usage.md): how to enable the producers, plus a worked tour of the navigation, selection, and hit-matching API.
- [Worked examples](examples.md): guided walkthroughs of two real events (Tau and Z→μμ).
- [Findings & changes](findings.md): the existing behavior we discovered, what we changed, and why.
- [Replacing truth objects](replacing-truth-objects.md): how `Branch` can stand in for `TrackingParticle` / `CaloParticle` / `SimCluster`, with validation.
- [Validation](validation.md): the relval workflows, topology audits, the DOT gallery, and the reco-side validators, with data.
- [Pileup](pileup.md): the pileup investigation and the Phase-A/B mixing work.
- [Implementation characteristics](optimization.md): the applied performance and layout design choices.
- [Roadmap](roadmap.md): the work that comes next.

## Contact

This is a prototype. It is **not yet open to external contributions**. Questions
and feedback are welcome. Send them to the author: **Felice Pantaleo** (CERN),
[felice.pantaleo@cern.ch](mailto:felice.pantaleo@cern.ch).
