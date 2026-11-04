# Adds the candidate dumper to a .88 step3 configuration.
import FWCore.ParameterSet.Config as cms


def addDumper(process, output):
    assoc = process.truthBranchTracksterAssociators
    process.truthAdaptiveCandidateDumper = cms.EDAnalyzer(
        "TruthAdaptiveCandidateDumper",
        graph=cms.InputTag("truthLogicalGraphProducer"),
        assignable=cms.InputTag("truthBranchTargets", "assignableRoots"),
        associator=cms.string("truthBranchTracksterAssociators"),
        recoCollections=assoc.recoCollections,
        output=cms.string(output),
    )
    process.truthAdaptiveDump = cms.EndPath(process.truthAdaptiveCandidateDumper)
    if process.schedule is not None:
        process.schedule.append(process.truthAdaptiveDump)
    return process
