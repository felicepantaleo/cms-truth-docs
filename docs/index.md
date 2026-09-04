# CMS MC-Truth Graph

## What problem this solves

A simulated CMS event knows exactly what happened. The generator wrote every particle it produced. Geant4 followed each particle through the detector and recorded every energy deposit. Nothing is hidden.

Reconstruction cannot use that knowledge directly. It has to be compared against it. Every efficiency, every fake rate and every training label answers the same question: which simulated particle should this reconstructed object correspond to?

CMS has answered that question with frozen truth objects. `TrackingParticle` describes the tracker view. `CaloParticle` and `SimCluster` describe the calorimeter view. `GenParticle` describes the generator view. Each is a separate collection, built at simulation time with thresholds decided then, and each covers one part of the detector. A particle's tracker footprint sits in one object and its calorimeter footprint in another, with no link between them. The decay history that connects them is gone, so a question like "do these two clusters come from the same neutral pion" cannot be asked. Changing a threshold means producing the samples again.

## What the truth graph is

The truth graph keeps the event history itself, as a graph, in one place. Particles and vertices are the nodes. Production and decay are the edges. Each particle carries its own detector hits, and also the hits of everything it produced, so one node describes a particle across the whole detector.

The frozen truth objects then become views on that graph rather than separate collections. You choose the truth object you need when you analyse the event, not when you simulate it. A view of the calorimeter-entering particles is what `CaloParticle` gave you. A view of the charged particles in the tracker is what `TrackingParticle` gave you. A view that nobody ever wrote is equally available, and it costs a query rather than a new production.

Three properties follow, and they are the point of the design:

- **One particle, one node, whole detector.** Tracker hits, calorimeter hits, muon hits and timing hits hang off the same object.
- **The history is navigable.** You can walk from a particle to its parents, its children or its whole decay branch, and you can ask two particles for their common ancestor.
- **Truth definitions become named and testable.** A truth level is a written rule, not a threshold frozen in a producer, so software can recompute it and check it. That check has already found real defects.

## Where to start

If you want to understand the design, read [Data model](data-model.md). If you want to run it, read [How to use the graph](usage.md). If you want to see it on real events, read [Worked examples](examples.md).

!!! warning "Status: under active development"
    The two packages `SimDataFormats/TruthInfo` and `PhysicsTools/TruthInfo` are in `CMSSW_20_1_X`. The work is Phase-2 only. The `enableTruth` process modifier gates the chain, and the Run4 eras apply it from `Phase2C17I13M9` onwards, so a standard Run4 workflow builds the truth graph during digitisation and stores it. Run2 and Run3 workflows are unaffected. One change is not gated: the `g4SimHits` `ReconnectDroppedAncestors` default, which is a detector-neutral fix of the simulated vertex connectivity and applies to every sample. See [Pileup](pileup.md) for the default wiring.

    Two layers are not in the release yet. The association layer (`SimGeneral/TruthGraphAssociatorProducers`) and the DQM package `Validation/TruthInfo` live on the `truth-adaptive-associator-v1` and `truth-adaptive-associator` branches. Pages that describe them say so.

    The interfaces still change. Check a signature against the headers before you rely on it.

## The three layers

The graph is built in three steps. Each layer stays simple, and the layer above adds meaning.

```
HepMC2/HepMC3 + SimTrack/SimVertex
        |  TruthGraphProducer
        v
1. TruthGraph        (raw)      the generator and simulation records as one graph,
        |                       still close to the input types
        |  TruthLogicalGraphProducer
        v
2. truth::Graph      (logical)  particles and vertices, generator and simulation
        |                       merged into one history, with a navigation API
        |  LogicalGraphHitIndexProducer (+ DetIdToRecHitMapProducer)
        v
3. truth::LogicalGraphHitIndex  the detector hits of each particle, its own hits
                                and those of everything it produced
```

Three helpers work on top of the logical graph. They are ordinary classes, not event products.

- **`truth::Branch`** is a particle together with a chosen part of its decay history. The code computes it on demand, so a branch costs nothing to store.
- **`truth::BranchHitAssociator`** matches any reconstructed object to a branch through shared detector hits.
- **`truth::BranchSelector`** applies the kinematic and species cuts that define a physics denominator.

## What the work adds to CMSSW

| Area | What |
|---|---|
| New package | `SimDataFormats/TruthInfo`: the data model (`TruthGraph`, `truth::Graph`, `truth::LogicalGraphHitIndex` and their payload types) |
| New package | `PhysicsTools/TruthInfo`: producers, dumpers, flat tables, the `Branch` view, hit associator, selector, tests |
| New producer | `SimCalorimetry/HGCalAssociatorProducers`: `DetIdToRecHitMapProducer` and `DetIdRecHitMap`, which are not HGCal-specific |
| New modifier | `Configuration/ProcessModifiers/enableTruth_cff` |
| New sequence | `Validation/Configuration/truthPrevalidation_cff` |
| Modified: default wiring | `Configuration/Eras` (`enableTruth` on `Phase2C17I13M9`, excluded by `Util_fastSimPhase2_cff`), `Digi_cff.py` (build after mixing), `digitizers_cfi.py` (the accumulator), `EventContent_cff.py` (the stored products) |
| Modified: validation | `globalValidation_cff.py`, `postValidation_cff.py`, `upgradeWorkflowComponents.py` (the `.88` workflow variant) |
| Modified: ungated | `g4SimHits_cfi.py` and `SimTrackManager` (`ReconnectDroppedAncestors`) |

## All pages

- [Data model](data-model.md): the three layers, the branch view, the associator and the selector.
- [How to use the graph](usage.md): how to enable the producers, and a tour of the navigation, selection and hit-matching API.
- [Worked examples](examples.md): two real events followed step by step, a tau and a Z to two muons.
- [Interface](interface.md): the precise signatures.
- [Findings and changes](findings.md): what we found in the existing simulation record, what we changed, and why.
- [Replacing truth objects](replacing-truth-objects.md): how a branch stands in for `TrackingParticle`, `CaloParticle` and `SimCluster`, with the measured agreement.
- [Validation](validation.md): the relval workflows, the topology audits, the graph gallery and the reconstruction-side validators.
- [Pileup](pileup.md): how truth survives event mixing.
- [Implementation characteristics](optimization.md): the layout and performance choices that are already applied.
- [Resource cost](resource-cost.md): the measured CPU and storage cost.
- [Roadmap](roadmap.md): what comes next.

## Contact

This is a prototype. It is not yet open to external contributions. Questions and feedback are welcome. Send them to the author: **Felice Pantaleo** (CERN), [felice.pantaleo@cern.ch](mailto:felice.pantaleo@cern.ch).
