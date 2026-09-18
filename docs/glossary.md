# Glossary

The terms this site uses, in the sense the code gives them.

## The event history

**Particle, vertex.** The two kinds of node in the logical graph. A particle is one
physical particle, generator side and simulation side merged into a single node. A vertex
is a point where particles were produced or decayed. Edges are production and decay.

**Copy, last copy.** A generator records a radiating particle as a chain of copies of
itself: a W that emits a photon appears several times. Only the final copy carries the
decay, so asking the first copy for its children returns the next copy, not the decay
products. `Particle::lastCopy()` walks to the end of the chain. This is the single most
common mistake in a first analysis.

**Interaction.** One proton-proton collision in the event. Every particle and vertex
records which one it came from, packed into an `EncodedEventId`. The signal is the in-time
collision with index 0. The packed value of the signal is zero, and so is the default
value of the field, so `isSignal()` exists to be asked rather than comparing with zero by
hand.

**Checkpoint.** The position and momentum of a particle recorded where it crossed a
labelled surface. Checkpoint 0 is the boundary between the tracker and the calorimeter,
and the `caloBoundary` level is defined by having it.

**Artificial vertex.** A vertex the graph invents to summarise activity that a selection
preset cut away, so that what was dropped stays visible. `Interaction` is the root of one
collision, and it fans out to an `InitialState` vertex, which holds the truncated
production context of the selected particles, and an `UnderlyingEvent` vertex, which holds
the stable particles that belong to no selected subgraph. A `BeamSideInput` vertex hangs
off a kept vertex instead, and holds the dropped parents that fed it from the beam side. A
particle produced at one of these is still a real particle; only the vertex is invented.

**Connector, signal stand-in.** The two kinds of particle the graph invents. A connector
joins the `Interaction` root to one of its source vertices, so that the whole collision
descends from a single node and the signal is everything reachable from the signal
`Interaction` vertex. A stand-in represents a resonance the generator never wrote, so that
a non-resonant sample still has a signal object; its momentum is an accounting sum over the
hard-process legs, not a generator quantity. Both are marked synthetic.

## Choosing a truth object

**Level.** A named, written rule that selects the particles one kind of measurement is
about: `caloBoundary` for what arrived at the calorimeter, `bHadrons` for the weakly
decaying beauty hadron of each chain, and ten more. Because a level is code, software
recomputes it and checks it against what a file stored.

**Antichain.** A set of particles in which none is an ancestor of another. Every level
must be one. The reason is arithmetic rather than aesthetic: a set holding both a tau and
its decay products asks for both as separate objects out of the same detector hits, so an
efficiency over that set counts the same energy twice and stops meaning anything.

**Preset.** The per-process statement of what the signal is: the Higgs in one sample, the
two top quarks in another, the gun particle in a single-particle sample. Ten presets cover
the Run4 samples, and one call applies a preset to every module that has to agree on it.

**Branch.** A particle together with a chosen part of its decay history. This is what
replaces a frozen truth object: a branch is computed when you ask for it, so it costs
nothing to store and you can ask for a different one on the same event.

**Closure.** The rule that says how far below its root a branch extends. `Subtree` takes
everything, `StableLeaves` stops at the particles the generator left stable, `DepthN` stops
after a fixed number of generations, `UntilPdgId` and `UntilLevels` stop at named species
or levels, and `Predicate` stops wherever a caller's function says so.

## Hits and matching

**Hit channel.** The four detector groups the hit index keys on: `Tracker`, `MTD`, `Calo`
and `Muon`. `Calo` is all calorimetry, endcap and barrel together. Each channel has its own
identifier space and its own matching metric, so a channel is chosen explicitly.

**Direct hits, subgraph hits.** The hits a particle left itself, and the hits of that
particle together with everything it produced. A photon that converts leaves no hit of its
own, and all of its energy appears in its subgraph hits. Summing energy over a subgraph
list is correct; per-cell arithmetic on one is not, because the same cell appears once per
contributing descendant and has to be coalesced first.

**Cell keying.** In the tracker a detector identifier names a module, not a readout cell,
so two particles crossing the same module share every identifier they leave there. The
tracker channel therefore carries the cell alongside the identifier, and a tracker match
requires the same cell.

**Working point.** One setting of the reconstruction-to-truth matching, written as its own
map so that several can be compared in the same job. `Fixed` is the plain per-candidate
match. `AdaptiveTight` and `AdaptiveNominal` let the match climb to an ancestor when that
ancestor describes the reconstructed object better, which is what recovers a merged neutral
pion whose two photons are one cluster. They differ in how far the climb may go.

**Score.** How much of the reconstructed object the truth candidate fails to cover. Lower
is better, and every association map this code writes sorts that way. The reverse score is
the same quantity the other way round: how much of the truth candidate the reconstructed
object fails to cover. A climb lowers the score and raises the reverse score, and the
adaptive working points balance the two.

**Shared energy, shared hits.** The two matching metrics. Shared energy weights each cell
by the energy in it and is the calorimeter metric. Shared hits counts cells and is the
tracker metric.

## Around the graph

**Truth level flags.** The levels a file recorded for each particle, stored as one bit
each. The python tools read these. The C++ can also recompute a level from the graph, which
is the definition that holds now; on a file written before a definition changed the two
differ, and that difference is how a stale file is detected.

**Event mixing.** The step that overlays the other proton-proton collisions of the bunch
crossing on the signal collision. The truth graph is built after it, so the graph holds the
pileup as well. See [Pileup](pileup.md).
