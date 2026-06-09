#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
APP_DIR="$ROOT_DIR/app/PersonalWorkflowApp"
APP_NAME="Personal Workflow.app"
INSTALL_ROOT="${PERSONAL_WORKFLOW_INSTALL_ROOT:-$HOME/Applications}"
APP_PATH="$INSTALL_ROOT/$APP_NAME"
DRY_RUN=0
REMOVE=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --remove) REMOVE=1 ;;
        --install-root)
            shift
            INSTALL_ROOT="$1"
            APP_PATH="$INSTALL_ROOT/$APP_NAME"
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 64
            ;;
    esac
    shift
done

case "$INSTALL_ROOT" in
    "$HOME"/Applications|"$HOME"/Applications/*|"$ROOT_DIR"/dist|"$ROOT_DIR"/dist/*) ;;
    *)
        echo "install root must be user-scoped ~/Applications or repo-local dist" >&2
        exit 65
        ;;
esac

if [ "$REMOVE" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would_remove_app=$APP_PATH"
    else
        rm -rf "$APP_PATH"
        echo "removed_app=$APP_PATH"
    fi
    exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "would_build_package=$APP_DIR"
    echo "would_install_app=$APP_PATH"
    exit 0
fi

swift build --package-path "$APP_DIR" -c release
BINARY_PATH="$(swift build --package-path "$APP_DIR" -c release --show-bin-path)/PersonalWorkflowApp"

mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"
cp "$BINARY_PATH" "$APP_PATH/Contents/MacOS/PersonalWorkflowApp"
chmod 755 "$APP_PATH/Contents/MacOS/PersonalWorkflowApp"
cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>PersonalWorkflowApp</string>
  <key>CFBundleIdentifier</key>
  <string>local.personal.workflow.app</string>
  <key>CFBundleName</key>
  <string>Personal Workflow</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0-local</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
</dict>
</plist>
PLIST

echo "installed_app=$APP_PATH"
echo "rollback=sh scripts/install-personal-workflow-app.sh --remove"
