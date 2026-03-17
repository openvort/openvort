#!/usr/bin/env python3
"""
简单测试 - 直接要求使用 git_code_task

用法:
    python test_simple_coding.py
"""

import asyncio
import sys
import json
from datetime import datetime
import httpx


BASE_URL = "http://localhost:9090/api"
USERNAME = "杨强"
PASSWORD = "openvort"


async def test():
    print("=" * 80)
    print("OpenVort git_code_task 工具进度测试")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 登录
        print("🔐 登录...")
        login_resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"user_id": USERNAME, "password": PASSWORD}
        )
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ 登录成功\n")
        
        # 创建会话
        print("📝 创建会话...")
        create_resp = await client.post(
            f"{BASE_URL}/chat/sessions",
            headers=headers,
            json={"title": f"编码测试 {datetime.now().strftime('%H:%M:%S')}"}
        )
        session_id = create_resp.json().get("session_id")
        print(f"✅ 会话ID: {session_id}\n")
        
        # 发送消息 - 明确要求使用 git_code_task
        message = """使用 git_code_task 工具帮我在 vortmall-admin 仓库创建一个 test.md 文件。

任务要求:
- 仓库: vortmall-admin  
- 创建文件: test.md (根目录)
- 文件内容: "# Test\\n\\nHello World"
- 自动提交和推送

请直接调用 git_code_task 工具。"""
        
        print("📤 发送消息...")
        print(f"内容: {message[:100]}...")
        send_resp = await client.post(
            f"{BASE_URL}/chat/send",
            headers=headers,
            json={"content": message, "images": [], "session_id": session_id}
        )
        message_id = send_resp.json().get("message_id")
        print(f"✅ 消息ID: {message_id}\n")
        
        # SSE 流式响应
        print("📡 接收 SSE 流式响应...")
        print("=" * 80)
        print()
        
        sse_url = f"{BASE_URL}/chat/stream/{message_id}"
        start_time = datetime.now()
        tool_progress_events = []
        
        try:
            async with client.stream("GET", sse_url, headers=headers) as response:
                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        event_data = line[6:].strip()
                        elapsed = (datetime.now() - start_time).total_seconds()
                        ts = f"[{elapsed:5.1f}s]"
                        
                        if event_type == "tool_use":
                            data = json.loads(event_data)
                            print(f"{ts} 🔧 工具调用: {data.get('name')}")
                        
                        elif event_type == "tool_progress":
                            data = json.loads(event_data)
                            tool_progress_events.append(data)
                            print(f"{ts} ⏱️  【进度】{data.get('name')}: {data.get('elapsed')}s")
                        
                        elif event_type == "tool_result":
                            data = json.loads(event_data)
                            print(f"{ts} ✅ 工具完成: {data.get('name')}")
                        
                        elif event_type == "text":
                            if len(event_data) < 50:
                                print(f"{ts} 💬 {event_data}")
                        
                        elif event_type == "done":
                            print(f"\n{ts} ✅ 完成\n")
                            break
                        
                        elif event_type == "error":
                            print(f"\n{ts} ❌ 错误: {event_data}\n")
                            break
        
        except Exception as e:
            print(f"\n❌ 错误: {e}\n")
        
        # 总结
        print("=" * 80)
        print(f"⏱️  总耗时: {(datetime.now() - start_time).total_seconds():.1f}s")
        print(f"📊 进度事件数: {len(tool_progress_events)}")
        
        if tool_progress_events:
            print("\n✅ 成功! 工具进度显示功能正常工作!")
            print(f"   收到 {len(tool_progress_events)} 个进度更新:")
            for evt in tool_progress_events:
                print(f"   - {evt.get('name')}: {evt.get('elapsed')}s")
        else:
            print("\n⚠️  未收到进度更新 (工具可能执行太快 <5s)")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\n⚠️  中断")
        sys.exit(0)
