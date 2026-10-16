#!/usr/bin/env bash
# Antigravity Marketplace Plugin Publisher & Validator Helper

set -e

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== Antigravity Plugin Marketplace Publisher ==="
echo "Target Plugin Directory: $PLUGIN_DIR"
echo ""

# 1. Validate plugin.json
if [ ! -f "$PLUGIN_DIR/plugin.json" ]; then
    echo "[!] Error: plugin.json not found in $PLUGIN_DIR"
    exit 1
fi

echo "[✓] Found plugin.json"
python3 -c "
import json
with open('$PLUGIN_DIR/plugin.json') as f:
    d = json.load(f)
assert 'name' in d, 'Missing name'
assert 'displayName' in d, 'Missing displayName'
assert 'description' in d, 'Missing description'
print('    - Name: ' + d['name'])
print('    - Display Name: ' + d['displayName'])
print('    - Version: ' + d.get('version', '1.0.0'))
"

# 2. Check Logo
if [ -f "$PLUGIN_DIR/assets/logo.svg" ]; then
    echo "[✓] Found logo asset: assets/logo.svg"
else
    echo "[!] Warning: assets/logo.svg is missing."
fi

# 3. Check Rules & Skills
echo "[✓] Checking rules: $(ls "$PLUGIN_DIR/rules/"* 2>/dev/null || echo 'None')"
echo "[✓] Checking skills: $(ls "$PLUGIN_DIR/skills/"* 2>/dev/null || echo 'None')"
echo "[✓] Checking bundled agents: $(ls "$PLUGIN_DIR/agents/"*.md 2>/dev/null | wc -l | tr -d ' ') agent definitions found."

echo ""
echo "=================================================="
echo "HOW TO PUBLISH TO ANTIGRAVITY MARKETPLACE:"
echo "=================================================="
echo "1. Push this directory to a public GitHub repository:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/multi-agent-orchestrator.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "2. Submit to the Antigravity Plugin Registry:"
echo "   Visit: https://antigravity.google/docs/plugins/publish"
echo "   Enter your repository URL and authorize publication."
echo ""
echo "3. Local Testing without Marketplace:"
echo "   Copy this plugin into your local Antigravity plugin folder:"
echo "   mkdir -p ~/.gemini/config/plugins"
echo "   cp -r '$PLUGIN_DIR' ~/.gemini/config/plugins/multi-agent-orchestrator"
echo "   Restart Antigravity to see it in the Plugins panel!"
echo "=================================================="
