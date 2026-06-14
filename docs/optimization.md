# Optimization review

A performance/quality pass over the package (CPU, memory, storage, readability,
comments). Findings are **prioritized and actionable**; none are applied yet (see
the [Roadmap](roadmap.md)). The persistent-data design is sound — the items below
are concentrated in the navigation layer, the hit-index builder, and two
robustness fixes in the mixing producers.

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
| **H1** | `parentsOf`/`childrenOf` (`Graph.cc:218-256`) allocate + zero-fill a `vector(nParticles)` dedup buffer **and** return a heap vector — and every BFS (`ancestors`, `descendants`, `firstAncestorWithPdgId`, `firstCommonAncestor`, `lowestCommonAncestor`) calls them per dequeued node → **O(N²) time + allocation** | span-returning core helpers that push into a caller buffer (degree is tiny; dedup with a linear scan); BFS keeps its own single `visited` array | **Order-of-magnitude** speedup on every ancestor/descendant/LCA query; the single most important finding |
| **H2** | `firstCommonAncestorOf`/`lowestCommonAncestor` scan all `nParticles`; LCA allocates a dense `k×N` int distance matrix | iterate only the visited set; reuse one `dist` buffer + per-ancestor hit counts | Large for pileup-size events; the "which particle did this jet come from" hot path |
| **H3** | `LogicalGraphHitIndexBuilder` keeps **one `unordered_map` per particle × 4 channels** (`~4·nParticles` hash tables); subgraph aggregation re-hashes each hit ~depth times | per-particle `vector<Hit>` + sort/coalesce; aggregate subgraphs by k-way merge of children's sorted spans | Large alloc/cache win in the **hottest** producer (full calo+tracker hit volume) |
| **H4** | `BranchHitAssociator` with default (empty) candidate roots treats **every** particle as a root and inserts every ancestor's subgraph hits into the inverted index ≈ O(hits×depth) | don't default to all particles (use direct-hit owners / selector roots); flat sorted `vector<pair<detId,root>>` + binary search | Large memory/CPU win on the documented default path |
| **H5** | The mixing producers (`TruthGraphAccumulator.cc:311-327`, `TruthGraphMixedProducer.cc:179-196`) build CSR via an `order`-permutation scatter (fragile; relies on non-stable sort matching offsets); the accumulator never calls `isConsistent()` before `put` | use the proven `cursor=offsets; pos=cursor[src]++` scatter (as in `buildCSR`); add `isConsistent()` to the accumulator | Removes a correctness landmine in the **largest** product (mixed signal+pileup); drops an O(E log E) sort |

## Medium priority

- **M1** — `Branch` reruns a full BFS `traverse()` on every accessor; `invisibleEnergy()` runs it **twice** (`p4`+`visibleP4`). Compute `stableLeaves()` once and derive all kinematics in one pass; offer an opt-in materialized branch for loops over many branches.
- **M3** — `TruthGraph` stores `simTrackToGen`/`simTrackToVtx` (SimTrack-only) and `simVtxToGen` (SimVertex-only) full-length over **all** nodes; size them to the SimTrack/SimVertex ranges (bases already computed) to shrink the persisted raw/mixed product.
- **M4** — the subgraph hit CSR re-stores `{detId, recHitIndex, energy}` for every ancestor (≈ Σ subtree hits ≫ distinct hits). Store subgraph spans as **indices into the direct-hit storage**, and/or drop `recHitIndex` (re-resolvable from the DetId map). Largest hit-index storage contributor; scales with shower depth.
- **M5** — `SimHitToRecHitMapProducer` ships an `unordered_map` with one entry per RecHit (millions for Phase-2 HGCal); a sorted `vector<pair>` + `lower_bound` is far more compact/cache-friendly for build-once/lookup-many.
- **M6** — `TruthGraphProducer::produce` / `TruthLogicalGraphProducer::produce` are ~450/480-line functions; extract phases (`fillGenNodes`, `buildGenToSimAssociations`, `collectEdges`) into the anonymous namespace for testability and to reuse the H5 scatter.
- **M7** — `collapseIntermediateGenParticleChains` representative walk is O(N) per particle (O(N²) worst case); path-compress (memoize representatives).

## Low priority

- **L1** — view-returning helpers allocate `vector<Particle>` (16-byte views) for one-shot iteration; offer `std::ranges` transform views.
- **L2** — `bestBranches` copies reco hits to sort even when already sorted; the template overload copies twice.
- **L3** — `TruthGraphTopologyChecker` does O(n²) scans for example mothers (diagnostic only; gated + capped).
- **L4** — **stale README**: it still references `TruthLogicalGraphHitIndexProducer`, an old `python/` layout, and lists `truth::Branch` as "not yet implemented" (it is). Refresh to match the shipped code.
- **L5** — `pack/decode EventId` (memcpy of `EncodedEventId`↔`uint64`) is duplicated in five files (one lacks the `static_assert`); move to one shared inline header.

## Suggested order of attack

1. **H1** (BFS per-node allocation) — biggest win, isolated to `Graph.cc`, unlocks H2.
2. **H5** (mixing-producer CSR scatter + `isConsistent`) — correctness landmine in the largest product; quick mechanical fix.
3. **H3 + H4** (hit-index `unordered_map`-per-particle; all-particles inverted index) — biggest memory/cache wins in the hottest producers.
4. **H2** (LCA dense matrix) on top of H1.
5. Storage items **M3 / M4 / M5** together — they shrink the persisted raw/mixed graph and hit index, the flagged scaling risk for pileup.
