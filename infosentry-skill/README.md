# infosentry-skill

让 AI Agent（Claude Code 等）通过 Skill 接入 infoSentry 平台，管理 Goals、Sources、Notifications。

纯 Python 标准库实现，**零依赖**。

## 安装

### 方式一：Claude Code Skill（推荐）

将本目录添加为 Claude Code 的自定义 Skill：

```bash
# 1. 克隆仓库（或仅复制 infosentry-skill 目录）
git clone https://github.com/your-org/infoSentry.git
cd infoSentry/infosentry-skill

# 2. 运行配置向导
python3 scripts/setup.py
```

配置向导会引导你填写：
- **Base URL** — infoSentry API 地址（如 `https://your-domain.com/api/v1`）
- **API Key** — 以 `isk_` 开头的密钥

配置保存在 `~/.infosentry/config.json`，权限自动设为 600。

然后在 Claude Code 中引用 `SKILL.md` 即可使用。

### 方式二：独立使用 CLI

不依赖 Claude Code，直接使用命令行工具：

```bash
# 1. 下载 scripts 目录
curl -LO https://raw.githubusercontent.com/your-org/infoSentry/main/infosentry-skill/scripts/setup.py
curl -LO https://raw.githubusercontent.com/your-org/infoSentry/main/infosentry-skill/scripts/infosentry.py

# 2. 配置
python3 setup.py

# 3. 使用
python3 infosentry.py goals list
```

仅需 Python 3.10+，无需 pip install。

## 获取 API Key

1. 登录 infoSentry Web 界面
2. 进入 **设置 > 开发者中心**
3. 点击 **创建 Key**
4. 选择所需权限范围（如 `goals:read`、`sources:read`）
5. 复制生成的密钥（`isk_` 开头，仅显示一次）

## 使用示例

```bash
# Goals
python3 scripts/infosentry.py goals list
python3 scripts/infosentry.py goals list --status active
python3 scripts/infosentry.py goals get <goal_id>

# Sources
python3 scripts/infosentry.py sources list

# Notifications
python3 scripts/infosentry.py notifications list
python3 scripts/infosentry.py notifications list --goal_id <id>

# 任意 API 调用
python3 scripts/infosentry.py raw GET /goals
python3 scripts/infosentry.py raw POST /goals '{"name": "test", "description": "..."}'
```

## 目录结构

```
infosentry-skill/
├── SKILL.md              # Claude Code Skill 定义（Agent 读取此文件）
├── README.md             # 本文件
├── scripts/
│   ├── setup.py          # 配置向导
│   └── infosentry.py     # CLI 工具
├── references/
│   └── api-reference.md  # 完整 API 文档
└── tests/
    └── test_e2e_skill.py # E2E 测试
```

## 权限范围

| Scope | 说明 |
|-------|------|
| `goals:read` | 读取 Goals 及匹配结果 |
| `goals:write` | 创建、更新、删除 Goals；AI 建议；触发邮件 |
| `sources:read` | 读取信息源 |
| `sources:write` | 创建、订阅/退订、启用/禁用信息源 |
| `notifications:read` | 读取通知 |
| `notifications:write` | 标记已读、提交反馈 |

完整 API 文档见 [references/api-reference.md](references/api-reference.md)。

## 运行测试

需要运行中的 infoSentry 实例：

```bash
cd infosentry-skill
python -m pytest tests/test_e2e_skill.py -v
```

环境变量：
- `API_BASE_URL` — API 地址（默认 `http://localhost:18000/api/v1`）
- `SECRET_KEY` — JWT 签名密钥（默认从 `../.env` 读取）
