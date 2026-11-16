PYTHON ?= python3.12

.PHONY: build-ApiFunction build-AIExplainFunction build-PriceWorkerFunction build-IngestionReportFunction
build-ApiFunction build-AIExplainFunction build-PriceWorkerFunction build-IngestionReportFunction:
	$(PYTHON) -m pip install --disable-pip-version-check --only-binary=:all: --platform manylinux2014_aarch64 --implementation cp --python-version 3.12 -r requirements.txt --target "$(ARTIFACTS_DIR)"
	rsync -a --include='*/' --include='*.py' --exclude='*' backend src "$(ARTIFACTS_DIR)/"
