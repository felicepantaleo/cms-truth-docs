# Adaptive associator tuner

`docs/assets/associator-tuner/index.html` is the page of `docs/associator-tuner.md`. It loads one JSON file per sample and collection from `docs/assets/associator-tuner/data/`.

- `plugin/`: `TruthAdaptiveCandidateDumper`, which writes every candidate of every trackster with both scores, as one JSON object per event. It reads the `Fixed` and `TruthToReco` maps of `truthBranchTracksterAssociators`, so the associator does not change.
- `addDumper.py`: adds the dumper to a configuration.
- `run.sh`: RECO, the offline associators and the dumper on a step2 file with the truth graph. The file does not need TrackingParticles.
- `pack.py`: checks the rule against the `AdaptiveTight` and `AdaptiveNominal` maps, checks the reduced candidate list against the full list, and writes the data files. It exits with 1 if any comparison differs.

## Make the data for a sample

In a CMSSW area with the four truth packages:

    mkdir -p $CMSSW_BASE/src/UserCode/AdaptiveTuner/plugins
    cp tools/associator-tuner/plugin/* $CMSSW_BASE/src/UserCode/AdaptiveTuner/plugins/
    (cd $CMSSW_BASE/src && cmsenv && numactl -N 0 -m 0 scram b -j 16)

    mkdir work && cd work
    <repo>/tools/associator-tuner/run.sh /path/to/step2.root ExtendedRun4D122 20
    cat DONE    # exit=0
    python3 <repo>/tools/associator-tuner/pack.py candidates.jsonl --name mysample --label "My sample, 20 events" --out <repo>/docs/assets/associator-tuner/data/mysample

Then add the sample and its collections to `SAMPLES` at the top of the script in `index.html`. Use `--skip` to leave out a large collection: `pack.py` still checks it. `index.html#mysample` opens that sample. A PU200 event adds about 1 MB per collection, so keep the repository small.

Run `pack.py` under the python of a CMSSW environment, which has numpy. It takes about 2 minutes for 12 PU200 events.
