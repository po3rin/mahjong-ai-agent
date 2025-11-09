#!/usr/bin/env python3
"""対々和の検出テスト"""

import json
import sys
from pathlib import Path

# プロジェクトのルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tools.calculator import calculate_score_with_json

# 対々和の手牌データ
hand_json = {
    "tiles": [
        "2z", "2z", "2z",
        "5z", "5z", "5z",
        "7z", "7z", "7z",
        "9m", "9m", "9m",
        "3z", "3z"
    ],
    "melds": [
        {
            "tiles": ["2z", "2z", "2z"],
            "is_open": True
        },
        {
            "tiles": ["5z", "5z", "5z"],
            "is_open": True
        },
        {
            "tiles": ["7z", "7z", "7z"],
            "is_open": True
        }
    ],
    "win_tile": "9m",
    "dora_indicators": ["1z"],
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
}

print("=" * 60)
print("対々和テスト")
print("=" * 60)
print("\n手牌:")
print(f"  tiles: {hand_json['tiles']}")
print(f"\n鳴き:")
for i, meld in enumerate(hand_json['melds'], 1):
    print(f"  {i}. {meld['tiles']} (open: {meld['is_open']})")
print(f"\n和了牌: {hand_json['win_tile']}")
print(f"ドラ表示牌: {hand_json['dora_indicators']}")
print(f"自風: {hand_json['player_wind']}, 場風: {hand_json['round_wind']}")

print("\n" + "=" * 60)
print("計算実行中...")
print("=" * 60)

try:
    result = calculate_score_with_json(json.dumps(hand_json))

    print("\n結果:")
    print(f"  翻数: {result.han}")
    print(f"  符: {result.fu}")
    print(f"  得点: {result.score}")
    print(f"  役: {result.yaku}")

    if result.error:
        print(f"\nエラー: {result.error}")

    # 対々和が含まれているかチェック
    has_toitoi = any("toitoi" in yaku.lower() or "対々" in yaku for yaku in result.yaku)

    print("\n" + "=" * 60)
    if has_toitoi:
        print("✓ 対々和が検出されました")
    else:
        print("✗ 対々和が検出されませんでした")
    print("=" * 60)

except Exception as e:
    print(f"\nエラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
