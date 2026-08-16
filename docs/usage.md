# How to use the graph

This page is a worked tour of the API. It shows how to put the products in a job. It
also shows how to navigate the logical graph and how to select interesting particles.
It shows how to match an arbitrary reco object to a truth branch. Every method, field, and
config label below exists in `PhysicsTools/TruthInfo`. See the
[Data model](data-model.md) for the design. See [Validation](validation.md) for
performance plots.

## The three layers and their producers

The package is layered. Each level stays compact. The level above adds navigation,
then physics, then detector hits.

| Layer | Type | Producer | What it is |
|---|---|---|---|
| 1 | `TruthGraph` (raw) | `truthGraphProducer` | typed-node CSR over GEN + SIM (`GenEvent`/`GenVertex`/`GenParticle`/`SimVertex`/`SimTrack` + `GenToSim` edges) |
| 2 | `truth::Graph` (logical) | `truthLogicalGraphProducer` | bipartite `Particle ↔ Vertex` CSR with the physics navigation API |
| 3 | `truth::LogicalGraphHitIndex` | `truthLogicalGraphHitIndexProducer` | per-particle calo/tracker hit spans (direct + aggregated subgraph) |

Three non-EDM helpers sit on top of the logical graph. You use them directly in your
code; they are not products. They are `truth::Branch` (a recomputed-on-demand subgraph
view), `truth::BranchSelector` (physics selection), and `truth::BranchHitAssociator`
(generic hit-based reco↔truth matching).

## Enabling the truth graph in a job

The producer chain order matters. Each producer consumes the previous one:

```
truthGraphProducer → truthLogicalGraphProducer → detIdToRecHitMapProducer → truthLogicalGraphHitIndexProducer
```

In a standard workflow the `enableTruth` process modifier
(`Configuration/ProcessModifiers/enableTruth_cff`) gates this chain. The Run4 eras
apply that modifier from `Phase2C17I13M9` onwards. It attaches
`truthGraphValidationProducers` to `baseCommonPreValidation`. It attaches
`truthGraphValidationAnalyzers` to `baseCommonValidation`
(`Validation/Configuration/python/globalValidation_cff.py`). Those are the sequences
that the Phase-2 `autoValidation` assembly schedules. The baseline `g4SimHits`
configuration sets `g4SimHits.TrackingAction.ReconnectDroppedAncestors = True` in the
SIM step. Every stored `SimTrack`'s production vertex then resolves to a stored
ancestor, so there are no orphans. `PersistencyEmin` stays at 50 GeV. See
[Findings](findings.md#1-orphan-simvertices-generator-history-retention):

```bash
# Run4 D120 relval with the truth producers enabled in RECO:
runTheMatrix.py -l 34087.88 --what upgrade
```

To run the chain standalone on an existing `step3.root`, use the bundled driver. It
dumps DOT graphs per event. It exposes selection options (`-n/--maxevts`,
`-m/--merge`, `-c/--collapse`, `-s/--seeds`, `-f/--flavors`, `-o/--outdir`):

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
process.detIdToRecHitMapProducer = cms.EDProducer(
    "DetIdToRecHitMapProducer",
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
    recHitMap = cms.InputTag("detIdToRecHitMapProducer"),
    simHitCollections = cms.VInputTag(
        cms.InputTag("g4SimHits", "HGCHitsEE", "SIM"),
        cms.InputTag("g4SimHits", "HGCHitsHEfront", "SIM"),
        cms.InputTag("g4SimHits", "HGCHitsHEback", "SIM"),
        cms.InputTag("g4SimHits", "EcalHitsEB", "SIM"),
        cms.InputTag("g4SimHits", "HcalHits", "SIM"),
    ),
    doHGCalRelabelling = cms.bool(False),
    doHcalRelabelling = cms.bool(True),
)
```

!!! note "Sim-to-reco DetId conversion"
    The two switches are independent, one per numbering scheme.
    `doHGCalRelabelling` unpacks the old hexagon-indexed HGCAL simulation DetIds. It
    is a no-op for the Run4 geometries, whose HGCAL simulation DetId is already the
    reco DetId. The example above can therefore leave it off. `doHcalRelabelling`
    runs `HcalHitRelabeller` on the HCAL simulation DetIds, which are in packed test
    numbering. Without it, the HCAL entries of the index carry sim ids that match no
    `HBHERecHit`. ECAL barrel needs no conversion.

!!! note
    The concatenation order in `DetIdToRecHitMapProducer` fixes the global
    `recHitIndex`: all `HGCRecHitCollection` inputs first, then all
    `reco::PFRecHitCollection` inputs. Changing the order changes every stored
    index. Never feed both `HGCalRecHit` and `particleFlowRecHitHGC` into the same
    map, because that double counts.

## Consuming the products in an EDAnalyzer

The three products are ordinary EDM products: `truth::Graph`,
`truth::LogicalGraphHitIndex`, and the raw `TruthGraph` if you need provenance
back-references. Declare a token in the constructor. Fetch the product with
`event.get` in `analyze`. The bundled validators (`BranchTrackingValidator`,
`BranchTrackerReplacementValidator`, `TruthBranchCaloAssociationProducer`) use
exactly this pattern:

```cpp
#include "FWCore/Framework/interface/global/EDAnalyzer.h"
#include "SimDataFormats/TruthInfo/interface/Graph.h"
#include "SimDataFormats/TruthInfo/interface/LogicalGraphHitIndex.h"

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
      // ... use tau.visibleP4(), hits.subgraphHits(truth::HitChannel::Calo, p.id()), ...
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

Get the product, then iterate. `truth::Graph` is a flat CSR. `particleViews()` and
`vertexViews()` give you lightweight `(graph*, id)` handles. `particle(id)` /
`vertex(id)` give you individual handles:

```cpp
#include "SimDataFormats/TruthInfo/interface/Graph.h"

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
**bipartite**: particles connect to vertices and vertices to particles.
`parents()`/`children()` therefore step through the production and decay vertices
for you.

### Relatives, ancestry, and common ancestors

```cpp
truth::Particle p = graph.particle(id);

std::vector<truth::Particle> par  = p.parents();       // immediate
std::vector<truth::Particle> kids = p.children();
std::vector<truth::Particle> anc  = p.ancestors();     // transitive closure
std::vector<truth::Particle> desc = p.descendants();

// "does this particle descend from a b hadron?" here, from a b quark:
if (p.hasAncestorPdgId(5)) { /* ... */ }

// the nearest ancestor of a given species (e.g. the originating Z):
if (auto z = p.firstAncestorWithPdgId(23); z.has_value())
  use(*z);
```

Use this call to find the closest common ancestor of two particles, that is, to ask
whether two reco objects come from the same parent:

```cpp
truth::Particle a = graph.particle(idA);
truth::Particle b = graph.particle(idB);

if (auto lca = a.firstCommonAncestor(b); lca.has_value()) {
  const int32_t pdg = lca->pdgId();   // e.g. 23 if both came from the same Z
}
```

For a whole set of particles, for example the truth constituents of a jet, use the
multi-source LCA on the graph. It answers which particle the jet came from, typically
the b quark of a b-jet:

```cpp
std::vector<truth::Particle> jetConstituents = /* ... */;
if (auto origin = graph.lowestCommonAncestor(jetConstituents); origin.has_value()) {
  // walk further up to a specific origin species, e.g. the top:
  if (auto top = origin->firstAncestorWithPdgId(6); top.has_value())
    use(*top);
}
```

The graph also offers graph-level extremities: `graph.roots()`, `graph.leaves()`,
`graph.sourceVertices()`, `graph.sinkVertices()`, plus `nParticles()` /
`nVertices()` and `isConsistent()`.

## The Branch subgraph view and selecting particles

A `truth::Branch` is a non-owning view. It holds one or more root particles plus a
**closure** of their descendants. It recomputes that closure on demand from the graph.
The closure kinds are `Subtree`, `StableLeaves`, `DepthN`, `UntilPdgId`, and
`Predicate`:

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

The producer's `postProcessing` PSet configures the interesting physics subgraph.
`seedPdgIds` keeps the most-upstream copy of each matching chain as a root, plus its
full downstream subgraph. `seedHadronFlavors` (`5`=b, `4`=c) seeds on heavy-flavor
hadrons. `seedParentDepth` keeps a few generations of ancestors as context.
`decayPdgIdGroups` filters roots by their decay products.
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

The special value `seedPdgIds = [0]` disables selection and keeps the full graph. It
is a debugging escape hatch.

!!! tip "Showing the seed's production co-products (e.g. VBF tagging jets)"
    `seedParentDepth` only walks **up** the ancestry. The partons that *recoil
    against* the seed at its production vertex are **siblings**, not ancestors. No
    parent depth reaches them. Seeding on the Higgs in VBF therefore leaves the
    event with nothing upstream. The two forward quarks that fused to make the
    Higgs share its production vertex, and they become the tagging jets.
    `keepProductionSiblings = True` keeps that production vertex and its other
    outgoing particles, with their subtrees. The recoiling quarks and their jets
    then appear. The real hard vertex is now kept, so the dumper shows it in place
    of the artificial Upstream summary. Standalone: `--keepProductionSiblings`.

    A worked VBF H→ZZ→4ν event uses `-s 25 --keepProductionSiblings`. The Higgs and
    the two tagging quarks share the hard vertex, and the quarks spread out into
    the forward jets. Browse the event in the
    [online gallery](https://felice.web.cern.ch/truth/?path=/VBFHZZ4Nu).

#### Per-process presets

`enableTruth` attaches to **every** Run4 workflow (~140 generator fragments). The same
presets pick a focused view across the much larger production set. They were validated
against all ~740 `genproductions_cards` fragment names. The right selection depends
only on the physics. The selections collapse to these archetypes:

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

The exotic/BSM set (SUSY, long-lived, dark-matter, EFT, generic BSM resonances) has no
clean single seed. It intentionally falls to `full`. Adding the diboson/VH/ttX/HH/W+jets
routing dropped the `full`-fallback rate over the production fragment set from 77 % to 45 %.

`PhysicsTools/TruthInfo/python/truthGraphSelections.py` maps a fragment name (or short
label) to its preset. It returns the `postProcessing` selection. You can override that
selection per call, so a preset is a starting point and not a fixed rule:

```python
from PhysicsTools.TruthInfo.truthGraphSelections import postProcessingPSet
producer.postProcessing = postProcessingPSet("VBFHZZ4Nu_14TeV")          # the VBF preset
producer.postProcessing = postProcessingPSet("ZMM_14", seedParentDepth=2)  # preset + override
```

The same module backs the standalone dumper and `makeTruthGallery.sh`. `python3
truthGraphSelections.py <fragment>` prints the flags. Adding a Run4 sample therefore
needs no config edit.

!!! note "Pile-up is an orthogonal axis, not a preset"
    The presets pick the **signal** of a *process*. Pile-up is an *overlay* that
    composes with any of them (ZMM+PU, TTbar+PU, …). It is therefore **not** an
    eleventh preset. Two separate layers handle it:

    - **Build layer** (`TruthGraphAccumulator`): `pileupBunchCrossings` (default
      `{0}` = in-time only) chooses which PU bunch crossings enter the graph. Every
      node carries its `EncodedEventId`: `(0,0)` for signal, `(bx, puIndex)` for
      pile-up.
    - **Selection layer** (`postProcessing`): the composable filter
      `signalOnly = True` keeps only the signal interaction.
      `keepBunchCrossings = [0]` keeps only the listed crossings. Both drop
      particles *after* the seed selection, by their `EncodedEventId`, so they layer
      on top of any preset. Downstream, `Branch::isSignal()` / `isFromPileup()`
      expose the same provenance. Standalone: `--signal-only` / `--bunch-crossings 0`.

    (MinBias has no hard scatter, so it is just the `full` preset. There is no signal
    to seed on.)

### Selecting branches at use time

`truth::BranchSelector` mirrors the cut surface of `TrackingParticleSelector` /
`CaloParticleSelector`. It applies that cut surface to a Branch. It takes the
kinematics from the Branch root:

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

The hit index answers two questions per logical particle and per detector **channel**.
It gives the SimHits that the particle produced **directly**. It also gives the SimHits
that its whole **subgraph** produced, that is, the full shower or decay-branch
footprint. `truth::HitChannel` keys the channels (`Calo`, `Tracker`, `MTD`, `Muon`).
Each channel has its own DetId space and metric. The accessors take the channel first,
then the particle id:

```cpp
#include "SimDataFormats/TruthInfo/interface/LogicalGraphHitIndex.h"

auto const& hitIndex = event.get(hitIndexToken_);  // truth::LogicalGraphHitIndex
using truth::HitChannel;

for (uint32_t pid = 0; pid < hitIndex.nParticles(); ++pid) {
  std::span<const truth::LogicalGraphHitIndex::Hit> direct =
      hitIndex.directHits(HitChannel::Calo, pid);
  std::span<const truth::LogicalGraphHitIndex::Hit> subgraph =
      hitIndex.subgraphHits(HitChannel::Calo, pid);
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

Each `Hit` is `{detId, recHitIndex, energy}`. Subgraph spans are contiguous and
DetId-sorted, so two particles' footprints merge by a linear merge-join. `recHitIndex`
is set where a recHit link exists: `Calo` (the HGCal recHit ordering) and `MTD` (the
FTLCluster ordering). The MTD ordering is *channel-relative*, not the same ordering as
calo. `Tracker` and `Muon` carry `energyLoss` as the hit energy but have no recHit
link. They therefore leave `recHitIndex` invalid, and their matching goes by shared-hit
multiplicity. `LogicalGraphHitIndexProducer` fills all four channels, but only for the
subdetectors named in its `subdetectors` config. Gate on `hitIndex.hasChannel(...)`
before using a channel.

### Matching an arbitrary reco object to a Branch

`truth::BranchHitAssociator` builds an inverted `detId → candidate roots` index over
the hit index once per event. `bestBranches()` then answers any reco object. It
merge-joins the object's hits against each candidate's subgraph span. It scores the
candidates and sorts them best-first (`score` ascending). Two metrics exist:
`SharedEnergy` (the HGCal by-hits score, comparing cell fractions) and `SharedHits`
(cell multiplicity). A `truth::HitChannel` constructor argument (default
`HitChannel::Calo`) selects which channel of the hit index the associator matches
against. Pass `HitChannel::Tracker` for tracks.

A reco object is matchable if it exposes its hits as a range of
`truth::RecoHit{detId, energy, fraction}`. That is the `HasTruthHits` concept. Any
object that provides a `truthHits()` method works with no other changes. Some objects
do not own their hits. For those, the free-function adapters in `RecoHitAdapters.h`
build the hit range from the object plus the external collections it references:

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

The package provides two adapters: `truth::recoHits(reco::Track const&)` (valid rechit
DetIds, unit weight) and
`truth::recoHits(ticl::Trackster const&, std::vector<reco::CaloCluster> const&)`
(layer-cluster cells with their fractions, coalesced). To make a new reco object
matchable, add one adapter that returns `std::vector<truth::RecoHit>`, or a
`truthHits()` member. The same `BranchHitAssociator` then matches it, and it replaces
the per-object bespoke associators.

These same adapters drive the generic reco-side DQM validators
(`BranchTrackRecoValidator` for tracks, `BranchTracksterRecoValidator` for
tracksters). They also drive the `makeTruthGraphValidationPlots.py` overlay macro. See
[Validation → reco-side validators](validation.md#reco-side-validators-generic-hit-exposure).

## Performance plots

The [Validation](validation.md) page holds the DQM performance plots. They compare the
truth `Branch` graph against the legacy truth objects (`CaloParticle`, `SimCluster`,
`TrackingParticle`). That page also holds the topology audits across the relval
library.

## Trackster-to-branch associations and the training dataset

!!! warning "Partly on the development branch"
    `AllTracksterToTruthBranchAssociatorsProducer` is in the release. The NanoAOD
    table producers and the training customise described from here on live on the
    `ticl-v6-dev` development branch. They are **not** in `CMSSW_20_1_X`. They are
    `TracksterTruthBranchTableProducer`, `TracksterFeatureFlatTableProducer`,
    `BranchSimTracksterProducer`, `customiseTruthBranchTraining`, the `@HGCALTruth`
    autoNANO block and the `labelClass` / `label_adaptive` columns. Merge that
    branch before following these recipes.


`AllTracksterToTruthBranchAssociatorsProducer` (PhysicsTools/TruthInfo) associates
TICL trackster collections to truth branches. It emits two pairs of
`ticl::AssociationMap` products per configured collection. The fixed-level pair is
`<label>ToTruthBranch` / `TruthBranchTo<label>`. The adaptive-level pair is
`<label>ToTruthBranchAdaptive` / `TruthBranchTo<label>Adaptive`. Each entry carries the
shared HGCAL rechit energy and the normalized association score of
`truth::BranchHitAssociator`, in both directions. The branch key is the root particle
index in the `truth::Graph`.

The branch roots are the particles that physically entered the calorimeter. They come
from the SimTrack tracker-calo boundary checkpoint (`Checkpoint::checkpointId == 0`),
excluding back-scattered re-entries. This is the CaloParticle boundary semantics read
off the truth graph. It forms an antichain by construction. Beam particles never cross
the boundary. In-calo shower secondaries are born inside and never cross it. A particle
that interacts or converts before the calorimeter promotes its crossing products. An
optional `branchPdgIds` restriction narrows the species. The default (empty) keeps
every crossing particle.

`TracksterTruthBranchTableProducer` (DPGAnalysis/HGCalNanoAOD) dumps the associations
to NanoAOD. It writes a `TruthBranch` table (pdgId, kinematics, gen/sim provenance,
back-scatter flag, graph root index) over the union of matched roots. It writes one
pair table per collection (`tracksterIdx`, `branchIdx`, `sharedEnergy`, `score`).
Together with the trackster feature tables this is a per-trackster training dataset
with continuous truth labels. A trackster with no pair rows is the principled
"unknown". Purity and completeness take one join: sharedEnergy over the trackster raw
energy, and sharedEnergy over the branch energy.

Production is a two-step chain, because the associator needs the sim hits while
the NanoAOD step does not:

```
cmsDriver.py step3 -s RAW2DIGI,RECO ... \
  --customise PhysicsTools/TruthInfo/customiseTruthBranchTraining.customise
cmsDriver.py step4 -s NANO:@HGCALTruth ...
```

The customisation runs the truth chain plus the associator during RECO. It persists
the `truth::Graph` and the association maps. The `@HGCALTruth` autoNANO flavour builds
the tables from them.

### Hierarchical labels: clean, ambiguous, unknown

The `TruthBranch` label table (`TracksterTruthBranchTableProducer`,
DPGAnalysis/HGCalNanoAOD) assigns every trackster the LOWEST truth-graph node whose
branch contains it with purity of at least `labelPurityMin` (default 0.75):

- `labelClass 0` (clean): a single calo-entering particle dominates. `labelPdgId`
  is its species. This is the standard PID training label.
- `labelClass 1` (ambiguous): no single leaf is pure, but a DECAY-LEVEL common
  ancestor of the significant contributors is pure. The trackster merges different
  legs of the same decay. Examples are the photons of a pi0, the products of a D0 or
  a phi, and the legs of a conversion. `labelPdgId` is the ancestor species. Which
  leaf PID to assign is genuinely unclear.
- `labelClass 2` (unknown): the significant contributors share no physical ancestor
  below the parton or event level, or nothing matches above `minSharedEnergy`. The
  trackster mixes unrelated particles, that is, it is fake.

The ancestor search takes the contributors above `contributorMinFraction` of the
matched energy. It uses `truth::Graph::lowestCommonAncestor`. Partonic ancestors
(quarks, gluons) mean "same jet", which is the unknown class and not the ambiguous
one. The companion columns `labelPurity`, `leafPurity` and `matchedFraction` carry the
continuous quantities the thresholds act on, so you can re-tune the cuts offline.

### Feature-table PID label: label and label_adaptive

The trackster FEATURE table (`TracksterFeatureFlatTableProducer`,
PhysicsTools/TruthInfo) is the one production dumps for training. It carries its OWN
calo-class label. That label is distinct from the `labelClass` above and comes from a
different search. `label` (leaf) is the single-particle class of the best
calo-crossing branch by shared energy, that is, the highest-`sharedEnergy` leaf above
`minSharedEnergy`. The values are `0` em (electron/photon), `1` mip (muon), `2`
hadronic (any meson or baryon), and `5` fake. `best_pdg` and `best_sharedE` carry the
matched species and its shared energy.

`label_adaptive` is the class of the branch the adaptive search picks. That branch is
the graph level whose subgraph hits best match the reco trackster. Climbing one
ancestor further only adds its far-away sim hits, which lowers the shared fraction, so
the search stops at the matching level. A single calo-crossing particle takes its own
class (em/mip/hadronic). Two other cases take the class of their calo-crossing
DESCENDANT leaves, the real shower-makers. Those cases are a merge node, and a
particle that crosses the boundary but decays before it can shower (a tau). Any
hadronic leaf makes it `4` merged_hadron. Otherwise an electron or photon makes it
`3` merged_em. Otherwise a muon makes it `1` mip. This lets a hadronic tau read as a
merged hadronic system. Without it the tau would fall to fake on pdgId 15, which is
not itself a calo object.
`adaptive_pdg`, `adaptive_sharedE` and `adaptive_score` carry the picked level and its
continuous match quantities.

Two more columns separate signal from pileup. `is_primary` is `1` when the matched
particle is from the hard scatter (bunch crossing 0, event 0), and `0` for pileup.
`signal_energy_fraction` is the fraction of the trackster's total shared energy that
comes from signal (`isPrimary`) particles, summed over all leaf branches. A value of
`0` is a pure-pileup trackster. Training keeps only the tracksters above that value.

### Multi-level branch SimTracksters

`BranchSimTracksterProducer` materializes branches as `ticl::Trackster` collections
(SIM iteration) at every level of the truth graph. Level 0 is the calo-entering
antichain: one trackster per boundary-crossing particle, covering its whole shower.
Each higher level is a decay or interaction ancestor that merges at least two selected
nodes. Examples are a pi0 over its photons, and a rho, omega, eta, K0, D or tau over
its products. The producer excludes the parton shower. It keeps a partonic merge node only when that
node carries the `kIsHardProcess` status flag.

Each trackster's vertices are the layer clusters touched by the node's subgraph hits.
The vertex multiplicities encode the shared fractions. The node's truth momentum is
the regressed energy. The node species sets a one-hot PID. The whole SimTrackster
toolchain therefore works against any level.

Parallel products carry `level`, `rootId` and `pdgId`. They also carry a `roots` list.
`AllTracksterToTruthBranchAssociatorsProducer` consumes that list (`rootsSrc`) and
produces reco associations against every level at once. The `@HGCALTruth` NanoAOD
flavour dumps them as the `TruthBranchAllLevels` and `*ToTruthBranchAllLevels` tables.
Together with the leaf-level labels this lets you score an ambiguous trackster against
the level where it IS pure (the pi0 instead of either photon).

> Note: since the MCTruthHelper fill, ParticleData.statusFlags carries real reco::GenStatusFlags for HepMC2-built graphs (isHardProcess etc.). HepMC3-built graphs still carry 0, pending an MCTruthHelper HepMC3 specialization.
