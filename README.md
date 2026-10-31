# 智能语音助手 · 实时语音转写 + AI 对话

一个本地运行的实时语音助手 Demo：**浏览器采集麦克风音频 → Vosk 离线中文语音识别 → 识别文本送入 DeepSeek 大模型生成回复**。

全程在本地推理语音，只有最终的文本会发到大模型接口。

## 功能特性

- **实时流式识别**：边说边出字，`partial` 结果实时刷新，识别完成后给出 `result` 整句
- **离线语音识别**：基于 Vosk + Kaldi 中文模型本地推理，音频不上传第三方
- **语音驱动的多轮对话**：识别结果可一键发送给 DeepSeek，服务端维护会话历史（保留最近 10 轮）
- **前后端分离**：WebSocket 承载音频流，HTTP/JSON 承载会话逻辑，两个服务可独立部署
- **状态可视化**：页面顶部实时显示 Vosk / DeepSeek 服务连接状态

## 系统架构

```
浏览器 web/vosk-chat.html
  │
  ├─ 音频通道 ── Web Audio API（16 kHz / 单声道）→ Int16 PCM → WebSocket 二进制帧
  │        └──► servers/vosk-server.py  ws://localhost:2700
  │                 └── KaldiRecognizer → 返回 {"type":"partial"|"result","text":...}
  │
  └─ 对话通道 ── fetch POST http://localhost:5001/api/chat
           └──► servers/deepseek_server.py（Flask）
                    └──► DeepSeek Chat API → 回复文本 / token 用量 / 耗时
```

## 目录结构

```
voice-assistant/
├── web/
│   └── vosk-chat.html        # 单页前端：录音、实时字幕、对话界面
├── servers/
│   ├── vosk-server.py        # WebSocket 语音识别服务（默认 2700）
│   └── deepseek_server.py    # Flask 代理服务，对接 DeepSeek API（默认 5001）
├── models/                   # 语音模型目录（体积大，未纳入版本库，需自行下载）
├── requirements.txt          # 直接依赖
├── requirements-freeze.txt   # 完整环境快照（pip freeze）
└── .env.example              # 密钥配置模板
```

## 快速开始

### 1. 准备环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 下载中文语音模型

到 [Vosk 模型仓库](https://alphacephei.com/vosk/models) 下载后解压到 `models/` 目录：

| 模型 | 解压后体积 | 适用场景 |
| --- | --- | --- |
| `vosk-model-cn-0.22` | 约 2.0 GB | 识别准确率更高，本仓库默认使用 |
| `vosk-model-small-cn-0.22` | 约 60 MB | 体积小、加载快，适合快速试用 |

最终目录形如 `models/vosk-model-cn-0.22/am/final.mdl`。若使用小模型，把 `servers/vosk-server.py` 里的 `model_path` 指向小模型目录即可。

### 3. 配置 API 密钥

```bash
cp .env.example .env
```

在 `.env` 中填入自己的密钥：

```
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

密钥也可以直接用系统环境变量 `DEEPSEEK_API_KEY` 提供。**`.env` 已被 `.gitignore` 忽略，不会被提交。**

### 4. 启动服务（两个终端）

```bash
# 终端 1：语音识别服务
python servers/vosk-server.py

# 终端 2：大模型代理服务
python servers/deepseek_server.py
```

首次启动 `vosk-server.py` 需要加载约 2 GB 的模型，内存占用较高、等待时间较长，属于正常现象。

### 5. 打开页面

用浏览器打开 `web/vosk-chat.html`，允许麦克风权限后点击「开始录音」即可。

> `getUserMedia` 只在 `localhost` 或 HTTPS 下可用，因此请在本机通过 `localhost` 访问；
> 若改用其它主机访问，需要额外配置 HTTPS。

## 接口说明

`servers/deepseek_server.py`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/chat` | 发送消息，`{message, session_id, context, stream}` |
| POST | `/api/clear_history` | 清空指定会话历史 |
| GET | `/api/history?session_id=` | 查询会话历史 |

`servers/vosk-server.py`（WebSocket）

- 客户端 → 服务端：16 kHz 单声道 16-bit PCM 二进制帧；`{"type":"init"}` 文本帧用于握手
- 服务端 → 客户端：`{"type":"partial","text":...}` 中间结果、`{"type":"result","text":...,"partial":false}` 整句结果

## 已知限制 / 后续可改进

- 前端使用 `ScriptProcessorNode`（已废弃但兼容性好），可迁移到 `AudioWorklet` 以降低主线程开销
- 会话历史存在进程内存中，重启即丢失，可替换为 Redis
- 目前仅支持单机单路录音，未做多用户并发压测
- 服务端为开发模式启动（`debug=True`），正式部署需改为 WSGI 生产模式并做鉴权

## 安全说明

仓库不包含任何密钥。如果你 fork 本项目，请不要把 `.env`、`key.txt` 之类文件提交到公开仓库；一旦密钥意外泄露，请立即到平台上吊销并重新生成。
