# Tutorial: the adaptive branch associator on single electron and single pion

Associate reco tracksters to MC-truth-graph branches, including the **adaptive-level**
match, on single-electron and single-pion samples in the HGCAL acceptance: no pileup,
Run4 **D122** geometry.

All commands are single-thread and assume an el8 node with CVMFS.

## 1. Release and branch

```bash
export SCRAM_ARCH=el8_amd64_gcc13
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

- The base MC-truth-graph packages (`SimDataFormats/TruthInfo`, `PhysicsTools/TruthInfo`)
  are already in this IB; the merge adds the default-on wiring, the `Calo` channel
  rename, and the adaptive associator.
- Compile on one socket only.
- The customise used below, `PhysicsTools/TruthInfo/python/addAdaptiveAssociator.py`,
  ships with the branch. Nothing to create by hand.

## 2. Single electron in HGCAL (no PU, D122)

Three steps: GEN-SIM, DIGI (the truth graph is built here automatically by the era),
then RECO with tracksters plus the associator.

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

The `...Adaptive` maps are the point of this associator. For each trackster it walks up
the truth graph and keeps the single level minimizing

```
score + adaptiveReverseWeight * reverseScore
```

`score` falls as the branch climbs (it covers more of the trackster); `reverseScore`
rises as the branch spreads into energy the trackster does not have. Levels whose
contamination exceeds `adaptiveMaxReverseScore` are rejected; if that empties the
candidate set, the ceiling is ignored and the global minimum is returned. The climb is
capped at physical particles: it never selects or crosses a bare parton, diquark,
string/cluster node, or electroweak boson.

So for a clean single electron the adaptive level is the electron itself, and for a
charged pion it is the pion; a converted photon or a decaying particle is where the
climb starts to pay off, since the adaptive level is the merged parent rather than the
individual daughters.

## 5. Tuning

Both knobs are arguments of the customise:

```bash
--customise PhysicsTools/TruthInfo/addAdaptiveAssociator.addAdaptiveAssociator \
--customise_commands "process.tracksterToTruthBranch.adaptiveReverseWeight = 2.0; \
process.tracksterToTruthBranch.adaptiveMaxReverseScore = 0.6"
```

- `adaptiveReverseWeight` (default 1.0): how hard the climb is penalized for spreading.
  Larger values keep the match lower in the graph.
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

The products are `ticl::AssociationMap<ticl::mapWithSharedEnergyAndScore>`. Read them
from a compiled `EDAnalyzer`: bare FWLite/cppyy cannot instantiate this template
reliably. Each entry gives the branch key (the root particle index in the
`truth::Graph`), the shared energy, and the normalized score.

## Notes and caveats

- **No pileup**: the DIGI step has no `--pileup`, so these are clean single-particle
  events. The truth graph is still built, from the signal `g4SimHits`.
- **Truth scope**: the default is the full detector (calo + MTD + muon + tracker). This
  associator uses only the `Calo` channel, so the scope does not change its result.
- **Consume, do not rebuild**: `truthLogicalGraphProducer` and
  `truthLogicalGraphHitIndexProducer` are NOT scheduled at RECO; their products come
  from the DIGI file. If you see them as modules in the RECO config, something is
  rebuilding the truth and the association will be signal-only.
- **Validation state**: build, unit tests, and the RECO config composition (associator
  scheduled, inputs produced, products kept) are verified. Run the three steps once on
  a couple of events and confirm the maps are non-empty before scaling up.
