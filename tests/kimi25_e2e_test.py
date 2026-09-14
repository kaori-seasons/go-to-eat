"""
Kimi 2.5 端到端测试
使用真实高德API和Kimi 2.5 API进行完整测试
"""

import asyncio
import time
import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

from real_amap_client import RealAmapClient


@dataclass
class KimiToolCall:
    """Kimi工具调用"""
    tool_name: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None


@dataclass
class KimiResponse:
    """Kimi响应"""
    content: str
    tool_calls: List[KimiToolCall]
    response_time_ms: float
    tokens_used: int = 0


class Kimi25Client:
    """Kimi 2.5 API客户端 - 通过 ZenMux 代理"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://zenmux.ai/api/v1/chat/completions"
        self.model = "moonshotai/kimi-k2.5"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用Kimi API

        Args:
            messages: 消息列表
            tools: 工具定义

        Returns:
            API响应
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()


class Kimi25E2ETest:
    """Kimi 2.5 端到端测试"""

    # 高德API工具定义
    AMAP_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "maps_geo",
                "description": "地理编码，将地址转换为坐标。当用户提到地点名称时使用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "地址名称，如'望京'、'国贸'"
                        },
                        "city": {
                            "type": "string",
                            "description": "城市名称，如'北京'、'上海'",
                            "default": "北京"
                        }
                    },
                    "required": ["address"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "maps_direction_driving",
                "description": "驾车路线规划，计算两点间的驾车时间和路线。需要先获取起点和终点的坐标。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "起点坐标，格式：经度,纬度"
                        },
                        "destination": {
                            "type": "string",
                            "description": "终点坐标，格式：经度,纬度"
                        }
                    },
                    "required": ["origin", "destination"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "maps_direction_transit",
                "description": "公交地铁路线规划，计算两点间的公共交通时间和换乘信息。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "起点坐标，格式：经度,纬度"
                        },
                        "destination": {
                            "type": "string",
                            "description": "终点坐标，格式：经度,纬度"
                        },
                        "city": {
                            "type": "string",
                            "description": "城市名称"
                        }
                    },
                    "required": ["origin", "destination", "city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "maps_text_search",
                "description": "关键词搜索，搜索附近的餐厅。可以按菜系、类型等搜索。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "搜索关键词，如'日料'、'火锅'、'烤肉'"
                        },
                        "city": {
                            "type": "string",
                            "description": "城市名称"
                        }
                    },
                    "required": ["keywords", "city"]
                }
            }
        }
    ]

    def __init__(self, kimi_api_key: str, amap_api_key: str):
        self.kimi_client = Kimi25Client(kimi_api_key)
        self.amap_client = RealAmapClient(amap_api_key)
        self.conversation_history: List[Dict[str, str]] = []
        self.tool_call_log: List[Dict[str, Any]] = []

    async def execute_tool_call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            params: 工具参数

        Returns:
            工具执行结果
        """
        print(f"    🔧 执行工具: {tool_name}")
        print(f"       参数: {json.dumps(params, ensure_ascii=False)}")

        start_time = time.time()

        try:
            if tool_name == "maps_geo":
                result = await self.amap_client.geocode(
                    address=params.get("address", ""),
                    city=params.get("city", "北京")
                )
            elif tool_name == "maps_direction_driving":
                result = await self.amap_client.direction_driving(
                    origin=params.get("origin", ""),
                    destination=params.get("destination", "")
                )
            elif tool_name == "maps_direction_transit":
                result = await self.amap_client.direction_transit(
                    origin=params.get("origin", ""),
                    destination=params.get("destination", ""),
                    city=params.get("city", "北京")
                )
            elif tool_name == "maps_text_search":
                result = await self.amap_client.text_search(
                    keywords=params.get("keywords", ""),
                    city=params.get("city", "北京")
                )
            else:
                result = {"status": "0", "info": "Unknown tool"}

            response_time = (time.time() - start_time) * 1000

            # 记录调用
            self.tool_call_log.append({
                "tool_name": tool_name,
                "params": params,
                "response_time_ms": response_time,
                "success": result.get("status") == "1"
            })

            success = result.get("status") == "1"
            print(f"       结果: {'✅ 成功' if success else '❌ 失败'} ({response_time:.0f}ms)")

            return result

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            print(f"       错误: {str(e)}")
            return {"status": "0", "info": str(e)}

    async def run_e2e_test(self, user_message: str, city: str = "北京") -> Dict[str, Any]:
        """
        运行端到端测试

        Args:
            user_message: 用户消息
            city: 城市

        Returns:
            测试结果
        """
        print("\n" + "=" * 70)
        print("  Kimi 2.5 + 高德API 端到端测试")
        print("=" * 70)
        print(f"\n📝 用户请求: {user_message}")
        print(f"📍 城市: {city}")

        start_time = time.time()

        # 初始化对话
        system_prompt = f"""你是一个智能聚餐推荐助手，可以帮助用户找到合适的餐厅。

你的能力：
1. 使用 maps_geo 将地点名称转换为坐标
2. 使用 maps_direction_driving 计算驾车路线和时间
3. 使用 maps_direction_transit 计算公交地铁路线和时间
4. 使用 maps_text_search 搜索餐厅

工作流程：
1. 首先，识别用户提到的所有地点
2. 对每个地点调用 maps_geo 获取坐标
3. 计算所有参与者到候选餐厅的路线时间
4. 搜索符合用户需求的餐厅
5. 根据公平性（最慢时间最短）推荐餐厅

当前城市：{city}

重要提示：
- 当用户提到地点时，必须先调用 maps_geo 获取坐标
- 坐标格式为：经度,纬度
- 路线规划需要使用坐标，不能直接使用地名
- 请按步骤执行，不要跳过任何步骤"""

        self.conversation_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        max_iterations = 15  # 最大迭代次数
        iteration = 0
        all_tool_calls = []

        print("\n🤖 Kimi 2.5 开始处理...")

        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- 迭代 {iteration} ---")

            # 调用Kimi API
            try:
                response = await self.kimi_client.chat(
                    messages=self.conversation_history,
                    tools=self.AMAP_TOOLS
                )
            except Exception as e:
                print(f"  ❌ Kimi API调用失败: {str(e)}")
                break

            # 解析响应
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})

            # 检查是否有工具调用
            if message.get("tool_calls"):
                # 处理工具调用
                tool_calls = message["tool_calls"]
                print(f"  📞 Kimi 请求调用 {len(tool_calls)} 个工具")

                # 将助手消息添加到历史
                self.conversation_history.append(message)

                # 执行所有工具调用
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        params = json.loads(func.get("arguments", "{}"))
                    except:
                        params = {}

                    # 执行工具
                    result = await self.execute_tool_call(tool_name, params)
                    all_tool_calls.append({
                        "tool_name": tool_name,
                        "params": params,
                        "result_summary": {
                            "status": result.get("status"),
                            "has_data": bool(result.get("geocodes") or result.get("route") or result.get("pois"))
                        }
                    })

                    # 将工具结果添加到历史
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(result, ensure_ascii=False)
                    })

            else:
                # 没有工具调用，生成最终响应
                content = message.get("content", "")
                print(f"\n✅ Kimi 生成最终响应:")
                print("-" * 50)
                print(content)
                print("-" * 50)

                execution_time = (time.time() - start_time) * 1000

                return {
                    "success": True,
                    "response": content,
                    "iterations": iteration,
                    "tool_calls": all_tool_calls,
                    "total_tool_calls": len(all_tool_calls),
                    "execution_time_ms": execution_time,
                    "api_stats": self.amap_client.get_call_stats()
                }

        # 达到最大迭代次数
        execution_time = (time.time() - start_time) * 1000
        return {
            "success": False,
            "response": "达到最大迭代次数",
            "iterations": iteration,
            "tool_calls": all_tool_calls,
            "total_tool_calls": len(all_tool_calls),
            "execution_time_ms": execution_time,
            "api_stats": self.amap_client.get_call_stats()
        }


async def main():
    """主函数"""
    # 从环境变量获取API密钥 - 使用ZENMUX_API_KEY
    kimi_api_key = os.getenv("ZENMUX_API_KEY")
    amap_api_key = "2a74be819e0a749654d071c21681477a"

    if not kimi_api_key:
        print("❌ 未找到 ZENMUX_API_KEY 环境变量")
        return

    print(f"✅ Kimi API Key: {kimi_api_key[:20]}...")
    print(f"✅ 高德 API Key: {amap_api_key[:20]}...")
    print(f"✅ API端点: https://zenmux.ai/api/v1/chat/completions")
    print(f"✅ 模型: moonshotai/kimi-k2.5")

    # 创建测试实例
    tester = Kimi25E2ETest(kimi_api_key, amap_api_key)

    # 测试场景
    test_cases = [
        {
            "name": "2人聚餐 - 烤肉",
            "message": "我们两个人分别从望京和霍营出发，想吃烤肉，帮我推荐一家餐厅",
            "city": "北京"
        },
        {
            "name": "3人聚餐 - 日料",
            "message": "我们三个人分别从国贸、中关村和五道口出发，想吃日料，19点到，帮我推荐餐厅",
            "city": "北京"
        },
        {
            "name": "2人聚餐 - 火锅",
            "message": "我和朋友从天通苑和三里屯出发，想吃火锅，帮我找一家公平的餐厅",
            "city": "北京"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"  测试 {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'='*70}")

        result = await tester.run_e2e_test(
            user_message=test_case["message"],
            city=test_case["city"]
        )

        result["test_name"] = test_case["name"]
        results.append(result)

        # 打印结果摘要
        print(f"\n📊 测试结果:")
        print(f"  成功: {'✅' if result['success'] else '❌'}")
        print(f"  迭代次数: {result['iterations']}")
        print(f"  工具调用数: {result['total_tool_calls']}")
        print(f"  执行时间: {result['execution_time_ms']:.0f}ms")
        print(f"  API调用统计: {result['api_stats']}")

        # 重置状态
        tester.conversation_history = []
        tester.tool_call_log = []
        tester.amap_client.reset()

    # 生成最终报告
    print("\n" + "=" * 70)
    print("  测试完成 - 汇总报告")
    print("=" * 70)

    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    total_tool_calls = sum(r["total_tool_calls"] for r in results)
    avg_execution_time = sum(r["execution_time_ms"] for r in results) / total_tests

    print(f"\n📊 总体统计:")
    print(f"  总测试数: {total_tests}")
    print(f"  成功数: {successful_tests}")
    print(f"  成功率: {successful_tests/total_tests*100:.1f}%")
    print(f"  总工具调用: {total_tool_calls}")
    print(f"  平均执行时间: {avg_execution_time:.0f}ms")

    # 保存报告
    report = {
        "test_date": datetime.now().isoformat(),
        "model": "Kimi 2.5 (moonshotai/kimi-k2.5 via ZenMux)",
        "api_endpoint": "https://zenmux.ai/api/v1/chat/completions",
        "amap_api_key": amap_api_key[:20] + "...",
        "summary": {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests/total_tests,
            "total_tool_calls": total_tool_calls,
            "avg_execution_time_ms": avg_execution_time
        },
        "test_results": results
    }

    report_path = "/Users/kaori/Downloads/where-to-eat-main/tests/results/kimi25_e2e_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📁 报告已保存至: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
