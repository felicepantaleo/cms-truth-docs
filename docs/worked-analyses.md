# Worked analyses

Eleven complete analyses on the truth graph live in their own repository,
[github.com/felicepantaleo/TruthGraphAnalysis](https://github.com/felicepantaleo/TruthGraphAnalysis).
Each answers one physics question on one topology. Each exists twice, once in C++ and once
in python, and the two print the same lines on the same event. Each is tested against a
committed graph of one real event, so the repository fails if an interface change alters
an answer.

Read them for the idiom rather than for the physics. Between them they cover every part of
the interface a new analysis needs: finding the signal, following a decay, reading a level,
walking to the last copy of a radiating particle, using the production siblings, and
counting what a detector would see.

## The analyses

| Analysis | Topology | The question |
|---|---|---|
| Gun | single particle gun | per gun particle, how many reconstructable products does it have, and how many of its descendants reach the calorimeter |
| Resonance | Z to two electrons | which two leptons does the Z decay to, and how much invariant mass does final-state radiation take away |
| Vbf | vector boson fusion | what are the dijet mass and the rapidity gap of the two quarks that recoil against the Higgs |
| Ggf | gluon fusion Higgs | what does the detector see of the Higgs, and which fraction of its energy is visible |
| Vh | Higgs with a vector boson | which vector boson was produced with the Higgs, and how did it decay |
| Top | top quark pair | for each top, is there a b, how did the W decay, and what class is the event |
| SingleTop | single top, t channel | what was produced with the top: the recoil quark, the associated W, or the b |
| Diboson | W pair | what is the mass of the boson pair, and how did each boson decay |
| HeavyFlavor | b hadrons | how far does each b hadron fly before it decays, and how many charm hadrons are below it |
| Tau | taus | how did each tau decay, in prongs and neutral pions, and how much energy is visible |
| Full | any event | what does the whole event hold, interaction by interaction |

## Run one

The repository is a set of CMSSW packages, so it builds and tests with `scram`:

```bash
cd $CMSSW_BASE/src
git clone https://github.com/felicepantaleo/TruthGraphAnalysis.git TruthGraphAnalysis
scram b -j 8
scram b runtests
```

Then run one analysis in either language. The python side reads a JSON dump or an EDM
file; the C++ side runs as a CMSSW module:

```bash
python3 TruthGraphAnalysis/Tau/py/tau.py TruthGraphAnalysis/Common/fixtures/tentau.json
cmsRun TruthGraphAnalysis/Common/test/runExample_cfg.py step3.root --example Tau
```

The Tau analysis prints one line per tau and then a count of each decay mode. On the
committed ten-tau event, the first two lines and the summary are:

```
tau -15 E 113.18 GeV: 1prong0pi0, reco mode 0, 1 prongs 0 pi0 0 photons, visible energy 0.40
tau 15 E 113.18 GeV: 1prong0pi0, reco mode 0, 1 prongs 0 pi0 0 photons, visible energy 0.02
...
mode 1prong0pi0: 2
mode 1prong1pi0: 2
mode 3prong0pi0: 3
mode 3prong1pi0: 1
mode electron: 2
```

`reco mode` is the number `reco::PFTau::hadronicDecayMode` gives the same decay, so a truth
decay mode can be compared directly with a reconstructed one.

## What each analysis is made of

```
<Analysis>/
  README.md              the question, how to run it, the expected output
  cpp/<Analysis>.cc      run(graph, out): the analysis as a free function
  cpp/<Analysis>Plugin.cc  an EDAnalyzer that runs it in cmsRun
  py/<analysis>.py       the same analysis in python
  test/                  the two tests and the expected output they both match
```

Keeping the analysis in a free function, away from the framework module, is what lets the
same code run on a JSON dump in a test and on an EDM file in a job.

## Two things they will teach you

**A radiating particle carries its decay on its last copy.** A generator records a W that
emits a photon as a chain of copies of the same W. Asking the first copy for its children
returns another copy, not the decay. `Particle::lastCopy()` walks to the end of the chain.
The Resonance analysis shows the size of the effect: the two decay legs of the Z reproduce
its mass exactly, 87.25 GeV, while the same leptons after radiation give 75.91 GeV.

**A level is not a substitute for asking the right question.** The Vbf analysis originally
took the two highest-momentum members of the parton-jet level as the tagging quarks. That
level also holds the decay quarks of a hadronic Higgs decay, which are often the hardest
ones, so on a top quark pair event the same code confidently reported the two b quarks from
the top decays. It now asks for the production siblings of the Higgs, which is the question
it meant.
