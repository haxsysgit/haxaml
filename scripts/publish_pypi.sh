#!/usr/bin/env bash

# Build and publish Haxaml distributions with uv.
#
# This script is intentionally local-first. It reads a PyPI token from .env so
# package publishing does not depend on a release tag or GitHub Actions secrets.
# Expected .env keys:
#
#   PYPI_TOKEN=pypi-...
#
# Optional alternatives are supported for convenience:
#
#   UV_PUBLISH_TOKEN=pypi-...
#   PYPI_API_TOKEN=pypi-...

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
TARGET="all"
SKIP_TESTS=0
SKIP_BUILD=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/publish_pypi.sh [--target all|core|mcp|ui] [--skip-tests] [--skip-build] [--dry-run]

Options:
  --target       Package set to publish. Defaults to all.
  --skip-tests   Do not run the test suite before building.
  --skip-build   Publish existing dist files instead of rebuilding them.
  --dry-run      Build and check packages, then print what would be published.
  -h, --help     Show this help text.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --skip-tests)
      SKIP_TESTS=1
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$TARGET" in
  all|core|mcp|ui) ;;
  *)
    echo "Invalid --target '$TARGET'. Use all, core, mcp, or ui." >&2
    exit 2
    ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  # .env is treated as shell syntax. The token is never printed.
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Missing .env at $ENV_FILE" >&2
  exit 1
fi

PUBLISH_TOKEN="${PYPI_TOKEN:-${UV_PUBLISH_TOKEN:-${PYPI_API_TOKEN:-}}}"
if [[ -z "$PUBLISH_TOKEN" && "$DRY_RUN" -eq 0 ]]; then
  echo "Missing PYPI_TOKEN, UV_PUBLISH_TOKEN, or PYPI_API_TOKEN in .env" >&2
  exit 1
fi

build_core() {
  uv build
  uv run twine check dist/*
}

build_mcp() {
  uv build --project packages/haxaml-mcp --out-dir packages/haxaml-mcp/dist
  uv run twine check packages/haxaml-mcp/dist/*
}

build_ui() {
  uv build --project packages/haxaml-ui --out-dir packages/haxaml-ui/dist
  uv run twine check packages/haxaml-ui/dist/*
}

publish_core() {
  uv publish --token "$PUBLISH_TOKEN" dist/*
}

publish_mcp() {
  uv publish --token "$PUBLISH_TOKEN" packages/haxaml-mcp/dist/*
}

publish_ui() {
  uv publish --token "$PUBLISH_TOKEN" packages/haxaml-ui/dist/*
}

cd "$ROOT_DIR"

if [[ "$SKIP_TESTS" -eq 0 ]]; then
  uv run pytest -q
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  case "$TARGET" in
    all)
      rm -rf dist packages/haxaml-mcp/dist packages/haxaml-ui/dist
      build_core
      build_mcp
      build_ui
      ;;
    core)
      rm -rf dist
      build_core
      ;;
    mcp)
      rm -rf packages/haxaml-mcp/dist
      build_mcp
      ;;
    ui)
      rm -rf packages/haxaml-ui/dist
      build_ui
      ;;
  esac
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  if [[ "$SKIP_BUILD" -eq 1 ]]; then
    echo "Dry run complete. No publish performed for target: $TARGET"
  else
    echo "Dry run complete. Built and checked target: $TARGET"
  fi
  exit 0
fi

case "$TARGET" in
  all)
    publish_core
    publish_mcp
    publish_ui
    ;;
  core) publish_core ;;
  mcp) publish_mcp ;;
  ui) publish_ui ;;
esac

echo "Published target: $TARGET"
