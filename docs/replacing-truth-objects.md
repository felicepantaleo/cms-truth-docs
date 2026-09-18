# Replacing the legacy truth objects

`TrackingParticle`, `CaloParticle` and `SimCluster` are the truth objects CMS uses today.
Each is a collection built during digitisation, for one detector and one purpose, with its
grouping and its thresholds fixed at that moment. Together they hold three views of the
same event history, and none of the three can be walked or regrouped afterwards.

A `truth::Branch` is one view of the unified graph, computed when an analysis asks for it.
This page shows that a branch reproduces what the legacy objects deliver, and measures how
closely.

## What a branch adds

| | `TrackingParticle`, `CaloParticle`, `SimCluster` | `truth::Branch` |
|---|---|---|
| Construction | grouped once, during digitisation | computed on demand from the graph and a closure |
| Navigation | none, the object is flat | parents, children, ancestors, common ancestor, whole decay branches |
| Granularity | fixed | any closure: subtree, stable leaves, depth N, until a species, until a level, or a predicate |
| Detectors | one detector per object, calorimeter truth separate from tracker truth | one object, with a calorimeter and a tracker hit channel |
| Provenance | limited | bunch crossing, signal or pileup, generator event |
| Matching to reconstruction | one bespoke associator per object type | one `BranchHitAssociator` for any object that exposes `truthHits()` |
| Kinematics | stored | computed from the branch, including the visible and invisible parts |

## How the comparison is made

Two DQM analysers in `Validation/TruthInfo` map each legacy object to its logical particle,
through `obj.g4Tracks().front().trackId()` and the trackId to logical-particle map. They
then compare the two descriptions of the same particle.

`BranchHGCalValidator` covers the calorimeter. It compares the `subgraphHits` of the branch
with the `hits_and_fractions()` of the legacy object, and reports completeness, the
fraction of the object's hits the branch covers, and purity, the fraction of the branch's
hits that belong to the object. It also runs `BranchHitAssociator` and checks whether the
tightest best-scoring branch is the mapped particle.

`BranchTrackingValidator` covers the tracker. For each reconstructed track it compares the
`TrackingParticle` from `ClusterTPAssociation` with the branch the tracker hit channel
gives, and checks whether the two name the same truth particle.

## Calorimeter results

Per event, over about five events.

| Sample | Object | Objects | Hit completeness | Energy completeness | Purity | Best branch correct |
|---|---|---|---|---|---|---|
| TTbar | CaloParticle | 526 | 1.00 | 1.00 | 0.73 | 0.85 |
| TTbar | SimCluster | 1179 | 1.00 | 1.00 | 0.85 | 0.87 |
| ZMM | CaloParticle | 278 | 1.00 | 1.00 | 0.71 | not measured |
| ZMM | SimCluster | 609 | 1.00 | 1.00 | 0.85 | not measured |

Completeness is 1.00 throughout: a branch holds every hit of the legacy object, and all of
its energy. Purity is 0.71 to 0.85 because a branch is broader by construction. It keeps a
shower or a decay together where the legacy objects split it into several `SimCluster`s or
`CaloParticle`s. A tighter closure gives finer granularity when that is what the
measurement wants.

## Tracker results

| Sample | Reconstructed tracks | Matched on both sides | Same truth particle |
|---|---|---|---|
| ZMM | 210 | 210 | 99.5% |
| TTbar | 441 | 441 | 96.4% |
| SingleElectron | 6 | 6 | 100% |

Both sides match every reconstructed track, and 96% to 100% of the tracks point to the same
truth particle. The remaining few percent in TTbar are the dense-jet cases: delta rays,
nuclear interactions and merged tracks. There the `PSimHit`-based truth and the
`DigiSimLink`-based truth resolve to neighbouring particles. The standard associators face
the same ambiguity.

## Building the truth object you need

A branch is a view, so the truth object is defined at the point of use.

- **A `SimCluster`-like object**: `Branch(root, StableLeaves)` with `subgraphHits`, rooted
  at any particle and at any granularity.
- **A `CaloParticle`-like object**: the subtree of a primary particle. `visibleP4()` and the
  calorimeter `subgraphHits` need nothing further.
- **A `TrackingParticle`-like object**: the tracker `subgraphHits` of a particle.
  `BranchSelector` reproduces the `TrackingParticleSelector` cuts on momentum,
  pseudorapidity, charge and signal.
- **A cross-detector object**, which the legacy split cannot express: one branch carries
  both footprints, so the track truth and the shower truth of an electron are one
  navigable object.
- **A pileup-aware object**: `isFromPileup()` and `bunchCrossing()` let a consumer keep or
  drop truth per bunch crossing. See [Pileup](pileup.md).

The matching stays uniform. One `BranchHitAssociator` associates any reconstructed object
that implements `truthHits()` to its best branch or branches, in place of the bespoke
per-object associators.
