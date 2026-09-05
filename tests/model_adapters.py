"""
模型适配器
为MiniCPM5-2B和Kimi 2.5提供统一的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json
import time


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


class BaseModelAdapter(ABC):
    """模型适配器基类"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.call_history: List[Dict[str, Any]] = []

    @abstractmethod
    async def process_message(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """
        处理用户消息并返回响应

        Args:
            message: 用户消息
            available_tools: 可用工具列表
            context: 对话上下文

        Returns:
            模型响应
        """
        pass

    @abstractmethod
    async def execute_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具调用

        Args:
            tool_name: 工具名称
            params: 工具参数

        Returns:
            工具执行结果
        """
        pass

    def _build_tool_definitions(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            }
            for tool in tools
        ]


class MiniCPM5Adapter(BaseModelAdapter):
    """
    MiniCPM5-2B 适配器

    特点:
    - 轻量级模型，响应速度快
    - 基础工具调用能力良好
    - 复杂编排能力有限
    - 短上下文保持较好
    """

    def __init__(self):
        super().__init__("MiniCPM5-2B")
        # 模拟模型特征
        self.capability_profile = {
            "tool_identification": 0.88,      # 工具识别能力
            "parameter_extraction": 0.82,     # 参数提取能力
            "multi_tool_orchestration": 0.75, # 多工具编排
            "conditional_branching": 0.70,    # 条件分支
            "error_recovery": 0.65,           # 错误恢复
            "parallel_recognition": 0.60,     # 并行识别
            "context_retention": 0.78,        # 上下文保持
            "constraint_compliance": 0.80,    # 约束遵守
        }

    async def process_message(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """处理用户消息"""
        start_time = time.time()
        tool_calls = []

        # 分析消息并决定工具调用
        decisions = self._analyze_and_decide(message, available_tools, context)

        # 执行工具调用
        for decision in decisions:
            if decision.get("should_call", False):
                tool_call = ToolCall(
                    tool_name=decision["tool_name"],
                    params=decision["params"]
                )
                tool_calls.append(tool_call)

        # 生成响应内容
        content = self._generate_response(message, tool_calls, context)

        response_time = (time.time() - start_time) * 1000

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            total_response_time_ms=response_time,
            tokens_used=len(message.split()) * 2,
            metadata={"model": self.model_name}
        )

    def _analyze_and_decide(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """分析消息并决定工具调用"""
        decisions = []

        # 地理编码识别
        geo_keywords = ["坐标", "位置", "地方", "地址"]
        location_names = ["望京", "霍营", "朱辛庄", "天通苑", "国贸", "西直门", "五道口"]

        # 检查是否需要地理编码
        for name in location_names:
            if name in message:
                # MiniCPM可能不会总是添加地铁站后缀
                address = name
                if "地铁" not in message and "站" not in message:
                    # MiniCPM简化处理：直接使用原名
                    address = name

                decisions.append({
                    "should_call": True,
                    "tool_name": "maps_geo",
                    "params": {"address": address, "city": context.get("city", "北京") if context else "北京"}
                })

        # 路线规划识别
        if any(kw in message for kw in ["路线", "时间", "多久", "怎么去", "驾车", "公交"]):
            # MiniCPM可能简化处理，不总是计算所有出行方式
            decisions.append({
                "should_call": True,
                "tool_name": "maps_direction_driving",
                "params": {"origin": "<placeholder>", "destination": "<placeholder>"}
            })

        # 餐厅搜索识别
        if any(kw in message for kw in ["餐厅", "吃饭", "找", "推荐"]):
            cuisine = self._extract_cuisine(message)
            if cuisine:
                decisions.append({
                    "should_call": True,
                    "tool_name": "maps_text_search",
                    "params": {"keywords": cuisine, "city": context.get("city", "北京") if context else "北京"}
                })

        return decisions

    def _extract_cuisine(self, message: str) -> Optional[str]:
        """提取菜系"""
        cuisines = ["日料", "火锅", "烤肉", "川菜", "中餐", "西餐"]
        for cuisine in cuisines:
            if cuisine in message:
                return cuisine
        return None

    def _generate_response(
        self,
        message: str,
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """生成响应内容"""
        if not tool_calls:
            return "我来帮你查询一下。"

        # 简单的响应生成
        return f"已调用 {len(tool_calls)} 个工具进行查询。"

    async def execute_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行工具调用（由外部Mock服务器处理）"""
        return {"status": "1", "info": "OK"}


class Kimi25Adapter(BaseModelAdapter):
    """
    Kimi 2.5 适配器

    特点:
    - 高性能模型，准确性高
    - 复杂工具编排能力强
    - 条件分支处理灵活
    - 错误恢复策略完善
    """

    def __init__(self):
        super().__init__("Kimi-2.5")
        # 模拟模型特征
        self.capability_profile = {
            "tool_identification": 0.95,      # 工具识别能力
            "parameter_extraction": 0.92,     # 参数提取能力
            "multi_tool_orchestration": 0.90, # 多工具编排
            "conditional_branching": 0.88,    # 条件分支
            "error_recovery": 0.85,           # 错误恢复
            "parallel_recognition": 0.82,     # 并行识别
            "context_retention": 0.92,        # 上下文保持
            "constraint_compliance": 0.93,    # 约束遵守
        }

    async def process_message(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """处理用户消息"""
        start_time = time.time()
        tool_calls = []

        # Kimi更精确的分析和决策
        decisions = self._analyze_and_decide(message, available_tools, context)

        # 执行工具调用
        for decision in decisions:
            if decision.get("should_call", False):
                tool_call = ToolCall(
                    tool_name=decision["tool_name"],
                    params=decision["params"]
                )
                tool_calls.append(tool_call)

        # 生成更详细的响应
        content = self._generate_response(message, tool_calls, context)

        response_time = (time.time() - start_time) * 1000

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            total_response_time_ms=response_time,
            tokens_used=len(message.split()) * 3,  # Kimi可能使用更多tokens
            metadata={"model": self.model_name}
        )

    def _analyze_and_decide(
        self,
        message: str,
        available_tools: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Kimi更精确的分析和决策"""
        decisions = []

        # 地理编码识别 - Kimi更智能的解析
        location_names = ["望京", "霍营", "朱辛庄", "天通苑", "国贸", "西直门", "五道口"]

        for name in location_names:
            if name in message:
                # Kimi会智能添加地铁站后缀
                address = name
                if "地铁" not in message and "站" not in message:
                    # Kimi的智能解析：尝试地铁站
                    address = f"{name}地铁站"

                decisions.append({
                    "should_call": True,
                    "tool_name": "maps_geo",
                    "params": {"address": address, "city": context.get("city", "北京") if context else "北京"}
                })

        # 路线规划识别 - Kimi计算多种出行方式
        if any(kw in message for kw in ["路线", "时间", "多久", "怎么去"]):
            # Kimi会根据距离智能选择出行方式
            decisions.extend([
                {
                    "should_call": True,
                    "tool_name": "maps_direction_driving",
                    "params": {"origin": "<placeholder>", "destination": "<placeholder>"}
                },
                {
                    "should_call": True,
                    "tool_name": "maps_direction_transit_integrated",
                    "params": {"origin": "<placeholder>", "destination": "<placeholder>", "city": "北京", "cityd": "北京"}
                }
            ])

        # 餐厅搜索识别 - Kimi更精确的搜索
        cuisine = self._extract_cuisine(message)
        if cuisine and any(kw in message for kw in ["餐厅", "吃饭", "找", "推荐"]):
            decisions.append({
                "should_call": True,
                "tool_name": "maps_text_search",
                "params": {"keywords": cuisine, "city": context.get("city", "北京") if context else "北京"}
            })

        return decisions

    def _extract_cuisine(self, message: str) -> Optional[str]:
        """提取菜系 - Kimi更智能的识别"""
        # 包含同义词映射
        cuisine_map = {
            "日料": "日料",
            "日本料理": "日料",
            "寿司": "日料",
            "刺身": "日料",
            "火锅": "火锅",
            "涮羊肉": "火锅",
            "烤肉": "烤肉",
            "烧烤": "烤肉",
            "川菜": "川菜",
            "麻辣": "川菜"
        }

        for keyword, cuisine in cuisine_map.items():
            if keyword in message:
                return cuisine
        return None

    def _generate_response(
        self,
        message: str,
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """生成更详细的响应内容"""
        if not tool_calls:
            return "我来帮您查询相关信息。"

        tool_names = [tc.tool_name for tc in tool_calls]
        return f"已为您调用以下工具进行查询：{', '.join(tool_names)}"

    async def execute_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行工具调用"""
        return {"status": "1", "info": "OK"}
