# Pileup

## The starting point: the truth graph was signal-only

The truth producers read `g4SimHits` / `generatorSmeared`. Those collections are
**signal only** (bunch crossing 0). The pileup truth is elsewhere, and it is mostly
inaccessible:

- **Standard mixing:** pileup `SimTrack`s live in the **transient**
  `CrossingFrame<SimTrack>`. The digitizers consume that frame, and CMSSW never
  persists it; only `CrossingFramePlaybackInfoNew` survives. The only persisted
  pileup truth is the flat `mix:MergedTrackTruth` / `mix:MergedCaloTruth`.
- **Premixing:** the framework overlays pileup at digi level. Stage-2 exposes only
  `mixData:MergedTrackTruth`, and no pileup `SimTrack`/`SimVertex`/HepMC at all.

Quantified on a PU=2 sample: `g4SimHits` SimTracks are 100% bx=0, while
`mix:MergedTrackTruth` is 91% pileup (bx≠0). The data model was *ready* for pileup.
Every node carries an `EncodedEventId`, `Branch` exposes `isFromPileup`/
`bunchCrossing`, and the artificial vertex roles were designed for overlaid pileup.
Only the inputs never delivered the pileup.

## Two routes

### Phase A: `MixCollection` prototype

`TruthGraphMixedProducer` reads the `CrossingFrame<SimTrack/SimVertex>` through
`MixCollection`, keyed by `(EncodedEventId, localId)`. Crossing frames are
transient, so the producer must run **inside the DIGI step**. The
`addMixedTruthGraph` customise does this, and it enables the frames with
`setCrossingFrameOn`. The output keeps the compact mixed graph.

It validated the data model on real mixed pileup. Pileup is visible across the
whole bunch-crossing window. The signal is isolated at `(bx=0, event=0)`. Every
track has one production vertex, and there are no cycles. But **flattening the
`MixCollection` fragments the graph**. The local ids must be regrouped per
sub-event, and a small fraction do not re-resolve. This gives ~1017
components/event. That weakness motivated Route B.

### Phase B: `TruthGraphAccumulator` (the production route, in progress)

This is a `DigiAccumulatorMixMod`, like `TrackingTruthAccumulator`. The framework
feeds it one sub-event at a time with its **native** `SimTrack`/`SimVertex`/HepMC
collections. The ids therefore stay in their original local context: **no
flattening, no cross-pileup keying, no fragmentation**. It is identical for
standard mixing and premixing, and it is consistent with the digis by construction.

It is **configurable**:

| Parameter | Default | Meaning |
|---|---|---|
| `pileupBunchCrossings` | `{0}` | which bunch crossings to include for pileup (in-time only by default) |
| `collapsePileupGen` | `true` | for pileup, collapse the GEN chain to the stable particles on a single gen vertex, keep the SIM |
| `collapseSignalGen` | `false` | keep the signal's full graph (full signal GEN+SIM is the next step) |

The pileup default is exactly this: *all the stable particles connected to the same
gen vertex, collapse the gen, keep the sim*. There is one GEN vertex per pileup
interaction, and it carries all the stable (status-1) particles of that
interaction. It has `GenToSim` links to the SIM primaries, and the accumulator
keeps the SIM continuation.

## Results (PU=2, self-mixed TTbar, 3 events)

| Stage | bunch crossings | components/event | notes |
|---|---|---|---|
| Phase A (MixCollection) | −12 … +3 (all) | ~1017 | flatten+regroup fragments |
| B1 accumulator (SIM only) | bx 0 (filter) | ~47 | native per-sub-event linking (20× less) |
| B1 + collapsed pileup GEN | bx 0 | ~22 | gen vertex connects each interaction |

With the collapsed pileup GEN there are 5 pileup gen vertices over 3 events, with
~486 stable particles per vertex. `GenToSim` merged ~2180 of them into their SIM
primaries. `multiProdParticles=0`, there are no cycles, and the filter confines
pileup to bx 0. The `TruthGraphTopologyChecker` reports the full
signal-vs-pileup per-bunch-crossing breakdown used for these numbers.

!!! note "Self-mixing caveat"
    The PU input here is the TTbar signal itself. This gives a quick, controllable
    mechanism test without an external minbias library. The *counts* are therefore
    heavy and not physical. What is validated is the *mechanism*: provenance,
    bunch-crossing tagging and connectivity. Real minbias pileup is much lighter
    per interaction.

## Signal vs pileup: how it is meant to separate

The truth graph separates signal from pileup **by reachability**, not by a flag.
Its own artificial `Interaction` vertex summarizes each interaction (see the
[Interface reference](interface.md) and the [TenTau example](examples.md)). The
**packed `EncodedEventId`** keys those vertices, one node per pp collision. The
signal is therefore everything reachable from the signal Interaction vertex
(bunch crossing 0, event 0). Each pileup interaction (distinct `EncodedEventId`)
gets its own Interaction vertex. The `truth::Particle::eventId` of every node
carries the same provenance. This is exactly what the `TruthGraphTopologyChecker`
already decodes for its signal-vs-pileup per-bunch-crossing breakdown.

This works end to end. The accumulator stamps each node's `EncodedEventId`:
signal `(0,0)`, pileup `(bunch crossing, pileup index)`. The logical producer
copies it onto the SIM-bearing logical particle. It round-trips through the ROOT
dictionary, which we checked with FWLite. The `Interaction`-vertex keying then
turns the distinct ids into one Interaction vertex per interaction. We verified
this on a freshly mixed TTbar event with in-time pileup. The accumulator added the
signal plus the in-time pileup sub-events with four distinct `EncodedEventId`s. The
logical graph then reported `signalParticles = 27611`, `pileupParticles = 20616`.
The split is clean, and it needs no graph changes.

The figure below is a muon-seeded view of that mixed graph
(`seedPdgIds = {13, -13}`, `dropHitlessSimSubgraphs = false`). The **blue** subgraph
descends from the signal Interaction vertex (`eid 0`). The **red** subgraph descends
from the in-time pileup interaction (`eid 1`). Signal against pileup is only a
question of which Interaction vertex you reach.

![Signal (blue) vs pile-up (red): two Interaction vertices keyed by EncodedEventId](img/pileup_signal_vs_pileup.svg)

Two practical notes:

- **You must turn off the detectable-truth pruning** for the mixed graph
  (`dropHitlessSimSubgraphs = false`). Pileup sim-hits live in the transient
  `CrossingFrame`, not in the signal `g4SimHits` collections that the producer
  reads. The pruning would otherwise drop the pileup as "hitless".
- **You must produce the mixed sample with current code.** An older
  `test/pu_probe/step2_acc.root` predated the working provenance and read back
  signal-only (all `eventId == 0`). We regenerated it from a clean build
  (full DIGI + in-time pileup, 3 events). It now carries the provenance:
  `signalParticles = 69549`, `pileupParticles = 269076` across the three events.

## Production flow: build at DIGI, consume at RECO

In a split production (GEN-SIM, DIGI-RAW, RECO, Validation as separate jobs) the
code builds the mixed truth **once, at the mixing/DIGI step**. At that step the
merged signal+pileup sim-hits are live. Every later step consumes the result.
`mixedTruthGraphCustomize.customiseTruthDigi` does this:

1. it registers the `TruthGraphAccumulator` (the merged raw `TruthGraph_mix`);
2. it builds the logical graph and the per-particle per-cell **hit index** right
   after mixing (`buildCompactTruthAtDigi`), reading the accumulator's merged
   sim-hits. The default scope is the full detector (Calo + Tracker + Muon; the MTD
   channel is resolved at RECO). `customiseTruthReduced` drops the Tracker channel
   for cost-sensitive runs, and leaves calo + MTD + muon;
3. it applies an event-content level.

The code builds the hit index **unresolved** (`recHitMap = ""`, so `recHitIndex`
stays invalid). This is deliberate. The shared-energy association
(`truth::BranchHitAssociator`) matches reco objects to branches **by `DetId`**, not
by `recHitIndex`. It also keys the per-cell total-sim-energy denominator on
`DetId`. The same unresolved index therefore serves every later stage that exposes
its reco objects as `(DetId, fraction)` (L1, HLT, offline RECO). The bulky merged
sim-hits never have to cross the DIGI→RECO boundary. MTD is left out of the DIGI
index, because its channel needs the reco Mtd cluster associations, which are
RECO-stage products.

At RECO, `customiseTruthMixedReco.customise` drops the signal-only rebuild that
`enableTruth` would otherwise schedule. The branch validators and association
producers therefore resolve to the DIGI-built mixed products. It also repoints the
`rawSrc` of the validators to `TruthGraph_mix`, and it persists the truth. RECO
needs no rebuild and no sim-hits.

### Event content: `compact` vs `full`

`truthEventContent_cff` defines two verbosity levels (`setTruthEventContent`):

| Level | Keeps | Serves |
|---|---|---|
| `compact` (default) | logical graph + **unresolved** hit index + raw `TruthGraph_mix` | correct hits-and-fractions shared energy at any stage whose rechits share the cell-level `DetId` space (HLT, offline RECO) |
| `full` | compact + the merged sim-hits of every in-scope channel | re-association at a **different granularity** (e.g. L1 trigger cells) or with a different metric, from the raw deposits |

**Denominator invariant:** the fraction denominator is the sum of the index hit
energies over *all* particles in a cell. The persisted index must therefore stay
complete: every hit-leaving contributor, no pdgId pruning. Pruning the index biases
every fraction high. Do not shrink the index without also persisting a separate
all-contributor per-cell total map.

### Default for Run4, not a special workflow

The whole chain is wired under the **`enableTruth` modifier**. `enableTruth` is
added to the **`Phase2C17I13M9` era**, the common, HGCal-geometry-agnostic Phase-2
base. Truth is therefore on by default for Run4, with no special workflow.
`Phase2C20I13M9` (hfnose), `Phase2C22I13M9` (HGCal V18), `Phase2C26I13M9` (V19) and
the `noMkFit` variants all inherit it, as does any future geometry era layered on
C17:

- `digitizers_cfi` registers the `TruthGraphAccumulator` in the mixing digitizers;
- `Digi_cff` builds the logical graph + unresolved hit index right after mixing;
- `EventContent` keeps the compact truth in FEVTDEBUGHLT and RECOSIM;
- `truthGraphValidation_cff` / `globalValidation_cff` consume the DIGI-built graph
  at RECO, with associators and validators that use `rawSrc=mix`. They deliberately
  do NOT import the signal-only build producers, which would attach at RECO and
  shadow the DIGI-built products.

**Excluded where it cannot work:** FastSim drops the `enableTruth` modifier itself.
`Util_fastSimPhase2_cff` excludes it from every FastSim era, because there are no
full-sim `g4SimHits`. Premixing keeps the modifier, because it comes from the era.
Premixing instead drops the pieces that cannot run. Premixed pileup carries no raw
pileup `SimTrack`s. `digitizers_cfi` therefore removes the accumulator, and
`Digi_cff` reverts to the truth-free `pdigiTask`. The validation and harvesting
sequences revert to their truth-free form, so nothing consumes products that were
never built. Phase-2 uses classic mixing, which is what the accumulator needs:
mixing overlays and captures the raw pileup `g4SimHits`.

**No special pileup sample is needed:** `ReconnectDroppedAncestors` is now an
unconditional GEN-SIM default, and `enableTruth` no longer gates it. Any Run4
MinBias library therefore already carries the well-formed SimTrack/SimVertex
connectivity that the pileup truth graph relies on. You reach the truth-off A/B
baseline by using a non-`enableTruth` era. The only GEN-SIM difference
(`ReconnectDroppedAncestors`) is detector-neutral, so the reco stays comparable.

We verified the full build→persist→consume→validate→harvest chain end to end on a
no-PU gun sample. The `BranchHGCalValidator`
efficiency/completeness/purity/response plots come from the DIGI-built truth. The
change is config-generation and single-event-runtime validated on D122/V19. The
full-detector truth builds, persists and reads back. The code writes the logical
graph, the unresolved hit index and `TruthGraph_mix`. The Calo channel carries
HGCAL, ECAL barrel and HCAL. Full relval plus IB validation is the next step.

## What remains

See the [Roadmap](roadmap.md) for the remaining work. It covers full GEN+SIM for
the signal, which means factoring the producer build. It also covers
premix-library storage of the minbias graph (B3), and a CPfromPU-style
simplification for PU200 storage (B4). The code builds the mixed hit index (B2) at
DIGI, as described above.
