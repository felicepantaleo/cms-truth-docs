# Interface reference

This page is the precise reference for the user-facing C++ interface of the logical
truth graph: the `truth::Graph` navigation API, the `truth::Branch` subgraph view,
and the `truth::BranchSelector` / `truth::BranchHitAssociator` helpers. Every
signature below is copied from the authoritative headers in
`PhysicsTools/TruthInfo/interface/`; for the design rationale see the
[Data model](data-model.md), and for narrative walk-throughs see
[How to use the graph](usage.md) and [Worked examples](examples.md).

!!! note "Where each symbol lives"
    | Symbol | Header |
    |---|---|
    | `truth::Graph`, `truth::Particle`, `truth::Vertex`, `truth::ParticleData`, `truth::VertexData`, `truth::Checkpoint`, `truth::VertexRole` | `interface/Graph.h` |
    | `truth::Branch`, `truth::ClosureSpec`, `truth::ClosureKind` | `interface/Branch.h` |
    | `truth::BranchSelector` | `interface/BranchSelector.h` |
    | `truth::BranchHitAssociator`, `truth::RecoHit`, `truth::BranchMatch`, `truth::HasTruthHits` | `interface/BranchHitAssociator.h` |
    | `truth::recoHits(...)` adapters | `interface/RecoHitAdapters.h` |
    | `truth::LogicalGraphHitIndex` | `interface/LogicalGraphHitIndex.h` |

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
      use(graph.particles[cid]);
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
| `position` | `math::XYZTLorentzVectorD` | best-available position (SIM if present, else GEN) |

`hasGen()`/`hasSim()`/`valid()` as above. `VertexRole vertexRole() const` and
`bool isArtificial() const` decode `role`. The roles are:

- `VertexRole::Normal` — a real GEN/SIM vertex.
- `VertexRole::Upstream` — an artificial source vertex summarizing the truncated
  production context of the selected roots (ISR / beam / initial-state activity).
- `VertexRole::UnderlyingEvent` — an artificial source vertex collecting stable
  final-state particles that are in no selected subgraph (underlying event).

Artificial vertices carry the `genEvent`/`eventId` of the activity they summarize,
so overlaid pile-up graphs stay distinguishable.

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
                             bool useTracker = false);

std::vector<BranchMatch> bestBranches(std::span<const RecoHit> recoHits,
                                      std::size_t maxResults = 0) const;  // 0 = all

template <HasTruthHits R>
std::vector<BranchMatch> bestBranches(R const& reco, std::size_t maxResults = 0) const;
```

The result is sorted by `score` ascending (lower is better):

```cpp
struct BranchMatch {
  uint32_t rootParticleId = 0;
  float    sharedEnergy = 0.f;  // (SharedHits metric: number of shared cells)
  float    score = 0.f;         // lower is better
};
```

The hit format is `truth::RecoHit { uint32_t detId; float energy; float fraction; }`.
Any reco object that satisfies the `HasTruthHits` concept — exposes a `truthHits()`
member returning a range of `RecoHit` — works with the templated `bestBranches`
overload directly. For objects that do not own their hits, use the free-function
adapters in `RecoHitAdapters.h`:

```cpp
std::vector<RecoHit> truth::recoHits(reco::Track const& track);
std::vector<RecoHit> truth::recoHits(ticl::Trackster const& trackster,
                                     std::vector<reco::CaloCluster> const& layerClusters);
```

- `Metric::SharedEnergy` is the HGCal-style by-hits score comparing cell fractions
  (the convention the calo association producers use).
- `Metric::SharedHits` counts shared cells (`sharedEnergy` then holds that count);
  the natural metric for the tracker, where hits carry no per-cell energy.
- `useTracker = true` switches `bestBranches` from the calo channel
  (`subgraphHits`) to the tracker channel (`trackerSubgraphHits`).

See [How to use the graph → matching an arbitrary reco object](usage.md#matching-an-arbitrary-reco-object-to-a-branch)
for end-to-end snippets, and [Physics questions](examples.md#physics-questions-the-interface-answers)
for what these methods let you ask.
