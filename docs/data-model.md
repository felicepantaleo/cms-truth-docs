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
- **Vertex roles** (`VertexRole`): `Normal`, `Interaction`, `Upstream`,
  `UnderlyingEvent`. When a selection truncates the upstream history, each
  interaction is summarized by one artificial `Interaction` source vertex that
  fans out (through artificial connector particles) to its `Upstream`
  (ISR/hard-scatter) and `UnderlyingEvent` sub-vertices, so the whole interaction
  descends from a single node. The Interaction vertices are keyed by the packed
  `EncodedEventId` (one per pp collision), so the signal is everything reachable
  from the signal `Interaction` vertex (bunch crossing 0, event 0) and each overlaid
  pile-up interaction gets its own. All carry the genEvent/eventId of the activity
  they summarize.
- **Hitless SIM subgraphs are pruned** (`postProcessing.dropHitlessSimSubgraphs`,
  default on): every SIM particle whose calorimeter + tracker sim-hit subgraph is
  empty is removed together with its whole downstream subtree, so the logical graph
  is the *detectable* truth — particles that left no signature in any calorimeter
  (HGCAL EE/HE, ECAL barrel, HCAL) nor in the tracker simply do not appear. The
  "empty subgraph" test is defined exactly as the `LogicalGraphHitIndex` attributes
  hits — a particle has a hit only when a sim-hit carries its `SimTrack` trackId
  with positive energy — so the kept graph is consistent with the hit index by
  construction. GEN-only descendants of a removed SIM particle (e.g. neutrinos from
  a soft hadron that deposited nothing) are swept out with it, while the GEN
  skeleton outside removed SIM subtrees (including invisible decays such as
  Z→νν that never enter the simulation) is preserved. Implemented as the first
  post-processing step in `TruthLogicalGraphPostProcessor`, before any collapsing
  or selection; the producer supplies the per-particle hit presence by reading the
  calo/tracker sim-hit collections. On a TTbar event this removes the ~13k purely
  invisible SIM particles while leaving every hit-bearing one untouched.

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

!!! note "Technical details"
    The traversals are **allocation-free**: immediate-relative cores push into a
    caller buffer, and every BFS/LCA reuses one buffer plus its own `dist`/`seen`
    array instead of allocating per dequeued node. The multi-source LCA iterates
    only the visited set (no dense `k×N` matrix). See
    [Implementation characteristics](optimization.md#allocation-free-graph-traversals).

## Layer 3 — `truth::LogicalGraphHitIndex`

`PhysicsTools/TruthInfo/interface/LogicalGraphHitIndex.h`. A per-logical-particle
hit index spanning **N detector channels**, built by `LogicalGraphHitIndexProducer`
from `PCaloHit`/`PSimHit` plus the DetId→RecHit-index map from
`SimHitToRecHitMapProducer`.

Channels are keyed by an enum so new detectors can be added without new hardcoded
members:

```cpp
enum class HitChannel : uint8_t {
  HGCalCalo = 0,  // calorimeter PCaloHits, recHit-mapped via the DetId->RecHit map
  Tracker   = 1,  // tracker PSimHits, energy = energyLoss, no recHit link
  MTD       = 2,  // MIP timing layer (BTL/ETL)
  Muon      = 3   // muon chambers (DT/CSC/RPC/GEM)
};
inline constexpr std::size_t kNumHitChannels = 4;
```

Each channel keeps its own per-particle hits (different DetId spaces, metrics and
recHit links never mix):

- **Direct hits** — a single particle's local detector contribution (the hits on its
  own `SimTrack`).
- **Subgraph hits** — the full detector footprint of a shower / decay branch (its own
  hits plus those of every logical descendant), coalesced and stored as a
  **contiguous, DetId-sorted span** (CSR), so two particles' footprints can be merged
  by a zero-gather merge-join.

A channel is one `Channel { directOffsets, directHits, subgraphOffsets, subgraphHits }`
CSR struct; the per-particle spans are reached through the channel accessors:

| Method | Returns |
|---|---|
| `directHits(HitChannel, particleId)` | `std::span<const Hit>` — particle's direct hits in that channel |
| `subgraphHits(HitChannel, particleId)` | `std::span<const Hit>` — particle's subgraph hits in that channel |
| `hasChannel(HitChannel)` | whether the channel is filled |
| `channel(HitChannel)` | the raw `Channel const&` (flat vectors, for whole-channel scans) |

- Each `Hit` is `{detId, recHitIndex, energy}` (unchanged). `recHitIndex` is the
  position in the global RecHit ordering from `SimHitToRecHitMapProducer` and is set
  only for channels that carry a DetId→RecHit link (`HGCalCalo`); for the tracker it
  stays `Hit::invalidRecHitIndex` (the order is HGCal collections first, then PF
  collections — changing it changes every index). `Hit::hasRecHit()` tests validity.

!!! note "Technical details"
    The builder uses flat, lazily-coalesced `vector<Hit>` per particle and channel
    (not a hash map per particle × channel) and aggregates subgraphs by a k-way merge
    of sorted spans; the `DetIdRecHitMap` is a sorted `vector<pair>` + binary search
    (~6× smaller than a hash map). See
    [Implementation characteristics](optimization.md#flat-per-particle-hit-index).

!!! info "Adding detector channels (planned / in-progress)"
    `HitChannel::MTD` and `HitChannel::Muon` are declared but **not yet filled** — the
    channel-enum design exists precisely so they can be added without new hardcoded
    members. The intended sources:

    - **MTD** — filled from `MtdSimLayerCluster` (already keyed by `SimTrack` trackId)
      via the official `MtdRecoClusterToSimLayerClusterAssociation`, whose recHit is the
      `FTLCluster`; MTD carries a DetId→RecHit link, so its `recHitIndex` will be set.
    - **Muon** — filled per subsystem from the `SimMuon/MCTruth` DigiSimLink associators
      (GEM/RPC/CSC/DT). ME0 has no rechits and is left out.

    Until those producers land, `hasChannel(HitChannel::MTD)` /
    `hasChannel(HitChannel::Muon)` return `false`.

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
- Works on any one channel, selected by a `HitChannel` constructor argument
  (default `HitChannel::HGCalCalo`).

!!! note "Technical details"
    The inverted index and per-cell energy map are flat, sorted CSR-style arrays
    looked up by binary search; `bestBranches` is a linear merge-join against each
    candidate's DetId-sorted span. The all-particles default (empty candidate-root
    list) is kept on purpose — restricting roots would change matching semantics.
    See [Implementation characteristics](optimization.md#flat-inverted-index-in-branchhitassociator).

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
