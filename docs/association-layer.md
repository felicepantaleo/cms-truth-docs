# The association layer

`SimGeneral/TruthGraphAssociatorProducers` turns the truth graph into association maps
between reconstructed objects and truth branches. `Validation/TruthInfo` turns those
maps into DQM plots. Both are offered upstream in cms-sw/cmssw#51829 and are not in
`CMSSW_20_1_X` yet.

## What runs, and when

The Run4 eras carry the `enableTruth` process modifier, so a standard Run4 validation
workflow schedules the whole chain with no customise:

- the association producers run in the prevalidation Path, from
  `truthGraphAssociatorsSequence`;
- the DQM analyzers run in the validation EndPath, from
  `truthBranchValidationSequence`;
- the harvesters run in HARVESTING, from `truthBranchHarvestingSequence`.

The HLT twins of each module are kept in separate sequences
(`truthGraphHltAssociatorsSequence`, `truthBranchHltValidationSequence`), because they
read HLT collections an offline reconstruction does not produce.

A job that wants the maps in its own output applies
`SimGeneral/TruthGraphAssociatorProducers/customiseTruthGraphAssociators.customiseTruthGraphAssociators`,
which schedules both flavours and adds the keep statements.

## The modules

| Module | cfi label | What it does |
|---|---|---|
| `TruthBranchTargetsProducer` | `truthBranchTargets` | The truth-side targets, once per event: `selectedRoots`, `assignableRoots`, the signal-seed denominators and one truth-to-reco denominator per level |
| `AllTrackToTruthBranchAssociatorsProducer` | `allTrackToTruthBranchAssociators` | Tracks, by shared tracker elements |
| `TruthBranchTracksterAssociatorsProducer` | `truthBranchTracksterAssociators` | TICL tracksters, by shared calorimeter cells |
| `AllVertexToTruthBranchAssociatorsProducer` | `allVertexToTruthBranchAssociators` | Primary vertices, through the track maps |
| `AllSecondaryVertexToTruthBranchAssociatorsProducer` | `allSecondaryVertexToTruthBranchAssociators` | Secondary vertices, through the track maps, against heavy-flavour decay vertices |

Every collection label lives in one place,
`python/truthGraphAssociationLabels_cff.py`, together with the working points and the
truth levels. The validation package reads the same file, so an analyzer cannot book a
folder whose denominator product does not exist.

## The products

Per configured collection, with `<key>` the collection label and any instance label
joined by an underscore:

- `<key>RecoToTruth<WorkingPoint>`, one per working point. Reco-driven: the score is
  reco-normalised, so `1 - score` is the reco purity.
- `<key>TruthToReco`, one per collection. Truth-driven, with no working point: the
  truth target is fixed a priori by the level, so no climb enters it.

All are `ticl::TICLAssociationMap`, sorted best first. Equal scores are ranked by the
tightest branch, so row [0] is the particle itself and not an ancestor of it.

## The working points

| Name | `adaptiveReverseWeight` | `adaptiveMaxReverseScore` | What it answers |
|---|---|---|---|
| `Fixed` | 0.0 | 0.0 | Not a climb: the map keeps every candidate root, best first. Its two numbers are unused. |
| `AdaptiveTight` | 1.0 | 0.6 | The weighted minimum among the candidates whose reverse score is at most 0.6, falling back to the unconstrained minimum when none is. |
| `AdaptiveNominal` | 1.0 | 1.0 | The unconstrained weighted minimum. The reverse score lies in [0, 1], so this ceiling never rejects anything. |

`AdaptiveTight` differs from `AdaptiveNominal` only when the unconstrained minimum
spreads past 0.6 and some other candidate does not, so the two agree on the large
majority of well matched objects and separate on the badly matched tail.

## Which particles may be an answer

An adaptive point answers only with a particle a detector could have seen. The
`assignableTargets` PSet of `truthBranchTargets` bars, each with its own flag:

- a synthetic particle, that is a connector or a signal stand-in;
- a particle produced at an artificial vertex;
- a beam particle, which has no production vertex;
- a parton;
- an electroweak boson, and anything in `extraBarredPdgIds`.

The barred roots stay in `selectedRoots` and in the `Fixed` map, because the levels made
of those particles need them as truth-side denominators, and the truth-driven direction
reads its pair scores from the first working point's map. Only the adaptive rows are
filtered. An object whose every candidate is barred gets no row and reads as unmatched,
rather than being assigned a particle no detector could see.

## The DQM package

`Validation/TruthInfo` holds one templated `TruthBranchRecoValidator` over tracks,
vertices, secondary vertices and tracksters, with `DQMGenericClient` harvesting. The
reco-driven metrics are booked per working point, the truth-driven ones per truth level.
See [Validation](validation.md) for the metric definitions and the measured numbers.
