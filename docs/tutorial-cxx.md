# Tutorial: write an analyser in C++

This tutorial builds a working CMSSW module that reads the truth graph, in three files. It
follows the layout the [worked analyses](worked-analyses.md) use, where the analysis is a
free function and the framework module is a thin shell around it. That separation is what
lets the same code run on one committed event in a unit test and on a full sample in a job.

Start from the sample and the release of [Quickstart](quickstart.md).

## Step 1: the analysis, as a free function

Make a package, `MyTruthStudy/Taus`, and write the analysis so that it takes a graph and a
stream. Nothing here knows about the framework.

```cpp
// MyTruthStudy/Taus/plugins/TauEnergy.h
#include <ostream>
#include "SimDataFormats/TruthInfo/interface/Graph.h"

namespace mystudy {
  void run(truth::Graph const& graph, std::ostream& out);
}
```

```cpp
// MyTruthStudy/Taus/plugins/TauEnergy.cc
#include "MyTruthStudy/Taus/plugins/TauEnergy.h"

#include "PhysicsTools/TruthInfo/interface/TruthLevels.h"

namespace mystudy {

  void run(truth::Graph const& graph, std::ostream& out) {
    // Both tau levels at once: each member is the last copy of a physical tau.
    const auto taus = truth::particlesAtLevels(
        graph, {truth::Level::TauVisibleHadronic, truth::Level::TauVisibleLeptonic});

    for (truth::Particle const& tau : taus) {
      // The decay products sit on the LAST copy of a radiating chain. On the first copy
      // the only child is the next copy of the same tau.
      double visible = 0.;
      for (truth::Particle const& product : tau.lastCopy().children()) {
        if (!truth::isInvisible(product.pdgId())) {
          visible += product.momentum().energy();
        }
      }

      out << "tau " << tau.pdgId() << " E " << tau.momentum().energy()
          << " GeV, visible fraction " << visible / tau.momentum().energy() << "\n";
    }
  }

}  // namespace mystudy
```

Three interface calls carry the work. `truth::particlesAtLevels` answers "which particles
is this measurement about". `Particle::lastCopy()` moves to the copy that carries the
decay. `truth::isInvisible` keeps the neutrinos out of a visible energy.

This is the generator-level visible energy: the tau decay products, without the neutrinos.
Resist the temptation to sum the leaves of the whole branch instead. The branch continues
into the Geant4 shower, where energy is absorbed in the detector, and the sum of the leaf
energies of one tau in this sample came out at 27 MeV of 46 GeV. The
[Tau worked analysis](worked-analyses.md) carries the full treatment, including the decay
mode in prongs and neutral pions.

## Step 2: the framework module

The module consumes the graph and calls the function. It is an `edm::global::EDAnalyzer`,
which is the right base class because it keeps no state between events.

```cpp
// MyTruthStudy/Taus/plugins/TauEnergyPlugin.cc
#include <sstream>

#include "FWCore/Framework/interface/Event.h"
#include "FWCore/Framework/interface/MakerMacros.h"
#include "FWCore/Framework/interface/global/EDAnalyzer.h"
#include "FWCore/MessageLogger/interface/MessageLogger.h"
#include "FWCore/ParameterSet/interface/ConfigurationDescriptions.h"
#include "FWCore/ParameterSet/interface/ParameterSetDescription.h"

#include "MyTruthStudy/Taus/plugins/TauEnergy.h"
#include "SimDataFormats/TruthInfo/interface/Graph.h"

class TauEnergyAnalyzer : public edm::global::EDAnalyzer<> {
public:
  explicit TauEnergyAnalyzer(edm::ParameterSet const& pset)
      : token_(consumes<truth::Graph>(pset.getParameter<edm::InputTag>("src"))) {}

  static void fillDescriptions(edm::ConfigurationDescriptions& descriptions) {
    edm::ParameterSetDescription desc;
    desc.add<edm::InputTag>("src", edm::InputTag("truthLogicalGraphProducer"));
    descriptions.addWithDefaultLabel(desc);
  }

  void analyze(edm::StreamID, edm::Event const& event, edm::EventSetup const&) const override {
    std::ostringstream out;
    out << "== event " << event.id().event() << "\n";
    mystudy::run(event.get(token_), out);
    edm::LogPrint("TauEnergy") << out.str();
  }

private:
  const edm::EDGetTokenT<truth::Graph> token_;
};

DEFINE_FWK_MODULE(TauEnergyAnalyzer);
```

Two details matter. The graph is consumed by token in the constructor, as any event
product. And `analyze` is `const`, which is what makes the module safe to run on several
events at once; keep any per-event scratch space local to the method.

## Step 3: build it

```xml
<!-- MyTruthStudy/Taus/plugins/BuildFile.xml -->
<use name="FWCore/Framework"/>
<use name="FWCore/MessageLogger"/>
<use name="FWCore/ParameterSet"/>
<use name="PhysicsTools/TruthInfo"/>
<use name="SimDataFormats/TruthInfo"/>

<library file="TauEnergy.cc,TauEnergyPlugin.cc" name="MyTruthStudyTausPlugins">
  <flags EDM_PLUGIN="1"/>
</library>
```

```bash
scram b -j 8
```

## Step 4: run it

```python
# run.py
import FWCore.ParameterSet.Config as cms

process = cms.Process("TAUENERGY")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))
process.source = cms.Source("PoolSource", fileNames=cms.untracked.vstring("file:step3.root"))
process.taus = cms.EDAnalyzer("TauEnergyAnalyzer", src=cms.InputTag("truthLogicalGraphProducer"))
process.p = cms.Path(process.taus)
```

```bash
cmsRun run.py
```

Run it on a tau sample, such as workflow 37645.0, which is Z to two taus. On five events
of that sample it prints:

```
== event 7
tau -15 E 524.517 GeV, visible fraction 0.523342
tau 15 E 46.0586 GeV, visible fraction 0.520351
== event 4
tau 15 E 47.0416 GeV, visible fraction 0.510566
tau -15 E 332.364 GeV, visible fraction 0.372354
```

Visible fractions near a half are what a tau decay gives: the neutrino takes the rest. A
top quark pair sample has a tau in only a few percent of its events, so use a tau sample
or run over many more events.

## Adding detector hits

Everything above uses the history alone. To ask which reconstructed object corresponds to
a truth object you need the hit index, which holds the detector hits of every particle and
of everything it produced.

```cpp
#include "PhysicsTools/TruthInfo/interface/BranchHitAssociator.h"
#include "PhysicsTools/TruthInfo/interface/TruthLevels.h"
#include "SimDataFormats/TruthInfo/interface/LogicalGraphHitIndex.h"

// In the constructor, alongside the graph token:
hitIndexToken_ = consumes<truth::LogicalGraphHitIndex>(
    pset.getParameter<edm::InputTag>("hitIndex"));

// In analyze: the candidate truth objects, then one inverted index per event.
std::vector<uint32_t> candidateRootIds;
for (truth::Particle const& p : truth::particlesAtLevel(graph, truth::Level::CaloBoundary)) {
  candidateRootIds.push_back(p.id());
}
const truth::BranchHitAssociator associator(event.get(hitIndexToken_),
                                            candidateRootIds,
                                            truth::BranchHitAssociator::Metric::SharedEnergy,
                                            truth::HitChannel::Calo);

// Then ask it per reco object, with that object's cells as truth::RecoHit entries.
const auto matches = associator.bestBranches(std::span<const truth::RecoHit>(recoHits));
```

`bestBranches` returns the candidates sorted best first. The metric argument chooses the
arithmetic, shared energy for calorimetry or shared hits for the tracker, and the channel
argument chooses which part of the detector the match is made in. A reco object that
exposes its own cells through a `truthHits()` member can be passed directly instead of a
span. [Hit content and matching reco objects](usage.md#hit-content-and-matching-reco-objects)
documents the hit layouts, the two metrics and the traps, of which the important one is
that a subgraph hit list repeats a DetId once per contributing descendant, so per-cell
arithmetic has to coalesce first.

If what you want is the standard efficiency and fake rate rather than your own matching,
do not write it: the association layer already produces those maps for tracks, tracksters,
vertices and particle-flow clusters, and the DQM package turns them into plots. See
[Association layer](association-layer.md) and
[Tutorial: the adaptive associator](adaptive-associator.md).

## Where to go next

- [Worked analyses](worked-analyses.md) for eleven complete modules to copy from.
- [Interface reference](interface.md) for the precise signatures.
- [How to use the graph](usage.md) for the full API tour, including the hit index.
