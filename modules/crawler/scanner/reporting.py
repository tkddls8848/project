"""메타데이터 scanner 결과의 파일 저장과 콘솔 요약."""

from __future__ import annotations

import json
import os
from typing import Any, Dict


def save_results(
    results: Dict[str, Any],
    scan_type: str,
    start_num: int,
    end_num: int,
    output_dir: str = "/data/metadata_results",
) -> Dict[str, str | None]:
    """기존 파일명과 payload를 유지해 스캔 결과를 저장한다."""
    type_dir = os.path.join(output_dir, scan_type)
    os.makedirs(type_dir, exist_ok=True)

    summary_file = os.path.join(type_dir, "summary.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_range": f"{start_num}-{end_num}",
                "total_scanned": results["total"],
                "data_found": results["with_data"],
                "data_not_found": results["without_data"],
                "failed": results["failed"],
                "retried": results["retried"],
                "retry_success": results["retry_success"],
                "retry_success_rate": (
                    f"{(results['retry_success'] / results['retried'] * 100):.2f}%"
                    if results["retried"] > 0
                    else "0.00%"
                ),
                "waiting_room_detected": results["waiting_room_detected"],
                "success_rate": f"{(results['with_data'] / results['total'] * 100):.2f}%",
                "data_types": results["data_types"],
                "scan_time": results.get("scan_time", {}),
                "data_count": len(results["data_numbers"]),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    numbers_file = os.path.join(type_dir, f"{scan_type}_numbers.json")
    with open(numbers_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                f"{scan_type}_numbers": results["data_numbers"],
                "count": len(results["data_numbers"]),
                "scan_info": {"range": f"{start_num}-{end_num}"},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    list_file = os.path.join(type_dir, f"{scan_type}_numbers.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for num in results["data_numbers"]:
            f.write(f"{num}\n")

    metadata_file = os.path.join(type_dir, f"{scan_type}_metadata.json")
    metadata = {
        num: details
        for num, details in results["details"].items()
        if details.get("has_data", False)
    }
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    for data_type, count in results["data_types"].items():
        if count > 0:
            type_numbers = []
            type_key = f"{scan_type}_type"
            for num, details in results["details"].items():
                if (details.get(type_key) or "").upper() == data_type:
                    type_numbers.append(num)

            if type_numbers:
                type_file = os.path.join(type_dir, f"{scan_type}_type_{data_type}.json")
                with open(type_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            f"{scan_type}_type": data_type,
                            "numbers": type_numbers,
                            "count": len(type_numbers),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

    failed_numbers = [
        num
        for num, details in results["details"].items()
        if details.get("status") != "success" and details.get("status") != "not_found"
    ]
    failed_file = None
    if failed_numbers:
        failed_file = os.path.join(type_dir, "failed_numbers.json")
        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "failed_numbers": failed_numbers,
                    "count": len(failed_numbers),
                    "details": {
                        num: results["details"][num] for num in failed_numbers
                    },
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    return {
        "summary_file": summary_file,
        "numbers_file": numbers_file,
        "list_file": list_file,
        "metadata_file": metadata_file,
        "failed_file": failed_file if failed_numbers else None,
    }


def print_summary(
    results: Dict[str, Any], scan_type: str, start_num: int, end_num: int
) -> None:
    """기존 콘솔 문구를 그대로 사용해 스캔 결과를 요약한다."""
    data_type_name = _get_data_type_name(scan_type)

    print("\n" + "=" * 60)
    print(f"📊 {scan_type} 메타데이터 스캔 완료!")
    print("=" * 60)
    print(f"🔍 스캔 범위: {start_num:,} ~ {end_num:,}")
    print(f"📋 총 스캔: {results['total']:,}개")
    print(
        f"✅ {data_type_name} 있음: {results['with_data']:,}개 "
        f"({results['with_data'] / results['total'] * 100:.1f}%)"
    )
    print(f"❌ {data_type_name} 없음: {results['without_data']:,}개")
    print(f"⚠️  실패: {results['failed']:,}개")

    if results["retried"] > 0:
        print(f"🔄 재시도: {results['retried']:,}개")
        print(f"✅ 재시도 성공: {results['retry_success']:,}개")
        retry_success_rate = (
            results["retry_success"] / results["retried"] * 100
            if results["retried"] > 0
            else 0
        )
        print(f"📈 재시도 성공률: {retry_success_rate:.1f}%")

    if results["waiting_room_detected"] > 0:
        print(f"🚨 대기실 감지: {results['waiting_room_detected']:,}회")

    if results.get("scan_time"):
        print(f"\n⏱️  소요 시간: {results['scan_time']['elapsed_formatted']}")
        print(f"📅 시작: {results['scan_time']['start']}")
        print(f"📅 종료: {results['scan_time']['end']}")

    if results["data_types"]:
        type_name = _get_type_name(scan_type)
        print(f"\n{type_name}:")
        sorted_types = sorted(results["data_types"].items(), key=lambda x: x[1], reverse=True)
        for data_type, count in sorted_types[:10]:
            percentage = count / results["with_data"] * 100 if results["with_data"] > 0 else 0
            print(f"   - {data_type}: {count}개 ({percentage:.1f}%)")

    org_stats: Dict[str, int] = {}
    for details in results["details"].values():
        if details.get("has_data") and details.get("organization"):
            org = details["organization"]
            org_stats[org] = org_stats.get(org, 0) + 1

    if org_stats:
        print("\n🏢 상위 제공 기관:")
        sorted_orgs = sorted(org_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        for org, count in sorted_orgs:
            print(f"   - {org}: {count}개")


def _get_data_type_name(scan_type: str) -> str:
    names = {"fileData": "파일", "openapi": "API", "standard": "표준"}
    return names.get(scan_type, "데이터")


def _get_type_name(scan_type: str) -> str:
    names = {
        "fileData": "📁 파일 타입별 분포",
        "openapi": "🔌 API 타입별 분포",
        "standard": "📋 표준 타입별 분포",
    }
    return names.get(scan_type, "📊 타입별 분포")


__all__ = ["print_summary", "save_results"]
