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
    keepProductionSiblings = cms.bool(False),
    signalOnly = cms.bool(False),                   # pile-up filter (see below)
    keepBunchCrossings = cms.vint32(),
    ignoredPdgIds = cms.vint32(),
    ignoredParticleIds = cms.vuint32(),
)
```

The special value `seedPdgIds = [0]` disables selection and keeps the full graph
(a debugging escape hatch).

!!! tip "Showing the seed's production co-products (e.g. VBF tagging jets)"
    `seedParentDepth` only walks **up** the ancestry. The partons that *recoil
    against* the seed at its production vertex are **siblings**, not ancestors, so
    no parent depth reaches them: seeding on the Higgs in VBF leaves the event with
    nothing upstream, even though the two forward quarks that fused to make it (and
    then become the tagging jets) share the Higgs's production vertex.
    `keepProductionSiblings = True` keeps that production vertex and its other
    outgoing particles (with their subtrees), so the recoiling quarks and their
    jets appear; because the real hard vertex is now kept, it is shown in place of
    the artificial Upstream summary. Standalone: `--keepProductionSiblings`.

    A worked VBF H→ZZ→4ν event (`-s 25 --keepProductionSiblings`) - the Higgs and
    the two tagging quarks share the hard vertex, the quarks fan out into the
    forward jets: browse it in the
    [online gallery](https://felice.web.cern.ch/truth/?path=/VBFHZZ4Nu).

#### Per-process presets

`enableTruth` attaches to **every** Run4 workflow (~140 generator fragments), and the
same presets are used to pick a focused view across the much larger production zoo
(validated against all ~740 `genproductions_cards` fragment names). The right selection
depends only on the physics, and they collapse to these archetypes:

| Preset | Fragments | Selection |
|---|---|---|
| `gun` | `Single*`/`Double*`/`Ten*`/`CloseBy*` | seed = the gun species (from the name) |
| `resonance` | `ZMM`/`ZEE`/`DYTo*` (incl. n-jet `DY1jTo*`/`dyellell*`), `Zp*`, `WTo*` and **W+jets** (`WJetsToLNu`/`W4JToLNu`) | seed the boson (+ ISR), channel decay group |
| `vbf` | `VBFH*` (incl. VBF HH), `QQToHToTauTau` | seed Higgs **+ keepProductionSiblings** |
| `ggf` | `H125GGgluonfusion`, **di-Higgs** `GluGluToHH*`/`HHto*` | seed Higgs (seeds every Higgs) |
| `vh` | **`WH*`/`ZH*`/`VH*`/`WWH*`/`ZZH*`** (associated Higgs) | seed Higgs **+ keepProductionSiblings** (recoiling boson) |
| `top` | `TTbar*`, **ttX** (`ttH`/`ttW`/`ttZ`/`ttbb`/four-top/`ttDM`), `Tprime*` | seed the top(s) **+ keepProductionSiblings** |
| `singletop` | `ST_t*`/`ST_tW`/`ST_s-channel` | seed top **+ keepProductionSiblings** (production partner) |
| `diboson` | **`WW*`/`WZ*`/`ZZ*`/`VBS*`/same-sign WW** | seed the bosons `{23,24,−24}` **+ keepProductionSiblings** |
| `heavyflavor` | `Bs*`/`Bu*`/`Jpsi*`/`Upsilon*` | seed by heavy-flavor content (b/c) |
| `full` | QCD / MinBias / NuGun / **SUSY / LLP / DM / EFT / BSM** / unknown | keep the whole graph |

The exotic/BSM zoo (SUSY, long-lived, dark-matter, EFT, generic BSM resonances) has no
clean single seed and intentionally lands on `full`. Adding the diboson/VH/ttX/HH/W+jets
routing dropped the `full`-fallback rate over the production fragment set from 77 % to 45 %.

`PhysicsTools/TruthInfo/python/truthGraphSelections.py` maps a fragment name (or short
label) to its preset and returns the `postProcessing` selection — overridable per call,
so a preset is a starting point, never a cage:

```python
from PhysicsTools.TruthInfo.truthGraphSelections import postProcessingPSet
producer.postProcessing = postProcessingPSet("VBFHZZ4Nu_14TeV")          # the VBF preset
producer.postProcessing = postProcessingPSet("ZMM_14", seedParentDepth=2)  # preset + override
```

The same module backs the standalone dumper (`python3 truthGraphSelections.py <fragment>`
prints the flags) and `makeTruthGallery.sh`, so adding a Run4 sample needs no config edit.

!!! note "Pile-up is an orthogonal axis, not a preset"
    The seven presets pick the **signal** of a *process*; pile-up is an *overlay*
    that composes with any of them (ZMM+PU, TTbar+PU, …), so it is **not** an eighth
    preset. It is handled on two separate layers:

    - **Build layer** (`TruthGraphAccumulator`): `pileupBunchCrossings` (default
      `{0}` = in-time only) chooses which PU bunch crossings enter the graph, and
      every node is stamped with its `EncodedEventId` — `(0,0)` signal vs
      `(bx, puIndex)` pile-up.
    - **Selection layer** (`postProcessing`): the composable filter
      `signalOnly = True` keeps only the signal interaction, and
      `keepBunchCrossings = [0]` keeps only the listed crossings — both drop
      particles *after* the seed selection, by their `EncodedEventId`, so they layer
      on top of any preset. Downstream, `Branch::isSignal()` / `isFromPileup()`
      expose the same provenance. Standalone: `--signal-only` / `--bunch-crossings 0`.

    (MinBias, having no hard scatter, is just the `full` preset — there is no signal
    to seed on.)

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

## Trackster-to-branch associations and the training dataset

`AllTracksterToTruthBranchAssociatorsProducer` (PhysicsTools/TruthInfo) associates
TICL trackster collections to truth branches: one pair of `ticl::AssociationMap`
products per configured collection (instance labels `<label>ToTruthBranch` and
`TruthBranchTo<label>`), each entry carrying the shared HGCAL rechit energy and the
normalized association score of `truth::BranchHitAssociator` (both directions). The
branch key is the root particle index in the `truth::Graph`.

The branch roots are the particles that physically entered the calorimeter: the
SimTrack tracker-calo boundary checkpoint (`Checkpoint::checkpointId == 0`),
excluding back-scattered re-entries. This is the CaloParticle boundary semantics
read off the graph and it forms an antichain by construction: beam particles never
cross, in-calo shower secondaries are born inside and never cross, and a particle
interacting or converting before the calorimeter promotes its crossing products.
An optional `branchPdgIds` restriction narrows the species; the default (empty)
keeps every crossing particle.

`TracksterTruthBranchTableProducer` (DPGAnalysis/HGCalNanoAOD) dumps the
associations to NanoAOD: a `TruthBranch` table (pdgId, kinematics, gen/sim
provenance, back-scatter flag, graph root index) over the union of matched roots,
and one pair table per collection (`tracksterIdx`, `branchIdx`, `sharedEnergy`,
`score`). Together with the trackster feature tables this is a per-trackster
training dataset with continuous truth labels; a trackster with no pair rows is
the principled "unknown". Purity and completeness are one join away
(sharedEnergy over the trackster raw energy and over the branch energy).

Production is a two-step chain, because the associator needs the sim hits while
the NanoAOD step does not:

```
cmsDriver.py step3 -s RAW2DIGI,RECO ... \
  --customise PhysicsTools/TruthInfo/customiseTruthBranchTraining.customise
cmsDriver.py step4 -s NANO:@HGCALTruth ...
```

The customisation runs the truth chain plus the associator during RECO and
persists the `truth::Graph` and the association maps; the `@HGCALTruth` autoNANO
flavour builds the tables from them.

### Hierarchical labels: clean, ambiguous, unknown

The label table (an extension of each trackster feature table) assigns every
trackster the LOWEST truth-graph node whose branch contains it with purity of at
least `labelPurityMin` (default 0.75):

- `labelClass 0` (clean): a single calo-entering particle dominates; `labelPdgId`
  is its species. The standard PID training label.
- `labelClass 1` (ambiguous): no single leaf is pure, but a DECAY-LEVEL common
  ancestor of the significant contributors is: the trackster merges different legs
  of the same decay (the photons of a pi0, the products of a D0 or a phi, the legs
  of a conversion). `labelPdgId` is the ancestor species; which leaf PID to assign
  is genuinely unclear.
- `labelClass 2` (unknown): the significant contributors share no physical ancestor
  below the parton or event level (or nothing matches above `minSharedEnergy`):
  the trackster mixes unrelated particles, i.e. it is fake.

The ancestor search takes the contributors above `contributorMinFraction` of the
matched energy and uses `truth::Graph::lowestCommonAncestor`; partonic ancestors
(quarks, gluons) mean "same jet", which is the unknown class, not ambiguous. The
companion columns `labelPurity`, `leafPurity` and `matchedFraction` carry the
continuous quantities the thresholds act on, so the cuts can be re-tuned offline.
