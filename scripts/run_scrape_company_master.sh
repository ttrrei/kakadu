#!/bin/bash
# ==============================================================================
# Kakadu Task Script: Company Master Scrape + Immediate Transform
# ==============================================================================
# Target: ODS_COMPANY_MASTER (Weekly Bulk API CSV Export)
# ==============================================================================

set -uo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
cd "$PROJECT_DIR"
source .venv/bin/activate

TASK_NAME="company_master"
TRANSFORM_GROUP="post_company_master" # 对应 config.yaml 中配置的清洗存储过程组
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%F_%H%M%S)
LOG_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.log"
ERR_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.err"

echo "=== [$(date)] START TASK & PIPELINE: $TASK_NAME ===" | tee -a "$LOG_FILE"

# 1. 前置清理 (保持良好习惯，防患于未然)
bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"

set +e
# 2. 执行数据采集 (Stdout/Stderr 优雅分流)
python -m src.main scrape --task "$TASK_NAME" > >(tee -a "$LOG_FILE") 2> >(tee -a "$ERR_FILE" >&2)
SCRAPE_EXIT=$?
set -e

if [ $SCRAPE_EXIT -eq 0 ]; then
    echo "[INFO] Scrape succeeded. Triggering database transformation ($TRANSFORM_GROUP)..." | tee -a "$LOG_FILE"
    
    # 3. 采集成功后，立即触发对应的 PL/SQL 转换/清洗
    set +e
    python -m src.main transform --group "$TRANSFORM_GROUP" >> "$LOG_FILE" 2>> "$ERR_FILE"
    TRANSFORM_EXIT=$?
    set -e
    
    if [ $TRANSFORM_EXIT -eq 0 ]; then
        echo "=== [$(date)] TASK & TRANSFORM SUCCEEDED SUCCESSFULLY ===" | tee -a "$LOG_FILE"
        EXIT_CODE=0
    else
        echo "[ERROR] Transformation failed with exit code $TRANSFORM_EXIT" | tee -a "$ERR_FILE"
        EXIT_CODE=$TRANSFORM_EXIT
    fi
else
    echo "[ERROR] Scrape failed with exit code $SCRAPE_EXIT" | tee -a "$ERR_FILE"
    EXIT_CODE=$SCRAPE_EXIT
fi

# 4. 后置清理
bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"

echo "=== [$(date)] EXIT CODE: $EXIT_CODE ===" | tee -a "$LOG_FILE"
exit $EXIT_CODE