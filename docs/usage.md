# How to use the graph

This page is a worked tour of the API: how to put the products in a job, how to
navigate the logical graph, how to select interesting particles, and how to match
an arbitrary reco object to a truth branch. Every method, field, and config label
below exists in `PhysicsTools/TruthInfo`; see the [Data model](data-model.md) for
the design and [Validation](validation.md) for performance plots.

## The three layers and their producers

The package is layered so that each level stays compact and the level above adds
navigation, then physics, then detector hits.

| Layer | Type | Producer | What it is |
|---|---|---|---|
| 1 | `TruthGraph` (raw) | `truthGraphProducer` | typed-node CSR over GEN + SIM (`GenEvent`/`GenVertex`/`GenParticle`/`SimVertex`/`SimTrack` + `GenToSim` edges) |
| 2 | `truth::Graph` (logical) | `truthLogicalGraphProducer` | bipartite `Particle ↔ Vertex` CSR with the physics navigation API |
| 3 | `truth::LogicalGraphHitIndex` | `truthLogicalGraphHitIndexProducer` | per-particle calo/tracker hit spans (direct + aggregated subgraph) |

On top of the logical graph, three non-EDM helpers (used directly in your code, not
products): `truth::Branch` (a recomputed-on-demand subgraph view), `truth::BranchSelector`
(physics selection), and `truth::BranchHitAssociator` (generic hit-based reco↔truth
matching).

## Enabling the truth graph in a job

The producer chain order matters — each consumes the previous:

```
truthGraphProducer → truthLogicalGraphProducer → simHitToRecHitMapProducer → truthLogicalGraphHitIndexProducer
```

In a standard workflow this is gated behind the `enableTruth` process modifier
(`Configuration/ProcessModifiers/enableTruth_cff`), which hooks the
`truthGraphPrevalidation` sequence (in
`Validation/Configuration/python/truthPrevalidation_cff.py`) into global validation
and sets `g4SimHits.TrackingAction.ReconnectDroppedAncestors = True` in the SIM step
so every stored `SimTrack`'s production vertex resolves to a stored ancestor (no
orphans) while `PersistencyEmin` stays at 50 GeV — see
[Findings](findings.md#1-orphan-simvertices-generator-history-retention):

```bash
# Run4 D120 relval with the truth producers enabled in RECO:
runTheMatrix.py -l 34087.88 --what upgrade
```

To run the chain standalone on an existing `step3.root`, use the bundled driver,
which dumps DOT graphs per event and exposes selection options
(`-n/--maxevts`, `-m/--merge`, `-c/--collapse`, `-s/--seeds`, `-f/--flavors`,
`-o/--outdir`):

```bash
cmsRun PhysicsTools/TruthInfo/test/dumpTruthGraphsFromGENSIMRECO_cfg.py step3.root -n 5
```

The minimal cfg wiring is:

```python
process.truthGraphProducer = cms.EDProducer(
    "TruthGraphProducer",
    genEventHepMC3 = cms.InputTag("generatorSmeared"),
    genEventHepMC  = cms.InputTag("generatorSmeared"),
    simTracks      = cms.InputTag("g4SimHits"),
    simVertices    = cms.InputTag("g4SimHits"),
    addGenToSimEdges = cms.bool(True),
)

process.truthLogicalGraphProducer = cms.EDProducer(
    "TruthLogicalGraphProducer",
    src = cms.InputTag("truthGraphProducer"),
    simTracks = cms.InputTag("g4SimHits"),
    simVertices = cms.InputTag("g4SimHits"),
    genEventHepMC3 = cms.InputTag("generatorSmeared"),
    genEventHepMC  = cms.InputTag("generatorSmeared"),
    mergeGenSimVertices = cms.bool(True),
    postProcessing = cms.PSet(
        collapseIntermediateGenParticles = cms.bool(True),
        seedPdgIds = cms.vint32(),          # empty = keep the full logical graph
        seedHadronFlavors = cms.vint32(),
        seedParentDepth = cms.uint32(0),
        keepStableSpectators = cms.bool(True),
        decayPdgIdGroups = cms.VPSet(),
        ignoredPdgIds = cms.vint32(),
        ignoredParticleIds = cms.vuint32(),
    ),
)

# DetId -> global RecHit index map (HGCal collections first, then PF collections).
process.simHitToRecHitMapProducer = cms.EDProducer(
    "SimHitToRecHitMapProducer",
    hgcalRecHits = cms.VInputTag(
        cms.InputTag("HGCalRecHit", "HGCEERecHits", "RECO"),
        cms.InputTag("HGCalRecHit", "HGCHEFRecHits", "RECO"),
        cms.InputTag("HGCalRecHit", "HGCHEBRecHits", "RECO"),
    ),
    pfRecHits = cms.VInputTag(
        cms.InputTag("particleFlowRecHitECAL", "Cleaned", "RECO"),
        cms.InputTag("particleFlowRecHitHBHE", "Cleaned", "RECO"),
        cms.InputTag("particleFlowRecHitHF",   "Cleaned", "RECO"),
        cms.InputTag("particleFlowRecHitHO",   "Cleaned", "RECO"),
    ),
)

process.truthLogicalGraphHitIndexProducer = cms.EDProducer(
    "TruthLogicalGraphHitIndexProducer",
    src = cms.InputTag("truthLogicalGraphProducer"),
    rawSrc = cms.InputTag("truthGraphProducer"),
    recHitMap = cms.InputTag("simHitToRecHitMapProducer"),
    simHitCollections = cms.VInputTag(
        cms.InputTag("g4SimHits", "HGCHitsEE", "SIM"),
        cms.InputTag("g4SimHits", "HGCHitsHEfront", "SIM"),
        cms.InputTag("g4SimHits", "HGCHitsHEback", "SIM"),
        cms.InputTag("g4SimHits", "EcalHitsEB", "SIM"),
        cms.InputTag("g4SimHits", "HcalHits", "SIM"),
    ),
    doHGCalRelabelling = cms.bool(False),
)
```

!!! note
    The global `recHitIndex` is fixed by the concatenation order in
    `SimHitToRecHitMapProducer` — all `HGCRecHitCollection` inputs first, then all
    `reco::PFRecHitCollection` inputs. Changing the order changes every stored
    index. Never feed both `HGCalRecHit` and `particleFlowRecHitHGC` into the same
    map (double counting).

## Consuming the products in an EDAnalyzer

The three products (`truth::Graph`, `truth::LogicalGraphHitIndex`, and the raw
`TruthGraph` if you need provenance back-references) are ordinary EDM products —
declare a token in the constructor, fetch with `event.get` in `analyze`. This is
the exact pattern the bundled validators (`BranchTrackingValidator`,
`BranchTrackerReplacementValidator`, `TruthBranchCaloAssociationProducer`) use:

```cpp
#include "FWCore/Framework/interface/global/EDAnalyzer.h"
#include "PhysicsTools/TruthInfo/interface/Graph.h"
#include "PhysicsTools/TruthInfo/interface/LogicalGraphHitIndex.h"

class MyTruthAnalyzer : public edm::global::EDAnalyzer<> {
public:
  explicit MyTruthAnalyzer(edm::ParameterSet const& cfg)
      : graphToken_(consumes<truth::Graph>(cfg.getParameter<edm::InputTag>("src"))),
        hitIndexToken_(consumes<truth::LogicalGraphHitIndex>(cfg.getParameter<edm::InputTag>("hitIndex"))) {}

  void analyze(edm::StreamID, edm::Event const& event, edm::EventSetup const&) const override {
    auto const& graph = event.get(graphToken_);          // truth::Graph
    auto const& hits  = event.get(hitIndexToken_);       // truth::LogicalGraphHitIndex

    for (truth::Particle p : graph.particleViews()) {
      if (!p.valid() || std::abs(p.pdgId()) != 15)       // taus only, say
        continue;
      truth::Branch tau(&graph, p.id());                 // see below
      // ... use tau.visibleP4(), hits.subgraphHits(p.id()), ...
    }
  }

private:
  const edm::EDGetTokenT<truth::Graph> graphToken_;
  const edm::EDGetTokenT<truth::LogicalGraphHitIndex> hitIndexToken_;
};
```

Config defaults: `src = cms.InputTag("truthLogicalGraphProducer")` and
`hitIndex = cms.InputTag("truthLogicalGraphHitIndexProducer")`. For the full method
list and exact signatures, see the [Interface reference](interface.md).

## Navigating the logical graph in C++

Get the product, then iterate. `truth::Graph` is a flat CSR; `particleViews()` and
`vertexViews()` hand you lightweight `(graph*, id)` handles, and individual handles
come from `particle(id)` / `vertex(id)`:

```cpp
#include "PhysicsTools/TruthInfo/interface/Graph.h"

auto const& graph = event.get(truthGraphToken_);  // EDGetTokenT<truth::Graph>

for (truth::Particle p : graph.particleViews()) {
  if (!p.valid())
    continue;
  const int32_t pdg = p.pdgId();
  const auto& p4 = p.momentum();         // math::XYZTLorentzVectorD
  const int16_t status = p.status();
  const bool isGenSim = p.hasGen() && p.hasSim();
}
```

The payload behind each handle is `ParticleData` (`pdgId`, `status`, `statusFlags`,
`eventId`, `genEvent`, `momentum`, provenance `genNode`/`simNode`, `checkpoints`)
and `VertexData` (`position`, `eventId`, `genEvent`, `role`). The graph is
**bipartite**: particles connect to vertices and vertices to particles, so
`parents()`/`children()` step through the production/decay vertices for you.

### Relatives, ancestry, and common ancestors

```cpp
truth::Particle p = graph.particle(id);

std::vector<truth::Particle> par  = p.parents();       // immediate
std::vector<truth::Particle> kids = p.children();
std::vector<truth::Particle> anc  = p.ancestors();     // transitive closure
std::vector<truth::Particle> desc = p.descendants();

// "does this particle descend from a b hadron?" — here, from a b quark:
if (p.hasAncestorPdgId(5)) { /* ... */ }

// the nearest ancestor of a given species (e.g. the originating Z):
if (auto z = p.firstAncestorWithPdgId(23); z.has_value())
  use(*z);
```

To find the closest common ancestor of two particles — "do these two reco objects
come from the same parent?":

```cpp
truth::Particle a = graph.particle(idA);
truth::Particle b = graph.particle(idB);

if (auto lca = a.firstCommonAncestor(b); lca.has_value()) {
  const int32_t pdg = lca->pdgId();   // e.g. 23 if both came from the same Z
}
```

For a whole set of particles (e.g. the truth constituents of a jet), use the
multi-source LCA on the graph — "which particle did this jet come from", typically
the b quark of a b-jet:

```cpp
std::vector<truth::Particle> jetConstituents = /* ... */;
if (auto origin = graph.lowestCommonAncestor(jetConstituents); origin.has_value()) {
  // walk further up to a specific origin species, e.g. the top:
  if (auto top = origin->firstAncestorWithPdgId(6); top.has_value())
    use(*top);
}
```

Graph-level extremities are available too: `graph.roots()`, `graph.leaves()`,
`graph.sourceVertices()`, `graph.sinkVertices()`, plus `nParticles()` /
`nVertices()` and `isConsistent()`.

## The Branch subgraph view and selecting particles

A `truth::Branch` is a non-owning view: one or more root particles plus a
**closure** of their descendants, recomputed on demand from the graph. The closure
kinds are `Subtree`, `StableLeaves`, `DepthN`, `UntilPdgId`, and `Predicate`:

```cpp
#include "PhysicsTools/TruthInfo/interface/Branch.h"

truth::Particle tau = /* a generated tau */;

truth::Branch full(&graph, tau.id());                                  // Subtree (default)
truth::Branch leaves(&graph, tau.id(), truth::ClosureSpec::stableLeaves());
truth::Branch shallow(&graph, tau.id(), truth::ClosureSpec::depth(2));
truth::Branch untilHadrons(&graph, tau.id(),
                           truth::ClosureSpec::untilPdgId({211, -211, 111}));

auto leafParticles = full.stableLeaves();
auto visP4         = full.visibleP4();        // sums stable leaves, excludes neutrinos
double eInvisible  = full.invisibleEnergy();  // p4().energy() - visibleP4().energy()
int32_t rootPdg    = full.rootPdgId();
bool fromB         = full.hasHeavyFlavor(5);  // any member is a b-flavored hadron

// provenance (pile-up aware):
bool signal  = full.isSignal();        // bunchCrossing()==0 && event()==0
bool fromPU  = full.isFromPileup();    // bunchCrossing()!=0
int  bx      = full.bunchCrossing();
```

Two branches can be related: `commonAncestor(other)` and `merged(other)`.

### Selecting roots at production time

The interesting physics subgraph is configured in the producer's `postProcessing`
PSet. `seedPdgIds` keeps the most-upstream copy of each matching chain as a root
plus its full downstream subgraph; `seedHadronFlavors` (`5`=b, `4`=c) seeds on
heavy-flavor hadrons; `seedParentDepth` keeps a few generations of ancestors as
context; `decayPdgIdGroups` filters roots by their decay products;
`collapseIntermediateGenParticles` removes redundant same-PDG GEN copies.

```python
postProcessing = cms.PSet(
    seedPdgIds = cms.vint32(23),                    # roots from Z bosons
    seedParentDepth = cms.uint32(1),
    seedHadronFlavors = cms.vint32(),
    collapseIntermediateGenParticles = cms.bool(True),
    decayPdgIdGroups = cms.VPSet(                    # keep Z -> mu mu, drop Z -> e e
        cms.PSet(pdgIds = cms.vint32(13, -13)),
    ),
    keepStableSpectators = cms.bool(True),
    ignoredPdgIds = cms.vint32(),
    ignoredParticleIds = cms.vuint32(),
)
```

The special value `seedPdgIds = [0]` disables selection and keeps the full graph
(a debugging escape hatch).

### Selecting branches at use time

`truth::BranchSelector` mirrors the cut surface of `TrackingParticleSelector` /
`CaloParticleSelector`, applied to a Branch (kinematics taken from its root):

```cpp
#include "PhysicsTools/TruthInfo/interface/BranchSelector.h"

truth::BranchSelector::Config cfg;
cfg.ptMin = 1.0;
cfg.etaMin = -3.0; cfg.etaMax = 3.0;
cfg.pdgIds = {13, -13};   // empty = accept all
cfg.signalOnly = true;    // bunchCrossing==0 && event==0
cfg.chargedOnly = true;

truth::BranchSelector select(cfg);
if (select(branch)) { /* passes */ }
```

## Hit content and matching reco objects

The hit index answers, per logical particle and per detector **channel**, two
questions: which SimHits the particle produced **directly**, and which its whole
**subgraph** produced (the full shower / decay-branch footprint). The channels are
keyed by `truth::HitChannel` (`HGCalCalo`, `Tracker`, `MTD`, `Muon`), each with its
own DetId space and metric. The accessors take the channel first, then the particle
id:

```cpp
#include "PhysicsTools/TruthInfo/interface/LogicalGraphHitIndex.h"

auto const& hitIndex = event.get(hitIndexToken_);  // truth::LogicalGraphHitIndex
using truth::HitChannel;

for (uint32_t pid = 0; pid < hitIndex.nParticles(); ++pid) {
  std::span<const truth::LogicalGraphHitIndex::Hit> direct =
      hitIndex.directHits(HitChannel::HGCalCalo, pid);
  std::span<const truth::LogicalGraphHitIndex::Hit> subgraph =
      hitIndex.subgraphHits(HitChannel::HGCalCalo, pid);
  std::span<const truth::LogicalGraphHitIndex::Hit> trk =
      hitIndex.subgraphHits(HitChannel::Tracker, pid);

  float e = 0.f;
  for (auto const& h : subgraph) {
    e += h.energy;                 // accumulated SimHit energy on this DetId
    if (h.hasRecHit())
      auto idx = h.recHitIndex;    // position in the global RecHit ordering
  }
}
```

Each `Hit` is `{detId, recHitIndex, energy}`; subgraph spans are contiguous and
DetId-sorted, so two particles' footprints merge by a linear merge-join. `recHitIndex`
is set where a recHit link exists: `HGCalCalo` (the HGCal recHit ordering) and `MTD`
(the FTLCluster ordering — note it is *channel-relative*, not the same ordering as
calo). `Tracker` and `Muon` carry no per-cell energy / no recHit link and leave it
invalid, so their matching is by shared-hit multiplicity. All four channels are
filled by `LogicalGraphHitIndexProducer`, but only for the subdetectors named in its
`subdetectors` config — gate on `hitIndex.hasChannel(...)` before using a channel.

### Matching an arbitrary reco object to a Branch

`truth::BranchHitAssociator` builds an inverted `detId → candidate roots` index over
the hit index once per event, then `bestBranches()` answers any reco object by a
merge-join of its hits against each candidate's subgraph span, scored and sorted
best-first (`score` ascending). Two metrics: `SharedEnergy` (the HGCal by-hits
score, comparing cell fractions) and `SharedHits` (cell multiplicity). A
`truth::HitChannel` constructor argument (default `HitChannel::HGCalCalo`) selects
which channel of the hit index it matches against — pass `HitChannel::Tracker` for
tracks.

A reco object is matchable if it exposes its hits as a range of
`truth::RecoHit{detId, energy, fraction}` — that is the `HasTruthHits` concept; any
object that provides a `truthHits()` method works with no other changes. For
objects that don't own their hits, the free-function adapters in
`RecoHitAdapters.h` build the hit range from the object plus the external
collections it references:

```cpp
#include "PhysicsTools/TruthInfo/interface/BranchHitAssociator.h"
#include "PhysicsTools/TruthInfo/interface/RecoHitAdapters.h"

// Calorimeter: a Trackster, matched by shared energy (cell fractions).
truth::BranchHitAssociator calo(hitIndex);  // default: SharedEnergy, calo channel
auto trackHits = truth::recoHits(trackster, layerClusters);  // adapter
std::vector<truth::BranchMatch> best = calo.bestBranches(std::span(trackHits), /*maxResults=*/3);
for (auto const& m : best) {
  uint32_t root = m.rootParticleId;
  float score   = m.score;          // lower is better
}

// Tracker: a reco::Track, matched by shared-hit multiplicity.
truth::BranchHitAssociator trk(hitIndex, /*candidateRoots=*/{},
                               truth::BranchHitAssociator::Metric::SharedHits,
                               truth::HitChannel::Tracker);
auto best2 = trk.bestBranches(truth::recoHits(track));
```

The adapters provided are `truth::recoHits(reco::Track const&)` (valid rechit
DetIds, unit weight) and
`truth::recoHits(ticl::Trackster const&, std::vector<reco::CaloCluster> const&)`
(layer-cluster cells with their fractions, coalesced). To make a new reco object
matchable, add one adapter that returns `std::vector<truth::RecoHit>` (or a
`truthHits()` member) and the same `BranchHitAssociator` matches it — replacing the
per-object bespoke associators.

These same adapters drive the generic reco-side DQM validators
(`BranchTrackRecoValidator` for tracks, `BranchTracksterRecoValidator` for
tracksters) and the `makeTruthGraphValidationPlots.py` overlay macro — see
[Validation → reco-side validators](validation.md#reco-side-validators-generic-hit-exposure).

## Performance plots

For DQM performance plots comparing the truth `Branch` graph against the legacy
truth objects (`CaloParticle`, `SimCluster`, `TrackingParticle`), and the topology
audits across the relval library, see the [Validation](validation.md) page.
