#!/bin/bash
# ==============================================================================
# Kakadu Task Script: Price OHLCV Post-Market Scrape + Immediate Transform
# ==============================================================================
# Target: ODS_PRICE_OHLCV (Iterative API Fetch ~2000 symbols + Retry + ETL)
# ==============================================================================

set -uo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
cd "$PROJECT_DIR"
source .venv/bin/activate

TASK_NAME="price_ohlcv_post"
TRANSFORM_GROUP="post_price_ohlcv_post" # 对应 config.yaml 中的 etl_groups
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%F_%H%M%S)
LOG_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.log"
ERR_FILE="$LOG_DIR/task_${TASK_NAME}_${TIMESTAMP}.err"

MAX_RETRIES=3
RETRY_DELAY=10
SUCCESS=false

echo "=== [$(date)] START TASK & PIPELINE: $TASK_NAME ===" | tee -a "$LOG_FILE"

for ((i=1; i<=MAX_RETRIES; i++)); do
    echo "--- [$(date)] Attempt $i of $MAX_RETRIES ---" | tee -a "$LOG_FILE"
    
    # 1. 前置防爆清理
    bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"
    
    set +e
    # 2. 执行数据采集（Stdout/Stderr 优雅分流）
    python -m src.main scrape --task "$TASK_NAME" > >(tee -a "$LOG_FILE") 2> >(tee -a "$ERR_FILE" >&2)
    SCRAPE_EXIT=$?
    
    if [ $SCRAPE_EXIT -eq 0 ]; then
        echo "[INFO] Scrape succeeded. Triggering database transformation ($TRANSFORM_GROUP)..." | tee -a "$LOG_FILE"
        
        # 3. 采集成功后，立即触发对应的 PL/SQL 转换
        python -m src.main transform --group "$TRANSFORM_GROUP" >> "$LOG_FILE" 2>> "$ERR_FILE"
        TRANSFORM_EXIT=$?
        
        if [ $TRANSFORM_EXIT -eq 0 ]; then
            echo "=== [$(date)] TASK & TRANSFORM SUCCEEDED on attempt $i ===" | tee -a "$LOG_FILE"
            SUCCESS=true
            break
        else
            echo "[WARNING] Transformation failed with exit code $TRANSFORM_EXIT" | tee -a "$ERR_FILE"
        fi
    else
        echo "[WARNING] Scrape failed with exit code $SCRAPE_EXIT" | tee -a "$ERR_FILE"
    fi
    set -e
    
    # 4. 后置清理
    bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"
    
    if [ $i -lt $MAX_RETRIES ]; then
        echo "[INFO] Waiting ${RETRY_DELAY}s before retry..." | tee -a "$LOG_FILE"
        sleep $RETRY_DELAY
        # 指数退避：延迟时间翻倍
        RETRY_DELAY=$((RETRY_DELAY * 2))
    fi
done

# 最终后置清理
bash scripts/cleanup_vm.sh | tee -a "$LOG_FILE"

if [ "$SUCCESS" = false ]; then
    echo "[ERROR] TASK $TASK_NAME failed permanently after $MAX_RETRIES attempts." | tee -a "$ERR_FILE"
    exit 1
fi

exit 0