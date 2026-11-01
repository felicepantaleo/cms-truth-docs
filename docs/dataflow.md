---
hide:
  - navigation
  - toc
---

# Data flow

The diagram shows every module that builds, keeps and uses the MC-truth graph, from the GEN and SIM products to the harvested DQM plots. For each module it gives what it does, its main parameters, its inputs and its consumers, when it runs, its time per event, the open pull requests that change it, and the page of this site that describes it.

Select a module to see what it reads, what reads it and its open items. Below the diagram are how to turn each part on, the open items, the products and the open pull requests.

<iframe src="../assets/truth-dataflow.html" title="Truth graph data flow" loading="lazy"
        style="width: 100%; height: 900px; border: 1px solid var(--md-default-fg-color--lightest);"></iframe>

[Open the diagram in a full window](assets/truth-dataflow.html){ target="_blank" }.

## Sources

- Modules, types and inputs: the configuration of runTheMatrix workflow 34834.88 (TTbar 14 TeV, D122, no pile-up) in `CMSSW_20_1_X_2026-10-27-2300`, steps 2 to 4.
- Times: the FastTimerService, on the same workflow and release, 20 events, 1 thread, 1 stream, one socket of patatrack-bg-01.
- Pull-request states: GitHub, 2026-11-01.
