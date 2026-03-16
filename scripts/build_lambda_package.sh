#!/bin/sh
set -eu

workspace_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

docker build -f "$workspace_dir/lambda/Dockerfile" -t teste-tecnico-lambda-builder "$workspace_dir"
docker run --rm -v "$workspace_dir:/workspace" teste-tecnico-lambda-builder
