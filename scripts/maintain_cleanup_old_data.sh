#!/bin/bash
# ==============================================================================
# Kakadu Maintenance Script: Cleanup Old Data & Logs
# ==============================================================================
set -uo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
cd "$PROJECT_DIR"
source .venv/bin/activate

GROUP_NAME="cleanup_old_data" # 对应 config.yaml 中定义的 etl_groups (maintain 路由)
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%F_%H%M%S)
LOG_FILE="$LOG_DIR/maintain_${GROUP_NAME}_${TIMESTAMP}.log"
ERR_FILE="$LOG_DIR/maintain_${GROUP_NAME}_${TIMESTAMP}.err"

echo "=== [$(date)] START MAINTENANCE ROUTINE: $GROUP_NAME ===" | tee -a "$LOG_FILE"

# 1. 触发数据库端的清理存储过程
set +e
python -m src.main maintain --group "$GROUP_NAME" > >(tee -a "$LOG_FILE") 2> >(tee -a "$ERR_FILE" >&2)
EXIT_CODE=$?

# 2. 顺便清理本地超过 7 天的旧日志文件，防止磁盘写满
echo "[INFO] Cleaning up local logs older than 7 days..." | tee -a "$LOG_FILE"
find "$LOG_DIR" -type f \( -name "*.log" -o -name "*.err" \) -mtime +7 -delete 2>/dev/null || true

set -e

echo "=== [$(date)] MAINTENANCE EXIT CODE: $EXIT_CODE ===" | tee -a "$LOG_FILE"
if [ $EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Maintenance routine failed. Check $ERR_FILE" | tee -a "$ERR_FILE"
fi

exit $EXIT_CODE