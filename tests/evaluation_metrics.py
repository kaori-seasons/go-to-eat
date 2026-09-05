"""
评估指标计算框架
用于量化评估两个模型的功能调用能力
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class TestResult:
    """单个测试用例的结果"""
    test_id: str
    test_name: str
    model_name: str
    tool_accuracy: float = 0.0
    param_accuracy: float = 0.0
    sequence_accuracy: float = 0.0
    error_recovery: float = 0.0
    response_time_ms: float = 0.0
    context_retention: float = 0.0
    compliance_score: float = 0.0
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelMetrics:
    """模型整体指标"""
    model_name: str
    tool_accuracy: float = 0.0
    param_accuracy: float = 0.0
    sequence_accuracy: float = 0.0
    error_recovery: float = 0.0
    response_time_ms: float = 0.0
    context_retention: float = 0.0
    compliance_score: float = 0.0
    weighted_score: float = 0.0
    test_results: List[TestResult] = field(default_factory=list)


class EvaluationMetrics:
    """功能调用能力评估指标计算器"""

    # 指标权重
    WEIGHTS = {
        'tool_accuracy': 0.25,
        'param_accuracy': 0.20,
        'sequence_accuracy': 0.15,
        'error_recovery': 0.15,
        'response_time': 0.10,
        'context_retention': 0.15,
        'compliance': 0.10
    }

    def __init__(self):
        self.results: List[TestResult] = []

    def calculate_tool_accuracy(
        self,
        expected_tools: List[str],
        actual_tools: List[str]
    ) -> float:
        """
        计算工具调用准确率

        Args:
            expected_tools: 期望的工具调用列表
            actual_tools: 实际的工具调用列表

        Returns:
            准确率 (0-1)
        """
        if not expected_tools:
            return 1.0

        # 计算正确调用的数量
        correct = 0
        expected_set = set(expected_tools)
        actual_set = set(actual_tools)

        # 完全匹配
        correct = len(expected_set & actual_set)

        return correct / len(expected_tools) if expected_tools else 0.0

    def calculate_param_accuracy(
        self,
        expected_params: Dict[str, Any],
        actual_params: Dict[str, Any]
    ) -> float:
        """
        计算参数准确率

        Args:
            expected_params: 期望的参数
            actual_params: 实际的参数

        Returns:
            准确率 (0-1)
        """
        if not expected_params:
            return 1.0

        correct = 0
        for key, expected_value in expected_params.items():
            if key in actual_params:
                actual_value = actual_params[key]
                # 深度比较
                if self._deep_compare(expected_value, actual_value):
                    correct += 1

        return correct / len(expected_params) if expected_params else 0.0

    def _deep_compare(self, expected: Any, actual: Any) -> bool:
        """深度比较两个值"""
        if expected == actual:
            return True

        # 处理动态值（如坐标）
        if isinstance(expected, str) and expected.startswith("<dynamic>"):
            return True

        # 处理数字比较（允许小误差）
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            return abs(expected - actual) < 0.001

        return False

    def calculate_sequence_accuracy(
        self,
        expected_seq: List[str],
        actual_seq: List[str]
    ) -> float:
        """
        计算调用顺序准确率

        Args:
            expected_seq: 期望的调用顺序
            actual_seq: 实际的调用顺序

        Returns:
            准确率 (0-1)
        """
        if not expected_seq:
            return 1.0

        # 计算正确位置的数量
        correct_positions = 0
        for i, (expected, actual) in enumerate(zip(expected_seq, actual_seq)):
            if i < len(actual_seq) and expected == actual:
                correct_positions += 1

        return correct_positions / len(expected_seq) if expected_seq else 0.0

    def calculate_error_recovery_rate(
        self,
        error_scenarios: List[Dict[str, Any]],
        recovery_actions: List[Dict[str, Any]]
    ) -> float:
        """
        计算错误恢复成功率

        Args:
            error_scenarios: 错误场景列表
            recovery_actions: 恢复操作列表

        Returns:
            成功率 (0-1)
        """
        if not error_scenarios:
            return 1.0

        successful = 0
        for scenario, action in zip(error_scenarios, recovery_actions):
            if self._is_valid_recovery(scenario, action):
                successful += 1

        return successful / len(error_scenarios) if error_scenarios else 1.0

    def _is_valid_recovery(
        self,
        scenario: Dict[str, Any],
        action: Dict[str, Any]
    ) -> bool:
        """验证恢复操作是否有效"""
        error_type = scenario.get("error_type", "")
        recovery_type = action.get("recovery_type", "")

        # 有效的恢复策略映射
        valid_recoveries = {
            "API_LIMIT_EXCEEDED": ["fallback", "retry_later", "alternative_tool"],
            "TIMEOUT": ["retry", "alternative_tool", "cached_result"],
            "INVALID_RESPONSE": ["retry", "alternative_tool", "error_message"],
            "NETWORK_ERROR": ["retry", "cached_result", "error_message"],
        }

        return recovery_type in valid_recoveries.get(error_type, [])

    def calculate_response_time_score(
        self,
        response_times: List[float],
        threshold_ms: float = 2000
    ) -> float:
        """
        计算响应时间达标率

        Args:
            response_times: 响应时间列表(毫秒)
            threshold_ms: 阈值(毫秒)

        Returns:
            达标率 (0-1)
        """
        if not response_times:
            return 0.0

        within_threshold = sum(1 for t in response_times if t < threshold_ms)
        return within_threshold / len(response_times)

    def calculate_context_retention_score(
        self,
        conversation_turns: List[Dict[str, Any]]
    ) -> float:
        """
        计算上下文保持率

        Args:
            conversation_turns: 对话轮次列表

        Returns:
            保持率 (0-1)
        """
        if not conversation_turns:
            return 1.0

        retained = sum(
            1 for turn in conversation_turns
            if turn.get('context_preserved', False)
        )
        return retained / len(conversation_turns)

    def calculate_compliance_score(
        self,
        constraint_checks: List[Dict[str, Any]]
    ) -> float:
        """
        计算约束遵守率

        Args:
            constraint_checks: 约束检查列表

        Returns:
            遵守率 (0-1)
        """
        if not constraint_checks:
            return 1.0

        passed = sum(1 for check in constraint_checks if check.get('passed', False))
        return passed / len(constraint_checks)

    def calculate_weighted_score(self, metrics_dict: Dict[str, float]) -> float:
        """
        计算加权综合得分

        Args:
            metrics_dict: 指标字典

        Returns:
            加权得分 (0-100)
        """
        total_score = 0.0
        for key, weight in self.WEIGHTS.items():
            value = metrics_dict.get(key, 0.0)
            total_score += value * weight

        return total_score * 100  # 转换为百分制

    def aggregate_model_metrics(
        self,
        test_results: List[TestResult]
    ) -> ModelMetrics:
        """
        聚合模型的所有测试结果

        Args:
            test_results: 测试结果列表

        Returns:
            模型整体指标
        """
        if not test_results:
            return ModelMetrics(model_name="unknown")

        model_name = test_results[0].model_name

        # 计算平均值
        avg_metrics = {
            'tool_accuracy': sum(r.tool_accuracy for r in test_results) / len(test_results),
            'param_accuracy': sum(r.param_accuracy for r in test_results) / len(test_results),
            'sequence_accuracy': sum(r.sequence_accuracy for r in test_results) / len(test_results),
            'error_recovery': sum(r.error_recovery for r in test_results) / len(test_results),
            'response_time': sum(r.response_time_ms for r in test_results) / len(test_results),
            'context_retention': sum(r.context_retention for r in test_results) / len(test_results),
            'compliance': sum(r.compliance_score for r in test_results) / len(test_results),
        }

        # 计算加权综合得分
        weighted_score = self.calculate_weighted_score(avg_metrics)

        return ModelMetrics(
            model_name=model_name,
            tool_accuracy=avg_metrics['tool_accuracy'],
            param_accuracy=avg_metrics['param_accuracy'],
            sequence_accuracy=avg_metrics['sequence_accuracy'],
            error_recovery=avg_metrics['error_recovery'],
            response_time_ms=avg_metrics['response_time'],
            context_retention=avg_metrics['context_retention'],
            compliance_score=avg_metrics['compliance'],
            weighted_score=weighted_score,
            test_results=test_results
        )

    def generate_comparison_report(
        self,
        minicpm_metrics: ModelMetrics,
        kimi_metrics: ModelMetrics
    ) -> Dict[str, Any]:
        """
        生成对比报告

        Args:
            minicpm_metrics: MiniCPM5-2B指标
            kimi_metrics: Kimi 2.5指标

        Returns:
            对比报告字典
        """
        comparison = {
            "summary": {
                "minicpm_weighted_score": minicpm_metrics.weighted_score,
                "kimi_weighted_score": kimi_metrics.weighted_score,
                "winner": "MiniCPM5-2B" if minicpm_metrics.weighted_score > kimi_metrics.weighted_score else "Kimi 2.5",
                "score_difference": abs(minicpm_metrics.weighted_score - kimi_metrics.weighted_score)
            },
            "detailed_comparison": {
                "tool_accuracy": {
                    "minicpm": minicpm_metrics.tool_accuracy,
                    "kimi": kimi_metrics.tool_accuracy,
                    "difference": kimi_metrics.tool_accuracy - minicpm_metrics.tool_accuracy,
                    "winner": "Kimi" if kimi_metrics.tool_accuracy > minicpm_metrics.tool_accuracy else "MiniCPM"
                },
                "param_accuracy": {
                    "minicpm": minicpm_metrics.param_accuracy,
                    "kimi": kimi_metrics.param_accuracy,
                    "difference": kimi_metrics.param_accuracy - minicpm_metrics.param_accuracy,
                    "winner": "Kimi" if kimi_metrics.param_accuracy > minicpm_metrics.param_accuracy else "MiniCPM"
                },
                "sequence_accuracy": {
                    "minicpm": minicpm_metrics.sequence_accuracy,
                    "kimi": kimi_metrics.sequence_accuracy,
                    "difference": kimi_metrics.sequence_accuracy - minicpm_metrics.sequence_accuracy,
                    "winner": "Kimi" if kimi_metrics.sequence_accuracy > minicpm_metrics.sequence_accuracy else "MiniCPM"
                },
                "error_recovery": {
                    "minicpm": minicpm_metrics.error_recovery,
                    "kimi": kimi_metrics.error_recovery,
                    "difference": kimi_metrics.error_recovery - minicpm_metrics.error_recovery,
                    "winner": "Kimi" if kimi_metrics.error_recovery > minicpm_metrics.error_recovery else "MiniCPM"
                },
                "response_time": {
                    "minicpm_ms": minicpm_metrics.response_time_ms,
                    "kimi_ms": kimi_metrics.response_time_ms,
                    "difference_ms": kimi_metrics.response_time_ms - minicpm_metrics.response_time_ms,
                    "winner": "MiniCPM" if minicpm_metrics.response_time_ms < kimi_metrics.response_time_ms else "Kimi"
                },
                "context_retention": {
                    "minicpm": minicpm_metrics.context_retention,
                    "kimi": kimi_metrics.context_retention,
                    "difference": kimi_metrics.context_retention - minicpm_metrics.context_retention,
                    "winner": "Kimi" if kimi_metrics.context_retention > minicpm_metrics.context_retention else "MiniCPM"
                },
                "compliance": {
                    "minicpm": minicpm_metrics.compliance_score,
                    "kimi": kimi_metrics.compliance_score,
                    "difference": kimi_metrics.compliance_score - minicpm_metrics.compliance_score,
                    "winner": "Kimi" if kimi_metrics.compliance_score > minicpm_metrics.compliance_score else "MiniCPM"
                }
            },
            "recommendation": self._generate_recommendation(minicpm_metrics, kimi_metrics)
        }

        return comparison

    def _generate_recommendation(
        self,
        minicpm_metrics: ModelMetrics,
        kimi_metrics: ModelMetrics
    ) -> Dict[str, str]:
        """生成部署建议"""
        recommendations = {}

        # 基于综合得分
        if minicpm_metrics.weighted_score > kimi_metrics.weighted_score:
            recommendations["overall"] = "MiniCPM5-2B在综合能力上表现更优"
        else:
            recommendations["overall"] = "Kimi 2.5在综合能力上表现更优"

        # 基于各维度
        if minicpm_metrics.response_time_ms < kimi_metrics.response_time_ms:
            recommendations["latency"] = "MiniCPM5-2B响应更快，适合低延迟场景"
        else:
            recommendations["latency"] = "Kimi 2.5响应时间可接受，适合高精度场景"

        if kimi_metrics.error_recovery > minicpm_metrics.error_recovery:
            recommendations["reliability"] = "Kimi 2.5错误恢复能力更强，适合生产环境"
        else:
            recommendations["reliability"] = "MiniCPM5-2B错误恢复能力足够，适合简单场景"

        return recommendations
