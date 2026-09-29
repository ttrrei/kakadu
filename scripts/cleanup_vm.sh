#!/bin/bash
# ==============================================================================
# Kakadu VM Resource Shield & Process Sanitization Script (ADR-019)
# ==============================================================================
# Purpose: Forcefully terminate orphaned browser processes and clean up temporary 
#          files to protect the 1GB RAM micro VM from out-of-memory (OOM) crashes.
# ==============================================================================

set -uo pipefail

echo "[$(date)] === Starting VM Resource Cleanup ==="

# 1. Forcefully kill any lingering Chrome or Chromedriver processes
if pgrep -f "chrome" >/dev/null 2>&1 || pgrep -f "chromedriver" >/dev/null 2>&1; then
    echo "[$(date)] [WARNING] Found orphaned browser processes. Terminating..."
    pkill -9 -f "chrome" 2>/dev/null || true
    pkill -9 -f "chromedriver" 2>/dev/null || true
    echo "[$(date)] Browser processes killed."
else
    echo "[$(date)] No orphaned browser processes found."
fi

# 2. Clean up temporary Chromium / Selenium profile directories in /tmp
if compgen -G "/tmp/.org.chromium.*" >/dev/null || compgen -G "/tmp/.com.google.Chrome.*" >/dev/null || compgen -G "/tmp/selenium*" >/dev/null; then
    echo "[$(date)] Cleaning up temporary Selenium/Chrome files in /tmp..."
    rm -rf /tmp/.org.chromium.* /tmp/.com.google.Chrome.* /tmp/selenium* 2>/dev/null || true
    echo "[$(date)] Temporary files cleaned."
else
    echo "[$(date)] No lingering temporary files in /tmp."
fi

echo "[$(date)] === VM Cleanup Completed Successfully ==="