# Data model

The package has three deliberate layers. The first is a compact **raw** graph
close to the EDM inputs. The second is a user-facing **logical** graph with a
physics navigation API. The third is an auxiliary **hit index**. All three use
cache-friendly CSR (compressed sparse-row) layouts.

## Layer 1: `TruthGraph` (raw)

`SimDataFormats/TruthInfo/interface/TruthGraph.h`. `TruthGraphProducer` builds a
single heterogeneous, read-only graph directly from HepMC2/HepMC3 plus
`SimTrack`/`SimVertex`.

- **Node kinds:** `GenEvent`, `GenVertex`, `GenParticle`, `SimVertex`, `SimTrack`.
- **Edge kinds:** `Gen` (within GEN), `Sim` (within SIM), `GenToSim` (the realm
  boundary, `GenParticle → SimTrack`), `SimToGen` (reserved).
- **Storage:** CSR out-edges (`offsets`, `edges`, `edgeKind`) + per-node payload
  (`pdgId`, `status`, `statusFlags`, packed `EncodedEventId`, `genEventOfNode`).
- **Associations:** `simTrackToGen`, `simTrackToVtx`, `simVtxToGen`. These hold the
  GEN↔SIM provenance, derived from `SimTrack::genpartIndex()` for primary G4 tracks.

The raw graph stays close to the inputs on purpose. It is the substrate for the
logical graph. The producer builds cross-domain `GenToSim` edges **only for
primary SimTracks**, and it reads `genpartIndex()` as a HepMC barcode. See
[Findings](findings.md) for why non-primary back-fill must not be used.

## Layer 2: `truth::Graph` (logical)

`SimDataFormats/TruthInfo/interface/Graph.h`. `TruthLogicalGraphProducer` builds a
user-facing **bipartite Particle ↔ Vertex** graph from the raw graph.

- `Particle` and `Vertex` are lightweight handles `(graph*, id)`. The payload is in
  `ParticleData` / `VertexData`. It holds the provenance back-refs
  `genNode`/`simNode`, `pdgId`, `status`, `EncodedEventId`, `genEvent`,
  four-momentum / position, and optional trajectory checkpoints.
- The producer **merges** GEN and SIM particles/vertices when they are robustly
  associated. A merged particle takes its production vertex from its **immediate
  GEN production vertex** (see [Findings](findings.md)). Intermediate GEN-only
  copies can be collapsed.
- **Vertex roles** (`VertexRole`): `Normal`, `Interaction`, `Upstream`,
  `UnderlyingEvent`. When a selection truncates the upstream history, one
  artificial `Interaction` source vertex summarizes each interaction. That vertex
  fans out, through artificial connector particles, to its `Upstream`
  (ISR/hard-scatter) and `UnderlyingEvent` sub-vertices. The whole interaction
  therefore descends from a single node. The Interaction vertices are keyed by the
  packed `EncodedEventId`, one per pp collision. The signal is therefore
  everything reachable from the signal `Interaction` vertex (bunch crossing 0,
  event 0), and each overlaid pileup interaction gets its own vertex. Every
  Interaction vertex carries the genEvent/eventId of the activity it summarizes.
- **Vertex reason** (`VertexReason`, `VertexData::vertexReason()`, reached as
  `vertex.data().vertexReason()`): every SIM vertex
  carries the *physical process that created it*. The code decodes it from the
  Geant4 process sub-type (`SimVertex::processType()`) of the creator process of
  its outgoing track. The values are
  `Primary`, `Decay`, `Bremsstrahlung`, `Ionisation` (delta-ray), `PairConversion`,
  `Compton`, `PhotoElectric`, `Annihilation`, `Rayleigh`, `CoulombScattering`,
  `HadronInelastic`, `HadronElastic`, `NuclearCapture`, `ChargeExchange`,
  `HadronAtRest`, and `Other`/`Unknown`. The raw graph stores the process sub-type
  verbatim (`TruthGraph::simVertexProcessType`). The logical producer folds it into
  the enum with `reasonFromG4ProcessSubType`. On a TTbar event the SIM vertices
  break down, most-frequent first, as hadronic-inelastic, e⁺e⁻ annihilation,
  bremsstrahlung, pair-conversion, decay, nuclear capture, hadron-at-rest, and so
  on. The reason therefore tells you *why* a given branch point exists.
- **Back-scattering** (`Particle::backscattered()`): the producer flags a SIM
  particle when Geant4 marked its track as inward albedo crossing the
  CALO→Tracker boundary (`SimTrack::isFromBackScattering()`). This is a
  track-level property, not a vertex reason. Such particles travel *back* toward
  the beamline and decrease their distance from the production region. They are a
  known source of apparent history-reversal. The producer ORs the flag onto a
  merged GEN+SIM particle from its SIM side, and propagates it through
  `TruthGraph::simTrackBackscattered`.
- **The producer prunes hitless SIM subgraphs**
  (`postProcessing.dropHitlessSimSubgraphs`, default on). It removes every SIM
  particle whose calorimeter + tracker sim-hit subgraph is empty, together with the
  whole downstream subtree of that particle. The logical graph is therefore the
  *detectable* truth. A particle that left no signature in any calorimeter
  (HGCAL EE/HE, ECAL barrel, HCAL) and none in the tracker does not appear. The
  "empty subgraph" test uses exactly the rule by which `LogicalGraphHitIndex`
  attributes hits. A particle has a hit only when a sim-hit carries its `SimTrack`
  trackId with positive energy. The kept graph is therefore consistent with the hit
  index by construction. GEN-only descendants of a removed SIM particle (e.g.
  neutrinos from a soft hadron that deposited nothing) go out with it. The GEN
  skeleton outside removed SIM subtrees stays, including invisible decays such as
  Z→νν that never enter the simulation. The pruning is the first post-processing
  step in `TruthLogicalGraphPostProcessor`, before any collapsing or selection. The
  producer supplies the per-particle hit presence by reading the calo/tracker
  sim-hit collections. On a TTbar event this removes the ~13k purely invisible SIM
  particles and leaves every hit-bearing one untouched.

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
    The traversals are **allocation-free**. The immediate-relative cores push into
    a caller buffer. Every BFS/LCA reuses one buffer plus its own `dist`/`seen`
    array, instead of allocating per dequeued node. The multi-source LCA iterates
    only the visited set, with no dense `k×N` matrix. See
    [Implementation characteristics](optimization.md#allocation-free-graph-traversals).

## Layer 3: `truth::LogicalGraphHitIndex`

`SimDataFormats/TruthInfo/interface/LogicalGraphHitIndex.h`.
`LogicalGraphHitIndexProducer` builds a per-logical-particle hit index that spans
**N detector channels**. It reads `PCaloHit`/`PSimHit` plus the DetId→RecHit-index
map from `DetIdToRecHitMapProducer`.

An enum keys the channels, so you can add new detectors without new hardcoded
members:

```cpp
enum class HitChannel : uint8_t {
  Tracker = 0,  // tracker PSimHits, energy = energyLoss, no recHit link
  MTD     = 1,  // MIP timing layer (BTL/ETL)
  Calo    = 2,  // all calorimeter PCaloHits (HGCAL endcap + ECAL barrel + HCAL), recHit-mapped via the DetId->RecHit map
  Muon    = 3   // muon chambers (DT/CSC/RPC/GEM)
};
inline constexpr std::size_t kNumHitChannels = 4;
```

Each channel keeps its own per-particle hits. Different DetId spaces, metrics and
recHit links never mix:

- **Direct hits**: a single particle's local detector contribution, which is the
  set of hits on its own `SimTrack`.
- **Subgraph hits**: the full detector footprint of a shower / decay branch, which
  is its own hits plus those of every logical descendant. The builder coalesces
  them and stores them as a **contiguous, DetId-sorted span** (CSR). A zero-gather
  merge-join can therefore merge two particles' footprints.

A channel is one `Channel { directOffsets, directHits, subgraphOffsets, subgraphHits }`
CSR struct. You reach the per-particle spans through the channel accessors:

| Method | Returns |
|---|---|
| `directHits(HitChannel, particleId)` | `std::span<const Hit>`: particle's direct hits in that channel |
| `subgraphHits(HitChannel, particleId)` | `std::span<const Hit>`: particle's subgraph hits in that channel |
| `hasChannel(HitChannel)` | whether the channel is filled |
| `channel(HitChannel)` | the raw `Channel const&` (flat vectors, for whole-channel scans) |

- Each `Hit` is `{detId, recHitIndex, energy}` (unchanged). `recHitIndex` is the
  position in the global RecHit ordering from `DetIdToRecHitMapProducer`. Only
  channels that carry a DetId→RecHit link (`Calo`) set it. For the tracker it
  stays `Hit::kInvalidRecHitIndex`. The order is HGCal collections first, then PF
  collections; changing that order changes every index. `Hit::hasRecHit()` tests
  validity.
- **One entry per DetId; `energy` is the summed sim deposit.** A particle can
  deposit in the same cell more than once, and for subgraph hits several of its
  descendants can deposit in the same cell. `coalesce()` merges those deposits into
  a **single** `Hit` whose `energy` is the **sum** of the deposits. So if two
  leaves of the same mother both hit cell `D` with `e1` and `e2`, the mother's
  subgraph holds `D` once with `energy = e1 + e2`. The contributions accumulate,
  they never duplicate.

!!! warning "Sim energy is per-particle; reco attribution is whole-cell, not fractional"
    `energy` is the particle's (or subtree's) **own** sim energy in the cell. This
    side *is* fractional: each particle carries exactly what it deposited. The
    **recHit** side is **binary**, not fractional. The coalesced `Hit` links the
    cell's recHit once. Summing `recHitEnergies[recHitIndex]` over a particle's hits
    therefore credits the particle the **full** cell energy for every cell its
    subtree touches. Within one subtree that is exact, because the cell's energy
    does belong to that ancestor. But a cell shared with a particle **outside** the
    subtree counts in full for *both*. The index does **not** carry per-cell energy
    fractions. This is deliberately **not** the `CaloParticle`/`SimCluster` fraction
    model. Use the sim `energy` (per-particle) when you need energy sharing. Treat
    the recHit sum as "reco energy in cells this branch lit up", not "this branch's
    share of the reco energy".

!!! note "Technical details"
    The builder uses a flat, lazily-coalesced `vector<Hit>` per particle and
    channel, not a hash map per particle × channel. It aggregates subgraphs by a
    k-way merge of sorted spans. The `DetIdRecHitMap` is a sorted `vector<pair>`
    plus binary search, ~6× smaller than a hash map. See
    [Implementation characteristics](optimization.md#flat-per-particle-hit-index).

!!! info "All four channels are filled"
    `LogicalGraphHitIndexProducer` fills the four channels, each from its own
    subdetector sources:

    - **Calo**: `PCaloHit`s (HGCAL EE/HE + ECAL barrel + HCAL) matched by
      `geantTrackId()`, with `recHitIndex` from the `DetIdRecHitMap`.
    - **Tracker**: tracker `PSimHit`s matched by `trackId()`; no recHit link.
    - **MTD**: filled from `MtdSimLayerCluster`, which `particleId()` already keys
      by the producing `SimTrack`, and restricted to the signal interaction by
      `EncodedEventId`. The `recHitIndex` is the matched reco **`FTLCluster`**. The
      producer looks it up through `MtdSimLayerClusterToRecoClusterAssociation` and
      indexes it in the barrel-then-endcap `FTLCluster` concatenation. This
      `recHitIndex` is *channel-relative*: the MTD ordering is FTLClusters, not the
      HGCal recHit ordering.
    - **Muon**: the five `g4SimHits:Muon{DT,CSC,RPC,GEM,ME0}Hits` `PSimHit`
      collections matched by `trackId()`, like the tracker channel. There is no
      recHit link, because muon rechits are reconstructed segments. A
      DigiSimLink-based link is future work. The producer reads ME0 hits, but they
      have no rechits.

    **Choosing subdetectors.** The producer takes a `subdetectors` list, default
    `{Calo, Tracker, MTD, Muon}`. A channel left off the list stays empty, and
    `hasChannel(...)` returns `false` for it. Each subdetector has its own config
    parameters for its input collections (`simHitCollections`,
    `trackerSimHitCollections`, `muonSimHitCollections`, `mtdSimLayerClusters` plus
    the FTLCluster inputs). You can therefore pick which subdetectors to read, and
    point each one at different collections.

## `truth::Branch`: the subgraph view

`PhysicsTools/TruthInfo/interface/Branch.h`. This is a decay-branch / subgraph view
of the logical graph. The code **recomputes it on demand** from a root, or a set of
roots, plus a closure spec. It needs no extra storage, so the logical graph stays
compact.

**Closures** (`ClosureKind`): `Subtree`, `StableLeaves`, `DepthN`, `UntilPdgId`,
`Predicate` (arbitrary `std::function<bool(Particle)>`).

| Question | Method |
|---|---|
| Members / stable leaves | `members()`, `memberIds()`, `stableLeaves()` |
| Kinematics | `p4()`, `visibleP4()`, `energy()`, `visibleEnergy()`, `invisibleEnergy()` |
| Tagging | `rootPdgId()`, `originWithPdgId(id)`, `hasHeavyFlavor(flavor)` |
| Provenance | `genEvent()`, `bunchCrossing()`, `event()`, `isInTime()`, `isFromPileup()`, `isSignal()` |
| Relations | `commonAncestor(other)`, `merged(other)` |

This answers the questions that reconstruction, tagging and performance studies
ask. Examples are "which b-quark did this jet come from", "what is the visible
energy of this τ branch", and "is this hit cluster from pileup".

## `truth::BranchHitAssociator`: generic hit-based matching

`PhysicsTools/TruthInfo/interface/BranchHitAssociator.h`. Given the hits of a reco
object, it finds the best truth branches efficiently.

- It works on **any reco object** that exposes a `truthHits()` method, through the
  C++20 concept `HasTruthHits`. A user opts an object in by defining that one
  method.
- It builds an inverted `detId → candidate roots` index from the hit index. It then
  runs a **sorted merge-join** of the reco hits against the DetId-sorted span of
  each candidate branch.
- **Metrics:** `SharedEnergy` (the HGCal by-hits score:
  `score = (1/Σ(f·E)²) · Σ max(0, f_reco − f_branch)²·E²`) and `SharedHits`.
- It works on any one channel. A `HitChannel` constructor argument selects the
  channel, default `HitChannel::Calo`.

!!! note "Technical details"
    The inverted index and the per-cell energy map are flat, sorted CSR-style
    arrays, looked up by binary search. `bestBranches` is a linear merge-join
    against the DetId-sorted span of each candidate. The all-particles default (an
    empty candidate-root list) is kept on purpose, because restricting roots would
    change the matching semantics.
    See [Implementation characteristics](optimization.md#flat-inverted-index-in-branchhitassociator).

## `truth::BranchSelector`: physics selection

`PhysicsTools/TruthInfo/interface/BranchSelector.h`. This is a configurable
predicate over branches: pt/eta window, pdgId list, charge, signal-only,
invert-eta. It follows the same pattern as `CaloParticleSelector` /
`TrackingParticleSelector`. Charge comes from
`HepPDT::ParticleID(pdgId).threeCharge()`.

## Auxiliary plugins

- `TruthGraphDumper`, `TruthLogicalGraphDumper`: DOT files per run/lumi/event. You
  render them to SVG/PDF; see [Validation](validation.md).
- `RecHitFlatTableProducer`, `PFRecHitFlatTableProducer`,
  `TrackerSimHitFlatTableProducer`: NanoAOD-style flat tables.
- `TruthGraphTopologyChecker`: the diagnostic analyzer used throughout
  [Validation](validation.md) for degree distributions, anomaly counts and the
  per-bunch-crossing breakdown.
