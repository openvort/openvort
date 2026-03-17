#!/usr/bin/env python3
"""
测试 OpenVort Web Chat SSE 流式和工具进度显示

用法:
    python test_web_chat_sse.py
"""

import asyncio
import sys
import json
from datetime import datetime
import httpx


BASE_URL = "http://localhost:9090/api"
USERNAME = "杨强"
PASSWORD = "openvort"


async def test_chat_sse():
    """测试聊天 SSE 流式和工具进度"""
    
    print("=" * 80)
    print("OpenVort Web Chat SSE 测试")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 1. 登录
        print("📝 步骤 1: 登录...")
        try:
            login_resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"user_id": USERNAME, "password": PASSWORD}
            )
            login_resp.raise_for_status()
            data = login_resp.json()
            token = data.get("token")
            user = data.get("user")
            print(f"✅ 登录成功: {user.get('name')} (ID: {user.get('member_id')})")
            print()
        except Exception as e:
            print(f"❌ 登录失败: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应内容: {e.response.text}")
            sys.exit(1)
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. 获取会话列表
        print("📝 步骤 2: 获取会话列表...")
        try:
            sessions_resp = await client.get(f"{BASE_URL}/chat/sessions", headers=headers)
            sessions_resp.raise_for_status()
            sessions = sessions_resp.json().get("sessions", [])
            print(f"✅ 当前会话数: {len(sessions)}")
            print()
        except Exception as e:
            print(f"⚠️  获取会话失败: {e}")
            sessions = []
        
        # 3. 创建新会话
        print("📝 步骤 3: 创建新会话...")
        try:
            create_resp = await client.post(
                f"{BASE_URL}/chat/sessions",
                headers=headers,
                json={"title": f"测试会话 {datetime.now().strftime('%H:%M:%S')}"}
            )
            create_resp.raise_for_status()
            session_data = create_resp.json()
            session_id = session_data.get("session_id")
            print(f"✅ 会话创建成功: {session_id}")
            print()
        except Exception as e:
            print(f"❌ 创建会话失败: {e}")
            sys.exit(1)
        
        # 4. 发送消息
        test_message = "帮我在 vortmall-admin 仓库的根目录创建一个 test.md 文件，文件内容为 hello world"
        print(f"📝 步骤 4: 发送消息...")
        print(f"消息内容: {test_message}")
        print()
        
        try:
            send_resp = await client.post(
                f"{BASE_URL}/chat/send",
                headers=headers,
                json={
                    "content": test_message,
                    "images": [],
                    "session_id": session_id
                }
            )
            send_resp.raise_for_status()
            message_id = send_resp.json().get("message_id")
            print(f"✅ 消息发送成功: {message_id}")
            print()
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
            sys.exit(1)
        
        # 5. 接收 SSE 流式响应
        print("📝 步骤 5: 接收 SSE 流式响应...")
        print("=" * 80)
        print()
        
        sse_url = f"{BASE_URL}/chat/stream/{message_id}"
        start_time = datetime.now()
        
        tool_calls = {}
        text_content = ""
        usage_info = None
        
        try:
            async with client.stream("GET", sse_url, headers=headers) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    
                    # 解析 SSE 格式: event: xxx\ndata: yyy
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        event_data = line[6:].strip()
                        elapsed = (datetime.now() - start_time).total_seconds()
                        
                        timestamp = f"[{elapsed:6.1f}s]"
                        
                        if event_type == "thinking":
                            print(f"{timestamp} 🧠 AI 开始思考...")
                        
                        elif event_type == "text":
                            text_content = event_data
                            # 只显示最后 100 字符
                            preview = text_content[-100:] if len(text_content) > 100 else text_content
                            print(f"{timestamp} 💬 文本更新: ...{preview}")
                        
                        elif event_type == "tool_use":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            tool_calls[tool_name] = {
                                "status": "running",
                                "start_time": elapsed,
                                "elapsed": 0
                            }
                            print(f"{timestamp} 🔧 工具调用: {tool_name}")
                        
                        elif event_type == "tool_progress":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            tool_elapsed = data.get("elapsed", 0)
                            if tool_name in tool_calls:
                                tool_calls[tool_name]["elapsed"] = tool_elapsed
                            print(f"{timestamp} ⏱️  工具进度: {tool_name} ({tool_elapsed}s)")
                        
                        elif event_type == "tool_result":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            result = data.get("result", "")
                            if tool_name in tool_calls:
                                tool_calls[tool_name]["status"] = "done"
                            result_preview = result[:100] if len(result) > 100 else result
                            print(f"{timestamp} ✅ 工具完成: {tool_name}")
                            print(f"             结果预览: {result_preview}")
                        
                        elif event_type == "usage":
                            usage_info = json.loads(event_data)
                            print(f"{timestamp} 📊 Token 用量:")
                            print(f"             输入: {usage_info.get('input_tokens', 0)}, "
                                  f"输出: {usage_info.get('output_tokens', 0)}, "
                                  f"缓存命中: {usage_info.get('cache_read_tokens', 0)}")
                        
                        elif event_type == "done":
                            print(f"{timestamp} ✅ 流式响应完成")
                            break
                        
                        elif event_type == "error":
                            print(f"{timestamp} ❌ 错误: {event_data}")
                            break
        
        except httpx.HTTPError as e:
            print(f"\n❌ SSE 连接错误: {e}")
        except Exception as e:
            print(f"\n❌ 处理 SSE 事件时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. 输出测试总结
        print()
        print("=" * 80)
        print("测试总结")
        print("=" * 80)
        print()
        
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"⏱️  总耗时: {total_elapsed:.1f}s")
        print()
        
        if tool_calls:
            print(f"🔧 工具调用记录 ({len(tool_calls)} 个):")
            for tool_name, info in tool_calls.items():
                status = "✅ 完成" if info["status"] == "done" else "⏳ 运行中"
                elapsed = info.get("elapsed", 0)
                print(f"   - {tool_name}: {status} (执行时间: {elapsed}s)")
            print()
        
        if text_content:
            print(f"💬 最终回复 (前 500 字符):")
            print(f"   {text_content[:500]}")
            print()
        
        if usage_info:
            print(f"📊 Token 统计:")
            print(f"   输入: {usage_info.get('total_input_tokens', 0)}")
            print(f"   输出: {usage_info.get('total_output_tokens', 0)}")
            print(f"   缓存创建: {usage_info.get('total_cache_creation_tokens', 0)}")
            print(f"   缓存命中: {usage_info.get('total_cache_read_tokens', 0)}")
            print()
        
        # 7. 验证关键功能
        print("🔍 功能验证:")
        print(f"   ✅ SSE 连接保持: {'是' if total_elapsed > 0 else '否'}")
        print(f"   ✅ 工具调用识别: {'是' if tool_calls else '否'}")
        print(f"   ✅ 工具进度显示: {'是' if any(t.get('elapsed', 0) > 0 for t in tool_calls.values()) else '否'}")
        print(f"   ✅ AI 文本回复: {'是' if text_content else '否'}")
        print(f"   ✅ Token 用量统计: {'是' if usage_info else '否'}")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test_chat_sse())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(0)
