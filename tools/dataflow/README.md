# Data-flow page generator

`gen.py` writes `docs/assets/truth-dataflow.html`, the diagram of the page `docs/dataflow.md`.

- `input/config-34834.88.json`: the truth modules of the runTheMatrix workflow 34834.88, steps 2 to 4, made by `dump.py`.
- `input/plugin-types.txt`: the plugin names of the four truth packages, which `dump.py` selects.
- `input/timing-s2.json`, `input/timing-s3.json`: FastTimerService summaries of steps 2 and 3, reduced to label, type, events and real time.
- `spec.py`: the text of the page: stages, states, module descriptions, open items, pull requests, links into the docs.
- `template.html`: the page layout and the renderer. `gen.py` puts the data in place of `__DATA__`.

## Regenerate after a text change

Edit `spec.py`, then, from the repository root:

    python3 tools/dataflow/gen.py tools/dataflow/input/config-34834.88.json tools/dataflow/template.html \
        docs/assets/truth-dataflow.html tools/dataflow/input/timing-s3.json tools/dataflow/input/timing-s2.json

Give the step 3 timing first: both steps have a module `mix`, and the step 2 value must win.
`gen.py` stops with an error when a module reads an input tag that no card makes; add the card or a
`TAG_NODE` entry in `spec.py`.

## Regenerate for a new release

1. Run `runTheMatrix.py -w upgrade -l 34834.88` in the release.
2. Dump the configuration, in the CMSSW environment:

        OUT=tools/dataflow/input/config-34834.88.json python3 tools/dataflow/dump.py \
            tools/dataflow/input/plugin-types.txt <wf dir>/step2_*.py <wf dir>/step3_*.py <wf dir>/step4_*.py

3. Time steps 2 and 3: one thread, one stream, `process.load("HLTrigger.Timer.FastTimerService_cfi")`,
   `writeJSONSummary = True`, on one socket. Reduce the JSON to the four fields above.
4. Update the release, the date and the totals in `spec.py` (`FOOTER`, the cost items), and the pull-request states.
5. Regenerate, run the strict build, and look at the page.
