# Implementation characteristics

This page describes the performance design of the package and what that design
gains. It is a reference for anyone who reads or extends the code. These are
**implemented** design choices, not a wish list. The remaining, not-yet-done
ideas live in the [Roadmap](roadmap.md). Each feature page links here for the
detail. This page is the single place that collects that detail.

## Foundations (by design from the start)

- **CSR everywhere** for the persistent products: raw `TruthGraph`, bipartite
  `truth::Graph`, and the hit index. CSR gives contiguous offsets and edge
  arrays. It is cache-friendly, and it needs no per-node pointer chasing.
- **`std::span` accessors** give zero-copy navigation into the CSR storage.
  Handles are 16-byte `(graph*, id)` views. They are never owning copies.
- **`reserve()` discipline**, path-halving union-find, and the right
  `edm::global`/`edm::stream` concurrency choice per producer.
- The **`Branch` view is non-owning and recomputed on demand**. There is no extra
  stored product, so the truth graph stays compact.

## Allocation-free graph traversals

*Relevant to: the [navigation API](data-model.md#layer-2-truthgraph-logical).*

The immediate-relative cores `appendParents` and `appendChildren` push neighbour
ids into a **caller-provided buffer**. The degree is tiny. A caller that needs
uniqueness does a short linear dedup. Every BFS/LCA traversal reuses a single
buffer plus its own `dist`/`seen` array. Those traversals are `ancestorsOf`,
`descendantsOf`, `firstAncestorWithPdgIdOf`, `firstCommonAncestorOf` and
`lowestCommonAncestor`. The earlier code instead allocated a `vector(nParticles)`
dedup buffer **per dequeued node**. The change removed the original O(N²)-time,
O(N²)-allocation behaviour on ancestor, descendant and LCA queries. The returned
sets and their order do not change.

The multi-source LCA additionally **iterates only the visited set**. It reuses one
distance buffer with per-ancestor hit counts. It does not scan all `nParticles`,
and it does not allocate a dense `k×N` distance matrix. On a ~260k-particle tree
the two-input LCA query dropped from ~1 ms to a few µs (~138×).

## Flat per-particle hit index

*Relevant to: [`truth::LogicalGraphHitIndex`](data-model.md#layer-3-truthlogicalgraphhitindex).*

The hit-index builder keeps a flat `vector<Hit>` per particle, for the calo and
tracker channels. It coalesces that vector lazily by sort-on-DetId plus sum.
Subgraphs aggregate by appending the already-coalesced span of each child and
coalescing once. That step is a k-way merge of sorted spans. The original code
instead used an `unordered_map<detId, accumulator>` **per particle × 4 channels**,
which re-hashed each hit roughly once per ancestor depth. This is the hottest
producer, because it handles the full calo and tracker hit volume. The gain in
allocation and in cache behaviour is not measured.

Hit sets, counts, recHit indices and recHit/tracker energies are bit-identical to
the hash-based build. Summed **sim-hit energies** agree only to float
**reassociation** (~1e-7 relative). The flat build sums in deterministic DetId
order. The old `unordered_map` summed in hash-bucket order, which is not
portable. The new value is therefore the more reproducible one. The cppunit
tolerance (1e-6) covers the difference.

The **DetId→RecHit map** (`hgcal::DetIdRecHitMap`, from
`DetIdToRecHitMapProducer`) is a **sorted `vector<pair>` plus binary search**
(`add`/`finalize`/`find`). It is ~6× smaller than a hash map (8 B/entry vs ~48),
and its lookups are cache-friendly. On a PU0 TTbar event it holds tens of
thousands of entries. It scales to a ~120 MB saving at PU200.

## Flat inverted index in `BranchHitAssociator`

*Relevant to: [`truth::BranchHitAssociator`](data-model.md#truthbranchhitassociator-generic-hit-based-matching).*

The inverted `detId → candidate roots` index and the per-cell energy map are flat,
sorted CSR-style arrays (`cellRootsKeys_`/`Offsets_`/`cellRoots_`,
`cellEnergyKeys_`/`Values_`). The code looks them up by binary search.
`bestBranches` is a **sorted merge-join** of the reco hits against the
DetId-sorted subgraph span of each candidate. That is the correct linear
algorithm. It relies on the sorted-span invariant of the builder.

!!! note "All-particles default kept on purpose"
    With an empty candidate-root list the associator treats every particle as a
    root. A restriction of the roots would change the matching semantics, because
    the calo validator matches reco objects against *ancestor* CaloParticles. The
    optimization here is therefore the index flattening only. Root restriction
    stays a deliberate, semantics-changing follow-up.

## Robust CSR construction in the mixing producers

*Relevant to: the [pileup mixing producers](pileup.md).*

Both mixing producers (`TruthGraphAccumulator`, `TruthGraphMixedProducer`) build
the out-edge CSR with the proven counting-sort scatter `cursor = offsets;
pos = cursor[src]++`. That scatter needs no permutation vector and no O(E log E)
sort. It also does not rely on a non-stable sort matching the offsets. The
accumulator asserts `isConsistent()` before `put`. This removed a correctness
risk in the largest product (mixed signal + pileup).

## Other applied items

- **Path-compressed collapse walk**: the representative walk in
  `collapseIntermediateGenParticleChains` is path-compressed (O(N²) → amortized
  O(N)). The representatives are identical. The worst case (a long single chain)
  went from tens of seconds to ~2 ms.

## Validation of the performance work

We checked old against new as a pure-performance change. The rebuild was clean
and from scratch. All cppunit tests pass. The topology audit on 8 Run4 relval
samples stays clean (`cycles=0`, `multiProd=0`, one component/event). The
branch-replacement validator on TTbar maps CaloParticle/SimCluster/TrackingParticle
with completeness 1. The per-particle `nParents`/`nChildren` and the hit counts,
sets, recHit indices and recHit energies in the gallery dumps are bit-identical to
the pre-change dumps. The pileup accumulator re-runs to a consistent, clean DAG.
`code-format` and `code-checks` are clean. The only quantity that is not
bit-identical is the summed sim-hit energy noted above (float reassociation,
~1e-7).
