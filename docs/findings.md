# Findings & changes

Building the truth graph showed several non-obvious behaviors in the existing CMS
truth machinery. This page records what we found and what we changed. The
`enableTruth` modifier gates all the changes.

## 1. Orphan SimVertices: generator-history retention

**Discovered:** with default simulation, the truth graph had components
disconnected from the generator. The root cause is in Geant4. Geant4 keeps the
full track/vertex history only above `TrackingAction.PersistencyEmin`. The
default is **50 GeV** in the `common_MCtruth` PSet. Below that value, Geant4
drops the intermediate `SimTrack`s. A stored low-energy `SimVertex` can then lose
its parent branch, which gives an orphan component.

### How `PersistencyEmin` actually works

The value is a **kinetic-energy threshold**. It comes from
`SimG4Core/Application/python/g4SimHits_cfi.py`:

```python
PersistencyEmin = cms.double(50.0), # in GeV
```

`Phase2TrackingAction.cc` converts the value to Geant4 internal units and stores
it as `ekinMin_`:

```cpp
ekinMin_(p.getParameter<double>("PersistencyEmin") * CLHEP::GeV),   // = 50 GeV
```

**Where it applies: once per Geant4 track, at track start.** The code is in
`Phase2TrackingAction::PreUserTrackingAction`:

```cpp
double ekin = aTrack->GetKineticEnergy();          // KE at the track's creation vertex
...
if (nullptr != trkInfo_ && ekin > ekinMin_) {
  trkInfo_->putInHistory();                         // mark "keep in history"
}
```

`putInHistory()` only sets `isInHistory_ = true` (`TrackInformation.h`). The
threshold therefore does one thing directly: *if a track is created with
KE > 50 GeV, flag it "in history."* Nothing else reads `ekinMin_`. The cut uses
the **kinetic energy at the creation vertex**. It does not use total energy, and
it does not use momentum. A slow heavy particle can have a KE far below its total
energy. The 50 GeV cut is therefore even more aggressive than it looks.

**What "in history" controls.** At track end, `PostUserTrackingAction` passes the
flag to the manager. The manager discards at once every track that is *not* in
history:

```cpp
trackManager_->addTrack(currentHistory_, aTrack, isInHistory, withAncestor);
...
if (!isInHistory) { delete currentHistory_; }       // not in history -> dropped immediately
```

In `SimTrackManager::addTrack`, **only in-history tracks enter `m_trackContainer`**.
That container is the searchable pool of tracks that CMSSW can persist later, and
that can serve as a *parent link*:

```cpp
if (inHistory) {
  ...
  m_trackContainer.push_back(iTrack);
}
```

Two paths set `isInHistory` to true:

- `putInHistory()` → KE > 50 GeV (the `PersistencyEmin` path), **or**
- `storeTrack()` → the track is needed on its own account. It has SimHits, or it
  is a primary, or it crossed the Tracker→CALO boundary, or it is a required
  ancestor. `storeTrack()` also sets `isInHistory_ = true`.

**Why the chain reconstruction needs it.** At the end of the event,
`storeTracks()` walks **up the parent chain** for every track that must be saved.
It uses `saveTrackAndItsBranch`:

```cpp
trkH->setToBeSaved();
int parent = trkH->parentID();
auto tk_itr = std::lower_bound(m_trackContainer.begin(), m_trackContainer.end(), parent, ...);
if (tk_itr != end && (*tk_itr)->trackID() == parent)
  saveTrackAndItsBranch(*tk_itr);   // recurse to the grandparent, etc.
```

The code finds the parent **only by searching `m_trackContainer`**. An
intermediate ancestor that was *not* in history (sub-50-GeV and with no hits of
its own) was already `delete`d and is absent. So `lower_bound` misses and the
recursion stops. **The branch is severed at the first dropped intermediate.**
The persisted secondary then gets its parent set to `idLastStoredAncestor()`.
This jumps over the dropped intermediates to the nearest surviving ancestor. If
no ancestor survives, its production `SimVertex` ends up with `parentIndex = -1`.
The vertex then looks like a fresh primary, which is the orphan component.

**What "50 GeV" means.** A track stays in the persistable history for ancestry
alone only if it was born with more than 50 GeV of kinetic energy. Otherwise it
stays only if it qualifies for persistence another way (hits, boundary crossing,
primary, needed ancestor). 50 GeV is a deliberately high cut. In a hadronic/EM
cascade or a τ-decay chain almost every intermediate is well below it. Geant4
therefore drops the intermediate tracks that link two genuinely-stored tracks.
The truth graph then loses the edges that link SIM back to GEN.

**Change:** the baseline `g4SimHits` configuration keeps `PersistencyEmin` at its
default **50 GeV**. It sets
`g4SimHits.TrackingAction.ReconnectDroppedAncestors = True` instead. When a
stored track's immediate parent was dropped, the code reattaches its production
vertex to the **nearest stored ancestor**. It finds that ancestor by walking the
full `trackID → parentID` topology. Geant4 retains that topology for *every* track
(in `idsave`, captured per event in `addTrack`), and the walk always ends at the
always-stored primary. `SimVertex::parentIndex` can therefore never be −1.

This replaced the original `PersistencyEmin = 0`. That setting keeps a mother
whenever any daughter is kept. `ekin > ekinMin_` is true for every track, so every
`TrackWithHistory` survives and `saveTrackAndItsBranch` always finds the real
mother. The cost is that it persists *every* intermediate. The reconnect has its
own cost: it **collapses** the dropped intermediate nodes. The reattached edge is
a shortcut to the nearest survivor. A sub-threshold π⁰→γγ therefore no longer
appears as a distinct node, and its two photons attach to the π⁰'s parent.

**Result:** exactly **one connected component per event** (no orphan fragments)
across all eight validation samples. The connectivity is identical to
`PersistencyEmin = 0`, with a much smaller collection. Measured on
TTbar+Run4D120 (2 events): 50 GeV alone gives **15286** orphan fragments; with the
flag it gives **0** (one component/event). Stored SimTracks are **12021** (flag)
against **33941** (`PersistencyEmin = 0`). That is a **~65% smaller** collection
for the same connectivity. See [Validation](validation.md).

### 50 GeV breaks the history only without the reconnect

`PersistencyEmin` is a **simulation-time** decision. It governs which `SimTrack`s
and `SimVertex`es Geant4 writes. The truth-graph producers run downstream at RECO.
They cannot recover a track that Geant4 never stored. A `step3.root` made from a
*plain* 50 GeV SIM is therefore fragmented, and no RECO-side setting recovers it.
The fix has to be at GEN-SIM. The *topology* is never lost: Geant4 keeps the full
`trackID → parentID` map for **every** track, whatever the threshold.
`ReconnectDroppedAncestors` uses that map at SIM time. It walks the map to the
nearest stored ancestor and reattaches the production vertex there. This is why
`enableTruth` can stay at 50 GeV and still be orphan-free. A bare 50 GeV does
break the history, **but the reconnect avoids it without lowering the threshold**.
The reconnect collapses the intermediate nodes and gives a SimTrack collection
~2.7× smaller than `PersistencyEmin = 0`.

### Limitation: calo SimHits are conserved, tracker SimHits are not

The reconnect fixes the graph **topology** (no orphan vertices). The sensitive
detectors govern hit **attribution** separately. The calorimeter SD and the
tracker SD behave differently.

- **Calorimeter: conserved.** `CaloSD` reassigns a dropped track's `PCaloHit`s to
  the nearest stored ancestor (`SimTrackManager::giveMotherNeeded`). Every calo
  hit therefore lands on a stored track, which is a track in the truth graph. The
  hit index then sums the per-detId energies on the owning particle
  (`coalesce()`). Measured on TTbar+Run4D120: **375228 calo hits attributed, 0
  lost**. The result is identical under `PersistencyEmin = 0` and under 50 GeV
  plus reconnect.
- **Tracker: partially lost.** `TkAccumulatingSensitiveDetector` does **not**
  reassign hit trackIds. A `PSimHit` on a dropped (sub-threshold) track therefore
  keeps a `trackId` that resolves to no SimTrack. It matches no logical particle,
  and the code drops it. The loss is **pre-existing**: ≈7% of real-trackId
  tracker hits are lost even at `PersistencyEmin = 0`. The code prunes tracks with
  no saved branch in either case. The high-`PersistencyEmin` reconnect widens the
  loss to ≈12%.

The tracker loss is **not recoverable downstream**, because the dropped track has
no SimTrack/SimVertex record at RECO. We tried a RECO-side reassignment of
unmatched hits to the nearest logical particle. It recovers **nothing**. The
hitless-SIM pruning already guarantees that every hit-carrying *stored* track is a
logical particle. There are therefore no "subsumed-with-hits" tracks to reattach,
and the only unmatched hits are on tracks that were truly dropped. To close the
loss we would need a **SIM-time** change to the tracker SD, which would reassign
hits like `CaloSD`. That change alters the standard tracker `PSimHit` collection
that `TrackingParticle` and other consumers rely on. It is a separate and broader
change. For the truth graph the calo channel is exact, and it holds most of the
deposited energy. The tracker channel under-counts soft-secondary hits. This is
the same reason why standard tracking truth uses the history-aware accumulation of
`TrackingParticle` rather than raw SimHit-`trackId` matching.

## 2. The GEN/SIM vertex mega-vertex and DAG cycles

**Discovered (logical graph only; the raw graph was always clean):** the logical
graph had a **giant merged vertex** and **DAG cycles**. This happened in every
sample with prompt activity at the primary. That vertex had an out-degree up to
~900 and hundreds of incoming edges.

**Root cause:** the post-processor merged GEN-only and SIM-only vertices by
spatial proximity (`mergeGenSimVerticesByPosition`, tolerance 5·10⁻³). Near the
primary, PYTHIA writes many *distinct* vertices (hard scatter, shower,
hadronization, prompt decays) within microns of (0,0,0). Geant4 has a *single*
beam vertex there. The situation is therefore **many-GEN-to-one-SIM**. The
union-find then collapsed the whole origin cluster transitively into one node. A
prompt particle whose production and decay both landed in that node produced a
`V→P→V` 2-cycle.

**Why position cannot fix it:** position cannot distinguish two cases. The first
is "a GEN vertex and its SIM counterpart", which should merge. The second is "two
distinct GEN vertices both near the origin", which must not merge.

**Change:** delete `mergeGenSimVerticesByPosition`. A merged GEN+SIM particle now
takes its production vertex from its **immediate GEN production vertex**, through
the faithful `genpartIndex` link. The producer drops the redundant SimTrack
production edge to the shared beam vertex.

**Result (per sample, 5 events):**

| | logical vtx out-degree (max) | particle parent-count (max) | cycles/event |
|---|---|---|---|
| Before (position merge) | 666 to 936 | 335 to 457 | 5/5 |
| After (immediate-GEN attach) | 51 to 104 (physical hadronization scale) | 30 to 61 | 0 |

`multiProdParticles=0`, one component/event, no cycles. The logical degree
distributions now match the raw *physical* maxima. See [Validation](validation.md).

## 3. `genpartIndex` is ancestor-collapsed (do not back-fill)

**Discovered while planning the fix above:** `SimTrack::genpartIndex()` is **not**
reliably the immediate GEN parent. For non-primary tracks,
`SimTrackManager.cc` sets it to `idLastStoredAncestor()`, and `MCTruthUtil`
inherits `mcTruthID` from the mother. Both paths collapse to the nearest *stored*
ancestor, up to the root, and drop the intermediate GenVertices.

**Consequence / guard:** the GEN↔SIM association must use `genpartIndex` only for
`simTrack.isPrimary()` tracks. For those tracks it *is* the immediate HepMC
barcode, which `Generator::setGenId(barcode)` sets for the whole
pre-assigned-decay cascade. `TruthGraphProducer` already enforces this. The
simulation captures the immediate link on the fly, so it does **not** need a new
product.

## 4. Pileup is invisible to the signal-only graph

**Discovered:** the truth producers read `g4SimHits` / `generatorSmeared` =
**signal only** (bx=0). Pileup `SimTrack`s live in the **transient**
`CrossingFrame<SimTrack>`. The digitizers consume that frame, and CMSSW never
persists it; only `CrossingFramePlaybackInfoNew` survives. The only persisted
pileup truth is the flat `mix:MergedTrackTruth` / `mix:MergedCaloTruth`. Premixing
exposes even less: only the digi-level `mixData:MergedTrackTruth`.

**Quantified** (PU=2, standard mixing): `g4SimHits` SimTracks = 100% bx=0;
`mix:MergedTrackTruth` = 91% pileup (bx≠0). The truth graph saw none of the
pileup.

**Change:** add pileup support. See the [Pileup](pileup.md) page for the Phase A
prototype and the Phase-B `DigiAccumulator`, which is configurable and uses
in-time pileup by default.

## 5. Cross-release dataformat incompatibility (CMSSW_17 → CMSSW_20)

**Discovered while re-validating the rebase:** CMSSW_20 cannot open a CMSSW_17
`step3.root`. The cause is a ROOT streamer-checksum change on
`edm::Wrapper<HcalDataFrameContainer<QIE10DataFrame>>`, because CMSSW_20 uses
`io_v1::` versioned dataformats. A cross-release comparison must therefore be a
full relval re-run, not a same-input shortcut. We validated the rebase by
re-running all eight workflows on CMSSW_20. The invariants are identical
(cycles/multiProd/orphans all 0), and the mean graph degrees agree within ~1.5%.
The differences are confined to the expected cross-release simulation RNG. See
[Validation](validation.md).

## 6. Jets without a clustering algorithm, and what the overlap costs

You can define a parton-initiated jet with no clustering at all. Everything
downstream of a hard-scatter quark or gluon is one jet, and the flavour is the
parton's own PDG id (`partonJets` level). This works because `collapseGenShower`
deletes every shower parton at graph build. A parton therefore survives only by
carrying `isHardProcess`: "the early quark" and "the quark that is present" are
the same particle. The deepest-element antichain rule resolves the top-versus-b
nesting by itself. It keeps the b, which is also the physics.

Measured on 200 no-PU ttbar events: 4.80 jets per event. The flavour split is
d 137, u 133, s 143, c 147, b 400, so the b bin is exactly twice the event count.
On QCD flat pT the result is exactly 2.00 per event, 67% gluon. There
`partonJets` coincides with `hardProcess` bin for bin, because every QCD
hard-scatter leg is a parton. On ttbar the two differ by exactly the 186 leptonic
legs. Read jet efficiency CUMULATIVELY: a jet is many reco objects, never one.

The cost of skipping the clustering step is measured, not hypothetical. The jet
ROOTS are an antichain, but the SUBGRAPHS overlap. The u and d~ of a hadronic W
are colour connected and fragment through one string, so its hadrons descend from
both. That gives 1221 of 8096 hits, 15% of the union, shared between exactly that
one pair. The b and b~ share nothing, and a dileptonic event shares 0. Assigning
each hadron to exactly one jet is exactly what a clustering algorithm does, and
this number is the case for adding one.

## 7. What discarding the generator record costs others

A secondary-vertex validation built on the legacy truth (cms-sw/cmssw#51577) gives
the contrast case for the truth-graph design. The generator handles B and D
hadrons, and they never become TrackingParticles. Only their stable descendants
do. Identifying the mother of a secondary vertex there therefore takes a four-case
algorithm. That algorithm ends in an HepMC tree climb with a 10-micron
merge-radius test. On the truth graph the same question is
`hadronHasQuark(pdgId, 5)` plus an antichain, because the B hadron IS a node. The
comparison shows the cost of freezing truth into flat objects, measured in code
someone had to write.
