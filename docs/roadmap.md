# Roadmap

This page lists the work that is **not yet done**. For the data model, the
validation results, and the already-applied performance work, see the respective
pages. See [Implementation characteristics](optimization.md) in particular for
the optimizations that are already applied.

## Pileup / Phase B

1. **Full GEN+SIM for the signal** in `TruthGraphAccumulator`. Today
   `collapseSignalGen=false` leaves the signal SIM-only. This item requires
   factoring the build of `TruthGraphProducer` into a shared helper. The
   accumulator can then call that helper for the signal sub-event. After the
   refactor, verify that the no-PU cppunit and a no-PU graph diff stay identical.
2. **B3, premix-library storage** of each minbias raw `TruthGraph` (plus the
   per-particle hit index). That storage makes the stage-2 overlay consistent by
   construction. This item only matters if someone wants truth under premixing.
   Today `premix_stage2` drops the accumulator and the build, because premixed
   pileup carries no raw pileup `SimTrack`s.
3. **B4, CPfromPU-style simplification**: thresholded or collapsed pileup for
   PU200 storage. This mirrors `removeCPFromPU`.

(B2, the mixed hit index accumulated per sub-event, is done. The producer builds
the index after mixing, from the merged sim-hits of the accumulator. Every hit
carries a key of its `EncodedEventId` together with the `SimTrack` trackId.
Sub-events therefore cannot collide. See [Pileup](pileup.md).)

## Validation

- **Disjoint "interesting particles" reference for the reco-side validators.** The
  generic reco-side efficiency/merge/duplicate is only well-defined against a
  disjoint (antichain) set of truth branches. A flat PDG-id selection is a
  sufficient antichain only for non-showering species (muons). The two reco-side
  modules therefore stay **opt-in**, that is, out of the default validation
  sequence. They stay opt-in until the physically correct, detector-dependent
  reference is wired in. That reference is the `BranchSelector` "interesting
  particles" antichain (`CaloParticle`-like for calo, `TrackingParticle`-like for
  tracking). See the caveat in
  [Validation](validation.md#reco-side-validators-generic-hit-exposure).

## Storage / data layout (deliberate changes, not mechanical)

1. **M3: sparse, layout-agnostic association storage** in `TruthGraph`. Today
   `simTrackToGen`/`simTrackToVtx`/`simVtxToGen` are full-length over all nodes.
   Ranging them by a single base requires contiguous SimTrack/SimVertex nodes.
   That condition holds for the signal producer. It does **not** hold for the
   per-sub-event layout of the accumulator. A naive range would silently corrupt
   mixed and pileup associations. The fix is a sparse sorted
   `vector<pair<nodeId,target>>` plus binary search, like the DetId-map rework.
   The fix keeps the `nodeSim*` API. It touches `TruthGraph.h`, all three
   producers and the dictionary. Guard the change with the topology audit.
2. **M4: subgraph hit-storage reduction.** The subgraph hit CSR re-stores
   `{detId, recHitIndex, energy}` for every ancestor (≈ Σ subtree hits). The
   `Branch` view and the `BranchHitAssociator` merge-join rely on a contiguous
   coalesced span. Storing subgraph spans as indices into the direct-hit storage
   breaks that span. The item therefore needs a contract decision: compute on
   read, or store coalesced. The cheap safe first step is to drop `recHitIndex`
   from subgraph storage and to resolve it again from the DetId map.

## Cleanup

- **M1**: `Branch` reruns a full BFS `traverse()` on every accessor.
  `invisibleEnergy()` runs it twice. Compute `stableLeaves()` once and derive all
  kinematics in one pass. Offer an opt-in materialized branch for loops over many
  branches.
- **M6**: `TruthGraphProducer::produce` and `TruthLogicalGraphProducer::produce`
  are large multi-phase functions. Extract the phases to make them testable.
- **L1-L5**: use `std::ranges` transform views for one-shot view-returning
  helpers. Avoid redundant reco-hit copies in `bestBranches`. Cap the diagnostic
  O(n²) scan in `TruthGraphTopologyChecker`. **Refresh the stale package README**:
  it still references `TruthLogicalGraphHitIndexProducer` and an old `python/`
  layout, and it lists `truth::Branch` as "not yet implemented". De-duplicate the
  `EncodedEventId` pack/unpack helper into one shared header.

## Multi-surface boundary crossings (CMSSW-core follow-up PR)

Each particle can carry trajectory **checkpoints**. A checkpoint is a position
and momentum snapshot where Geant4 records a boundary crossing. The code stores
it as `Checkpoint{checkpointId, position, momentum}` on `ParticleData`. Today
there is exactly **one** crossing: the **Tracker → CALO** boundary. We want
several surfaces, for example ECAL → HCAL, the muon system entrance, and the
HGCAL front face. Each surface carries its own 4-position and 4-momentum. A
consumer can then sample a branch where it enters each subdetector.

**How the code produces the single crossing today.** Geant4 detects the crossing
in `SimG4Core/Application/src/SteppingAction.cc`. It compares the pre-step and
post-step **physical volumes** against the names configured in
`SimG4Core/Application/python/g4SimHits_cfi.py` (`SteppingAction.TrackerName = 'Tracker'`,
`CaloName = 'CALO'`). That file already holds a `BTLName = 'BarrelTimingLayer'`,
and `SaveCaloBoundaryInformation = True` under the Phase-2 modifier. On the
transition Geant4 calls `TrackInformation::setCrossedBoundary(...)`
(`SimG4Core/Notification/interface/TrackInformation.h`). The chain propagates
that call through `TrackWithHistory` → `TmpSimTrack` → the persistent `SimTrack`
(`DataFormats/Track/interface/SimTrack.h`). There it lands as a **single**
`idAtBoundary_` / `positionAtBoundary_` / `momentumAtBoundary_` plus one
`crossedBoundary_` bit.

**Why config alone is not enough.** `SimTrack` stores exactly one crossing.
Multiple surfaces therefore need a data-format change *and* a `SimG4Core` change:

1. **`SimTrack` (DataFormats/Track)**: replace the single boundary fields with a
   `std::vector<BoundaryCrossing>` (`{int surfaceId; XYZTLorentzVectorF position;
   XYZTLorentzVectorF momentum;}`). This needs a class-version bump and schema
   evolution.
2. **`SteppingAction`**: accept a list of volume (or `G4Region`) pairs instead of
   the single Tracker/CALO pair. Detect every configured transition. Call
   `addBoundaryCrossing(surfaceId, pos, mom)` for each one.
3. **`TrackInformation` / `TrackWithHistory` / `SimTrackManager`** (SimG4Core/Notification):
   carry a vector of crossings, and transfer all of them to the final `SimTrack`.
4. **GEN-SIM re-run**: the simulation produces the boundary information at
   simulation time. Existing samples therefore need a new production to gain the
   new surfaces.

**Geometry hooks.** Named physical volumes already exist for `Tracker`, `CALO`
and `BarrelTimingLayer`. `G4Region`s such as `EcalRegion` / `HcalRegion` / the
HGCAL regions also exist, but the code currently uses them only for physics cuts.
Extending `SteppingAction` to test `G4Region` pointers would expose ECAL↔HCAL and
HGCAL-front surfaces.

On the truth-graph side the change is small. Each extra `SimTrack` crossing
becomes one more `Checkpoint` on the particle, with the surface id as
`checkpointId`. The existing `checkpoints()` / `checkpoint(id)` API exposes it.
The logical graph needs no schema change.
