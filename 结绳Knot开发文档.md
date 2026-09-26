# 结绳 Knot · 开发文档

| 项 | 值 |
|---|---|
| 项目名称（中文） | **结绳** |
| 项目名称（英文） | **Knot** |
| 包名 / 命令名 | `knot` |
| 文档版本 | 1.2 |
| 文档状态 | 正式 |
| 目标平台 | Windows / macOS / Linux |
| 语言要求 | Python ≥ 3.11（推荐 3.13+） |
| 运行时依赖 | 无（仅 Python 标准库） |
| 适用地区 | 中国大陆（人民币本位、中文输入、中文会计科目） |

**变更记录**

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0 | 2026-09-26 | 首次发布 |
| 1.1 | 2026-09-26 | 文件扩展名由 `.ledger` 统一为 `.knot`；Python 包版本起点调整为 `0.1.0`；里程碑增加版本号对照 |
| 1.2 | 2026-09-26 | v0.2.0 范围并入关键字中英双写、一键规范化、一键运行与账本生成；新增 §3.8、§3.9、§16.2 与功能 F11–F13 |

---

## 目录

1. 项目概述
2. 术语与命名规范
3. 账本语法规范
4. 技术栈与依赖约束
5. 中文环境规范
6. 仓库结构
7. Core 内核规范
8. CLI 规范
9. TUI 规范
10. Web 端规范
11. 图表规范
12. 账单导入规范
13. 测试规范
14. 性能规范
15. 分发与部署
16. 里程碑
17. 风险登记册
18. 附录

**规范用语**：本文档中 MUST / MUST NOT / SHOULD / SHOULD NOT / MAY 遵循 RFC 2119 语义。

---

# 1 项目概述

## 1.1 定义

结绳 Knot 是一个以纯文本文件为唯一数据存储的个人复式记账系统，提供 CLI、TUI、Web 三种操作界面，面向中国大陆用户适配中文输入、中文会计科目与人民币本位。

## 1.2 设计约束

以下四条为不可协商的设计约束：

- **C1 文本唯一真相**：系统 MUST NOT 引入数据库作为权威存储。所有写操作的最终结果 MUST 为文本文件的行级变更。
- **C2 内核零依赖**：Core 模块 MUST NOT 依赖任何第三方包，且 MUST NOT 依赖任何 UI 框架。
- **C3 增量写回**：写操作 MUST 仅修改受影响的行区间。全文件重新序列化 MUST NOT 在常规写路径中出现。
- **C4 定点金额**：金额运算 MUST 全程使用 `decimal.Decimal`。`float` MUST NOT 参与任何金额运算。

## 1.3 功能范围

| 编号 | 功能 | 阶段 |
|---|---|---|
| F1 | 纯文本账本解析、校验、格式化 | M0 |
| F2 | 命令行记账、查询、报表 | M0 |
| F3 | 中文输入适配（全角归一化、中文数字、中文日期） | M0 |
| F4 | 别名系统与学习式分类规则 | M0 |
| F5 | 账单导入（微信 / 支付宝 / 银行 CSV） | M1 |
| F6 | 报表聚合与图表数据生成 | M1 |
| F7 | Web 界面（本地服务） | M2 |
| F8 | TUI 界面（终端三栏） | M3 |
| F9 | 拼音检索 | M4 |
| F10 | 多币种投资、成本基础、预算、对账 | M4 |
| F11 | 一键运行（启动脚本 / 单文件）与账本生成（`初始化`） | M1 |
| F12 | 关键字中英双写与语法大全 | M1 |
| F13 | 全角 / 半角一键规范化（`规范`） | M1 |

## 1.4 非功能目标

| 编号 | 目标 |
|---|---|
| N1 | 账本文件可被人直接阅读、用任意文本编辑器修改、纳入 Git 版本管理 |
| N2 | 常规写操作产生的 diff 仅包含实际变更的行 |
| N3 | 单文件分发，无需安装过程或仅需 Python 解释器 |

---

# 2 术语与命名规范

## 2.1 术语表

| 术语 | 英文 | 定义 |
|---|---|---|
| 账本 | Ledger | 存储全部会计数据的一个或多个 `.knot` 文本文件集合 |
| 主账本 | Main ledger | 入口文件，默认为 `main.knot` |
| 指令 | Directive | 账本中的一条顶层记录 |
| 交易 | Transaction | 记录一次资金变动的指令 |
| 分录 | Posting | 交易中的一行，描述一个科目的金额变动 |
| 科目 | Account | 以冒号分隔的层级式会计科目名 |
| 科目根 | Account root | 五大顶层科目之一 |
| 对手科目 | Counterparty | 流水简写中由 `@` 指定的对方科目 |
| 自动配平腿 | Balancing posting | 由系统计算生成的分录 |
| 断言 | Balance assertion | 指定日期上某科目应有余额的校验声明 |
| 定期交易 | Recurring transaction | 按周期展开的模板，仅在内存中实例化 |
| 别名 | Alias | 短名称到完整科目名或命令关键字的映射 |
| 诊断 | Diagnostic | 解析或校验过程中产生的错误、警告、提示 |
| ChartSpec | ChartSpec | 与渲染无关的图表中间数据结构 |

## 2.2 项目命名

| 用途 | 名称 |
|---|---|
| 中文名 | 结绳 |
| 英文名 | Knot |
| PyPI 包名 | `knot`（若被占用则 `knot-ledger`） |
| Python 包名 | `knot` |
| CLI 命令 | `knot` |
| 文件扩展名 | `.knot` |
| 主账本默认名 | `main.knot` |

**命名释义**：结绳记事是人类最早的记账形式。项目名称取"绳结"之意——每一笔交易是一个结，整本账是串起来的绳。与纯文本账本"用最朴素符号记录金钱"的设计哲学一致。

## 2.3 标识符命名约定

| 对象 | 约定 | 示例 |
|---|---|---|
| Python 模块 | 英文小写，下划线 | `number_cn.py` |
| Python 类 | 大驼峰 | `Transaction` |
| Python 函数 | 英文小写，下划线 | `parse_amount` |
| 账本目录与文件名 | 中文 | `别名.knot`、`规则/分类规则.knot` |
| HTTP 路径 | 中文 | `/api/流水` |
| CLI 命令 | 英文为主，中文别名 | `add` / `记` |

---

# 3 账本语法规范

> 本章为全系统唯一数据契约。实现前 MUST 完成 `schema/GRAMMAR.md` 定稿。

## 3.1 基本约定

| 项 | 规范 |
|---|---|
| 编码 | UTF-8。读取 MUST 兼容 BOM（`utf-8-sig`）。写入默认不带 BOM |
| 扩展名 | `.knot` |
| 注释 | 以 `;` 起始，可整行或行尾 |
| 行尾 | 兼容 LF / CRLF |
| 缩进 | 分录相对指令行缩进；推荐 2 空格，MUST 探测并沿用文件既有风格 |
| 顺序 | 文本顺序 MUST NOT 影响语义。加载后按日期排序 |

## 3.2 指令全集

| 指令 | 语法 | 说明 |
|---|---|---|
| `option` | `option "键" "值"` | 全局选项 |
| `include` | `include "路径或通配符"` | 引入其它文件 |
| `open` | `日期 open 科目 [币种…] [元数据]` | 开立科目 |
| `close` | `日期 close 科目` | 关闭科目 |
| `balance` | `日期 balance 科目 金额` | 余额断言 |
| `price` | `日期 price 商品 金额` | 报价 / 汇率 |
| `commodity` | `日期 commodity 代码` | 商品声明 |
| `recur` | `日期 recur "周期" "说明" from 起 to 止` + 分录 | 定期交易模板 |
| `budget` | `日期 budget 周期 科目 金额` | 预算 |
| `event` | `日期 event "名称" "值"` | 备忘事件 |
| 交易 | `日期 [标志] "收款方" ["摘要"]` + 分录 | 见 3.3 |

## 3.3 交易语法

```
日期 [标志] ["收款方"] ["摘要"] [#标签…] [^链接…]
  [; 元数据键: 值]
  科目  [金额] [币种] [{成本}|@单价|@@总价] [@对手科目]
  科目  [金额] [币种] ...
```

### 3.3.1 标志

| 标志 | 含义 | 用途 |
|---|---|---|
| `*` | 已确认（默认） | 正常交易 |
| `!` | 待确认 | 需复核 |
| `?` | 待分类 | 收件箱，默认归入 `费用:待分类` |
| `P` | 已对账 | 已与账单核对 |

### 3.3.2 金额写法

| 写法 | 语义 |
|---|---|
| `38.00 CNY` | 显式币种金额 |
| `38.00` | 省略币种，取科目默认币种 |
| 留空 | 自动配平腿，由系统计算 |
| `-173.00 CNY` | 负值 |
| `1000 FUND {3.8500 CNY}` | 带成本基础（单价） |
| `1000 FUND @ 4.10 CNY` | 带成交价 |
| `1000 FUND @@ 4100.00 CNY` | 带总价 |

### 3.3.3 对手科目

单腿交易 MUST 使用 `@ 对手科目` 指定对方科目。未指定时，取 `default_asset`（支出）或 `default_income`（收入）。系统据此生成反向分录，并标记 `generated=True`。

## 3.4 五大科目根

存储 MUST 使用中文规范名。英文形式为输入别名，归一化后转为中文。

| 规范名 | 英文别名 | 缩写 | 中文别名 |
|---|---|---|---|
| 资产 | `Assets` | `A` | — |
| 负债 | `Liabilities` | `L` | — |
| 权益 | `Equity` | `E` | 所有者权益、净资产 |
| 收入 | `Income` | `I` | 进账 |
| 费用 | `Expenses` | `X` | 支出 |

费用根缩写为 `X`，以规避与权益（`E`）冲突。

### 3.4.1 会计恒等式

以下恒等式 MUST 在校验阶段验证：

```
资产 = 负债 + 权益
利润 = 收入 - 费用
资产 = 负债 + 权益 + (收入 - 费用)      ; 结账前扩展式
```

## 3.5 选项

| 键 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `operating_currency` | 币种代码 | `CNY` | 记账本位币 |
| `strict` | `off` / `warn` / `on` | `warn` | 宽容度 |
| `account_language` | `zh` / `en` | `zh` | 存储与显示语言 |
| `default_asset` | 科目名 | `资产:现金` | 默认付款科目 |
| `default_income` | 科目名 | `收入:其他` | 默认收款科目 |
| `write_bom` | `on` / `off` | `off` | 写入 BOM |
| `sort_accounts` | `unicode` / `pinyin` | `unicode` | 科目排序方式 |
| `pinyin` | `on` / `off` | `off` | 拼音检索 |

### 3.5.1 宽容度定义

| 取值 | 行为 |
|---|---|
| `off` | 科目即用即建；单腿自动配平；未声明事项产生 hint |
| `warn` | 同上，并对未声明科目产生 warning |
| `on` | 科目 MUST 先 `open`；交易 MUST 显式双腿平衡；未知币种报错 |

## 3.6 语法示例

```knot
; ══════════ 全局选项 ══════════
option "operating_currency" "CNY"
option "strict"             "warn"
option "account_language"   "zh"
option "default_asset"      "资产:现金"
option "default_income"     "收入:其他"

include "别名.knot"
include "规则/分类规则.knot"
include "2026/*.knot"

; ══════════ 科目声明 ══════════
2026-01-01 open 资产:银行:招行     CNY
2026-01-01 open 资产:现金          CNY
2026-01-01 open 资产:第三方:支付宝  CNY
2026-01-01 open 负债:信用卡:招行    CNY
2026-01-01 open 收入:工资          CNY
2026-01-01 open 费用:待分类
2026-01-01 open 权益:期初

; ══════════ 期初余额 ══════════
2026-01-01 * "期初"
  资产:银行:招行   12,300.00 CNY
  权益:期初

; ══════════ 完整复式 ══════════
2026-01-05 * "腾讯" "1月工资"
  收入:工资          -18,000.00 CNY
  资产:银行:招行      18,000.00 CNY

; ══════════ 流水简写 ══════════
2026-01-06 "早餐 豆浆油条"    费用:餐饮:早餐    8.50 CNY  @ 资产:现金
2026-01-06 "地铁"            费用:交通          6.00 CNY  @ 资产:现金
2026-01-07 "房租"            费用:居住:房租 3,500.00 CNY  @ 资产:银行:招行

; ══════════ 极简写法 ══════════
2026-01-08 "买菜"            费用:餐饮:食材    62.30 CNY

; ══════════ 待分类收件箱 ══════════
2026-01-09 ? "便利店"        费用:待分类       25.00 CNY  @ 负债:信用卡:招行

; ══════════ 标签 / 链接 / 元数据 ══════════
2026-01-10 * "团建 AA" #工作聚餐 ^proj-2026Q1
  ; 凭证: ./凭证/2026-01-10-团建.jpg
  费用:餐饮:聚餐      180.00 CNY  @ 资产:现金

; ══════════ 多分录 ══════════
2026-01-11 * "超市"
  费用:餐饮:食材     128.00 CNY
  费用:日用品         45.00 CNY
  资产:现金                -173.00 CNY

; ══════════ 自动配平 ══════════
2026-01-12 * "饭钱"
  费用:餐饮:聚餐      88.00 CNY
  资产:现金

; ══════════ 余额断言 ══════════
2026-02-01 balance 资产:银行:招行   29,845.20 CNY

; ══════════ 定期交易模板 ══════════
2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-12-01
  费用:居住:房租   3,500.00 CNY  @ 资产:银行:招行

; ══════════ 多币种与成本 ══════════
2026-03-01 * "买入沪深300"
  资产:投资:沪深300    1000 FUND {3.8500 CNY}
  资产:银行:招行      -3,850.00 CNY

2026-06-01 price FUND 4.1200 CNY

; ══════════ 预算 ══════════
2026-01-01 budget monthly 费用:餐饮  2000.00 CNY
```

## 3.7 词法：科目名字符类

```python
ACCOUNT_CHARS = (
    r"\u4e00-\u9fff"      # CJK 统一表意文字
    r"\u3400-\u4dbf"      # CJK 扩展 A
    r"\uf900-\ufaff"      # CJK 兼容表意文字
    r"A-Za-z0-9_\-"
)
ACCOUNT_RE = re.compile(f"[{ACCOUNT_CHARS}]+(:[{ACCOUNT_CHARS}]+)*")
```

实现 MUST NOT 使用 `\w` 匹配科目名字符，其 Unicode 行为在不同版本间存在歧义。

## 3.8 关键字中英双写（v0.2.0 起）

账本中的**关键字**（指令、选项键、选项值、周期、`from`/`to`）MUST 同时接受英文与中文两种写法，两者语义完全等价。

- 单一事实源：`core/keywords.py` 维护映射表与规范化函数，其它模块 MUST NOT 自行硬编码关键字字面量
- 写回语言：默认**中文**；若文件内既有指令为英文，则沿用该文件的英文（**按文件跟随**）；`option "keyword_language" "en"` 可强制英文
- `整理` / `规范` MUST NOT 改变既有文件的关键字语言（幂等）
- 标志符号（`*` `!` `?` `P`）MUST NOT 提供中文写法：该位置与收款方 / 摘要相邻，中文词会造成歧义
- 对照表见 [`docs/语法大全.md`](./docs/语法大全.md)，由 `scripts/生成语法大全.py` 从关键字表生成，`tests/test_keywords.py` 断言二者一致

## 3.9 一键规范化（v0.2.0 起）

`knot 规范` 提供全角 / 半角一键转换：

| 方向 | 作用范围 | 说明 |
|---|---|---|
| 全 → 半 | 句法层（默认） | 科目层级 `：`、千分位 `，`、引号 `“”`、注释 `；`、标签链接 `＃＾`、`＠`、`｛｝`、货币符号 `￥`、全角数字字母、全角空格 |
| 全 → 半 | 全部（`--范围 全部`） | 上述之外，引号内文本也转换 |
| 半 → 全 | 全部（`--范围 全部`） | 引号内文本的中文标点按 `，。！？（）【】“”` 转换；句法层 MUST 保持半角 |

- 未闭合字符串、不配对括号：默认**只报告诊断**；`--修复未闭合` 才在行尾补全引号 / 括号
- `--试运行` MUST NOT 写文件；`--检查` 以退出码表示「是否需要规范化」
- 转换 MUST 幂等：对同一文件重复执行，第二次的结果 MUST 与第一次相同

---

# 4 技术栈与依赖约束

## 4.1 选型

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python ≥ 3.11 | 推荐 3.13+；3.15 起 UTF-8 为默认编码（PEP 686） |
| 金额 | `decimal.Decimal` | 见 7.2 |
| 数据模型 | `dataclasses` | 使用 `slots=True` |
| CLI | `argparse` | 子命令使用 `add_subparsers` 与 `aliases` |
| TUI | 自研 ANSI 绘制层 | `termios` / `tty` / `select` / `msvcrt` / `shutil` |
| Web | `http.server.ThreadingHTTPServer` | 配合 `urllib.parse`、`json` |
| 前端图表 | 原生 SVG 或内嵌 `echarts.min.js` | 非 Python 依赖 |
| 中文宽度 | `unicodedata.east_asian_width` | 标准库 |
| 全角归一化 | `unicodedata.normalize` + 映射表 | 标准库 |
| 纠错建议 | `difflib.get_close_matches` | 标准库 |
| 测试 | `unittest` | 黄金测试驱动器 |

## 4.2 依赖约束

**运行时依赖数量 MUST 为 0。** 以下包 MUST NOT 出现在 `pyproject.toml` 的 `dependencies` 中：

`typer` `textual` `fastapi` `uvicorn` `pydantic` `matplotlib` `numpy` `pandas` `SQLAlchemy` `argcomplete` `shtab` `windows-curses` `watchfiles` `requests`

开发期工具（格式化、类型检查、测试增强）MAY 置于 `dependency-groups.dev`，且 MUST NOT 进入运行时。

## 4.3 约束说明

### 4.3.1 TUI 不使用 curses

标准库 `curses` 在 Windows 平台无 `_curses` C 扩展（官方 CPython 不为 Windows 编译），需第三方 `windows-curses` 才能导入。为满足 4.2 约束，TUI MUST 基于 ANSI 转义序列自行实现。

### 4.3.2 Web 不使用第三方框架

本项目为本地单人工具，默认仅监听 `127.0.0.1`。`http.server` 的并发与吞吐满足需求。使用 `ThreadingHTTPServer` 以避免长连接阻塞。

### 4.3.3 CLI 不使用第三方参数库

`argparse` 满足全部需求。唯一缺失为 shell 补全，由 8.5 定义的静态补全生成解决。

---

# 5 中文环境规范

## 5.1 语言标识体系

存储 MUST 使用中文规范名。英文形式与缩写为输入别名，经别名系统归一化后转为中文。

`option "account_language"` 仅在 `en` 时反转该映射方向。该切换 MUST NOT 改变账本结构。

### 5.1.1 报表术语

| 概念 | 显示名 |
|---|---|
| Balance Sheet | 资产负债表 |
| Income Statement | 利润表 |
| Cash Flow Statement | 现金流量表 |
| Trial Balance | 试算平衡表 |
| Net Worth | 净资产（资产 − 负债） |
| Debit / Credit | 借方 / 贷方 |
| Posting | 分录 |
| Opening / Closing Balance | 期初余额 / 期末余额 |
| Reconciliation | 对账 |

## 5.2 别名系统

别名系统 MUST 同时支持科目名映射与命令关键字映射。

### 5.2.1 解析优先级

| 优先级 | 来源 | 可修改 |
|---|---|---|
| 1 | 用户自定义：`账本目录/别名.knot` | 是 |
| 2 | 内置常用科目：`core/aliases.py` 内嵌字典 | 否（可被 1 覆盖） |
| 3 | 内置科目根常量 | 否 |

### 5.2.2 别名文件格式

```
; 格式：别名 = 目标
; 目标可为完整科目名或命令关键字
```

### 5.2.3 内置别名（第 2 层）

**科目根**

```
A = 资产    L = 负债    E = 权益    I = 收入    X = 费用
Assets = 资产    Liabilities = 负债    Equity = 权益
Income = 收入    Expenses = 费用
支出 = 费用    进账 = 收入
```

**常用资产**

```
现金 = 资产:现金
银行 = 资产:银行
招行 = 资产:银行:招行        cmb = 资产:银行:招行
建行 = 资产:银行:建行        工行 = 资产:银行:工行
支付宝 = 资产:第三方:支付宝   alipay = 资产:第三方:支付宝
微信 = 资产:第三方:微信       wechat = 资产:第三方:微信
余额宝 = 资产:投资:余额宝     证券 = 资产:投资:证券
```

**常用负债**

```
信用卡 = 负债:信用卡    花呗 = 负债:信用卡:花呗
房贷 = 负债:贷款:房贷    车贷 = 负债:贷款:车贷
```

**常用收入**

```
工资 = 收入:工资    salary = 收入:工资
奖金 = 收入:工资:奖金    理财 = 收入:投资收益
```

**常用费用**

```
餐饮 = 费用:餐饮    吃饭 = 费用:餐饮
早餐 = 费用:餐饮:早餐    午餐 = 费用:餐饮:午餐    外卖 = 费用:餐饮:外卖
交通 = 费用:交通    打车 = 费用:交通:打车    地铁 = 费用:交通:公共交通
房租 = 费用:居住:房租    水电 = 费用:居住:水电
购物 = 费用:购物    医疗 = 费用:医疗    娱乐 = 费用:娱乐
教育 = 费用:教育    人情 = 费用:人情往来    待分类 = 费用:待分类
```

**命令关键字**

```
记 = add    查 = show    余 = bal    图 = chart    报 = report
检查 = check    整理 = fmt    导入 = import    对账 = reconcile    服务 = serve
```

### 5.2.4 解析算法

```
输入记号
  1. 精确命中别名表 → 返回目标
  2. 本身为合法完整科目名 → 直接返回
  3. 别名键为其前缀或子串 → 唯一匹配则返回
  4. 拼音匹配（pinyin=on 时）
  5. 唯一匹配 → 返回
  6. 多候选 → 返回候选列表，要求用户选择
  7. 无匹配 → strict=off/warn 时按层级新建科目并产生提示；strict=on 时报错
```

多候选时 MUST 输出编号列表并接受编号或完整科目名。

### 5.2.5 学习式分类规则

「收款方 → 科目」映射 MUST 自动沉淀至 `规则/分类规则.knot`（纯文本）。匹配 MAY 使用子串或正则。该文件 MUST 可被用户手工编辑。

## 5.3 输入归一化

所有用户输入 MUST 在进入解析前经过 `normalize_text()`。

### 5.3.1 全角转半角映射

```python
FULLWIDTH_MAP = str.maketrans({
    "：": ":", "，": ",", "。": ".",
    "（": "(", "）": ")", "！": "!", "？": "?", "；": ";",
    "％": "%", "／": "/", "＼": "\\", "－": "-", "＿": "_",
    "　": " ",                      # U+3000 全角空格
    "￥": "¥", "＄": "$",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "．": ".", "＋": "+", "＝": "=", "＊": "*",
})

def normalize_text(s: str) -> str:
    s = s.translate(FULLWIDTH_MAP)
    return unicodedata.normalize("NFKC", s)
```

顺序 MUST 为先 `translate` 后 `normalize`，以避免自定义映射被 NFKC 二次处理。

### 5.3.2 中文数字金额

```python
UNITS = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10_000, "萬": 10_000,
    "亿": 100_000_000, "億": 100_000_000,
    "k": 1000, "K": 1000, "w": 10_000, "W": 10_000,
}
```

余数规则：`N单位M` 中 `M` 乘以 `单位 / 10`。

| 输入 | 值 |
|---|---|
| `38` | 38 |
| `38.5` / `38元` / `¥38` | 38.5 / 38 / 38 |
| `3千` | 3000 |
| `1.5万` | 15000 |
| `2万3` | 23000（20000 + 3×1000） |
| `3千5` | 3500（3000 + 5×100） |
| `1亿2千万` | 120000000 |
| `1,234.56` | 1234.56 |
| `38块5` | 38.5 |

### 5.3.3 中文日期

| 输入 | 语义 |
|---|---|
| `今天` / `今日` / `today` | 当前日期 |
| `昨天` / `昨日` / `yesterday` | 当前日期 − 1 |
| `前天` | 当前日期 − 2 |
| `明天` | 当前日期 + 1 |
| `本月` / `上月` / `今年` | 对应区间 |
| `9月20日` / `9月20号` | 当年 9 月 20 日 |
| `2026年9月20日` | 2026-09-20 |
| `9/20` / `9-20` / `2026-09-20` | 标准格式 |
| `上周一` / `上周五` | 相对周 |

### 5.3.4 货币符号归一化

| 输入 | 归一化为 |
|---|---|
| `¥` `￥` `CNY` `RMB` `元` `块` `人民币` | `CNY` |
| `$` `USD` `美元` | `USD` |

## 5.4 编码

### 5.4.1 读写约定

文件读写 MUST 显式指定 `encoding="utf-8"`，MUST NOT 依赖解释器默认编码。

读取 MUST 使用 `utf-8-sig` 以兼容 BOM。

### 5.4.2 控制台

```python
def setup_console() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    if sys.platform == "win32":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleCP(65001)
            k.SetConsoleOutputCP(65001)
        except (OSError, AttributeError):
            pass

    for stream, errors in ((sys.stdout, "replace"), (sys.stderr, "replace")):
        try:
            stream.reconfigure(encoding="utf-8", errors=errors)
        except (AttributeError, ValueError):
            pass
```

`setup_console()` MUST 在 CLI 与 TUI 入口最先调用。

`SetConsoleOutputCP(65001)` 仅影响当前进程，进程退出后父 shell 恢复原代码页。

### 5.4.3 账单 CSV 编码探测

```python
def sniff_and_read(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise KnotError(f"无法识别编码：{path}")
```

探测顺序 MUST 为 `utf-8-sig` → `gb18030` → `utf-16`。`gb18030` 为 GB2312 / GBK 超集。

## 5.5 显示宽度

东亚宽字符占 2 个显示列。排版 MUST NOT 使用 `len()` 或 `str.ljust()`。

```python
def char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1

def str_width(s: str) -> int:
    return sum(char_width(c) for c in s)

def pad(s: str, width: int, align: str = "left") -> str:
    n = max(0, width - str_width(s))
    return s + " " * n if align == "left" else " " * n + s

def truncate(s: str, width: int, ellipsis: str = "…") -> str:
    if str_width(s) <= width:
        return s
    w, out = 0, []
    for c in s:
        cw = char_width(c)
        if w + cw > width - str_width(ellipsis):
            break
        out.append(c); w += cw
    return "".join(out) + ellipsis
```

表格列宽 MUST 按 `str_width()` 的最大值计算。

## 5.6 中文输入法

### 5.6.1 前提

IME 的候选与预编辑由终端模拟器或操作系统处理，应用程序接收已提交文本。系统 MUST NOT 自行实现候选框。

### 5.6.2 双模式输入

界面导航使用 raw 模式；文本录入 MUST 切换至 cooked（canonical）模式，交由操作系统行编辑器处理。

```python
@contextmanager
def raw_mode():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        yield fd
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

@contextmanager
def cooked_line():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        new = list(old)
        new[3] |= (termios.ICANON | termios.ECHO)
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
```

### 5.6.3 raw 模式 UTF-8 拼接

```python
_dec = codecs.getincrementaldecoder("utf-8")(errors="replace")

def read_key(timeout: float = 0.1) -> str | None:
    if not select.select([sys.stdin], [], [], timeout)[0]:
        return None
    return _dec.decode(os.read(sys.stdin.fileno(), 1024))
```

Windows 平台使用 `msvcrt.getwch()`。

### 5.6.4 输入面收敛

TUI 表单 MUST 将需自由文本的字段收敛至最小：

| 字段 | 输入方式 | 需 IME |
|---|---|---|
| 金额 | 数字 + 中文单位 | 部分 |
| 科目 | 列表选择 / 别名 | 否 |
| 对手科目 | 列表选择 / 别名 | 否 |
| 日期 | 默认值或 `9-20` | 否 |
| 备注 / 收款方 | 自由文本（可选） | 是 |

## 5.7 拼音检索

拼音检索为 M4 功能，默认关闭。实现 MUST 内嵌常用汉字拼音表（约 3500 字），MAY 压缩存储。索引 MUST 仅覆盖科目名与收款方，运行时按需展开。

---

# 6 仓库结构

```
knot/
├── pyproject.toml
├── README.md
│
├── src/knot/
│   ├── __init__.py
│   ├── __main__.py
│   ├── version.py
│   │
│   ├── core/                       # 内核：零依赖
│   │   ├── model.py
│   │   ├── amount.py
│   │   ├── normalize.py
│   │   ├── number_cn.py
│   │   ├── date_cn.py
│   │   ├── width.py
│   │   ├── console.py
│   │   ├── aliases.py
│   │   ├── rules.py
│   │   ├── i18n.py
│   │   ├── lexer.py
│   │   ├── parser.py
│   │   ├── diagnostic.py
│   │   ├── loader.py
│   │   ├── book.py
│   │   ├── inventory.py
│   │   ├── recur.py
│   │   ├── query.py
│   │   ├── report.py
│   │   ├── chart.py
│   │   ├── writer.py
│   │   ├── fmt.py
│   │   ├── table.py
│   │   └── importer/
│   │       ├── base.py
│   │       ├── wechat.py
│   │       ├── alipay.py
│   │       └── bank.py
│   │
│   ├── cli/
│   │   ├── main.py
│   │   ├── completion.py
│   │   ├── ansi.py
│   │   └── commands/
│   │       ├── add.py   show.py   bal.py    report.py
│   │       ├── chart.py check.py  fmt.py
│   │       ├── import_.py  reconcile.py  serve.py  alias.py
│   │
│   ├── tui/
│   │   ├── term.py
│   │   ├── input.py
│   │   ├── screen.py
│   │   ├── theme.py
│   │   ├── widgets/
│   │   │   ├── list.py
│   │   │   ├── tree.py
│   │   │   ├── form.py
│   │   │   └── spark.py
│   │   └── app.py
│   │
│   └── web/
│       ├── server.py
│       ├── api.py
│       ├── watcher.py
│       └── static/
│           ├── index.html
│           ├── app.js
│           ├── chart.js
│           └── style.css
│
├── schema/
│   ├── GRAMMAR.md
│   ├── chartspec.schema.json
│   └── 测试数据/
│       ├── 基础.knot          基础.expected.json
│       ├── 中文别名.knot      中文别名.expected.json
│       ├── 多币种.knot        多币种.expected.json
│       ├── 定期交易.knot      定期交易.expected.json
│       ├── 微信账单.csv         微信账单.knot
│       └── 畸形输入.knot      畸形输入.expected.json
│
├── tests/
│   ├── test_lexer.py      test_parser.py    test_book.py
│   ├── test_normalize.py  test_number_cn.py test_date_cn.py
│   ├── test_width.py      test_aliases.py   test_encoding.py
│   ├── test_writer.py     test_report.py    test_importer.py
│   └── golden.py
│
└── docs/
    ├── 用户手册.md
    └── 语法速查.md
```

## 6.1 pyproject.toml

```toml
[project]
name = "knot"
version = "0.1.0"
description = "结绳 Knot：纯文本复式记账（CLI / TUI / Web）"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
knot = "knot.cli.main:main"

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["RUF001", "RUF002", "RUF003"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`dependencies` MUST 为空列表。`RUF001/002/003` MUST 被忽略，以避免中文标点产生误报。

---

# 7 Core 内核规范

## 7.1 model.py

```python
class Flag(str, Enum):
    OK      = "*"
    PENDING = "!"
    UNKNOWN = "?"
    CLEARED = "P"

@dataclass(frozen=True, slots=True)
class Amount:
    number: Decimal
    currency: str

@dataclass(frozen=True, slots=True)
class Cost:
    number: Decimal
    currency: str
    kind: str = "unit"          # unit | price | total
    date: date | None = None

@dataclass(slots=True)
class Posting:
    account: str
    units: Amount | None = None
    cost: Cost | None = None
    counterparty: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
    generated: bool = False

@dataclass(slots=True)
class Transaction:
    date: date
    flag: Flag
    payee: str | None
    narration: str
    postings: list[Posting]
    tags: frozenset[str] = frozenset()
    links: frozenset[str] = frozenset()
    meta: dict[str, str] = field(default_factory=dict)
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0

@dataclass(slots=True)
class Balance:
    date: date
    account: str
    amount: Amount
    src_file: str = ""
    src_line_start: int = 0
    src_line_end: int = 0
```

所有指令类型 MUST 携带 `src_file` / `src_line_start` / `src_line_end`。该字段为增量写回的基础，MUST 自解析器首版起存在。

`Open` / `Close` / `Price` / `Commodity` / `Recur` / `Budget` / `Event` 依同约定定义。

## 7.2 amount.py

```python
getcontext().prec = 28
CENT = Decimal("0.01")
TOLERANCE = Decimal("0.005")

def q2(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)
```

约束：

- 金额 MUST 全程使用 `Decimal`
- 解析 MUST NOT 经 `float` 中转
- 平衡校验 MUST 使用 `abs(total) < TOLERANCE`，MUST NOT 使用 `== 0`
- `float()` 转换 MAY 仅出现在 ChartSpec 序列化出口

## 7.3 lexer.py / parser.py

解析器 MUST 为手写递归下降实现，以满足诊断质量要求。

诊断输出格式：

```
main.knot:42:5  错误：未知科目 "费用:餐引"
  42 |   费用:餐引    38.00 CNY
         ^^^^^^^^
  提示：是否意为 "费用:餐饮"？（相似度 0.75）
```

解析器约束：

1. MUST NOT 因单个错误终止解析； MUST 实现恐慌模式恢复（跳至下一日期行）
2. 错误 MUST NOT 抛出异常，MUST 收集至 `Diagnostic` 列表
3. MUST 记录每条指令的源码行区间

纠错建议 SHOULD 使用 `difflib.get_close_matches`。

## 7.4 diagnostic.py

```python
@dataclass(slots=True)
class Diagnostic:
    level: str                   # error | warning | hint
    file: str
    line: int
    col: int
    message: str
    suggestion: str | None = None
    snippet: str | None = None
    caret: str | None = None
```

渲染 MUST 使用 `width.py` 处理显示宽度。

## 7.5 book.py —— 校验流水线

```python
def build(directives, options) -> tuple[Book, list[Diagnostic]]:
    directives = expand_recur(directives)              # 1 展开定期交易
    directives.sort(key=lambda d: (d.date, d.src_line_start))  # 2 稳定排序
    auto_open_accounts(directives, options, diags)     # 3 自动开科目
    balance_single_legs(directives, options, diags)    # 4 单腿配平
    check_balance(directives, diags)                   # 5 借贷平衡
    check_inventory(directives, diags)                 # 6 库存与成本
    check_assertions(directives, diags)                # 7 余额断言
    check_identity(directives, diags)                  # 8 会计恒等式
    return Book(directives, options), diags
```

由 `expand_recur` 生成的交易 MUST NOT 写回文件。

## 7.6 writer.py

```python
@dataclass
class Edit:
    line_start: int
    line_end: int
    new_lines: list[str]

def apply_edits(path: Path, edits: list[Edit]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for e in sorted(edits, key=lambda x: x.line_start, reverse=True):
        lines[e.line_start - 1 : e.line_end] = e.new_lines
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    tmp.replace(path)
```

约束：

- 常规写路径 MUST NOT 重新序列化整个文件
- 编辑 MUST 按行号降序应用，以避免行号偏移
- 写入 MUST 为原子操作（临时文件 + `replace`）
- 新增交易 MUST 插入至对应年份文件的日期位置
- 全量对齐 MUST 仅在 `整理` 命令中执行
- 渲染 MUST 沿用文件的既有缩进宽度与列对齐风格

## 7.7 query.py / report.py / chart.py

M0–M3 MUST 实现结构化过滤器：

```python
@dataclass
class Filter:
    account: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    tags: frozenset[str] = frozenset()
    payee: str | None = None
    min_amount: Decimal | None = None
    currency: str | None = None
```

SQL 子集（`SELECT` / `WHERE` / `GROUP BY` / `ORDER BY`）为 M4 功能。

```python
@dataclass
class Series:
    name: str
    data: list[float]

@dataclass
class ChartSpec:
    type: str                       # bar | line | pie | treemap | heatmap
    title: str
    currency: str
    x: list[str]
    series: list[Series]
    meta: dict
    def to_json(self) -> dict: ...
```

---

# 8 CLI 规范

## 8.1 命令清单

| 命令 | 别名 | 功能 |
|---|---|---|
| `add` | `记` `a` | 记一笔 |
| `show` | `查` `s` | 查看流水 |
| `bal` | `余` `b` | 科目余额 |
| `report` | `报` `r` | 报表 |
| `chart` | `图` `c` | 图表 |
| `check` | `检查` | 校验 |
| `fmt` | `整理` | 格式化对齐 |
| `import` | `导入` | 账单导入 |
| `reconcile` | `对账` | 对账向导 |
| `serve` | `服务` | 启动 Web 服务 |
| `alias` | — | 别名管理 |
| `init` | `初始化` `新建` | 生成账本骨架（M1） |
| `normalize` | `规范` `nrm` | 全角 / 半角一键规范化（M1） |

## 8.2 命令示例

```bash
knot 记 38 餐饮 -f 招行 -n 午饭
knot 记 38 餐饮:午饭 --from 银行:招行 --date 昨天
knot 记 5000 工资 -t 招行
knot 记 2万3 房租 -f 招行
knot 记                                  # 交互式

knot 查 --月 2026-09
knot 余 --树 --深度 2
knot 报 收入|支出|净资产|现金流 --月 2026-09
knot 图 支出 --按 分类 --月 2026-09

knot 检查
knot 整理
knot 导入 微信 账单.csv
knot 对账 资产:银行:招行
knot 服务 --端口 5000

knot 别名 列表
knot 别名 添加 星巴克 费用:餐饮:咖啡
knot 别名 删除 星巴克

knot --补全 bash > ~/.knot-completion.bash
```

## 8.3 参数定义

```python
p = argparse.ArgumentParser(prog="knot", description="结绳 Knot：纯文本复式记账")
p.add_argument("--账本", "--ledger", dest="ledger", default="main.knot")
p.add_argument("--补全", dest="completion", choices=["bash", "zsh", "fish"])
sub = p.add_subparsers(dest="cmd", required=True)

pa = sub.add_parser("add", aliases=["记", "a"], help="记一笔")
pa.add_argument("金额", metavar="金额")
pa.add_argument("科目", metavar="科目")
pa.add_argument("-f", "--from", dest="from_")
pa.add_argument("-t", "--to", dest="to_")
pa.add_argument("-d", "--date", default="今天")
pa.add_argument("-n", "--note")
pa.add_argument("--标签", dest="tags", action="append")
```

## 8.4 输出与退出码

| 流 | 内容 |
|---|---|
| stdout | 正常结果 |
| stderr | 错误与诊断 |

| 退出码 | 含义 |
|---|---|
| 0 | 正常 |
| 1 | 账本校验失败 |
| 2 | 参数或用法错误 |
| 130 | 用户中断 |

`--json` MAY 附加于任意查询类命令，输出结构化结果供管道消费。

`check` MUST 支持作为 Git pre-commit 钩子使用。

## 8.5 彩色输出与补全

```python
_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def style(text: str, *codes: int) -> str:
    if not _ENABLED:
        return text
    return f"\033[{';'.join(map(str, codes))}m{text}\033[0m"
```

Windows 平台输出前 MUST 调用 `enable_vt()`。

shell 补全 MUST 由 `cli/completion.py` 生成静态脚本（bash / zsh / fish）。实现 SHOULD 遍历 `ArgumentParser` 的子命令与选项生成 `COMPREPLY`。

---

# 9 TUI 规范

## 9.1 终端控制

```python
def enable_vt() -> None:
    if sys.platform != "win32":
        return
    k = ctypes.windll.kernel32
    STD_OUTPUT_HANDLE = -11
    ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
    h = k.GetStdHandle(STD_OUTPUT_HANDLE)
    mode = ctypes.c_uint32()
    k.GetConsoleMode(h, ctypes.byref(mode))
    k.SetConsoleMode(h, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

def size() -> tuple[int, int]:
    cols, rows = shutil.get_terminal_size((80, 24))
    return rows, cols
```

## 9.2 屏幕缓冲

```python
class Screen:
    def __init__(self):
        self.rows, self.cols = size()
        self.buf = [[" "] * self.cols for _ in range(self.rows)]
        self.prev: list[str] | None = None

    def put(self, row: int, col: int, text: str, style: str = "") -> None:
        c = col
        for ch in text:
            w = char_width(ch)
            if c + w > self.cols:
                break
            self.buf[row][c] = ch
            for k in range(1, w):
                self.buf[row][c + k] = ""
            c += w

    def flush(self, out) -> None:
        curr = ["".join(r) for r in self.buf]
        if self.prev is None:
            out.write("\033[2J\033[H")
        else:
            for i, (a, b) in enumerate(zip(self.prev, curr)):
                if a != b:
                    out.write(f"\033[{i+1};1H\033[K{b}")
        out.write("\033[?7l")
        out.flush()
        self.prev = curr
```

渲染 MUST 仅重绘发生变更的行。宽字符 MUST 在缓冲区中占位。

## 9.3 控件

| 模块 | 职责 |
|---|---|
| `widgets/list.py` | 可滚动流水表：方向键、PageUp/PageDown、`/` 搜索 |
| `widgets/tree.py` | 科目树：按 `:` 层级构建，支持折叠展开 |
| `widgets/form.py` | 记账表单；文本字段使用 `cooked_line()` |
| `widgets/spark.py` | 盲文迷你图（8 级） |

## 9.4 布局与键位

```
┌─ 科目树 ───────┬─ 流水列表 ────────────────┬─ 详情 ──────────┐
│ ▾ 资产         │ 09-20  餐饮:午饭    38.00 │ 日期 2026-09-20 │
│   ▾ 银行       │ 09-20  交通:地铁     6.00 │ 收款方 楼下快餐 │
│     招行 12.3k │ 09-21  餐饮:食材    62.30 │ ─────────────── │
│     建行  3.2k │ 09-22  居住:房租 3,500.00 │ 支出  38.00 CNY │
│   现金    820  │                           │   → 资产:现金   │
│ ▾ 费用         │                           │ 标签  #工作日   │
│   餐饮  1,240  │                           ├─────────────────┤
│   交通    310  │                           │ 本月支出 ▁▃▅█▂▁ │
└────────────────┴───────────────────────────┴─────────────────┘
 a记账 e编辑 /搜索 f筛选 t图表 s排序 ?帮助 q退出
```

| 键 | 动作 |
|---|---|
| `a` | 新增 |
| `e` | 编辑 |
| `/` | 搜索 |
| `f` | 筛选 |
| `t` | 图表 |
| `s` | 排序 |
| `?` | 帮助 |
| `q` | 退出 |

实现约束：TUI MUST NOT 实现通用 widget 树、布局引擎或样式表。布局为固定三栏，按行列直接计算坐标。总代码量 SHOULD 控制在 800 行以内。

---

# 10 Web 端规范

## 10.1 架构

```
浏览器 ←HTTP JSON→ http.server ←→ Core
                        ↓ mtime 轮询
                    *.knot
```

- 后端职责限定为：读账本产出 JSON；接收写请求并调用 `writer.apply_edits`
- 前端为静态资源，随包分发，MUST NOT 依赖 CDN

## 10.2 路由

```python
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if   u.path == "/api/流水":                 self._json(api.list_txs(q))
        elif u.path == "/api/余额":                 self._json(api.balances(q))
        elif u.path.startswith("/api/报表/"):       self._json(api.report(u.path, q))
        elif u.path.startswith("/api/图表/"):       self._json(api.chart(u.path, q))
        elif u.path == "/api/科目":                 self._json(api.accounts(q))
        elif u.path == "/api/别名":                 self._json(api.aliases(q))
        elif u.path == "/api/变更":                 self._sse()
        else:                                        self._static(u.path)
```

服务器 MUST 使用 `ThreadingHTTPServer`。

## 10.3 变更推送（SSE）

```python
def _sse(self):
    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
    self.send_header("Cache-Control", "no-cache")
    self.end_headers()
    for change in watch_ledger():
        payload = json.dumps(change, ensure_ascii=False)
        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
        self.wfile.flush()
```

实现 MUST NOT 使用 WebSocket。文件监听 SHOULD 采用 `os.stat().st_mtime` 轮询（间隔 500 ms）。

## 10.4 页面

| 页面 | 内容 |
|---|---|
| 仪表盘 | 净资产趋势、本月收支对比、分类占比、预算进度、最近流水 |
| 记一笔 | 一行式快速记账 / 完整表单 |
| 流水 | 虚拟滚动表格、批量归类待分类、筛选器 |
| 科目 | 树形结构、余额走势 |
| 报表 | 资产负债表、利润表、现金流量表 |
| 导入向导 | 拖入 CSV → 规则预览 → 去重确认 → 写入 |

## 10.5 前端约定

- `<html lang="zh-CN">`
- 字体栈：`"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei", sans-serif`
- 数字格式使用 `Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' })`

## 10.6 安全约束

- 默认监听地址 MUST 为 `127.0.0.1`
- 绑定 `0.0.0.0` 时 MUST 启用口令保护
- 文档 MUST 明确声明该服务不得直接暴露至公网

---

# 11 图表规范

## 11.1 渲染分工

| 端 | 渲染方式 |
|---|---|
| CLI | 输出 ChartSpec JSON，或打印 Web 地址 |
| TUI | 盲文迷你图（消费同一 ChartSpec） |
| Web | 原生 SVG 或 ECharts，消费同一 JSON |

三端 MUST 消费同一 `ChartSpec`，以保证数值一致性。

## 11.2 图表清单

| 编号 | 图表 | 类型 | 阶段 |
|---|---|---|---|
| 1 | 净资产趋势 | 折线 | M1 |
| 2 | 月度收支对比 | 双系列柱状 | M1 |
| 3 | 支出分类占比 | 环形 / 矩形树图 | M1 |
| 4 | 分类趋势 | 堆叠面积 | M1 |
| 5 | 科目余额随时间 | 多线 | M1 |
| 6 | 现金流瀑布图 | 瀑布 | M4 |
| 7 | 预算进度 | 仪表盘 | M4 |
| 8 | 消费日历热力图 | 热力图 | M4 |

---

# 12 账单导入规范

## 12.1 来源适配

| 来源 | 前置处理 |
|---|---|
| 微信支付账单 | 跳过前 16 行；表头位于第 17 行；剥离 `¥` 前缀；按状态过滤退款行 |
| 支付宝账单 | 跳过前 24 行；剔除末尾统计行；过滤「不计收支」类型 |
| 银行流水 | 借贷分列合成为正负金额；余额列可生成 `balance` 断言 |
| Excel 导出 CSV | 兼容 BOM；嗅探分隔符（`,` / `\t`） |

各来源 MUST 提供对应 importer 与规则文件。规则文件 MUST 为纯文本且可手工编辑。

## 12.2 导入流程

```
读取 CSV
 → 编码探测 → 跳行 → 表头校验
 → 应用规则匹配科目（学习式规则 + 别名）
 → 预览：高亮未匹配科目的行
 → 去重（日期 + 金额 + 收款方 指纹）
 → 用户确认
 → writer 批量写入
```

导入 MUST 执行去重。

## 12.3 规则文件格式

```
; 规则/分类规则.knot
星巴克 = 费用:餐饮:咖啡
瑞幸   = 费用:餐饮:咖啡
美团   = 费用:餐饮:外卖
滴滴   = 费用:交通:打车
腾讯   = 收入:工资
```

---

# 13 测试规范

## 13.1 黄金测试

`schema/测试数据/` 存放「输入账本 + 期望输出 JSON」对。

```python
CASES = sorted(pathlib.Path("schema/测试数据").glob("*.knot"))

def test_golden(ledger_path):
    book, diags = loader.load_file(ledger_path)
    assert [d for d in diags if d.level == "error"] == []
    actual = report.summarize(book)
    expected = json.loads(
        ledger_path.with_suffix(".expected.json").read_text(encoding="utf-8")
    )
    assert actual == expected
```

新增功能 MUST 先添加测试用例再实现。

## 13.2 必选测试

| 测试 | 断言要点 |
|---|---|
| `test_lexer.py` | 中文科目词法；行号列号 |
| `test_parser.py` | 各类畸形输入；恐慌恢复 |
| `test_book.py` | 借贷平衡、自动配平、库存成本、断言、恒等式 |
| `test_normalize.py` | 全角冒号、全角数字、全角空格、`￥` |
| `test_number_cn.py` | `38` `3千` `1.5万` `2万3` `38块5` `¥38` |
| `test_date_cn.py` | 今天 / 昨天 / 前天 / `9月20日` / `2026年9月20日` / 上月 |
| `test_width.py` | `str_width("资产:银行") == 11`；截断不破坏汉字 |
| `test_aliases.py` | 三层优先级、英文缩写、用户覆盖、多候选 |
| `test_encoding.py` | GBK 解码、BOM 兼容、微信 / 支付宝跳行 |
| `test_writer.py` | 往返一致；**未编辑行字节级不变** |
| `test_report.py` | 报表数值、ChartSpec 结构、边界输入 |
| `test_importer.py` | 各来源解析与去重 |

## 13.3 执行命令

```bash
python -m unittest discover tests
python -m pytest
ruff check . && ruff format .
```

---

# 14 性能规范

| 项 | 要求 |
|---|---|
| 目标规模 | 数万条交易 |
| 解析缓存 | 按 `(file, mtime, size)` 缓存，Web 端 MUST 启用 |
| 内存 | dataclass 使用 `slots=True` / `frozen=True` |
| 优化时机 | 达十万条级别后再考虑分片懒加载与整数分存储 |

---

# 15 分发与部署

## 15.1 方式对照

| 场景 | 方式 |
|---|---|
| 开发 | `python -m venv` + `pip install -e .` |
| 自用 | `python -m zipapp` 生成单文件 |
| 家庭共享 | Docker 部署 Web 服务 |
| Windows 可执行 | Nuitka |

## 15.2 zipapp

```bash
python -m zipapp src -m "knot.cli.main:main" -o knot.pyz
python knot.pyz 记 38 餐饮 -f 招行
```

静态资源 MUST 一并打包。

## 15.3 Docker

```dockerfile
FROM python:3.13-slim
COPY . /app
WORKDIR /app
RUN pip install -e .
EXPOSE 5000
CMD ["python", "-m", "knot", "服务", "--host", "0.0.0.0", "--端口", "5000"]
```

账本目录 MUST 挂载为卷。

## 15.4 可执行程序

- 优先使用 Nuitka
- MUST 使用 CI 矩阵在三平台分别构建（不支持交叉编译）
- 入口 MUST 调用 `setup_console()`
- 打包配置 MUST 设置 `PYTHONUTF8=1`

## 15.5 部署前检查

```
1. PyPI    包名 knot / knot-ledger 可用性
2. GitHub  仓库名 knot 可用性
3. 商标    「结绳」第 9 类（软件）与第 42 类注册情况
```

---

# 16 里程碑

| 阶段 | 版本 | 周期 | 交付 | 验收标准 |
|---|---|---|---|---|
| M0 | v0.1.0 | 2–3 周 | GRAMMAR、parser、book、中文基础模块、CLI 的 `记/查/余/检查/整理` | 可用中文一句话记账；账本可纳入 Git；`检查` 可用作 pre-commit |
| M1 | v0.2.0 | 3–4 周 | report、ChartSpec、账单导入（含 GBK 编码） | 可导入账单并生成净资产趋势与分类占比 |
| M2 | v0.3.0 | 4–6 周 | Web 端（http.server + SSE + SVG 图表） | 浏览器中完成记账全流程 |
| M3 | v0.4.0 | 3–4 周 | TUI（自研 ANSI 层，cooked 模式中文输入） | macOS / Linux 下键盘流记账 |
| M4 前半 | v0.5.0 | 持续 | 定期交易、预算、对账、拼音检索、别名管理 | 各项能力可用且测试覆盖 |
| M4 后半 | v0.6.0 | 持续 | 多币种投资、成本基础、SQL 子集、瀑布图与热力图 | 多币种净值折算正确；ChartSpec 三端一致 |
| 稳定化 | v0.7.0 | — | 语法冻结、Nuitka 三平台可执行、用户手册与语法速查、性能验收 | 数万条交易规模；无 P0 / P1 缺陷；文档齐全 |

版本号策略详见 [docs/版本规划.md](./docs/版本规划.md)。`0.x` 阶段不承诺向后兼容；`1.0.0` 及以上的版本号 MUST 经项目所有者许可后方可规划。

## 16.1 M0 任务分解

| 序号 | 任务 |
|---|---|
| 1 | `schema/GRAMMAR.md` 定稿 |
| 2 | `core/console.py` UTF-8 控制台 |
| 3 | `core/width.py` 东亚宽度 |
| 4 | `core/normalize.py` 全角归一化 |
| 5 | `core/number_cn.py` 中文数字金额 |
| 6 | `core/date_cn.py` 中文日期 |
| 7 | `core/aliases.py` 别名系统 |
| 8 | `core/i18n.py` 中英术语表 |
| 9 | `core/model.py` 数据模型 |
| 10 | `core/amount.py` Decimal 封装 |
| 11 | `core/lexer.py` 词法 |
| 12 | `core/parser.py` 递归下降 |
| 13 | `core/diagnostic.py` 中文诊断 |
| 14 | `core/loader.py` include 展开与缓存 |
| 15 | `core/book.py` 校验流水线 |
| 16 | `core/writer.py` 增量写回 |
| 17 | `core/fmt.py` 格式化对齐 |
| 18 | `core/table.py` 宽度感知表格 |
| 19 | `cli/main.py` 命令树 |
| 20 | `cli/commands/*` 各子命令 |
| 21 | `tests/*` 测试套件 |

任务 2 与 3 MUST 优先于其它模块实现。

## 16.2 M1 任务分解（v0.2.0）

详细计划见 [`docs/开发计划/v0.2.0.md`](./docs/开发计划/v0.2.0.md)。

| 序号 | 任务 | 主题 |
|---|---|---|
| 1 | `core/keywords.py` 关键字中英映射（单一事实源） | A 语言完备 |
| 2 | `lexer.py` / `parser.py` 接受中英双写并记录文件语言 | A |
| 3 | 写回语言策略（默认中文 / 按文件跟随 / 选项覆盖） | A |
| 4 | 诊断词表双语（`i18n.py` 扩展） | A |
| 5 | `scripts/生成语法大全.py` + `tests/test_keywords.py` 一致性校验 | A |
| 6 | `core/convert.py` 全角 → 半角（句法安全集） | B 数据清理 |
| 7 | `core/convert.py` 半角 → 全角（中文标点集） | B |
| 8 | 未闭合字符串 / 不配对括号检测与 `--修复未闭合` | B |
| 9 | `cli/commands/normalize.py`（`规范` 命令） | B |
| 10 | `core/scaffold.py` 账本骨架生成器 | C 上手体验 |
| 11 | `cli/commands/init.py`（`初始化` 命令） | C |
| 12 | 启动脚本 `knot.bat` / `knot.sh`（环境自举 + 无参数菜单） | C |
| 13 | `scripts/打包.py`（zipapp，作为 Release 附件） | C |
| 14 | `core/report.py` 报表聚合 | D 报表与图表 |
| 15 | `cli/commands/report.py`（`报` 命令） | D |
| 16 | `core/chart.py`（`ChartSpec` → SVG） | D |
| 17 | `cli/commands/chart.py`（`图` 命令） | D |
| 18 | `core/importer/base.py` 导入基座（编码探测、跳行、表头、指纹） | E 账单导入 |
| 19 | `importer/wechat.py` / `alipay.py` / `bank.py` 三源格式 | E |
| 20 | `cli/commands/import_.py`（`导入` 命令与导入报告） | E |
| 21 | 测试与样例：`test_convert`、`test_keywords`、`test_init`、`test_report`、`test_chart`、`test_importer`；`schema/测试数据/导入/` | 质量 |
| 22 | 文档：`docs/语法大全.md`、`docs/语法速查.md`、用户手册增补、发布 v0.2.0 | F 文档与发布 |

任务 1–5 MUST 优先于任务 14–20：语言策略先行，避免报表与导入完成后返工。

---

# 17 风险登记册

| 编号 | 风险 | 影响 | 缓解措施 |
|---|---|---|---|
| R1 | 全文件重写 | diff 污染、格式丢失 | 增量写回；`test_writer.py` 断言字节级不变 |
| R2 | `float` 参与金额运算 | 对账误差 | 全链路 `Decimal`；评审禁止金额路径出现 float |
| R3 | 断言依赖文件顺序 | 重排文件即报错 | 断言绑定日期；加载后排序 |
| R4 | 多端并发编辑 | 文件覆盖 | `.lock` 文件锁 + mtime 校验；冲突时提示 |
| R5 | Web 端引入数据库作为第二真相 | 数据不一致 | 缓存仅可只读，且必须可由文本重建 |
| R6 | 过早实现 SQL 查询 | 拖慢 MVP | 先结构化过滤器；SQL 子集列入 M4 |
| R7 | 使用 `len()` / `ljust()` 排版 | 中文表格错位 | 全部经 `width.py`；纳入评审清单 |
| R8 | 未做全角归一化 | 全角标点导致解析失败 | 所有输入入口调用 `normalize_text()` |
| R9 | 依赖解释器默认编码 | Windows 乱码 | 显式 `encoding="utf-8"`；调用 `setup_console()` |
| R10 | 账单 CSV 为 GBK | 导入乱码 | `utf-8-sig → gb18030 → utf-16` 探测 |
| R11 | 账单前置说明行 | 解析错位 | 各来源固定跳行数 + 表头校验 |
| R12 | raw 模式下中文输入 | 无回显、无退格 | 文本字段切换 `cooked_line()` |
| R13 | Windows 无 `_curses` | TUI 不可用 | 自研 ANSI 层；Windows 以 Web 为主 |
| R14 | 中文文件名与长路径 | 路径异常 | 使用 `pathlib`；避免超长路径 |
| R15 | 货币符号混用 | 币种不一致 | 归一化为 `CNY` |
| R16 | 中文排序不符合直觉 | 体验下降 | M4 增加拼音排序；默认按层级 |
| R17 | 导入重复 | 重复交易 | 指纹去重 |
| R18 | TUI 框架化倾向 | 工期失控 | 限制 800 行；禁止实现布局引擎 |

---

# 18 附录

## 18.1 最小可运行账本

```knot
option "operating_currency" "CNY"
option "strict" "warn"

2026-01-01 open 资产:现金     CNY
2026-01-01 open 费用:待分类
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-09-25 "午饭"    费用:餐饮    38.00 CNY  @ 资产:现金
2026-09-25 "地铁"    费用:交通     6.00 CNY  @ 资产:现金
```

## 18.2 科目根速查

```
资产 A    负债 L    权益 E    收入 I    费用 X

资产 = 负债 + 权益
利润 = 收入 - 费用
```

## 18.3 中文数字规则

```
N单位M → N × 单位 + M × (单位 / 10)

2万3    = 20000 + 3 × 1000 = 23000
3千5    = 3000  + 5 × 100  = 3500
1.5万   = 15000
1亿2千万 = 120000000
38块5   = 38.5
```

## 18.4 全角归一化速查

| 输入 | 输出 |
|---|---|
| `：` | `:` |
| `，` | `,` |
| `。` | `.` |
| `１` `２` | `1` `2` |
| `　` | ` ` |
| `￥` | `¥` |
| `（）` | `()` |
| `／` | `/` |

## 18.5 退出码

| 码 | 含义 |
|---|---|
| 0 | 正常 |
| 1 | 账本校验失败 |
| 2 | 参数或用法错误 |
| 130 | 用户中断 |

## 18.6 开工顺序

```
1. schema/GRAMMAR.md
2. core/console.py
3. core/width.py
4. core/normalize.py / number_cn.py / date_cn.py
5. core/aliases.py
6. core/model.py / amount.py
7. core/lexer.py / parser.py
8. cli 的 `记` 命令，使用真实数据验证
```

---

**文档结束**
