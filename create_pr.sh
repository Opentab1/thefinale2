#!/bin/bash
# Quick script to open PR creation page

BRANCH="cursor/debug-song-and-temp-readings-38c0"
BASE="main"
REPO="Opentab1/thefinale2"

TITLE="Fix temperature display and song detection issues"
DESC="Fixes temperature readings not displaying on dashboard and improves song detection with better logging and error handling."

URL="https://github.com/${REPO}/compare/${BASE}...${BRANCH}?expand=1&title=$(echo -n "$TITLE" | jq -sRr @uri)"

echo "PR Creation URL:"
echo "$URL"
echo ""
echo "Or use this command:"
echo "gh pr create --title '$TITLE' --body '$DESC' --base $BASE --head $BRANCH"
