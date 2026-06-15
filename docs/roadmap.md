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
