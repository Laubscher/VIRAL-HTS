#!/usr/bin/env bash

CONFIG_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.example.sh
source "$CONFIG_DIR/config.example.sh"

# Put local overrides below this line if the installation paths differ.

