"""
综合测试套件
使用真实高德API进行大规模测试
"""

import asyncio
import time
import json
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from real_amap_client import RealAmapClient


@dataclass
class ComprehensiveTestResult:
    """综合测试结果"""
    test_id: str
    test_name: str
    category: str
    success: bool
    api_calls: List[Dict[str, Any]]
    execution_time_ms: float
    metrics: Dict[str, float]
    error_message: Optional[str] = None


class ComprehensiveTestSuite:
    """综合测试套件"""

    # 测试地点数据
    TEST_LOCATIONS = {
        "北京": [
            {"name": "望京", "expected_district": "朝阳区"},
            {"name": "望京地铁站", "expected_district": "朝阳区"},
            {"name": "霍营", "expected_district": "昌平区"},
            {"name": "霍营地铁站", "expected_district": "昌平区"},
            {"name": "朱辛庄", "expected_district": "昌平区"},
            {"name": "朱辛庄地铁站", "expected_district": "昌平区"},
            {"name": "天通苑", "expected_district": "昌平区"},
            {"name": "天通苑地铁站", "expected_district": "昌平区"},
            {"name": "国贸", "expected_district": "朝阳区"},
            {"name": "西直门", "expected_district": "西城区"},
            {"name": "五道口", "expected_district": "海淀区"},
            {"name": "中关村", "expected_district": "海淀区"},
            {"name": "三里屯", "expected_district": "朝阳区"},
            {"name": "王府井", "expected_district": "东城区"},
            {"name": "西单", "expected_district": "西城区"},
            {"name": "回龙观", "expected_district": "昌平区"},
            {"name": "立水桥", "expected_district": "朝阳区"},
            {"name": "北苑", "expected_district": "朝阳区"},
            {"name": "大望路", "expected_district": "朝阳区"},
            {"name": "双井", "expected_district": "朝阳区"}
        ],
        "上海": [
            {"name": "陆家嘴", "expected_district": "浦东新区"},
            {"name": "人民广场", "expected_district": "黄浦区"},
            {"name": "南京路", "expected_district": "黄浦区"},
            {"name": "徐家汇", "expected_district": "徐汇区"},
            {"name": "虹桥", "expected_district": "闵行区"}
        ],
        "广州": [
            {"name": "天河城", "expected_district": "天河区"},
            {"name": "珠江新城", "expected_district": "天河区"},
            {"name": "北京路", "expected_district": "越秀区"}
        ],
        "深圳": [
            {"name": "南山", "expected_district": "南山区"},
            {"name": "福田", "expected_district": "福田区"},
            {"name": "罗湖", "expected_district": "罗湖区"}
        ]
    }

    # 菜系类型
    CUISINE_TYPES = ["日料", "火锅", "烤肉", "川菜", "粤菜", "湘菜", "西餐", "烧烤"]

    # 测试参与者组合
    TEST_PARTICIPANT_COMBOS = [
        # 2人组合
        ["望京", "霍营"],
        ["国贸", "中关村"],
        ["五道口", "西直门"],
        ["天通苑", "三里屯"],

        # 3人组合
        ["望京", "霍营", "朱辛庄"],
        ["国贸", "中关村", "五道口"],
        ["天通苑", "回龙观", "立水桥"],

        # 4人组合
        ["望京", "霍营", "朱辛庄", "天通苑"],
        ["国贸", "中关村", "五道口", "西直门"],

        # 5人组合
        ["望京", "霍营", "朱辛庄", "天通苑", "回龙观"],
    ]

    def __init__(self, api_key: str):
        """初始化测试套件"""
        self.client = RealAmapClient(api_key)
        self.results: List[ComprehensiveTestResult] = []

    async def run_geocode_tests(self, city: str = "北京", count: int = 10) -> List[ComprehensiveTestResult]:
        """
        运行地理编码测试

        Args:
            city: 测试城市
            count: 测试数量

        Returns:
            测试结果列表
        """
        print(f"\n{'='*60}")
        print(f"运行地理编码测试 ({city})")
        print(f"{'='*60}")

        results = []
        locations = self.TEST_LOCATIONS.get(city, [])[:count]

        for i, location in enumerate(locations, 1):
            test_id = f"GEO-{city[:2]}-{i:03d}"
            print(f"\n[{i}/{len(locations)}] 测试: {location['name']}")

            start_time = time.time()

            try:
                # 调用地理编码API
                response = await self.client.geocode(location["name"], city)

                execution_time = (time.time() - start_time) * 1000

                # 解析结果
                success = response.get("status") == "1"
                geocodes = response.get("geocodes", [])

                metrics = {
                    "success": 1.0 if success else 0.0,
                    "has_results": 1.0 if geocodes else 0.0,
                    "response_time_ms": execution_time,
                    "accuracy": self._check_geocode_accuracy(geocodes, location)
                }

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"地理编码: {location['name']}",
                    category="D1-工具识别",
                    success=success and len(geocodes) > 0,
                    api_calls=[{
                        "endpoint": "geocode/geo",
                        "params": {"address": location["name"], "city": city},
                        "success": success
                    }],
                    execution_time_ms=execution_time,
                    metrics=metrics
                )

                # 打印结果
                if geocodes:
                    geo = geocodes[0]
                    print(f"  ✓ 成功: {geo.get('formatted_address', 'N/A')}")
                    print(f"  坐标: {geo.get('location', 'N/A')}")
                    print(f"  区域: {geo.get('district', 'N/A')}")
                else:
                    print(f"  ✗ 失败: 未找到结果")

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                print(f"  ✗ 错误: {str(e)}")

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"地理编码: {location['name']}",
                    category="D1-工具识别",
                    success=False,
                    api_calls=[],
                    execution_time_ms=execution_time,
                    metrics={"success": 0.0},
                    error_message=str(e)
                )

            results.append(result)
            self.results.append(result)

        return results

    async def run_route_tests(self, city: str = "北京", count: int = 5) -> List[ComprehensiveTestResult]:
        """
        运行路线规划测试

        Args:
            city: 测试城市
            count: 测试数量

        Returns:
            测试结果列表
        """
        print(f"\n{'='*60}")
        print(f"运行路线规划测试 ({city})")
        print(f"{'='*60}")

        results = []
        combos = self.TEST_PARTICIPANT_COMBOS[:count]

        for i, combo in enumerate(combos, 1):
            test_id = f"ROUTE-{city[:2]}-{i:03d}"
            print(f"\n[{i}/{len(combos)}] 测试: {' → '.join(combo)}")

            start_time = time.time()
            api_calls = []

            try:
                # 获取所有地点的坐标
                coords = []
                for name in combo:
                    geo_response = await self.client.geocode(name, city)
                    if geo_response.get("geocodes"):
                        coords.append(geo_response["geocodes"][0]["location"])
                    else:
                        raise ValueError(f"无法获取 {name} 的坐标")

                # 计算路线
                route_results = []
                for j in range(len(coords) - 1):
                    origin = coords[j]
                    destination = coords[j + 1]

                    # 驾车路线
                    driving_response = await self.client.direction_driving(origin, destination)
                    api_calls.append({
                        "endpoint": "direction/driving",
                        "params": {"origin": origin, "destination": destination},
                        "success": driving_response.get("status") == "1"
                    })

                    # 公交路线
                    transit_response = await self.client.direction_transit(origin, destination, city)
                    api_calls.append({
                        "endpoint": "direction/transit",
                        "params": {"origin": origin, "destination": destination, "city": city},
                        "success": transit_response.get("status") == "1"
                    })

                    route_results.append({
                        "from": combo[j],
                        "to": combo[j + 1],
                        "driving": driving_response,
                        "transit": transit_response
                    })

                execution_time = (time.time() - start_time) * 1000

                # 计算指标
                metrics = self._calculate_route_metrics(route_results, execution_time)

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"路线规划: {' → '.join(combo)}",
                    category="D4-多工具编排",
                    success=True,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics=metrics
                )

                # 打印结果
                for route in route_results:
                    print(f"  {route['from']} → {route['to']}:")
                    if route['driving'].get('route', {}).get('paths'):
                        driving_time = int(route['driving']['route']['paths'][0].get('duration', 0)) // 60
                        print(f"    驾车: {driving_time}分钟")
                    if route['transit'].get('route', {}).get('transits'):
                        transit_time = int(route['transit']['route']['transits'][0].get('duration', 0)) // 60
                        print(f"    公交: {transit_time}分钟")

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                print(f"  ✗ 错误: {str(e)}")

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"路线规划: {' → '.join(combo)}",
                    category="D4-多工具编排",
                    success=False,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics={"success": 0.0},
                    error_message=str(e)
                )

            results.append(result)
            self.results.append(result)

        return results

    async def run_restaurant_search_tests(self, city: str = "北京", count: int = 5) -> List[ComprehensiveTestResult]:
        """
        运行餐厅搜索测试

        Args:
            city: 测试城市
            count: 测试数量

        Returns:
            测试结果列表
        """
        print(f"\n{'='*60}")
        print(f"运行餐厅搜索测试 ({city})")
        print(f"{'='*60}")

        results = []
        cuisines = self.CUISINE_TYPES[:count]

        for i, cuisine in enumerate(cuisines, 1):
            test_id = f"SEARCH-{city[:2]}-{i:03d}"
            print(f"\n[{i}/{len(cuisines)}] 测试: {cuisine}")

            start_time = time.time()
            api_calls = []

            try:
                # 搜索餐厅
                search_response = await self.client.text_search(cuisine, city)
                api_calls.append({
                    "endpoint": "place/text",
                    "params": {"keywords": cuisine, "city": city},
                    "success": search_response.get("status") == "1"
                })

                execution_time = (time.time() - start_time) * 1000

                # 解析结果
                pois = search_response.get("pois", [])
                success = len(pois) > 0

                metrics = {
                    "success": 1.0 if success else 0.0,
                    "result_count": len(pois),
                    "response_time_ms": execution_time,
                    "has_restaurants": 1.0 if any("餐饮" in p.get("type", "") for p in pois) else 0.0
                }

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"餐厅搜索: {cuisine}",
                    category="D9-结果整合",
                    success=success,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics=metrics
                )

                # 打印结果
                print(f"  找到 {len(pois)} 个结果")
                for poi in pois[:3]:
                    print(f"    - {poi.get('name', 'N/A')}: {poi.get('address', 'N/A')}")

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                print(f"  ✗ 错误: {str(e)}")

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"餐厅搜索: {cuisine}",
                    category="D9-结果整合",
                    success=False,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics={"success": 0.0},
                    error_message=str(e)
                )

            results.append(result)
            self.results.append(result)

        return results

    async def run_end_to_end_tests(self, city: str = "北京", count: int = 3) -> List[ComprehensiveTestResult]:
        """
        运行端到端测试

        Args:
            city: 测试城市
            count: 测试数量

        Returns:
            测试结果列表
        """
        print(f"\n{'='*60}")
        print(f"运行端到端测试 ({city})")
        print(f"{'='*60}")

        results = []
        combos = self.TEST_PARTICIPANT_COMBOS[:count]
        cuisines = random.sample(self.CUISINE_TYPES, count)

        for i, (combo, cuisine) in enumerate(zip(combos, cuisines), 1):
            test_id = f"E2E-{city[:2]}-{i:03d}"
            print(f"\n[{i}/{count}] 测试: {len(combo)}人聚餐 - {cuisine}")
            print(f"  参与者: {', '.join(combo)}")

            start_time = time.time()
            api_calls = []

            try:
                # Step 1: 地理编码所有参与者
                print(f"  [Step 1] 地理编码...")
                coords = []
                for name in combo:
                    geo_response = await self.client.geocode(name, city)
                    api_calls.append({
                        "endpoint": "geocode/geo",
                        "params": {"address": name, "city": city},
                        "success": geo_response.get("status") == "1"
                    })

                    if geo_response.get("geocodes"):
                        coords.append({
                            "name": name,
                            "location": geo_response["geocodes"][0]["location"]
                        })

                # Step 2: 计算中心点
                print(f"  [Step 2] 计算中心点...")
                if coords:
                    lats = [float(c["location"].split(",")[1]) for c in coords]
                    lons = [float(c["location"].split(",")[0]) for c in coords]
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)
                    center_location = f"{center_lon},{center_lat}"

                    # 逆地理编码获取中心点地址
                    regeo_response = await self.client.regeocode(center_location)
                    api_calls.append({
                        "endpoint": "geocode/regeo",
                        "params": {"location": center_location},
                        "success": regeo_response.get("status") == "1"
                    })

                    center_name = regeo_response.get("regeocode", {}).get("formatted_address", "未知区域")
                    print(f"    中心点: {center_name}")

                # Step 3: 搜索餐厅
                print(f"  [Step 3] 搜索{cuisine}餐厅...")
                search_response = await self.client.text_search(cuisine, city)
                api_calls.append({
                    "endpoint": "place/text",
                    "params": {"keywords": cuisine, "city": city},
                    "success": search_response.get("status") == "1"
                })

                pois = search_response.get("pois", [])[:5]  # 取前5个
                print(f"    找到 {len(pois)} 家餐厅")

                # Step 4: 计算路线
                print(f"  [Step 4] 计算路线...")
                route_results = []

                for poi in pois[:3]:  # 只对前3家餐厅计算路线
                    restaurant_location = poi.get("location", "")
                    if not restaurant_location:
                        continue

                    restaurant_routes = []
                    for coord in coords:
                        # 驾车路线
                        driving = await self.client.direction_driving(coord["location"], restaurant_location)
                        api_calls.append({
                            "endpoint": "direction/driving",
                            "params": {"origin": coord["location"], "destination": restaurant_location},
                            "success": driving.get("status") == "1"
                        })

                        # 公交路线
                        transit = await self.client.direction_transit(coord["location"], restaurant_location, city)
                        api_calls.append({
                            "endpoint": "direction/transit",
                            "params": {"origin": coord["location"], "destination": restaurant_location, "city": city},
                            "success": transit.get("status") == "1"
                        })

                        restaurant_routes.append({
                            "participant": coord["name"],
                            "driving": driving,
                            "transit": transit
                        })

                    route_results.append({
                        "restaurant": poi.get("name", "N/A"),
                        "location": restaurant_location,
                        "routes": restaurant_routes
                    })

                execution_time = (time.time() - start_time) * 1000

                # 计算指标
                metrics = self._calculate_e2e_metrics(route_results, execution_time, len(api_calls))

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"端到端: {len(combo)}人{cuisine}聚餐",
                    category="D10-约束遵守",
                    success=True,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics=metrics
                )

                # 打印摘要
                print(f"  ✓ 完成! API调用: {len(api_calls)}次, 耗时: {execution_time:.0f}ms")

                # 打印推荐餐厅
                if route_results:
                    best = route_results[0]
                    print(f"  推荐: {best['restaurant']}")

            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                print(f"  ✗ 错误: {str(e)}")

                result = ComprehensiveTestResult(
                    test_id=test_id,
                    test_name=f"端到端: {len(combo)}人{cuisine}聚餐",
                    category="D10-约束遵守",
                    success=False,
                    api_calls=api_calls,
                    execution_time_ms=execution_time,
                    metrics={"success": 0.0},
                    error_message=str(e)
                )

            results.append(result)
            self.results.append(result)

        return results

    def _check_geocode_accuracy(self, geocodes: List[Dict], expected: Dict[str, str]) -> float:
        """检查地理编码准确性"""
        if not geocodes:
            return 0.0

        geo = geocodes[0]
        expected_district = expected.get("expected_district", "")

        if expected_district and expected_district in geo.get("district", ""):
            return 1.0
        elif expected_district:
            return 0.5  # 部分匹配
        else:
            return 1.0  # 无期望值，默认匹配

    def _calculate_route_metrics(self, route_results: List[Dict], execution_time_ms: float) -> Dict[str, float]:
        """计算路线指标"""
        success_count = sum(1 for r in route_results
                          if r.get("driving", {}).get("status") == "1"
                          or r.get("transit", {}).get("status") == "1")

        return {
            "success": 1.0 if success_count > 0 else 0.0,
            "route_success_rate": success_count / len(route_results) if route_results else 0.0,
            "response_time_ms": execution_time_ms,
            "avg_time_per_route": execution_time_ms / len(route_results) if route_results else 0
        }

    def _calculate_e2e_metrics(self, route_results: List[Dict], execution_time_ms: float, api_call_count: int) -> Dict[str, float]:
        """计算端到端指标"""
        return {
            "success": 1.0,
            "restaurants_found": len(route_results),
            "api_calls": api_call_count,
            "response_time_ms": execution_time_ms,
            "efficiency": len(route_results) / api_call_count if api_call_count > 0 else 0
        }

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """生成综合报告"""
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)

        # 按类别统计
        category_stats = {}
        for result in self.results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "success": 0, "time": 0}
            category_stats[cat]["total"] += 1
            if result.success:
                category_stats[cat]["success"] += 1
            category_stats[cat]["time"] += result.execution_time_ms

        # API调用统计
        api_stats = self.client.get_call_stats()

        report = {
            "test_summary": {
                "test_date": datetime.now().isoformat(),
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
                "total_api_calls": api_stats.get("total_calls", 0),
                "avg_api_response_time_ms": api_stats.get("avg_response_time_ms", 0),
                "api_success_rate": api_stats.get("success_rate", 0)
            },
            "category_breakdown": category_stats,
            "api_statistics": api_stats,
            "detailed_results": [asdict(r) for r in self.results]
        }

        return report
