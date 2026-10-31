#!/usr/bin/env python3
import asyncio
import websockets
import json
import sys
import os
from vosk import Model, KaldiRecognizer

# 配置日志功能但不强制使用logging模块
try:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    USE_LOGGER = True
except:
    USE_LOGGER = False
    print("⚠️  logging模块不可用，使用简单输出")

def log_info(message):
    """统一的日志输出"""
    if USE_LOGGER:
        logger.info(message)
    else:
        print(f"INFO: {message}")

def log_error(message):
    """统一的错误输出"""
    if USE_LOGGER:
        logger.error(message)
    else:
        print(f"ERROR: {message}")

def log_debug(message):
    """统一的调试输出"""
    if USE_LOGGER:
        logger.debug(message)
    else:
        print(f"DEBUG: {message}")

# 加载大模型
model_path = "models/vosk-model-cn-0.22"

if not os.path.exists(model_path):
    error_msg = f"❌ 未找到模型: {model_path}"
    log_error(error_msg)
    print(f"\n{error_msg}")
    print(f"📥 请下载大型中文模型并放到 {model_path}")
    print("💡 下载地址: https://alphacephei.com/vosk/models (vosk-model-cn-0.22)")
    print("📝 解压后放在 models/ 目录下，详见 README")
    sys.exit(1)

try:
    # 检查模型大小
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(model_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    size_mb = total_size / (1024 * 1024)
    info_msg = f"📦 加载Vosk大模型: {model_path} ({size_mb:.1f} MB)"
    log_info(info_msg)
    print(info_msg)
except Exception as e:
    info_msg = f"📦 加载Vosk大模型: {model_path}"
    log_info(info_msg)
    print(info_msg)
    print(f"⚠️  无法计算模型大小: {e}")

print("⏳ 正在初始化模型，请稍候...")
model = Model(model_path)
print("✅ 模型加载完成")

# 识别器管理
recognizer_cache = {}
rec_counter = 0

def create_recognizer():
    """创建并配置识别器"""
    global rec_counter
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(True)
    # 尝试启用部分词识别，如果支持的话
    try:
        rec.SetPartialWords(True)
        log_debug("启用了部分词识别")
    except:
        log_debug("部分词识别不可用")
    
    rec_id = rec_counter
    rec_counter += 1
    recognizer_cache[rec_id] = rec
    return rec_id, rec

async def handle_audio(websocket):
    """处理音频连接 - 完全遵循原版接口"""
    log_info("客户端连接成功")
    
    # 为每个连接创建新的识别器（简化版，也可以复用）
    rec_id, rec = create_recognizer()
    log_debug(f"创建识别器 #{rec_id}")
    
    try:
        async for message in websocket:
            if isinstance(message, bytes):
                log_debug(f"收到音频数据: {len(message)} bytes")
                
                if rec.AcceptWaveform(message):
                    result = json.loads(rec.Result())
                    text = result.get("text", "")
                    if text:
                        log_info(f"识别结果: {text[:60]}...")
                        await websocket.send(json.dumps({
                            "type": "result",
                            "text": text,
                            "partial": False
                        }))
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text:
                        log_debug(f"部分结果: {partial_text}")
                        await websocket.send(json.dumps({
                            "type": "partial",
                            "text": partial_text
                        }))
                        
            elif isinstance(message, str):
                try:
                    data = json.loads(message)
                    log_debug(f"收到文本消息: {data}")
                    if data.get("type") == "init":
                        await websocket.send(json.dumps({
                            "status": "ready", 
                            "message": "服务器已准备好",
                            "model": "vosk-model-cn-0.22",
                            "sample_rate": 16000
                        }))
                except json.JSONDecodeError:
                    log_debug(f"无法解析的文本消息: {message}")
                    
    except websockets.exceptions.ConnectionClosed:
        log_info("客户端断开连接")
    except Exception as e:
        log_error(f"处理音频时出错: {e}")
    finally:
        # 清理识别器
        if rec_id in recognizer_cache:
            del recognizer_cache[rec_id]
            log_debug(f"清理识别器 #{rec_id}")

async def main():
    """主函数"""
    print("\n" + "="*60)
    print("🎤 Vosk语音识别服务器 (优化版)")
    print("="*60)
    print(f"📡 WebSocket地址: ws://localhost:2700")
    print(f"📁 模型: vosk-model-cn-0.22 (2.0G)")
    print(f"🎯 识别器缓存: 连接时动态创建")
    print("="*60)
    print("💡 按 Ctrl+C 停止服务器")
    
    # 使用与原版完全相同的调用方式
    async with websockets.serve(handle_audio, "localhost", 2700):
        print("✅ 服务器启动成功！")
        print("🌐 请在浏览器中打开 voice_chat.html 文件")
        await asyncio.Future()  # 永远运行

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 服务器已停止")
    except Exception as e:
        print(f"❌ 服务器启动失败: {e}")