"""
真实模型适配器
接入MiniCPM5-2B和Kimi 2.5的真实API
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import httpx


@dataclass
class ToolCall:
    """工具调用记录"""
    tool_name: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    response_time_ms: float = 0
    success: bool = True


@dataclass
class ModelResponse:
    """模型响应"""
    content: str
    tool_calls: List[ToolCall]
    total_response_time_ms: float
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RealModelAdapter:
    """真实模型适配器基类"""

    def __init__(self, model_name: str, api_url: str, api_key: str):
        self.model_name = model_name
        self.api_url = api_url
        self.api_key = api_key
        self.call_history: List[Dict[str, Any]] = []

    async def call_api(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        调用模型API

        Args:
            messages: 消息列表
            tools: 工具定义列表

        Returns:
            API响应
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False
        }

        # 如果有工具定义，添加到请求中
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        start_time = time.time()

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
            except httpx.HTTPStatusError as e:
                print(f"API错误: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print(f"请求错误: {str(e)}")
                raise

        response_time = (time.time() - start_time) * 1000

        # 记录调用
        self.call_history.append({
            "model": self.model_name,
            "messages": messages,
            "response_time_ms": response_time,
            "status": "success" if result.get("choices") else "error"
        })

        return result


class MiniCPM5RealAdapter(RealModelAdapter):
    """MiniCPM5-2B 真实API适配器"""

    def __init__(self):
        super().__init__(
            model_name="MiniCPM5-2B-0822",
            api_url="https://api.modelbest.cn/v1/chat/completions",
            api_key="sk-live-kSYNRRl2WfjElqdg049sg6suZ2009OsrM2g6ByvO8eY"
        )

    async def process_message(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """处理用户消息并返回响应"""
        start_time = time.time()

        # 构建系统提示
        system_prompt = self._build_system_prompt(context)

        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        # 构建工具定义
        tools = self._build_tool_definitions(available_tools)

        try:
            # 调用API
            result = await self.call_api(messages, tools)

            # 解析响应
            content = ""
            tool_calls = []

            if result.get("choices"):
                choice = result["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")

                # 检查是否有工具调用
                if message.get("tool_calls"):
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        try:
                            params = json.loads(func.get("arguments", "{}"))
                        except:
                            params = {}

                        tool_calls.append(ToolCall(
                            tool_name=tool_name,
                            params=params
                        ))

            response_time = (time.time() - start_time) * 1000
            tokens_used = result.get("usage", {}).get("total_tokens", 0)

            return ModelResponse(
                content=content,
                tool_calls=tool_calls,
                total_response_time_ms=response_time,
                tokens_used=tokens_used,
                metadata={"model": self.model_name}
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ModelResponse(
                content=f"API调用失败: {str(e)}",
                tool_calls=[],
                total_response_time_ms=response_time,
                metadata={"model": self.model_name, "error": str(e)}
            )

    def _build_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """构建系统提示"""
        base_prompt = """你是一个智能助手，可以帮助用户查询地理位置、路线和餐厅信息。

可用工具：
1. maps_geo - 地理编码，将地址转换为坐标
2. maps_regeocode - 逆地理编码，将坐标转换为地址
3. maps_direction_driving - 驾车路线规划
4. maps_direction_transit_integrated - 公交地铁路线规划
5. maps_direction_bicycling - 骑行路线规划
6. maps_text_search - 关键词搜索餐厅
7. maps_search_detail - 查询餐厅详情

规则：
- 当用户提到地点时，使用maps_geo获取坐标
- 当用户询问路线时，使用对应的路线规划工具
- 当用户想找餐厅时，使用maps_text_search搜索
- 所有坐标格式为：经度,纬度
- 城市默认为北京"""

        if context:
            if context.get("city"):
                base_prompt += f"\n当前城市：{context['city']}"
            if context.get("cuisine"):
                base_prompt += f"\n用户偏好菜系：{context['cuisine']}"

        return base_prompt

    def _build_tool_definitions(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建工具定义"""
        tool_definitions = []

        for tool in tools:
            tool_name = tool.get("name", "")

            # 根据工具名称构建定义
            if tool_name == "maps_geo":
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": "maps_geo",
                        "description": "地理编码，将地址字符串转换为坐标",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "address": {
                                    "type": "string",
                                    "description": "地址字符串"
                                },
                                "city": {
                                    "type": "string",
                                    "description": "城市名称",
                                    "default": "北京"
                                }
                            },
                            "required": ["address"]
                        }
                    }
                })
            elif tool_name == "maps_direction_driving":
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": "maps_direction_driving",
                        "description": "驾车路线规划，计算两点间的驾车时间和路线",
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
                })
            elif tool_name == "maps_direction_transit_integrated":
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": "maps_direction_transit_integrated",
                        "description": "公交地铁路线规划，计算两点间的公共交通时间和换乘信息",
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
                                    "description": "出发地城市",
                                    "default": "北京"
                                },
                                "cityd": {
                                    "type": "string",
                                    "description": "目的地城市",
                                    "default": "北京"
                                }
                            },
                            "required": ["origin", "destination", "city", "cityd"]
                        }
                    }
                })
            elif tool_name == "maps_text_search":
                tool_definitions.append({
                    "type": "function",
                    "function": {
                        "name": "maps_text_search",
                        "description": "关键词搜索，按关键词搜索附近的餐厅",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "keywords": {
                                    "type": "string",
                                    "description": "搜索关键词，如：日料、火锅、烤肉"
                                },
                                "city": {
                                    "type": "string",
                                    "description": "城市名称",
                                    "default": "北京"
                                }
                            },
                            "required": ["keywords", "city"]
                        }
                    }
                })

        return tool_definitions


class Kimi25RealAdapter(RealModelAdapter):
    """Kimi 2.5 真实API适配器"""

    def __init__(self):
        # Kimi 2.5 使用Moonshot API
        super().__init__(
            model_name="moonshot-v1-8k",
            api_url="https://api.moonshot.cn/v1/chat/completions",
            api_key="sk-your-kimi-api-key"  # 需要用户提供
        )

    async def process_message(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """处理用户消息并返回响应"""
        start_time = time.time()

        # 构建系统提示
        system_prompt = self._build_system_prompt(context)

        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        # 构建工具定义
        tools = self._build_tool_definitions(available_tools)

        try:
            # 调用API
            result = await self.call_api(messages, tools)

            # 解析响应
            content = ""
            tool_calls = []

            if result.get("choices"):
                choice = result["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")

                # 检查是否有工具调用
                if message.get("tool_calls"):
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        try:
                            params = json.loads(func.get("arguments", "{}"))
                        except:
                            params = {}

                        tool_calls.append(ToolCall(
                            tool_name=tool_name,
                            params=params
                        ))

            response_time = (time.time() - start_time) * 1000
            tokens_used = result.get("usage", {}).get("total_tokens", 0)

            return ModelResponse(
                content=content,
                tool_calls=tool_calls,
                total_response_time_ms=response_time,
                tokens_used=tokens_used,
                metadata={"model": self.model_name}
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ModelResponse(
                content=f"API调用失败: {str(e)}",
                tool_calls=[],
                total_response_time_ms=response_time,
                metadata={"model": self.model_name, "error": str(e)}
            )

    def _build_system_prompt(self, context: Optional[Dict[str, Any]]) -> str:
        """构建系统提示"""
        base_prompt = """你是一个智能助手，可以帮助用户查询地理位置、路线和餐厅信息。

可用工具：
1. maps_geo - 地理编码，将地址转换为坐标
2. maps_regeocode - 逆地理编码，将坐标转换为地址
3. maps_direction_driving - 驾车路线规划
4. maps_direction_transit_integrated - 公交地铁路线规划
5. maps_direction_bicycling - 骑行路线规划
6. maps_text_search - 关键词搜索餐厅
7. maps_search_detail - 查询餐厅详情

规则：
- 当用户提到地点时，使用maps_geo获取坐标
- 当用户询问路线时，使用对应的路线规划工具
- 当用户想找餐厅时，使用maps_text_search搜索
- 所有坐标格式为：经度,纬度
- 城市默认为北京
- 优先考虑多人聚餐的公平性"""

        if context:
            if context.get("city"):
                base_prompt += f"\n当前城市：{context['city']}"
            if context.get("cuisine"):
                base_prompt += f"\n用户偏好菜系：{context['cuisine']}"

        return base_prompt

    def _build_tool_definitions(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建工具定义"""
        # 复用MiniCPM的工具定义
        adapter = MiniCPM5RealAdapter()
        return adapter._build_tool_definitions(tools)
