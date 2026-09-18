# Tutorial: choose a truth definition

An efficiency is only as meaningful as the truth object it is measured against. The graph
holds the whole event history, so it does not decide for you which particles a measurement
is about. This tutorial shows the two mechanisms that make that choice explicit: truth
levels, which name a rule, and selection presets, which name the signal of a process.

It follows on from [Quickstart](quickstart.md) and uses the same three simulated top quark
pair events.

## The problem a level solves

At the end of the quickstart the most energetic object in the event was a 7 TeV beam
proton, and it belonged to no level. A beam proton is in the graph because it is part of
the history, not because any measurement is about it. The same is true of a Pythia string,
of an intermediate copy of a radiating electron, and of the thousands of secondary
particles a shower makes.

A truth level is a named, written rule that selects the particles one kind of measurement
is about. The rules are code, so software recomputes them and checks them, which is how
several defects in the simulation record were found. [Findings and changes](findings.md)
lists them.

## What each level holds

Count them on one event:

```bash
python3 -c "
from PhysicsTools.TruthInfo.graphTools import eventGraphs, LEVEL_BITS
for graph in eventGraphs('step3.root', maxEvents=1):
    for level in LEVEL_BITS:
        members = graph.particlesOfLevel(level)
        if members:
            print('%-28s %4d' % (level, len(members)))
"
```

On one of the quickstart events:

```
hardProcess                     6
stableDecayProducts           259
caloBoundary                  755
partonJets                      6
bHadrons                        2
cHadrons                        3
reconstructableFinalState     203
```

Read that as a set of answers to different questions.

| Level | The question it answers |
|---|---|
| `hardProcess` | which particles came out of the hard scattering |
| `partonJets` | which quarks and gluons of the hard process each stand for a jet |
| `caloBoundary` | which particles arrived at the calorimeter, which is what `CaloParticle` gave you |
| `stableDecayProducts` | which particles the generator left stable |
| `reconstructableFinalState` | which objects a detector could reconstruct, with a neutral pion counted as one object rather than two photons |
| `bHadrons`, `cHadrons` | which weakly decaying heavy-flavour hadron sits on each chain |
| `tauVisibleHadronic`, `tauVisibleLeptonic` | which taus decayed to hadrons and which to a lepton |

Six levels printed nothing, and the reason matters. Four of them are defined relative to
the signal or to the vertices that summarise it, so they stay empty until a selection
preset names the signal: `signal`, `reconstructableFromSignal`, `stableLegsFromInitialState`
and `underlyingEvent`. The two tau levels are empty only because this event has no tau.
[Validation](validation.md) lists all twelve levels with their rules.

## Asking for one level, or several

The counts above use the flags stored on each particle. In C++ you can also recompute a
level from the graph, which is the authoritative definition:

```cpp
#include "PhysicsTools/TruthInfo/interface/TruthLevels.h"

// The members of one level, as particle views.
for (truth::Particle const& p : truth::particlesAtLevel(graph, truth::Level::BHadrons)) {
  ...
}

// Several levels at once. Any is the union, All the intersection.
const auto visible = truth::particlesAtLevels(
    graph, {truth::Level::CaloBoundary, truth::Level::StableDecayProducts}, truth::LevelMatch::All);
```

`Any` is deliberately not reduced to a single generation. Levels nest: a hard-process b
quark is the ancestor of a B hadron, which is the ancestor of a D hadron, and each is the
member of its own level. A union that kept only the topmost would drop the very members
the caller asked for.

To get the decay products of each member as well, ask for branches instead of particles.
A branch is a particle together with a chosen part of its history:

```cpp
for (truth::Branch const& b : truth::branchesAtLevel(graph, truth::Level::BHadrons)) {
  b.p4();          // the four-momentum of the whole branch
  b.members();     // the particles it contains
}
```

## Presets: naming the signal of a process

A level is detector-facing and the same for every sample. What differs by sample is which
particle is the signal: the Higgs in one, the two top quarks in another, the gun particle
in a single-particle sample. A selection preset is that statement, and there is one per
physics topology.

Here is one top quark pair event, the same event read twice. Without a preset:

```
particles 1482, signal particles []
vertex roles {'Normal': 972}
levels hardProcess 6, stableDecayProducts 206, caloBoundary 578, partonJets 4,
       bHadrons 2, cHadrons 4, reconstructableFinalState 155, tauVisibleHadronic 1
```

With the preset for top quark pair production:

```
particles 1369, signal particles [(2, 6), (3, -6)]
vertex roles {'Normal': 874, 'Interaction': 1, 'InitialState': 1,
              'BeamSideInput': 1, 'UnderlyingEvent': 1}
levels signal 2, stableLegsFromInitialState 93, reconstructableFromSignal 70,
       underlyingEvent 114, hardProcess 6, stableDecayProducts 206, caloBoundary 578,
       partonJets 4, bHadrons 2, cHadrons 2, reconstructableFinalState 184,
       tauVisibleHadronic 1
```

Three things happened. The two top quarks now carry the `signal` level, so a question such
as "what fraction of the top quark energy is visible" has a subject. Four artificial
vertices appeared: the graph summarises everything the preset dropped into one interaction
point with three labelled sources, so that everything reachable from the interaction
vertex is, by definition, the signal. And the four signal-relative levels are now
populated.

The particle count fell from 1482 to 1369, and two levels moved with it: `cHadrons` from 4
to 2 and `reconstructableFinalState` from 155 to 184. A preset is a selection, so it
removes particles, and a level computed on the selected graph is not the same set as the
level computed on the whole event. Pick the preset for the question you are asking, and
state it when you report a number. [Reading real events](examples.md) shows the artificial
structure in a picture.

Apply a preset with one call, which sets it on every module that has to agree on it:

```bash
cmsDriver.py step3 ... \
  --customise_commands "from PhysicsTools.TruthInfo.customiseTruthPreset import applyTruthPreset; applyTruthPreset(process, preset='top')"
```

You can also name the generator fragment and let the rules choose the preset, which is
what a production does:

```bash
TRUTH_GRAPH_FRAGMENT=TTbar_14TeV_TuneCP5_cfi cmsDriver.py step3 ... \
  --customise PhysicsTools/TruthInfo/customiseTruthPreset.customiseTruthPreset
```

The job prints the preset it resolved and the seed species it used, so the log says which
view was built. The ten presets and the fragments they cover are listed in
[How to use the graph](usage.md#per-process-presets).

## Signal and pileup

Every particle and vertex records which proton collision it came from, and one test
separates the signal from the overlaid collisions:

```python
graph.isSignal(particleId)      # python
```

```cpp
particle.data().isSignal();     // C++
```

Do not compare the interaction id with zero by hand. The packed id of the signal is zero
and so is the default value of the field, so a path that forgets to set it labels pileup
as signal. That mistake has been made. [Pileup](pileup.md) explains the encoding.

## Where to go next

- [Read a graph in python](tutorial-python.md) for the rest of the python interface.
- [Write an analyser in C++](tutorial-cxx.md) to use these levels in a CMSSW module.
- [Worked analyses](worked-analyses.md) has one complete analysis per preset.
