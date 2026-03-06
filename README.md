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
