#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -p 'test_*.py' -v
./run_all.sh
git diff --exit-code -- results/summary.json
python3 -I tools/check_results.py
