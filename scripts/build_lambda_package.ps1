$ErrorActionPreference = "Stop"

$workspace = Resolve-Path "$PSScriptRoot\.."

docker build -f "$workspace\lambda\Dockerfile" -t teste-tecnico-lambda-builder "$workspace"
docker run --rm -v "${workspace}:/workspace" teste-tecnico-lambda-builder
