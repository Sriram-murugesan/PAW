#!/bin/sh
# Every check except the ones that open windows (npm run app:smoke).
set -eu
cd "$(dirname "$0")/.."
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
(cd backend && uv sync -q && uv run ruff format -q --check . && uv run ruff check -q . && uv run mypy && uv run lint-imports | grep Contracts: && uv run pytest -q)
(cd desktop && cp src/types/api.ts /tmp/paw-api-types.$$ && npm run -s types >/dev/null && cmp src/types/api.ts /tmp/paw-api-types.$$ && rm /tmp/paw-api-types.$$)
(cd desktop && npm run -s typecheck && npm run -s lint && npm test && npm run -s build)
(cd desktop/src-tauri && cargo fmt --check && cargo clippy -q --all-targets --all-features && cargo test -q)
echo "all checks passed"
