# Findings & changes

Building the graph surfaced several non-obvious behaviors in the existing CMS
truth machinery. This page documents what we discovered and what we changed (all
changes gated behind `enableTruth`).

## 1. Orphan SimVertices — generator-history retention

**Discovered:** with default simulation, the truth graph had components
disconnected from the generator. Root cause: Geant4 keeps the full track/vertex
history only above `TrackingAction.PersistencyEmin` (default **50 GeV** in the
`common_MCtruth` PSet). Below it, intermediate `SimTrack`s are dropped, so a
stored low-energy `SimVertex` can lose its parent branch → an orphan component.

**Change:** `enableTruth` sets `g4SimHits.TrackingAction.PersistencyEmin = 0` in
the SIM step, so every stored `SimTrack` keeps its full ancestor branch.

**Result:** exactly **one connected component per event** across all eight
validation samples (no orphan fragments). See [Validation](validation.md).

## 2. The GEN/SIM vertex mega-vertex and DAG cycles

**Discovered (logical graph only; the raw graph was always clean):** in every
sample with prompt activity at the primary, the logical graph had a **giant merged
vertex** (out-degree up to ~900, hundreds of incoming) and **DAG cycles**.

**Root cause:** the post-processor merged GEN-only and SIM-only vertices by spatial
proximity (`mergeGenSimVerticesByPosition`, tolerance 5·10⁻³). Near the primary,
PYTHIA writes many *distinct* vertices (hard scatter, shower, hadronization, prompt
decays) within microns of (0,0,0) while Geant4 has a *single* beam vertex — a
fundamentally **many-GEN-to-one-SIM** situation. The union-find then transitively
collapsed the whole origin cluster into one node, and a prompt particle whose
production and decay both landed in it produced a `V→P→V` 2-cycle.

**Why position can't fix it:** it cannot tell "a GEN vertex and its SIM
counterpart" (should merge) from "two distinct GEN vertices both near the origin"
(must not).

**Change:** delete `mergeGenSimVerticesByPosition`. Instead, a merged GEN+SIM
particle takes its production vertex from its **immediate GEN production vertex**
(via the faithful `genpartIndex` link); the redundant SimTrack production edge to
the shared beam vertex is dropped.

**Result (per sample, 5 events):**

| | logical vtx out-degree (max) | particle parent-count (max) | cycles/event |
|---|---|---|---|
| Before (position merge) | 666–936 | 335–457 | 5/5 |
| After (immediate-GEN attach) | 51–104 (physical hadronization scale) | 30–61 | 0 |

`multiProdParticles=0`, one component/event, no cycles — and the logical degree
distributions now match the raw *physical* maxima. See [Validation](validation.md).

## 3. `genpartIndex` is ancestor-collapsed (do not back-fill)

**Discovered while planning the fix above:** `SimTrack::genpartIndex()` is **not**
reliably the immediate GEN parent. For non-primary tracks,
`SimTrackManager.cc` sets it to `idLastStoredAncestor()`, and `MCTruthUtil`
inherits `mcTruthID` from the mother — both collapse to the nearest *stored*
ancestor (up to the root), dropping intermediate GenVertices.

**Consequence / guard:** the GEN↔SIM association must only use `genpartIndex` for
`simTrack.isPrimary()` tracks (where it *is* the immediate HepMC barcode, set by
`Generator::setGenId(barcode)` for the whole pre-assigned-decay cascade).
`TruthGraphProducer` already enforces this. The immediate link is therefore
captured on-the-fly at simulation time and does **not** need a new product.

## 4. Pileup is invisible to the signal-only graph

**Discovered:** the truth producers read `g4SimHits` / `generatorSmeared` =
**signal only** (bx=0). Pileup `SimTrack`s live in the **transient**
`CrossingFrame<SimTrack>` (consumed by digitizers, never persisted — only
`CrossingFramePlaybackInfoNew` survives), and the only persisted pileup truth is
the flat `mix:MergedTrackTruth` / `mix:MergedCaloTruth`. Premixing exposes even
less (digi-level `mixData:MergedTrackTruth` only).

**Quantified** (PU=2, standard mixing): `g4SimHits` SimTracks = 100% bx=0;
`mix:MergedTrackTruth` = 91% pileup (bx≠0). The graph saw none of the pileup.

**Change:** add pileup support — see the [Pileup](pileup.md) page (Phase A
prototype + the Phase-B `DigiAccumulator`, configurable, in-time pileup by default).

## 5. Cross-release dataformat incompatibility (CMSSW_17 → CMSSW_20)

**Discovered while re-validating the rebase:** CMSSW_20 cannot open CMSSW_17
`step3.root` (ROOT streamer-checksum change on
`edm::Wrapper<HcalDataFrameContainer<QIE10DataFrame>>`; CMSSW_20 uses `io_v1::`
versioned dataformats). So cross-release comparison must be a full relval re-run,
not a same-input shortcut. The rebase was validated by re-running all eight
workflows on CMSSW_20: identical invariants (cycles/multiProd/orphans all 0), mean
graph degrees within ~1.5% — differences are confined to expected cross-release
simulation RNG. See [Validation](validation.md).
