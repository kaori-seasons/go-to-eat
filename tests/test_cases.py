"""
测试用例集
覆盖10个核心测试场景
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class TestCategory(Enum):
    """测试类别"""
    TOOL_IDENTIFICATION = "D1-工具识别"
    PARAMETER_EXTRACTION = "D2-参数提取"
    PARAMETER_VALIDATION = "D3-参数验证"
    MULTI_TOOL_ORCHESTRATION = "D4-多工具编排"
    CONDITIONAL_BRANCHING = "D5-条件分支"
    ERROR_RECOVERY = "D6-错误恢复"
    PARALLEL_RECOGNITION = "D7-并行调用"
    CONTEXT_RETENTION = "D8-上下文保持"
    RESULT_INTEGRATION = "D9-结果整合"
    CONSTRAINT_COMPLIANCE = "D10-约束遵守"


class TestDifficulty(Enum):
    """测试难度"""
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5


@dataclass
class ExpectedToolCall:
    """期望的工具调用"""
    tool_name: str
    params: Dict[str, Any]
    is_parallel: bool = False
    dependency: Optional[str] = None


@dataclass
class TestCase:
    """测试用例"""
    test_id: str
    name: str
    category: TestCategory
    difficulty: TestDifficulty
    description: str
    input_message: str
    context: Dict[str, Any]
    available_tools: List[Dict[str, Any]]
    expected_tool_calls: List[ExpectedToolCall]
    expected_sequence: List[str]
    evaluation_criteria: List[str]
    error_injection: Optional[Dict[str, Any]] = None
    conversation_turns: Optional[List[Dict[str, Any]]] = None


# ============================================================================
# 测试用例定义
# ============================================================================

# TC-001: 工具识别 - 简单场景
TC_001 = TestCase(
    test_id="TC-001",
    name="单工具识别",
    category=TestCategory.TOOL_IDENTIFICATION,
    difficulty=TestDifficulty.LEVEL_1,
    description="从自然语言中识别需要调用的地理编码工具",
    input_message="帮我查一下望京地铁站的坐标",
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_direction_driving", "description": "驾车路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="maps_geo",
            params={"address": "望京地铁站", "city": "北京"}
        )
    ],
    expected_sequence=["maps_geo"],
    evaluation_criteria=[
        "正确识别需要地理编码工具",
        "排除不相关的路线搜索工具",
        "参数包含正确的地址和城市"
    ]
)

# TC-002: 参数提取 - 多字段
TC_002 = TestCase(
    test_id="TC-002",
    name="多参数提取",
    category=TestCategory.PARAMETER_EXTRACTION,
    difficulty=TestDifficulty.LEVEL_2,
    description="从用户输入中提取起点终点并调用多个工具",
    input_message="计算从来广营到国贸的驾车时间",
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_direction_driving", "description": "驾车路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="maps_geo",
            params={"address": "来广营", "city": "北京"}
        ),
        ExpectedToolCall(
            tool_name="maps_geo",
            params={"address": "国贸", "city": "北京"}
        ),
        ExpectedToolCall(
            tool_name="maps_direction_driving",
            params={"origin": "<dynamic>", "destination": "<dynamic>"}
        )
    ],
    expected_sequence=["maps_geo", "maps_geo", "maps_direction_driving"],
    evaluation_criteria=[
        "正确拆分起点终点",
        "坐标格式符合要求 (经度,纬度)",
        "使用上下文中的城市信息"
    ]
)

# TC-003: 参数验证 - 边界值
TC_003 = TestCase(
    test_id="TC-003",
    name="边界参数验证",
    category=TestCategory.PARAMETER_VALIDATION,
    difficulty=TestDifficulty.LEVEL_2,
    description="验证缺失参数时的处理",
    input_message="帮我找附近的火锅店",
    context={},  # 故意缺少城市信息
    available_tools=[
        {"name": "maps_text_search", "description": "关键词搜索"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(
            tool_name="maps_text_search",
            params={"keywords": "火锅", "city": "<missing>"}
        )
    ],
    expected_sequence=["maps_text_search"],
    evaluation_criteria=[
        "能识别缺失必填参数",
        "给出明确的参数补充请求",
        "不尝试调用不完整的工具"
    ]
)

# TC-004: 多工具编排 - 顺序依赖
TC_004 = TestCase(
    test_id="TC-004",
    name="顺序依赖编排",
    category=TestCategory.MULTI_TOOL_ORCHESTRATION,
    difficulty=TestDifficulty.LEVEL_3,
    description="测试多工具按正确顺序调用",
    input_message="我从望京出发，朋友从霍营出发，帮我找一家日料店聚餐",
    context={"city": "北京", "cuisine": "日料"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_regeocode", "description": "逆地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_direction_driving", "description": "驾车路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_geo", params={"address": "望京", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "霍营", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_text_search", params={"keywords": "日料", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"})
    ],
    expected_sequence=["maps_geo", "maps_geo", "maps_text_search", "maps_direction_driving", "maps_direction_driving"],
    evaluation_criteria=[
        "地理编码在搜索之前",
        "路线计算在获取餐厅后",
        "工具调用顺序符合业务逻辑",
        "正确处理异步依赖关系"
    ]
)

# TC-005: 条件分支 - 动态决策
TC_005 = TestCase(
    test_id="TC-005",
    name="条件分支决策",
    category=TestCategory.CONDITIONAL_BRANCHING,
    difficulty=TestDifficulty.LEVEL_3,
    description="根据距离动态选择出行方式",
    input_message="计算从朱辛庄到五道口的出行时间",
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_direction_driving", "description": "驾车路线"},
        {"name": "maps_direction_transit_integrated", "description": "公交地铁路线"},
        {"name": "maps_direction_bicycling", "description": "骑行路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_geo", params={"address": "朱辛庄", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "五道口", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"})
    ],
    expected_sequence=["maps_geo", "maps_geo", "maps_direction_driving", "maps_direction_transit_integrated"],
    evaluation_criteria=[
        "根据坐标距离动态选择出行方式",
        "不固定使用所有出行方式",
        "分支决策有合理依据"
    ]
)

# TC-006: 错误恢复 - API失败
TC_006 = TestCase(
    test_id="TC-006",
    name="API调用失败恢复",
    category=TestCategory.ERROR_RECOVERY,
    difficulty=TestDifficulty.LEVEL_4,
    description="测试工具调用失败时的降级处理",
    input_message="帮我规划从国贸到西直门的路线",
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_direction_driving", "description": "驾车路线"},
        {"name": "maps_direction_transit_integrated", "description": "公交地铁路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_geo", params={"address": "国贸", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "西直门", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"})
    ],
    expected_sequence=["maps_geo", "maps_geo", "maps_direction_driving", "maps_direction_transit_integrated"],
    evaluation_criteria=[
        "识别错误类型",
        "执行合理的降级策略",
        "明确告知用户服务状态",
        "不静默失败"
    ],
    error_injection={
        "tool": "maps_direction_driving",
        "error": "API_LIMIT_EXCEEDED",
        "injection_rate": 1.0
    }
)

# TC-007: 并行调用识别
TC_007 = TestCase(
    test_id="TC-007",
    name="独立工具并行执行",
    category=TestCategory.PARALLEL_RECOGNITION,
    difficulty=TestDifficulty.LEVEL_4,
    description="识别可并行的独立工具调用",
    input_message="我们三个人分别从望京、霍营、朱辛庄出发，帮我推荐餐厅",
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_direction_driving", "description": "驾车路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_geo", params={"address": "望京", "city": "北京"}, is_parallel=True),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "霍营", "city": "北京"}, is_parallel=True),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "朱辛庄", "city": "北京"}, is_parallel=True),
        ExpectedToolCall(tool_name="maps_text_search", params={"keywords": "餐厅", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}, is_parallel=True),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}, is_parallel=True),
        ExpectedToolCall(tool_name="maps_direction_driving", params={"origin": "<dynamic>", "destination": "<dynamic>"}, is_parallel=True)
    ],
    expected_sequence=["maps_geo", "maps_geo", "maps_geo", "maps_text_search", "maps_direction_driving", "maps_direction_driving", "maps_direction_driving"],
    evaluation_criteria=[
        "识别三个地理编码可并行",
        "识别三个路线计算可并行",
        "串行依赖关系正确",
        "并行调用数量合理（不超过API限制）"
    ]
)

# TC-008: 多轮上下文管理
TC_008 = TestCase(
    test_id="TC-008",
    name="多轮对话状态保持",
    category=TestCategory.CONTEXT_RETENTION,
    difficulty=TestDifficulty.LEVEL_4,
    description="测试多轮对话中的上下文保持",
    input_message="",  # 将使用conversation_turns
    context={"city": "北京"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_direction_driving", "description": "驾车路线"}
    ],
    expected_tool_calls=[],
    expected_sequence=[],
    evaluation_criteria=[
        "正确维护对话状态",
        "坐标信息在轮次间传递",
        "切换需求时保持上下文",
        "不重复已完成的工具调用"
    ],
    conversation_turns=[
        {"turn": 1, "user": "我从望京出发", "expected_tools": ["maps_geo"], "context_preserved": True},
        {"turn": 2, "user": "朋友从霍营", "expected_tools": ["maps_geo"], "context_preserved": True},
        {"turn": 3, "user": "找一家火锅店", "expected_tools": ["maps_text_search", "maps_direction_driving"], "context_preserved": True},
        {"turn": 4, "user": "换一家烤肉店", "expected_tools": ["maps_text_search"], "context_preserved": True}
    ]
)

# TC-009: 完整流程端到端
TC_009 = TestCase(
    test_id="TC-009",
    name="端到端推荐流程",
    category=TestCategory.RESULT_INTEGRATION,
    difficulty=TestDifficulty.LEVEL_5,
    description="测试完整的餐厅推荐流程",
    input_message="我们四个人分别从望京、霍营、朱辛庄、天通苑出发，想吃日料，19点到，帮我推荐餐厅",
    context={"city": "北京", "cuisine": "日料", "arrival_time": "19:00", "participants": 4},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_regeocode", "description": "逆地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_search_detail", "description": "餐厅详情"},
        {"name": "maps_direction_driving", "description": "驾车路线"},
        {"name": "maps_direction_transit_integrated", "description": "公交地铁路线"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_geo", params={"address": "望京", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "霍营", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "朱辛庄", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_geo", params={"address": "天通苑", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_text_search", params={"keywords": "日料", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"}),
        ExpectedToolCall(tool_name="maps_direction_transit_integrated", params={"origin": "<dynamic>", "destination": "<dynamic>", "city": "北京", "cityd": "北京"})
    ],
    expected_sequence=[
        "maps_geo", "maps_geo", "maps_geo", "maps_geo",
        "maps_text_search",
        "maps_direction_transit_integrated", "maps_direction_transit_integrated",
        "maps_direction_transit_integrated", "maps_direction_transit_integrated"
    ],
    evaluation_criteria=[
        "完整执行所有阶段",
        "遵守API调用限制 (max 9 detail queries)",
        "正确计算公平指标",
        "输出格式符合规范",
        "时间计算包含缓冲"
    ]
)

# TC-010: 复杂约束遵守
TC_010 = TestCase(
    test_id="TC-010",
    name="多约束条件遵守",
    category=TestCategory.CONSTRAINT_COMPLIANCE,
    difficulty=TestDifficulty.LEVEL_5,
    description="测试多重约束条件的解析和应用",
    input_message="帮我找餐厅，但不要川菜，预算200以内，要有包间",
    context={"city": "北京", "budget": 200, "exclude_cuisine": "川菜", "feature": "包间"},
    available_tools=[
        {"name": "maps_geo", "description": "地理编码"},
        {"name": "maps_text_search", "description": "关键词搜索"},
        {"name": "maps_search_detail", "description": "餐厅详情"}
    ],
    expected_tool_calls=[
        ExpectedToolCall(tool_name="maps_text_search", params={"keywords": "餐厅", "city": "北京"}),
        ExpectedToolCall(tool_name="maps_search_detail", params={"id": "<dynamic>"})
    ],
    expected_sequence=["maps_text_search", "maps_search_detail"],
    evaluation_criteria=[
        "正确解析多重约束",
        "在搜索/过滤阶段应用约束",
        "不遗漏任何约束条件",
        "输出中体现约束满足情况"
    ]
)


# 测试用例集合
ALL_TEST_CASES = [
    TC_001, TC_002, TC_003, TC_004, TC_005,
    TC_006, TC_007, TC_008, TC_009, TC_010
]


def get_test_case_by_id(test_id: str) -> Optional[TestCase]:
    """根据ID获取测试用例"""
    for tc in ALL_TEST_CASES:
        if tc.test_id == test_id:
            return tc
    return None


def get_test_cases_by_category(category: TestCategory) -> List[TestCase]:
    """根据类别获取测试用例"""
    return [tc for tc in ALL_TEST_CASES if tc.category == category]


def get_test_cases_by_difficulty(difficulty: TestDifficulty) -> List[TestCase]:
    """根据难度获取测试用例"""
    return [tc for tc in ALL_TEST_CASES if tc.difficulty == difficulty]
