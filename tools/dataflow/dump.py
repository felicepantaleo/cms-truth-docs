"""Dump the truth modules of cmsRun configurations to JSON: label, type, scheduled or not,
input tags and the python dump of each module.

Usage, in a CMSSW environment: OUT=<out.json> python3 dump.py <plugin-types.txt> <step cfg.py> ...
A module is kept when its type is in plugin-types.txt (the plugins of the four truth packages),
or when it is a DQMGenericClient of a truth folder. The truth accumulator of process.mix is kept
under the label mix.<name>.
"""
import importlib.util
import json
import os
import sys

import FWCore.ParameterSet.Config as cms

types = set(open(sys.argv[1]).read().split())


def tags(pset, pre=""):
    r = []
    for n in pset.parameterNames_():
        v = getattr(pset, n)
        if isinstance(v, cms.InputTag):
            r.append((pre + n, v.configValue().strip("'")))
        elif isinstance(v, cms.VInputTag):
            r += [(f"{pre}{n}[{i}]", (x.configValue() if hasattr(x, "configValue") else str(x)).strip("'")) for i, x in enumerate(v)]
        elif isinstance(v, cms.PSet):
            r += tags(v, pre + n + ".")
        elif isinstance(v, cms.VPSet):
            for i, p in enumerate(v):
                r += tags(p, f"{pre}{n}[{i}].")
    return r


out = {}
for cfg in sys.argv[2:]:
    cfg = os.path.abspath(cfg)
    d = os.path.dirname(cfg)
    sys.path.insert(0, d)
    os.chdir(d)
    spec = importlib.util.spec_from_file_location("c", cfg)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    p = m.process
    sched = set()
    for pth in list(p.paths_().values()) + list(p.endpaths_().values()):
        sched |= set(pth.moduleNames())
    step = os.path.basename(cfg).split("_")[0]
    mods = {}
    for coll in (p.producers_(), p.analyzers_(), p.filters_()):
        for lab, mod in coll.items():
            t = mod.type_()
            if t in types or (t == "DQMGenericClient" and "ruth" in str(getattr(mod, "subDirs", ""))) or "ruth" in t:
                mods[lab] = dict(type=t, sched=lab in sched, tags=tags(mod), dump=mod.dumpPython()[:3000])
    if hasattr(p, "mix"):
        for n in p.mix.digitizers.parameterNames_():
            ps = getattr(p.mix.digitizers, n)
            if hasattr(ps, "accumulatorType") and ps.accumulatorType.value() in types:
                mods["mix." + n] = dict(type=ps.accumulatorType.value(), sched=True, tags=tags(ps), dump=ps.dumpPython()[:3000])
    out[step] = mods
    sys.path.pop(0)
json.dump(out, open(os.environ["OUT"], "w"), indent=1)
