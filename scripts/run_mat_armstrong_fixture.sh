#!/usr/bin/env sh
set -eu
python3 -m shorts_fidelity_judge.cli evaluate \
  benchmark/fixtures/mat_armstrong_manifest.json \
  --output output/mat_armstrong_fixture
