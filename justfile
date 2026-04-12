# Engram — coding preference memory

set dotenv-load

# Development
dev:
    uv run uvicorn engram.server:app --reload --host 0.0.0.0 --port 3000

# Service management
start:
    launchctl load ~/Library/LaunchAgents/com.engram.service.plist

stop:
    launchctl unload ~/Library/LaunchAgents/com.engram.service.plist

restart: stop start

status:
    @launchctl list | grep engram || echo "engram is not running"

logs:
    tail -f ~/.engram/logs/engram.log

# Installation
install: install-service install-hook

uninstall: uninstall-hook uninstall-service

install-service:
    #!/usr/bin/env bash
    set -euo pipefail
    REPO_DIR="$(pwd)"
    UV_PATH="$(which uv)"
    cat > ~/Library/LaunchAgents/com.engram.service.plist << PLIST
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.engram.service</string>
        <key>ProgramArguments</key>
        <array>
            <string>${UV_PATH}</string>
            <string>run</string>
            <string>python</string>
            <string>-m</string>
            <string>engram.server</string>
        </array>
        <key>WorkingDirectory</key>
        <string>${REPO_DIR}</string>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>$HOME/.engram/logs/engram.log</string>
        <key>StandardErrorPath</key>
        <string>$HOME/.engram/logs/engram.log</string>
        <key>EnvironmentVariables</key>
        <dict>
            <key>PATH</key>
            <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        </dict>
    </dict>
    </plist>
    PLIST
    echo "Installed launchd plist"
    launchctl load ~/Library/LaunchAgents/com.engram.service.plist
    echo "Service started"

uninstall-service:
    -launchctl unload ~/Library/LaunchAgents/com.engram.service.plist
    rm -f ~/Library/LaunchAgents/com.engram.service.plist
    @echo "Removed launchd plist"

install-hook:
    #!/usr/bin/env bash
    set -euo pipefail
    SETTINGS_DIR="$HOME/.claude"
    mkdir -p "$SETTINGS_DIR"
    HOOK_SCRIPT="$SETTINGS_DIR/engram-hook.sh"
    cat > "$HOOK_SCRIPT" << 'HOOK'
    #!/usr/bin/env bash
    # Engram session injection hook
    ENGRAM_URL="http://localhost:3000"
    CLAUDE_MD="$HOME/.claude/CLAUDE.md"

    if ! curl -sf "$ENGRAM_URL/api/health" > /dev/null 2>&1; then
        exit 0
    fi

    REPO=""
    if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
        REMOTE_URL=$(git config --get remote.origin.url 2>/dev/null || true)
        if [[ "$REMOTE_URL" =~ github[^:/]*[:/](.+)/([^/]+)$ ]]; then
            REPO="${BASH_REMATCH[2]%.git}"
        fi
    fi

    SCOPES="global"
    if ls *.py **/*.py > /dev/null 2>&1; then SCOPES="$SCOPES,python"; fi
    if ls *.ts **/*.ts *.tsx **/*.tsx > /dev/null 2>&1; then SCOPES="$SCOPES,typescript"; fi
    if ls *.js **/*.js *.jsx **/*.jsx > /dev/null 2>&1; then SCOPES="$SCOPES,javascript"; fi
    if ls *.go **/*.go > /dev/null 2>&1; then SCOPES="$SCOPES,go"; fi
    if ls *.rs **/*.rs > /dev/null 2>&1; then SCOPES="$SCOPES,rust"; fi
    if ls *test* **/*test* > /dev/null 2>&1; then SCOPES="$SCOPES,testing"; fi

    QUERY="scopes=$SCOPES"
    if [[ -n "$REPO" ]]; then QUERY="$QUERY&repo=$REPO"; fi
    PREFS=$(curl -sf "$ENGRAM_URL/api/inject?$QUERY" 2>/dev/null || true)

    if [[ -z "$PREFS" ]]; then
        exit 0
    fi

    touch "$CLAUDE_MD"
    sed -i '' '/<!-- engram:start -->/,/<!-- engram:end -->/d' "$CLAUDE_MD"
    printf '\n%s\n' "$PREFS" >> "$CLAUDE_MD"
    HOOK
    chmod +x "$HOOK_SCRIPT"
    echo "Installed hook script at $HOOK_SCRIPT"
    echo "Add this to your Claude Code settings.json hooks:"
    echo '  "hooks": { "SessionStart": [{ "command": "bash ~/.claude/engram-hook.sh" }] }'

uninstall-hook:
    rm -f ~/.claude/engram-hook.sh
    @echo "Removed engram hook script"
    @echo "Remember to remove the hook entry from Claude Code settings.json"

# Code quality
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

format:
    uv run ruff format src/ tests/

typecheck:
    uv run pyright

test *args:
    uv run pytest {{args}}

check: lint typecheck test

# Setup
setup:
    uv sync --all-extras
    @echo "Setup complete. Run 'just dev' to start the development server."

# Git operations (DannyMor account via ~/mydev/tools/github)
push:
    git push origin "$(git rev-parse --abbrev-ref HEAD)"

pr title body="":
    source ~/mydev/tools/github/gh_env.zsh && gpr "{{title}}" "{{body}}"

quick title body="":
    source ~/mydev/tools/github/gh_env.zsh && gquick "{{title}}" "{{body}}"
