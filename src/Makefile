# SAM "makefile" build for the Lambda functions.
#
# Why not the default Python build: pydantic (and its compiled pydantic-core
# wheel) must match the Lambda runtime (Linux, arm64, CPython 3.12). Building on
# a developer laptop with the default builder grabs the host-platform wheel.
# This target pins the platform explicitly so `sam build` works without Docker.
#
# infra/template.yaml sets `Metadata: BuildMethod: makefile` on each function;
# SAM then calls `make build-<LogicalId>` with ARTIFACTS_DIR set.

PLATFORM  := manylinux2014_aarch64
PYVERSION := 3.12
PIP       := $(shell command -v pip || echo "python3 -m pip")

define build_function
	$(PIP) install \
		--platform $(PLATFORM) \
		--implementation cp \
		--python-version $(PYVERSION) \
		--only-binary=:all: --upgrade \
		--target "$(ARTIFACTS_DIR)" \
		-r requirements.txt
	cp -r household_agent "$(ARTIFACTS_DIR)/"
endef

build-ApiFunction:
	$(build_function)

build-SweepFunction:
	$(build_function)
