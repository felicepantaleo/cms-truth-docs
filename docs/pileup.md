# Pileup

## The starting point: the graph was signal-only

The truth producers read `g4SimHits` / `generatorSmeared`, which are **signal
only** (bunch crossing 0). Pileup truth is elsewhere and mostly inaccessible:

- **Standard mixing:** pileup `SimTrack`s live in the **transient**
  `CrossingFrame<SimTrack>` — consumed by digitizers, never persisted (only
  `CrossingFramePlaybackInfoNew` survives). The only persisted pileup truth is the
  flat `mix:MergedTrackTruth` / `mix:MergedCaloTruth`.
- **Premixing:** pileup is overlaid at digi level; stage-2 exposes only
  `mixData:MergedTrackTruth` — no pileup `SimTrack`/`SimVertex`/HepMC at all.

Quantified on a PU=2 sample: `g4SimHits` SimTracks are 100% bx=0, while
`mix:MergedTrackTruth` is 91% pileup (bx≠0). The data model was *ready* for pileup
(every node carries an `EncodedEventId`; `Branch` exposes `isFromPileup`/
`bunchCrossing`; the artificial vertex roles were designed for overlaid pileup) —
the inputs just never delivered it.

## Two routes

### Phase A — `MixCollection` prototype

`TruthGraphMixedProducer` reads the `CrossingFrame<SimTrack/SimVertex>` via
`MixCollection`, keyed by `(EncodedEventId, localId)`. Because crossing frames are
transient, it must run **inside the DIGI step** (via the `addMixedTruthGraph`
customise, which enables the frames with `setCrossingFrameOn`); the compact mixed
graph is kept in the output.

It validated the data model on real mixed pileup — pileup visible across the whole
bunch-crossing window, signal isolated at `(bx=0, event=0)`, every track one
production vertex, no cycles — but **flattening the `MixCollection` fragments the
graph** (the local ids must be regrouped per sub-event, and a small fraction don't
re-resolve), giving ~1017 components/event. That weakness motivated Route B.

### Phase B — `TruthGraphAccumulator` (the production route, in progress)

A `DigiAccumulatorMixMod` (like `TrackingTruthAccumulator`). The framework feeds it
one sub-event at a time with its **native** `SimTrack`/`SimVertex`/HepMC
collections, so ids stay in their original local context — **no flattening, no
cross-pileup keying, no fragmentation**. It is identical for standard mixing and
premixing, and consistent with the digis by construction.

It is **configurable**:

| Parameter | Default | Meaning |
|---|---|---|
| `pileupBunchCrossings` | `{0}` | which bunch crossings to include for pileup (in-time only by default) |
| `collapsePileupGen` | `true` | for pileup, collapse the GEN chain to the stable particles on a single gen vertex, keep the SIM |
| `collapseSignalGen` | `false` | keep the signal's full graph (full signal GEN+SIM is the next step) |

The pileup default is exactly *"all the stable particles connected to the same gen
vertex — collapse the gen, keep the sim"*: one GEN vertex per pileup interaction
carrying all its stable (status-1) particles, with `GenToSim` links to the SIM
primaries and the SIM continuation kept.

## Results (PU=2, self-mixed TTbar, 3 events)

| Stage | bunch crossings | components/event | notes |
|---|---|---|---|
| Phase A (MixCollection) | −12 … +3 (all) | ~1017 | flatten+regroup fragments |
| B1 accumulator (SIM only) | bx 0 (filter) | ~47 | native per-sub-event linking (20× less) |
| B1 + collapsed pileup GEN | bx 0 | ~22 | gen vertex connects each interaction |

With the collapsed pileup GEN: 5 pileup gen vertices over 3 events, ~486 stable
particles per vertex, `GenToSim` merged ~2180 of them into their SIM primaries;
`multiProdParticles=0`, no cycles, pileup confined to bx 0 (the filter). The
`TruthGraphTopologyChecker` reports the full signal-vs-pileup per-bunch-crossing
breakdown used for these numbers.

!!! note "Self-mixing caveat"
    The PU input here is the TTbar signal itself (a quick, controllable mechanism
    test without an external minbias library), so the *counts* are heavy and not
    physical; the *mechanism* — provenance, bunch-crossing tagging, connectivity —
    is what is validated. Real minbias pileup is much lighter per interaction.

## Signal vs pile-up: how it is meant to separate

The truth graph separates signal from pile-up **by reachability**, not by a flag:
each interaction is summarized by its own artificial `Interaction` vertex (see the
[Interface reference](interface.md) and the [TenTau example](examples.md)), and
those vertices are keyed by the **packed `EncodedEventId`** — one node per pp
collision. So the signal is everything reachable from the signal Interaction vertex
(bunch crossing 0, event 0), and each pile-up interaction (distinct `EncodedEventId`)
gets its own Interaction vertex. The `truth::Particle::eventId` of every node carries
the same provenance, exactly what the `TruthGraphTopologyChecker` already decodes for
its signal-vs-pile-up per-bunch-crossing breakdown.

This works end to end. The accumulator stamps each node's `EncodedEventId`
(signal `(0,0)`, pile-up `(bunch crossing, pile-up index)`); the logical producer
copies it onto the SIM-bearing logical particle; it round-trips through the ROOT
dictionary (checked with FWLite); and the `Interaction`-vertex keying turns the
distinct ids into one Interaction vertex per interaction. Verified on a freshly
mixed TTbar event with in-time pile-up: the accumulator added the signal plus the
in-time pile-up sub-events with four distinct `EncodedEventId`s, and the logical
graph then reported `signalParticles = 27611`, `pileupParticles = 20616` — a clean
split, no graph changes needed.

The figure below is a muon-seeded view of that mixed graph
(`seedPdgIds = {13, -13}`, `dropHitlessSimSubgraphs = false`): the **blue** subgraph
descends from the signal Interaction vertex (`eid 0`), the **red** one from the
in-time pile-up interaction (`eid 1`). Signal vs pile-up is just "which Interaction
vertex do you reach".

![Signal (blue) vs pile-up (red): two Interaction vertices keyed by EncodedEventId](img/pileup_signal_vs_pileup.svg)

Two practical notes:

- **The detectable-truth pruning must be turned off** for the mixed graph
  (`dropHitlessSimSubgraphs = false`): pile-up sim-hits live in the transient
  `CrossingFrame`, not in the signal `g4SimHits` collections the producer reads, so
  the pruning would otherwise drop the pile-up as "hitless".
- **The mixed sample must be produced with current code.** An older
  `test/pu_probe/step2_acc.root` predated the working provenance and read back
  signal-only (all `eventId == 0`). It has been regenerated from a clean build
  (full DIGI + in-time pile-up, 3 events) and now carries the provenance:
  `signalParticles = 69549`, `pileupParticles = 269076` across the three events.

## Production flow: build at DIGI, consume at RECO

For a split production (GEN-SIM, DIGI-RAW, RECO, Validation as separate jobs) the
mixed truth is built **once, at the mixing/DIGI step**, where the merged
signal+pileup sim-hits are live, and every later step consumes it. This is what
`mixedTruthGraphCustomize.customiseTruthDigi` does:

1. registers the `TruthGraphAccumulator` (the merged raw `TruthGraph_mix`);
2. builds the logical graph and the per-particle per-cell **hit index** right after
   mixing (`buildCompactTruthAtDigi`), reading the accumulator's merged calo
   (and, under `includeTrackingHits`, tracker/muon) sim-hits;
3. applies an event-content level.

The hit index is built **unresolved** (`recHitMap = ""`, so `recHitIndex` stays
invalid). This is deliberate: the shared-energy association
(`truth::BranchHitAssociator`) matches reco objects to branches **by `DetId`**, not
by `recHitIndex`, and it keys the per-cell total-sim-energy denominator on `DetId`
too. The same unresolved index therefore serves every later stage that exposes its
reco objects as `(DetId, fraction)` (L1, HLT, offline RECO), and the bulky merged
sim-hits never have to cross the DIGI→RECO boundary. (MTD is left out of the DIGI
index: its channel needs the reco Mtd cluster associations, which are RECO-stage
products.)

At RECO, `customiseTruthMixedReco.customise` drops the signal-only rebuild that
`enableTruth` would otherwise schedule, so the branch validators and association
producers resolve to the DIGI-built mixed products; it repoints the validators'
`rawSrc` to `TruthGraph_mix`; and it persists the truth. No rebuild and no sim-hits
are needed at RECO.

### Event content: `compact` vs `full`

`truthEventContent_cff` defines two verbosity levels (`setTruthEventContent`):

| Level | Keeps | Serves |
|---|---|---|
| `compact` (default) | logical graph + **unresolved** hit index + raw `TruthGraph_mix` | correct hits-and-fractions shared energy at any stage whose rechits share the cell-level `DetId` space (HLT, offline RECO) |
| `full` | compact + merged sim-hits (calo, plus tracking under `includeTrackingHits`) | re-association at a **different granularity** (e.g. L1 trigger cells) or with a different metric, from the raw deposits |

**Denominator invariant:** the fraction denominator is the sum of the index hit
energies over *all* particles in a cell, so the persisted index must stay complete
(every hit-leaving contributor, no pdgId pruning); pruning it biases every fraction
high. Do not shrink the index without also persisting a separate all-contributor
per-cell total map.

### Default for Run4, not a special workflow

The whole chain is wired under the **`enableTruth` modifier**, and `enableTruth` is
added to the **`Phase2C22I13M9` era**, so truth is on by default for Run4 with no
special workflow (`Phase2C26I13M9` and the `noMkFit` variants inherit it through the
C22 chain):

- `digitizers_cfi` registers the `TruthGraphAccumulator` in the mixing digitizers;
- `Digi_cff` builds the logical graph + unresolved hit index right after mixing;
- `EventContent` keeps the compact truth in FEVTDEBUGHLT and RECOSIM;
- `truthGraphValidation_cff` / `globalValidation_cff` consume the DIGI-built graph at
  RECO (associators + validators with `rawSrc=mix`), and deliberately do NOT import
  the signal-only build producers, which would attach at RECO and shadow the
  DIGI-built products.

**Excluded where it cannot work:** `premix_stage2` (premixed pileup carries no raw PU
`SimTrack`s) and FastSim (no full-sim `g4SimHits`) both drop `enableTruth`. Phase-2
uses classic mixing, which is what the accumulator needs: the raw pileup `g4SimHits`
are overlaid and captured during mixing.

**The one central-sample requirement:** because it is default on all Run4 PU, the
Run4 MinBias pileup library should itself be produced with `enableTruth`, so the
`ReconnectDroppedAncestors` connectivity keeps the pileup SimTrack/SimVertex graph
well formed. The stock MinBias still works, just with poorer pileup subgraphs. The
truth-off A/B baseline is reachable by using a non-`enableTruth` era
(`ReconnectDroppedAncestors` is detector-neutral, so the reco stays comparable).

The full build→persist→consume→validate→harvest chain is verified end to end on a
no-PU gun sample: the `BranchHGCalValidator` efficiency/completeness/purity/response
plots are produced from the DIGI-built truth. The change is config-generation
validated (accumulator, build and keeps appear via the era; RECO consumes; premix and
FastSim exclude it); runtime and relval validation is the next step.

## What remains

See the [Roadmap](roadmap.md): full GEN+SIM for the signal (factor the producer
build), premix-library storage of the minbias graph (B3), and a CPfromPU-style
simplification for PU200 storage (B4). The mixed hit index (B2) is built at DIGI as
described above.
