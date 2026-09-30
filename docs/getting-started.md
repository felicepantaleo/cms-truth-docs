# Getting started: recipes and FAQ

This page is a set of short recipes. Each recipe answers one question and runs on the
TruthGraphTutorial samples. The outputs shown are from those samples.
For the concepts behind the recipes, read [Quickstart](quickstart.md) and
[Choose a truth definition](tutorial-truth-definitions.md).

## The tutorial samples

Seven samples ran the full chain, from generation to harvesting, with cms-sw/cmssw#51829
at `6d57fc7871a` on `CMSSW_20_1_X_2026-09-28-1100`. All of them use geometry
ExtendedRun4D122, era Phase2C26I13M9 and conditions `auto:phase2_realistic_T35`.

| Sample | Process | Pileup | Events |
|---|---|---|---|
| `tentau` | Ten taus per event from the vertex, E 15 to 500 GeV, abs(eta) < 3.1 | none | 1000 |
| `zmumu` | Z to mumu, 14 TeV | none | 1063 |
| `zee` | Z to ee, 14 TeV | none | 1000 |
| `drellyan` | Drell-Yan to ee, mumu and tautau, M(ll) > 50 GeV, 14 TeV | none | 1000 |
| `ttbar` | ttbar, 14 TeV | none | 1000 |
| `vbf` | VBF H to ZZ to 4 neutrinos, 14 TeV | none | 1000 |
| `ttbar_pu200` | ttbar, 14 TeV | 200 | 100 |

Browse them at
[orbit/TruthGraphTutorial](https://felice.web.cern.ch/orbit/?path=%2FTruthGraphTutorial).
Each sample folder holds:

- `step3.root`: GEN-SIM-RECO with the truth graph, the hit index and the truth association maps.
- `step3_inMINIAODSIM.root`, the DQMIO file `step3_inDQM.root` and the harvested DQM file.
- `configs/`: the four cmsRun configurations and the script that ran them.
- `graphs/`: two events drawn as DOT and PDF, and the logical graph as JSON.
- `validation/`: the truth validation gallery.

Every file is readable over HTTPS. FWLite and `cmsRun` open the URL directly, so you do
not need to copy a file to start:

```
https://felice.web.cern.ch/orbit/TruthGraphTutorial/<sample>/step3.root
```

A remote file reads more slowly than a local one. For a full sample, copy it first with
`wget`.

## Set up an area

```bash
cmsrel CMSSW_20_1_X_2026-09-28-1100      # scram list CMSSW_20_1_X shows what is on cvmfs today
cd CMSSW_20_1_X_2026-09-28-1100/src
cmsenv
git cms-init
git cms-merge-topic felicepantaleo:truth-adaptive-associator-v1
git clone https://github.com/felicepantaleo/TruthGraphAnalysis.git TruthGraphAnalysis
scram b -j 8
```

Integration builds leave cvmfs after about two weeks. If this one is gone, take the most
recent one. A newer release reads the tutorial files. An older release cannot read them.

The recipes below use scripts from
[TruthGraphAnalysis](https://github.com/felicepantaleo/TruthGraphAnalysis), in the
folders `GettingStarted` and `Tracking`. Set this variable once:

```bash
T=https://felice.web.cern.ch/orbit/TruthGraphTutorial
```

## Is the graph in my file?

```bash
edmDumpEventContent step3.root | grep -E 'truth::|TruthGraph '
```

```
TruthGraph                            "mix"                                 ""   "HLT"
truth::Graph                          "truthLogicalGraphProducer"           ""   "HLT"
truth::LogicalGraphHitIndex           "truthLogicalGraphHitIndexProducer"   ""   "HLT"
```

`truth::Graph` is the graph you analyse. `truth::LogicalGraphHitIndex` holds the detector
hits of each particle. `TruthGraph` is the raw graph, which is for debugging. The three
products are built in the digitisation step, so `step2.root` holds them too.

The association maps are made in the reconstruction step. The tutorial samples ran
`customiseTruthGraphAssociators`, so their `step3.root` holds them:

```bash
edmDumpEventContent step3.root | grep allTrackToTruthBranchAssociators
```

```
... "allTrackToTruthBranchAssociators"   "generalTracksRecoToTruthAdaptiveNominal"   "RECO"
... "allTrackToTruthBranchAssociators"   "generalTracksRecoToTruthAdaptiveTight"     "RECO"
... "allTrackToTruthBranchAssociators"   "generalTracksRecoToTruthFixed"             "RECO"
... "allTrackToTruthBranchAssociators"   "generalTracksTruthToReco"                  "RECO"
```

## What does one event hold?

`GettingStarted/py/first_look.py` counts the particles, the vertices and the
interactions, and prints the children of each top.

```bash
python3 TruthGraphAnalysis/GettingStarted/py/first_look.py $T/ttbar/step3.root -n 2
```

```
2115 particles (707 with GEN, 1680 with SIM, 2115 signal), 1306 vertices, 1 interactions
  top 5 -> [-24, -5]
  top 10 -> [24, 5]
3691 particles (1030 with GEN, 3088 with SIM, 3691 signal), 2237 vertices, 1 interactions
  top 4 -> [24, 5]
  top 5 -> [-24, -5]
```

A particle can have GEN, SIM or both. A particle with both is one node: the generator
particle and the Geant4 track are merged. The core of the script is:

```python
from PhysicsTools.TruthInfo.graphTools import eventGraphs

for graph in eventGraphs("step3.root", maxEvents=2):
    for i in range(graph.nParticles()):
        if abs(graph.pdgId(i)) == 6 and graph.lastCopy(i) == i:
            print("top", i, "->", [graph.pdgId(c) for c in graph.children(i)])
```

`lastCopy` skips the copies that the generator writes when a particle radiates. The last
copy is the one that decays.

## How do I draw an event?

Every sample folder has two events in `graphs/`, as PDF. To draw your own event:

```bash
wget $T/zee/step3.root
cmsRun $CMSSW_BASE/src/PhysicsTools/TruthInfo/test/dumpTruthGraphsFromGENSIMRECO_cfg.py \
    file:step3.root -n 1 --geometry ExtendedRun4D122
dot -Tpdf truthlogicalgraph_run1_lumi1_event<N>.dot -o event.pdf
```

The `truthlogicalgraph` file is the graph you analyse. The `truthgraph` file is the raw
graph. Orbit draws DOT files up to 3 MB in the sample folder.

### Look at an event on a laptop, with no CMSSW

The [truth graph viewer](https://github.com/felicepantaleo/CMSSWTruthViz) draws the graph
interactively and the rechits of each particle in 3D. The orbit folder `viewer/` has 14
tutorial events, two per sample, ready for it. You need Python 3.9 or newer:

```bash
git clone https://github.com/felicepantaleo/CMSSWTruthViz.git
cd CMSSWTruthViz
curl -O https://felice.web.cern.ch/orbit/TruthGraphTutorial/viewer/TruthGraphTutorialViewer.tar.gz
tar xzf TruthGraphTutorialViewer.tar.gz
TRUTHVIZ_CATALOG=$PWD/TruthGraphTutorialViewer/catalog.json TRUTHVIZ_SKIP_CMSSW_INSTALL=1 ./run.sh
```

Open the URL that the server prints, normally `http://localhost:8009/app/`, select
`Sample catalogue` and pick an event. Click a particle and select `Direct hits` or
`Subgraph hits` to draw its rechits. `TRUTHVIZ_SKIP_CMSSW_INSTALL=1` stops `run.sh` from
installing a CMSSW release when it finds `/cvmfs`, for example on lxplus.

To show the rechits, the viewer needs the sim-hit DetIds of each particle in the DOT file.
The dumper writes them only with `process.truthLogicalGraphDumper.dumpSimHits = True`, so the
DOT files in `graphs/` and the ones from the command above do not have them. The viewer
sets this parameter itself when it processes a `step3.root`: select `CMSSW ROOT` in the
page, start `run.sh` in the area of [Set up an area](#set-up-an-area) (after `cmsenv`, or
with `TRUTHVIZ_CMSSW_SRC=$CMSSW_BASE/src`) and give the dumper arguments
`--geometry ExtendedRun4D122`.

## What are the decay products of a tau?

The children of a tau are its generator decay products. Its descendants also hold the
particles that Geant4 makes later: the photons and electrons of showers and conversions,
and the products of nuclear interactions. The visible decay products are the
generator-stable descendants, without the neutrinos:

```python
NEUTRINOS = (12, 14, 16)
for tau in range(graph.nParticles()):
    if abs(graph.pdgId(tau)) != 15 or graph.lastCopy(tau) != tau:
        continue
    products = [d for d in graph.descendants(tau)
                if graph.particle(d)["hasGen"] and graph.particle(d)["status"] == 1
                and abs(graph.pdgId(d)) not in NEUTRINOS]
```

```bash
python3 TruthGraphAnalysis/GettingStarted/py/tau_products.py $T/tentau/step3.root
```

```
tau 0: [-11] (74 descendants in total, Geant4 included)
tau 1: [13] (13 descendants in total, Geant4 included)
tau 2: [22, 22, 211] (9 descendants in total, Geant4 included)
tau 3: [-211, -211, 22, 22, 211] (20 descendants in total, Geant4 included)
tau 4: [22, 22, 211] (68 descendants in total, Geant4 included)
...
```

The two photons are the decay products of a pi0: the generator decays the pi0, so its
photons are generator-stable. `hasGen` is sufficient to remove the Geant4 particles. In
200 ttbar events, Geant4 produced 510047 particles and none of them is at a generator
vertex.
The [Tau example](https://github.com/felicepantaleo/TruthGraphAnalysis/tree/main/Tau)
goes further: it names the decay mode, gives the reconstruction decay mode number and
computes the visible energy. In C++, `truth::Branch::finalState()` on the branch of the
tau gives the same decay mode as this rule for all 71 taus of 200 ttbar events.

## How do I compute a physics quantity?

`GettingStarted/py/z_mass.py` takes the last copy of each Z, its two lepton children, and
the mass of the pair. It writes a histogram with matplotlib.

```bash
python3 TruthGraphAnalysis/GettingStarted/py/z_mass.py $T/zmumu/step3.root -o z_mass.png
```

```
1063 Z decays, mean mass 91.64 GeV
```

The script reads 1063 events in about 45 seconds from a local file.

## What does a pileup event hold?

```bash
python3 TruthGraphAnalysis/GettingStarted/py/pileup.py $T/ttbar_pu200/step3.root
```

```
135289 particles, 1943 signal, 194 interactions
  particles per bunch crossing: {0: 135289}
  caloBoundary: 64303 particles, 842 signal
```

Every particle carries the interaction it comes from. `isSignal` is true for the in-time
signal interaction and `isFromPileup` for all the others. In this sample every particle
is in bunch crossing 0: the graph holds the in-time pileup only.
`particlesOfLevel("caloBoundary")` gives the particles that enter the calorimeter, for
the signal and for the pileup together.

## Which truth particle made this track?

The maps are C++ objects that FWLite python cannot read, so this recipe is an
`EDAnalyzer`. The map `RecoToTruth` has one row per track. Each entry is a particle, the
number of hits it shares with the track, and a score.

```cpp
using BranchMap = ticl::TICLAssociationMap<ticl::mapWithSharedEnergyAndScore>;
const edm::EDGetTokenT<BranchMap> recoToTruthToken_ = consumes(
    edm::InputTag("allTrackToTruthBranchAssociators", "generalTracksRecoToTruthAdaptiveNominal"));

// in analyze()
auto const& graph = event.get(graphToken_);
auto const& tracks = event.get(tracksToken_);
auto const& recoToTruth = event.get(recoToTruthToken_).getMap();
for (uint32_t t = 0; t < tracks.size(); ++t) {
  if (recoToTruth[t].empty())
    continue;  // no candidate particle shares a hit with this track
  auto const& best = recoToTruth[t].front();
  const truth::Particle particle(&graph, best.index());
  const float purity = best.sharedEnergy() / tracks[t].numberOfValidHits();
}
```

There is one map for each working point:

- `Fixed`: every candidate particle that shares a hit, in order of score. The detector
  particles come first, so row [0] is a detector particle when one matches. The partons,
  the bosons and the beam particles come after them.
- `AdaptiveTight` and `AdaptiveNominal`: one particle per track. The associator climbs the
  ancestry and stops at the particle whose hits match the track best. The answer is never
  a parton, a boson or a beam particle.

The truth validation books all three.

[Match reconstruction to truth](adaptive-associator.md) explains the working points.
For tracksters and other calorimeter objects the maps have the same form, with shared
energy in place of shared hits.

## Can I reproduce the TrackingParticle efficiency?

Yes. `Tracking/test/trackingEfficiency_cfg.py` measures the efficiency, the fake rate and
the duplicate rate of `generalTracks` with the definitions of `MultiTrackValidator` (MTV):

- Selected particles: simulated, charged, signal and in time, pT > 0.9 GeV,
  abs(eta) < 4.5, production vertex with r < 2.5 cm and abs(z) < 30 cm. This is the MTV
  selection for the efficiency against eta.
- A track comes from a particle when the particle owns at least 75% of its hits.
- A particle is found when a track comes from it.
- A track is fake when its best particle owns less than 75% of its hits.

```bash
cmsRun TruthGraphAnalysis/Tracking/test/trackingEfficiency_cfg.py -i $T/ttbar/step3.root -n 100
```

```
selected particles 6825, efficiency 0.902711, duplicate rate 0.00278388; tracks 13913, fake rate 0.00136563
```

The table compares the result with the MTV of the same reconstruction job, on the same
events.

| Sample | Candidates | Selected, graph / MTV | Tracks | Efficiency, graph / MTV | Fake rate, graph / MTV |
|---|---|---|---|---|---|
| ttbar, 1000 events | maps in the file | 71985 / 71974 | 149286 | 0.906 / 0.889 | 0.0011 / 0.0048 |
| ttbar, 1000 events | `--candidatePtMin 0.1` | 71985 / 71974 | 149286 | 0.907 / 0.889 | 0.0001 / 0.0048 |
| ttbar PU200, 100 events | maps in the file | 6829 / 6829 | 773396 | 0.900 / 0.880 | 0.811 / 0.111 |
| ttbar PU200, 100 events | `--candidatePtMin 0.1` | 6829 / 6829 | 773396 | 0.901 / 0.880 | 0.099 / 0.111 |

The graph selects the same particles as MTV: the counts agree to within 12 of 71974.
The efficiency of the graph is higher in every region of eta. Without pileup it is 1.3 to
3.0 points higher below abs(eta) 3.5, and 0.8 points higher from 3.5 to 4.5. At PU200 it
is 1.8 to 4.3 points higher below abs(eta) 3.5.
The two definitions of "hits of a particle" are not the same. A TrackingParticle holds the
hits of one Geant4 track. A branch holds the hits of the particle and of its
descendants. This page does not measure how much of the difference comes from this.

The fake rate needs the right candidates. The maps in the file offer only stable
particles with pT > 1 GeV and abs(eta) < 4 as candidates. At pileup most tracks come from
softer particles, so these tracks have no candidate and count as fake: 0.811.
`--candidatePtMin 0.1` runs the association again in the job, with every particle above
0.1 GeV and abs(eta) < 4.5 as a candidate. The fake rate at pileup is then 0.099. This
costs about 3.6 s per PU200 event on one thread.

For efficiency against truth levels (`caloBoundary`, `stableDecayProducts`, ...), and
for the reco-driven view with duplicates, see the tracking analyzers in
[taustudies](https://gitlab.cern.ch/cms-tau-pog/taustudies).

## MTD: reproduce MtdTracksValidation

The [MTD example](https://github.com/felicepantaleo/TruthGraphAnalysis/tree/main/Mtd) is
a port of `MtdTracksValidation` to the graph. It fills the monitor elements of the legacy
module under the same names, in the folder `MTD/TracksGraph`.
[Port an existing associator](tutorial-port-associator.md) explains each step of the
port. To run it on a finished `step3.root`, without the reconstruction:

```bash
wget $T/ttbar/step3.root $T/ttbar/step3_inDQM.root
cmsRun TruthGraphAnalysis/Mtd/test/mtdGraphOnStep3_cfg.py -i step3.root -o mtdGraph_inDQM.root
cmsDriver.py step4 -s HARVESTING:@phase2Validation -n -1 --conditions auto:phase2_realistic_T35 \
    --geometry ExtendedRun4D122 --era Phase2C26I13M9 --mc --scenario pp --filetype DQM \
    --filein file:mtdGraph_inDQM.root,file:step3_inDQM.root
python3 TruthGraphAnalysis/Mtd/test/compareMtdPort.py DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root
```

The job builds the MTD channel of the hit index from the MTD sim clusters in the file,
associates the tracks with a candidate floor of 0 GeV, and runs the port. The harvesting
takes the legacy folder `MTD/Tracks` from `step3_inDQM.root` of the sample. The ttbar
sample, 1000 events:

```
BTL                                        legacy    graph  graph/legacy
tracks matched to truth                     42155    42382         1.005
  particle with direct hits                 30167    30097         0.998
    first direct cluster on the track       26735    26739         1.000
    another cluster on the track             1325     1258         0.949
    no cluster on the track                  2107     2100         0.997
  particle with other hits only              6105     6192         1.014
  particle without MTD hits                  5883     6093         1.036

ETL                                        legacy    graph  graph/legacy
tracks matched to truth                     28026    28060         1.001
  particle with MTD hits                    19690    19610         0.996
    correct cluster                         14859    14888         1.002
    wrong cluster                            1792     1702         0.950
    no cluster                               3039     3020         0.994
  particle without MTD hits                  8336     8450         1.014

time residual, correct cluster      legacy mean     rms   graph mean     rms  [ps]
  BTL                                     -11.1    32.5        -11.0    32.5
  ETL                                      -7.9    34.8         -7.9    34.8
```

The MTD hits of a particle come from `directHits(truth::HitChannel::MTD, particle)` of the
hit index, with the module, the cell, the energy and the time of each hit. This is the
starting point for any other MTD question: a time resolution per particle type, the
clusters of a pileup particle, or the hits that a secondary leaves.

## e/gamma: associate GSF tracks

The release does not associate GSF tracks. The associator can run in your own analyzer
on any collection of tracks: a `reco::GsfTrack` is a `reco::Track`, so the hit adapter
takes it as it is. The [Egamma
example](https://github.com/felicepantaleo/TruthGraphAnalysis/tree/main/Egamma) does
this for `electronGsfTracks`:

```cpp
// once per event: the candidates of the file, on the tracker channel, counting hits
const truth::BranchHitAssociator associator(hitIndex,
                                            std::vector<uint32_t>(selected.begin(), selected.end()),
                                            truth::BranchHitAssociator::Metric::SharedHits,
                                            truth::HitChannel::Tracker,
                                            /*emptyRootsMeansAll=*/false);
// per GSF track: every candidate that shares a hit, best score first
const auto hits = truth::recoHits(gsfTrack);
for (auto const& match : associator.bestBranches(std::span<const truth::RecoHit>(hits))) {
  if (!assignable[match.rootParticleId])
    continue;  // a parton, a boson or a beam particle
  const double purity = 1. - match.score;
  const truth::Particle electron = truth::Particle(&graph, match.rootParticleId).lastCopy();
  break;
}
```

`lastCopy()` is necessary. The generator writes an electron again after it radiates a
photon, and the two copies own the same hits. On a tie the associator puts the particle
with the lower index first, which is the earlier copy. On the zee sample the analyzer
finds 863 of the 1552 Z electrons without `lastCopy()`, and 1391 with it.

```bash
cmsRun TruthGraphAnalysis/Egamma/test/gsfTrackTruth_cfg.py -i $T/zee/step3.root
```

```
GSF tracks 1655: 1652 with a particle owning 75% of the hits, 1496 of them an electron, 1484 an electron from the Z
Z electrons 1552: found by hits 1391, by delta R 1391, by both 1391
```

The Z electrons have pT > 5 GeV and abs(eta) < 3. The hit match and a delta R < 0.05
match find the same 1391 electrons. The mean of pT(GSF) / pT(truth) is 0.949. The same
code takes any other track collection, for example `hltEgammaGsfTracksUnseeded`. This page
does not test that.

## Particle flow: check PF candidates

The [ParticleFlow
example](https://github.com/felicepantaleo/TruthGraphAnalysis/tree/main/ParticleFlow)
compares the type of each PF candidate with the true particle. A charged candidate takes
the particle of its track, from the track map. A neutral candidate takes the particle of
its most energetic ECAL or HCAL cluster, from the PF cluster maps
`truthBranchPFClusterEcalAssociators` and `truthBranchPFClusterHcalAssociators`.

```cpp
// charged: row [0] of the track map for the track of the candidate
auto const track = candidate.trackRef();
auto const& best = trackMap[track.key()].front();
// neutral: the most energetic ECAL or HCAL cluster in the candidate blocks
for (auto const& [block, index] : candidate.elementsInBlocks()) {
  auto const cluster = block->elements()[index].clusterRef();
  ...
}
```

```bash
cmsRun TruthGraphAnalysis/ParticleFlow/test/pfCandidateTruth_cfg.py -i $T/ttbar/step3.root --minEnergy 5
```

```
PF type vs truth class (rows: PF type)
               e        mu     gamma       h+-        h0    merged  no match
     h      1216       100        34     47583        45        91       141
     e       555         3         4       716         0         6        20
    mu         3       571         0       121         0         1         0
 gamma        90         0       572       165       295      2591       204
    h0         3         0         2       294       361       365       222
neutral candidates without an ECAL or HCAL cluster (HGCAL or HF): 105987
mean E response: charged 0.977653, neutral 0.527128
```

This is the ttbar sample, 1000 events, candidates above 5 GeV. A match counts when the
particle owns at least 75% of the object. The class `merged` is a particle that the
generator decayed, for example a pi0, an eta or a B meson. It is the best match when
the cluster merges several of its decay products. Most PF photons above 5 GeV are of this
kind: the photons of one pi0 in one cluster. The endcap neutral candidates come from
HGCAL through TICL and have no ECAL or HCAL cluster. For them, use the TICL candidate
maps, `truthBranchTracksterAssociators:ticlCandidate...`.

## Where are the validation plots?

Each sample folder has a `validation/` gallery, made by
`Validation/TruthInfo/scripts/makeTruthValidationPlots.py` from the harvested DQM file.
It shows efficiency, fake rate, duplicate rate, purity and resolution for tracks,
tracksters, candidates and PF clusters, for each truth level and each working point.
Start at `validation/index.html`. [Validation](validation.md) explains the plots.

To make the gallery from your own DQM file:

```bash
python3 $CMSSW_BASE/src/Validation/TruthInfo/scripts/makeTruthValidationPlots.py \
    DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root --outputDir plots --sample "my sample"
```

## FAQ

**The children of my particle include electrons and photons that I did not expect.**
Geant4 adds them: delta rays, bremsstrahlung, conversions, nuclear interactions. They
have `hasGen` false. Select `hasGen` for the generator view, as in the tau recipe.

**Can I read the association maps in python?**
No. FWLite python cannot instantiate the map type, `TICLAssociationMap<..., void, void>`.
Read the maps in an `EDAnalyzer`, as in the tracking recipe. The graph itself reads in
python.

**My track is matched to a W or a top.**
You read an entry of `Fixed` after row [0]. A W carries the hits of all its descendants,
so it shares every hit with the track. Take row [0] of `Fixed`, or use an `Adaptive`
map.

**My match is an earlier copy of the particle, with no SIM part.**
The generator writes a particle again after it radiates, and the copies own the same
hits. The maps of the release put the later copy first on a tie. The associator that you
run yourself does not. Take `lastCopy()` of the match, as in the e/gamma recipe.

**Many of my pileup tracks have no match.**
The shipped candidate set requires pT > 1 GeV and abs(eta) < 4 for stable particles.
Run the association again with a wider set, as `--candidatePtMin` does in the tracking
recipe.

**Does the graph hold out-of-time pileup?**
No. In the PU200 sample all 135289 particles of the first event are in bunch crossing 0.

**How do I produce my own sample?**
Every Run4 era builds the graph in the digitisation step. For the association maps and
the truth validation, add this to the reconstruction step:

```bash
--procModifiers enableTruth \
--customise SimGeneral/TruthGraphAssociatorProducers/customiseTruthGraphAssociators.customiseTruthBranchValidation,SimGeneral/TruthGraphAssociatorProducers/customiseTruthGraphAssociators.customiseTruthGraphAssociators
```

`configs/run_sample.sh` in each tutorial sample folder has the four complete commands.

**Where do I find more examples?**
[Worked analyses](worked-analyses.md) has one example per physics process, in C++ and in
python. [taustudies](https://gitlab.cern.ch/cms-tau-pog/taustudies) has tau and tracking
studies with plots.
