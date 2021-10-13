# Makefile
COLLECTION_NAME="ciscops.mdd"
COLLECTION_VERSION := $(shell awk '/^version:/{print $$NF}' galaxy.yml)
TARBALL_NAME=ciscops-mdd-${COLLECTION_VERSION}.tar.gz
PYDIRS="plugins"

help: ## Display help
	@awk -F ':|##' \
	'/^[^\t].+?:.*?##/ {\
	printf "\033[36m%-30s\033[0m %s\n", $$1, $$NF \
	}' $(MAKEFILE_LIST)

all: test build publish ## Setup python-viptela env and run tests

$(TARBALL_NAME): galaxy.yml
	@ansible-galaxy collection build

build: $(TARBALL_NAME) ## Build Collection

publish: $(TARBALL_NAME) ## Publish Collection (set env:GALAXY_TOKEN)
	ansible-galaxy collection publish $(TARBALL_NAME) --token=$(GALAXY_TOKEN)

format: ## Format Python code
	yapf --style=yapf.ini -i -r *.py $(PYDIRS)

test: ## Run Sanity Tests
	ansible-test sanity --docker default -v

clean: ## Clean
	$(RM) $(TARBALL_NAME)

.PHONY: all clean test build publish
