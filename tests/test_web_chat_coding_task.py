#!/usr/bin/env python3
"""
测试 OpenVort Web Chat SSE 流式和工具进度显示 - 使用耗时工具

用法:
    python test_web_chat_coding_task.py
"""

import asyncio
import sys
import json
from datetime import datetime
import httpx


BASE_URL = "http://localhost:9090/api"
USERNAME = "杨强"
PASSWORD = "openvort"


async def test_coding_task_sse():
    """测试 AI 编码任务的 SSE 流式和工具进度"""
    
    print("=" * 80)
    print("OpenVort Web Chat SSE 测试 - AI 编码任务")
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
        
        # 2. 创建新会话
        print("📝 步骤 2: 创建新会话...")
        try:
            create_resp = await client.post(
                f"{BASE_URL}/chat/sessions",
                headers=headers,
                json={"title": f"编码任务测试 {datetime.now().strftime('%H:%M:%S')}"}
            )
            create_resp.raise_for_status()
            session_data = create_resp.json()
            session_id = session_data.get("session_id")
            print(f"✅ 会话创建成功: {session_id}")
            print()
        except Exception as e:
            print(f"❌ 创建会话失败: {e}")
            sys.exit(1)
        
        # 3. 发送 AI 编码任务
        test_message = """请帮我创建一个 AI 编码任务:
在 vortmall-admin 仓库创建一个新分支,在根目录添加 test.md 文件,内容为 "# Test File\\n\\nHello World",然后提交并推送。
使用 git_code_task 工具。"""
        
        print(f"📝 步骤 3: 发送 AI 编码任务...")
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
        
        # 4. 接收 SSE 流式响应
        print("📝 步骤 4: 接收 SSE 流式响应 (可能需要几分钟)...")
        print("=" * 80)
        print()
        
        sse_url = f"{BASE_URL}/chat/stream/{message_id}"
        start_time = datetime.now()
        
        tool_calls = {}
        text_content = ""
        usage_info = None
        last_event_time = start_time
        
        try:
            async with client.stream("GET", sse_url, headers=headers) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    
                    # 解析 SSE 格式
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        event_data = line[6:].strip()
                        current_time = datetime.now()
                        elapsed = (current_time - start_time).total_seconds()
                        time_since_last = (current_time - last_event_time).total_seconds()
                        last_event_time = current_time
                        
                        timestamp = f"[{elapsed:6.1f}s]"
                        
                        if event_type == "thinking":
                            print(f"{timestamp} 🧠 AI 开始思考...")
                        
                        elif event_type == "text":
                            # 只在文本有显著变化时输出
                            new_len = len(event_data)
                            old_len = len(text_content)
                            if new_len > old_len + 50 or time_since_last > 1.0:
                                text_content = event_data
                                preview = text_content[-80:].replace('\n', ' ') if len(text_content) > 80 else text_content.replace('\n', ' ')
                                print(f"{timestamp} 💬 文本: ...{preview}")
                            else:
                                text_content = event_data
                        
                        elif event_type == "tool_use":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            tool_calls[tool_name] = {
                                "status": "running",
                                "start_time": elapsed,
                                "elapsed": 0,
                                "progress_count": 0
                            }
                            print(f"\n{timestamp} 🔧 工具调用开始: {tool_name}")
                            print(f"{'':9} ⏳ 等待进度更新 (每5秒一次)...\n")
                        
                        elif event_type == "tool_progress":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            tool_elapsed = data.get("elapsed", 0)
                            if tool_name in tool_calls:
                                tool_calls[tool_name]["elapsed"] = tool_elapsed
                                tool_calls[tool_name]["progress_count"] += 1
                            # 高亮显示进度更新
                            print(f"{timestamp} ⏱️  【进度更新】{tool_name}: {tool_elapsed}s")
                        
                        elif event_type == "tool_result":
                            data = json.loads(event_data)
                            tool_name = data.get("name")
                            result = data.get("result", "")
                            if tool_name in tool_calls:
                                tool_calls[tool_name]["status"] = "done"
                                total_time = tool_calls[tool_name]["elapsed"]
                                progress_updates = tool_calls[tool_name]["progress_count"]
                                print(f"\n{timestamp} ✅ 工具执行完成: {tool_name}")
                                print(f"{'':9} ⏱️  总耗时: {total_time}s")
                                print(f"{'':9} 📊 进度更新次数: {progress_updates}")
                                print(f"{'':9} 📄 结果预览: {result[:150]}\n")
                        
                        elif event_type == "usage":
                            usage_info = json.loads(event_data)
                            print(f"{timestamp} 📊 Token 用量: "
                                  f"输入={usage_info.get('input_tokens', 0)}, "
                                  f"输出={usage_info.get('output_tokens', 0)}, "
                                  f"缓存={usage_info.get('cache_read_tokens', 0)}")
                        
                        elif event_type == "done":
                            print(f"\n{timestamp} ✅ 流式响应完成\n")
                            break
                        
                        elif event_type == "error":
                            print(f"\n{timestamp} ❌ 错误: {event_data}\n")
                            break
        
        except httpx.HTTPError as e:
            print(f"\n❌ SSE 连接错误: {e}")
        except Exception as e:
            print(f"\n❌ 处理 SSE 事件时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. 输出测试总结
        print("=" * 80)
        print("测试总结")
        print("=" * 80)
        print()
        
        total_elapsed = (datetime.now() - start_time).total_seconds()
        print(f"⏱️  总耗时: {total_elapsed:.1f}s")
        print()
        
        if tool_calls:
            print(f"🔧 工具调用详情 ({len(tool_calls)} 个):")
            for tool_name, info in tool_calls.items():
                status = "✅ 完成" if info["status"] == "done" else "⏳ 运行中"
                elapsed = info.get("elapsed", 0)
                progress_count = info.get("progress_count", 0)
                print(f"   📦 {tool_name}:")
                print(f"      状态: {status}")
                print(f"      执行时间: {elapsed}s")
                print(f"      进度更新次数: {progress_count}")
            print()
        
        if text_content:
            lines = text_content.split('\n')
            preview_lines = lines[:10]
            print(f"💬 最终回复 (前10行):")
            for line in preview_lines:
                print(f"   {line}")
            if len(lines) > 10:
                print(f"   ... (还有 {len(lines) - 10} 行)")
            print()
        
        if usage_info:
            print(f"📊 Token 统计:")
            print(f"   输入: {usage_info.get('total_input_tokens', 0)}")
            print(f"   输出: {usage_info.get('total_output_tokens', 0)}")
            print(f"   缓存命中: {usage_info.get('total_cache_read_tokens', 0)}")
            print()
        
        # 6. 验证关键功能
        has_progress = any(t.get('progress_count', 0) > 0 for t in tool_calls.values())
        has_long_running = any(t.get('elapsed', 0) >= 5 for t in tool_calls.values())
        
        print("🔍 功能验证结果:")
        print(f"   {'✅' if total_elapsed > 0 else '❌'} SSE 连接保持")
        print(f"   {'✅' if tool_calls else '❌'} 工具调用识别")
        print(f"   {'✅' if has_progress else '⚠️'} 工具进度显示 {'(有进度更新)' if has_progress else '(无进度更新-可能工具执行太快)'}")
        print(f"   {'✅' if has_long_running else '⚠️'} 长时间运行工具 (>=5s)")
        print(f"   {'✅' if text_content else '❌'} AI 文本回复")
        print(f"   {'✅' if usage_info else '❌'} Token 用量统计")
        print()
        
        if has_progress:
            print("🎉 测试成功! 工具进度显示功能正常工作!")
        elif has_long_running:
            print("⚠️  工具运行时间 >=5s 但未收到进度更新,可能存在问题!")
        else:
            print("⚠️  工具执行太快 (<5s),未能测试进度显示。请尝试更耗时的任务。")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test_coding_task_sse())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(0)
