"""
MiniCPM5-2B 端到端测试
使用真实高德API和MiniCPM API进行完整测试
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
class MiniCPMResponse:
    """MiniCPM响应"""
    content: str
    tool_calls: List[Dict[str, Any]]
    response_time_ms: float
    tokens_used: int = 0


class MiniCPMClient:
    """MiniCPM API客户端"""

    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key
        self.api_url = "https://api.modelbest.cn/v1/chat/completions"
        self.model = model or os.getenv("MINICPM_MODEL", "MiniCPM5-2B-0822")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        调用MiniCPM API

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


def _parse_tool_calls_from_text(content: str) -> List[Dict[str, Any]]:
    """从模型输出文本中解析 <tool_call> JSON 块。

    MiniCPM-V-4.5 将工具调用以文本标签形式输出：
     <tool_call>
    {"name": "maps_geo", "arguments": {"address": "望京", "city": "北京"}}
    </tool_call>
    需要解析为标准 tool_calls 格式。
    """
    import re
    tool_calls = []
    # 先提取每个 <tool_call>...</tool_call> 块，再解析其中的 JSON
    block_pattern = r'<tool_call>\s*(.*?)\s*(?:</tool_call>|<｜tool▁call▁end｜>)'
    for block_match in re.finditer(block_pattern, content, re.DOTALL):
        block = block_match.group(1).strip()
        try:
            tc = json.loads(block)
            tool_calls.append(tc)
        except json.JSONDecodeError:
            # 尝试提取块中的第一个 JSON 对象
            json_match = re.search(r'\{.*\}', block, re.DOTALL)
            if json_match:
                try:
                    tc = json.loads(json_match.group(0))
                    tool_calls.append(tc)
                except json.JSONDecodeError:
                    continue
    return tool_calls


def _compact_tool_result(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """压缩工具结果，只保留模型需要的关键字段，避免超出上下文窗口。"""
    if tool_name == "maps_geo":
        geocodes = result.get("geocodes") or []
        if geocodes:
            g = geocodes[0]
            return {"location": g.get("location", ""), "address": g.get("formatted_address", "")}
        return {"location": "", "address": ""}
    elif tool_name == "maps_direction_driving":
        try:
            duration = result["route"]["paths"][0]["duration"]
            return {"duration_seconds": float(duration), "duration_text": f"{float(duration)/60:.0f}分钟"}
        except (KeyError, IndexError, TypeError):
            return {"error": "路线规划失败"}
    elif tool_name == "maps_direction_transit":
        try:
            transits = result["route"]["transits"]
            durations = [float(t["duration"]) for t in transits if t.get("duration")]
            best = min(durations) if durations else None
            return {"best_duration_seconds": best, "best_duration_text": f"{best/60:.0f}分钟" if best else "无可用路线", "options": len(transits)}
        except (KeyError, TypeError):
            return {"error": "路线规划失败"}
    elif tool_name == "maps_text_search":
        pois = result.get("pois") or []
        compact_pois = []
        for poi in pois[:6]:
            compact_pois.append({
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "location": poi.get("location", ""),
                "rating": poi.get("rating", ""),
                "cost": poi.get("cost", "")
            })
        return {"pois": compact_pois, "total": len(pois)}
    return result


class MiniCPME2ETest:
    """MiniCPM5-2B 端到端测试"""

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

    def __init__(self, minicpm_api_key: str, amap_api_key: str, model: str = ""):
        self.minicpm_client = MiniCPMClient(minicpm_api_key, model=model)
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
        print("  MiniCPM5-2B + 高德API 端到端测试")
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

        print("\n🤖 MiniCPM5-2B 开始处理...")

        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- 迭代 {iteration} ---")

            # 调用MiniCPM API
            try:
                response = await self.minicpm_client.chat(
                    messages=self.conversation_history,
                    tools=self.AMAP_TOOLS
                )
            except httpx.HTTPStatusError as e:
                print(f"  ❌ MiniCPM API调用失败: {e.response.status_code} {e.response.text[:300]}")
                break
            except Exception as e:
                print(f"  ❌ MiniCPM API调用失败: {str(e)}")
                break

            # 解析响应
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})

            # 检查是否有工具调用（标准格式 + 文本标签格式）
            tool_calls_raw = message.get("tool_calls") or []
            content = message.get("content", "")

            # MiniCPM-V-4.5: 从文本中解析 <tool_call> 标签
            if not tool_calls_raw and content:
                parsed = _parse_tool_calls_from_text(content)
                if parsed:
                    tool_calls_raw = [
                        {"id": f"tc_{i}", "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)}}
                        for i, tc in enumerate(parsed)
                    ]
                    # 打印模型原始输出中的工具调用
                    print(f"  📝 从文本中解析到 {len(tool_calls_raw)} 个工具调用")

            if tool_calls_raw:
                # 处理工具调用
                print(f"  📞 MiniCPM 请求调用 {len(tool_calls_raw)} 个工具")

                # 将助手消息添加到历史（标准 tool_calls 格式）
                assistant_msg = {"role": "assistant", "content": content or None, "tool_calls": tool_calls_raw}
                self.conversation_history.append(assistant_msg)

                # 执行所有工具调用
                for tc in tool_calls_raw:
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

                    # 将工具结果添加到历史（压缩：只保留关键字段，避免超出上下文窗口）
                    compact = _compact_tool_result(tool_name, result)
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": json.dumps(compact, ensure_ascii=False)
                    })

            else:
                # 没有工具调用，生成最终响应
                content = message.get("content", "")
                print(f"\n✅ MiniCPM 生成最终响应:")
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
    # 从环境变量获取API密钥
    minicpm_api_key = os.getenv("MINICPM_API_KEY") or os.getenv("MINICPM_NEW_API_KEY")
    amap_api_key = "2a74be819e0a749654d071c21681477a"

    if not minicpm_api_key:
        print("❌ 未找到 MINICPM_API_KEY 环境变量")
        return

    minicpm_model = os.getenv("MINICPM_MODEL", "MiniCPM5-2B-0822")

    print(f"✅ MiniCPM API Key: {minicpm_api_key[:20]}...")
    print(f"✅ 高德 API Key: {amap_api_key[:20]}...")
    print(f"✅ MiniCPM 模型: {minicpm_model}")

    # 创建测试实例
    tester = MiniCPME2ETest(minicpm_api_key, amap_api_key, model=minicpm_model)

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
        "model": minicpm_model,
        "api_endpoint": "https://api.modelbest.cn/v1/chat/completions",
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

    report_path = "/Users/kaori/Downloads/where-to-eat-main/tests/results/minicpm_e2e_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📁 报告已保存至: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
