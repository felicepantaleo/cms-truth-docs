# Validation

All numbers below come from the eight `enableTruth` Run4 D120 (no-PU) relval
topologies, regenerated into a small library and audited with the
`TruthGraphTopologyChecker`.

## The relval library

Workflow `34xxx.88` = base workflow + the `enableTruth` UpgradeWorkflow variant
(offset `.88`, which appends `--procModifiers enableTruth` to the GenSim, HARVESTGlobal and
RecoGlobal steps). Regenerated with `runTruthRelvals.sh`; DOT gallery with
`makeTruthGallery.sh`.

| Folder | Sample | Workflow | Natural seeds |
|---|---|---|---|
| SingleElectron | SingleElectronPt35 | 34002.88 | 11, -11 |
| TTbar | TTbar 14 TeV | 34034.88 | 6, -6 |
| DYToLL | DYToLL M-50 | 34044.88 | 23 |
| DYToTauTau | DYToTauTau M-50 | 34045.88 | 23 |
| ZMM | ZMM 14 TeV | 34050.88 | 23 |
| H125_diphoton | H125 ggF | 34052.88 | 25 |
| VBFHZZ4Nu | VBF H→ZZ→4ν | 34131.88 | 25 |
| TenTau | TenTau E 15 to 500 | 34087.88 | 15, -15 |
| SingleTop | ST t-channel (custom) | 34999.88 | 6, -6 |
| TTbarPowheg | ttbar POWHEG (custom) | 34998.88 | 6, -6 |
| Diboson | WW→2ℓ2ν (custom) | 34997.88 | 23, 24, -24 |
| VH | ZH→bb,ℓℓ (custom) | 34996.88 | 25 |

## Topology audit (after the immediate-GEN-attach fix)

5 events per sample. **Invariants are clean across all eight**: proper DAG
(`cycles=0`), every particle has exactly one production vertex
(`multiProdParticles=0`), and one connected component per event
(`orphanFragments=0`). The max degrees are at the physical hadronization /
shower scale.

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

For context, **before** the fix (position-based vertex merge) the same logical
graphs had a mega-vertex of out-degree 666 to 936 and cycles in every event, see
[Findings](findings.md).

The **raw** graph is also clean everywhere: `multiProd=0`, `cycles=0`, one
component/event. Its large numbers (e.g. SimVtx out-degree up to ~600 in TTbar,
many multi-parent particles) are **physical**: hard scatter (Z←q q̄ has 2 parents),
PYTHIA string hadronization (status-71/72 multi-endpoint mothers), and Geant4
shower vertices.

## CMSSW_17 → CMSSW_20 rebase

The branch was rebased from `CMSSW_17_0_0_pre2` to `CMSSW_20_0_0_pre1`. Because of
a cross-release dataformat change (see [Findings](findings.md)), the comparison was
a **full relval re-run** on CMSSW_20. Result: **no change in truth-graph behavior**.

- Clean rebuild from scratch; all cppunit tests pass identically.
- All 8 workflows PASSED every step (8/8/8/8/8).
- Structural invariants identical (cycles/multiProd/orphans all 0; one component/event).
- Mean graph degrees agree within ~1.5%; only the max degrees over 5 events wiggle,
  fully explained by different relval events (cross-release simulation RNG).

| | invariants | mean vtx-out | mean parent |
|---|---|---|---|
| CMSSW_17 | 0/0/0 (all 8) | 1.06 to 1.40 | 1.00 to 1.28 |
| CMSSW_20 | 0/0/0 (all 8) | 1.06 to 1.39 | 1.00 to 1.25 |

## The DOT gallery

`makeTruthGallery.sh` re-derives the logical graph from each `step3.root` and emits
per process: a full-graph DOT (`seedPdgIds=0`, reference) and three selected
DOT/SVG views, with the per-process selection resolved from the generator fragment
by the [per-process presets](usage.md#per-process-presets) (so VBF shows its tagging
jets, Drell-Yan its dilepton channel, guns their species). Both galleries
(`test/dot_gallery` for CMSSW_17, `test/dot_gallery_v20` for CMSSW_20) have the
identical structure: one full-graph DOT plus three selected DOT/SVG views per
process, all
rendering cleanly (the old mega-vertex would have blown up the layout).

**Browse the rendered gallery:** the full CMSSW_20 set (SVG + DOT) is online and
searchable at **[felice.web.cern.ch/truth](https://felice.web.cern.ch/truth/)**
(an [Orbit](https://github.com/felicepantaleo/orbit) folder browser, click a
process, then a `*_signal_*` / `*_full_*` SVG for the inline zoomable view).

## DQM performance plots (Branch vs legacy truth objects)

A parallel DQM section (it does **not** fork the release validators) compares the
truth `Branch` graph to the legacy truth objects, in the same fashion as
`HGCalValidator` / `MultiTrackValidator`: TICL-style `AssociationMap` *producers*
build the reco↔Branch links as standalone EDM products, and DQM *analyzers* turn
them into plots; a `DQMGenericClient` harvester forms the efficiencies.

**Calorimetry**: `BranchHGCalValidator` (folder `HGCAL/BranchValidator/{CaloParticle,SimCluster}`)
compares the Branch subgraph calo hits to each object's `hits_and_fractions`:
reproduction efficiency vs η/p_T/E, purity, hit/energy completeness, and energy response.
Three response references are booked. `energy_response` is the **sim-energy containment**
`E^{sim}_Branch / E_gen`, which folds in the active-material sampling fraction and so
sits well below 1 and varies by region. `raw_energy_response_sim` and
`raw_energy_response_reco` instead normalise the Branch's energy **on the object's own
cells** by the object's **fraction-weighted hit energy** (rather than the generator
energy), on the deposited (PCaloHit) and reconstructed (RecHit) scales. The deposited
one is a **closure test**: a CaloParticle/SimCluster's per-cell fraction *is* its tracks'
share of the deposit, i.e. the Branch's own sim energy on that cell, so the ratio is
**== 1 by construction** and any deviation flags a fraction↔deposit bug in PR validation
(numerator restricted to the object footprint also keeps it finite; un-restricted, a
tiny object whose `trackId` maps to a large shower would blow the un-thresholded sim
ratio up to ~10⁵). The reconstructed one is the informative plot: the Branch claims each
shared cell's **whole** RecHit while the object keeps only its fraction, so it peaks just
above 1 (TenTau: CaloParticle ⟨E^{rec}_Branch/E^{rec}_hits⟩ ≈ 1.1, SimCluster ≈ 1.2) and
measures the non-fractional reco energy the Branch picks up in cells shared between
overlapping showers. `TruthBranchCaloAssociationProducer` emits
`caloParticleToBranch` / `branchToCaloParticle` (+ SimCluster), shared-energy + score,
best first. Verified on TTbar: CaloParticle eff ≈ 0.76, SimCluster ≈ 0.93.

**Tracking**: a `TrackingParticle` carries *no hits of its own* (only its
`SimTrack`s), so the Branch↔TrackingParticle comparison cannot be a direct hit
overlap like the calorimeter. The hit-bearing probe is the **reco track**:
`TruthBranchTrackingAssociationProducer` matches each `reco::Track` to a Branch by
shared tracker simhit DetIds (`BranchHitAssociator`, tracker channel, shared-hit
multiplicity, since the tracker has no per-cell energy to share), producing
`trackToBranch` / `branchToTrack`. `BranchTrackingValidator` (folder
`Tracking/BranchValidator/TrackingParticle`, the DQM form of the
`BranchTrackerReplacementValidator`) closes the loop to the `TrackingParticle` via
the standard `ClusterTPAssociation` (`tpClusterProducer`) and books a
"Branch reproduces the TP track→truth assignment" efficiency vs η/p_T plus the
shared-hit completeness/multiplicity. Verified on TTbar (CMSSW_20, 5 evt):
**0.875** (246/281 TP-matched tracks), shared-hit multiplicity ≈ 16/track. In
Phase-2 D120 only the pixel `TrackerHitsPixel{Barrel,Endcap}*` simhits are populated
(the TIB/TID/TOB/TEC branches are empty), so the match is pixel-DetId based, still
more than enough to identify the particle.

Standalone drivers: `test/validateBranch{DQM,TrackingDQM}_cfg.py` (→ DQMIO),
`test/harvestBranchDQM_cfg.py` (→ legacy `DQM_V0001`). Both sequences live in
`PhysicsTools/TruthInfo/python/truthGraphValidation_cff.py` and
`truthGraphDQMHarvester_cff.py`. Both are wired into the release sequences behind
`enableTruth`: the association producers into `baseCommonPreValidation` and the DQM
analyzers into `baseCommonValidation` (`globalValidation_cff`), with the matching
harvesting attached to `postValidation_common` (`postValidation_cff`). The Run4 eras
apply `enableTruth`, so these run in the standard Phase-2 validation. The reco-side
validators and their harvesters stay opt-in (see the antichain caveat below).

## Reco-side validators (generic hit exposure)

The validators above compare the Branch graph to the *legacy truth objects*. The
generic layer below closes the other loop: it matches **reco objects**
(reco tracks, TICL tracksters) directly to the Branch graph through shared hits, and
books MultiTrackValidator / HGCalValidator-style efficiency, fake-rate, merge-rate
and duplicate-rate plots. Adding a new reco type is one adapter, no DataFormats
change.

**The hit-exposure layer**: `interface/RecoHitAdapters.h` provides free functions
that reduce any reco object to a range of `truth::RecoHit{detId, energy, fraction}`,
the `HasTruthHits` customization point used by `BranchHitAssociator`:

- `truth::recoHits(reco::Track const&)`: the track's valid rechit DetIds, unit
  weight (the tracker has no per-cell energy, so matching is by shared-hit
  multiplicity).
- `truth::recoHits(ticl::Trackster const&, std::vector<reco::CaloCluster> const&)`:
  the trackster's layer-cluster cells with their fractions, coalesced.

These are free functions, not data-format methods, on purpose: a trackster
references layer clusters that live in a separate collection (a member method
couldn't reach them), and returning a `PhysicsTools` type from a `DataFormats` class
would invert the package dependency. A new reco type = one new adapter returning
`std::vector<truth::RecoHit>`.

**The validator**: `plugins/BranchRecoValidator.cc` is one template
(`BranchRecoValidatorT<Traits>`) with two concrete modules:

- **`BranchTrackRecoValidator`**: `reco::Track` (default `generalTracks`), tracker
  channel, shared-hit multiplicity; second axis = p<sub>T</sub>. DQM folder
  `Tracking/BranchValidator/recoTrack`.
- **`BranchTracksterRecoValidator`**: `ticl::Trackster`
  (`ticlTrackstersCLUE3DHigh` + `hgcalMergeLayerClusters`), calo channel, shared
  energy; second axis = energy. DQM folder `HGCAL/BranchValidator/Trackster`.

Each books, **vs η and the second axis**, a truth-side efficiency
(`effnum`/`denom`) and duplicate rate (`dupnum`/`denom`), a reco-side fake rate
(`fakenum`/`recodenom`) and merge rate (`mergenum`/`recodenom`), plus a best-branch
match-`purity` distribution. The ratios are formed by `DQMGenericClient`
post-processors in `truthGraphDQMHarvester_cff` (`branchTrackRecoPostProcessor`,
`branchTracksterRecoPostProcessor`).

!!! warning "Reco-side metrics need a disjoint truth reference"
    The reco-side efficiency/merge/duplicate is only meaningful against a
    **disjoint (antichain)** set of interesting truth branches. A Branch subgraph
    aggregates *all* of a particle's descendants, so against the **full** graph
    every ancestor trivially contains its descendants' hits: every reco object
    "merges" ≥2 nested branches (merge-rate ≈ 1) and almost nothing is uniquely
    matched (efficiency ≈ 0), degenerate by construction, not a real performance
    number.

    A flat `interestingPdgIds` list is a sufficient antichain **only for
    non-showering species**: restricting the track validator to **muons** on Z→μμ
    gives sensible numbers (merge-rate ≈ 0.02, efficiency ≈ 0.56), whereas a broader
    charged-stable list is still degenerate on e.g. TTbar, because pions, protons
    and electrons are deeply nested in the hadronic/EM cascade. The physically
    correct reference is detector-dependent: `CaloParticle`-like (the particle
    entering HGCAL) for calo, `TrackingParticle`-like (per charged track-maker) for
    tracking, i.e. the `BranchSelector` "interesting particles" antichain, which is
    not yet wired (see the [Roadmap](roadmap.md#validation)). For that reason the two
    modules are **opt-in** (`truthGraphRecoSideValidationSequence`), kept out of the
    default validation sequence; the muon configuration in
    `test/validateBranchRecoDQM_cfg.py` is the working demonstration.

**The plots macro**: `scripts/makeTruthGraphValidationPlots.py` is a self-contained
PyROOT macro (inspired by `makeHGCalValidationPlots.py` but with no framework
dependency). It reads the analyzer DQMIO output **or** a legacy harvested
`DQM_V0001` file, locates the Branch-validator folders, derives the
efficiency/fake/merge/duplicate ratios with **binomial errors**, overlays several
samples in one set of plots and writes PNGs + an `index.html`:

```bash
makeTruthGraphValidationPlots.py tau.root:Tau zmm.root:ZMM ttbar.root:TTbar -o plots
```

The `FILE:LABEL` form sets the legend entry; passing several samples doubles as the
per-event guided comparison (cf. [Worked examples](examples.md)).

**The library wrapper**: `test/makeBranchValidationPlots.sh` automates the above
over a `runTruthRelvals.sh` library: it locates each workflow's harvested legacy
DQM file (`DQM_V0001_R*__Global__*__RECO.root`) and overlays a few representative
samples (TTbar / TenTau / ZMM by default; override with `SAMPLES`) in one set of
PNGs + `index.html`, the companion to `makeTruthGallery.sh`:

```bash
cmsenv
makeBranchValidationPlots.sh /path/library /path/branch_plots
```

## Reco-side metrics in `Validation/TruthInfo` (current generation, 2026-08-01)

The sections above describe the first-generation validators. The package that ships the
DQM pages today is `Validation/TruthInfo`, one templated
`TruthBranchRecoValidator` over tracks, vertices, secondary vertices and tracksters,
harvested entirely by `DQMGenericClient` string configuration. Four metrics live on the
reco side and they answer four different questions; the numbers below are measured on
200 events per sample.

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
    (`recoEnergy = fraction * cellTotalEnergy`), so at PU200 a cell shared with overlaid
    interactions drives it towards 1 even for a well matched object. Measured on ttbar
    PU200, `ticlCandidate` / AdaptiveNominal: **73.8%** of tracksters fail the 0.6 cut
    while only **2.2%** have no candidate at all. Quote `fakerate` for "reconstructed
    something that is not there" and `contaminated` for "shares its cells with other
    truth". `contaminated` is kept precisely because it is HGCalValidator's criterion and
    so stays comparable to the reference.

Each metric has **its own numerator**. `num_assoc(recoToSim)` is filled once per matched
object, `num_recopurity` is the same objects weighted by the purity of the match. Merging
the two, which is what the package did until 2026-08-01, turns the fake rate into one
minus the mean purity: it read 0.83 on no-PU ttbar where the fake rate is 0.003.

The fake rate is **identical at all four working points** while the purity climbs from
0.28 (`Fixed`) to 0.97 (`AdaptiveNominal`) on no-PU ttbar. That is the control, not a
coincidence: the adaptive climb changes *which* branch an object matches, not *whether* it
matches one, so the gain must appear on the purity page. A fake rate that moves with the
working point means the association gained or lost candidates.

!!! note "At PU200 `nocandidate` saturates"
    PU200 tracking `nocandidate` is 0.000 to 0.001, **lower** than with no pileup, because
    the truth graph is dense enough that nearly every reco object overlaps something and
    "matched to nothing" stops discriminating on its own. Read the pileup rate (0.93 to
    0.95 adaptive) and the purity (0.10 to 0.73) beside it.

### A fake is an object no truth branch owns

A fake is an object whose hits come from several different generated particles with
**none dominating**, so there is nothing to attribute it to. That is the criterion the
`fakerate` page publishes:

```
fake = matched to nothing
       OR (has a candidate at dominanceLevel AND leading share < minLeadingTruthShare)
```

`minLeadingTruthShare` defaults to **0.5**. `leading_truth_share` (leading contributor's
shared energy over all contributors') and `dominance_ratio` (leading over runner-up,
capped at 20) are booked as monitor elements in their own right. Both are read from the
**first** working point's map, the only one carrying every candidate, since an adaptive
point inserts just the branch it climbed to. That makes the fake rate **identical at all
four working points** by construction, which the validation scripts assert as a control.

#### The antichain requirement

Dominance is computed over one **level**, set by `dominanceLevel` (default
`caloBoundary`), and this is not a detail. "Nothing dominates" is unfalsifiable off an
antichain, because the leader and the runner-up can be the same particle at two depths:
`selectedBranchRoots` is every particle passing the selector, so a tau, its daughter pion
and that pion's descendants are candidates simultaneously with **nested** subgraphs
carrying nearly identical shared energy.

The control is no-PU TenTau, where ten isolated taus must give one overwhelming winner:

| candidate set | median leading share | fraction with ratio near 1 |
|---|---|---|
| `selectedBranchRoots` (nested) | 0.26 | 0.999 |
| `caloBoundary` (antichain) | 0.98 | 0.064 |

#### Objects the question does not reach

An object that matched truth but has **no candidate at the dominance level** is not a
fake. The question is undefined for it rather than answered negatively, and counting it
as a fake measures how much of the event that level covers instead of how well the
collection reconstructs. It has its own page, `nolevelcandidate`, and that page must be
read beside the fake rate.

This was established by measurement, not assumed. Counting those objects as fakes gave
0.36 to 0.60 on no-PU across every sample and both domains. The cause was isolated three
ways: it is **not** the threshold (among objects where dominance is defined, the share is
1.0 for 45% of ttbar tracksters and below 0.5 for only 5.7%), **not** the level (a
config-only probe moving the tracking level from `caloBoundary` to `stableDecayProducts`
took the rate from 0.540 to 0.489, with calorimetry identical to four decimals as the
control), and **not** nesting (projecting each candidate onto the antichain member it
descends from changed nothing to four decimals, because the associators insert roots that
are already members or unrelated).

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
    `nolevelcandidate` is **0.87 to 0.93** at PU200, so the fake rate is measured on 7% to
    13% of the collection. `caloBoundary` holds about 113 objects per event at PU200
    against 99.7 with no pileup, only ~14 extra from 200 interactions, because the
    selector's 1 GeV floor removes nearly all soft pileup, while there are thousands of
    tracksters. The dominance question therefore asks "does one particle above 1 GeV
    dominate" and is undefined for the soft mush. Never quote a PU200 fake rate without
    `nolevelcandidate` beside it. TenTau is the counter-example that shows the level works
    when the event suits it: `nolevelcandidate` is 0.021 there.

DY no-PU is worth reading as a sanity check rather than a defect: its 0.406 is almost
entirely `nocandidate` (0.403), genuine soft tracksters matching no truth at all in a
Z to two leptons event.

### The calorimetric duplicate outcome is not booked

`num_duplicate` is absent from calorimetric folders. The outcome needs two reco objects
each below `maxSimToRecoScoreForDuplicate` on the same branch, and two objects built from
**disjoint** layer clusters have scores summing to at least one. Measured on 200 no-PU
ttbar events, `ticlCandidate`, `ticlTrackstersCLUE3DHigh` and `ticlTracksterLinks` each
use every layer cluster in at most one trackster. A collection whose objects share layer
clusters would make it reachable again. This diverges deliberately from HGCalValidator,
which books the plot; the split rate carries the calorimetric pathology instead.

## Build & checks

- `scram b` clean (only external `vecgeom` warnings).
- `scram b code-format` and `scram b code-checks` clean for the package.
- Unit tests (cppunit, `scram b runtests`): **41** assertions across 5 binaries:
  `TruthLogicalGraphPostProcessor_t` (23), `BranchHitAssociator_t` (6), `Branch_t`
  (5), `BranchSelector_t` (4), `LogicalGraphHitIndexBuilder_t` (3), plus the
  `truthGraphSelections_t` and `testTruthHistoryGuard` tests.
