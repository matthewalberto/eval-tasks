#!/bin/bash
# Grades the hook by behaviour. No network, no extra packages: the grader is plain Python.
set -u

mkdir -p /logs/verifier

python3 /tests/test_guard.py 2>&1 | tee /logs/verifier/grader.log
status=${PIPESTATUS[0]}

if [ "$status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
