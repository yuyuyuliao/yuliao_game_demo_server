# yuliao_game_demo_server

用于 unity 小游戏 demo 的后端轻量化服务（FastAPI）。

使用codex开发

## 安装依赖

```bash
pip install -r requirements.txt
```

## OpenAI 聊天配置

`app/agent/chat_agent.py` 现在基于 LangChain + LangGraph 编排聊天流程，会优先通过官方 `openai` Python SDK 调用模型生成聊天回复，并可按需调用玩家资料、田地资料与游戏攻略查询工具。运行前可按需配置以下环境变量：

- `OPENAI_API_KEY`：OpenAI API Key，配置后 `/chat/daily` 会优先走真实模型调用。
- `OPENAI_CHAT_MODEL`：聊天模型名，默认 `gpt-4o-mini`。
- `OPENAI_BASE_URL`：可选，自定义 OpenAI 兼容网关地址。

如果未配置 `OPENAI_API_KEY`，服务会继续使用本地兜底回复，方便本地开发和测试。

## 数据库迁移与初始化

项目默认使用 SQLite，数据目录位于 `app/data/`：

- 主数据库：`app/data/game.db`
- Chroma 数据目录：`app/data/chroma`

### 1. 执行表迁移

应用启动时会自动执行 `app/migrations/` 下尚未应用的 SQL 迁移脚本，因此首次启动项目时无需额外手动建表。

```bash
uvicorn app.main:app --reload --port 8080
```

如果只想单独执行迁移、不启动 FastAPI，可以直接调用仓库内的初始化入口：

```bash
python -c "from app.command.database import init_db; init_db()"
```

如需迁移到其他 SQLite 文件，可自行传入路径：

```bash
python -c "from pathlib import Path; from app.command.database import init_db; init_db(Path('app/data/game.db'))"
```

### 2. 初始化默认数据

表迁移只负责创建或升级表结构，不会写入农场默认数据。若需要 6 块默认土地和 3 种默认作物，请单独执行初始化脚本：

```bash
cd /path/to/yuliao_game_demo_server
python scripts/20260307_seed_farm_data.py
python scripts/20260520_seed_player.py
```

脚本支持通过 `--db-path` 指定数据库文件：

```bash
python scripts/20260307_seed_farm_data.py --db-path app/data/game.db
python scripts/20260520_seed_player.py --db-path app/data/game.db
```

该脚本会先确保迁移已执行，再按需写入默认数据；如果表中已有数据，则不会重复插入，可重复执行。

### 3. 推荐首次启动顺序

```bash
pip install -r requirements.txt
python -c "from app.command.database import init_db; init_db()"
python scripts/20260307_seed_farm_data.py
python scripts/20260520_seed_player.py
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

如果只是体验聊天、棋类或扫雷接口，可以跳过“初始化默认数据”这一步；只有农场默认土地/作物演示需要额外执行脚本。

### 4. 重新初始化本地数据

如需重置本地 SQLite 数据，请先备份 `app/data/game.db`，再删除该文件并重新执行“表迁移”和“初始化默认数据”步骤。

## 运行

```bash
uvicorn app.main:app --reload --port 8080
```

## 项目结构

- `app/main.py`：应用入口，只负责组装 FastAPI 和生命周期
- `app/api/`：接口层，定义接口与请求参数；每个具体接口函数只调用对应 command 的 `run`
- `app/command/`：业务命令层，按具体接口拆分 command，并在 `run` 中承接业务逻辑
- `app/model/`：SQLAlchemy 异步 ORM 模型定义，每张表一个 model 文件
- `app/migrations/`：SQLite 数据库迁移脚本，启动时按版本顺序执行
- `scripts/`：按需执行的数据写入脚本，文件名使用“日期+功能”
- `app/prompt/`：统一管理 AI prompt
- `app/agent/`：统一管理当前几个 AI agent
- `app/knowledge_parser.py`：知识库元数据解析

## 接口

- `GET /health`：健康检查
- `POST /chat/record`：记录玩家聊天内容（SQLite）
- `POST /chat/daily`：读取玩家历史聊天，返回有记忆的日常对话，并可按需查询玩家信息、田地信息和知识库攻略
- `GET /player/info/{player_id}`：查询指定玩家的公开资料（ID、昵称、账号、等级、金币）
- `POST /minesweeper/suggest`：根据扫雷棋盘给出下一步建议
- `POST /chess/suggest`：根据国际象棋局面给出下一步建议
- `POST /chess/opponent-move`：根据当前局面，作为对手给出下一步落位
- `GET /farm/crops`：查询全部作物基础信息（不是土地上的种植实例）
- `GET /farm/lands`：查询全部土地（自增ID、价格、等级、描述）
- `POST /farm/plant`：在指定土地种植作物，请求体包含 `player_id`、`index`、`plantId`；种植成功后扣除作物价格并返回当前 `gold`
- `GET /farm/status/{index}`：按土地序号查询当前作物与生长阶段（含水量、肥力、温度）
- `POST /farm/harvest`：采集成熟作物

## 知识库元数据

知识库数据存放在 `app/knowledge_metadata.json`，由 `KnowledgeParser` 工具类解析。

JSON 结构说明：

```json
{
  "version": "1.0",
  "knowledge": [
    {
      "id": "唯一字符串ID",
      "game": "minesweeper|chess",
      "title": "知识标题",
      "tags": ["标签1", "标签2"],
      "content": "实际用于检索和回复的知识文本"
    }
  ]
}
```

其中 `id` 和 `content` 为解析所需字段，其他字段用于元数据扩展和管理。
