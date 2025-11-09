#!/usr/bin/env python3
"""修正後の表示テスト"""

import asyncio
import json
import logging
from mahjong_ai_agent.verifier import QuestionVerifier

# ログ設定
logging.basicConfig(level=logging.INFO)

# 対々和の手牌データ（完全版）
hand_json = json.dumps({
    "tiles": [
        "2z", "2z", "2z",
        "5z", "5z", "5z",
        "7z", "7z", "7z",
        "9m", "9m", "9m",
        "3z", "3z"
    ],
    "melds": [
        {"tiles": ["2z", "2z", "2z"], "is_open": True},
        {"tiles": ["5z", "5z", "5z"], "is_open": True},
        {"tiles": ["7z", "7z", "7z"], "is_open": True}
    ],
    "win_tile": "9m",
    "dora_indicators": ["2z"],
    "is_riichi": False,
    "is_tsumo": False,
    "is_ippatsu": False,
    "is_rinshan": False,
    "is_chankan": False,
    "is_haitei": False,
    "is_houtei": False,
    "is_daburu_riichi": False,
    "is_nagashi_mangan": False,
    "is_tenhou": False,
    "is_chiihou": False,
    "is_renhou": False,
    "is_open_riichi": False,
    "player_wind": "south",
    "round_wind": "south",
    "kyoutaku_number": 0,
    "tsumi_number": 6
})

async def main():
    verifier = QuestionVerifier(use_baml=True)

    print("=" * 60)
    print("検証中...")
    print("=" * 60)

    # 詳細な検証
    details = await verifier.verify_with_details(hand_json)

    print("\n検証結果:")
    print(f"  is_verified: {details.get('is_verified')}")
    print(f"  翻数: {details.get('han')}")
    print(f"  符: {details.get('fu')}")
    print(f"  点数: {details.get('score')}")
    print(f"  役: {details.get('yaku')}")
    if details.get('error'):
        print(f"  エラー: {details.get('error')}")

    # 指示適合性判定
    print("\n" + "=" * 60)
    print("指示適合性判定中...")
    print("=" * 60)

    instruction = "対々和の問題を作成してください"
    compliance = await verifier.judge_instruction_compliance(instruction, details)

    print(f"\n指示: {instruction}")
    print(f"判定結果:\n{compliance}")

asyncio.run(main())
