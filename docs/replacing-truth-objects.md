# Replacing the legacy truth objects

`TrackingParticle`, `CaloParticle`, and `SimCluster` are CMS's current truth
objects. They are useful but **static and detector-specific**: each is a frozen,
pre-grouped collection built for one purpose, and they encode different,
non-navigable views of the same event history. A `truth::Branch` is a **navigable,
recomputed-on-demand** view of one unified graph — and it can reproduce what those
objects deliver while removing their limitations.

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

The claim we validated: **for the things the legacy objects are used for (hit
content and reco↔truth association), a Branch reproduces them** — using the
existing associators as the reference — and then offers strictly more (navigation,
closures, unified calo+tracker, provenance, tagging).

## How the validation works

Two EDAnalyzers map each legacy object to its logical particle (via
`obj.g4Tracks().front().trackId()` → the trackId→logical-particle map) and compare:

- **Calo** (`BranchTruthReplacementValidator`): the Branch's `subgraphHits` vs the
  object's `hits_and_fractions()` — **completeness** (object hits covered by the
  Branch) and **purity** (Branch hits that are the object's). Also runs the
  `BranchHitAssociator` and checks the tightest best-score branch is the mapped
  particle.
- **Tracker** (`BranchTrackerReplacementValidator`): for each reco track, the
  TrackingParticle from `ClusterTPAssociation` vs the Branch from the tracker hit
  channel; checks both point to the **same truth particle**.

## Results

### Calorimeter — `CaloParticle` and `SimCluster` (per event, ~5 events)

| Sample | Object | N | hit-compl. | energy-compl. | purity | best-branch-correct |
|---|---|---|---|---|---|---|
| TTbar | CaloParticle | 526 | 1.00 | 1.00 | 0.73 | 0.85 |
| TTbar | SimCluster | 1179 | 1.00 | 1.00 | 0.85 | 0.87 |
| ZMM | CaloParticle | 278 | 1.00 | 1.00 | 0.71 | — |
| ZMM | SimCluster | 609 | 1.00 | 1.00 | 0.85 | — |

**Completeness is 1.0**: a Branch contains *all* of the legacy object's hits (and
energy). Purity 0.71–0.85 because a Branch is deliberately **broader** — it unifies
a shower / decay that the legacy objects split into several `SimCluster`s /
`CaloParticle`s. That breadth is a feature: the Branch is the physically complete
object, and finer granularity is available by choosing a tighter closure.

### Tracker — `TrackingParticle` (track→truth agreement)

| Sample | reco tracks | both matched | Branch–TP agreement |
|---|---|---|---|
| ZMM | 210 | 210 | **99.5%** |
| TTbar | 441 | 441 | **96.4%** |
| SingleElectron | 6 | 6 | **100%** |

Every reco track is matched on both sides; 96–100% point to the same truth
particle. The few-percent misses in TTbar are the expected dense-jet cases
(delta-rays, nuclear interactions, merged tracks) where the PSimHit-detUnit truth
and the cluster-DigiSimLink truth resolve to adjacent particles — the same
ambiguity the standard associators face.

## Creating new and better truth objects

Because a Branch is a *view*, you build the truth object you need at use time:

- **A SimCluster-like object**: `Branch(root, StableLeaves)` + `subgraphHits` — but
  rooted at any particle, at any granularity.
- **A CaloParticle-like object**: the subtree of a primary; `visibleP4()` and the
  calo `subgraphHits` come for free.
- **A TrackingParticle-like object**: the tracker `subgraphHits` of a particle;
  `BranchSelector` reproduces the `TrackingParticleSelector` cuts (pt/eta/charge/signal).
- **Cross-detector objects** (impossible with the legacy split): one Branch carries
  both its calo and tracker footprint, so an electron's track *and* shower truth is
  one navigable object.
- **Pileup-aware objects**: `isFromPileup()` / `bunchCrossing()` let a consumer keep
  or drop pileup truth per bunch crossing (see [Pileup](pileup.md)).

The matching interface is uniform: any reco object that implements `truthHits()`
can be associated to the best branch(es) with one `BranchHitAssociator`, replacing
the per-object bespoke associators.
