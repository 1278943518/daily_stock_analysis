# -*- coding: utf-8 -*-
"""
股票分析包装脚本 — 支持中文名称输入 → 自动映射代码 → 运行分析 + 飞书推送 + 记录追踪
用法：
  python scripts/run_analysis.py 兆易创新
  python scripts/run_analysis.py 贵州茅台 宁德时代
  python scripts/run_analysis.py --market-only    # 仅大盘复盘
  python scripts/run_analysis.py --nightly          # 夜间自动（大盘 + 最近个股）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 把项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.services.name_to_code_resolver import resolve_name_to_code

TRACKING_FILE = PROJECT_ROOT / ".workbuddy" / "last_stocks.json"


def get_last_stocks() -> list[str]:
    """读取最近一次分析的股票代码列表"""
    if TRACKING_FILE.exists():
        try:
            data = json.loads(TRACKING_FILE.read_text(encoding="utf-8"))
            return data.get("stocks", [])
        except Exception:
            pass
    return []


def save_last_stocks(codes: list[str]):
    """保存最近分析的股票代码"""
    TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "stocks": codes,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    TRACKING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_names(names: list[str]) -> list[str]:
    """将股票名称列表解析为代码列表，跳过解析失败的"""
    codes = []
    failed = []
    for name in names:
        code = resolve_name_to_code(name)
        if code:
            codes.append(code)
            print(f"  ✅ {name} → {code}")
        else:
            failed.append(name)
            print(f"  ❌ {name} → 未能识别")
    if failed:
        print(f"\n⚠️  {len(failed)} 个名称未能识别: {', '.join(failed)}")
    return codes


def run_stock_analysis(codes: list[str]):
    """运行个股分析 + 飞书推送"""
    if not codes:
        print("⚠️ 没有有效的股票代码，跳过个股分析")
        return

    stocks_arg = ",".join(codes)
    print(f"\n📊 开始分析 {len(codes)} 只股票: {stocks_arg}")
    print("━" * 60)

    env = os.environ.copy()
    # 确保 .env 中的配置生效
    cmd = [
        sys.executable, str(PROJECT_ROOT / "main.py"),
        "--stocks", stocks_arg,
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=False)
    return result.returncode


def run_market_review():
    """运行大盘复盘分析"""
    print("\n📈 开始大盘复盘分析")
    print("━" * 60)

    env = os.environ.copy()
    cmd = [
        sys.executable, str(PROJECT_ROOT / "main.py"),
        "--market-review",
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=False)
    return result.returncode


def run_nightly():
    """夜间自动模式：大盘复盘 + 最近分析的个股"""
    print("=" * 60)
    print(f"🌙 夜间自动分析 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. 大盘复盘
    market_ok = run_market_review() == 0

    # 2. 最近分析的个股
    last_codes = get_last_stocks()
    if last_codes:
        print(f"\n📋 上次分析的股票: {', '.join(last_codes)}")
        stocks_ok = run_stock_analysis(last_codes) == 0
    else:
        print("\n⚠️ 没有最近分析的股票记录，仅推送大盘")
        stocks_ok = True

    if market_ok and stocks_ok:
        print("\n✅ 夜间推送完成")
        return 0
    else:
        print("\n⚠️ 部分分析失败，请检查日志")
        return 1


def main():
    parser = argparse.ArgumentParser(description="股票分析 → 飞书推送")
    parser.add_argument("stocks", nargs="*", help="股票名称或代码（支持中文）")
    parser.add_argument("--market-only", action="store_true", help="仅大盘复盘")
    parser.add_argument("--nightly", action="store_true", help="夜间自动模式（大盘+最近个股）")
    args = parser.parse_args()

    if args.nightly:
        return run_nightly()

    if args.market_only:
        return run_market_review()

    if not args.stocks:
        parser.print_help()
        print("\n示例：")
        print("  python scripts/run_analysis.py 兆易创新")
        print("  python scripts/run_analysis.py 贵州茅台 宁德时代")
        print("  python scripts/run_analysis.py --market-only")
        print("  python scripts/run_analysis.py --nightly")
        return 1

    # 手动模式：解析名称 → 分析 → 记录
    print(f"\n🔍 解析 {len(args.stocks)} 个股票名称...")
    codes = resolve_names(args.stocks)

    if not codes:
        print("\n❌ 没有有效的股票代码，退出")
        return 1

    # 保存追踪
    save_last_stocks(codes)

    # 运行分析
    return run_stock_analysis(codes)


if __name__ == "__main__":
    sys.exit(main())
