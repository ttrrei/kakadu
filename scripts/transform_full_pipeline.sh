#!/bin/bash
# ==============================================================================
# Kakadu Standalone Script: Full Pipeline Database Transformation
# ==============================================================================
set -uo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
cd "$PROJECT_DIR"
source .venv/bin/activate

GROUP_NAME="full_pipeline" # 对应 config.yaml 中定义的高级 etl_groups
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%F_%H%M%S)
LOG_FILE="$LOG_DIR/transform_${GROUP_NAME}_${TIMESTAMP}.log"
ERR_FILE="$LOG_DIR/transform_${GROUP_NAME}_${TIMESTAMP}.err"

echo "=== [$(date)] START STANDALONE TRANSFORM: $GROUP_NAME ===" | tee -a "$LOG_FILE"

set +e
python -m src.main transform --group "$GROUP_NAME" > >(tee -a "$LOG_FILE") 2> >(tee -a "$ERR_FILE" >&2)
EXIT_CODE=$?
set -e

echo "=== [$(date)] TRANSFORM EXIT CODE: $EXIT_CODE ===" | tee -a "$LOG_FILE"
if [ $EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Standalone transform failed. Check $ERR_FILE" | tee -a "$ERR_FILE"
fi

exit $EXIT_CODE