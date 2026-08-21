# Tutorial: the adaptive branch associator on single electron and single pion

Associate reco tracksters to truth-graph branches, including the **adaptive-level**
match. The samples are single-electron and single-pion in the HGCAL acceptance.
There is no pileup, and the geometry is Run4 **D122**.

All commands are single-thread and need CVMFS.

## 1. Release and branch

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh

cmsrel CMSSW_20_1_X_2026-07-22-2300
cd CMSSW_20_1_X_2026-07-22-2300/src
cmsenv

git cms-init
# One merge brings everything: truth-adaptive-associator is stacked on the
# "MC-truth graph by default for Run4" branch, so this single topic pulls in both
# the default-on truth graph and the adaptive associator.
git cms-merge-topic felicepantaleo:truth-adaptive-associator

scram b -j 8
```

Notes:

- Do not set `SCRAM_ARCH` by hand. `cmsrel` picks the architecture that matches
  your machine. This IB is built for both `el8_amd64_gcc13` and `el9_amd64_gcc13`.
  If your OS is not one of those, first run inside the matching CMS container, for
  example `cmssw-el8` or `cmssw-el9`. Then follow the same commands.
- The base truth-graph packages (`SimDataFormats/TruthInfo`,
  `PhysicsTools/TruthInfo`) are already in this IB. The merge adds the default-on
  wiring, the `Calo` channel rename, and the adaptive associator.
- Compile on one socket only.
- The customise used below is
  `PhysicsTools/TruthInfo/python/addAdaptiveAssociator.py`. It ships with the
  `truth-adaptive-associator` development branch this tutorial merges, so you
  create nothing by hand. It is not in the upstream pull requests: those carry
  the `SimGeneral/TruthGraphAssociatorProducers` associators, which schedule
  three working points per collection instead of this standalone producer.

## 2. Single electron in HGCAL (no PU, D122)

There are three steps: GEN-SIM, DIGI, then RECO with tracksters plus the
associator. The era builds the truth graph automatically at the DIGI step.

```bash
# 2a. GEN-SIM: single electron, 1.7 < |eta| < 2.7 (HGCAL), pt 15 GeV
cmsDriver.py SingleElectronPt15Eta1p7_2p7_cfi \
  -s GEN,SIM -n 10 \
  --conditions auto:phase2_realistic_T35 --beamspot DBrealisticHLLHC \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM --eventcontent FEVTDEBUG \
  --fileout file:ele_step1.root

# 2b. DIGI + L1 + RAW, no pileup. The truth graph and the unresolved hit index are
#     built and persisted here BY DEFAULT (enableTruth is in the era): no extra option.
cmsDriver.py step2 \
  -s DIGI:pdigi_valid,L1TrackTrigger,L1,L1P2GT,DIGI2RAW,HLT:@relvalRun4 -n 10 \
  --conditions auto:phase2_realistic_T35 \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM-DIGI-RAW --eventcontent FEVTDEBUGHLT \
  --filein file:ele_step1.root --fileout file:ele_step2.root

# 2c. RECO: tracksters plus the adaptive associator
cmsDriver.py step3 \
  -s RAW2DIGI,L1Reco,RECO -n 10 \
  --conditions auto:phase2_realistic_T35 \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM-RECO --eventcontent FEVTDEBUGHLT \
  --filein file:ele_step2.root --fileout file:ele_step3.root \
  --customise PhysicsTools/TruthInfo/addAdaptiveAssociator.addAdaptiveAssociator
```

## 3. Single pion in HGCAL (no PU, D122)

Same three steps with the charged-pion gun:

```bash
cmsDriver.py SinglePiPt25Eta1p7_2p7_cfi \
  -s GEN,SIM -n 10 \
  --conditions auto:phase2_realistic_T35 --beamspot DBrealisticHLLHC \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM --eventcontent FEVTDEBUG \
  --fileout file:pi_step1.root

cmsDriver.py step2 \
  -s DIGI:pdigi_valid,L1TrackTrigger,L1,L1P2GT,DIGI2RAW,HLT:@relvalRun4 -n 10 \
  --conditions auto:phase2_realistic_T35 \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM-DIGI-RAW --eventcontent FEVTDEBUGHLT \
  --filein file:pi_step1.root --fileout file:pi_step2.root

cmsDriver.py step3 \
  -s RAW2DIGI,L1Reco,RECO -n 10 \
  --conditions auto:phase2_realistic_T35 \
  --geometry ExtendedRun4D122 --era Phase2C26I13M9 \
  --datatier GEN-SIM-RECO --eventcontent FEVTDEBUGHLT \
  --filein file:pi_step2.root --fileout file:pi_step3.root \
  --customise PhysicsTools/TruthInfo/addAdaptiveAssociator.addAdaptiveAssociator
```

## 4. What comes out

```bash
edmDumpEventContent ele_step3.root | grep -i tracksterToTruthBranch
```

Four association products per trackster collection (here `ticlTrackstersCLUE3DHigh`):

| Product | Meaning |
|---|---|
| `ticlTrackstersCLUE3DHighToTruthBranch` | trackster to branch, fixed-level (every branch root) |
| `TruthBranchToticlTrackstersCLUE3DHigh` | reverse, branch to trackster |
| `ticlTrackstersCLUE3DHighToTruthBranchAdaptive` | trackster to its single adaptive-level branch |
| `TruthBranchToticlTrackstersCLUE3DHighAdaptive` | reverse of the adaptive match |

The `...Adaptive` maps are the point of this associator. For each trackster the
associator walks up the truth graph. It keeps the single level that minimizes

```
score + adaptiveReverseWeight * reverseScore
```

`score` falls as the branch climbs, because the branch covers more of the
trackster. `reverseScore` rises as the branch spreads into energy that the
trackster does not have. The associator rejects levels whose contamination exceeds
`adaptiveMaxReverseScore`. If that empties the candidate set, it ignores the
ceiling and returns the global minimum. The climb stops at physical particles: it
never selects or crosses a bare parton, diquark, string/cluster node, or
electroweak boson.

So for a clean single electron the adaptive level is the electron itself, and for a
charged pion it is the pion. The climb becomes useful for a converted photon or a
decaying particle. There the adaptive level is the merged parent, not the
individual daughters.

## 5. Tuning

Both parameters are arguments of the customise:

```bash
--customise PhysicsTools/TruthInfo/addAdaptiveAssociator.addAdaptiveAssociator \
--customise_commands "process.tracksterToTruthBranch.adaptiveReverseWeight = 2.0; \
process.tracksterToTruthBranch.adaptiveMaxReverseScore = 0.6"
```

- `adaptiveReverseWeight` (default 1.0): how much the associator penalizes the
  climb for spreading. Larger values keep the match lower in the truth graph.
- `adaptiveMaxReverseScore` (default 1.0): the contamination ceiling per level.

To associate more collections, call the customise from your own snippet:

```python
from PhysicsTools.TruthInfo.addAdaptiveAssociator import addAdaptiveAssociator
process = addAdaptiveAssociator(
    process,
    tracksterCollections=("ticlTrackstersCLUE3DHigh", "ticlTracksterLinks"),
)
```

## 6. Reading the maps

The products are `ticl::AssociationMap<ticl::mapWithSharedEnergyAndScore>`. Read
them from a compiled `EDAnalyzer`, because bare FWLite/cppyy cannot instantiate
this template reliably. Each entry gives the branch key (the root particle index in
the `truth::Graph`), the shared energy, and the normalized score.

`AdaptiveAssociationDumper` ships with this branch and prints them directly:

```python
# dump.py
import FWCore.ParameterSet.Config as cms
process = cms.Process("DUMP")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("PoolSource",
                            fileNames=cms.untracked.vstring("file:ele_step3.root"))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))
process.d = cms.EDAnalyzer(
    "AdaptiveAssociationDumper",
    fixed    = cms.InputTag("tracksterToTruthBranch",
                            "ticlTrackstersCLUE3DHighToTruthBranch"),
    adaptive = cms.InputTag("tracksterToTruthBranch",
                            "ticlTrackstersCLUE3DHighToTruthBranchAdaptive"),
)
process.p = cms.Path(process.d)
```

```bash
cmsRun dump.py
```

Output on a single-electron event (5 events, D122, no PU):

```
=== event 1 ===
FIXED   [ticlTrackstersCLUE3DHighToTruthBranch]: 3 tracksters, 3 with >=1 match
    trackster 0 -> branch 1  sharedEnergy=585      score=0.00340715
    trackster 0 -> branch 7  sharedEnergy=99.4849  score=0.792751
    ...
    trackster 2 -> branch 0  sharedEnergy=666      score=1.3336e-16
ADAPTIVE[ticlTrackstersCLUE3DHighToTruthBranchAdaptive]: 3 tracksters, 3 with >=1 match
    trackster 0 -> branch 1  sharedEnergy=585      score=0.00340715
    trackster 1 -> branch 1  sharedEnergy=46       score=0.0212766
    trackster 2 -> branch 0  sharedEnergy=666      score=1.3336e-16
```

Read it like this. The FIXED map ranks every candidate branch per trackster, with
shared energy falling and score rising. The ADAPTIVE map keeps exactly **one**
branch per trackster, the level that best matches it. A low score means a good
match.

## 7. What to expect: electron versus pion

We ran both samples end to end on this branch (5 events each, D122, no PU). Every
trackster gets a match in both samples. What differs is the **number of candidate
branches**. Understand this difference before you interpret your own plots:

| Sample | Distinct candidate branches per event |
|---|---|
| single electron | 15, 24, 19, 15, 20 |
| single pion | 2, 2, 2, 2, 17 |

The gun fires one particle per endcap, so **2** is the floor: one branch per primary.

- The **electron** radiates bremsstrahlung in the tracker. Those photons cross the
  tracker-calorimeter boundary themselves, so each one becomes its own branch root.
  One electron therefore produces a whole family of candidate branches. This is why
  the electron tracksters have long ranked candidate lists.
- The **pion** in events 1 to 4 crosses the boundary as a single particle and
  showers *inside* the calorimeter. The simulation creates its shower daughters past
  the boundary, so they are not roots. They are subgraph hits of the pion branch.
  This gives exactly 2 branches. Event 5 (17 branches) is the different case. That
  pion interacted early, upstream of the calorimeter, so its secondaries crossed the
  boundary and became roots.

Consequence for the adaptive level: for a clean single particle the adaptive match
coincides with the best fixed-level match. There is nothing to climb to. The
adaptive climb is useful in **merged** topologies. There several roots belong to one
physical object, and the right label is their common parent. Examples are a pi0
whose two photons are separate roots, an electron plus its brem photons, and an
early pion interaction. Test the climb there, not on a clean pion.

## 8. Checking the truth-to-rechit match per calorimeter

The association matches truth to reco by `DetId`. It therefore works only where the
hit index stores the same `DetId` that the reco rechits use.
`CaloRecHitMatchAnalyzer` checks exactly that, per calorimeter. It reports how many
index cells, and how much index sim energy, it finds in the HGCAL, ECAL barrel and
HBHE reco rechit collections.

```python
# calomatch.py
import FWCore.ParameterSet.Config as cms
process = cms.Process("CALOMATCH")
process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("PoolSource",
                            fileNames=cms.untracked.vstring("file:pi_step3.root"))
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(3))
process.m = cms.EDAnalyzer("CaloRecHitMatchAnalyzer")
process.p = cms.Path(process.m)
```

```bash
cmsRun calomatch.py
```

Output on a 100 GeV pion in the HGCAL acceptance:

```
=== event 1: reco rechits  HGCAL=21278  ECAL(EB)=1419  HCAL(HBHE)=4
    HGCAL EE  : cells 3800/4444 (85.5%)   simE 3.3966/3.4389 (98.8%)
    HGCAL HSi : cells  643/906  (71.0%)   simE 0.2103/0.2211 (95.1%)
    HGCAL HSc : cells   47/922  ( 5.1%)   simE 0.0779/0.0977 (79.7%)
```

**Read the energy column, not the cell column.** A calorimeter cell with a sim
deposit below the rechit threshold has no rechit to match. Single-particle showers
leave a large tail of such cells. This is why the cell fractions are much lower than
the energy fractions everywhere, including channels that work correctly. A channel
is working when the matched sim ENERGY is high, about 80% or more. A channel whose
energy fraction is near zero **while it holds real energy** is a genuine `DetId`
mismatch.

Choose a sample that puts energy where you want to test. An endcap particle
exercises HGCAL, but it leaves ECAL barrel and HCAL almost empty, so their fractions
there are meaningless. A barrel particle exercises ECAL barrel and HCAL. One example
is `SinglePiPt100_pythia8_cfi` with
`process.generator.PGunParameters.MinEta = -1.0` and `MaxEta = 1.0`. Reference
values measured on D122 with no pileup: HGCAL EE 99%, HGCAL HSi 95 to 98%, HGCAL HSc
80 to 92%. ECAL barrel is 90 to 98%, and HCAL barrel is 89 to 92%.

## Notes and caveats

- **No pileup**: the DIGI step has no `--pileup`, so these are clean single-particle
  events. The code still builds the truth graph, from the signal `g4SimHits`.
- **Truth scope**: the default is the full detector (calo + MTD + muon + tracker).
  This associator uses only the `Calo` channel, so the scope does not change its
  result.
- **Consume, do not rebuild**: `truthLogicalGraphProducer` and
  `truthLogicalGraphHitIndexProducer` are NOT scheduled at RECO. Their products come
  from the DIGI file. If you see them as modules in the RECO config, something is
  rebuilding the truth, and the association will be signal-only.
- **Validation state**: we ran both chains, single electron and single pion, end to
  end on this branch (5 events each, D122, no PU). All steps exit 0. The job writes
  the four association products, and the maps are populated: every trackster is
  matched, with exactly one adaptive branch each. Build and unit tests pass.
