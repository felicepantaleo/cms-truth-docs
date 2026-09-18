# Quickstart: your first truth graph

This tutorial takes you from an empty directory to a truth graph you can read, in about
half an hour of which most is the simulation job running. You will produce three
simulated events, confirm that the graph is in the output, print what one event contains,
and draw its history as a picture.

You need an account with access to `/cvmfs/cms.cern.ch` and a machine with about 20 GB of
free disk.

## Step 1: get a release and the branch

The two data-format packages are in `CMSSW_20_1_X`. The association layer and the DQM
package are offered upstream in cms-sw/cmssw#51829, so for now one merge brings
everything.

```bash
cmsrel CMSSW_20_1_X_2026-09-13-2300      # scram list CMSSW_20_1_X shows what is on cvmfs today
cd CMSSW_20_1_X_2026-09-13-2300/src
cmsenv
git cms-init
git cms-merge-topic felicepantaleo:truth-adaptive-associator-v1
scram b -j 8
```

Integration builds age off cvmfs after about two weeks, so take a recent one rather than
the release named here.

## Step 2: produce three events

Every Run4 era carries the `enableTruth` process modifier, so a standard workflow builds
the truth graph by itself. No option, no customise.

```bash
runTheMatrix.py -w upgrade -l 37634.0 --nEvents 3 -t 8
```

Workflow 37634.0 is top quark pair production at 14 TeV, with the Run4 D127 geometry and
no pileup. The job runs generation and simulation, then digitisation, then
reconstruction, then harvesting. It writes into a directory named after the workflow and
takes about ten minutes.

## Step 3: confirm the graph is there

The graph is built during digitisation, so it is already in the step 2 output.

```bash
cd 37634.0_TTbar_14TeV+Run4D127
edmDumpEventContent step2.root | grep -E '^truth::|^TruthGraph'
```

You should see three products:

```
TruthGraph                     "mix"
truth::Graph                   "truthLogicalGraphProducer"
truth::LogicalGraphHitIndex    "truthLogicalGraphHitIndexProducer"
```

These are the three layers. `TruthGraph` is the generator and simulation records joined
into one graph. `truth::Graph` is the physics view of that graph, with particles and
vertices as nodes. `truth::LogicalGraphHitIndex` holds the detector hits of each particle.
[Data model](data-model.md) describes all three.

## Step 4: read one event in python

```bash
python3 -c "
from PhysicsTools.TruthInfo.graphTools import eventGraphs
for graph in eventGraphs('step3.root', maxEvents=1):
    print('particles', graph.nParticles(), 'vertices', graph.nVertices())
    print(graph.summary())
    leading = max(range(graph.nParticles()), key=lambda i: graph.p4(i)[3])
    print('most energetic:', graph.pdgId(leading), '%.1f GeV' % graph.p4(leading)[3], graph.levels(leading))
"
```

On the first event of this sample it prints:

```
particles 2003 vertices 1165
eid 0 (bx 0, index 0): 2003 particles, no artificial vertex
most energetic: 2212 7000.0 GeV []
```

Your numbers will differ. Which events a job writes, and in which order, depends on how
many events were asked for and on the number of threads, so the counts below are one
event and not a property of the sample.

Three things are worth noticing.

The event has 2003 particles and 1165 vertices. That is the whole history, generator and
simulation together, not a selected list.

The summary line reports one interaction, `eid 0`, which is the signal. With pileup there
would be one line per overlaid interaction. See [Pileup](pileup.md).

The most energetic object is pdgId 2212, a 7 TeV proton, and it belongs to no truth level.
It is a beam particle. Truth levels are named rules that pick out the particles a given
measurement is about, and no measurement is about the beam. The next tutorial is about
choosing the right level.

## Step 5: draw the event

A picture of the history is the fastest way to understand what the graph holds.

```bash
cmsRun $CMSSW_BASE/src/PhysicsTools/TruthInfo/test/dumpTruthGraphsFromGENSIMRECO_cfg.py \
    file:step3.root -n 1 -o dump --geometry ExtendedRun4D127
dot -Tsvg dump/truthlogicalgraph_run1_lumi1_event*.dot -o event.svg
```

The `--geometry` option must name the geometry the sample was produced with, because the
dumper reads hit positions through it. The job also writes the same graph as JSON, which
the python tools read directly with `TruthGraphView.fromJson`.

Open `event.svg` in a browser and zoom in. Particles are ellipses, vertices are boxes, and
the colour of a vertex says what happened there: a decay, a photon conversion, a nuclear
interaction. [Reading real events](examples.md) reads two such pictures in detail.

## Where to go next

- [Choose a truth definition](tutorial-truth-definitions.md) explains truth levels and
  selection presets, which decide what counts as a truth object.
- [Read a graph in python](tutorial-python.md) is a tour of the python interface.
- [Write an analyser in C++](tutorial-cxx.md) does the same from a CMSSW module.
- [Worked analyses](worked-analyses.md) is a repository of eleven complete analyses, one
  per physics topology, each in both languages.
