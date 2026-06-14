# Data model

The package is deliberately layered: a compact **raw** graph close to the EDM
inputs, a user-facing **logical** graph with a physics navigation API, and an
auxiliary **hit index**. All three use cache-friendly CSR (compressed
sparse-row) layouts.

## Layer 1 — `TruthGraph` (raw)

`PhysicsTools/TruthInfo/interface/TruthGraph.h`. A single heterogeneous,
read-only graph built directly from HepMC2/HepMC3 + `SimTrack`/`SimVertex` by
`TruthGraphProducer`.

- **Node kinds:** `GenEvent`, `GenVertex`, `GenParticle`, `SimVertex`, `SimTrack`.
- **Edge kinds:** `Gen` (within GEN), `Sim` (within SIM), `GenToSim` (the realm
  boundary — `GenParticle → SimTrack`), `SimToGen` (reserved).
- **Storage:** CSR out-edges (`offsets`, `edges`, `edgeKind`) + per-node payload
  (`pdgId`, `status`, `statusFlags`, packed `EncodedEventId`, `genEventOfNode`).
- **Associations:** `simTrackToGen`, `simTrackToVtx`, `simVtxToGen` — the GEN↔SIM
  provenance, derived from `SimTrack::genpartIndex()` for primary G4 tracks.

The raw graph is intentionally close to the inputs and is the substrate for the
logical graph. Cross-domain `GenToSim` edges are built **only for primary
SimTracks**, interpreting `genpartIndex()` as a HepMC barcode (see
[Findings](findings.md) for why non-primary back-fill must not be used).

## Layer 2 — `truth::Graph` (logical)

`PhysicsTools/TruthInfo/interface/Graph.h`. A user-facing **bipartite
Particle ↔ Vertex** graph built by `TruthLogicalGraphProducer` from the raw graph.

- `Particle` and `Vertex` are lightweight handles `(graph*, id)`; the payload is in
  `ParticleData` / `VertexData` (provenance back-refs `genNode`/`simNode`, `pdgId`,
  `status`, `EncodedEventId`, `genEvent`, four-momentum / position, optional
  trajectory checkpoints).
- GEN and SIM particles/vertices are **merged** when robustly associated; a merged
  particle takes its production vertex from its **immediate GEN production vertex**
  (see [Findings](findings.md)). Intermediate GEN-only copies can be collapsed.
- **Vertex roles** (`VertexRole`): `Normal`, `Upstream`, `UnderlyingEvent` —
  artificial source vertices summarize cut activity and carry the genEvent/eventId
  so overlaid pile-up graphs stay distinguishable.

### Navigation API

| Method | Returns |
|---|---|
| `parents()`, `children()` | immediate relatives (via production/decay vertices) |
| `ancestors()`, `descendants()` | transitive closure |
| `productionVertices()`, `decayVertices()` | the bipartite neighbors |
| `firstAncestorWithPdgId(id)`, `hasAncestorPdgId(id)` | typed ancestry |
| `firstCommonAncestor(other)` | pairwise LCA |
| `lowestCommonAncestor(particles)` | multi-source LCA ("which particle did this jet come from") |
| `roots()`, `leaves()`, `sourceVertices()`, `sinkVertices()` | graph extremities |

## Layer 3 — `truth::LogicalGraphHitIndex`

`PhysicsTools/TruthInfo/interface/LogicalGraphHitIndex.h`. A per-logical-particle
calorimeter + tracker hit index, built by `LogicalGraphHitIndexProducer` from
`PCaloHit`/`PSimHit` plus the DetId→RecHit-index map from `SimHitToRecHitMapProducer`.

- **Direct hits** — a single particle's local detector contribution.
- **Subgraph hits** — the full detector footprint of a shower / decay branch
  (recursive subtree aggregation), stored as a **contiguous, DetId-sorted span**
  (CSR), so two particles' footprints can be merged by a zero-gather merge-join.
- Separate **calo** and **tracker** channels (`subgraphHits` vs
  `trackerSubgraphHits`).
- Each `Hit` is `{detId, recHitIndex, energy}`; `recHitIndex` is the position in
  the global RecHit ordering from `SimHitToRecHitMapProducer` (the order is HGCal
  collections first, then PF collections — changing it changes every index).

## `truth::Branch` — the subgraph view

`PhysicsTools/TruthInfo/interface/Branch.h`. A decay-branch / subgraph view of the
logical graph, **recomputed on demand** from a root (or set of roots) + a closure
spec. No extra storage; the graph stays compact.

**Closures** (`ClosureKind`): `Subtree`, `StableLeaves`, `DepthN`, `UntilPdgId`,
`Predicate` (arbitrary `std::function<bool(Particle)>`).

| Question | Method |
|---|---|
| Members / stable leaves | `members()`, `memberIds()`, `stableLeaves()` |
| Kinematics | `p4()`, `visibleP4()`, `energy()`, `visibleEnergy()`, `invisibleEnergy()` |
| Tagging | `rootPdgId()`, `originWithPdgId(id)`, `hasHeavyFlavor(flavor)` |
| Provenance | `genEvent()`, `bunchCrossing()`, `event()`, `isInTime()`, `isFromPileup()`, `isSignal()` |
| Relations | `commonAncestor(other)`, `merged(other)` |

This answers the questions reconstruction/tagging/performance studies actually ask
("which b-quark did this jet come from", "what is the visible energy of this τ
branch", "is this hit cluster from pileup").

## `truth::BranchHitAssociator` — generic hit-based matching

`PhysicsTools/TruthInfo/interface/BranchHitAssociator.h`. Given the hits of a reco
object, efficiently finds the best truth branches.

- Works on **any reco object** that exposes a `truthHits()` method (a C++20
  concept `HasTruthHits`) — users opt their object in by defining that one method.
- Builds an inverted `detId → candidate roots` index from the hit index, then a
  **sorted merge-join** of the reco hits against each candidate branch's
  DetId-sorted span.
- **Metrics:** `SharedEnergy` (the HGCal by-hits score:
  `score = (1/Σ(f·E)²) · Σ max(0, f_reco − f_branch)²·E²`) and `SharedHits`.
- Calo or tracker channel (`useTracker`).

## `truth::BranchSelector` — physics selection

`PhysicsTools/TruthInfo/interface/BranchSelector.h`. A configurable predicate over
branches — pt/eta window, pdgId list, charge, signal-only, invert-eta — in the
spirit of `CaloParticleSelector` / `TrackingParticleSelector`. Charge comes from
`HepPDT::ParticleID(pdgId).threeCharge()`.

## Auxiliary plugins

- `TruthGraphDumper`, `TruthLogicalGraphDumper` — DOT files per run/lumi/event
  (rendered to SVG/PDF; see [Validation](validation.md)).
- `RecHitFlatTableProducer`, `PFRecHitFlatTableProducer`,
  `TrackerSimHitFlatTableProducer` — NanoAOD-style flat tables.
- `TruthGraphTopologyChecker` — the diagnostic analyzer used throughout
  [Validation](validation.md) (degree distributions, anomaly counts, per-bunch-crossing breakdown).
