# Optimization review

A performance/quality pass over the package (CPU, memory, storage, readability,
comments). Findings are **prioritized and actionable**. Implemented so far:
**H1, H3, H4, H5** (`fce7b87314b`), **H2** (`f523cd1ace0`), **M5** (`d2a67b5cb0c`)
and **M7** (`1d3b7b5e7d3`). Still open: the storage items **M3/M4** (reclassified
below as deliberate design changes, not mechanical fixes) and the **M1/M6/L**
cleanup (see the [Roadmap](roadmap.md)). The persistent-data design is sound — the
items below are concentrated in the navigation layer, the hit-index builder, and
two robustness fixes in the mixing producers.

## Already well done (keep)

- **CSR everywhere** for the persistent products (raw `TruthGraph`, bipartite
  `truth::Graph`, the hit index) — cache-friendly, no per-node pointer chasing.
- **`std::span` accessors** — zero-copy navigation into the CSR storage.
- **Sorted merge-join** in `BranchHitAssociator::bestBranches`, relying on the
  builder's DetId-sorted span invariant — the correct linear algorithm.
- **`reserve()` discipline**, path-halving union-find, correct
  `edm::global`/`edm::stream` concurrency choices, `buildCSR` counting-sort scatter.
- The `Branch` view is deliberately non-owning / recomputed on demand.

## High priority

| # | Issue | Fix | Impact |
|---|---|---|---|
| **H1** ✅ | `parentsOf`/`childrenOf` (`Graph.cc:218-256`) allocate + zero-fill a `vector(nParticles)` dedup buffer **and** return a heap vector — and every BFS (`ancestors`, `descendants`, `firstAncestorWithPdgId`, `firstCommonAncestor`, `lowestCommonAncestor`) calls them per dequeued node → **O(N²) time + allocation** | span-returning core helpers that push into a caller buffer (degree is tiny; dedup with a linear scan); BFS keeps its own single `visited` array | **Order-of-magnitude** speedup on every ancestor/descendant/LCA query; the single most important finding |
| **H2** ⬜ | `firstCommonAncestorOf`/`lowestCommonAncestor` scan all `nParticles`; LCA allocates a dense `k×N` int distance matrix | iterate only the visited set; reuse one `dist` buffer + per-ancestor hit counts | Large for pileup-size events; the "which particle did this jet come from" hot path |
| **H3** ✅ | `LogicalGraphHitIndexBuilder` keeps **one `unordered_map` per particle × 4 channels** (`~4·nParticles` hash tables); subgraph aggregation re-hashes each hit ~depth times | per-particle `vector<Hit>` + sort/coalesce; aggregate subgraphs by k-way merge of children's sorted spans | Large alloc/cache win in the **hottest** producer (full calo+tracker hit volume) |
| **H4** ✅ | `BranchHitAssociator` with default (empty) candidate roots treats **every** particle as a root and inserts every ancestor's subgraph hits into the inverted index ≈ O(hits×depth) | don't default to all particles (use direct-hit owners / selector roots); flat sorted `vector<pair<detId,root>>` + binary search | Large memory/CPU win on the documented default path |
| **H5** ✅ | The mixing producers (`TruthGraphAccumulator.cc:311-327`, `TruthGraphMixedProducer.cc:179-196`) build CSR via an `order`-permutation scatter (fragile; relies on non-stable sort matching offsets); the accumulator never calls `isConsistent()` before `put` | use the proven `cursor=offsets; pos=cursor[src]++` scatter (as in `buildCSR`); add `isConsistent()` to the accumulator | Removes a correctness landmine in the **largest** product (mixed signal+pileup); drops an O(E log E) sort |

### Implemented (commit `fce7b87314b`)

H1, H3, H4 and H5 landed as one pure-performance commit on top of Phase-B B1.
What was done, and where it deviated from the proposal above:

- **H1** — `parentsOf`/`childrenOf` now delegate to allocation-free
  `appendParents`/`appendChildren` cores that push immediate-neighbour ids into a
  caller buffer (callers that need uniqueness do a tiny linear dedup); the
  BFS/LCA traversals (`ancestorsOf`, `descendantsOf`, `firstAncestorWithPdgIdOf`,
  `firstCommonAncestorOf`, `lowestCommonAncestor`) reuse a single buffer plus
  their own `dist`/`seen` array instead of allocating a `vector(nParticles)` per
  dequeued node. Returned sets and order are unchanged.
- **H3** — the four per-particle `unordered_map<detId, accumulator>` hit maps are
  replaced by flat `vector<Hit>` lists, coalesced (sort by detId + sum) lazily;
  subgraphs aggregate by appending each child's already-coalesced span and
  coalescing once. Hit sets, counts, recHit indices and recHit/tracker energies
  are bit-identical to the hash-based build. Summed **sim-hit energies** agree
  only to float **reassociation** (~1e-7 relative): the new sum runs in
  deterministic detId order, whereas the old `unordered_map` summed in
  (non-portable) hash-bucket order — so the new value is the more reproducible of
  the two. The cppunit tolerance (`1e-6`) covers it.
- **H4** — the inverted index and per-cell energy map are now flat, sorted
  CSR-style arrays looked up by binary search (`cellRootsKeys_`/`Offsets_`/
  `cellRoots_`, `cellEnergyKeys_`/`Values_`). The **all-particles default was
  deliberately kept**: restricting the candidate roots (the other half of the
  original H4 proposal) would change matching semantics and break the calo
  validator, which matches reco objects against *ancestor* CaloParticles. So H4
  here is the index-flattening only; root-restriction is left as a separate,
  semantics-changing follow-up.
- **H5** — both mixing producers build the out-edge CSR with the proven
  `cursor = offsets; pos = cursor[src]++` counting-sort scatter (no sort, no
  permutation vector), and the accumulator now asserts `isConsistent()` before
  `put`.

**Validation (old-vs-new):** clean from-scratch rebuild; 31 cppunit tests pass;
library topology audit on 8 Run4 relval samples (`cycles=0, multiProd=0`, one
component/event); branch-replacement validator on TTbar (CaloParticle/SimCluster/
TrackingParticle all mapped, completeness=1); the gallery dump's per-particle
`nParents`/`nChildren` and hit counts/sets/recHit-indices/recHit-energies are
bit-identical to the pre-change dumps; the pile-up accumulator re-runs to a
consistent, clean DAG. `code-format` + `code-checks` clean.

## Medium priority

- **M1** — `Branch` reruns a full BFS `traverse()` on every accessor; `invisibleEnergy()` runs it **twice** (`p4`+`visibleP4`). Compute `stableLeaves()` once and derive all kinematics in one pass; offer an opt-in materialized branch for loops over many branches.
- **M3** ⏸ **deferred (needs design, not mechanical)** — `TruthGraph` stores `simTrackToGen`/`simTrackToVtx`/`simVtxToGen` full-length over **all** nodes. Ranging them by a single base requires SimTrack/SimVertex nodes to be **contiguous**, which holds for the signal `TruthGraphProducer` but **not** for the accumulator's per-sub-event layout — so a naive range would silently corrupt the mixed/pileup associations. The layout-agnostic fix is sparse sorted `vector<pair<nodeId,target>>` + binary search (like M5), keeping the `nodeSim*` accessor API; it touches `TruthGraph.h`, all three producers and the dictionary. Worth doing, but as a deliberate change with the topology audit as the guard.
- **M4** ⏸ **deferred (contract change)** — the subgraph hit CSR re-stores `{detId, recHitIndex, energy}` for every ancestor (≈ Σ subtree hits). Storing subgraph spans as indices into the direct-hit storage breaks the `O(1)` contiguous coalesced span that the `Branch` view and `BranchHitAssociator` merge-join rely on (a coalesced subgraph hit sums energies across descendants, so it is not a single direct-hit index). This needs a contract decision (compute-on-read vs store-coalesced); the cheap safe sub-part (drop `recHitIndex` from subgraph storage, re-resolve from the DetId map) is the recommended first step.
- **M5** ✅ **done** (`d2a67b5cb0c`) — `DetIdRecHitMap` is now a sorted `vector<pair>` + binary search (`add`/`finalize`/`find`); ~6× smaller (8 B/entry vs ~48), cache-friendly lookups. Measured 23104 entries on a PU0 TTbar event; scales to a ~120 MB saving at PU200. Branch-replacement validator bit-identical.
- **M6** ⬜ — `TruthGraphProducer::produce` / `TruthLogicalGraphProducer::produce` are ~450/480-line functions; extract phases for testability.
- **M7** ✅ **done** (`1d3b7b5e7d3`) — `collapseIntermediateGenParticleChains` representative walk path-compressed (O(N²)→amortized O(N)); identical representatives. Worst-case microbench (200k-particle chain): 32415 ms → 1.9 ms.

## Low priority

- **L1** — view-returning helpers allocate `vector<Particle>` (16-byte views) for one-shot iteration; offer `std::ranges` transform views.
- **L2** — `bestBranches` copies reco hits to sort even when already sorted; the template overload copies twice.
- **L3** — `TruthGraphTopologyChecker` does O(n²) scans for example mothers (diagnostic only; gated + capped).
- **L4** — **stale README**: it still references `TruthLogicalGraphHitIndexProducer`, an old `python/` layout, and lists `truth::Branch` as "not yet implemented" (it is). Refresh to match the shipped code.
- **L5** — `pack/decode EventId` (memcpy of `EncodedEventId`↔`uint64`) is duplicated in five files (one lacks the `static_assert`); move to one shared inline header.

## Suggested order of attack

1. ~~**H1** (BFS per-node allocation) — biggest win, isolated to `Graph.cc`, unlocks H2.~~ **Done** (`fce7b87314b`).
2. ~~**H5** (mixing-producer CSR scatter + `isConsistent`) — correctness landmine in the largest product; quick mechanical fix.~~ **Done** (`fce7b87314b`).
3. ~~**H3 + H4** (hit-index `unordered_map`-per-particle; flat inverted index) — biggest memory/cache wins in the hottest producers.~~ **Done** (`fce7b87314b`); H4 = index-flattening only, all-particles default kept on purpose.

4. ~~**H2** (LCA dense matrix)~~ **Done** (`f523cd1ace0`) — visited-set BFS, no dense `k×N` matrix. Microbench (262k-particle tree, 3000 two-input queries): 988.8 µs → 7.2 µs/query (**138×**), 2 MB/query scratch eliminated, identical results.
5. ~~**M5**~~ **Done** (`d2a67b5cb0c`) and ~~**M7**~~ **Done** (`1d3b7b5e7d3`) — see above.

**Remaining (each a deliberate change, not a mechanical fix):**

6. **M3** (sparse association storage) — layout-agnostic sorted-pair rework; guard with the topology audit.
7. **M4** (subgraph hit storage) — needs the compute-on-read vs store-coalesced contract decision; start with dropping `recHitIndex`.
8. **M1 / M6** and **L1–L5** as cleanup.
