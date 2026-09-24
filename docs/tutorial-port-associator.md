# Tutorial: port an existing associator

Many validation modules already match reconstruction to simulation. They read
`TrackingParticle`s or `CaloParticle`s, take an association map from a standard associator,
and then apply conditions of their own: an in-time particle, a charge, a production region,
a detector the particle must reach. This page shows how to move such a module to the truth
graph. It uses a real module as the example, the MTD track validation
`Validation/MtdValidation/plugins/MtdTracksValidation.cc`, and it ends with a measurement:
the port and the original run in the same job, on the same tracks, and give the same numbers.

The rule of a port is simple. The reconstruction side does not change. Only the questions
that the module asks of the truth change their source.

## Step 1: list the truth questions of your module

Read the module and write down every place where it reads truth. For
`MtdTracksValidation` there are seven.

| # | Question | Where the legacy module answers it |
|---|---|---|
| 1 | Which particle made this track? | `getMatchedTP`: the first in-time `TrackingParticle` of `trackingParticleRecoTrackAsssociation` (`QuickTrackAssociatorByHits`, 75% hit purity) |
| 2 | Is it from the in-time bunch crossing? | `tp.eventId().bunchCrossing() == 0` |
| 3 | Is it charged, and inside the eta and pt cuts? | `trkTPSelAll`: `tp.charge()`, `tp.eta()`, `tp.pt()` |
| 4 | Was it produced inside the MTD volume? | `trkTPSelAll`: `tp.parentVertex()->position()`, rho below 110 cm and abs(z) below 290 cm |
| 5 | Is it a generator final-state particle? | `trkTPSelLV`: `tp.status() == 1` |
| 6 | Which MTD sensors did it cross, directly or through a secondary, and when? | `mtdSimLayerClusterToTPAssociation`: the `MtdSimLayerCluster`s of the TP, with `hitProdType()` and `simLCTime()` |
| 7 | Is the MTD cluster on the track its own? | `mtdRecoClusterToSimLayerClusterAssociation`: a shared cell, a time pull below 10 and, in BTL, a reco over sim energy below 5; then the sim cluster is looked up in the TP's clusters |

Everything else in the module is reconstruction: the tracks, the track selection, the MTD
hits on the track, the track time. That part is copied unchanged.

## Step 2: answer each question with the graph

| # | Graph answer |
|---|---|
| 1 | The track map `generalTracksRecoToTruthFixed` of `AllTrackToTruthBranchAssociatorsProducer`. A row is sorted by score, and the score is 1 minus the purity, so a score of at most 0.25 is the 75% purity of the legacy associator. |
| 2 | `ParticleData::bunchCrossing() == 0`. |
| 3 | `Particle::threeCharge() != 0` and `ParticleData::momentum`. |
| 4 | The production vertex, `Graph::productionVertices(id)`. Its position is in cm and ns, so the conversion from seconds that the legacy module does with `simUnit_` is not necessary. |
| 5 | `ParticleData::status == 1`. |
| 6 | `LogicalGraphHitIndex::directHits(HitChannel::MTD, id)` and `directHitTimes(HitChannel::MTD, id)`: one hit per (sensor module, cell, category), with its energy and its earliest time. The category is the `hitProdType`: 0 direct, 1 secondary not saved, 2 looper, 3 back-scatter, 4 ETL rear face. |
| 7 | The same hits: `detId` is the sensor module and bits 0 to 23 of `recHitIndex` are the `(row, col)` of an `FTLCluster` pixel. A reco cluster is the particle's own when it shares a cell and passes the same time and energy cuts. |

In code, questions 1 to 5 are two short functions. This is the whole of question 1:

```cpp
std::optional<uint32_t> matchedParticle(TrackMap const& map, truth::Graph const& graph, unsigned int track) {
  for (auto const& element : map[track]) {
    if (element.score() > 0.25f)  // 1 - purity, sorted
      break;
    if (graph.particles()[element.index()].bunchCrossing() == 0)
      return element.index();
  }
  return std::nullopt;
}
```

Questions 6 and 7 read two parallel spans. The port groups the hits per (module,
category) into a `Deposit`, the counterpart of a `MtdSimLayerCluster`: summed energy,
energy-weighted time, and the cells.

```cpp
const auto hits = hitIndex.directHits(truth::HitChannel::MTD, particle);
const auto times = hitIndex.directHitTimes(truth::HitChannel::MTD, particle);
for (std::size_t i = 0; i < hits.size(); ++i) {
  const uint32_t module = hits[i].detId;                // sensor module
  const uint32_t category = hits[i].recHitIndex >> 24;  // 0 direct, 1 to 4 other
  const uint32_t cell = hits[i].recHitIndex & 0x00FFFFFFu;  // row << 16 | col
  const float time = times[i];                          // ns, earliest in the cell
}
```

BTL and ETL share this storage but not their physics. A BTL cell is a crystal, read like a
calorimeter, so the legacy rule also compares energies there. An ETL cell is a pixel, read
like a tracker, so a shared cell and a compatible time are enough. The port applies the
rule of each detector.

The legacy module needs three association products and a `TrackingParticle` collection for
these seven questions. The port needs one graph, one hit index and one track map.

## Step 3: check that the candidates cover your selection

This step is the one that is easy to miss. An associator can match a reco object only to a
candidate truth particle. The shared configuration makes a particle a candidate above
1 GeV (`truthBranchSelectorBlock.ptMin` in `truthGraphAssociators_cff.py`). The MTD
selection starts at 0.7 GeV.

A pion of 0.8 GeV is then not a candidate. Its track is not unmatched: it goes to an
ancestor of the pion, because the subgraph of that ancestor holds the same tracker hits,
with the same purity. The analysis then reads the properties of the wrong particle.

So clone the targets producer with a candidate floor below your own cut:

```python
process.mtdTruthBranchTargets = truthBranchTargets.clone()
process.mtdTruthBranchTargets.branchSelector.ptMin = 0.
process.mtdTrackToTruth = allTrackToTruthBranchAssociators.clone(
    recoCollections=["generalTracks"],
    targetsSrc=("mtdTruthBranchTargets", "selectedRoots"),
    assignableTargetsSrc=("mtdTruthBranchTargets", "assignableRoots"),
    workingPointNames=["Fixed"], adaptiveReverseWeight=[0.], adaptiveMaxReverseScore=[0.])
```

Do the same check for every cut of your module: eta, species, signal only. The associator
cuts must be looser than the analysis cuts, never tighter.

## Step 4: build the inputs that a default job does not have

The DIGI step writes the graph and the hit index with the tracker, calorimeter and muon
channels. The MTD channel is not in the default. It reads only the MTD sim clusters and
the MTD topology, so any job after mixing can build it with a second hit index producer
that fills only that channel:

```python
process.truthMtdHitIndex = truthLogicalGraphHitIndexProducer.clone(
    src="truthLogicalGraphProducer", rawSrc="mix", recHitMap="",
    subdetectors=cms.vstring("MTD"), trackerDigiSimLinks=[], simHitCollections=[])
```

The track map is not in a default job either. Step 3 schedules it.

## Step 5: run both in one job and compare

The complete port is the `Mtd` example of
[TruthGraphAnalysis](https://github.com/felicepantaleo/TruthGraphAnalysis/tree/main/Mtd).
Its customise adds the three producers and the analyser `MtdTracksGraphValidation`, which
books the monitor elements of `MtdTracksValidation` under the same names in
`MTD/TracksGraph`:

```bash
cmsDriver.py step3 ... --customise TruthGraphAnalysis/Mtd/customiseMtdGraphValidation.customise
cmsDriver.py step4 ... -s HARVESTING:@phase2Validation+@phase2
python3 TruthGraphAnalysis/Mtd/test/compareMtdPort.py DQM_V0001_R000000001__Global__CMSSW_X_Y_Z__RECO.root
```

Run the two modules in one job, not in two. Then the tracks, the MTD clusters and the
track times are the same objects, and a difference can come only from the truth.

## The result

Two samples, both ttbar at 14 TeV, Run4 D127, reconstructed with
`CMSSW_20_1_X_2026-09-23-1100` and the follow-up branch `truth-association-tie-descendant`
of PR 51829 merged on top (the same counts come out of `CMSSW_20_1_X_2026-09-13-2300`): 100 events without pileup, from the step2 file of workflow 37634.0, and 30
events with 5 interactions in each bunch crossing, with the MinBias of workflow 37640.0 as
pileup. The branch includes the pileup GEN payload, which gives a pileup particle its own
production time; without it that time was 0 and the pileup time residual of the port was
wider (BTL RMS 40.6 ps against 31.9 ps). Tracks with pt above 0.7 GeV; BTL is abs(eta) below 1.5. Both modules run in one
job on each sample.

| Category | No pileup: legacy | graph | 5 pileup: legacy | graph |
|---|---:|---:|---:|---:|
| BTL: tracks matched to truth | 3950 | 3975 | 1860 | 1872 |
| BTL: particle with direct hits | 2792 | 2782 | 1289 | 1286 |
| BTL: the first direct cluster on the track | 2512 | 2505 | 1106 | 1104 |
| BTL: another cluster on the track | 105 | 103 | 65 | 64 |
| BTL: ... a later direct cluster of it | 68 | 66 | 50 | 49 |
| BTL: ... not its cluster | 35 | 35 | 15 | 15 |
| BTL: no cluster on the track | 175 | 174 | 118 | 118 |
| BTL: particle with other hits only | 585 | 595 | 296 | 297 |
| BTL: particle without MTD hits | 573 | 598 | 275 | 289 |
| ETL: particle with MTD hits | 1853 | 1841 | 986 | 978 |
| ETL: correct cluster on the track | 1360 | 1395 | 725 | 742 |
| ETL: wrong cluster on the track | 204 | 162 | 103 | 80 |
| ETL: no cluster on the track | 289 | 284 | 158 | 156 |

The time residual of the tracks with a correct cluster, t0 minus the production time of
the particle, without pileup: BTL mean -9.5 ps and RMS 32.8 ps for the legacy module,
-9.4 ps and 32.6 ps for the port; ETL -8.4 ps and 34.8 ps against -8.3 ps and 34.9 ps.
With pileup: BTL -9.5 ps and 30.4 ps against -9.5 ps and 30.4 ps; ETL -3.4 ps and 31.1 ps
against -3.3 ps and 30.8 ps.

Every BTL category agrees within 2%, including the split into direct and other hits and
the rule "the first direct cluster in time", which the category and the time of each hit
make possible. Each remaining difference has a measured cause.

- **Tracks matched.** The two track associators match 25 more BTL tracks in 3950, 0.6%.
  These tracks go to "particle without MTD hits".
- **ETL correct and wrong.** Per pair of a track and one of its ETL clusters, the two
  modules agree on 2825 of 2883, 98.0%. In all 47 pairs that only the port calls the
  particle's own, the legacy reco-to-sim map attaches no sim cluster at all to that reco
  cluster, although a cell is shared. One cause is in the legacy associator
  (`MtdRecoClusterToSimLayerClusterAssociatorByHitsImpl`): it calls
  `std::set_intersection` on hit lists that are not sorted. Measured on 20 events, that
  misses 11 of 5828 ETL pairs within the time cut. In all 11 pairs that only the legacy
  module calls own, the two track associators chose different particles.

## What the as-released column showed

The first version of this port ran on PR 51829 alone. It found MTD hits for 10% fewer BTL
particles, 3029 against 3377. A diagnostic run on the same events traced all 357 of those
tracks to one cause. The track map assigned the track to the parent resonance of the pion
or kaon, a rho, a K* or a Lambda_c, which is a generator particle with no SimTrack and so
with no MTD hits. When the photons of the pi0 do not convert, the subgraph of the resonance
holds exactly the tracker cells of the pion. The two candidates then tie on the score and
on the reverse score, and the last rule of the sort took the lower particle id, the
ancestor. The follow-up branch ranks the particle with the larger generation first on an
exact tie.

## What the graph does not give yet

- **The grouping of hits into sim clusters.** The port groups a particle's hits per
  (module, category). The legacy accumulator also splits one group into several clusters
  when the cells are not adjacent. The port's energy and time for such a group are then
  those of the union, which makes the match slightly looser. On 20 ttbar events this
  concerns 855 of 13521 BTL groups, 6.3%, and 22 of 6192 ETL groups.
- **The wrong-cluster breakdown.** The legacy module picks the reason from the last sim
  cluster it looked at. The port uses the order "a later direct deposit, an other deposit,
  not its deposit". Both split the wrong tracks into the same three bins, but not always
  the same way.

## Porting a CaloParticle associator

The steps are the same for a calorimeter module. The questions change, and so do the
answers.

| Legacy | Graph |
|---|---|
| a `CaloParticle` | a member of the `caloBoundary` level; `truth::branchesAtLevel` gives the branches of any level; see [Choose a truth definition](tutorial-truth-definitions.md) |
| a `SimCluster` | a branch of a `caloBoundary` particle with a tighter closure; see [Replacing truth objects](replacing-truth-objects.md) |
| `hits_and_fractions()` | `LogicalGraphHitIndex::subgraphHits(HitChannel::Calo, id)` |
| a layer cluster or trackster association | the trackster map of `TruthBranchTracksterAssociatorsProducer` |

Check the candidate floor of step 3 for these too, and run the two modules in one job, as in
step 5, before you trust a number.
