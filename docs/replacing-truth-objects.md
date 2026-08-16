# Replacing the legacy truth objects

`TrackingParticle`, `CaloParticle`, and `SimCluster` are the current truth
objects of CMS. They are useful, but they are **static and detector-specific**.
Each one is a frozen, pre-grouped collection built for one purpose. Together they
encode different, non-navigable views of the same event history. A
`truth::Branch` is a **navigable, recomputed-on-demand** view of one unified
graph. It reproduces what those objects deliver, and it removes their
limitations.

## Why a Branch is a better primitive

| | Legacy `TrackingParticle` / `CaloParticle` / `SimCluster` | `truth::Branch` |
|---|---|---|
| Construction | static, pre-grouped at digi/mixing time | derived on the fly from graph + closure |
| Navigation | none (flat object) | parents/children/ancestors/LCA, decay branches |
| Granularity | fixed | any closure (subtree, stable-leaves, depth-N, until-pdgId, predicate) |
| Detectors | per-detector (calo vs tracker truth separate) | one graph, calo **and** tracker hit channels |
| Provenance | limited | bunch crossing, signal/pileup, gen-event |
| Reco matching | bespoke associators per object | one generic `BranchHitAssociator` (any object with `truthHits()`) |
| Kinematics | stored | `p4`/visible/invisible computed from the branch |

We validated this claim: **for the purposes the legacy objects serve (hit content
and reco↔truth association), a Branch reproduces them**. The reference is the set
of existing associators. A Branch then offers strictly more: navigation,
closures, unified calo and tracker, provenance, and tagging.

## How the validation works

Two EDAnalyzers map each legacy object to its logical particle. The mapping goes
through `obj.g4Tracks().front().trackId()` into the trackId→logical-particle map.
The two analyzers then compare:

- **Calo** (`BranchTruthReplacementValidator`): it compares the `subgraphHits` of
  the Branch against the `hits_and_fractions()` of the object. It reports
  **completeness** (object hits covered by the Branch) and **purity** (Branch hits
  that are the object's). It also runs the `BranchHitAssociator`. It then checks
  that the tightest best-score branch is the mapped particle.
- **Tracker** (`BranchTrackerReplacementValidator`): for each reco track it
  compares the TrackingParticle from `ClusterTPAssociation` against the Branch
  from the tracker hit channel. It checks that both point to the **same truth
  particle**.

## Results

### Calorimeter: `CaloParticle` and `SimCluster` (per event, ~5 events)

| Sample | Object | N | hit-compl. | energy-compl. | purity | best-branch-correct |
|---|---|---|---|---|---|---|
| TTbar | CaloParticle | 526 | 1.00 | 1.00 | 0.73 | 0.85 |
| TTbar | SimCluster | 1179 | 1.00 | 1.00 | 0.85 | 0.87 |
| ZMM | CaloParticle | 278 | 1.00 | 1.00 | 0.71 | not measured |
| ZMM | SimCluster | 609 | 1.00 | 1.00 | 0.85 | not measured |

**Completeness is 1.0**: a Branch contains *all* of the legacy object's hits, and
all of its energy. Purity is 0.71 to 0.85, because a Branch is deliberately
**broader**. A Branch unifies a shower or decay that the legacy objects split
into several `SimCluster`s or `CaloParticle`s. That breadth is deliberate: the
Branch is the physically complete object. A tighter closure gives finer
granularity.

### Tracker: `TrackingParticle` (track→truth agreement)

| Sample | reco tracks | both matched | Branch-TP agreement |
|---|---|---|---|
| ZMM | 210 | 210 | **99.5%** |
| TTbar | 441 | 441 | **96.4%** |
| SingleElectron | 6 | 6 | **100%** |

Both sides match every reco track. Between 96% and 100% of the tracks point to
the same truth particle. The few-percent misses in TTbar are the expected
dense-jet cases (delta-rays, nuclear interactions, merged tracks). In those cases
the PSimHit-detUnit truth and the cluster-DigiSimLink truth resolve to adjacent
particles. The standard associators face the same ambiguity.

## Creating new and better truth objects

A Branch is a *view*, so you build the truth object you need at use time:

- **A SimCluster-like object**: `Branch(root, StableLeaves)` plus `subgraphHits`.
  You can root it at any particle, at any granularity.
- **A CaloParticle-like object**: the subtree of a primary. `visibleP4()` and the
  calo `subgraphHits` need no extra work.
- **A TrackingParticle-like object**: the tracker `subgraphHits` of a particle.
  `BranchSelector` reproduces the `TrackingParticleSelector` cuts
  (pt/eta/charge/signal).
- **Cross-detector objects** (impossible with the legacy split): one Branch
  carries both its calo and tracker footprint. The track truth *and* the shower
  truth of an electron are then one navigable object.
- **Pileup-aware objects**: `isFromPileup()` / `bunchCrossing()` let a consumer
  keep or drop pileup truth per bunch crossing (see [Pileup](pileup.md)).

The matching interface is uniform. One `BranchHitAssociator` associates any reco
object that implements `truthHits()` to the best branch or branches. It replaces
the bespoke per-object associators.
