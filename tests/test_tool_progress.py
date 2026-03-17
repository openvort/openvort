#!/usr/bin/env python3
"""
最小化测试 - 测试工具进度显示功能

通过直接构造一个慢速工具调用来触发 tool_progress 事件
"""

import asyncio
import sys
import json
from datetime import datetime
import httpx


BASE_URL = "http://localhost:9090/api"
USERNAME = "杨强"
PASSWORD = "openvort"

# 测试一个需要较长时间的命令
TEST_MESSAGE = "帮我查询 vortmall-admin 仓库最近 50 条提交记录,并分析每条提交的内容"


async def test():
    print("=" * 80)
    print("工具进度显示测试")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        # 登录
        print("🔐 登录中...")
        try:
            login_resp = await client.post(
                f"{BASE_URL}/auth/login",
                json={"user_id": USERNAME, "password": PASSWORD}
            )
            login_resp.raise_for_status()
            token = login_resp.json().get("token")
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ 登录成功\n")
        except Exception as e:
            print(f"❌ 登录失败: {e}")
            return
        
        # 创建会话
        print("📝 创建会话...")
        try:
            create_resp = await client.post(
                f"{BASE_URL}/chat/sessions",
                headers=headers,
                json={"title": f"进度测试 {datetime.now().strftime('%H:%M:%S')}"}
            )
            create_resp.raise_for_status()
            session_id = create_resp.json().get("session_id")
            print(f"✅ 会话创建成功\n")
        except Exception as e:
            print(f"❌ 创建会话失败: {e}")
            return
        
        # 发送消息
        print(f"📤 发送消息: {TEST_MESSAGE}\n")
        try:
            send_resp = await client.post(
                f"{BASE_URL}/chat/send",
                headers=headers,
                json={"content": TEST_MESSAGE, "images": [], "session_id": session_id}
            )
            send_resp.raise_for_status()
            message_id = send_resp.json().get("message_id")
        except Exception as e:
            print(f"❌ 发送失败: {e}")
            return
        
        # SSE 接收
        print("📡 接收 SSE 流式响应...")
        print("=" * 80)
        print()
        
        sse_url = f"{BASE_URL}/chat/stream/{message_id}"
        start_time = datetime.now()
        
        tool_events = {"use": [], "progress": [], "result": []}
        
        try:
            event_type = None
            async with client.stream("GET", sse_url, headers=headers, timeout=600.0) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    if line.startswith(":"):  # SSE 注释
                        continue
                    
                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        event_data = line[6:].strip()
                        elapsed = (datetime.now() - start_time).total_seconds()
                        ts = f"[{elapsed:6.1f}s]"
                        
                        if event_type == "thinking":
                            print(f"{ts} 🧠 AI 思考中...")
                        
                        elif event_type == "tool_use":
                            try:
                                data = json.loads(event_data)
                                tool_name = data.get("name", "unknown")
                                tool_events["use"].append((elapsed, tool_name))
                                print(f"{ts} 🔧 工具调用: {tool_name}")
                            except:
                                pass
                        
                        elif event_type == "tool_progress":
                            try:
                                data = json.loads(event_data)
                                tool_name = data.get("name", "unknown")
                                tool_elapsed = data.get("elapsed", 0)
                                tool_events["progress"].append((elapsed, tool_name, tool_elapsed))
                                print(f"{ts} ⏱️  【进度更新】{tool_name}: 已执行 {tool_elapsed}s")
                            except Exception as e:
                                print(f"{ts} ⚠️  解析进度事件失败: {e}")
                        
                        elif event_type == "tool_result":
                            try:
                                data = json.loads(event_data)
                                tool_name = data.get("name", "unknown")
                                result_preview = data.get("result", "")[:80]
                                tool_events["result"].append((elapsed, tool_name))
                                print(f"{ts} ✅ 工具完成: {tool_name}")
                                if result_preview:
                                    print(f"{'':9} 结果: {result_preview}...")
                            except:
                                pass
                        
                        elif event_type == "text":
                            # 只显示较短的文本片段
                            if len(event_data) < 100 and elapsed - start_time.timestamp() < 2:
                                print(f"{ts} 💬 {event_data[:80]}")
                        
                        elif event_type == "done":
                            print(f"\n{ts} ✅ 流式响应结束\n")
                            break
                        
                        elif event_type == "error":
                            print(f"\n{ts} ❌ 错误: {event_data}\n")
                            break
        
        except httpx.ReadTimeout:
            print("\n⚠️  超时,可能工具执行时间过长\n")
        except Exception as e:
            print(f"\n❌ SSE 错误: {e}\n")
            import traceback
            traceback.print_exc()
        
        # 总结
        total_time = (datetime.now() - start_time).total_seconds()
        
        print("=" * 80)
        print("测试结果")
        print("=" * 80)
        print()
        print(f"⏱️  总耗时: {total_time:.1f}s")
        print()
        print(f"📊 事件统计:")
        print(f"   工具调用 (tool_use): {len(tool_events['use'])}")
        print(f"   进度更新 (tool_progress): {len(tool_events['progress'])}")
        print(f"   工具结果 (tool_result): {len(tool_events['result'])}")
        print()
        
        if tool_events['use']:
            print("🔧 工具调用列表:")
            for t, name in tool_events['use']:
                print(f"   [{t:6.1f}s] {name}")
            print()
        
        if tool_events['progress']:
            print("⏱️  进度更新详情:")
            for t, name, tool_t in tool_events['progress']:
                print(f"   [{t:6.1f}s] {name}: 已运行 {tool_t}s")
            print()
        
        # 判断测试是否成功
        print("🔍 功能验证:")
        has_tools = len(tool_events['use']) > 0
        has_progress = len(tool_events['progress']) > 0
        has_long_tool = any(tool_t >= 5 for _, _, tool_t in tool_events['progress'])
        
        print(f"   {'✅' if has_tools else '❌'} 工具调用检测")
        progress_count = len(tool_events['progress'])
        progress_text = f"({progress_count} 次)" if has_progress else "(0 次)"
        print(f"   {'✅' if has_progress else '⚠️'} 工具进度更新 {progress_text}")
        print(f"   {'✅' if has_long_tool else '⚠️'} 长时间运行检测 (>=5s)")
        print()
        
        if has_progress:
            print("🎉 测试成功! 工具进度显示功能正常工作!")
        elif has_tools and not has_progress:
            print("⚠️  工具被调用但未收到进度更新 (可能工具执行太快 <5s)")
        else:
            print("❌ 未检测到工具调用")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        sys.exit(0)
