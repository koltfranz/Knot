# 贡献指南

感谢关注结绳 Knot。本文档定义开发环境搭建方式、代码规范与**提交格式**。

## 开发环境

```bash
git clone https://github.com/koltfranz/Knot.git
cd Knot
python -m venv .venv
pip install -e .
```

要求 Python ≥ 3.11（推荐 3.13+）。

## 验证命令

```bash
python -m unittest discover tests   # 单元测试
python -m pytest                    # 单元测试（pytest 驱动）
ruff check . && ruff format .       # lint + 格式化
```

新增功能 MUST 先添加测试用例再实现。

## 提交格式（Conventional Commits）

提交信息采用 Conventional Commits，**正文与描述使用中文**：

```
<type>(<scope>): <中文简短描述>

<可选正文：说明动机与变更内容>

<可选尾部：BREAKING CHANGE / 关联 Issue>
```

### type 取值

| type | 含义 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复缺陷 |
| `docs` | 仅文档变更 |
| `style` | 代码格式（不影响逻辑，如 ruff format） |
| `refactor` | 重构（既非新功能也非修复） |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `build` | 构建系统或依赖变更 |
| `ci` | CI 配置变更 |
| `chore` | 杂项（不修改 src 或 tests） |
| `revert` | 回滚提交 |

### scope 取值

| scope | 范围 |
|---|---|
| `core` | 内核（解析、模型、写回、报表） |
| `cli` | 命令行界面 |
| `tui` | 终端界面 |
| `web` | Web 端 |
| `importer` | 账单导入 |
| `schema` | 语法定义与测试数据 |
| `docs` | 文档 |
| `repo` | 仓库配置（.gitignore、CI 等） |

### 示例

```
feat(core): 实现中文数字金额解析
fix(writer): 修复 CRLF 文件写回丢失行尾
docs: 补充账本语法示例
test(parser): 添加全角冒号畸形输入用例
chore(repo): 初始化仓库文档
```

### 规则

- 简短描述 MUST 使用祈使句中文，不加句号
- 一个提交只做一件事；混合变更 MUST 拆分
- 破坏性变更 MUST 在正文标注 `BREAKING CHANGE: <说明>`
- 关联 Issue 使用 `Closes #12` 写在正文或尾部

## 分支规范

| 分支 | 用途 |
|---|---|
| `main` | 稳定分支，直接关联发布 |
| `feat/<简述>` | 功能开发，如 `feat/lexer` |
| `fix/<简述>` | 缺陷修复 |
| `docs/<简述>` | 文档变更 |

## 代码规范

以下为开发文档中的硬性约束，评审 MUST 检查：

1. **零运行时依赖**：`pyproject.toml` 的 `dependencies` MUST 为空列表
2. **金额全程 `Decimal`**：金额路径出现 `float` 一律拒绝
3. **增量写回**：常规写路径 MUST NOT 全文件重新序列化；未编辑行字节级不变
4. **显式编码**：文件读写 MUST 指定 `encoding="utf-8"`，读取用 `utf-8-sig`
5. **显示宽度**：中日韩文本排版 MUST 经 `width.py`，禁止 `len()` / `str.ljust()` 直接对齐
6. **输入归一化**：所有用户输入入口 MUST 调用 `normalize_text()`
7. **格式与 lint**：`ruff`，行宽 100，`RUF001/002/003` 已忽略（中文标点误报）

## 文档同步

修改行为、语法或命令时，MUST 同步更新：

- [结绳Knot开发文档.md](./结绳Knot开发文档.md)（变更记录表追加版本）
- [CHANGELOG.md](./CHANGELOG.md)
