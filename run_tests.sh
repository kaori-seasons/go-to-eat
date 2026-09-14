#!/usr/bin/env bash
# 运行 orchestrator 全部离线单测
set -e
cd "$(dirname "$0")"
echo "=== P0: 核心编排器 ==="
python3 -m pytest tests/test_orchestrator.py -v --tb=short
echo ""
echo "=== P1: guard / 持久化 / 多轮 / 召回 ==="
python3 -m pytest tests/test_orchestrator_p1.py -v --tb=short
echo ""
echo "=== P2: tracing / disk cache / config ==="
python3 -m pytest tests/test_orchestrator_p2.py -v --tb=short
echo ""
echo "=== 全部通过 ==="
