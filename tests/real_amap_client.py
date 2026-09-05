"""
真实高德地图API客户端
使用真实的高德API进行测试
"""

import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import httpx


@dataclass
class APICallRecord:
    """API调用记录"""
    endpoint: str
    params: Dict[str, Any]
    timestamp: float
    response_time_ms: float = 0
    success: bool = True
    response_data: Optional[Dict[str, Any]] = None


class RealAmapClient:
    """真实高德API客户端"""

    BASE_URL = "https://restapi.amap.com/v3"

    # 支持的城市及其adcode
    SUPPORTED_CITIES = {
        "北京": "110000",
        "上海": "310000",
        "广州": "440100",
        "深圳": "440300",
        "厦门": "350200"
    }

    def __init__(self, api_key: str):
        """
        初始化客户端

        Args:
            api_key: 高德API密钥
        """
        self.api_key = api_key
        self.call_log: List[APICallRecord] = []

    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送API请求

        Args:
            endpoint: API端点
            params: 请求参数

        Returns:
            API响应
        """
        # 添加通用参数
        params["key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        start_time = time.time()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
            except httpx.HTTPStatusError as e:
                print(f"  API错误: {e.response.status_code}")
                result = {"status": "0", "info": "HTTP_ERROR"}
            except Exception as e:
                print(f"  请求错误: {str(e)}")
                result = {"status": "0", "info": str(e)}

        response_time = (time.time() - start_time) * 1000

        # 记录调用
        record = APICallRecord(
            endpoint=endpoint,
            params=params,
            timestamp=start_time,
            response_time_ms=response_time,
            success=result.get("status") == "1",
            response_data=result
        )
        self.call_log.append(record)

        return result

    async def geocode(self, address: str, city: str = "") -> Dict[str, Any]:
        """
        地理编码 - 将地址转换为坐标

        Args:
            address: 地址
            city: 城市

        Returns:
            包含坐标的响应
        """
        params = {"address": address}
        if city:
            params["city"] = city

        return await self._make_request("geocode/geo", params)

    async def regeocode(self, location: str) -> Dict[str, Any]:
        """
        逆地理编码 - 将坐标转换为地址

        Args:
            location: 坐标 (经度,纬度)

        Returns:
            包含地址的响应
        """
        params = {"location": location}
        return await self._make_request("geocode/regeo", params)

    async def direction_driving(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        驾车路线规划

        Args:
            origin: 起点坐标
            destination: 终点坐标

        Returns:
            路线规划结果
        """
        params = {
            "origin": origin,
            "destination": destination
        }
        return await self._make_request("direction/driving", params)

    async def direction_transit(self, origin: str, destination: str, city: str, cityd: str = "") -> Dict[str, Any]:
        """
        公交地铁路线规划

        Args:
            origin: 起点坐标
            destination: 终点坐标
            city: 出发城市
            cityd: 目的城市

        Returns:
            路线规划结果
        """
        if not cityd:
            cityd = city

        params = {
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": cityd
        }
        return await self._make_request("direction/transit/integrated", params)

    async def direction_bicycling(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        骑行路线规划

        Args:
            origin: 起点坐标
            destination: 终点坐标

        Returns:
            路线规划结果
        """
        params = {
            "origin": origin,
            "destination": destination
        }
        return await self._make_request("direction/bicycling", params)

    async def text_search(self, keywords: str, city: str, types: str = "餐饮") -> Dict[str, Any]:
        """
        关键词搜索

        Args:
            keywords: 搜索关键词
            city: 城市
            types: POI类型

        Returns:
            搜索结果
        """
        params = {
            "keywords": keywords,
            "city": city,
            "types": types
        }
        return await self._make_request("place/text", params)

    async def search_detail(self, id: str) -> Dict[str, Any]:
        """
        POI详情查询

        Args:
            id: POI ID

        Returns:
            POI详情
        """
        params = {"id": id}
        return await self._make_request("place/detail", params)

    def get_call_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        if not self.call_log:
            return {"total_calls": 0}

        endpoint_counts = {}
        for record in self.call_log:
            endpoint_counts[record.endpoint] = endpoint_counts.get(record.endpoint, 0) + 1

        avg_response_time = sum(r.response_time_ms for r in self.call_log) / len(self.call_log)
        success_rate = sum(1 for r in self.call_log if r.success) / len(self.call_log)

        return {
            "total_calls": len(self.call_log),
            "endpoint_counts": endpoint_counts,
            "avg_response_time_ms": avg_response_time,
            "success_rate": success_rate
        }

    def reset(self):
        """重置调用日志"""
        self.call_log.clear()
