#!/bin/bash
# ==============================================================================
# Kakadu Task Script: Analyst Targets Scrape + Immediate Transform
# ==============================================================================
set -uo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
cd "$PROJECT_DIR"
source .venv/bin/activate

TASK_NAME="analyst_targets"
TRANSFORM_GROUP="post_analyst_targets"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%F_%H%M%S)
LOG_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.log"
ERR_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.err"

echo "=== [$(date)] START TASK & PIPELINE: $TASK_NAME ===" | tee -a "$LOG_FILE"
bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"

set +e
python -m src.main scrape --task "$TASK_NAME" > >(tee -a "$LOG_FILE") 2> >(tee -a "$ERR_FILE" >&2)
SCRAPE_EXIT=$?

if [ $SCRAPE_EXIT -eq 0 ]; then
    python -m src.main transform --group "$TRANSFORM_GROUP" >> "$LOG_FILE" 2>> "$ERR_FILE"
    EXIT_CODE=$?
else
    EXIT_CODE=$SCRAPE_EXIT
fi
set -e

bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"
exit $EXIT_CODE