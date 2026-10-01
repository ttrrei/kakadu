#!/bin/bash
# ==============================================================================
# Kakadu Crontab Installation Script
# ==============================================================================
# Purpose: Automatically install production crontab schedules for Kakadu engine.
# ==============================================================================

set -euo pipefail

PROJECT_DIR="/home/ubuntu/kakadu"
SCRIPTS_DIR="$PROJECT_DIR/scripts"

echo "=== [$(date)] Installing Kakadu Crontab Schedules ==="

# 1. 检查脚本目录及核心脚本是否存在
if [ ! -d "$SCRIPTS_DIR" ]; then
    echo "[ERROR] Scripts directory not found at $SCRIPTS_DIR"
    exit 1
fi

# 2. 备份现有的 crontab（如果有的话）
BACKUP_CRON="/tmp/crontab_backup_$(date +%F_%H%M%S).bak"
crontab -l > "$BACKUP_CRON" 2>/dev/null && echo "[INFO] Existing crontab backed up to $BACKUP_CRON" || echo "[INFO] No existing crontab found."

# 3. 生成新的 crontab 内容
# 注意：所有路径均使用绝对路径，确保 cron 执行时能正确找到解释器和项目环境
NEW_CRON=$(cat << 'EOF'
# ==============================================================================
# Kakadu Production Crontab Schedule (AEST)
# ==============================================================================

# 1. 每日物理重启 (ADR-004/019 - 凌晨 03:00 彻底清空 OS 缓存与碎片)
0 3 * * * /sbin/shutdown -r now

# 2. 盘前任务 (15:25 AEST)
25 15 * * 1-5 /home/ubuntu/kakadu/scripts/run_scrape_afr.sh

# 3. 盘后任务 (16:45 AEST - 批量行情、短仓及 AFR 采集并即时清洗)
45 16 * * 1-5 /home/ubuntu/kakadu/scripts/run_scrape_price_ohlcv_post.sh
45 16 * * 1-5 /home/ubuntu/kakadu/scripts/run_scrape_afr.sh
45 16 * * 1-5 /home/ubuntu/kakadu/scripts/run_scrape_short.sh

# 4. 每日早间公告 (09:30 AEST - Selenium 任务)
30 9 * * 1-5 /home/ubuntu/kakadu/scripts/run_scrape_annc.sh

# 5. 周末全量维护与静态数据更新
0 6 * * 6 /home/ubuntu/kakadu/scripts/run_scrape_company_master.sh
0 7 * * 0 /home/ubuntu/kakadu/scripts/run_scrape_analyst_trends.sh
0 7 * * 0 /home/ubuntu/kakadu/scripts/run_scrape_analyst_targets.sh

# 6. 独立维护与全量 ETL 任务
0 18 * * 1-5 /home/ubuntu/kakadu/scripts/transform_full_pipeline.sh
0 2 * * 0 /home/ubuntu/kakadu/scripts/maintain_cleanup_old_data.sh
EOF
)

# 4. 写入新的 crontab
echo "$NEW_CRON" | crontab -

echo "=== [$(date)] Crontab successfully installed! ==="
echo "Current active crontab:"
echo "------------------------------------------------------------------"
crontab -l
echo "------------------------------------------------------------------"