"""Write the truth data-flow page from dump.json, spec.py and the timing JSON files.

Usage: python3 gen.py <dump.json> <template.html> <out.html> [<timing.json> ...]
"""
import json
import sys

import spec

dump = json.load(open(sys.argv[1]))
template = open(sys.argv[2]).read()
out = sys.argv[3]

# Times in ms per event, by module label, from the FastTimerService JSON summaries.
times = {}
for path in sys.argv[4:]:
    t = json.load(open(path))
    for m in t["modules"]:
        if m.get("events"):
            times[m["label"]] = m["time_real"] / m["events"]

nodes = {}


def add(id_, **kw):
    n = dict(id=id_, title=kw.pop("title", id_), inputs=[], prs=[], issues=[], doc=[], steps=None, params=None, type="", text="")
    n.update(kw)
    nodes[id_] = n
    return n


for id_, kw in spec.NODES.items():
    add(id_, **kw)

conf = {**dump["step2"], **dump["step3"]}
conf["mix"] = dump["step2"]["mix.truthGraph"]

for lab in spec.STUDY_ASSOC + spec.HLT_ASSOC:
    add(lab, stage="hlt" if lab.startswith("hlt") else "assoc", status="hlt" if lab.startswith("hlt") else "study",
        type=conf[lab]["type"], text=spec.ASSOC_TEXT, steps=spec.ASSOC_STEPS, params=spec.ASSOC_PARAMS, doc=["assoc", "wp", "products"])
for lab in spec.STUDY_VAL + spec.HLT_VAL:
    hlt = lab.startswith("hlt")
    add(lab, stage="hlt" if hlt else "val", status="hlt" if hlt else "study", type=conf[lab]["type"], text=spec.VAL_TEXT, doc=["valreco", "dqm"])
for lab, kw in spec.DEFAULT_VAL.items():
    add(lab, stage="val", status="default", type=conf[lab]["type"], **kw)
add(spec.HLT_RECO, stage="hlt", status="ext", title="HLT collections", type="reco::Track, reco::Vertex, ticl::Trackster",
    text="hltGeneralTracks, hltOfflinePrimaryVertices, the HLT TICL candidates and tracksters, hltMergeLayerClusters, and the HLT HGCAL and PF rechits.")

# Inputs from the configuration dump.
for lab, n in nodes.items():
    if lab not in conf:
        continue
    for param, tag in conf[lab]["tags"]:
        tag = tag.strip('"')
        if not tag:
            continue
        label = tag.split(":")[0]
        if tag in spec.TAG_NODE:
            src = spec.TAG_NODE[tag]
        elif label in spec.TAG_NODE:
            src = spec.TAG_NODE[label]
        elif label in nodes:
            src = label
        elif label.startswith("hlt"):
            src = spec.HLT_RECO
        else:
            raise SystemExit(f"{lab}: no node for input {param} = {tag}")
        n["inputs"].append([param, tag, src])
    if "associator = cms.string('" in conf[lab]["dump"]:
        a = conf[lab]["dump"].split("associator = cms.string('")[1].split("'")[0]
        n["inputs"].append(["associator", a, a])

# The validators of the HLT customise name their associator by convention; the dump has it.
# Harvesting: one card per domain for its three DQMGenericClient modules.
harv = {}
for lab, x in dump["step4"].items():
    if not x["sched"] or "PostProcessor" not in lab:
        continue
    base = lab.replace("LevelCandidatePostProcessor", "").replace("TruthPostProcessor", "").replace("PostProcessor", "")
    harv.setdefault(base, []).append(lab)
for base, labs in sorted(harv.items()):
    id_ = base + "PostProcessor"
    add(id_, stage="harv", status="study", title=base + "*PostProcessor", type="DQMGenericClient x %d" % len(labs),
        text="Divides the booked numerators by the denominators: efficiency, fake rate, purity, and the per-level and level-candidate ratios.",
        params="; ".join(sorted(labs)), doc=["dqm"])
    nodes[id_]["inputs"].append(["subDirs", "DQM folders of " + base + "Validator", base + "Validator"])
add("makeTruthValidationPlots", stage="harv", status="study", title="makeTruthValidationPlots.py", type="script (Validation/TruthInfo)",
    text="Makes the plots and the gallery from the harvested DQM file. It merges all its input files, so an A/B needs one run per leg.",
    params="makeTruthValidationPlots.py --outputDir <dir> --sample <name> --title <t> --gallery <DQM file>", doc=["valreco"],
    inputs=[["DQM file", id_, id_] for id_ in nodes if id_.endswith("PostProcessor")])
nodes["eventContent"]["inputs"] = [["keep", x, x] for x in ("mix", "truthLogicalGraphProducer", "truthLogicalGraphHitIndexProducer")]
nodes["truthGraphMetadata"]["inputs"] = [["process history", x, x] for x in ("mix", "truthLogicalGraphProducer", "truthLogicalGraphHitIndexProducer")]

for number, title, mods, state in spec.PRS:
    for m in mods:
        nodes[m]["prs"].append(number)
mixTime = times.pop("mix", None)
if mixTime is not None:
    nodes["mix"]["issues"].insert(0, f"The whole mix module takes {mixTime:.0f} ms/event in the timing job. The truth accumulator is one of its digitizers and is not timed alone.")
for lab, n in nodes.items():
    n["time"] = None if n["status"] == "ext" else times.get(lab)
    n["doc"] = [[k, spec.DOC[k]] for k in n["doc"]]

edges, seen = [], set()
for lab, n in nodes.items():
    for param, tag, src in n["inputs"]:
        if (src, lab) in seen or src == lab:
            continue
        seen.add((src, lab))
        edges.append(dict(s=src, t=lab, common=src in spec.COMMON))

products = [
    ["TruthGraph", "mix", "", "mix", "FEVTDEBUGHLT, RECOSIM"],
    ["truth::Graph", "truthLogicalGraphProducer", "", "truthLogicalGraphProducer", "FEVTDEBUGHLT, RECOSIM"],
    ["truth::LogicalGraphHitIndex", "truthLogicalGraphHitIndexProducer", "", "truthLogicalGraphHitIndexProducer", "FEVTDEBUGHLT, RECOSIM"],
    ["std::vector<PCaloHit>, std::vector<PSimHit>, SimTrack, SimVertex", "mix", "mergedHGCHits, mergedEcalHits, mergedHcalHits, mergedTrackerHits, mergedMuonHits, mergedSimTracks, mergedSimVertices", "mix", "not kept"],
    ["std::vector<unsigned int>", "truthBranchTargets", "selectedRoots, denominatorRoots, assignableRoots, signalSeeds, signalSeedsNoSelection, <level>, <level>Eligibility", "truthBranchTargets", "not kept"],
    ["ticl::TICLAssociationMap", "<associator>", "<collection>RecoToTruth<WP>, <collection>TruthToReco", "allTrackToTruthBranchAssociators", "kept only with customiseTruthGraphAssociators"],
    ["truth::GraphMetadata (run product)", "truthGraphMetadata", "", "truthGraphMetadata", "kept by addTruthMetadata (#52350)"],
]

D = dict(nodes=nodes, edges=edges, stages=spec.STAGES, status=spec.STATUS, common=spec.COMMON, prs=spec.PRS, products=products,
         footer=spec.FOOTER)
html = template.replace("__DATA__", json.dumps(D, separators=(",", ":")))
open(out, "w").write(html)
print(f"{len(nodes)} nodes, {len(edges)} edges, {sum(1 for n in nodes.values() if n['time'] is not None)} timed")
