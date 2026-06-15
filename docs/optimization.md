# Implementation characteristics

How the package is built for performance and what that buys, as a reference for
anyone reading or extending the code. These are **implemented** design choices, not
a wish list — the remaining, not-yet-done ideas live in the [Roadmap](roadmap.md).
Each feature page links here for the gory detail; this page is the single place that
collects it.

## Foundations (by design from the start)

- **CSR everywhere** for the persistent products (raw `TruthGraph`, bipartite
  `truth::Graph`, the hit index) — contiguous offsets + edge arrays, cache-friendly,
  no per-node pointer chasing.
- **`std::span` accessors** — zero-copy navigation into the CSR storage; handles are
  16-byte `(graph*, id)` views, never owning copies.
- **`reserve()` discipline**, path-halving union-find, and the right
  `edm::global`/`edm::stream` concurrency choice per producer.
- The **`Branch` view is non-owning and recomputed on demand** — no extra stored
  product; the graph stays compact.

## Allocation-free graph traversals

*Relevant to: the [navigation API](data-model.md#layer-2-truthgraph-logical).*

The immediate-relative cores `appendParents` / `appendChildren` push neighbour ids
into a **caller-provided buffer** (degree is tiny; callers needing uniqueness do a
short linear dedup). Every BFS/LCA traversal — `ancestorsOf`, `descendantsOf`,
`firstAncestorWithPdgIdOf`, `firstCommonAncestorOf`, `lowestCommonAncestor` — reuses
a single buffer plus its own `dist`/`seen` array, instead of allocating a
`vector(nParticles)` dedup buffer **per dequeued node**. That removed the original
O(N²)-time, O(N²)-allocation behaviour on ancestor/descendant/LCA queries with no
change to the returned sets or their order.

The multi-source LCA additionally **iterates only the visited set** and reuses one
distance buffer with per-ancestor hit counts, rather than scanning all `nParticles`
and allocating a dense `k×N` distance matrix. On a ~260k-particle tree the two-input
LCA query dropped from ~1 ms to a few µs (~138×).

## Flat per-particle hit index

*Relevant to: [`truth::LogicalGraphHitIndex`](data-model.md#layer-3-truthlogicalgraphhitindex).*

The hit-index builder keeps a flat `vector<Hit>` per particle (calo and tracker
channels), coalesced lazily by sort-on-DetId + sum. Subgraphs aggregate by appending
each child's already-coalesced span and coalescing once — a k-way merge of sorted
spans — instead of the original `unordered_map<detId, accumulator>` **per particle ×
4 channels**, which re-hashed each hit roughly once per ancestor depth. This is the
hottest producer (the full calo + tracker hit volume) and the win is large in both
allocation and cache behaviour.

Hit sets, counts, recHit indices and recHit/tracker energies are bit-identical to the
hash-based build. Summed **sim-hit energies** agree only to float **reassociation**
(~1e-7 relative): the flat build sums in deterministic DetId order, whereas the old
`unordered_map` summed in (non-portable) hash-bucket order — so the new value is the
more reproducible. The cppunit tolerance (1e-6) covers it.

The **DetId→RecHit map** (`hgcal::DetIdRecHitMap`, from `SimHitToRecHitMapProducer`)
is a **sorted `vector<pair>` + binary search** (`add`/`finalize`/`find`), ~6× smaller
than a hash map (8 B/entry vs ~48) with cache-friendly lookups — on a PU0 TTbar event
it holds tens of thousands of entries and scales to a ~120 MB saving at PU200.

## Flat inverted index in `BranchHitAssociator`

*Relevant to: [`truth::BranchHitAssociator`](data-model.md#truthbranchhitassociator-generic-hit-based-matching).*

The inverted `detId → candidate roots` index and the per-cell energy map are flat,
sorted CSR-style arrays looked up by binary search
(`cellRootsKeys_`/`Offsets_`/`cellRoots_`, `cellEnergyKeys_`/`Values_`), and
`bestBranches` is a **sorted merge-join** of the reco hits against each candidate's
DetId-sorted subgraph span — the correct linear algorithm, relying on the builder's
sorted-span invariant.

!!! note "All-particles default kept on purpose"
    With an empty candidate-root list the associator treats every particle as a
    root. Restricting the roots would change matching semantics (the calo validator
    matches reco objects against *ancestor* CaloParticles), so the optimization here
    is the index flattening only; root restriction is left as a deliberate,
    semantics-changing follow-up.

## Robust CSR construction in the mixing producers

*Relevant to: the [pileup mixing producers](pileup.md).*

Both mixing producers (`TruthGraphAccumulator`, `TruthGraphMixedProducer`) build the
out-edge CSR with the proven counting-sort scatter `cursor = offsets;
pos = cursor[src]++` — no permutation vector, no O(E log E) sort, and not reliant on
a non-stable sort matching the offsets. The accumulator asserts `isConsistent()`
before `put`. This removed a correctness landmine in the largest product (mixed
signal + pileup).

## Other applied items

- **Path-compressed collapse walk** — the representative walk in
  `collapseIntermediateGenParticleChains` is path-compressed (O(N²) → amortized
  O(N)); identical representatives. Worst case (a long single chain) went from tens
  of seconds to ~2 ms.

## Validation of the performance work

Old-vs-new was checked as a pure-performance change: clean from-scratch rebuild;
all cppunit tests pass; the topology audit on 8 Run4 relval samples stays clean
(`cycles=0`, `multiProd=0`, one component/event); the branch-replacement validator
on TTbar maps CaloParticle/SimCluster/TrackingParticle with completeness 1; the
gallery dumps' per-particle `nParents`/`nChildren` and hit
counts/sets/recHit-indices/recHit-energies are bit-identical to the pre-change
dumps; the pileup accumulator re-runs to a consistent, clean DAG. `code-format` and
`code-checks` clean. The only non-bit-identical quantity is the summed sim-hit energy
noted above (float reassociation, ~1e-7).
