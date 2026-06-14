# Roadmap

What is done, and what is next.

## Done

- Three-layer data model (raw `TruthGraph`, logical `truth::Graph`, hit index) +
  `Branch` view, `BranchHitAssociator`, `BranchSelector`.
- Connectivity fix (`PersistencyEmin=0`) and the GEN/SIM **immediate-vertex attach**
  fix (no mega-vertex, no cycles) — see [Findings](findings.md).
- Validated as a replacement for `TrackingParticle` / `CaloParticle` / `SimCluster`
  on eight relval topologies — see [Replacing truth objects](replacing-truth-objects.md).
- Rebased to `CMSSW_20_0_0_pre1` with no behavior change — see [Validation](validation.md).
- Pileup **Phase A** (MixCollection prototype) and **Phase B / B1**
  (`TruthGraphAccumulator`, configurable, in-time pileup by default, collapsed
  pileup GEN) — see [Pileup](pileup.md).

## Next — pileup / Phase B

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

## Next — optimization (from the [review](optimization.md))

In suggested order:

1. **H1** — remove the per-node allocation in `parentsOf`/`childrenOf` (O(N²)→O(V+E)
   on every BFS query).
2. **H5** — replace the `order`-permutation CSR scatter in the mixing producers with
   the proven cursor pattern; add `isConsistent()` to the accumulator.
3. **H3 + H4** — replace the `unordered_map`-per-particle hit-index builder and the
   all-particles inverted index with flat sorted structures.
4. **H2** — drop the dense LCA distance matrix.
5. **M3 / M4 / M5** — shrink the persisted raw/mixed graph, the subgraph hit CSR,
   and the DetId→RecHit map (the flagged pileup scaling risk).

## Housekeeping

- **Refresh the package README** (`PhysicsTools/TruthInfo/README.md`): it still
  references `TruthLogicalGraphHitIndexProducer`, an old `python/` layout, and lists
  `truth::Branch` as "not yet implemented" (it is) — see optimization item L4.
- De-duplicate the `EncodedEventId` pack/unpack helper into one shared header (L5).
