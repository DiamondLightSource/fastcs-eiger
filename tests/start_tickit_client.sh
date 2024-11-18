#!/bin/bash
export EPICS_CA_SERVER_PORT=6064
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
python -m tickit --log-level INFO all $SCRIPT_DIR/system/eiger.yaml
