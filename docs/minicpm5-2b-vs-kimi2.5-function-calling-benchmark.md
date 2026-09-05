# MiniCPM5-2B vs Kimi 2.5 功能调用能力对比测试方案

> **项目上下文**：Where to Eat - 多人聚餐地点推荐系统
> **测试目标**：精细化对比两个模型在复杂工具链场景下的功能调用能力
> **文档版本**：v1.0.0 | 2024-09-05

---

## 目录

- [1. 测试架构设计](#1-测试架构设计)
- [2. 功能调用能力维度分解](#2-功能调用能力维度分解)
- [3. 并行推理测试矩阵](#3-并行推理测试矩阵)
- [4. 测试用例集](#4-测试用例集)
- [5. 评估指标体系](#5-评估指标体系)
- [6. 执行流程与工具链](#6-执行流程与工具链)
- [7. 结果分析框架](#7-结果分析框架)
- [8. 生产部署建议](#8-生产部署建议)

---

## 1. 测试架构设计

### 1.1 神经网络结构并行推理模型

```
                        ┌─────────────────────────────────────────────┐
                        │           输入层 (Input Layer)              │
                        │   用户自然语言请求 → 标准化测试用例           │
                        └──────────────────┬──────────────────────────┘
                                           │
                ┌──────────────────────────┼──────────────────────────┐
                │                          │                          │
                ▼                          ▼                          ▼
    ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
    │   MiniCPM5-2B     │    │   Kimi 2.5        │    │   对照组          │
    │   (测试分支A)     │    │   (测试分支B)     │    │   (人工基准)      │
    └─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │      特征提取层              │
                        │  (多维度能力评估指标提取)    │
                        └──────────────┬──────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │      决策融合层              │
                        │  (加权评分 + 排序输出)       │
                        └──────────────┬──────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │      输出层                  │
                        │  对比报告 + 能力雷达图       │
                        └─────────────────────────────┘
```

### 1.2 测试隔离策略

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          测试环境隔离                                       │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     │
│  │   模拟环境       │     │   真实环境       │     │   压力环境       │     │
│  │   (Mock API)    │     │   (高德API)     │     │   (并发请求)    │     │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘     │
│           │                       │                       │               │
│  ┌────────┴────────┐     ┌────────┴────────┐     ┌────────┴────────┐     │
│  │  • 固定响应      │     │  • 真实数据      │     │  • 50+并发      │     │
│  │  • 可重复性      │     │  • 网络延迟      │     │  • 超时测试      │     │
│  │  • 错误注入      │     │  • 限流测试      │     │  • 内存监控      │     │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘     │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 功能调用能力维度分解

### 2.1 能力维度金字塔

```
                                    ▲
                                   /  \
                                  / 9  \
                                 / 复杂 \
                                / 决策  \
                               /─────────\
                              / 7, 8      \
                             / 多轮对话   \
                            /  上下文管理  \
                           /───────────────\
                          /  4, 5, 6        \
                         / 参数推断          \
                        / 错误处理            \
                       / 条件分支              \
                      /───────────────────────\
                     /  1, 2, 3                \
                    / 单工具调用                 \
                   / 参数验证                    \
                  / 响应解析                     \
                 /───────────────────────────────\
```

### 2.2 十大能力维度

| 维度ID | 维度名称 | 权重 | 描述 | 测试难度 |
|--------|----------|------|------|----------|
| D1 | 工具识别 | 10% | 从自然语言中识别需要调用的工具 | ★☆☆☆☆ |
| D2 | 参数提取 | 15% | 从用户输入中提取正确的工具参数 | ★★☆☆☆ |
| D3 | 参数验证 | 10% | 验证参数格式、类型、边界值 | ★★☆☆☆ |
| D4 | 多工具编排 | 15% | 按正确顺序调用多个工具 | ★★★☆☆ |
| D5 | 条件分支 | 10% | 根据前序结果决定下一步调用 | ★★★☆☆ |
| D6 | 错误恢复 | 10% | 工具调用失败时的降级处理 | ★★★★☆ |
| D7 | 并行调用 | 10% | 识别可并行的独立工具调用 | ★★★★☆ |
| D8 | 上下文保持 | 10% | 多轮对话中保持工具状态 | ★★★★☆ |
| D9 | 结果整合 | 5% | 将多个工具结果整合为统一输出 | ★★★★★ |
| D10 | 约束遵守 | 5% | 遵守业务规则和输出格式约束 | ★★★★★ |

---

## 3. 并行推理测试矩阵

### 3.1 测试场景矩阵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          场景复杂度矩阵                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     工具数量                                                                 │
│        ▲                                                                    │
│        │                                                                    │
│    7+  │  ┌─────┐                                                          │
│        │  │ S7  │  高复杂度多工具链                                          │
│        │  └─────┘                                                          │
│    5-6 │  ┌─────┐  ┌─────┐                                                │
│        │  │ S5  │  │ S6  │  中高复杂度                                     │
│        │  └─────┘  └─────┘                                                │
│    3-4 │  ┌─────┐  ┌─────┐  ┌─────┐                                       │
│        │  │ S3  │  │ S4  │  │ S4b │  中等复杂度                            │
│        │  └─────┘  └─────┘  └─────┘                                       │
│    1-2 │  ┌─────┐  ┌─────┐                                                │
│        │  │ S1  │  │ S2  │  低复杂度                                      │
│        │  └─────┘  └─────┘                                                │
│        └────────────────────────────────────────────────────> 对话轮次     │
│              1        2-3       4-5       6+                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 场景分类

| 场景ID | 场景名称 | 工具数 | 对话轮次 | 核心测试点 |
|--------|----------|--------|----------|------------|
| S1 | 单工具解析 | 1 | 1 | 基础参数提取 |
| S2 | 地理编码验证 | 2-3 | 1 | 参数验证+结果校验 |
| S3 | 路线规划 | 3-4 | 2-3 | 多工具编排 |
| S4 | 餐厅搜索+排序 | 4-5 | 3-4 | 条件分支+结果整合 |
| S5 | 完整推荐流程 | 5-6 | 4-5 | 全链路执行 |
| S6 | 错误恢复场景 | 5+ | 3+ | 降级策略 |
| S7 | 多轮交互优化 | 7+ | 6+ | 上下文管理 |

---

## 4. 测试用例集

### 4.1 基础能力测试 (D1-D3)

#### TC-001: 工具识别 - 简单场景

```yaml
id: TC-001
name: 单工具识别
category: D1-工具识别
difficulty: 1/5

input:
  user_message: "帮我查一下望京地铁站的坐标"

available_tools:
  - maps_geo
  - maps_text_search
  - maps_direction_driving

expected_tool_call:
  name: maps_geo
  confidence: high

evaluation_criteria:
  - 是否正确识别需要地理编码工具
  - 是否排除不相关的路线搜索工具
  - 响应延迟 < 2s
```

#### TC-002: 参数提取 - 多字段

```yaml
id: TC-002
name: 多参数提取
category: D2-参数提取
difficulty: 2/5

input:
  user_message: "计算从来广营到国贸的驾车时间"
  context:
    city: 北京

available_tools:
  - maps_geo
  - maps_direction_driving

expected_tool_calls:
  - name: maps_geo
    params:
      address: "来广营"
      city: "北京"
  - name: maps_geo
    params:
      address: "国贸"
      city: "北京"
  - name: maps_direction_driving
    params:
      origin: "<dynamic>"
      destination: "<dynamic>"

evaluation_criteria:
  - 正确拆分起点终点
  - 坐标格式符合要求 (经度,纬度)
  - 使用上下文中的城市信息
```

#### TC-003: 参数验证 - 边界值

```yaml
id: TC-003
name: 边界参数验证
category: D3-参数验证
difficulty: 2/5

input:
  user_message: "帮我找附近的火锅店"

available_tools:
  - maps_text_search

test_variations:
  - variation: 无城市信息
    expected: 请求补充城市或使用默认城市
  - variation: 关键词为空
    expected: 请求用户提供搜索关键词
  - variation: 城市不在支持范围
    expected: 明确告知不支持该城市

evaluation_criteria:
  - 能识别缺失必填参数
  - 给出明确的参数补充请求
  - 不尝试调用不完整的工具
```

### 4.2 中级能力测试 (D4-D6)

#### TC-004: 多工具编排 - 顺序依赖

```yaml
id: TC-004
name: 顺序依赖编排
category: D4-多工具编排
difficulty: 3/5

input:
  user_message: "我从望京出发，朋友从霍营出发，帮我找一家日料店聚餐"
  context:
    city: 北京
    cuisine: 日料

execution_plan:
  step_1: maps_geo (望京)
  step_2: maps_geo (霍营)
  step_3: calculate_centroid
  step_4: maps_regeocode (centroid)
  step_5: maps_text_search (日料, near centroid)
  step_6: maps_direction_driving (望京 → restaurant)
  step_7: maps_direction_driving (霍营 → restaurant)

evaluation_criteria:
  - 地理编码在搜索之前
  - 路线计算在获取餐厅后
  - 工具调用顺序符合业务逻辑
  - 正确处理异步依赖关系
```

#### TC-005: 条件分支 - 动态决策

```yaml
id: TC-005
name: 条件分支决策
category: D5-条件分支
difficulty: 3/5

input:
  user_message: "计算从朱辛庄到五道口的出行时间"

branching_scenarios:
  - scenario: 距离 < 3km
    expected_branch: 计算骑行+公交+驾车
    reasoning: 短距离多方式对比
  - scenario: 距离 3-10km
    expected_branch: 计算公交+驾车
    reasoning: 中距离主要方式
  - scenario: 距离 > 10km
    expected_branch: 计算驾车+长途公交
    reasoning: 长距离考虑长途交通

evaluation_criteria:
  - 根据坐标距离动态选择出行方式
  - 不固定使用所有出行方式
  - 分支决策有合理依据
```

#### TC-006: 错误恢复 - API失败

```yaml
id: TC-006
name: API调用失败恢复
category: D6-错误恢复
difficulty: 4/5

input:
  user_message: "帮我规划从国贸到西直门的路线"

error_injection:
  - tool: maps_direction_driving
    error: "API_LIMIT_EXCEEDED"
    injection_rate: 100%

expected_behavior:
  primary: "尝试使用公共交通替代"
  secondary: "告知用户驾车服务暂时不可用"
  fallback: "提供估算时间（明确标注为估算）"

evaluation_criteria:
  - 识别错误类型
  - 执行合理的降级策略
  - 明确告知用户服务状态
  - 不静默失败
```

### 4.3 高级能力测试 (D7-D10)

#### TC-007: 并行调用识别

```yaml
id: TC-007
name: 独立工具并行执行
category: D7-并行调用
difficulty: 4/5

input:
  user_message: "我们三个人分别从望京、霍营、朱辛庄出发，帮我推荐餐厅"

parallel_detection:
  independent_calls:
    - maps_geo (望京)
    - maps_geo (霍营)
    - maps_geo (朱辛庄)
  sequential_chain:
    - calculate_centroid
    - maps_text_search
    - [maps_direction_driving × 3]

evaluation_criteria:
  - 识别三个地理编码可并行
  - 识别三个路线计算可并行
  - 串行依赖关系正确
  - 并行调用数量合理（不超过API限制）
```

#### TC-008: 多轮上下文管理

```yaml
id: TC-008
name: 多轮对话状态保持
category: D8-上下文保持
difficulty: 4/5

conversation_flow:
  turn_1:
    user: "我从望京出发"
    expected: 调用 maps_geo，保存坐标
  turn_2:
    user: "朋友从霍营"
    expected: 调用 maps_geo，保存坐标
  turn_3:
    user: "找一家火锅店"
    expected: 使用前两轮坐标计算中心点，搜索火锅
  turn_4:
    user: "换一家烤肉店"
    expected: 保持坐标，重新搜索烤肉

evaluation_criteria:
  - 正确维护对话状态
  - 坐标信息在轮次间传递
  - 切换需求时保持上下文
  - 不重复已完成的工具调用
```

#### TC-009: 完整流程端到端

```yaml
id: TC-009
name: 端到端推荐流程
category: D9-结果整合 + D10-约束遵守
difficulty: 5/5

input:
  user_message: "我们四个人分别从望京、霍营、朱辛庄、天通苑出发，想吃日料，19点到，帮我推荐餐厅"
  context:
    city: 北京
    cuisine: 日料
    arrival_time: "19:00"

full_flow_validation:
  phase_1_geocoding:
    - maps_geo × 4
    - adcode验证
    - 格式: "原始输入 → 实际使用地点"

  phase_2_restaurant_search:
    - calculate_centroid
    - maps_text_search (日料)
    - deduplication
    - max 9 candidates

  phase_3_route_calculation:
    - maps_direction_transit × 4 × N_restaurants
    - maps_direction_driving × 4 × N_restaurants
    - duration extraction (秒→分钟)

  phase_4_scoring:
    - max = max(每人耗时)
    - spread = max - min
    - avg = sum / 人数
    - sort by strategy (default: max优先)

  phase_5_output:
    - 1 recommended + 2 alternatives
    - 每人完整路线说明
    - 建议出发时间 = arrival - duration - 5min

evaluation_criteria:
  - 完整执行所有阶段
  - 遵守API调用限制 (max 9 detail queries)
  - 正确计算公平指标
  - 输出格式符合规范
  - 时间计算包含缓冲
```

#### TC-010: 复杂约束遵守

```yaml
id: TC-010
name: 多约束条件遵守
category: D10-约束遵守
difficulty: 5/5

input:
  user_message: "帮我找餐厅，但不要川菜，预算200以内，要有包间"

constraints:
  - exclusion: 川菜
  - budget: 200
  - feature: 包间

validation_checkpoints:
  - 搜索结果是否排除川菜
  - 人均消费是否 ≤ 200
  - 是否检查餐厅设施信息
  - 输出是否明确说明约束应用情况

evaluation_criteria:
  - 正确解析多重约束
  - 在搜索/过滤阶段应用约束
  - 不遗漏任何约束条件
  - 输出中体现约束满足情况
```

---

## 5. 评估指标体系

### 5.1 量化指标

```python
# 评估指标计算框架

class EvaluationMetrics:
    """功能调用能力评估指标"""

    def calculate_tool_accuracy(self, expected_tools, actual_tools):
        """
        工具调用准确率
        权重: 25%
        """
        correct = len(set(expected_tools) & set(actual_tools))
        return correct / len(expected_tools) if expected_tools else 0

    def calculate_param_accuracy(self, expected_params, actual_params):
        """
        参数准确率
        权重: 20%
        包含: 类型正确 + 值正确 + 格式正确
        """
        if not expected_params:
            return 1.0
        correct = sum(1 for k, v in expected_params.items()
                     if k in actual_params and actual_params[k] == v)
        return correct / len(expected_params)

    def calculate_sequence_accuracy(self, expected_seq, actual_seq):
        """
        调用顺序准确率
        权重: 15%
        """
        if not expected_seq:
            return 1.0
        correct_positions = sum(1 for i, (e, a) in
                               enumerate(zip(expected_seq, actual_seq))
                               if e == a)
        return correct_positions / len(expected_seq)

    def calculate_error_recovery_rate(self, error_scenarios, recovery_actions):
        """
        错误恢复成功率
        权重: 15%
        """
        successful = sum(1 for scenario, action in
                        zip(error_scenarios, recovery_actions)
                        if self._is_valid_recovery(scenario, action))
        return successful / len(error_scenarios) if error_scenarios else 1.0

    def calculate_response_time(self, response_times, threshold_ms=2000):
        """
        响应时间达标率
        权重: 10%
        """
        within_threshold = sum(1 for t in response_times if t < threshold_ms)
        return within_threshold / len(response_times) if response_times else 0

    def calculate_context_retention(self, conversation_turns):
        """
        上下文保持率
        权重: 15%
        """
        retained = sum(1 for turn in conversation_turns
                      if turn['context_preserved'] == True)
        return retained / len(conversation_turns) if conversation_turns else 0

    def calculate_compliance_score(self, constraint_checks):
        """
        约束遵守率
        权重: 10%
        """
        passed = sum(1 for check in constraint_checks if check['passed'])
        return passed / len(constraint_checks) if constraint_checks else 0

    def calculate_weighted_score(self, metrics_dict):
        """
        加权综合得分
        """
        weights = {
            'tool_accuracy': 0.25,
            'param_accuracy': 0.20,
            'sequence_accuracy': 0.15,
            'error_recovery': 0.15,
            'response_time': 0.10,
            'context_retention': 0.15,
            'compliance': 0.10
        }

        total_score = sum(metrics_dict[k] * weights[k]
                         for k in weights.keys())
        return total_score * 100  # 转换为百分制
```

### 5.2 评分标准

| 指标 | 优秀 (90-100) | 良好 (70-89) | 一般 (50-69) | 较差 (<50) |
|------|---------------|--------------|--------------|------------|
| 工具准确率 | ≥95% | 80-94% | 60-79% | <60% |
| 参数准确率 | ≥90% | 75-89% | 60-74% | <60% |
| 调用顺序 | 100%正确 | 90%+正确 | 70%+正确 | <70% |
| 错误恢复 | 全部成功 | 80%+成功 | 60%+成功 | <60% |
| 响应时间 | <1s | 1-2s | 2-3s | >3s |
| 上下文保持 | 100%保持 | 90%+保持 | 70%+保持 | <70% |
| 约束遵守 | 100%遵守 | 90%+遵守 | 80%+遵守 | <80% |

---

## 6. 执行流程与工具链

### 6.1 测试执行流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          测试执行流程                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │ 1. 环境准备 │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│  │ 2. Mock API │────▶│ 3. 执行测试 │────▶│ 4. 结果收集 │                  │
│  │    配置     │     │    用例     │     │    存储     │                  │
│  └─────────────┘     └──────┬──────┘     └──────┬──────┘                  │
│                             │                    │                          │
│                             ▼                    ▼                          │
│                      ┌─────────────┐     ┌─────────────┐                  │
│                      │ 5. 自动评估 │────▶│ 6. 人工复核 │                  │
│                      │    计算     │     │    抽样     │                  │
│                      └──────┬──────┘     └──────┬──────┘                  │
│                             │                    │                          │
│                             ▼                    ▼                          │
│                      ┌─────────────┐     ┌─────────────┐                  │
│                      │ 7. 报告生成 │────▶│ 8. 结果发布 │                  │
│                      │    输出     │     │    归档     │                  │
│                      └─────────────┘     └─────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 测试工具链

```yaml
# 测试基础设施配置

infrastructure:
  mock_server:
    name: "WireMock / MockServer"
    purpose: "模拟高德API响应"
    features:
      - 固定响应配置
      - 延迟注入
      - 错误注入
      - 请求验证

  test_runner:
    name: "pytest + pytest-asyncio"
    purpose: "测试执行与并发控制"
    features:
      - 异步测试支持
      - 并发测试执行
      - 测试夹具管理
      - 参数化测试

  assertion_lib:
    name: "自定义断言库"
    purpose: "功能调用验证"
    features:
      - 工具调用链验证
      - 参数深度比较
      - 顺序验证
      - 时间窗口验证

  metrics_collector:
    name: "Prometheus + Grafana"
    purpose: "性能指标收集"
    features:
      - 响应时间直方图
      - 调用成功率
      - 资源使用监控
      - 实时仪表板

  report_generator:
    name: "Allure Report"
    purpose: "测试报告生成"
    features:
      - 交互式报告
      - 历史趋势
      - 失败分析
      - 截图/日志附件
```

### 6.3 Mock API 配置示例

```python
# mock_amap_server.py

MOCK_RESPONSES = {
    "maps_geo": {
        "success": {
            "status": "1",
            "info": "OK",
            "geocodes": [{
                "location": "116.439192,40.027183",
                "formatted_address": "北京市朝阳区来广营",
                "province": "北京市",
                "city": "北京市",
                "district": "朝阳区",
                "adcode": "110105"
            }]
        },
        "error_not_found": {
            "status": "0",
            "info": "INVALID_KEY"
        }
    },
    "maps_direction_driving": {
        "success": {
            "status": "1",
            "route": {
                "origin": "116.439192,40.027183",
                "destination": "116.371135,40.064888",
                "distance": "11356",
                "paths": [{
                    "distance": "11356",
                    "duration": "1169",
                    "steps": []
                }]
            }
        }
    }
}

class MockAmapServer:
    """高德API模拟服务器"""

    def __init__(self, latency_ms=100, error_rate=0.0):
        self.latency_ms = latency_ms
        self.error_rate = error_rate
        self.call_log = []

    async def handle_request(self, endpoint, params):
        """处理模拟请求"""
        # 记录调用
        self.call_log.append({
            "endpoint": endpoint,
            "params": params,
            "timestamp": time.time()
        })

        # 模拟延迟
        await asyncio.sleep(self.latency_ms / 1000)

        # 随机错误注入
        if random.random() < self.error_rate:
            return {"status": "0", "info": "MOCK_ERROR"}

        # 返回模拟响应
        return MOCK_RESPONSES.get(endpoint, {}).get("success", {})
```

---

## 7. 结果分析框架

### 7.1 雷达图对比模板

```
                        工具识别 (D1)
                             ▲
                            /|\
                           / | \
                          /  |  \
                         /   |   \
                        /    |    \
                       /     |     \
                      /      |      \
     约束遵守 ◀─────/───────┼───────\─────▶ 参数提取 (D2)
     (D10)         /        |        \         (D10)
                  /         |         \
                 /          |          \
                /           |           \
               /            |            \
              /             |             \
             └──────────────┴──────────────┘
            /               |               \
           /                |                \
          /                 |                 \
         /                  |                  \
上下文保持 ◀────────────────┼────────────────▶ 结果整合 (D9)
  (D8)                      │                      (D9)
                            │
     错误恢复 ◀─────────────┼─────────────▶ 并行调用 (D7)
     (D6)                   │                   (D7)
                            │
     条件分支 ◀─────────────┴─────────────▶ 多工具编排 (D4)
     (D5)                                   (D5)

    ─── MiniCPM5-2B    ---- Kimi 2.5
```

### 7.2 统计分析方法

```python
# 统计分析框架

class StatisticalAnalysis:
    """结果统计分析"""

    def __init__(self, minicpm_results, kimi_results):
        self.minicpm = minicpm_results
        self.kimi = kimi_results

    def welch_t_test(self, metric_name):
        """
        Welch's t-test
        用于比较两个模型的均值差异
        H0: 两个模型在该指标上无显著差异
        """
        from scipy import stats

        t_stat, p_value = stats.ttest_ind(
            self.minicpm[metric_name],
            self.kimi[metric_name],
            equal_var=False  # 方差不齐
        )

        return {
            't_statistic': t_stat,
            'p_value': p_value,
            'significant': p_value < 0.05,
            'effect_size': self._cohens_d(metric_name)
        }

    def _cohens_d(self, metric_name):
        """
        Cohen's d 效应量
        0.2: 小效应
        0.5: 中等效应
        0.8: 大效应
        """
        import numpy as np

        mean_diff = (np.mean(self.minicpm[metric_name]) -
                    np.mean(self.kimi[metric_name]))
        pooled_std = np.sqrt(
            (np.std(self.minicpm[metric_name])**2 +
             np.std(self.kimi[metric_name])**2) / 2
        )

        return mean_diff / pooled_std if pooled_std > 0 else 0

    def bootstrap_confidence_interval(self, metric_name, n_bootstrap=1000):
        """
        Bootstrap置信区间
        用于估计差异的可靠性
        """
        import numpy as np

        diffs = []
        for _ in range(n_bootstrap):
            minicpm_sample = np.random.choice(
                self.minicpm[metric_name],
                size=len(self.minicpm[metric_name]),
                replace=True
            )
            kimi_sample = np.random.choice(
                self.kimi[metric_name],
                size=len(self.kimi[metric_name]),
                replace=True
            )
            diffs.append(np.mean(minicpm_sample) - np.mean(kimi_sample))

        return {
            'mean_diff': np.mean(diffs),
            'ci_lower': np.percentile(diffs, 2.5),
            'ci_upper': np.percentile(diffs, 97.5)
        }
```

### 7.3 决策矩阵

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        模型选择决策矩阵                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                        MiniCPM5-2B 更优                                    │
│                              ▲                                             │
│                              │                                             │
│                              │                                             │
│     资源受限 ────────────────┼──────────────── 高精度需求                  │
│     (端侧部署)               │                (云端服务)                   │
│                              │                                             │
│                              │                                             │
│                              │                                             │
│                              ▼                                             │
│                        Kimi 2.5 更优                                       │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  维度          │ MiniCPM5-2B 优势      │ Kimi 2.5 优势                    │
├────────────────────────────────────────────────────────────────────────────┤
│  工具识别      │ 轻量级场景更高效       │ 复杂工具链更准确                  │
│  参数提取      │ 基础参数足够           │ 多参数/嵌套参数更稳定              │
│  多工具编排    │ 3-4工具链表现良好      │ 5+工具链更可靠                    │
│  错误恢复      │ 简单降级策略           │ 复杂恢复策略更灵活                │
│  上下文保持    │ 短对话(3轮内)          │ 长对话(5轮+)更稳定                │
│  响应速度      │ 更快(端侧推理)        │ 略慢(但更准确)                   │
│  资源消耗      │ 更低(适合部署)        │ 更高(需要GPU)                    │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 生产部署建议

### 8.1 模型选择策略

```python
class ModelSelector:
    """基于场景的模型选择器"""

    def __init__(self, minicpm_model, kimi_model):
        self.minicpm = minicpm_model
        self.kimi = kimi_model

    def select_model(self, request_context):
        """
        根据请求上下文选择最优模型

        决策因素:
        1. 工具调用复杂度
        2. 对话轮次
        3. 延迟要求
        4. 资源限制
        """

        # 计算复杂度得分
        complexity_score = self._calculate_complexity(request_context)

        # 决策逻辑
        if complexity_score < 0.3:
            # 简单场景: 使用MiniCPM (更快、更省资源)
            return self.minicpm
        elif complexity_score > 0.7:
            # 复杂场景: 使用Kimi (更准确)
            return self.kimi
        else:
            # 中等场景: 基于延迟要求选择
            if request_context.get('latency_sensitive', False):
                return self.minicpm
            else:
                return self.kimi

    def _calculate_complexity(self, context):
        """
        计算请求复杂度 (0-1)
        """
        factors = {
            'tool_count': min(context.get('expected_tools', 1) / 7, 1),
            'turn_count': min(context.get('dialogue_turns', 1) / 5, 1),
            'has_error_handling': 0.2 if context.get('error_prone') else 0,
            'has_parallel': 0.1 if context.get('parallelizable') else 0,
            'context_length': min(len(str(context)) / 1000, 1)
        }

        weights = {
            'tool_count': 0.3,
            'turn_count': 0.25,
            'has_error_handling': 0.2,
            'has_parallel': 0.1,
            'context_length': 0.15
        }

        return sum(factors[k] * weights[k] for k in factors)
```

### 8.2 混合部署架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        混合部署架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        请求路由层                                    │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │   │
│  │  │ 复杂度评估  │───▶│ 模型选择    │───▶│ 负载均衡    │            │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘            │   │
│  └───────────────────────────┬─────────────────────────────────────────┘   │
│                              │                                              │
│         ┌────────────────────┼────────────────────┐                       │
│         │                    │                    │                         │
│         ▼                    ▼                    ▼                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │  MiniCPM5   │    │   Kimi 2.5  │    │   降级模型   │                    │
│  │  (轻量级)   │    │  (高性能)   │    │  (备用)     │                    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│         │                  │                   │                           │
│         └──────────────────┼───────────────────┘                           │
│                            │                                               │
│                            ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        结果后处理层                                  │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │   │
│  │  │ 结果验证    │───▶│ 格式统一    │───▶│ 缓存存储    │            │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 监控与告警

```yaml
# 监控配置

monitoring:
  metrics:
    - name: "tool_call_accuracy"
      type: "gauge"
      threshold: 0.85
      alert: "warning"

    - name: "response_latency_p99"
      type: "histogram"
      threshold_ms: 3000
      alert: "critical"

    - name: "error_rate"
      type: "counter"
      threshold: 0.05
      alert: "critical"

    - name: "model_switch_rate"
      type: "gauge"
      threshold: 0.3
      alert: "info"

  dashboards:
    - name: "Function Calling Overview"
      panels:
        - "工具调用成功率趋势"
        - "模型切换频率"
        - "响应时间分布"
        - "错误类型统计"

    - name: "Model Comparison"
      panels:
        - "MiniCPM vs Kimi 准确率对比"
        - "场景分布热力图"
        - "资源使用对比"
```

---

## 附录 A: 测试环境要求

```yaml
# 环境配置

environment:
  python: "3.10+"
  dependencies:
    - "pytest>=7.0"
    - "pytest-asyncio>=0.21"
    - "httpx>=0.24"
    - "pydantic>=2.0"
    - "scipy>=1.10"

  api_keys:
    - name: "minicpm_api_key"
      env: "MINICPM_API_KEY"
    - name: "kimi_api_key"
      env: "KIMI_API_KEY"

  mock_server:
    port: 8080
    latency_ms: 100
    error_rate: 0.0

  test_data:
    cities: ["北京", "上海", "广州", "深圳"]
    participants_range: [2, 5]
    cuisine_types: ["日料", "火锅", "烤肉", "川菜"]
```

---

## 附录 B: 预期输出模板

```markdown
# 功能调用能力对比测试报告

## 测试概要
- 测试时间: YYYY-MM-DD
- 测试用例数: 10
- 总执行次数: 200 (每个模型100次)

## 核心指标对比

| 指标 | MiniCPM5-2B | Kimi 2.5 | 差异 | 显著性 |
|------|-------------|----------|------|--------|
| 工具准确率 | XX.X% | XX.X% | +X.X% | p=0.XXX |
| 参数准确率 | XX.X% | XX.X% | +X.X% | p=0.XXX |
| 调用顺序 | XX.X% | XX.X% | +X.X% | p=0.XXX |
| 错误恢复 | XX.X% | XX.X% | +X.X% | p=0.XXX |
| 平均响应时间 | XXXms | XXXms | +XXms | - |

## 场景分析

### 简单场景 (工具数≤3)
- MiniCPM5-2B: 更快，资源消耗更低
- Kimi 2.5: 准确率略高

### 复杂场景 (工具数≥5)
- MiniCPM5-2B: 编排能力下降明显
- Kimi 2.5: 保持稳定表现

## 推荐部署策略
1. 简单查询: MiniCPM5-2B (低延迟、低成本)
2. 复杂推荐: Kimi 2.5 (高准确、高可靠)
3. 混合场景: 路由层动态选择

## 风险提示
- Kimi 2.5 在低延迟场景可能不适用
- MiniCPM5-2B 在长上下文场景需验证
```

---

## 附录 C: 参考文献

1. Anthropic. (2024). Tool Use Best Practices.
2. Amap Open Platform. (2024). MCP API Documentation.
3. OpenAI. (2023). Function Calling Guide.
4. 高德开放平台. (2024). 地理编码与路径规划 API 指南.

---

**文档维护者**: Claude Code
**最后更新**: 2024-09-05
**版本**: 1.0.0
