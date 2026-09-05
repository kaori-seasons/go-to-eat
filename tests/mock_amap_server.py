"""
高德地图API模拟服务器
用于测试功能调用能力，无需真实API Key
"""

import asyncio
import time
import random
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class APICallRecord:
    """API调用记录"""
    endpoint: str
    params: Dict[str, Any]
    timestamp: float
    response_time_ms: float = 0
    success: bool = True


class MockAmapServer:
    """高德API模拟服务器"""

    # 模拟地理编码数据库
    GEO_DATABASE = {
        "望京": {
            "location": "116.481028,40.004375",
            "formatted_address": "北京市朝阳区望京",
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "adcode": "110105",
            "level": "商圈"
        },
        "望京地铁站": {
            "location": "116.479818,40.004141",
            "formatted_address": "北京市朝阳区望京地铁站",
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "adcode": "110105",
            "level": "地铁站"
        },
        "霍营": {
            "location": "116.368207,40.076214",
            "formatted_address": "北京市昌平区霍营",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "地名"
        },
        "霍营地铁站": {
            "location": "116.367428,40.075547",
            "formatted_address": "北京市昌平区霍营地铁站",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "地铁站"
        },
        "朱辛庄": {
            "location": "116.306005,40.091268",
            "formatted_address": "北京市昌平区朱辛庄",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "地名"
        },
        "朱辛庄地铁站": {
            "location": "116.305269,40.090848",
            "formatted_address": "北京市昌平区朱辛庄地铁站",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "地铁站"
        },
        "天通苑": {
            "location": "116.418762,40.075547",
            "formatted_address": "北京市昌平区天通苑",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "居住区"
        },
        "天通苑地铁站": {
            "location": "116.417893,40.076019",
            "formatted_address": "北京市昌平区天通苑地铁站",
            "province": "北京市",
            "city": "北京市",
            "district": "昌平区",
            "adcode": "110114",
            "level": "地铁站"
        },
        "国贸": {
            "location": "116.460526,39.908372",
            "formatted_address": "北京市朝阳区国贸",
            "province": "北京市",
            "city": "北京市",
            "district": "朝阳区",
            "adcode": "110105",
            "level": "商圈"
        },
        "西直门": {
            "location": "116.356878,39.940728",
            "formatted_address": "北京市西城区西直门",
            "province": "北京市",
            "city": "北京市",
            "district": "西城区",
            "adcode": "110102",
            "level": "地名"
        },
        "五道口": {
            "location": "116.339301,39.992956",
            "formatted_address": "北京市海淀区五道口",
            "province": "北京市",
            "city": "北京市",
            "district": "海淀区",
            "adcode": "110108",
            "level": "商圈"
        },
    }

    # 模拟餐厅数据库
    RESTAURANT_DATABASE = {
        "日料": [
            {
                "id": "REST001",
                "name": "�的场日本料理",
                "location": "116.412000,39.980000",
                "address": "北京市朝阳区工体北路8号",
                "city": "北京市",
                "cost": "258.00",
                "rating": "4.8",
                "open_time": "11:00-22:00",
                "type": "日本料理"
            },
            {
                "id": "REST002",
                "name": "�的寿司",
                "location": "116.425000,39.975000",
                "address": "北京市朝阳区三里屯路19号",
                "city": "北京市",
                "cost": "198.00",
                "rating": "4.6",
                "open_time": "11:30-21:30",
                "type": "日本料理"
            },
            {
                "id": "REST003",
                "name": "樱花日本料理",
                "location": "116.435000,39.968000",
                "address": "北京市朝阳区亮马桥路50号",
                "city": "北京市",
                "cost": "320.00",
                "rating": "4.9",
                "open_time": "17:00-23:00",
                "type": "日本料理"
            }
        ],
        "火锅": [
            {
                "id": "REST010",
                "name": "海底捞(望京店)",
                "location": "116.482000,40.005000",
                "address": "北京市朝阳区望京西路8号",
                "city": "北京市",
                "cost": "150.00",
                "rating": "4.7",
                "open_time": "10:00-02:00",
                "type": "火锅"
            },
            {
                "id": "REST011",
                "name": "呷哺呷哺(霍营店)",
                "location": "116.369000,40.077000",
                "address": "北京市昌平区回龙观东大街20号",
                "city": "北京市",
                "cost": "85.00",
                "rating": "4.5",
                "open_time": "10:30-22:00",
                "type": "火锅"
            },
            {
                "id": "REST012",
                "name": "小龙坎(西直门店)",
                "location": "116.357000,39.941000",
                "address": "北京市西城区西直门外大街1号",
                "city": "北京市",
                "cost": "120.00",
                "rating": "4.6",
                "open_time": "11:00-02:00",
                "type": "火锅"
            }
        ],
        "烤肉": [
            {
                "id": "REST020",
                "name": "权金城(五道口店)",
                "location": "116.340000,39.993000",
                "address": "北京市海淀区成府路28号",
                "city": "北京市",
                "cost": "138.00",
                "rating": "4.4",
                "open_time": "11:00-23:00",
                "type": "烤肉"
            },
            {
                "id": "REST021",
                "name": "汉拿山(国贸店)",
                "location": "116.461000,39.909000",
                "address": "北京市朝阳区建国门外大街1号",
                "city": "北京市",
                "cost": "168.00",
                "rating": "4.5",
                "open_time": "11:00-22:00",
                "type": "烤肉"
            }
        ]
    }

    def __init__(self, latency_ms: int = 100, error_rate: float = 0.0):
        """
        初始化模拟服务器

        Args:
            latency_ms: 模拟延迟(毫秒)
            error_rate: 错误注入率(0-1)
        """
        self.latency_ms = latency_ms
        self.error_rate = error_rate
        self.call_log: list[APICallRecord] = []
        self._call_count = 0

    async def handle_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理模拟API请求

        Args:
            endpoint: API端点名称
            params: 请求参数

        Returns:
            模拟API响应
        """
        start_time = time.time()
        self._call_count += 1

        # 记录调用
        record = APICallRecord(
            endpoint=endpoint,
            params=params.copy(),
            timestamp=start_time
        )

        # 模拟延迟
        await asyncio.sleep(self.latency_ms / 1000)

        # 随机错误注入
        if random.random() < self.error_rate:
            response = {"status": "0", "info": "MOCK_ERROR", "infocode": "10001"}
            record.success = False
        else:
            # 根据端点返回模拟响应
            handler = getattr(self, f"_handle_{endpoint}", None)
            if handler:
                response = handler(params)
            else:
                response = {"status": "0", "info": "UNKNOWN_ENDPOINT"}

        # 记录响应时间
        record.response_time_ms = (time.time() - start_time) * 1000
        self.call_log.append(record)

        return response

    def _handle_maps_geo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理地理编码请求"""
        address = params.get("address", "")

        # 尝试从数据库查找
        if address in self.GEO_DATABASE:
            geo_data = self.GEO_DATABASE[address]
            return {
                "status": "1",
                "info": "OK",
                "infocode": "10000",
                "geocodes": [geo_data]
            }

        # 模糊匹配
        for key, value in self.GEO_DATABASE.items():
            if address in key or key in address:
                return {
                    "status": "1",
                    "info": "OK",
                    "infocode": "10000",
                    "geocodes": [value]
                }

        # 未找到
        return {
            "status": "0",
            "info": "FAIL",
            "infocode": "10003",
            "geocodes": []
        }

    def _handle_maps_regeocode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理逆地理编码请求"""
        location = params.get("location", "")

        # 简单模拟：返回一个通用地址
        return {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "regeocode": {
                "formatted_address": "北京市朝阳区",
                "addressComponent": {
                    "province": "北京市",
                    "city": "北京市",
                    "district": "朝阳区"
                }
            }
        }

    def _handle_maps_direction_driving(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理驾车路线规划"""
        origin = params.get("origin", "")
        destination = params.get("destination", "")

        # 计算模拟距离和时间
        try:
            o_lon, o_lat = map(float, origin.split(","))
            d_lon, d_lat = map(float, destination.split(","))
            distance_km = ((d_lon - o_lon)**2 + (d_lat - o_lat)**2)**0.5 * 111
            duration_min = distance_km * 2.5 + random.uniform(5, 15)  # 模拟驾驶时间
        except:
            distance_km = 10
            duration_min = 25

        return {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "route": {
                "origin": origin,
                "destination": destination,
                "distance": str(int(distance_km * 1000)),
                "paths": [{
                    "distance": str(int(distance_km * 1000)),
                    "duration": str(int(duration_min * 60)),
                    "steps": []
                }]
            }
        }

    def _handle_maps_direction_transit_integrated(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理公交/地铁路线规划"""
        origin = params.get("origin", "")
        destination = params.get("destination", "")

        try:
            o_lon, o_lat = map(float, origin.split(","))
            d_lon, d_lat = map(float, destination.split(","))
            distance_km = ((d_lon - o_lon)**2 + (d_lat - o_lat)**2)**0.5 * 111
            duration_min = distance_km * 3 + random.uniform(10, 20)  # 模拟公交时间
        except:
            distance_km = 10
            duration_min = 40

        return {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "route": {
                "origin": origin,
                "destination": destination,
                "distance": str(int(distance_km * 1000)),
                "transits": [{
                    "duration": str(int(duration_min * 60)),
                    "walking_distance": str(int(random.uniform(200, 800))),
                    "segments": []
                }]
            }
        }

    def _handle_maps_direction_bicycling(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理骑行路线规划"""
        origin = params.get("origin", "")
        destination = params.get("destination", "")

        try:
            o_lon, o_lat = map(float, origin.split(","))
            d_lon, d_lat = map(float, destination.split(","))
            distance_km = ((d_lon - o_lon)**2 + (d_lat - o_lat)**2)**0.5 * 111
            duration_min = distance_km * 4 + random.uniform(5, 10)  # 模拟骑行时间
        except:
            distance_km = 5
            duration_min = 25

        return {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "route": {
                "origin": origin,
                "destination": destination,
                "distance": str(int(distance_km * 1000)),
                "duration": str(int(duration_min * 60))
            }
        }

    def _handle_maps_text_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理关键词搜索"""
        keywords = params.get("keywords", "")
        city = params.get("city", "北京")

        # 从餐厅数据库中搜索
        results = []
        for cuisine, restaurants in self.RESTAURANT_DATABASE.items():
            if keywords in cuisine or cuisine in keywords:
                results.extend(restaurants)

        # 如果没有匹配，返回空结果
        return {
            "status": "1",
            "info": "OK",
            "infocode": "10000",
            "pois": results,
            "count": str(len(results))
        }

    def _handle_maps_search_detail(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理餐厅详情查询"""
        poi_id = params.get("id", "")

        # 在数据库中查找
        for cuisine, restaurants in self.RESTAURANT_DATABASE.items():
            for restaurant in restaurants:
                if restaurant["id"] == poi_id:
                    return {
                        "status": "1",
                        "info": "OK",
                        "infocode": "10000",
                        "poi": restaurant
                    }

        return {
            "status": "0",
            "info": "FAIL",
            "infocode": "10004",
            "poi": None
        }

    def get_call_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        if not self.call_log:
            return {"total_calls": 0}

        endpoint_counts = {}
        for record in self.call_log:
            endpoint_counts[record.endpoint] = endpoint_counts.get(record.endpoint, 0) + 1

        avg_response_time = sum(r.response_time_ms for r in self.call_log) / len(self.call_log)

        return {
            "total_calls": len(self.call_log),
            "endpoint_counts": endpoint_counts,
            "avg_response_time_ms": avg_response_time,
            "success_rate": sum(1 for r in self.call_log if r.success) / len(self.call_log)
        }

    def reset(self):
        """重置服务器状态"""
        self.call_log.clear()
        self._call_count = 0
