#!/usr/bin/env bash
# Run Jarvis locally with the LOCALHOST Google redirect URI, then restore the
# production secrets on exit. Use this to test "Sign in with Google" on your machine.
#
#   1. In Google Cloud Console → your OAuth client → Authorized redirect URIs, add:
#          http://localhost:8501/oauth2callback
#   2. Run:  bash run_local.sh
#   3. Open: http://localhost:8501
set -e
cd "$(dirname "$0")"

PROD=".streamlit/secrets.toml"
LOCAL=".streamlit/secrets.local.toml"
BAK=".streamlit/secrets.prod.bak"

if [ -f "$PROD" ]; then cp "$PROD" "$BAK"; fi
cp "$LOCAL" "$PROD"

restore() {
  if [ -f "$BAK" ]; then mv "$BAK" "$PROD"; fi
  echo "Restored production secrets."
}
trap restore EXIT

echo "Running Jarvis locally on http://localhost:8501 (localhost redirect URI)…"
streamlit run app.py --server.port 8501
