#!/bin/bash
# run.sh <step2 file> <geometry> <events>: RECO, the offline associators and the candidate dumper,
# in the current directory, on socket 0. Needs cmsenv. Writes DONE last.
set -u
S2=$1; GEO=$2; N=$3
HERE=$(cd "$(dirname "$0")" && pwd)
rm -f DONE candidates.jsonl
NUMA="numactl --cpunodebind=0 --membind=0"
$NUMA cmsDriver.py step3 -s RAW2DIGI,RECO --conditions auto:phase2_realistic_T35 --geometry "$GEO" --era Phase2C26I13M9 --procModifiers enableTruth --datatier AODSIM --eventcontent AODSIM -n "$N" --filein "file:$S2" --fileout file:step3.root --nThreads 16 --nStreams 4 --no_exec --python_filename cfg.py > driver.log 2>&1 || { echo "exit=driver $?" > DONE; exit 1; }
cat >> cfg.py <<PY

import importlib.util as _u
from SimGeneral.TruthGraphAssociatorProducers.customiseTruthGraphAssociators import _loadAssociators, _appendPath
_loadAssociators(process)
_appendPath(process, "truthAssocPath", process.truthGraphAssociatorsSequence)
_s = _u.spec_from_file_location("addDumper", "$HERE/addDumper.py")
_m = _u.module_from_spec(_s); _s.loader.exec_module(_m)
process = _m.addDumper(process, "candidates.jsonl")
for _n in list(process.outputModules_().keys()):
    _p = getattr(process, _n + "_step", None)
    if _p is not None and _p in process.schedule:
        process.schedule.remove(_p)
PY
$NUMA timeout 5400 cmsRun cfg.py > job.log 2>&1
echo "exit=$?" > DONE
