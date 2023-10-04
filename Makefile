# Makefile
PYTHON_EXE = python3.10
COLLECTION_NAME="ciscops.mdd"
COLLECTION_VERSION := $(shell awk '/^version:/{print $$NF}' galaxy.yml)
TARBALL_NAME=ciscops-mdd-${COLLECTION_VERSION}.tar.gz
PYDIRS="plugins"
VENV = venv
VENV_BIN=$(VENV)/bin

help: ## Display help
	@awk -F ':|##' \
	'/^[^\t].+?:.*?##/ {\
	printf "\033[36m%-30s\033[0m %s\n", $$1, $$NF \
	}' $(MAKEFILE_LIST)

all: clean build test ## Setup python-viptela env and run tests

$(VENV): $(VENV_BIN)/activate ## Build virtual environment

$(VENV_BIN)/activate:
	test -d $(VENV) || $(PYTHON_EXE) -m venv $(VENV)
	. $(VENV_BIN)/activate

$(TARBALL_NAME): galaxy.yml
	@ansible-galaxy collection build

build: $(TARBALL_NAME) ## Build Collection

publish: $(TARBALL_NAME) ## Publish Collection (set env:GALAXY_TOKEN)
	ansible-galaxy collection publish $(TARBALL_NAME) --token=$(GALAXY_TOKEN)

format: ## Format Python code
	yapf --style=yapf.ini -i -r *.py $(PYDIRS)

test: clean build $(VENV) $(TARBALL_NAME) ## Run Sanity Tests
	$(RM) -r ./ansible_collections
	ansible-galaxy collection install --force $(TARBALL_NAME) -p ./ansible_collections
	cd ./ansible_collections/ciscops/mdd && git init .
	$(VENV_BIN)/pip uninstall -y ansible-base
	$(VENV_BIN)/pip install https://github.com/ansible/ansible/archive/stable-2.13.tar.gz --disable-pip-version-check
	cd ./ansible_collections/ciscops/mdd && ../../../$(VENV_BIN)/ansible-test sanity --docker -v --color
	$(VENV_BIN)/pip uninstall -y ansible-base
	$(VENV_BIN)/pip install https://github.com/ansible/ansible/archive/stable-2.14.tar.gz --disable-pip-version-check
	cd ./ansible_collections/ciscops/mdd && ../../../$(VENV_BIN)/ansible-test sanity --docker -v --color
	$(VENV_BIN)/pip uninstall -y ansible-base
	$(VENV_BIN)/pip install https://github.com/ansible/ansible/archive/devel.tar.gz --disable-pip-version-check
	cd ./ansible_collections/ciscops/mdd && ../../../$(VENV_BIN)/ansible-test sanity --docker -v --color
	$(RM) $(TARBALL_NAME)
	$(RM) -r ./ansible_collections
	$(RM) -r ./venv

clean: ## Clean
	$(RM) $(TARBALL_NAME)
	$(RM) -r ./ansible_collections
	$(RM) -r ./venv

.PHONY: all clean build test publish
