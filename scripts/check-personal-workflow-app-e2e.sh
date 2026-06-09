#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CONFIG_PATH="${PERSONAL_WORKFLOW_CODEX_CONFIG:-$HOME/.codex/config.toml}"
INSTALL_ROOT="${PERSONAL_WORKFLOW_INSTALL_ROOT:-$ROOT_DIR/dist}"
APP_PATH="$INSTALL_ROOT/Personal Workflow.app"
CODEX_URL="${PERSONAL_WORKFLOW_CODEX_URL:-codex://workflow-ui-commondb-20260608/local-only-e2e?ref=artifact.workflow-ui-commondb-20260608}"
DRY_RUN=0
OPEN_LINK=0
LAUNCH_APP=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --open-link) OPEN_LINK=1 ;;
        --launch-app) LAUNCH_APP=1 ;;
        --config)
            shift
            CONFIG_PATH="$1"
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 64
            ;;
    esac
    shift
done

case "$CODEX_URL" in
    codex://*) ;;
    *)
        echo "codex_link_status=blocked"
        exit 66
        ;;
esac

case "$CODEX_URL" in
    *token*|*secret*|*password*|*raw*|*"/Users/"*|*"/users/"*|*file://*|*http://*|*https://*)
        echo "codex_link_status=blocked"
        exit 66
        ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
    sh "$ROOT_DIR/scripts/install-personal-workflow-app.sh" --dry-run --install-root "$INSTALL_ROOT" >/dev/null
else
    sh "$ROOT_DIR/scripts/install-personal-workflow-app.sh" --install-root "$INSTALL_ROOT" >/dev/null
    test -x "$APP_PATH/Contents/MacOS/PersonalWorkflowApp"
fi

python3 "$ROOT_DIR/scripts/commondb-mcp-dry-run.py" --config "$CONFIG_PATH" --json >/dev/null

if [ "$OPEN_LINK" -eq 1 ]; then
    open "$CODEX_URL"
fi

if [ "$LAUNCH_APP" -eq 1 ] && [ "$DRY_RUN" -eq 0 ]; then
    open "$APP_PATH"
fi

echo "schema_version=0.1"
echo "record_type=personal_workflow_app_e2e_result"
echo "status=passed"
echo "app_artifact=$APP_PATH"
echo "deploy_status=$([ "$DRY_RUN" -eq 1 ] && echo dry_run || echo installed)"
echo "codex_link_status=codex_scheme_only"
echo "commondb_mcp_dry_run_status=passed"
echo "security_block_status=passed"
echo "live_mcp=not_used"
echo "qdrant=out_of_scope"
