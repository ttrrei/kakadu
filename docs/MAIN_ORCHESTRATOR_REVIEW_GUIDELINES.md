# Kakadu `main.py` 核心调度器审查与实现规范 (AI 实施红线)

> **适用对象**：所有尝试修改、重构或审查 `src/main.py` 的 AI 助手与工程师。  
> **核心原则**：Thin-Edge, Thick-Core | 1GB RAM 物理防爆 | 严格退出码契约 | 零静默失败。

---

## 一、 架构契约与红线原则（Red Lines - 绝对禁止项）

1. **禁止内部散落 `sys.exit()`**：
   - 所有的 Handler (`handle_scrape`, `handle_transform`, `handle_maintain`) **必须返回整数退出码** (`return 0` / `return 1`)。
   - 整个文件中，只有入口函数最外层的 `sys.exit(main())` 拥有终止 Python 运行时的权力。
   - **原因**：散落的 `sys.exit()` 会破坏异常冒泡机制，阻断资源清理，并破坏自动化集成测试。

2. **禁止破坏外部 Master Shell 调度契约 (ADR-019)**：
   - 进程级硬清理（尤其是 Chrome/Chromedriver 的 SIGKILL）由外部 Shell 脚本 `run_task.sh` 在 Python 启动前和退出后强制执行。
   - `main.py` 必须精准返回标准 Linux 退出状态码供外部 Shell 捕获：
     - `0`: 任务与后置 ETL 全部成功
     - `1`: 发生致命业务/系统错误
     - `2`: CLI 参数解析错误
     - `130`: 用户主动打断 (`KeyboardInterrupt` / SIGINT)

3. **禁止将 Session Type 作为 CLI 参数传入 (ADR-010)**：
   - 不得存在 `--session-type` 参数。
   - 所有的时段隔离（如盘前/盘后）均直接编码在 Task 标识中（例如 `price_ohlcv_pre`, `price_ohlcv_post`）。

4. **禁止提前更新 Batch 状态为 SUCCESS (ADR-005 审计时序红线)**：
   - 批次生命周期的推进顺序必须且绝对只能是：
     $$\text{INSERT RUNNING} \longrightarrow \text{Scrape \& Pure-INSERT} \longrightarrow \text{Cloud Sync} \longrightarrow \text{Post-ETL} \longrightarrow \text{UPDATE SUCCESS}$$
   - 若 Post-ETL 触发失败，该批次**必须置为 FAILED**，严禁在 Post-ETL 执行前提前置为 SUCCESS。

5. **禁止在 Python 侧向 PL/SQL 传递 BATCH_ID (ADR-021)**：
   - 存储过程调用 (`db_transformer.trigger_group`) 不接受 BATCH_ID 参数。数据层由 PL/SQL 自行根据业务规则与 ODS 的 LOAD_TIME 抽取，保持 Python 的 Thin-Edge。

---

## 二、 核心模块职责与依赖规范

| 模块 / 类 | 必须遵循的调用规范 |
| :--- | :--- |
| `StartupHealthChecker` | 在任何命令分发前必须最先运行（除非显式指定 `--skip-health-check`）。探测失败必须阻断执行并触发 Tier 2 报警。 |
| `ScraperFactory` | 严禁通过 `import` 直接写死爬虫类。必须统一通过 `ScraperFactory.get_scraper(task_name)` 获取爬虫类，并依赖注入 `db_operator`。 |
| `BackupManager` & `UploadManager` | 云备份失败属于 **Tier 1 Warning**。只能打日志记录 Warning 并保留本地数据，**绝不允许**因为云备份超时或失败而终止主流程或将批次标记为 FAILED。 |
| `DbTransformer` | 负责根据 `config.yaml` 中的 `etl_groups` 执行存储过程。**一旦执行抛错，必须中断后续所有过程**，向上冒泡让 Handler 将批次状态置为 FAILED。 |
| `AlertManager` | 系统启动失败、抓取严重中断、ETL 失败必须触发 Tier 2 Pushover 报警。报警接口失败本身不得压制原始异常。 |

---

## 三、 命令行接口规范 (CLI Interface)

`main.py` 必须严格支持以下三种子命令结构：

```bash
# 1. 数据采集 (自动串联 Post-ETL，如 post_price_ohlcv_pre)
python -m src.main [--skip-health-check] scrape --task <task_name>

# 2. 独立数据转换 (调用 config.yaml -> etl_groups 中定义的存储过程组)
python -m src.main [--skip-health-check] transform --group <group_name>

# 3. 运维例行任务 (语义化别名，用于调用维护类存储过程)
python -m src.main [--skip-health-check] maintain --group <group_name>
```

---

## 四、 数据库连接池生命周期托管规范 (Connection Pool Stewardship)

> **物理红线**：`DbOperator` 为全进程单例，其底层连接池在 Python 运行时期间必须保持生命周期连续。

1. **绝对禁止在 Handler 内部关闭连接池**：
   - 严禁在 `handle_scrape`、`handle_transform` 或 `handle_maintain` 中调用 `db_operator.close()`。
   - 严禁在局部的 `except` 代码块中提前关闭连接池（会导致后续的 `update_batch_status(FAILED)` 因失去连接而失败）。
2. **全局统一终结原则**：
   - 连接池关闭（若需显式调用）**只能且必须**出现在 `main()` 函数的最外层 `finally` 代码块中，在所有业务分发完成后执行。
   - 正确模式：
     ```python
     def main() -> int:
         exit_code = 1
         try:
             # 1. 启动检查
             # 2. 命令分发 (scrape / transform / maintain)
             exit_code = ...
         except KeyboardInterrupt:
             exit_code = 130
         except Exception as e:
             # Tier 2 报警
             exit_code = 1
         finally:
             # 全局唯一的连接池收尾点，静默兜底，不遮蔽主退出码
             try:
                 db_operator.close()
             except Exception as e:
                 logger.debug(f"DbOperator cleanup ignored: {e}")
         return exit_code
     ```

---

## 五、 AI 代码审查检查清单（Review Checklist）

在提交或合并任何 `main.py` 的代码更改前，必须逐项核对：

- [ ] **[Q1] 退出码规范**：是否不存在任何内部子函数中的 `sys.exit()`？
- [ ] **[Q2] 审计时序**：`db_operator.update_batch_status(..., status="SUCCESS")` 是否位于整个流程（包括 Post-ETL）的最后一步？
- [ ] **[Q3] 审计完整度**：`transform` 和 `maintain` 子命令是否也生成了 `batch_id` 并在 `SYS_BATCH_LOG` 中留下了审计轨迹？
- [ ] **[Q4] 错误捕获降级**：Cloud Sync 异常是否被局部捕获（仅 Warning），而没有误伤将批次置为 FAILED？
- [ ] **[Q5] Tier 2 覆盖**：发生 Unhandled Exception 时，是否都兜底调用了 `alert_manager.send_tier2_alert(...)`？
- [ ] **[Q6] 资源收尾**：`main()` 函数是否包含对 `KeyboardInterrupt` 的友好拦截？
- [ ] **[Q7] OCI 配置稳健性**：PAR URL 的解析是否能够容错处理空配置，而不会产生 AttributeError 或非法的 URL 拼接？
- [ ] **[Q8] 连接池生命周期**：`db_operator.close()` 是否**仅且只**出现在 `main()` 函数顶层的 `finally` 块中，Handler 内部完全未过早切断连接？