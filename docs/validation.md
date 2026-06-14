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

## Build & checks

- `scram b` clean (only external `vecgeom` warnings).
- `scram b code-format` and `scram b code-checks` clean for the package.
- Unit tests (cppunit, `scram b runtests`): **31** assertions across 5 binaries —
  `TruthLogicalGraphPostProcessor_t` (17), `Branch_t` (4), `BranchHitAssociator_t`
  (4), `BranchSelector_t` (4), `LogicalGraphHitIndexBuilder_t` (2).
