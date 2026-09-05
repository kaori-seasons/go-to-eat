"""
综合测试执行器
运行所有测试用例并生成报告
"""

import asyncio
import json
from datetime import datetime

from comprehensive_test_suite import ComprehensiveTestSuite


# 高德API密钥
AMAP_API_KEY = "xxxxx"


async def main():
    """主函数"""
    print("=" * 70)
    print("  Where to Eat - 高德地图API综合测试")
    print("  使用真实API Key进行大规模测试")
    print("=" * 70)

    # 初始化测试套件
    test_suite = ComprehensiveTestSuite(AMAP_API_KEY)

    # 运行各类测试
    # 1. 地理编码测试 - 北京20个地点
    await test_suite.run_geocode_tests(city="北京", count=20)

    # 2. 地理编码测试 - 其他城市
    await test_suite.run_geocode_tests(city="上海", count=5)
    await test_suite.run_geocode_tests(city="广州", count=3)
    await test_suite.run_geocode_tests(city="深圳", count=3)

    # 3. 路线规划测试
    await test_suite.run_route_tests(city="北京", count=8)

    # 4. 餐厅搜索测试
    await test_suite.run_restaurant_search_tests(city="北京", count=8)

    # 5. 端到端测试
    await test_suite.run_end_to_end_tests(city="北京", count=5)

    # 生成报告
    report = test_suite.generate_comprehensive_report()

    # 保存报告
    report_path = "/Users/kaori/Downloads/where-to-eat-main/tests/results/comprehensive_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("  测试完成!")
    print("=" * 70)

    # 打印摘要
    summary = report["test_summary"]
    print(f"\n📊 测试摘要:")
    print(f"  总测试数: {summary['total_tests']}")
    print(f"  成功数: {summary['successful_tests']}")
    print(f"  成功率: {summary['success_rate']:.2%}")
    print(f"  总API调用: {summary['total_api_calls']}")
    print(f"  平均API响应时间: {summary['avg_api_response_time_ms']:.0f}ms")
    print(f"  API成功率: {summary['api_success_rate']:.2%}")

    print(f"\n📁 详细报告已保存至: {report_path}")

    # 打印分类统计
    print(f"\n📈 分类统计:")
    for category, stats in report["category_breakdown"].items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        avg_time = stats["time"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {category}:")
        print(f"    测试数: {stats['total']}, 成功率: {success_rate:.2%}, 平均耗时: {avg_time:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
