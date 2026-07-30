# Interface reference

This page is the precise reference for the user-facing C++ interface of the logical
truth graph: the `truth::Graph` navigation API, the `truth::Branch` subgraph view,
and the `truth::BranchSelector` / `truth::BranchHitAssociator` helpers. Every
signature below is quoted from the authoritative headers (with `[[nodiscard]]`
omitted for brevity), which live in two packages:
the data-model headers in `SimDataFormats/TruthInfo/interface/` and the analysis-layer
headers in `PhysicsTools/TruthInfo/interface/`; for the design rationale see the
[Data model](data-model.md), and for narrative walk-throughs see
[How to use the graph](usage.md) and [Worked examples](examples.md).

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

`truth::Graph` is the EDM product. It stores two parallel payload arrays —
`std::vector<ParticleData> particles` and `std::vector<VertexData> vertices` — and
four CSR adjacency structures that wire particles to vertices and back:

| Direction | Offsets array | Targets array |
|---|---|---|
| particle → its decay vertices | `particleToDecayVertexOffsets` | `particleToDecayVertices` |
| particle → its production vertices | `particleToProductionVertexOffsets` | `particleToProductionVertices` |
| vertex → outgoing particles | `vertexToOutgoingParticleOffsets` | `vertexToOutgoingParticles` |
| vertex → incoming particles | `vertexToIncomingParticleOffsets` | `vertexToIncomingParticles` |

The graph is **bipartite**: an edge always crosses realms — a particle points only
at vertices, a vertex only at particles. There is no direct particle→particle edge;
"the children of a particle" means *the outgoing particles of its decay vertices*.
The handle API hides this for you (`Particle::children()` does the two hops), but
the raw spans are public if you want to walk the CSR by hand:

```cpp
auto const& graph = event.get(graphToken_);            // truth::Graph
for (uint32_t pid = 0; pid < graph.nParticles(); ++pid) {
  for (uint32_t vid : graph.decayVertices(pid))        // std::span<const uint32_t>
    for (uint32_t cid : graph.outgoingParticles(vid))  // children of pid
      use(graph.particles()[cid]);
}
```

`Particle` and `Vertex` are **lightweight non-owning handles** — a `(Graph const*,
uint32_t id)` pair, cheap to copy and pass by value. They are only valid while the
`Graph` they reference is alive. A default-constructed handle has
`valid() == false` (its `graph_` is null); `std::optional<Particle>` is returned
wherever a query may find nothing.

## `truth::ParticleData`

The per-particle payload (`Particle::data()` returns a `const ParticleData&`):

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
math::XYZTLorentzVectorF momentum; }` — a position/momentum snapshot of the
trajectory recorded by Geant4 (e.g. as the particle crosses a calorimeter
boundary). Checkpoints exist only for the merged GEN+SIM particles that Geant4
propagated far enough.

## `truth::VertexData`

| Member | Type | Meaning |
|---|---|---|
| `genNode`, `simNode` | `int32_t` | raw-graph back-refs, `-1` if none |
| `eventId` | `uint64_t` | packed `EncodedEventId`; `0` if none |
| `genEvent` | `int32_t` | GEN component id; `-1` if N/A |
| `role` | `uint8_t` | a `VertexRole` stored as its underlying type |
| `reason` | `uint8_t` | a `VertexReason` stored as its underlying type |
| `position` | `math::XYZTLorentzVectorD` | best-available position (SIM if present, else GEN) |

`hasGen()`/`hasSim()`/`valid()` as above. `VertexRole vertexRole() const` and
`bool isArtificial() const` decode `role`, and `VertexReason vertexReason() const`
decodes `reason` (the free helper `vertexReasonName(VertexReason)` gives its name).
The roles are:

- `VertexRole::Normal` — a real GEN/SIM vertex.
- `VertexRole::Interaction` — the per-interaction artificial source vertex, keyed
  by the packed `EncodedEventId` (one per pp collision). It is the single root of
  one interaction and fans out, through artificial connector particles, to that
  interaction's `Upstream` and `UnderlyingEvent` sub-vertices.
- `VertexRole::Upstream` — an artificial vertex summarizing the truncated
  production context of the selected roots (ISR / beam / initial-state activity).
- `VertexRole::UnderlyingEvent` — an artificial vertex collecting stable
  final-state particles that are in no selected subgraph (underlying event).

Artificial vertices carry the `genEvent`/`eventId` of the activity they summarize,
so overlaid pile-up graphs stay distinguishable: the signal is everything reachable
from the signal `Interaction` vertex, and each pile-up interaction gets its own.
The `Interaction → {Upstream, UnderlyingEvent}` links go through artificial
connector particles (`genNode = simNode = -1`, `pdgId = 0`), so a consumer that
walks particles will encounter them — filter on `isArtificial()` vertices or the
connector `pdgId` if you need only real particles.

## `truth::Particle`

Construct with `Particle(Graph const* graph, uint32_t id)`; obtain from
`graph.particle(id)`, `graph.particleViews()`, or any navigation call.

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

`Particle` is equality-comparable (`operator==`/`operator!=`) — same graph and same
id.

!!! note "PDG-id matching is signed"
    `pdgId()`, `hasAncestorPdgId()`, `firstAncestorWithPdgId()`, and the selector's
    `pdgIds` list all compare the **signed** PDG id. To accept a particle and its
    antiparticle, list both (`{15, -15}`) or take `std::abs` yourself.

## `truth::Vertex`

Construct with `Vertex(Graph const* graph, uint32_t id)`; obtain from
`graph.vertex(id)`, `graph.vertexViews()`, `graph.sourceVertices()`,
`graph.sinkVertices()`, or `Particle::productionVertices()` / `decayVertices()`.

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

The raw CSR spans (`decayVertices(id)`, `productionVertices(id)`,
`outgoingParticles(id)`, `incomingParticles(id)`) each return a
`std::span<const uint32_t>` of neighbor ids — the zero-copy fast path used by the
handle methods.

!!! note "`roots()`/`leaves()` vs `lowestCommonAncestor`"
    `roots()` are graph extremities (no parents at all); a `Branch` root is a
    *selected* particle, not necessarily a graph root. `lowestCommonAncestor`
    answers "which particle did this set come from" — e.g. the b quark of a b-jet
    given the jet's truth constituents; walk further up with
    `firstAncestorWithPdgId` to reach a specific origin species (the top).

## `truth::Branch`

A `Branch` is a non-owning, recomputed-on-demand **view** of a coherent subgraph:
one or more root particles plus a *closure* of their descendants. It stores no graph
data and is **not an EDM product**; it is the dynamic successor to the static
`CaloParticle`/`TrackingParticle`.

### Construction and closures

```cpp
Branch(Graph const* graph, uint32_t rootId,             ClosureSpec spec = ClosureSpec::subtree());
Branch(Graph const* graph, std::vector<uint32_t> rootIds, ClosureSpec spec = ClosureSpec::subtree());
```

The closure (`ClosureSpec` / `ClosureKind`) controls how far below the root(s) the
branch extends:

| Factory | Kind | Behavior |
|---|---|---|
| `ClosureSpec::subtree()` | `Subtree` | the full descendant subtree (default) |
| `ClosureSpec::stableLeaves()` | `StableLeaves` | roots + final-state (childless) particles only |
| `ClosureSpec::depth(n)` | `DepthN` | keep `n` generations below each root (`0` = roots only) |
| `ClosureSpec::untilPdgId(ids)` | `UntilPdgId` | stop at (and include) particles whose pdgId is in `ids` |
| `ClosureSpec::predicate(p)` | `Predicate` | stop at (and include) particles where `std::function<bool(Particle)>` is true |

The traversal is a BFS from the roots; `members()`, `memberIds()`, and
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

The source event of the root, decoded from its `EncodedEventId`:

```cpp
int32_t  genEvent() const;
int      bunchCrossing() const;
int      event() const;
bool     isInTime() const;     // bunchCrossing() == 0
bool     isFromPileup() const; // bunchCrossing() != 0
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

A configurable predicate over branches, mirroring the cut surface of
`TrackingParticleSelector` / `CaloParticleSelector`. Branch kinematics are taken
from the **root** particle.

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

The per-logical-particle hit index, indexed by particle id and by detector
**channel**. Channels are keyed by an enum so detectors can be added without new
hardcoded members:

```cpp
enum class HitChannel : uint8_t { Tracker = 0, MTD = 1, Calo = 2, Muon = 3 };
inline constexpr std::size_t kNumHitChannels = 4;
```

Each particle has, per channel, its **direct** hits (on its own `SimTrack`) and its
**subgraph** hits (its own plus every logical descendant's). The accessors take the
channel first, then the particle id:

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

A `Hit` is `{ uint32_t detId; uint32_t recHitIndex; float energy; }` with
`bool hasRecHit() const` (⇔ `recHitIndex != Hit::kInvalidRecHitIndex`). `recHitIndex`
is set only for channels carrying a DetId→RecHit link (`Calo`); the tracker
leaves it invalid.

### Two storage layouts

Which layout an index carries is a property of the **data**, not of the reading job.
`sharedSubgraphStore()` reports it and the accessors handle both, so an index written
either way reads back correctly.

**Shared, the default.** Each hit is stored once, ordered so that a particle's
descendants occupy the slots right after it. A subgraph is then a set of ranges of that
one store, where a range is

```cpp
struct SlotRange { uint32_t firstSlot = 0; uint32_t slotCount = 0; };
```

and costs no hit storage at all. This removed the dominant cost of the index:
the materialised layout stored a hit once per ancestor containing it, turning 26744 hits
per event into 46259 stored entries with no GEN half, and 1467228 with the full one.

**Materialised** (`sharedSubgraphStore=False`). `subgraphOffsets`/`subgraphHits` hold a second,
coalesced and DetId-sorted copy of every descendant's hits under each ancestor. Every
index written before the shared layout existed carries this too, which is why the read
path stays.

!!! warning "Use `truth::SubgraphHitView`, not `subgraphHits()`, for an arbitrary particle"
    `subgraphHits()` returns a single span, so under the shared layout it is **empty** for
    a GEN-only particle, which owns several ranges. If the particle you pass can be any
    node of the graph, hold a `truth::SubgraphHitView`
    (`PhysicsTools/TruthInfo/interface/SubgraphHitView.h`) and call its `subgraphHits`:
    it returns the coalesced, detId-sorted span in **either** layout, caching the
    coalesced form for the rest of the event. One per event and per module; it is not
    thread safe. Every in-tree consumer already goes through it.

!!! warning "A shared range is not coalesced"
    In the shared layout a subgraph range is in **tree order**, not DetId order, and
    repeats a DetId hit once per contributing descendant. If you need per-cell energies,
    sum the entries sharing a DetId yourself. `BranchHitAssociator` does exactly this,
    once per candidate root when it is constructed, so its own results are unchanged.

    `subgraphHits()` returns a single span, which is correct for every particle that
    carries hits. A **GEN-only** particle sits above the SIM tree in a DAG and spans
    several ranges, so it returns an empty span there. Use `appendSubgraphHits()`, which
    is correct for every particle in both layouts, or iterate `subgraphRanges()`.

A `Channel` is the CSR struct
`{ directOffsets, directHits, subgraphOffsets, subgraphHits, dfsOffsets }`, exposed for
callers that scan a whole channel (e.g. `BranchHitAssociator`'s inverted-index build);
most consumers use the span accessors above.

!!! note "Empty channels return empty spans"
    `directHits`/`subgraphHits` on a channel that was not filled (the `subdetectors`
    list selects which ones are) or an
    out-of-range particle id return an **empty span**, not an error. Gate on
    `hasChannel(channel)` if you need to distinguish "no hits" from "channel not
    built".

## `truth::BranchHitAssociator`

Matches reco objects to truth branches by shared detector hits. Built once per
event over a set of candidate branch roots (empty = every particle); it caches an
inverted `detId → roots` index plus per-cell total sim energy as flat sorted arrays
(binary-searched, no per-event hashing).

```cpp
enum class Metric { SharedEnergy, SharedHits };

explicit BranchHitAssociator(LogicalGraphHitIndex const& hitIndex,
                             std::vector<uint32_t> candidateRoots = {},
                             Metric metric = Metric::SharedEnergy,
                             HitChannel channel = HitChannel::Calo,
                             bool emptyRootsMeansAll = true);

std::vector<BranchMatch> bestBranches(std::span<const RecoHit> recoHits,
                                      std::size_t maxResults = 0) const;  // 0 = all

template <HasTruthHits R>
std::vector<BranchMatch> bestBranches(R const& reco, std::size_t maxResults = 0) const;

BranchMatch bestAdaptiveBranch(std::span<const RecoHit> recoHits,
                               float reverseWeight = 1.f,
                               float maxReverseScore = 1.f) const;
```

`emptyRootsMeansAll` guards the restricted-root case: with the default, an empty
`candidateRoots` means "every particle"; pass `false` when an empty list must instead
mean "no candidates", so a selection that legitimately returns nothing does not
silently widen to the whole event.

The result is sorted by `score` ascending (lower is better):

```cpp
struct BranchMatch {
  static constexpr uint32_t kInvalidRoot = 0xFFFFFFFFu;

  uint32_t rootParticleId = 0;
  float    sharedEnergy = 0.f;   // (SharedHits metric: number of shared cells)
  float    score = 0.f;          // reco-normalized, lower is better
  float    reverseScore = 0.f;   // branch-normalized: how far the branch spreads
};
```

### Adaptive-level matching

`bestAdaptiveBranch` answers a different question from `bestBranches`: not "which
branches share hits with this object" but "at which level of the graph does this
object best correspond to a single branch". Among every candidate root sharing hits
with the reco object (leaves and their ancestors, when the candidate set is the
ancestor closure) it returns the one minimizing

```
score + reverseWeight * reverseScore
```

`score` falls as the branch climbs and covers more of the reco object, while
`reverseScore` rises as the branch spreads into energy the reco object does not have,
so the minimum is the level that matches the object best. Candidates whose
`reverseScore` exceeds `maxReverseScore` are rejected; if that empties the candidate
set the ceiling is ignored and the global minimum is returned. When the reco object
shares no hits with any root, `rootParticleId` is `BranchMatch::kInvalidRoot`.

The hit format is `truth::RecoHit { uint32_t detId; float energy; float fraction; }`.
Any reco object that satisfies the `HasTruthHits` concept — exposes a `truthHits()`
member returning a range of `RecoHit` — works with the templated `bestBranches`
overload directly. For objects that do not own their hits, use the free-function
adapters in `RecoHitAdapters.h`:

```cpp
std::vector<RecoHit> truth::recoHits(reco::Track const& track);
std::vector<RecoHit> truth::recoHits(reco::CaloCluster const& layerCluster);
std::vector<RecoHit> truth::recoHits(ticl::Trackster const& trackster,
                                     std::vector<reco::CaloCluster> const& layerClusters);
```

- `Metric::SharedEnergy` is the HGCal-style by-hits score comparing cell fractions
  (the convention the calo association producers use).
- `Metric::SharedHits` counts shared cells (`sharedEnergy` then holds that count);
  the natural metric for the tracker, where hits carry no per-cell energy.
- The `channel` argument selects which `HitChannel` of the hit index `bestBranches`
  matches against: `HitChannel::Calo` (the default) for calorimeter objects,
  `HitChannel::Tracker` for tracks, and so on once MTD/Muon are filled.

See [How to use the graph → matching an arbitrary reco object](usage.md#matching-an-arbitrary-reco-object-to-a-branch)
for end-to-end snippets, and [Physics questions](examples.md#physics-questions-the-interface-answers)
for what these methods let you ask.
