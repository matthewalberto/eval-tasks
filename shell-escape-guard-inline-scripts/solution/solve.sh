#!/bin/bash
# Reference solution: install the published version of the hook, which adds the
# inline-script-argument route (python -c, node -e, sed and friends) to the heredoc scan.
set -euo pipefail

cp /solution/guard_heredoc_escapes.py /app/hooks/guard_heredoc_escapes.py
python3 /app/hooks/guard_heredoc_escapes.py --selftest
