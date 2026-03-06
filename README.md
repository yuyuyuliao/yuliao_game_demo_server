# yuliao_game_demo_server

用于 unity 小游戏 demo 的后端轻量化服务（FastAPI）。

## 运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 接口

- `GET /health`：健康检查
- `POST /chat/record`：记录玩家聊天内容（SQLite）
- `POST /chat/daily`：读取玩家历史聊天，返回有记忆的日常对话
- `POST /minesweeper/suggest`：根据扫雷棋盘给出下一步建议
- `POST /chess/suggest`：根据国际象棋局面给出下一步建议
- `POST /chess/opponent-move`：根据当前局面，作为对手给出下一步落位
- `GET /farm/lands`：查询全部土地（自增ID、价格、等级、描述）
- `POST /farm/plant`：在指定土地种植作物
- `GET /farm/status/{land_id}`：查询土地当前作物与生长阶段（含水量、肥力、温度）
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
