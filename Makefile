# Build the docs against a self-contained virtualenv, so the build never depends
# on whatever fragmented `mkdocs`/`pip` happen to be on PATH (the AFS .local
# launcher is broken; the system python3 has no mkdocs).
#
#   make serve     # live preview at http://127.0.0.1:8000 (auto-bootstraps the venv)
#   make build     # strict static build into site/
#   make deploy    # build + push to the gh-pages branch
#   make clean     # remove the venv and the built site
#
# The venv is created with a known-good Python 3.12; override if needed:
#   make serve PYTHON=/path/to/python3

PYTHON ?= /cvmfs/cms.cern.ch/el8_amd64_gcc13/cms/cmssw/CMSSW_20_0_0_pre1/external/el8_amd64_gcc13/bin/python3
VENV   := .venv
BIN    := $(VENV)/bin
STAMP  := $(VENV)/.installed

.PHONY: serve build deploy clean

# Re-run pip whenever requirements.txt changes (the stamp is keyed to it).
$(STAMP): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -r requirements.txt
	@touch $(STAMP)

serve: $(STAMP)
	$(BIN)/mkdocs serve

build: $(STAMP)
	$(BIN)/mkdocs build --strict

deploy: $(STAMP)
	$(BIN)/mkdocs gh-deploy --force

clean:
	rm -rf $(VENV) site
