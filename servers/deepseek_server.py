#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
import time
import threading

# 从 .env 文件加载环境变量（可选依赖，缺失时仍可从系统环境变量读取）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# DeepSeek API配置：密钥通过环境变量注入，不要把密钥写进代码
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# 聊天历史存储
chat_histories = {}

def get_chat_history(session_id):
    """获取或创建聊天历史"""
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    return chat_histories[session_id]

def clear_chat_history(session_id):
    """清空聊天历史"""
    if session_id in chat_histories:
        chat_histories[session_id] = []

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "ok",
        "service": "DeepSeek API Proxy",
        "timestamp": time.time()
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        data = request.json
        
        # 验证输入
        if not data or 'message' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少message参数"
            }), 400
        
        message = data['message'].strip()
        session_id = data.get('session_id', 'default')
        stream = data.get('stream', False)
        
        if not message:
            return jsonify({
                "status": "error",
                "message": "消息内容不能为空"
            }), 400
        
        print(f"📨 收到消息 (会话: {session_id}): {message[:50]}...")
        
        # 获取聊天历史
        history = get_chat_history(session_id)
        
        # 构建消息列表
        messages = []
        
        # 添加上下文（保留最近的10轮对话）
        if 'context' in data and data['context']:
            messages.append({"role": "system", "content": data['context']})
        
        # 添加历史消息
        for h in history[-10:]:  # 最多保留10轮历史
            messages.append(h)
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": message})
        
        # 准备API请求
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.7,
            "stream": stream
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        # 调用DeepSeek API
        start_time = time.time()
        response = requests.post(
            DEEPSEEK_API_URL, 
            headers=headers, 
            json=payload,
            timeout=60
        )
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            
            # 提取回复
            if 'choices' in result and len(result['choices']) > 0:
                reply = result['choices'][0]['message']['content']
                
                # 更新聊天历史
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": reply})
                
                # 限制历史长度
                if len(history) > 20:  # 最多20条消息
                    history = history[-20:]
                chat_histories[session_id] = history
                
                print(f"✅ 回复生成成功 (耗时: {end_time - start_time:.2f}秒)")
                
                return jsonify({
                    "status": "success",
                    "reply": reply,
                    "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                    "response_time": end_time - start_time,
                    "session_id": session_id
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "API返回格式异常"
                }), 500
                
        else:
            error_msg = f"API调用失败: {response.status_code}"
            print(f"❌ {error_msg}")
            return jsonify({
                "status": "error",
                "message": error_msg,
                "details": response.text[:200] if response.text else "无错误详情"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "message": "请求超时，请稍后重试"
        }), 504
    except Exception as e:
        print(f"❌ 服务器错误: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"服务器内部错误: {str(e)}"
        }), 500

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """清空聊天历史"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        
        clear_chat_history(session_id)
        
        return jsonify({
            "status": "success",
            "message": f"已清空会话 {session_id} 的历史"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取聊天历史"""
    session_id = request.args.get('session_id', 'default')
    history = get_chat_history(session_id)
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "history": history,
        "count": len(history)
    })

def cleanup_old_sessions():
    """定期清理旧的会话历史"""
    while True:
        time.sleep(3600)  # 每小时清理一次
        try:
            current_time = time.time()
            # 这里可以添加会话清理逻辑
            print("🔄 会话清理任务运行中...")
        except Exception as e:
            print(f"清理任务错误: {e}")

if __name__ == "__main__":
    # 启动会话清理线程
    # cleanup_thread = threading.Thread(target=cleanup_old_sessions, daemon=True)
    # cleanup_thread.start()
    
    print("🚀 DeepSeek API 服务器启动中...")
    print("=" * 50)
    print("📡 API端点:")
    print("  GET  /api/health        - 健康检查")
    print("  POST /api/chat          - 发送消息")
    print("  POST /api/clear_history - 清空历史")
    print("  GET  /api/history       - 获取历史")
    print("=" * 50)
    print(f"🌐 服务器地址: http://localhost:5001")

    # 检查API密钥
    if not DEEPSEEK_API_KEY:
        print("\n❌ 错误: 未检测到 DEEPSEEK_API_KEY")
        print("1. 访问 https://platform.deepseek.com/ 注册并创建 API Key")
        print("2. 把 .env.example 复制为 .env，填入 DEEPSEEK_API_KEY=<你的密钥>")
        print("3. 或直接设置系统环境变量 DEEPSEEK_API_KEY")
    else:
        print("✅ 已读取 DEEPSEEK_API_KEY（来自环境变量 / .env）")
        app.run(host='localhost', port=5001, debug=True)