---
hide:
  - navigation
  - toc
---

# Tune the adaptive associator

Each trackster answers with the candidate that minimises `score + adaptiveReverseWeight * reverseScore`, among the candidates with `reverseScore` at or below `adaptiveMaxReverseScore`. If the ceiling rejects all candidates, the unconstrained minimum answers. See [Match reconstruction to truth](adaptive-associator.md) for the definitions.

Move the sliders to run this rule again on the real candidates of every trackster. Select a trackster to see its candidates in the plane of `score` against `reverseScore`.

<iframe src="../assets/associator-tuner/index.html" title="Adaptive associator tuner" loading="lazy"
        style="width: 100%; height: 1100px; border: 1px solid var(--md-default-fg-color--lightest);"></iframe>

[Open the tuner in a full window](assets/associator-tuner/index.html){ target="_blank" }. The PU200 sample loads about 10 MB when you select it.

## How to read it

- `fakerate` and `nocandidate` read the `Fixed` map, so they do not depend on the working point and are not on the page.
- The quantities that move are the purity and the truth coverage of the pick, the strict match (`score < 0.6`), the tracksters that share a pick, the level and the type of the pick, the pileup share and the energy response.
- Purity is a property of the truth definition, not a figure of merit by itself.
- The energy response uses the raw trackster energy. Compare it between working points. Do not read it as a calibration.

## Sources and check

- TTbar, no pile-up, D122, 20 events, all offline trackster collections. QCD, PU200, D127, 12 events, `ticlCandidate` and `ticlTrackstersCLUE3DHigh`. Default TICL configuration.
- Code: `CMSSW_20_1_X_2026-11-02-1100` with the branch of pull request 52380 at `49aa56bff1d`.
- The argmin of `tools/associator-tuner/pack.py` gives the same particle as the `AdaptiveTight` and `AdaptiveNominal` maps of the same job, for all 24594 tracksters of the TTbar sample and all 393428 tracksters of the QCD sample. The page repeats this check for the loaded collection when it loads and shows the result under "Provenance and limits".
- The page keeps only the candidates that can answer. A candidate is removed when an earlier candidate has both scores lower or equal. On a scan of working points the reduced list and the full list gave the same particle in 984182 of 984182 comparisons.
- These samples are large enough to explore the behaviour. They are too small to fix a final value.

To make the data for other samples, see `tools/associator-tuner/README.md`.
