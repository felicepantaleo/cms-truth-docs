# Tutorial: read a graph in python

The python interface is for looking at events: understanding one event, checking a claim,
or prototyping a selection before writing it in C++. It reads either an EDM file or a JSON
dump, and it needs no compilation.

This tutorial uses the sample from [Quickstart](quickstart.md). Every command runs inside
a CMSSW environment, because the module ships with `PhysicsTools/TruthInfo`.

## Opening events

`eventGraphs` yields one view per event of an EDM file. `TruthGraphView.fromJson` reads a
dump written by `TruthLogicalGraphDumper`, which is what the tests use because it needs no
input file.

```python
from PhysicsTools.TruthInfo.graphTools import eventGraphs, TruthGraphView

for graph in eventGraphs("step3.root", maxEvents=5):
    ...

graph = TruthGraphView.fromJson("event.json")
```

A view holds the whole event. Particles and vertices are addressed by integer id, and
every accessor takes that id.

## A first pass over one event

Save this as `look.py` and run it in the directory of the quickstart sample.

```python
from PhysicsTools.TruthInfo.graphTools import eventGraphs

for graph in eventGraphs("step3.root", maxEvents=1):
    print("particles", graph.nParticles(), "vertices", graph.nVertices())

    visible = graph.particlesOfLevel("reconstructableFinalState")
    print("reconstructable final state:", len(visible))

    lead = max(visible, key=lambda i: graph.p4(i)[3])
    print("leading: pdgId %d, E %.1f GeV, levels %s"
          % (graph.pdgId(lead), graph.p4(lead)[3], graph.levels(lead)))

    node, chain = lead, []
    while graph.parents(node):
        node = graph.parents(node)[0]
        chain.append(graph.pdgId(node))
    print("ancestry of the leading object:", chain)

    for b in graph.particlesOfLevel("bHadrons"):
        products = [graph.pdgId(c) for c in graph.children(graph.lastCopy(b))]
        print("b hadron %d decays to %s" % (graph.pdgId(b), products))

    print("interactions:", [(i["eventId"], i["isSignal"]) for i in graph.interactions()])
```

It prints:

```
particles 2003 vertices 1165
reconstructable final state: 203
leading: pdgId -2212, E 1946.9 GeV, levels ['stableDecayProducts', 'reconstructableFinalState']
ancestry of the leading object: [-2214, 21, 21, 21, 21, 2212]
b hadron -531 decays to [433, 331, -211, 111, 213, -211, 111]
b hadron 521 decays to [-423, 211, 331, 111, 113]
interactions: [(0, True)]
```

## Reading the result

**The most energetic reconstructable object is not the physics.** It is an antiproton of
1.9 TeV, and its ancestry runs back through a Delta baryon and a chain of gluons to the
beam proton. It is a beam remnant going down the beam pipe. A level says what kind of
object something is, not whether it is in the acceptance: apply a pseudorapidity and a
momentum cut for that, which is what `truth::BranchSelector` does in C++.

**The ancestry is a chain of copies.** Four gluons appear in a row. A generator records a
radiating particle as a sequence of copies of itself, and the graph keeps that record
faithfully. This is why `graph.lastCopy(i)` exists and why the loop above calls it before
asking for the children of a b hadron: on the first copy the only child would be the next
copy.

**A b hadron decay reads as physics.** The first line is an anti-B<sub>s</sub> meson
(pdgId -531) decaying to a D<sub>s</sub>\* meson (433), an eta prime (331), two negative
pions, two neutral pions and a positive rho. These are generator-level decay products, not
reconstructed objects.

## The rest of the interface

Navigation, in each case by particle id:

```python
graph.parents(i), graph.children(i)          # one generation
graph.descendants(i)                         # everything below, each once
graph.productionVertices(i), graph.decayVertices(i)
graph.productionSiblings(i)                  # what was produced with it
graph.firstChildWithPdgId(i, 22)             # the first child of that species
graph.lastCopy(i)                            # the end of a radiating chain
```

Levels and provenance:

```python
graph.levels(i)                              # the names of every level it is at
graph.isAtLevel(i, "caloBoundary")
graph.particlesOfLevel("bHadrons")
graph.particlesAtLevels(["caloBoundary", "stableDecayProducts"], "all")
graph.signalParticles()                      # what the preset named as the signal
graph.isSignal(i), graph.isFromPileup(i)
graph.bunchCrossing(i), graph.eventIndex(i)
```

The event as a whole:

```python
graph.interactions()                         # one entry per proton collision, signal first
graph.interactionVertices()                  # the vertices the graph marks as interaction points
graph.summary()                              # one line per interaction
```

[Interface reference](interface.md) lists the C++ signatures, which carry the same names.

## Two differences from C++ worth knowing

The python side reads the level flags stored on each particle when the file was
written. The C++ side can also recompute a level from the graph, which is the current
definition. On a file written by the current release the two agree. On an older file they
can differ, and the recomputed answer is the definition that holds now.

Python has no hit index. Matching a reconstructed object to a truth object through shared
detector hits is C++ only, because the hit index is large and the matching is a merge over
sorted hit lists. [Write an analyser in C++](tutorial-cxx.md) covers it.

## Where to go next

- [Write an analyser in C++](tutorial-cxx.md) to run inside a CMSSW job and use the hits.
- [Worked analyses](worked-analyses.md) has eleven python analyses to copy from.
