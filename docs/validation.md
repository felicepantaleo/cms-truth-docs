# Validation

All numbers below come from the eight `enableTruth` Run4 D120 (no-PU) relval
topologies, regenerated into a small library and audited with the
`TruthGraphTopologyChecker`.

## The relval library

Workflow `34xxx.88` = base workflow + the `enableTruth` UpgradeWorkflow variant
(offset `.88`, which appends `--procModifiers enableTruth` to the GenSim and
RecoGlobal steps). Regenerated with `runTruthRelvals.sh`; DOT gallery with
`makeTruthGallery.sh`.

| Folder | Sample | Workflow | Natural seeds |
|---|---|---|---|
| SingleElectron | SingleElectronPt35 | 34002.88 | 11, −11 |
| TTbar | TTbar 14 TeV | 34034.88 | 6, −6 |
| DYToLL | DYToLL M-50 | 34044.88 | 23 |
| DYToTauTau | DYToTauTau M-50 | 34045.88 | 23 |
| ZMM | ZMM 14 TeV | 34050.88 | 23 |
| H125_diphoton | H125 ggF | 34052.88 | 25 |
| VBFHZZ4Nu | VBF H→ZZ→4ν | 34131.88 | 25 |
| TenTau | TenTau E 15–500 | 34087.88 | 15, −15 |

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
graphs had a mega-vertex of out-degree 666–936 and cycles in every event — see
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

- Clean rebuild from scratch; all 31 cppunit tests pass identically.
- All 8 workflows PASSED every step (8/8/8/8/8).
- Structural invariants identical (cycles/multiProd/orphans all 0; one component/event).
- Mean graph degrees agree within ~1.5%; only the max degrees over 5 events wiggle,
  fully explained by different relval events (cross-release simulation RNG).

| | invariants | mean vtx-out | mean parent |
|---|---|---|---|
| CMSSW_17 | 0/0/0 (all 8) | 1.06–1.40 | 1.00–1.28 |
| CMSSW_20 | 0/0/0 (all 8) | 1.06–1.39 | 1.00–1.25 |

## The DOT gallery

`makeTruthGallery.sh` re-derives the logical graph from each `step3.root` and emits
per process: a full-graph DOT (`seedPdgIds=0`, reference) and three selected
DOT/SVG views (natural seeds, `seedParentDepth=1`). Both galleries
(`test/dot_gallery` for CMSSW_17, `test/dot_gallery_v20` for CMSSW_20) have the
identical structure: 8 processes × (1 full + 3 selected) = 32 DOT, 24 SVG, all
rendering cleanly (the old mega-vertex would have blown up the layout).

## DQM performance plots (Branch vs legacy truth objects)

A parallel DQM section (it does **not** fork the release validators) compares the
truth `Branch` graph to the legacy truth objects, in the same fashion as
`HGCalValidator` / `MultiTrackValidator`: TICL-style `AssociationMap` *producers*
build the reco↔Branch links as standalone EDM products, and DQM *analyzers* turn
them into plots; a `DQMGenericClient` harvester forms the efficiencies.

**Calorimetry** — `BranchHGCalValidator` (folder `HGCAL/BranchValidator/{CaloParticle,SimCluster}`)
compares the Branch subgraph calo hits to each object's `hits_and_fractions`:
reproduction efficiency vs η/p_T/E, purity, hit/energy completeness, and sim-energy
containment. `TruthBranchCaloAssociationProducer` emits `caloParticleToBranch` /
`branchToCaloParticle` (+ SimCluster), shared-energy + score, best first. Verified on
TTbar: CaloParticle eff ≈ 0.76, SimCluster ≈ 0.93.

**Tracking** — a `TrackingParticle` carries *no hits of its own* (only its
`SimTrack`s), so the Branch↔TrackingParticle comparison cannot be a direct hit
overlap like the calorimeter. The hit-bearing probe is the **reco track**:
`TruthBranchTrackingAssociationProducer` matches each `reco::Track` to a Branch by
shared tracker simhit DetIds (`BranchHitAssociator`, tracker channel, shared-hit
multiplicity — the tracker has no per-cell energy to share), producing
`trackToBranch` / `branchToTrack`. `BranchTrackingValidator` (folder
`Tracking/BranchValidator/TrackingParticle`, the DQM form of the
`BranchTrackerReplacementValidator`) closes the loop to the `TrackingParticle` via
the standard `ClusterTPAssociation` (`tpClusterProducer`) and books a
"Branch reproduces the TP track→truth assignment" efficiency vs η/p_T plus the
shared-hit completeness/multiplicity. Verified on TTbar (CMSSW_20, 5 evt):
**0.875** (246/281 TP-matched tracks), shared-hit multiplicity ≈ 16/track. In
Phase-2 D120 only the pixel `TrackerHitsPixel{Barrel,Endcap}*` simhits are populated
(the TIB/TID/TOB/TEC branches are empty), so the match is pixel-DetId based — still
more than enough to identify the particle.

Standalone drivers: `test/validateBranch{DQM,TrackingDQM}_cfg.py` (→ DQMIO),
`test/harvestBranchDQM_cfg.py` (→ legacy `DQM_V0001`). Both sequences live in
`PhysicsTools/TruthInfo/python/truthGraphValidation_cff.py` and
`truthGraphDQMHarvester_cff.py`; wiring into `globalValidation` / `postValidation`
behind `enableTruth` is still pending.

## Reco-side validators (generic hit exposure)

The validators above compare the Branch graph to the *legacy truth objects*. The
generic layer below closes the other loop — it matches **reco objects**
(reco tracks, TICL tracksters) directly to the Branch graph through shared hits, and
books MultiTrackValidator / HGCalValidator-style efficiency, fake-rate, merge-rate
and duplicate-rate plots. Adding a new reco type is one adapter, no DataFormats
change.

**The hit-exposure layer** — `interface/RecoHitAdapters.h` provides free functions
that reduce any reco object to a range of `truth::RecoHit{detId, energy, fraction}`,
the `HasTruthHits` customization point used by `BranchHitAssociator`:

- `truth::recoHits(reco::Track const&)` — the track's valid rechit DetIds, unit
  weight (the tracker has no per-cell energy, so matching is by shared-hit
  multiplicity).
- `truth::recoHits(ticl::Trackster const&, std::vector<reco::CaloCluster> const&)` —
  the trackster's layer-cluster cells with their fractions, coalesced.

These are free functions, not data-format methods, on purpose: a trackster
references layer clusters that live in a separate collection (a member method
couldn't reach them), and returning a `PhysicsTools` type from a `DataFormats` class
would invert the package dependency. A new reco type = one new adapter returning
`std::vector<truth::RecoHit>`.

**The validator** — `plugins/BranchRecoValidator.cc` is one template
(`BranchRecoValidatorT<Traits>`) with two concrete modules:

- **`BranchTrackRecoValidator`** — `reco::Track` (default `generalTracks`), tracker
  channel, shared-hit multiplicity; second axis = p<sub>T</sub>. DQM folder
  `Tracking/BranchValidator/recoTrack`.
- **`BranchTracksterRecoValidator`** — `ticl::Trackster`
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
    matched (efficiency ≈ 0) — degenerate by construction, not a real performance
    number.

    A flat `interestingPdgIds` list is a sufficient antichain **only for
    non-showering species**: restricting the track validator to **muons** on Z→μμ
    gives sensible numbers (merge-rate ≈ 0.02, efficiency ≈ 0.56), whereas a broader
    charged-stable list is still degenerate on e.g. TTbar, because pions, protons
    and electrons are deeply nested in the hadronic/EM cascade. The physically
    correct reference is detector-dependent — `CaloParticle`-like (the particle
    entering HGCAL) for calo, `TrackingParticle`-like (per charged track-maker) for
    tracking — i.e. the `BranchSelector` "interesting particles" antichain, which is
    not yet wired (see the [Roadmap](roadmap.md#validation)). For that reason the two
    modules are **opt-in** (`truthGraphRecoSideValidationSequence`), kept out of the
    default validation sequence; the muon configuration in
    `test/validateBranchRecoDQM_cfg.py` is the working demonstration.

**The plots macro** — `scripts/makeTruthGraphValidationPlots.py` is a self-contained
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

**The library wrapper** — `test/makeBranchValidationPlots.sh` automates the above
over a `runTruthRelvals.sh` library: it locates each workflow's harvested legacy
DQM file (`DQM_V0001_R*__Global__*__RECO.root`) and overlays a few representative
samples (TTbar / TenTau / ZMM by default; override with `SAMPLES`) in one set of
PNGs + `index.html`, the companion to `makeTruthGallery.sh`:

```bash
cmsenv
makeBranchValidationPlots.sh /path/library /path/branch_plots
```

## Build & checks

- `scram b` clean (only external `vecgeom` warnings).
- `scram b code-format` and `scram b code-checks` clean for the package.
- Unit tests (cppunit, `scram b runtests`): **31** assertions across 5 binaries —
  `TruthLogicalGraphPostProcessor_t` (17), `Branch_t` (4), `BranchHitAssociator_t`
  (4), `BranchSelector_t` (4), `LogicalGraphHitIndexBuilder_t` (2).
