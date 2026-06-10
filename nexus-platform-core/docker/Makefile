ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
IMAGE ?= nexus-cloud-genomics:latest
CONFIG_DIR := $(ROOT)/docker/config
DATA_DIR := $(ROOT)/docker/data
REF_DIR := $(ROOT)/docker/references
ENV_FILE := $(ROOT)/docker/.env
DOCKER_RUN_OPTS := --rm \
	-v "$(CONFIG_DIR):/config:ro" \
	-v "$(DATA_DIR):/data" \
	-v "$(REF_DIR):/references:ro"

ifneq (,$(wildcard $(ENV_FILE)))
  DOCKER_RUN_OPTS += --env-file $(ENV_FILE)
endif

.PHONY: build help versions shell blast kraken2 minimap2 bowtie2 init-config compose-build

build:
	docker build -t $(IMAGE) -f $(ROOT)/docker/Dockerfile $(ROOT)

compose-build:
	docker compose -f $(ROOT)/docker/docker-compose.yml build

help: build
	docker run --rm $(IMAGE) help

versions: build
	docker run --rm $(IMAGE) versions

shell: build
	docker run --rm -it $(DOCKER_RUN_OPTS) $(IMAGE) shell

blast: build
	docker run $(DOCKER_RUN_OPTS) $(IMAGE) blast --config /config/blast.json

kraken2: build
	docker run $(DOCKER_RUN_OPTS) $(IMAGE) kraken2 --config /config/kraken2.json

minimap2: build
	docker run $(DOCKER_RUN_OPTS) $(IMAGE) minimap2 --config /config/minimap2.json

bowtie2: build
	docker run $(DOCKER_RUN_OPTS) $(IMAGE) bowtie2 --config /config/bowtie2.json

init-config:
	mkdir -p "$(CONFIG_DIR)" "$(DATA_DIR)" "$(REF_DIR)"
	cp -n "$(ROOT)/nexus_cloud/config.example.json" "$(CONFIG_DIR)/blast.json" 2>/dev/null || true
	cp -n "$(ROOT)/nexus_cloud/config.kraken2.example.json" "$(CONFIG_DIR)/kraken2.json" 2>/dev/null || true
	cp -n "$(ROOT)/nexus_cloud/config.minimap2.example.json" "$(CONFIG_DIR)/minimap2.json" 2>/dev/null || true
	cp -n "$(ROOT)/nexus_cloud/config.bowtie2.example.json" "$(CONFIG_DIR)/bowtie2.json" 2>/dev/null || true
	cp -n "$(ROOT)/docker/.env.example" "$(ENV_FILE)" 2>/dev/null || true
	@echo "Configs written to docker/config/. Edit them and docker/.env before running."
