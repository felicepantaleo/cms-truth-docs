# Roadmap

What is **not yet done**. For the data model, the validation results, and the
already-applied performance work, see the respective pages — in particular
[Implementation characteristics](optimization.md) for the optimizations that have
landed.

## Pileup / Phase B

1. **Full GEN+SIM for the signal** in `TruthGraphAccumulator`
   (`collapseSignalGen=false` currently leaves the signal SIM-only). Requires
   factoring `TruthGraphProducer`'s build into a shared helper so the accumulator
   can call it for the signal sub-event; verify the no-PU cppunit + a no-PU graph
   diff stay identical after the refactor.
2. **B2 — mixed hit index**: accumulate per sub-event, consistent with the digis.
3. **B3 — premix-library storage** of each minbias raw `TruthGraph` (+ per-particle
   hit index) so the stage-2 overlay is consistent by construction.
4. **B4 — CPfromPU-style simplification**: thresholded/collapsed pileup for PU200
   storage (mirroring `removeCPFromPU`).

## Validation

- **Wire the Branch validators into the release sequences.** The DQM analyzers,
  associators and harvesters exist and run standalone; hooking them into
  `globalValidation` / `postValidation` behind `enableTruth` is still pending — see
  [Validation](validation.md).
- **Disjoint "interesting particles" reference for the reco-side validators.** The
  generic reco-side efficiency/merge/duplicate is only well-defined against a
  disjoint (antichain) set of truth branches. A flat PDG-id selection is a
  sufficient antichain only for non-showering species (muons), so the two reco-side
  modules are kept **opt-in** (out of the default validation sequence) until the
  physically correct, detector-dependent reference — the `BranchSelector`
  "interesting particles" antichain (`CaloParticle`-like for calo,
  `TrackingParticle`-like for tracking) — is wired in. See the caveat in
  [Validation](validation.md#reco-side-validators-generic-hit-exposure).

## Storage / data layout (deliberate changes, not mechanical)

1. **M3 — sparse, layout-agnostic association storage** in `TruthGraph`. Today
   `simTrackToGen`/`simTrackToVtx`/`simVtxToGen` are full-length over all nodes;
   ranging them by a single base requires contiguous SimTrack/SimVertex nodes, which
   holds for the signal producer but **not** for the accumulator's per-sub-event
   layout — a naive range would silently corrupt mixed/pileup associations. The fix
   is sparse sorted `vector<pair<nodeId,target>>` + binary search (like the
   DetId-map rework), keeping the `nodeSim*` API; touches `TruthGraph.h`, all three
   producers and the dictionary. Guard with the topology audit.
2. **M4 — subgraph hit-storage reduction.** The subgraph hit CSR re-stores
   `{detId, recHitIndex, energy}` for every ancestor (≈ Σ subtree hits). Storing
   subgraph spans as indices into the direct-hit storage breaks the contiguous
   coalesced span the `Branch` view and `BranchHitAssociator` merge-join rely on, so
   it needs a compute-on-read vs store-coalesced contract decision; the cheap safe
   first step is to drop `recHitIndex` from subgraph storage and re-resolve it from
   the DetId map.

## Cleanup

- **M1** — `Branch` reruns a full BFS `traverse()` on every accessor
  (`invisibleEnergy()` runs it twice). Compute `stableLeaves()` once and derive all
  kinematics in one pass; offer an opt-in materialized branch for loops over many
  branches.
- **M6** — `TruthGraphProducer::produce` / `TruthLogicalGraphProducer::produce` are
  large multi-phase functions; extract phases for testability.
- **L1–L5** — `std::ranges` transform views for one-shot view-returning helpers;
  avoid redundant reco-hit copies in `bestBranches`; cap the diagnostic O(n²) scan
  in `TruthGraphTopologyChecker`; **refresh the stale package README** (it still
  references `TruthLogicalGraphHitIndexProducer`, an old `python/` layout, and lists
  `truth::Branch` as "not yet implemented"); de-duplicate the `EncodedEventId`
  pack/unpack helper into one shared header.

## Multi-surface boundary crossings (CMSSW-core follow-up PR)

Each particle can carry trajectory **checkpoints** — a position/momentum snapshot
where Geant4 records a boundary crossing (stored as `Checkpoint{checkpointId, position,
momentum}` on `ParticleData`). Today there is exactly **one** crossing: the
**Tracker → CALO** boundary. We want several surfaces (e.g. ECAL → HCAL, the muon
system entrance, the HGCAL front face), each with its own per-surface 4-position /
4-momentum, so a branch can be sampled where it enters each subdetector.

**How the single crossing is produced today.** Geant4 detects it in
`SimG4Core/Application/src/SteppingAction.cc` by comparing the pre- and post-step
**physical volumes** against the names configured in
`SimG4Core/Application/python/g4SimHits_cfi.py` (`SteppingAction.TrackerName = 'Tracker'`,
`CaloName = 'CALO'`; there is already a `BTLName = 'BarrelTimingLayer'`, and
`SaveCaloBoundaryInformation = True` under the Phase-2 modifier). On the transition it
calls `TrackInformation::setCrossedBoundary(...)`
(`SimG4Core/Notification/interface/TrackInformation.h`), which is propagated through
`TrackWithHistory` → `TmpSimTrack` → the persistent `SimTrack`
(`DataFormats/Track/interface/SimTrack.h`), where it lands as a **single**
`idAtBoundary_` / `positionAtBoundary_` / `momentumAtBoundary_` plus one `crossedBoundary_`
bit.

**Why it is not config-only.** `SimTrack` stores exactly one crossing, so multiple
surfaces need a data-format change *and* a `SimG4Core` change:

1. **`SimTrack` (DataFormats/Track)** — replace the single boundary fields with a
   `std::vector<BoundaryCrossing>` (`{int surfaceId; XYZTLorentzVectorF position;
   XYZTLorentzVectorF momentum;}`); a class-version bump and schema evolution.
2. **`SteppingAction`** — accept a list of volume (or `G4Region`) pairs instead of the
   single Tracker/CALO pair, detect every configured transition, and
   `addBoundaryCrossing(surfaceId, pos, mom)` for each.
3. **`TrackInformation` / `TrackWithHistory` / `SimTrackManager`** (SimG4Core/Notification)
   — carry a vector of crossings and transfer all of them to the final `SimTrack`.
4. **GEN-SIM re-run** — boundary information is produced at simulation time, so existing
   samples must be regenerated to gain the new surfaces.

**Geometry hooks.** Named physical volumes already exist for `Tracker`, `CALO` and
`BarrelTimingLayer`; `G4Region`s such as `EcalRegion` / `HcalRegion` / the HGCAL regions
exist but are currently used only for physics cuts — extending `SteppingAction` to test
`G4Region` pointers would expose ECAL↔HCAL and HGCAL-front surfaces.

On the truth-graph side the change is small: each extra `SimTrack` crossing becomes one
more `Checkpoint` (with the surface id as `checkpointId`) on the particle, surfaced
through the existing `checkpoints()` / `checkpoint(id)` API — no logical-graph schema
change needed.
