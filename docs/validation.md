# Validation

All numbers below come from the eight `enableTruth` Run4 D120 (no-PU) relval
topologies. `runTruthRelvals.sh` regenerates them into a small library. The
`TruthGraphTopologyChecker` audits that library.

## The relval library

Workflow `34xxx.88` = base workflow + the `enableTruth` UpgradeWorkflow variant.
The offset `.88` appends `--procModifiers enableTruth` to the GenSim,
HARVESTGlobal and RecoGlobal steps. `runTruthRelvals.sh` regenerates the library.
`makeTruthGallery.sh` builds the DOT gallery.

| Folder | Sample | D120 | D122 | Natural seeds |
|---|---|---|---|---|
| SingleElectron | SingleElectronPt35 | 34002.88 | 34802.88 | 11, -11 |
| TTbar | TTbar 14 TeV | 34034.88 | 34834.88 | 6, -6 |
| DYToLL | DYToLL M-50 | 34044.88 | 34844.88 | 23 |
| DYToTauTau | DYToTauTau M-50 | 34045.88 | 34845.88 | 23 |
| ZMM | ZMM 14 TeV | 34050.88 | 34850.88 | 23 |
| H125_diphoton | H125 ggF | 34052.88 | 34852.88 | 25 |
| VBFHZZ4Nu | VBF H→ZZ→4ν | 34131.88 | 34931.88 | 25 |
| TenTau | TenTau E 15 to 500 | 34087.88 | 34887.88 | 15, -15 |
| SingleTop | ST t-channel (custom) | 34999.88 | D120 only | 6, -6 |
| TTbarPowheg | ttbar POWHEG (custom) | 34998.88 | D120 only | 6, -6 |
| Diboson | WW→2ℓ2ν (custom) | 34997.88 | D120 only | 23, 24, -24 |
| VH | ZH→bb,ℓℓ (custom) | 34996.88 | D120 only | 25 |

The D122 base id is the D120 one plus 800, checked against `runTheMatrix.py -w upgrade -n`
(34802.0 is `SingleElectronPt35_pythia8_Run4D122`, and likewise for the other seven). The
last four are locally defined workflows with no upstream D122 counterpart, so a D122
campaign covers the first eight. Keep the geometry the same on both sides of a mix: a D120
pileup library overlaid on a D122 signal is not a valid sample.

## Levels: hardProcess is the legs, signal is the resonance

These numbers come from one event of each of the twelve templates above. The level
membership now sits on the truth graph itself (`ParticleData::levelFlags`).

| level | what it holds |
|---|---|
| `hardProcess` | the **outgoing legs** of the hard scatter. ttbar gives b, b~ and the W decay products, **not** the two tops; H to two photons gives the photons; VBF gives the two tagging quarks plus the four neutrinos. Empty for a particle gun, correctly. |
| `signal` | the **resonance**: 2 tops, 1 Z, 1 Higgs, 10 taus, W+ and W- for the diboson sample, 1 top for t-channel |
| `stableDecayProducts` | final-state generator particles, ~45% gamma and ~35% charged pions across every template |
| `caloBoundary` | those reaching the calorimeter, plus secondaries made in material (ttbar 559 to 649, VBF 231 to 468) |
| `stableLegsFromUpstream` | preset-dependent, so it varies from 4 (H125) to 2095 (ttbar) |
| `reconstructableFromSignal` | the signal's **visible final state**: walk down from each signal root, stop at the first object a detector reconstructs. A pi0 is labelled, its two photons are not; an a1 or rho is walked through; neutrinos are dropped. TenTau gives 18.59 per event |
| `underlyingEvent` | the stable legs of the underlying event, the counterpart of `stableLegsFromUpstream`. ttbar gives 103.17 per event, a particle gun 0 |
| `partonJets` | one root per **parton-initiated jet**: the hard-scatter legs that are quarks or gluons, each standing for its whole descendant subgraph. No clustering. ttbar gives 4.80 per event with the b bin at exactly 2.00; QCD flat pT gives exactly 2.00 per event, 67% gluons |
| `bHadrons`, `cHadrons` | the first hadron of each heavy flavour along a chain, so B* to B counts once. Separate levels because a B decays to a D and one combined level would drop every charm member. ttbar: 2.02 and 3.38 per event. These two also define the secondary-vertex truth below |

`isHardProcess` marks the hard-scatter participants. The deepest-element antichain
keeps the outgoing ones. That is why this level holds the final state and not the
resonance. **Use `signal` when you want the object the analysis names.**

All twelve templates contain the resonance. The truth graph therefore never has to
invent one. A synthetic stand-in exists for a generator that omits the resonance.
`ParticleRole::SignalStandIn` marks that stand-in. The role is the marker on purpose.
A connector particle has the same empty GEN and SIM back-references and the same
status 0. Code that infers "synthetic" from empty fields therefore cannot tell the two
apart. The stand-in's momentum is the sum of the hard-process legs. That momentum is an
accounting quantity, never generator truth.

A sample whose configuration names NO resonance has no `signal` level at all. An empty
seed list, or the full-graph escape hatch `{0}`, means the question is not answerable.
The code then leaves the `signal` and `signalNoSelection` folders unbooked, rather than
booking them empty. The associators and the hit-based validators both take the seed list
as `signalSeedPdgIds`. The two must carry the SAME value in the DQM configuration.
Otherwise the folders vanish or read wrong.

`signal` is the one level bit that nothing can recompute from the truth graph alone. The
seed PDG ids that produced it therefore sit on the truth graph. The dumper audits every
flagged particle against those ids.

[truth-graph-levels](https://felice.web.cern.ch/orbit/?path=%2Ftruth-graph-levels)
publishes a dot and PDF of one event per template. Each node draws the levels as
coloured rows.

## Topology audit (after the immediate-GEN-attach fix)

5 events per sample. **The invariants are clean across all eight samples.** The
truth graph is a proper DAG (`cycles=0`). Every particle has exactly one production
vertex (`multiProdParticles=0`). Each event has one connected component
(`orphanFragments=0`). The max degrees sit at the physical hadronization and shower
scale.

| Sample | cycles | multiProd | orphans | logical vtx-out (max) | parent-count (max) |
|---|---|---|---|---|---|
| SingleElectron | 0 | 0 | 0 | 10 | 1 |
| TTbar | 0 | 0 | 0 | 75 | 43 |
| DYToLL | 0 | 0 | 0 | 81 | 42 |
| DYToTauTau | 0 | 0 | 0 | 81 | 42 |
| ZMM | 0 | 0 | 0 | 76 | 33 |
| H125 ggF | 0 | 0 | 0 | 104 | 61 |
| TenTau | 0 | 0 | 0 | 64 | 1 |
| VBFHZZ4Nu | 0 | 0 | 0 | 51 | 30 |

For context, compare the state **before** the fix (position-based vertex merge). The
same logical graphs then had a mega-vertex of out-degree 666 to 936, and cycles in
every event. See [Findings](findings.md).

The **raw** graph is also clean everywhere: `multiProd=0`, `cycles=0`, one
component/event. Its large numbers are **physical**, for example a SimVtx out-degree
up to ~600 in TTbar and many multi-parent particles. Three effects produce them: the
hard scatter (Z←q q̄ has 2 parents), PYTHIA string hadronization (status-71/72
multi-endpoint mothers), and Geant4 shower vertices.

## CMSSW_17 → CMSSW_20 rebase

The branch moved from `CMSSW_17_0_0_pre2` to `CMSSW_20_0_0_pre1` by rebase. A
cross-release dataformat change (see [Findings](findings.md)) forced the comparison
to be a **full relval re-run** on CMSSW_20. Result: **no change in truth-graph
behavior**.

- The rebuild from scratch is clean. All cppunit tests pass identically.
- All 8 workflows PASSED every step (8/8/8/8/8).
- The structural invariants are identical (cycles/multiProd/orphans all 0; one
  component/event).
- The mean graph degrees agree within ~1.5%. Only the max degrees over 5 events vary.
  Different relval events explain that variation fully (cross-release simulation RNG).

| | invariants | mean vtx-out | mean parent |
|---|---|---|---|
| CMSSW_17 | 0/0/0 (all 8) | 1.06 to 1.40 | 1.00 to 1.28 |
| CMSSW_20 | 0/0/0 (all 8) | 1.06 to 1.39 | 1.00 to 1.25 |

## The DOT gallery

`makeTruthGallery.sh` re-derives the logical graph from each `step3.root`. For each
process it emits a full-graph DOT (`seedPdgIds=0`, reference) and three selected
DOT/SVG views. The [per-process presets](usage.md#per-process-presets) resolve the
per-process selection from the generator fragment. VBF therefore shows its tagging
jets, Drell-Yan its dilepton channel, and guns their species. Both galleries
(`test/dot_gallery` for CMSSW_17, `test/dot_gallery_v20` for CMSSW_20) have the
identical structure: one full-graph DOT plus three selected DOT/SVG views per
process. All of them render cleanly. The old mega-vertex would have broken the
layout.

**Browse the rendered gallery.** The full CMSSW_20 set (SVG + DOT) is online and
searchable at **[felice.web.cern.ch/truth](https://felice.web.cern.ch/truth/)**. That
site is an [Orbit](https://github.com/felicepantaleo/orbit) folder browser. Click a
process, then a `*_signal_*` / `*_full_*` SVG for the inline zoomable view.

## DQM performance plots (Branch vs legacy truth objects)

A parallel DQM section compares the truth `Branch` graph to the legacy truth objects.
It does **not** fork the release validators. It works in the same fashion as
`HGCalValidator` / `MultiTrackValidator`. TICL-style `AssociationMap` *producers* build
the reco↔Branch links as standalone EDM products. DQM *analyzers* turn those links into
plots. A `DQMGenericClient` harvester forms the efficiencies.

**Calorimetry**: `BranchHGCalValidator` (folder `HGCAL/BranchValidator/{CaloParticle,SimCluster}`)
compares the Branch subgraph calo hits to each object's `hits_and_fractions`. It books
reproduction efficiency vs η/p_T/E, purity, hit/energy completeness, and energy
response. It books three response references.

`energy_response` is the **sim-energy containment** `E^{sim}_Branch / E_gen`. It folds
in the active-material sampling fraction. It therefore sits well below 1 and varies by
region.

`raw_energy_response_sim` and `raw_energy_response_reco` instead normalise the Branch's
energy **on the object's own cells** by the object's **fraction-weighted hit energy**,
not by the generator energy. They do so on the deposited (PCaloHit) and reconstructed
(RecHit) scales.

The deposited one is a **closure test**. A CaloParticle/SimCluster's per-cell fraction
*is* its tracks' share of the deposit, that is, the Branch's own sim energy on that
cell. The ratio is therefore **== 1 by construction**. Any deviation flags a
fraction↔deposit bug in PR validation. Restricting the numerator to the object footprint
also keeps the ratio finite. Without that restriction, a tiny object whose `trackId`
maps to a large shower would raise the un-thresholded sim ratio up to ~10⁵.

The reconstructed one is the informative plot. The Branch claims each shared cell's
**whole** RecHit while the object keeps only its fraction. The ratio therefore peaks
just above 1 (TenTau: CaloParticle ⟨E^{rec}_Branch/E^{rec}_hits⟩ ≈ 1.1, SimCluster
≈ 1.2). It measures the non-fractional reco energy the Branch picks up in cells shared
between overlapping showers.

`TruthBranchCaloAssociationProducer` emits `caloParticleToBranch` /
`branchToCaloParticle` (+ SimCluster), shared-energy + score, best first. Verified on
TTbar: CaloParticle eff ≈ 0.76, SimCluster ≈ 0.93.

**Tracking**: a `TrackingParticle` carries *no hits of its own*, only its
`SimTrack`s. The Branch↔TrackingParticle comparison therefore cannot be a direct hit
overlap like the calorimeter one. The hit-bearing probe is the **reco track**.
`TruthBranchTrackingAssociationProducer` matches each `reco::Track` to a Branch by
shared tracker simhit DetIds. It uses `BranchHitAssociator` on the tracker channel with
shared-hit multiplicity, because the tracker has no per-cell energy to share. It
produces `trackToBranch` / `branchToTrack`.

`BranchTrackingValidator` (folder `Tracking/BranchValidator/TrackingParticle`) is the
DQM form of the `BranchTrackerReplacementValidator`. It closes the loop to the
`TrackingParticle` through the standard `ClusterTPAssociation` (`tpClusterProducer`).
It books a "Branch reproduces the TP track→truth assignment" efficiency vs η/p_T. It
also books the shared-hit completeness/multiplicity. Verified on TTbar (CMSSW_20,
5 evt): **0.875** (246/281 TP-matched tracks), shared-hit multiplicity ≈ 16/track.

In Phase-2 D120 only the pixel `TrackerHitsPixel{Barrel,Endcap}*` simhits are
populated. The TIB/TID/TOB/TEC branches are empty. The match is therefore
pixel-DetId based, which is still more than enough to identify the particle.

Standalone drivers: `test/validateBranch{DQM,TrackingDQM}_cfg.py` (→ DQMIO),
`test/harvestBranchDQM_cfg.py` (→ legacy `DQM_V0001`). Both sequences live in
`PhysicsTools/TruthInfo/python/truthGraphValidation_cff.py` and
`truthGraphDQMHarvester_cff.py`. The release sequences take both behind `enableTruth`.
The association producers go into `baseCommonPreValidation`. The DQM analyzers go into
`baseCommonValidation` (`globalValidation_cff`). The matching harvesting attaches to
`postValidation_common` (`postValidation_cff`). The Run4 eras apply `enableTruth`, so
these modules run in the standard Phase-2 validation. The reco-side validators and
their harvesters stay opt-in (see the antichain caveat below).

## Reco-side validators (generic hit exposure)

The validators above compare the Branch graph to the *legacy truth objects*. The
generic layer below closes the other loop. It matches **reco objects** (reco tracks,
TICL tracksters) directly to the Branch graph through shared hits. It books
MultiTrackValidator / HGCalValidator-style efficiency, fake-rate, merge-rate and
duplicate-rate plots. Adding a new reco type takes one adapter and no DataFormats
change.

**The hit-exposure layer**: `interface/RecoHitAdapters.h` provides free functions.
They reduce any reco object to a range of `truth::RecoHit{detId, energy, fraction}`.
That range is the `HasTruthHits` customization point, which `BranchHitAssociator`
uses:

- `truth::recoHits(reco::Track const&)`: the track's valid rechit DetIds, unit
  weight. The tracker has no per-cell energy, so the associator matches by
  shared-hit multiplicity.
- `truth::recoHits(ticl::Trackster const&, std::vector<reco::CaloCluster> const&)`:
  the trackster's layer-cluster cells with their fractions, coalesced.

These are free functions, not data-format methods, on purpose. A trackster references
layer clusters that live in a separate collection, and a member method could not reach
them. Returning a `PhysicsTools` type from a `DataFormats` class would also invert the
package dependency. A new reco type = one new adapter returning
`std::vector<truth::RecoHit>`.

**The validator**: `plugins/BranchRecoValidator.cc` is one template
(`BranchRecoValidatorT<Traits>`) with two concrete modules:

- **`BranchTrackRecoValidator`**: `reco::Track` (default `generalTracks`), tracker
  channel, shared-hit multiplicity; second axis = p<sub>T</sub>. DQM folder
  `Tracking/BranchValidator/recoTrack`.
- **`BranchTracksterRecoValidator`**: `ticl::Trackster`
  (`ticlTrackstersCLUE3DHigh` + `hgcalMergeLayerClusters`), calo channel, shared
  energy; second axis = energy. DQM folder `HGCAL/BranchValidator/Trackster`.

Each module books two truth-side plots **vs η and the second axis**: an efficiency
(`effnum`/`denom`) and a duplicate rate (`dupnum`/`denom`). It books two reco-side
plots on the same axes: a fake rate (`fakenum`/`recodenom`) and a merge rate
(`mergenum`/`recodenom`). It also books a best-branch match-`purity` distribution.
`DQMGenericClient` post-processors in `truthGraphDQMHarvester_cff` form the ratios
(`branchTrackRecoPostProcessor`, `branchTracksterRecoPostProcessor`).

!!! warning "Reco-side metrics need a disjoint truth reference"
    The reco-side efficiency, merge rate and duplicate rate are only meaningful
    against a **disjoint (antichain)** set of interesting truth branches. A Branch
    subgraph aggregates *all* of a particle's descendants. Against the **full**
    truth graph every ancestor therefore contains its descendants' hits. Every reco
    object then "merges" ≥2 nested branches (merge-rate ≈ 1). Almost nothing is
    uniquely matched (efficiency ≈ 0). That result is degenerate by construction,
    not a real performance number.

    A flat `interestingPdgIds` list is a sufficient antichain **only for
    non-showering species**. Restricting the track validator to **muons** on Z→μμ
    gives sensible numbers (merge-rate ≈ 0.02, efficiency ≈ 0.56). A broader
    charged-stable list is still degenerate on TTbar, for example, because pions,
    protons and electrons are deeply nested in the hadronic/EM cascade. The
    physically correct reference depends on the detector: `CaloParticle`-like (the
    particle entering HGCAL) for calo, and `TrackingParticle`-like (per charged
    track-maker) for tracking. That reference is the `BranchSelector` "interesting
    particles" antichain, which is not yet wired (see the
    [Roadmap](roadmap.md#validation)). For that reason the two modules are
    **opt-in** (`truthGraphRecoSideValidationSequence`) and stay out of the default
    validation sequence. The muon configuration in
    `test/validateBranchRecoDQM_cfg.py` is the working demonstration.

**The plots macro**: `scripts/makeTruthGraphValidationPlots.py` is a self-contained
PyROOT macro. It follows `makeHGCalValidationPlots.py` but has no framework
dependency. It reads the analyzer DQMIO output **or** a legacy harvested `DQM_V0001`
file. It locates the Branch-validator folders. It derives the efficiency, fake, merge
and duplicate ratios with **binomial errors**. It overlays several samples in one set
of plots and writes PNGs plus an `index.html`:

```bash
makeTruthGraphValidationPlots.py tau.root:Tau zmm.root:ZMM ttbar.root:TTbar -o plots
```

The `FILE:LABEL` form sets the legend entry. Passing several samples also gives the
per-event guided comparison (cf. [Worked examples](examples.md)).

**The library wrapper**: `test/makeBranchValidationPlots.sh` automates the above over
a `runTruthRelvals.sh` library. It locates each workflow's harvested legacy DQM file
(`DQM_V0001_R*__Global__*__RECO.root`). It then overlays a few representative samples
in one set of PNGs plus an `index.html`. The default samples are TTbar, TenTau and
ZMM; override them with `SAMPLES`. This script is the companion to
`makeTruthGallery.sh`:

```bash
cmsenv
makeBranchValidationPlots.sh /path/library /path/branch_plots
```

## Reco-side metrics in `Validation/TruthInfo` (current generation, 2026-08-01)

The sections above describe the first-generation validators. `Validation/TruthInfo` is
the package that ships the DQM pages today. It holds one templated
`TruthBranchRecoValidator` over tracks, vertices, secondary vertices and tracksters.
`DQMGenericClient` string configuration harvests all of it. Six metrics live on the
reco side and they answer four different questions. The numbers below come from 200
events per sample.

| Page | Formula | Question |
|---|---|---|
| `fakerate` | `1 - num_dominated/num_reco` | does **one** truth branch own the object |
| `nocandidate` | `1 - num_assoc(recoToSim)/num_reco` | does it correspond to **any** truth branch (a subset of `fakerate`) |
| `nolevelcandidate` | `1 - num_levelcandidate/num_reco` | is the dominance question even **defined** for it |
| `contaminated` | `1 - num_assoc_strict/num_reco` | does its best candidate pass the 0.6 recoToSim score (HGCalValidator's non-fake cut) |
| `recopurity` | `num_recopurity/num_reco` | how much of the object belongs to the branch it matched, as a **mean** |
| `pileuprate` | `num_pileup/num_reco` | is the matched branch an overlaid interaction |

!!! warning "`fakerate` and `contaminated` are not the same question"
    The recoToSim score is normalised against the cell's **total** truth energy
    (`recoEnergy = fraction * cellTotalEnergy`). At PU200 a cell shared with overlaid
    interactions therefore drives the score towards 1, even for a well matched object.
    Measured on ttbar PU200, `ticlCandidate` / AdaptiveNominal: **73.8%** of tracksters
    fail the 0.6 cut, while only **2.2%** have no candidate at all. Quote `fakerate`
    for "reconstructed something that is not there". Quote `contaminated` for "shares
    its cells with other truth". `contaminated` stays in the package precisely because
    it is HGCalValidator's criterion, so it stays comparable to the reference.

Each metric has **its own numerator**. The validator fills `num_assoc(recoToSim)` once
per matched object. `num_recopurity` holds the same objects weighted by the purity of
the match. Merging the two turns the fake rate into one minus the mean purity. The
package did merge them until 2026-08-01: the fake rate then read 0.83 on no-PU ttbar,
where the fake rate is 0.003.

The fake rate is **identical at all four working points**. The purity meanwhile climbs
from 0.28 (`Fixed`) to 0.97 (`AdaptiveNominal`) on no-PU ttbar. That is the control,
not a coincidence. The adaptive climb changes *which* branch an object matches, not
*whether* it matches one. The gain must therefore appear on the purity page. A fake
rate that moves with the working point means the association gained or lost candidates.

!!! note "At PU200 `nocandidate` saturates"
    PU200 tracking `nocandidate` is 0.000 to 0.001, **lower** than with no pileup. The
    truth graph is dense enough that nearly every reco object overlaps something.
    "Matched to nothing" therefore stops discriminating on its own. Read the pileup
    rate (0.93 to 0.95 adaptive) and the purity (0.10 to 0.73) beside it.

### A fake is an object no truth branch owns

A fake is an object whose hits come from several different generated particles, with
**none dominating**. Nothing can then own the object. That is the criterion the
`fakerate` page publishes:

```
fake = matched to nothing
       OR (has a candidate at dominanceLevel AND leading share < minLeadingTruthShare)
```

`minLeadingTruthShare` defaults to **0.5**. The validator books `leading_truth_share`
and `dominance_ratio` as monitor elements in their own right. `leading_truth_share` is
the leading contributor's shared energy over all contributors'. `dominance_ratio` is
the leading contributor over the runner-up, capped at 20. The validator reads both from
the **first** working point's map. That map is the only one carrying every candidate,
because an adaptive point inserts just the branch it climbed to. That makes the fake
rate **identical at all four working points** by construction. The validation scripts
assert this as a control.

#### The antichain requirement

The validator computes dominance over one **level**, set by `dominanceLevel` (default
`caloBoundary`). This is not a detail. "Nothing dominates" is unfalsifiable off an
antichain, because the leader and the runner-up can be the same particle at two depths.
`selectedBranchRoots` is every particle passing the selector. A tau, its daughter pion
and that pion's descendants are therefore candidates at the same time, with **nested**
subgraphs carrying nearly identical shared energy.

The control is no-PU TenTau. There, ten isolated taus must give one clear winner:

| candidate set | median leading share | fraction with ratio near 1 |
|---|---|---|
| `selectedBranchRoots` (nested) | 0.26 | 0.999 |
| `caloBoundary` (antichain) | 0.98 | 0.064 |

#### Objects the question does not reach

An object that matched truth but has **no candidate at the dominance level** is not a
fake. The question is undefined for it, not answered negatively. Counting it as a fake
measures how much of the event that level covers, not how well the collection
reconstructs. It has its own page, `nolevelcandidate`. Read that page beside the fake
rate.

Measurement established this, rather than assumption. Counting those objects as fakes
gave 0.36 to 0.60 on no-PU across every sample and both domains. Three checks isolated
the cause.

It is **not** the threshold. Among objects where dominance is defined, the share is 1.0
for 45% of ttbar tracksters and below 0.5 for only 5.7%.

It is **not** the level. A config-only probe moved the tracking level from
`caloBoundary` to `stableDecayProducts`. The rate went from 0.540 to 0.489.
Calorimetry stayed identical to four decimals, as the control.

It is **not** nesting. Projecting each candidate onto the antichain member it descends
from changed nothing to four decimals. The associators insert roots that are already
members or unrelated.

Measured on 200 events per sample, `ticlCandidate`:

| sample | `fakerate` | `nocandidate` | `nolevelcandidate` |
|---|---|---|---|
| ttbar no-PU | 0.218 | 0.180 | 0.325 |
| DY no-PU | 0.406 | 0.403 | 0.537 |
| VBF no-PU | 0.258 | 0.185 | 0.354 |
| TenTau no-PU | 0.047 | 0.000 | 0.021 |
| ttbar PU200 | 0.027 | 0.022 | 0.872 |
| DY PU200 | 0.085 | 0.084 | 0.930 |
| VBF PU200 | 0.050 | 0.046 | 0.897 |

!!! warning "At PU200 the fake rate is formed on a small subset"
    `nolevelcandidate` is **0.87 to 0.93** at PU200. The fake rate therefore covers 7%
    to 13% of the collection. `caloBoundary` holds about 113 objects per event at PU200
    against 99.7 with no pileup. That is only ~14 extra from 200 interactions, because
    the selector's 1 GeV floor removes nearly all soft pileup. The event meanwhile holds
    thousands of tracksters. The dominance question therefore asks "does one particle
    above 1 GeV dominate". It is undefined for the soft remainder. Never quote a PU200
    fake rate without `nolevelcandidate` beside it. TenTau is the counter-example. It
    shows that the level works when the event suits it, with `nolevelcandidate` at
    0.021.

Read DY no-PU as a sanity check, not as a defect. Its 0.406 is almost entirely
`nocandidate` (0.403). These are genuine soft tracksters matching no truth at all in a
Z to two leptons event.

### The truth-side denominators are variable-blind (2026-08-05)

An efficiency drawn against pt must not apply the pt cut to its own denominator. The cut
would deform the turn-on that the plot exists to show. The measurement re-ran the
associators on 200 no-PU ttbar events with the selector open. The `caloBoundary`
denominator in the first pt bin is 10024 with the 1 GeV floor and 144529 without, a
factor 14.4. The second bin moves by 1.05.

The selector therefore reports WHICH plotted-axis cut a branch fails (pt or eta),
instead of one accept-or-reject. The associator publishes that mask beside each level
denominator as `truthToRecoTargets<Level>Eligibility`. The validator fills a variable
only for objects that fail nothing except the cut on that variable itself. An object
that fails both cuts enters no plot. Levels whose roots Geant4 never tracked stay
untouched, because the kinematic cuts never apply to them. `partonJets`, `bHadrons` and
`hardProcess` measure identically with the selector open.

### The secondary-vertex denominator is the heavy-flavour decay vertices (2026-08-04)

A secondary vertex is where a b or c hadron decayed. The denominator is therefore the
decay vertices of the `bHadrons` and `cHadrons` antichains. The associator's
`heavyFlavorOnly` switches that denominator on. Measured on no-PU ttbar, per event:

| criterion | truth SVs |
|---|---|
| b/c hadron decay vertices | **4.00** (801 over 200 events) |
| incoming particle's subgraph carries heavy flavour anywhere | 12 to 16 |
| every graph vertex with two selected roots | 45.9 |
| what `inclusiveSecondaryVertices` reconstructs | **4.1** |

Only the first criterion matches reco. The others cap the efficiency at a third and a
tenth, whatever the reconstruction does. That cap is a property of the denominator.

The levels name the **weakly decaying** hadron of each chain (2026-08-20). Before that,
they kept the first hadron of the chain. For most chains the first hadron is an excited
state, and it decays electromagnetically at its production point. The count was identical,
but 35.3% of the denominator vertices sat below 100 microns from the beam axis, at the
primary vertex, where no secondary vertex exists to reconstruct. With the weak-decay
convention that fraction is 3.2%, and the median decay radius moves from 0.046 cm to
0.41 cm (10 ttbar PU200 events; the 20-event sample gives 6.30 truth SVs per event). The
unchanged count is why the old convention looked correct: only the vertex positions were
wrong. The earlier 17.0% below-100-micron figure for no-PU ttbar was measured with the old
convention; re-measure it before quoting it. Whether to cut the residual sub-100-micron
vertices away is still an open choice, because it changes the published efficiency.

### Axes that span decades are symlog, and every axis was scanned (2026-08-05)

`pt`, `vertpos` and `nhits` cover orders of magnitude, and uniform bins lost the ends.
19% of `partonJets` entries sat in the pt overflow at 100 GeV. 93.4% of all truth
secondary vertices fell in the first 1.5 cm `vertpos` bin. These axes are now symlog:
one linear bin up to a threshold (0.1 GeV, 10 microns, 1 hit) and a log ladder above.
They are symlog rather than log because these axes have a real population at EXACTLY
zero. On DY, 20.5% of the `signal` level is the pre-ISR copy of the resonance at pt
exactly 0. A log axis would move that population into the underflow unseen.

The same scan found one plot that had never drawn anything at all. Reco `zpos` in the
calorimetric domain was 100% out of range. A trackster barycentre sits at |z| 320 to
520 cm, against the tracker's +-30 cm axis. The truth and reco sides of one domain can
now carry different ranges for the same quantity. Keep this habit: for every `num_*`
monitor element, check the under-plus-overflow fraction. The same quantity reading 0% in
one domain and 100% in another is inherited configuration, not physics.

### The calorimetric duplicate outcome is not booked

`num_duplicate` is absent from calorimetric folders. The outcome needs two reco objects
on the same branch, each below `maxSimToRecoScoreForDuplicate`. Two objects built from
**disjoint** layer clusters have scores summing to at least one. Measured on 200 no-PU
ttbar events, `ticlCandidate`, `ticlTrackstersCLUE3DHigh` and `ticlTracksterLinks` each
use every layer cluster in at most one trackster. A collection whose objects share layer
clusters would make the outcome reachable again. This diverges deliberately from
HGCalValidator, which books the plot. The split rate carries the calorimetric pathology
instead.

## Build & checks

- `scram b` is clean, apart from external `vecgeom` warnings.
- `scram b code-format` and `scram b code-checks` are clean for the package.
- Unit tests (cppunit, `scram b runtests`): **41** assertions across 5 binaries:
  `TruthLogicalGraphPostProcessor_t` (23), `BranchHitAssociator_t` (6), `Branch_t`
  (5), `BranchSelector_t` (4), `LogicalGraphHitIndexBuilder_t` (3), plus the
  `truthGraphSelections_t` and `testTruthHistoryGuard` tests.
