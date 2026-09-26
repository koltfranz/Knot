# 变更日志

本项目所有值得注意的变更都将记录于此。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.3.0] - 2026-09-26

对应里程碑 M2：Web 界面（本地服务）。

### Added

- `服务`（`serve`）命令：`ThreadingHTTPServer` + 中文路由，默认监听 `127.0.0.1:5000`
- Web 数据层 `web/service.py`：按文件 mtime 缓存快照，写操作复用 `core.actions`，变更后自动失效
- HTTP 接口：`/api/概览`、`/api/流水`、`/api/余额`、`/api/科目`、`/api/别名`、`/api/待分类`、`/api/报表/<类型>`、`/api/图表/<类型>`、`/api/变更`（SSE）、`POST /api/记一笔`、`POST /api/归类`、`POST /api/导入预览`、`POST /api/导入`
- 静态前端（随包分发、无 CDN、无第三方库）：仪表盘、记一笔、流水、科目、报表、导入向导六页；ChartSpec 在前端渲染为 SVG，与 CLI/TUI 消费同一结构
- 三大财务报表：`report.balance_sheet`、`income_statement`、`cash_flow_statement`（现金流量按经营 / 投资 / 筹资分类）
- 待分类批量归类：`POST /api/归类` 整块改写交易并沉淀分类规则（走 `core.actions.reclassify`）
- 写操作内核 `core/actions.py`：CLI 与 Web 共用记账与归类逻辑（含收入方向符号推导）
- 安全约束：绑定非本机地址必须设置口令，否则拒绝启动；静态文件目录穿越防护

### Changed

- `writer.render_transaction` 支持渲染交易与分录元数据（归类等重写操作可无损保留 `; 键: 值`）
- 用户手册新增第 10 章「浏览器界面（本地服务）」与 HTTP 接口表

## [0.2.0] - 2026-09-26

对应里程碑 M1：报表、导入与语言完备。

### Added

- 语言完备：关键字中英双写（`选项/option`、`开立/open`、`断言/balance`、`定期/recur`、`起止/from-to`、周期与选项键值），`core/keywords.py` 为单一事实源
- 写回语言策略：默认中文、按文件跟随，`option "keyword_language"` 可强制
- `docs/语法大全.md`（对照表由 `scripts/生成语法大全.py` 从代码生成，测试断言一致）与 `docs/语法速查.md`
- `规范`（`normalize`）命令：全角 ↔ 半角一键规范化，含未闭合引号与不配对花括号的检测与 `--修复未闭合`
- `初始化`（`init`）命令：一键生成账本骨架（main.knot / 年份文件 / 别名 / 分类规则 / .gitignore）
- 一键运行：`knot.bat`（Windows）、`knot.sh`（macOS/Linux）自动准备环境并进入交互菜单；`scripts/打包.py` 生成 `dist/knot.pyz` 单文件
- `菜单`（`menu`）命令：交互式主菜单
- 报表 `报`（`report`）：概况 / 收支 / 净资产 / 分类 / 科目，支持 `--json`
- 图表 `图`（`chart`）：ChartSpec → 自包含 SVG，支持柱 / 线 / 饼 / 树（treemap）/ 热力（日历），>300 点自动降采样
- 账单导入 `导入`（`import`）：微信 / 支付宝（GBK 探测）/ 银行（单列或收支两列），表头定位、指纹去重、分类规则套用、`费用:待分类` 兜底、`--试运行`
- 测试：新增 `test_keywords`、`test_convert`、`test_init`、`test_report`、`test_importer` 与导入样例数据

### Changed

- 解析器接受中英关键字混写；`Options.from_pairs` 归一化中文选项键与取值
- 开发文档升至 1.2：新增 §3.8 关键字中英双写、§3.9 一键规范化、§16.2 M1 任务分解与功能 F11–F13
- 用户手册增补「一键运行与账本生成」「中英双写」「报表与图表」「账单导入」「一键规范化」五节

### Notes

- 诊断与提示文案保持中文（0.2.0 范围收敛；关键字纠错建议会按文件语言给出对应写法）
- PyPI 尚未发布，安装方式见 README

## [0.1.0] - 2026-09-26

对应里程碑 M0：内核与 CLI 记账。

### Added

- 仓库初始化：README、贡献指南（提交规范）、变更日志、GPL-3.0 许可证
- 开发文档《结绳Knot开发文档》纳入版本管理
- 版本规划文档 [《版本规划》](./docs/版本规划.md)：版本号自 `0.1.0` 起步，稳定化版本为 `0.7.0`
- 内核：中文基础模块（控制台 UTF-8、东亚宽度、全角归一化、中文数字金额、中文日期、别名系统、分类规则）
- 内核：词法与手写递归下降解析器，含恐慌模式恢复、中文诊断与纠错建议
- 内核：`include` 展开与解析缓存、定期交易展开、结构化查询过滤器
- 内核：校验流水线（自动开立科目、单腿配平、借贷平衡、库存成本、余额断言、会计恒等式）
- 内核：增量写回（行级编辑、原子替换、沿用既有缩进与列对齐）、格式化对齐、宽度感知表格
- CLI：`记 / 查 / 余 / 检查 / 整理 / 别名` 子命令，中文命令别名，`--补全` 生成 bash / zsh / fish 脚本
- `schema/GRAMMAR.md` 定稿；`schema/测试数据/` 黄金用例与 `tests/` 测试套件
- 用户手册 [docs/用户手册.md](./docs/用户手册.md)

### Changed

- 开发文档 v1.1：文件扩展名由 `.ledger` 统一为 `.knot`；Python 包版本起点由 `1.0.0` 调整为 `0.1.0`
