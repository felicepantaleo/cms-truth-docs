# Interface reference

This page is the precise reference for the user-facing C++ interface of the truth
graph. It covers the `truth::Graph` navigation API, the `truth::Branch` subgraph
view, and the `truth::BranchSelector` and `truth::BranchHitAssociator` helpers.
Every signature below comes from the authoritative headers, with `[[nodiscard]]`
omitted for brevity. The headers live in two packages.
`SimDataFormats/TruthInfo/interface/` holds the data-model headers.
`PhysicsTools/TruthInfo/interface/` holds the analysis-layer headers. For the
design rationale see the [Data model](data-model.md). For narrative walk-throughs
see [How to use the graph](usage.md) and [Worked examples](examples.md).

!!! note "Where each symbol lives"
    | Symbol | Header |
    |---|---|
    | `truth::Graph` | `SimDataFormats/TruthInfo/interface/Graph.h` |
    | `truth::Particle` | `SimDataFormats/TruthInfo/interface/Particle.h` |
    | `truth::Vertex` | `SimDataFormats/TruthInfo/interface/Vertex.h` |
    | `truth::ParticleData` | `SimDataFormats/TruthInfo/interface/ParticleData.h` |
    | `truth::VertexData`, `truth::VertexRole`, `truth::VertexReason` | `SimDataFormats/TruthInfo/interface/VertexData.h` |
    | `truth::Checkpoint` | `SimDataFormats/TruthInfo/interface/Checkpoint.h` |
    | `truth::Branch`, `truth::ClosureSpec`, `truth::ClosureKind` | `PhysicsTools/TruthInfo/interface/Branch.h` |
    | `truth::BranchSelector` | `PhysicsTools/TruthInfo/interface/BranchSelector.h` |
    | `truth::BranchHitAssociator`, `truth::RecoHit`, `truth::BranchMatch`, `truth::HasTruthHits` | `PhysicsTools/TruthInfo/interface/BranchHitAssociator.h` |
    | `truth::recoHits(...)` adapters | `PhysicsTools/TruthInfo/interface/RecoHitAdapters.h` |
    | `truth::LogicalGraphHitIndex`, `truth::HitChannel` | `SimDataFormats/TruthInfo/interface/LogicalGraphHitIndex.h` |

## The bipartite Particle ↔ Vertex CSR model

`truth::Graph` is the EDM product. It stores two parallel payload arrays:
`std::vector<ParticleData> particles` and `std::vector<VertexData> vertices`. It
also stores four CSR adjacency structures. These structures wire particles to
vertices and back:

| Direction | Offsets array | Targets array |
|---|---|---|
| particle → its decay vertices | `particleToDecayVertexOffsets` | `particleToDecayVertices` |
| particle → its production vertices | `particleToProductionVertexOffsets` | `particleToProductionVertices` |
| vertex → outgoing particles | `vertexToOutgoingParticleOffsets` | `vertexToOutgoingParticles` |
| vertex → incoming particles | `vertexToIncomingParticleOffsets` | `vertexToIncomingParticles` |

The truth graph is **bipartite**. An edge always crosses realms: a particle points
only at vertices, and a vertex points only at particles. There is no direct
particle→particle edge. "The children of a particle" means *the outgoing particles
of its decay vertices*. The handle API hides this for you, because
`Particle::children()` does the two hops. The raw spans are public, so you can also
walk the CSR by hand:

```cpp
auto const& graph = event.get(graphToken_);            // truth::Graph
for (uint32_t pid = 0; pid < graph.nParticles(); ++pid) {
  for (uint32_t vid : graph.decayVertices(pid))        // std::span<const uint32_t>
    for (uint32_t cid : graph.outgoingParticles(vid))  // children of pid
      use(graph.particles()[cid]);
}
```

`Particle` and `Vertex` are **lightweight non-owning handles**. Each one is a
`(Graph const*, uint32_t id)` pair. They are cheap to copy and to pass by value.
They are only valid while the `Graph` they reference is alive. A
default-constructed handle has `valid() == false`, because its `graph_` is null. A
query that may find nothing returns `std::optional<Particle>`.

## `truth::ParticleData`

`Particle::data()` returns a `const ParticleData&`. This is the per-particle
payload:

| Member | Type | Meaning |
|---|---|---|
| `genNode` | `int32_t` | raw `TruthGraph` GEN node, `-1` if none |
| `simNode` | `int32_t` | raw `TruthGraph` SIM node, `-1` if none |
| `pdgId` | `int32_t` | PDG id (signed) |
| `status` | `int16_t` | generator/sim status code |
| `statusFlags` | `uint16_t` | packed `reco::GenStatusFlags`; `0` = none/not available |
| `eventId` | `uint64_t` | packed `EncodedEventId` (bunch crossing + event); `0` if none |
| `genEvent` | `int32_t` | GEN connected-component id from the raw graph; `-1` if N/A |
| `momentum` | `math::XYZTLorentzVectorD` | four-momentum (GEN p4 for GEN+SIM, SimTrack p4 for SIM-only) |
| `checkpoints` | `std::vector<Checkpoint>` | optional trajectory checkpoints |
| `backscattered` | `bool` | Geant4 marked the track as inward albedo crossing CALO to Tracker |

`bool hasGen() const` ⇔ `genNode >= 0`; `bool hasSim() const` ⇔ `simNode >= 0`;
`bool valid() const` ⇔ `hasGen() || hasSim()`.

A `Checkpoint` is `{ uint32_t checkpointId; math::XYZTLorentzVectorF position;
math::XYZTLorentzVectorF momentum; }`. It is a snapshot of the position and the
momentum along the trajectory. Geant4 records it, for example as the particle
crosses a calorimeter boundary. Checkpoints exist only for the merged GEN+SIM
particles that Geant4 propagated far enough.

## `truth::VertexData`

| Member | Type | Meaning |
|---|---|---|
| `genNode`, `simNode` | `int32_t` | raw-graph back-refs, `-1` if none |
| `eventId` | `uint64_t` | packed `EncodedEventId`; `0` if none |
| `genEvent` | `int32_t` | GEN component id; `-1` if N/A |
| `role` | `uint8_t` | a `VertexRole` stored as its underlying type |
| `reason` | `uint8_t` | a `VertexReason` stored as its underlying type |
| `position` | `math::XYZTLorentzVectorD` | best-available position (SIM if present, else GEN) |

`hasGen()`, `hasSim()` and `valid()` work as above. `VertexRole vertexRole() const`
and `bool isArtificial() const` decode `role`. `VertexReason vertexReason() const`
decodes `reason`. The free helper `vertexReasonName(VertexReason)` gives its name.
The roles are:

- `VertexRole::Normal` is a real GEN/SIM vertex.
- `VertexRole::Interaction` is the per-interaction artificial source vertex. The
  packed `EncodedEventId` keys it, one key per pp collision. It is the single root
  of one interaction. It fans out to that interaction's `Upstream` and
  `UnderlyingEvent` sub-vertices, through artificial connector particles.
- `VertexRole::Upstream` is an artificial vertex. It summarizes the truncated
  production context of the selected roots: ISR, beam and initial-state activity.
- `VertexRole::UnderlyingEvent` is an artificial vertex. It collects the stable
  final-state particles that are in no selected subgraph, that is the underlying
  event.

Artificial vertices carry the `genEvent` and `eventId` of the activity they
summarize. Overlaid pileup graphs therefore stay distinguishable. The signal is
everything reachable from the signal `Interaction` vertex. Each pileup interaction
gets its own `Interaction` vertex. The `Interaction → {Upstream, UnderlyingEvent}`
links go through artificial connector particles, which carry `genNode = simNode =
-1` and `pdgId = 0`. A consumer that walks particles will meet these connector
particles. Filter on `isArtificial()` vertices or on the connector `pdgId` if you
need only real particles.

## `truth::Particle`

Construct a `Particle` with `Particle(Graph const* graph, uint32_t id)`. You also
get one from `graph.particle(id)`, from `graph.particleViews()`, or from any
navigation call.

### Identity and payload accessors

```cpp
bool      valid() const;            // graph_ != nullptr
uint32_t  id() const;
const ParticleData& data() const;

bool      hasGen() const;
bool      hasSim() const;
int32_t   pdgId() const;
int16_t   status() const;
uint16_t  statusFlags() const;
uint64_t  eventId() const;
int32_t   genEvent() const;
bool      backscattered() const;
const math::XYZTLorentzVectorD& momentum() const;
```

### Checkpoints

```cpp
std::span<const Checkpoint>  checkpoints() const;
bool                         hasCheckpoints() const;
std::optional<Checkpoint>    checkpoint(uint32_t checkpointId) const;
```

### Topology predicates

```cpp
bool isRoot() const;   // no parents
bool isLeaf() const;   // no children (stable final-state)
```

### Bipartite neighbors

```cpp
std::vector<Vertex>  productionVertices() const;
std::vector<Vertex>  decayVertices() const;
```

### Relatives and ancestry

```cpp
std::vector<Particle>  parents() const;        // immediate
std::vector<Particle>  children() const;       // immediate
std::vector<Particle>  ancestors() const;      // transitive closure upward
std::vector<Particle>  descendants() const;    // transitive closure downward

bool                       hasAncestorPdgId(int pdgId) const;
std::optional<Particle>    firstAncestorWithPdgId(int pdgId) const;  // nearest such ancestor
std::optional<Particle>    firstCommonAncestor(Particle other) const;  // pairwise LCA
```

`Particle` is equality-comparable through `operator==` and `operator!=`. Two
handles are equal when they carry the same `Graph` and the same id.

!!! note "PDG-id matching is signed"
    `pdgId()`, `hasAncestorPdgId()`, `firstAncestorWithPdgId()`, and the selector's
    `pdgIds` list all compare the **signed** PDG id. To accept a particle and its
    antiparticle, list both (`{15, -15}`) or take `std::abs` yourself.

## `truth::Vertex`

Construct a `Vertex` with `Vertex(Graph const* graph, uint32_t id)`. You also get
one from `graph.vertex(id)`, `graph.vertexViews()`, `graph.sourceVertices()`,
`graph.sinkVertices()`, `Particle::productionVertices()` or
`Particle::decayVertices()`.

```cpp
bool      valid() const;
uint32_t  id() const;
const VertexData& data() const;

bool      hasGen() const;
bool      hasSim() const;
uint64_t  eventId() const;
int32_t   genEvent() const;
const math::XYZTLorentzVectorD& position() const;

bool isSource() const;   // no incoming particles
bool isSink() const;     // no outgoing particles

std::vector<Particle>  incomingParticles() const;
std::vector<Particle>  outgoingParticles() const;
```

`Vertex` is equality-comparable as well.

## `truth::Graph`

```cpp
using size_type = uint32_t;

size_type  nParticles() const;
size_type  nVertices() const;
bool       empty() const;

Particle   particle(size_type id) const;
Vertex     vertex(size_type id) const;

std::vector<Particle>  particleViews() const;   // handles for all particles
std::vector<Vertex>    vertexViews() const;

std::vector<Particle>  roots() const;           // particles with no parents
std::vector<Particle>  leaves() const;          // stable final-state particles
std::vector<Vertex>    sourceVertices() const;
std::vector<Vertex>    sinkVertices() const;

// Multi-source LCA: the single particle from which all inputs descend,
// minimizing total generations. nullopt if they share no ancestor.
std::optional<Particle>  lowestCommonAncestor(std::vector<Particle> const& particles) const;

bool isConsistent() const;   // CSR self-consistency check (debug/tests)
```

The raw CSR spans are `decayVertices(id)`, `productionVertices(id)`,
`outgoingParticles(id)` and `incomingParticles(id)`. Each one returns a
`std::span<const uint32_t>` of neighbor ids. They are the zero-copy fast path that
the handle methods use.

!!! note "`roots()`/`leaves()` vs `lowestCommonAncestor`"
    `roots()` returns the graph extremities, the particles with no parents at all.
    A `Branch` root is a *selected* particle, and it is not necessarily a graph
    root. `lowestCommonAncestor` answers "which particle did this set come from".
    One example is the b quark of a b-jet, given the jet's truth constituents.
    Walk further up with `firstAncestorWithPdgId` to reach a specific origin
    species, such as the top.

## `truth::Branch`

A `Branch` is a non-owning **view** of a coherent subgraph, recomputed on demand.
It holds one or more root particles plus a *closure* of their descendants. It
stores no graph data and is **not an EDM product**. It is the dynamic successor to
the static `CaloParticle` and `TrackingParticle`.

### Construction and closures

```cpp
Branch(Graph const* graph, uint32_t rootId,             ClosureSpec spec = ClosureSpec::subtree());
Branch(Graph const* graph, std::vector<uint32_t> rootIds, ClosureSpec spec = ClosureSpec::subtree());
```

The closure (`ClosureSpec` and `ClosureKind`) controls how far below the roots the
branch extends:

| Factory | Kind | Behavior |
|---|---|---|
| `ClosureSpec::subtree()` | `Subtree` | the full descendant subtree (default) |
| `ClosureSpec::stableLeaves()` | `StableLeaves` | roots + final-state (childless) particles only |
| `ClosureSpec::depth(n)` | `DepthN` | keep `n` generations below each root (`0` = roots only) |
| `ClosureSpec::untilPdgId(ids)` | `UntilPdgId` | stop at (and include) particles whose pdgId is in `ids` |
| `ClosureSpec::predicate(p)` | `Predicate` | stop at (and include) particles where `std::function<bool(Particle)>` is true |

The traversal is a BFS from the roots. `members()`, `memberIds()` and
`stableLeaves()` return ascending-id, deduplicated results.

### Members, roots, kinematics

```cpp
bool                  valid() const;          // non-null graph and at least one root
Graph const*          graph() const;
Particle              root() const;           // first root
std::vector<Particle> roots() const;
std::vector<uint32_t> rootIds() const;
ClosureSpec const&    closure() const;

std::vector<uint32_t> memberIds() const;
std::vector<Particle> members() const;
std::vector<Particle> stableLeaves() const;

math::XYZTLorentzVectorD  p4() const;          // sum over stable leaves
math::XYZTLorentzVectorD  visibleP4() const;   // excludes neutrinos (|pdg| 12/14/16)
double                    energy() const;          // p4().energy()
double                    visibleEnergy() const;   // visibleP4().energy()
double                    invisibleEnergy() const; // energy() - visibleEnergy()
```

### Tagging and origin

```cpp
int32_t                  rootPdgId() const;
std::optional<Particle>  originWithPdgId(int32_t pdgId) const;  // root if it matches, else nearest ancestor
bool                     hasHeavyFlavor(int32_t quarkFlavor) const;  // any member is a flavor-q hadron (5=b, 4=c)
```

### Provenance (pile-up aware)

These accessors give the source event of the root. They decode it from the
`EncodedEventId` of the root:

```cpp
int32_t  genEvent() const;
int      bunchCrossing() const;
int      event() const;
bool     isInTime() const;     // bunchCrossing() == 0
bool     isFromPileup() const; // !isSignal(). In-time pileup has bunchCrossing() 0
                               // and a nonzero event(), and the default production
                               // keeps in-time pileup only, so a bunch-crossing test
                               // would miss every pileup particle in it.
bool     isSignal() const;     // bunchCrossing() == 0 && event() == 0
```

### Relations between branches

```cpp
std::optional<Particle>  commonAncestor(Branch const& other) const;  // LCA over both root sets
Branch                   merged(Branch const& other) const;          // union of roots, same closure
```

!!! warning "Single-root vs multi-root semantics"
    `rootPdgId()`, `genEvent()`, `bunchCrossing()`, `event()`, and the provenance
    predicates read the **first** root (`roots_.front()`). For a multi-root branch
    they describe that first root only. `commonAncestor()` and `merged()` operate
    over **all** roots of both branches.

## `truth::BranchSelector`

`BranchSelector` is a configurable predicate over branches. It mirrors the cut
surface of `TrackingParticleSelector` and `CaloParticleSelector`. It takes the
branch kinematics from the **root** particle.

```cpp
struct BranchSelector::Config {
  double ptMin   = 0.;
  double ptMax   = 1e100;
  double etaMin  = -1e100;
  double etaMax  = 1e100;
  std::vector<int32_t> pdgIds;   // empty = accept all; matched on signed PDG id
  bool signalOnly = false;       // bunchCrossing == 0 and event == 0
  bool intimeOnly = false;       // bunchCrossing == 0
  bool chargedOnly = false;      // root particle electrically charged
  bool invertEta = false;        // keep |eta| OUTSIDE [etaMin, etaMax]
};

BranchSelector();
explicit BranchSelector(Config config);
bool          operator()(Branch const& branch) const;   // true = passes
Config const& config() const;
```

Charge for `chargedOnly` comes from `HepPDT::ParticleID(pdgId).threeCharge()`.

## `truth::LogicalGraphHitIndex`

`truth::LogicalGraphHitIndex` is the per-logical-particle hit index. It indexes
hits by particle id and by detector **channel**. An enum keys the channels, so you
can add detectors without new hardcoded members:

```cpp
enum class HitChannel : uint8_t { Tracker = 0, MTD = 1, Calo = 2, Muon = 3 };
inline constexpr std::size_t kNumHitChannels = 4;
```

Each particle has two hit sets per channel. The **direct** hits are the hits on its
own `SimTrack`. The **subgraph** hits are its own hits plus the hits of every
logical descendant. The accessors take the channel first, then the particle id:

```cpp
uint32_t                     nParticles() const;
static constexpr std::size_t nChannels();   // == kNumHitChannels

std::span<const Hit>  directHits(HitChannel channel, uint32_t particleId) const;
std::span<const Hit>  subgraphHits(HitChannel channel, uint32_t particleId) const;
void                  appendSubgraphHits(HitChannel channel, uint32_t particleId,
                                         std::vector<Hit>& out) const;

bool                       sharedSubgraphStore() const;       // which layout, see below
std::span<const SlotRange> subgraphRanges(uint32_t particleId) const;
std::span<const Hit>       rangeHits(HitChannel channel, SlotRange range) const;

bool                  hasChannel(HitChannel channel) const;   // channel is filled
Channel const&        channel(HitChannel channel) const;      // raw flat storage
```

A `Hit` is `{ uint32_t detId; uint32_t recHitIndex; float energy; }`. It carries
`bool hasRecHit() const` (⇔ `recHitIndex != Hit::kInvalidRecHitIndex`). Only
channels that carry a DetId→RecHit link set `recHitIndex`, that is `Calo`. The
tracker leaves it invalid.

### Two storage layouts

The layout an index carries is a property of the **data**, not of the reading job.
`sharedSubgraphStore()` reports the layout. The accessors handle both layouts, so
an index written either way reads back correctly.

**Shared, the default.** The index stores each hit once. It orders the hits so that
the descendants of a particle occupy the slots right after it. A subgraph is then a
set of ranges of that one store. A range is

```cpp
struct SlotRange { uint32_t firstSlot = 0; uint32_t slotCount = 0; };
```

and it costs no hit storage at all. This layout removed the dominant cost of the
index. The materialised layout stored a hit once per ancestor containing it. That
turned 26744 hits per event into 46259 stored entries with no GEN half, and into
1467228 stored entries with the full GEN half.

**Materialised** (`sharedSubgraphStore=False`). Here `subgraphOffsets` and
`subgraphHits` hold a second copy of the hits of every descendant under each
ancestor. That copy is coalesced and DetId-sorted. Every index written before the
shared layout existed carries this layout too, which is why the read path stays.

!!! warning "Use `truth::SubgraphHitView`, not `subgraphHits()`, for an arbitrary particle"
    `subgraphHits()` returns a single span. A GEN-only particle owns several
    ranges, so under the shared layout that span is **empty**. Hold a
    `truth::SubgraphHitView`
    (`PhysicsTools/TruthInfo/interface/SubgraphHitView.h`) if the particle you pass
    can be any node of the truth graph. Call its `subgraphHits`. It returns the
    coalesced, detId-sorted span in **either** layout, and it caches the coalesced
    form for the rest of the event. Hold one per event and per module. It is not
    thread safe. Every in-tree consumer already goes through it.

!!! warning "A shared range is not coalesced"
    In the shared layout a subgraph range is in **tree order**, not in DetId order.
    It repeats a DetId hit once per contributing descendant. Sum the entries that
    share a DetId yourself if you need per-cell energies. `BranchHitAssociator`
    does exactly this, once per candidate root at construction, so its own results
    are unchanged.

    `subgraphHits()` returns a single span. That is correct for every particle that
    carries hits. A **GEN-only** particle sits above the SIM tree in a DAG and
    spans several ranges, so `subgraphHits()` returns an empty span for it. Use
    `appendSubgraphHits()`, which is correct for every particle in both layouts, or
    iterate `subgraphRanges()`.

A `Channel` is the CSR struct
`{ directOffsets, directHits, subgraphOffsets, subgraphHits, dfsOffsets }`. The
index exposes it for callers that scan a whole channel, for example the
inverted-index build of `BranchHitAssociator`. Most consumers use the span
accessors above.

!!! note "Empty channels return empty spans"
    `directHits` and `subgraphHits` return an **empty span**, not an error, on a
    channel that was not filled. They also return an empty span for an
    out-of-range particle id. The `subdetectors` list selects which channels are
    filled. Gate on `hasChannel(channel)` if you need to distinguish "no hits" from
    "channel not built".

## `truth::BranchHitAssociator`

`BranchHitAssociator` matches reco objects to truth branches by shared detector
hits. You build it once per event over a set of candidate branch roots, where an
empty set means every particle. It caches an inverted `detId → roots` index plus
the per-cell total sim energy. It holds both as flat sorted arrays, binary-searched,
with no per-event hashing.

```cpp
enum class Metric { SharedEnergy, SharedHits };

explicit BranchHitAssociator(LogicalGraphHitIndex const& hitIndex,
                             std::vector<uint32_t> candidateRoots = {},
                             Metric metric = Metric::SharedEnergy,
                             HitChannel channel = HitChannel::Calo,
                             bool emptyRootsMeansAll = true,
                             uint32_t denominatorDetectors = kAllDetectors);

std::vector<BranchMatch> bestBranches(std::span<const RecoHit> recoHits,
                                      std::size_t maxResults = 0) const;  // 0 = all

template <HasTruthHits R>
std::vector<BranchMatch> bestBranches(R const& reco, std::size_t maxResults = 0) const;

BranchMatch bestAdaptiveBranch(std::span<const RecoHit> recoHits,
                               float reverseWeight = 1.f,
                               float maxReverseScore = 1.f) const;
```

`emptyRootsMeansAll` guards the restricted-root case. With the default, an empty
`candidateRoots` means "every particle". Pass `false` when an empty list must
instead mean "no candidates". A selection that legitimately returns nothing then
does not silently widen to the whole event.

`denominatorDetectors` is a bit per `DetId::det()` value. It names the detectors
that the `sharedEnergyFraction` denominator covers. One hit channel spans several
detectors. `HitChannel::Calo` carries the barrel ECAL and HCAL deposits next to the
HGCAL ones. Their sampling energies are orders of magnitude apart. A branch that
showered in the barrel therefore has a channel-wide energy that no endcap reco
object can share half of. Pass the detectors that your reco collection
reconstructs. `kAllDetectors` keeps the whole channel. This does not affect the two
scores. They keep the denominators that the TICL association gives them.

`bestBranches` sorts the result by `score` ascending, where lower is better:

```cpp
struct BranchMatch {
  static constexpr uint32_t kInvalidRoot = 0xFFFFFFFFu;

  uint32_t rootParticleId = 0;
  float    sharedEnergy = 0.f;   // (SharedHits metric: number of shared cells)
  float    score = 0.f;          // reco-normalized, lower is better
  float    reverseScore = 0.f;   // branch-normalized: how far the branch spreads
  float    sharedEnergyFraction = 0.f;  // sim-normalized: shared energy over the
                                        // branch's energy in denominatorDetectors
};
```

### Adaptive-level matching

`bestAdaptiveBranch` answers a different question from `bestBranches`.
`bestBranches` answers "which branches share hits with this object".
`bestAdaptiveBranch` answers "at which level of the truth graph does this object
best correspond to a single branch". It looks at every candidate root that shares
hits with the reco object. When the candidate set is the ancestor closure, those
candidate roots are the leaves and their ancestors. It returns the root that
minimizes

```
score + reverseWeight * reverseScore
```

`score` falls as the branch climbs and covers more of the reco object.
`reverseScore` rises as the branch spreads into energy that the reco object does
not have. The minimum is therefore the level that matches the object best.
`bestAdaptiveBranch` rejects candidates whose `reverseScore` exceeds
`maxReverseScore`. If that leaves no candidate, it ignores the ceiling and returns
the global minimum. When the reco object shares no hits with any root,
`rootParticleId` is `BranchMatch::kInvalidRoot`.

The hit format is `truth::RecoHit { uint32_t detId; float energy; float fraction; }`.
A reco object satisfies the `HasTruthHits` concept when it exposes a `truthHits()`
member returning a range of `RecoHit`. Any such object works with the templated
`bestBranches` overload directly. For objects that do not own their hits, use the
free-function adapters in `RecoHitAdapters.h`:

```cpp
std::vector<RecoHit> truth::recoHits(reco::Track const& track);
std::vector<RecoHit> truth::recoHits(reco::CaloCluster const& layerCluster);
std::vector<RecoHit> truth::recoHits(ticl::Trackster const& trackster,
                                     std::vector<reco::CaloCluster> const& layerClusters);
```

- `Metric::SharedEnergy` is the HGCal-style by-hits score that compares cell
  fractions. It is the convention that the calo association producers use.
- `Metric::SharedHits` counts shared cells, and `sharedEnergy` then holds that
  count. It is the natural metric for the tracker, where hits carry no per-cell
  energy.
- The `channel` argument selects which `HitChannel` of the hit index `bestBranches`
  matches against. Use `HitChannel::Calo`, the default, for calorimeter objects.
  Use `HitChannel::Tracker` for tracks. More channels follow once MTD and Muon are
  filled.

See [How to use the graph → matching an arbitrary reco object](usage.md#matching-an-arbitrary-reco-object-to-a-branch)
for end-to-end snippets. See [Physics questions](examples.md#physics-questions-the-interface-answers)
for what these methods let you ask.
