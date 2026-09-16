#!/usr/bin/env bash
# Builds the moonstar-physics-experiment-runner image used by
# NumericalExperimentTransform to run Phase 2's generated numpy/scipy
# scripts in isolation. Build once (or whenever the Dockerfile changes) —
# this is NOT rebuilt automatically per pipeline run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker build -t moonstar-physics-experiment-runner "$ROOT/moonstar_physics/docker/experiment-runner"
echo "Built moonstar-physics-experiment-runner"
