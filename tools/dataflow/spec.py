"""Hand-written part of the truth data-flow page: states, texts, PRs and open items.

Module labels, types and input tags come from dump.json (configuration dump of the IB .88
workflow). Times come from the FastTimerService JSON files of the timing run.
"""

STATUS = {
    "default": ["Default", "Runs in every Run4 workflow whose era applies enableTruth (C17 eras, not premix, not FastSim)."],
    "study": ["Study only", "Runs only with customiseTruthBranchValidation, for example in the runTheMatrix .88 workflows."],
    "hlt": ["HLT study", "Runs only with customiseTruthHltValidation."],
    "pr": ["Open PR", "In an open pull request, not in the IB."],
    "ext": ["Outside truth", "A product of another package that a truth module reads."],
}

STAGES = [
    {"id": "in", "name": "GEN and SIM", "desc": "Generator record and Geant4 output, from the GEN-SIM step."},
    {"id": "digi", "name": "Build at DIGI", "desc": "The DIGI step builds the raw graph, the logical graph and the hit index while mixing runs."},
    {"id": "out", "name": "Output", "desc": "What the files keep. A RECO job reads the graph from its input file."},
    {"id": "reco", "name": "Reconstruction", "desc": "The reconstructed collections that the associators score."},
    {"id": "targets", "name": "Truth levels", "desc": "The truth particles of each level that can be an answer."},
    {"id": "assoc", "name": "Association", "desc": "Maps from each reco object to truth and back, per working point."},
    {"id": "val", "name": "Validation", "desc": "DQM plots, filled in the RECO job."},
    {"id": "hlt", "name": "HLT validation", "desc": "The same association and plots for the HLT collections."},
    {"id": "harv", "name": "Harvesting", "desc": "Ratios from the booked numerators and denominators, then the plot script."},
]

DOC = {
    "raw": "../data-model/#layer-1-truthgraph-raw",
    "logical": "../data-model/#layer-2-truthgraph-logical",
    "hitindex": "../data-model/#layer-3-truthlogicalgraphhitindex",
    "pileup": "../pileup/#phase-b-truthgraphaccumulator-the-production-route-merged-and-default-for-run4",
    "content": "../pileup/#event-content-compact-vs-full",
    "enable": "../usage/#enabling-the-truth-graph-in-a-job",
    "metadata": "../usage/#run-metadata",
    "genonly": "../usage/#a-graph-from-a-gen-only-job",
    "selroots": "../usage/#selecting-roots-at-production-time",
    "assoc": "../association-layer/",
    "wp": "../association-layer/#the-working-points",
    "assignable": "../association-layer/#which-particles-may-be-an-answer",
    "products": "../association-layer/#the-products",
    "levels": "../tutorial-truth-definitions/",
    "dqm": "../association-layer/#the-dqm-package",
    "valreco": "../validation/#reco-side-metrics-in-validationtruthinfo-current-generation-2026-08-01",
    "legacy": "../validation/#dqm-performance-plots-branch-vs-legacy-truth-objects",
    "cost": "../resource-cost/",
}

PRS = [
    # [number, title, modules, state]
    ["#52342", "Store TruthGraph::NodeRef kind in one byte", ["mix"], "Signed by dqm and generators. Core signature pending."],
    ["#52343", "Truth graph: add isInTime() to particles and vertices", ["truthLogicalGraphProducer"], "Fully signed."],
    ["#52344", "TruthInfo: small bug fixes", ["truthLogicalGraphProducer", "truthBranchTargets", "truthBranchTrackValidator"], "Generators signed. DQM pending."],
    ["#52345", "Drop invisible members from the truth level efficiency denominators", ["truthBranchTargets"], "DQM and generators pending."],
    ["#52346", "The hitless-subgraph pruning reads the MTD sim hits, and the DIGI hit index fills the MTD channel", ["truthLogicalGraphProducer", "truthLogicalGraphHitIndexProducer"], "Fully signed."],
    ["#52348", "Optional hit requirement for the truth-to-reco denominators", ["truthBranchTargets"], "Generators signed. DQM pending."],
    ["#52349", "A selection preset keeps the spectator pi0", ["truthLogicalGraphProducer"], "Fully signed."],
    ["#52350", "Truth graph in a GEN-only job, and run metadata of the graph", ["truthGraphMetadata", "truthLogicalGraphProducer"], "Generators pending."],
    ["#52319", "Truth: keep the calorimeter PFRecHits", ["eventContent"], "Fully signed."],
]

# Per module: text, algorithm steps, short parameter summary, doc link, open items.
NODES = {
    "generatorSmeared": dict(stage="in", status="ext", type="HepMC3 product", text="The generator event after the vertex smearing. The GEN half of the graph comes from it."),
    "g4SimHits": dict(stage="in", status="ext", type="OscarMTProducer", text="Geant4: SimTracks, SimVertices and the sim hits of every subdetector. In a pile-up job the mixing module reads the same collections from each pile-up event."),
    "mix": dict(stage="digi", status="default", title="mix (truthGraph accumulator)", type="MixingModule + TruthGraphAccumulator",
        text="Builds the raw TruthGraph of the signal and of every pile-up interaction, and merges their SimTracks, SimVertices and sim hits.",
        steps=["For each interaction (signal, then each pile-up event of each bunch crossing): read the HepMC event, the SimTracks and the SimVertices.",
               "Add GEN nodes and edges, then SIM nodes and edges. Link a SimTrack to its GenParticle by the HepMC barcode, keyed by (eventId, barcode).",
               "Collapse the GEN shower of the pile-up interactions (collapsePileupGen) and keep the listed pdgIds (collapsedGenKeptPdgIds).",
               "Merge the sim hits, SimTracks and SimVertices of all interactions into one collection each. The logical graph and the hit index read these merged collections."],
        params="pileupBunchCrossings = [0]; collapseGenShower = True; collapsePileupGen = True; collapseSignalGen = False; collapsedGenKeptPdgIds = [111]",
        doc=["raw", "pileup"],
        issues=["Computing cost gives the cost of the truth accumulator alone, from an A/B that removes it from the mix module."]),
    "truthLogicalGraphProducer": dict(stage="digi", status="default", type="TruthLogicalGraphProducer",
        text="Turns the raw graph into the logical particle-vertex graph, applies the GEN collapse and the hitless pruning, and sets the level flags of each particle.",
        steps=["Merge each GEN vertex with the SIM vertex at the same point (mergeGenSimVertices).",
               "Collapse the intermediate GEN particles (collapseIntermediateGenParticles) and keep the reconstructable pdgIds (111).",
               "Drop the SIM subgraphs that have no hit in the listed sim-hit collections (dropHitlessSimSubgraphs, default True).",
               "Add the artificial vertices and particles (VertexRole, ParticleRole), then set ParticleData::levelFlags."],
        params="mergeGenSimVertices = True; postProcessing.collapseIntermediateGenParticles = True; reconstructablePdgIds = [111]; keepStableSpectators = True; seedPdgIds = []",
        doc=["logical", "selroots"],
        issues=["In the IB the pruning does not read the MTD sim hits, so a SIM subgraph with MTD hits only is dropped (#52346 adds them).",
                "The pruning sees only the listed sim-hit collections. A particle whose hits are in a collection that is not listed is removed with no warning."]),
    "truthLogicalGraphHitIndexProducer": dict(stage="digi", status="default", type="TruthLogicalGraphHitIndexProducer",
        text="Stores the hit footprint of each logical particle: its own hits and the hits of its subgraph, per channel (Tracker, MTD, Calo, Muon).",
        steps=["Read the merged sim hits and the pixel digi-sim links.",
               "Key the calorimeter hits by DetId, the tracker hits by pixel cell, the muon hits by DetId.",
               "Relabel the HCAL DetIds (doHcalRelabelling).",
               "Store each hit once. A particle points to its direct hits and to the range of its subgraph."],
        params="subdetectors = [Calo, Muon, Tracker]; recHitMap = '' (no rechit index at DIGI); doHcalRelabelling = True",
        doc=["hitindex"],
        issues=["The MTD channel is empty in the IB: the MTD is not in subdetectors (#52346 fills it).",
                "recHitMap is empty at DIGI, so every Hit has recHitIndex = kInvalidRecHitIndex. A consumer matches by DetId."]),
    "simSiPixelDigis": dict(stage="digi", status="ext", type="Phase-2 tracker digitizer", text="The pixel and outer-tracker digi-sim links. The hit index uses them to key the tracker hits by cell."),
    "truthGraphMetadata": dict(stage="digi", status="pr", type="TruthGraphMetadataProducer",
        text="Writes one GraphMetadata product per run: build mode, pile-up bunch crossings, generator, selection preset, level names, hit-index channels and energy units.",
        steps=["Find each graph module (raw, logical, hit index) in the process history: this job first, then the earlier jobs, latest first.",
               "Take a job only if it made the product of that module.",
               "Copy the selection, pruning and hit-index parameters of that job into the product."],
        params="Added with addTruthMetadata (PhysicsTools/TruthInfo/python/customiseTruthMetadata.py). Also in a GEN-only job.",
        doc=["metadata", "genonly"],
        issues=["A job that reads a file without the raw TruthGraph gives buildMode Unknown, with a warning."]),
    "eventContent": dict(stage="out", status="default", title="FEVTDEBUGHLT, RECOSIM", type="output modules",
        text="Under enableTruth both event contents keep TruthGraph_mix, the truth::Graph and the LogicalGraphHitIndex. The merged sim hits are not kept. MINIAODSIM keeps no truth product.",
        params="keep *_truthLogicalGraphProducer_*_*; keep *_truthLogicalGraphHitIndexProducer_*_*; keep TruthGraph_mix_*_*",
        doc=["content"],
        issues=["The association maps are not in RECOSIM. customiseTruthGraphAssociators keeps them."]),
    "generalTracks": dict(stage="reco", status="ext", type="reco::Track", text="Offline tracks."),
    "offlinePrimaryVertices": dict(stage="reco", status="ext", type="reco::Vertex", text="Offline primary vertices."),
    "inclusiveSecondaryVertices": dict(stage="reco", status="ext", type="reco::Vertex", text="Inclusive secondary vertices."),
    "particleFlowClusterECAL": dict(stage="reco", status="ext", type="reco::PFCluster", text="ECAL barrel PF clusters."),
    "particleFlowClusterHCAL": dict(stage="reco", status="ext", type="reco::PFCluster", text="HCAL PF clusters."),
    "ticl": dict(stage="reco", status="ext", title="TICL tracksters", type="ticl::Trackster, TICLCandidate",
        text="ticlCandidate, ticlTracksterLinks, ticlTracksterLinksSuperclusteringDNN, ticlTrackstersCLUE3DHigh, ticlTrackstersRecovery, and the layer clusters hgcalMergeLayerClusters."),
    "legacyTruth": dict(stage="reco", status="ext", title="legacy truth", type="CaloParticle, SimCluster, TrackingParticle",
        text="mix:MergedCaloTruth and the cluster-to-TrackingParticle map (tpClusterProducer). The comparison validators read them."),
    "truthBranchTargets": dict(stage="targets", status="study", type="TruthBranchTargetsProducer",
        text="For each truth level, the particles that a reco object can be matched to, and the efficiency denominator of each level.",
        steps=["For each level in truthLevels, take the particles whose levelFlags bit is set.",
               "Apply branchSelector (pt > 1 GeV, |eta| < 4, kinematics on stable particles).",
               "selectedRoots: every cut of the selector except its pt floor. The track, cluster and trackster associators read it.",
               "denominatorRoots: every cut, plus the level targets. The vertex associators read it.",
               "assignableRoots: the particles that can be an answer at the adaptive working points (no beam particle, parton, electroweak boson or synthetic particle)."],
        params="12 levels: stableLegsFromInitialState, caloBoundary, stableDecayProducts, hardProcess, reconstructableFromSignal, underlyingEvent, partonJets, bHadrons, cHadrons, reconstructableFinalState, tauVisibleHadronic, tauVisibleLeptonic",
        doc=["levels", "assignable"],
        issues=["Every denominator must be an antichain: a set that holds a particle and its ancestor counts the energy twice.",
                "#52345 removes the invisible members from the denominators. #52348 adds an optional hit requirement."]),
}

ASSOC_TEXT = "Scores every reco object against every target branch by shared hits, and stores RecoToTruth maps per working point and one TruthToReco map per collection."
ASSOC_STEPS = ["Build a BranchHitAssociator over the target roots and the hit index.",
               "For each reco object, score the shared energy (calorimeter) or the shared hits (tracker) with each candidate branch.",
               "Fixed: every candidate root, best first, the assignable roots before the barred ones.",
               "AdaptiveTight: the weighted minimum among the assignable candidates whose reverse score is at most 0.6. AdaptiveNominal: the unconstrained weighted minimum.",
               "Store <collection>RecoToTruth<WP> and <collection>TruthToReco."]
ASSOC_PARAMS = "workingPointNames = [Fixed, AdaptiveTight, AdaptiveNominal]; adaptiveMaxReverseScore = [0, 0.6, 1.0]; adaptiveReverseWeight = [0, 1, 1]"
VAL_TEXT = "Books efficiency, fake rate, purity and resolution numerators and denominators per collection, truth level and working point."

STUDY_ASSOC = ["allTrackToTruthBranchAssociators", "allVertexToTruthBranchAssociators", "allSecondaryVertexToTruthBranchAssociators",
               "truthBranchPFClusterEcalAssociators", "truthBranchPFClusterHcalAssociators", "truthBranchTracksterAssociators"]
STUDY_VAL = ["truthBranchTrackValidator", "truthBranchVertexValidator", "truthBranchSecondaryVertexValidator",
             "truthBranchPFClusterEcalValidator", "truthBranchPFClusterHcalValidator", "truthBranchTracksterValidator"]
DEFAULT_VAL = {
    "truthGraphSummaryValidator": dict(text="Per interaction: how many interactions the graph holds, their sizes, the artificial vertices, and the members of each level, signal and pile-up apart.", doc=["legacy"], params="folder = TruthInfo/Graph"),
    "branchHGCalValidator": dict(text="For each CaloParticle and SimCluster, finds the branch that reproduces it and compares their calorimeter hits.", doc=["legacy"], params="folder = HGCAL/BranchValidator; minPt = 1.0; maxEta = 3.0",
        issues=["It runs by default and takes 206 ms/event in the timing job, 2.8% of the 7471 ms/event of the whole RECO job."]),
    "branchTrackingValidator": dict(text="For each track, checks that the branch match and the TrackingParticle match give the same logical particle.", doc=["legacy"], params="folder = Tracking/BranchValidator; minPt = 0.9; maxEta = 3.0",
        issues=["It runs by default and takes 154 ms/event in the timing job, 2.1% of the 7471 ms/event of the whole RECO job."]),
}
HLT_ASSOC = ["hltTrackToTruthBranchAssociators", "hltVertexToTruthBranchAssociators", "hltTruthBranchTracksterAssociators"]
HLT_VAL = ["hltTruthBranchTrackValidator", "hltTruthBranchVertexValidator", "hltTruthBranchTracksterValidator"]

# Map an input-tag label (or label:instance) to the node that makes it.
TAG_NODE = {
    "mix:MergedCaloTruth": "legacyTruth", "tpClusterProducer": "legacyTruth",
    "ticlCandidate": "ticl", "ticlTracksterLinks": "ticl", "ticlTracksterLinksSuperclusteringDNN": "ticl",
    "ticlTrackstersCLUE3DHigh": "ticl", "ticlTrackstersRecovery": "ticl", "hgcalMergeLayerClusters": "ticl",
}
HLT_RECO = "hltReco"
COMMON = ["truthLogicalGraphProducer", "truthLogicalGraphHitIndexProducer"]

FOOTER = ("Sources: the configuration of runTheMatrix workflow 34834.88 (TTbar 14 TeV, D122, no pile-up) in CMSSW_20_1_X_2026-10-27-2300: "
          "step2 (DIGI to HLT), step3 (RECO, VALIDATION, DQM) and step4 (HARVESTING). The HLT validation modules are defined in that configuration but not scheduled. "
          "Times: FastTimerService, mean real time per event of each module, on the same workflow and release, 20 events, 1 thread, 1 stream, one socket of patatrack-bg-01 (2026-11-01). The DIGI step takes 9464 ms/event and the RECO step 7471 ms/event in total. "
          "Pull-request states: GitHub, 2026-11-01.")
