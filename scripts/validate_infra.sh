#!/bin/bash
# Validate Redis, MySQL, Kafka connectivity using config.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${PERF_CONFIG:-$PERF_DIR/config/infra.json}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config not found: $CONFIG_FILE"
  exit 1
fi

python3 -c "
import sys
sys.path.insert(0, '$PERF_DIR/backend')
import json
from validate import validate_all
with open('$CONFIG_FILE') as f:
    config = json.load(f)
for name, r in validate_all(config).items():
    status = 'OK' if r['ok'] else 'FAIL'
    print(f'{name}: {status} - {r[\"message\"]}')
" 
