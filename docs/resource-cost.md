# Computing cost

The truth graph against the legacy frozen truth objects.

This page gives what it costs to keep `TrackingParticle`, `TrackingVertex`,
`CaloParticle` and `SimCluster`. It also gives what it costs to keep the truth
graph plus its associators instead. Every number below comes from a measurement on
one sample. Nothing here is extrapolated. A quantity that was not measured is
listed as not measured, never as an estimate.

## Sample and conditions

These conditions are identical for every number in this document.

| | |
|---|---|
| Process | `TTbar_14TeV_TuneCP5`, no pileup (`mixNoPU_cfi`) |
| Events | 10 |
| Release | `CMSSW_20_1_0_pre2` (section 1); `CMSSW_20_1_X_2026-07-22-2300` (sections 2 to 7) |
| Geometry, era, global tag | `ExtendedRun4D122`, `Phase2C26I13M9`, `auto:phase2_realistic_T35` |
| Steps | GEN,SIM then DIGI,L1,DIGI2RAW,HLT:@relvalRun4 then RAW2DIGI,L1Reco,RECO |
| Host | AMD EPYC 9754, 1 thread, 1 stream |

Sections 1 to 6 are NO PILEUP. Section 7 measures the event size at PU200. The two
schemes scale very differently there. The CPU and memory numbers remain no-PU only.

## 1. Event size

`edmEventSize -v` reads these sizes. Both schemes first appear at DIGI. The chain
copies them unchanged into RECO, so the DIGI and RECO byte counts are identical.

| Scheme | branches | uncompressed kB/event | compressed kB/event |
|---|---:|---:|---:|
| Legacy: TrackingParticle, TrackingVertex, CaloParticle, SimCluster | 11 | 2135.2 | 772.2 |
| Graph, **default** (shared) hit index: `TruthGraph`, `truth::Graph`, `truth::LogicalGraphHitIndex` | 3 | 1805.1 | 577.4 |
| Truth-branch association maps, denominators and eligibility masks | 52 | 457.3 | 57.4 |
| **Graph total, default index** | **55** | **2262.4** | **634.8** |

Compressed, the truth graph plus every association product is 137.4 kB/event smaller
than the legacy collections, a factor 1.22. The margin is much narrower than it was
when this document was first written. Two changes narrowed it. First, the truth graph
grew when its detector scope was corrected. The pruning and the hit index had been
blind to the barrel, HCAL, the tracker and the muon chambers. The truth graph was
therefore small because it was wrong. Second, the association layer grew from one
working point to four plus the per-level denominators. The levels work added the level
flags and the particle role. These cost 5 bytes per particle before compression.

The legacy row is unchanged, because nothing in the graph work touches those
collections. The graph and association rows come from a re-measurement on the current
build.

Drop the legacy collections and keep the truth graph plus all four association working
points. That saves **137.4 kB/event compressed, 17.8%** of the truth payload. That is
with the full signal GEN half included, which the legacy collections do not carry at
all. The shared hit index is what makes the truth graph a saving rather than a cost;
the materialised index is larger, see section 1.2.

!!! note "The chain is not bit-reproducible, so read the last digit as noise"
    Two runs of the identical configuration differ in 64 of 1338 branches. HLT
    tracking is among them. `TruthGraph_mix` ranged 53793 to 56124 compressed
    bytes/event over four runs, a 4.2% spread. The graph row therefore uses its mean
    of 54.9 kB/event. The hit index and `truth::Graph` are stable to the byte, and so
    is everything derived from them. Section 6 has the detail.

The single largest graph branch is the hit index. It is 202.3 kB/event compressed by
default, and 445.3 with the materialised layout. It is a separate product, so you can
drop it on its own. The two graph structures alone are 166.0 kB/event.

For context, the whole RECO event is 7991.4 kB/event compressed. Graph products are
4.9% of it. Legacy truth is 7.8%.

### 1.1 Older measurements: the pruning-scope fix

!!! warning "Not re-measured"
    This subsection and section 1.2 hold measurements from
    `CMSSW_20_1_X_2026-07-22-2300`. Only the section 1 table above is re-measured on
    `CMSSW_20_1_0_pre2`. Do not compare a number here with a number there.

The section 1 table of that older release was an undercount, for the reason below.

The hitless-subgraph pruning used to be wired to the HGCAL endcap only. It therefore
pruned as hitless every particle depositing solely in the ECAL/HCAL barrel. Under
pileup it also pruned every pileup charged particle. The truth graph was smaller
because it was wrong.

Controlled A/B, same 10 ttbar events, same job. Only the sim-hit collections of the
producer changed. Compressed bytes per event:

| branch | pruning on HGCAL only | pruning on the full detector |
|---|---:|---:|
| `TruthGraph` (`mix`) | 35264 | 34661 |
| `truth::Graph` | 50570 | 128166 |
| `truth::LogicalGraphHitIndex` | 116202 | 143477 |
| **total** | **202037** | **306304** |

The graph branch grows 2.5x, because it now keeps the barrel particles it always
should have kept. The table in section 1 was measured before this fix. Re-measure it
on the reference conditions before you quote any size claim from it again.

### 1.2 What changed since the first version of this document

Two things moved in opposite directions and the net is a saving.

The truth graph now carries the **full signal GEN half**, contracted.
`truth::collapseGenShower` collapses away the parton shower and the intermediate
copies of a resonance. A resonance that appears several times is therefore one node,
whose children are its decay products. That half did not exist when this document was
first written.

The hit index now uses the **shared subgraph store**. It writes each hit once. The
order makes the subtree of a particle a contiguous run of slots. A subgraph is
therefore a set of ranges of that one store, not a second materialised copy under
every ancestor. A GEN-only particle sits above the SIM tree in a DAG. It therefore
owns a merged set of runs rather than a single one. Measured over 3 events, 1039 such
particles need 2547 ranges, mean 2.45, median 1, max 183.

A/B on the same GEN-SIM, 10 events, compressed bytes/event of the three graph branches:

| variant | hit index | `truth::Graph` | `TruthGraph_mix` | total |
|---|---:|---:|---:|---:|
| no GEN half, materialised index | 271013 | 92499 | 54037 | 417549 |
| full GEN half, materialised index | 696729 | 126768 | 74681 | 898178 |
| collapsed GEN half, materialised index | 445329 | 111070 | 55413 | 611812 |
| **collapsed GEN half, shared index (the default)** | **202300** | **111070** | **54938** | **368308** |

The `TruthGraph_mix` column carries the run-to-run spread noted above. Differences of
about a kB in that column and in the total are therefore not significant. The hit
index column is stable to the byte. That column is what these variants are about.

The materialised index stored a hit once per ancestor containing it. 26744 hits per
event became 46259 stored entries even with no GEN half at all, and 1467228 stored
entries with the full GEN half. The shared store keeps the 26744. Reading is automatic
in both layouts, which keeps every file written before this change readable.

The cost is paid at query time. A range is in tree order and repeats a detId hit by
several descendants. A consumer that needs per-cell energies therefore coalesces it.
`BranchHitAssociator` does this once per candidate root at construction. Measured on
the same 10 events, `allTrackToTruthBranchAssociators` goes from 10.1 to 12.2
ms/event. The whole RECO job goes from 692.5 to 694.9 ms/event, +0.3%.

### Cost per object

| Collection | objects/event | compressed bytes/object |
|---|---:|---:|
| `truth::Graph` particles + vertices | 1186.5 + 557.3 | 53 |
| `TrackingParticle` (MergedTrackTruth) | 896.1 | 99 |
| `CaloParticle` (MergedCaloTruth) | 185.4 | 414 |

The graph node is cheaper for a structural reason, not by a compression accident. A
`TrackingParticle` embeds `std::vector<SimTrack> g4Tracks_`, and so do `CaloParticle`
and `SimCluster`. Each `SimTrack` carries 12 members. The same SimTracks are already
persisted separately in `SimTracks_g4SimHits` (431.2 kB/event compressed). The legacy
classes also store their topology as `edm::Ref` and `RefVector` members
(`parentVertex_`, `decayVertices_`, `daughterTracks_`, `sourceTracks_`, `simClusters_`).
`truth::ParticleData` and `truth::VertexData` embed no SimTrack and no Ref. Topology
lives once, in the CSR offset arrays of `truth::Graph`. The hit index holds the hit
payload once. The legacy scheme instead duplicates that payload as parallel `hits_` and
`fractions_` vectors in every `CaloParticle` and every `SimCluster`.

The duplication is the point. The legacy scheme writes four distinct `SimCluster`
collections, plus `CaloParticle`, plus `TrackingParticle` and `TrackingVertex`. Each of
these re-embeds its own SimTrack copies and hit arrays. The truth graph writes one
structure that covers tracker and calorimeter together. That is 1186.5 particles per
event against 896.1 + 185.4 + 423.5 legacy objects.

## 2. CPU and allocated memory at DIGI

!!! warning "Not re-measured"
    Measured on `CMSSW_20_1_X_2026-07-22-2300`. Section 1 has since been re-measured
    on `CMSSW_20_1_0_pre2`. Treat the numbers below as the older release until they
    are redone.

`TrackingTruthAccumulator`, `CaloTruthAccumulator` and `TruthGraphAccumulator` are all
`DigiAccumulatorMixMod` plugins inside the single `mix` module. The FastTimerService
therefore cannot separate them. An A/B isolated them, on the same input, the same 10
events and the same host. The A/B deletes entries from `process.mix.digitizers`, with
three repetitions each.

| Variant | mix real ms/event (mean, sd, n=3) | mix allocated kB/event |
|---|---:|---:|
| as shipped | 2449.0, 2.6 | 969 965.4 |
| without `TruthGraphAccumulator` | 2469.1, 40.6 | 960 045.1 |
| without `TrackingTruth` and `CaloTruth` | 2430.0, 14.2 | 940 884.7 |
| without all three | 2408.2, 6.2 | 930 964.4 |

All three truth accumulators together cost **40.8 +- 3.9 ms/event**. That is **1.7% of
the 2449 ms/event that `mix` costs**. The split of that time between graph and legacy
is NOT resolved at three repetitions. The two independent estimates of each disagree by
more than their errors.

The allocated-memory split is exact and additive (9920.3 + 29080.7 = 39001.0):

- `TruthGraphAccumulator`: **9.9 MB/event**
- `TrackingTruthAccumulator` + `CaloTruthAccumulator`: **29.1 MB/event**, a factor **2.9**
  more.

The downstream stages of the truth graph are ordinary EDProducers and are timed
separately. `truthLogicalGraphProducer` costs 3.5 ms/event.
`truthLogicalGraphHitIndexProducer` costs 5.4 ms/event.

## 3. CPU at RECO

!!! warning "Not re-measured"
    Measured on `CMSSW_20_1_X_2026-07-22-2300`. Section 1 has since been re-measured
    on `CMSSW_20_1_0_pre2`. Treat the numbers below as the older release until they
    are redone.

These numbers come from a re-run of the RECO step with the FastTimerService. The
framework TimeReport agrees to the microsecond.

| Module | real ms/event | allocated kB/event |
|---|---:|---:|
| `allTrackToTruthBranchAssociators` | 3.713 | 1669.0 |
| `allVertexToTruthBranchAssociators` | 0.475 | 155.6 |
| `allSecondaryVertexToTruthBranchAssociators` | 0.091 | 140.3 |
| total | 4.28 | 1964.9 |

That is **0.38% of the 1119.7 ms/event** summed over all scheduled RECO modules. It is
with three working points per domain. No legacy truth producer runs in this RECO
sequence. There is therefore no legacy counterpart to compare the associators against.

## 4. What the graph does NOT save

This section states it plainly, because the opposite is easy to assume.

**The DIGI-time accumulation step is not removed.** All three accumulators exist for
the same reason. Pileup sub-event SimTracks, SimVertices and SimHits are only reachable
through `PileUpEventPrincipal` while mixing runs. They are never in the output event.
The sources make this explicit:

- `SimGeneral/TrackingAnalysis/plugins/TrackingTruthAccumulator.cc:407` and `:471`
- `SimGeneral/CaloAnalysis/plugins/CaloTruthAccumulator.cc:684` and `:782`
- `PhysicsTools/TruthInfo/plugins/TruthGraphAccumulator.cc:458` and `:469`

The truth graph replaces two accumulators with one. It does not eliminate the step. The
saving is in what that step allocates and writes, not in skipping it.

**MTD legacy truth is untouched.** `MtdSimClusters`, `MtdSimLayerClusters`,
`MtdSimTracksters` and `MtdCaloParticles` are a further 243.6 kB/event compressed. The
truth graph does not currently replace them.

**Raw SimTracks and SimVertices stay.** They are 529.8 kB/event compressed. The SIM
step writes them and both schemes consume them.

## 5. Reading a subgraph in either layout

`LogicalGraphHitIndex::subgraphHits` returns a single span. In the shared layout a
particle that carries hits owns exactly one slot range, so its span is fine. A GEN-only
particle owns several ranges, and the accessor then returns an **empty** span. Four
validators used the size of that span as a smallest-footprint tie-break. A zero-size
answer makes a GEN-only root win a comparison meant to pick the tightest branch. A
simple switch of layout would therefore have read as a near-total loss of reproduction
efficiency.

Consumers use `truth::SubgraphHitView` instead. It returns the coalesced, detId-sorted
span in either layout. The materialised layout already persists that form, and the view
hands it back untouched. The view coalesces the shared layout once per particle and
caches the result. A particle whose subgraph is a single one-slot range needs neither
step, because the builder already sorted and summed its own direct hits. Hold one view
per event and per module. It caches, so it is not thread safe.

All seven consumers now go through it, and the arithmetic in each is unchanged. The
check ran the calorimeter validator on 10 ttbar events, over a materialised index and
over a shared index. It compared every monitor element: **50 compared, 50 non-empty, 0
differing**. That rests on the accessor-level equivalence measured in section 1.1,
which covered every particle and every channel.

## 6. This chain is not bit-reproducible, and that is not a truth-graph property

Read the byte counts in section 1 with this in mind. Two runs of the identical
configuration, same input file, same host, one thread, do not write the same file.
**64 of 1338 branches differ in compressed size**. Five of them differ uncompressed
too, so the difference is real content and not just packing. The largest by absolute
delta is `TruthGraph_mix` (56123.9 against 55250.2 compressed bytes/event,
uncompressed identical at 498985). It is not alone:

| branch | compressed | uncompressed |
|---|---|---|
| `TruthGraph_mix` | 56123.9 -> 55250.2 | same |
| `recoTrackExtras_hltGeneralTracks` | 46859.7 -> 46867.5 | differs |
| `recoTracks_hltInitialStepTrackSelectionHighPurity` | 8934.8 -> 8937.2 | same |
| `recoVertexs_hltOfflinePrimaryVertices` | 521.2 -> 519.8 | same |
| `uints_hltPhase2PixelTracksCAExtension` | 525.9 -> 527.2 | same |

The HLT tracking output changes between identical runs. That is the root of most of
this. It is upstream of the truth graph and independent of it.

The part that matters here is that the truth **content** is reproducible.
`truth::Graph` and `truth::LogicalGraphHitIndex` hash identically across the same runs.
The hash covers the logical particle and vertex records, all eight CSR arrays, and every
hit and offset of all four channels. Of the persisted arrays of `TruthGraph`, these are
all identical run to run: `offsets`, `edges`, `edgeKind`, `pdgId`, `status`,
`statusFlags`, `eventId`, `genEventOfNode`, `simVertexProcessType`,
`simTrackBackscattered` and `simTrackToGen`.

One open point is specific to this package. It is worth a look, but it is not a
blocker. `TruthGraph_mix` is the one branch whose compressed size moves while its
uncompressed size does not. That means the same length and different bytes.
`TruthGraph::NodeRef` is `{ NodeKind kind; int64_t key; }`, with `NodeKind` a
`uint8_t`. It therefore carries seven bytes of padding, and the branch is written
unsplit. Uninitialised padding would produce exactly that signature, without changing
any value a consumer reads. This is a hypothesis, not a result. Confirming it needs a
C++-side dump of the raw buffer, because PyROOT cannot read the unsplit struct reliably.
That is also why the hashes above exclude `kind`.

## 7. Event size at PU200

!!! warning "Not re-measured"
    Measured on `CMSSW_20_1_X_2026-07-22-2300`. Section 1 has since been re-measured
    on `CMSSW_20_1_0_pre2`. Treat the numbers below as the older release until they
    are redone.

Same signal process, same release and geometry, 10 events. Classic mixing with an
average of 200 minimum-bias interactions from a D122 truth-enabled library. Default
truth wiring, no selection preset. Compressed kB/event:

| Scheme | kB/event | vs no pileup |
|---|---:|---:|
| Legacy: TrackingParticle, 2x TrackingVertex, 4x SimCluster, CaloParticle | 56717 | x91 |
| Graph: `TruthGraph`, `truth::Graph`, `truth::LogicalGraphHitIndex` | 8791 | x24 |

At PU200 the truth graph is **15.5% of the legacy truth payload**, a factor 6.5. With
no pileup it is 82.2%, from the section 1 table. The saving grows with pileup for two reasons. The legacy objects
re-embed their SimTrack copies and hit arrays per object and per collection, and pileup
multiplies the objects. The topology of the truth graph stays CSR, and its hits stay
stored once. The shared hit index is 4762 kB/event of the graph total. It remained the
persisted layout in 10 of 10 events, with no fallback and no degradation warnings.

MTD legacy truth, which neither scheme replaces, is a further 9859 kB/event at PU200.

The pileup GEN half is collapsed (`collapsePileupGen=True`). Each pileup interaction
carries one Interaction vertex and one UnderlyingEvent vertex holding its stable
particles, and nothing else. The SIM tracks and hits of the 200 extra interactions
therefore dominate their graph cost, not their generator records.

## 8. Not measured

- CPU and allocated memory at PU200. Section 7 measures the event size there. The
  accumulator A/B of section 2 and the RECO timings of section 3 are no-PU only.
- The RECO-side associator numbers in section 3 predate the shared hit index. Section
  1.1 gives the measured before and after for `allTrackToTruthBranchAssociators` on the
  same 10 events. The per-module table in section 3 was not re-measured with the
  FastTimerService.
- Peak RSS. No log in this chain reports `SimpleMemoryCheck`, and this work added no
  instrumentation. The memory figures above are the FastTimerService allocated-bytes
  counter.
- The CPU split between `TruthGraphAccumulator` and the two legacy accumulators inside
  `mix`. Only the combined 40.8 +- 3.9 ms/event is resolved at three repetitions.
- A true A/B of file size with the truth graph removed from the chain. The per-branch
  sizes above are read off the single existing chain.
- Legacy associator CPU at RECO, for example `quickTrackAssociatorByHits`, which is not
  in this RECO sequence.
- Any multi-threaded scaling. Everything is one thread, one stream.

## Summary

On a no-pileup ttbar event, replace the frozen truth objects with the truth graph and
its associators. That is a **17.8% reduction of the persisted truth payload** (772.2 to
634.8 kB/event compressed). It is a **factor 2.9 less memory allocated during mixing**
(29.1 to 9.9 MB/event). It is a RECO-side association cost of a few ms/event, well
under 1% of the scheduled reconstruction. That is with the full signal GEN half
included, which the legacy collections do not carry at all. The DIGI-time accumulation
step itself is not removed. At PU200 the size advantage grows to a factor 6.5 (section
7). The CPU and memory numbers remain no-PU only.
