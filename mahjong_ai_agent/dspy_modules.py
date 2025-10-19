"""DSPyを使った麻雀問題生成の共通モジュール"""
import dspy


class MahjongQuestionSignature(dspy.Signature):
    """麻雀の点数計算問題を生成するシグネチャ"""

    difficulty = dspy.InputField(
        desc="問題の難易度 (easy, medium, hard)"
    )
    variation_hint = dspy.InputField(
        desc="問題のバリエーションヒント（多様性を持たせるための追加情報）",
        default=""
    )
    question = dspy.OutputField(
        desc="麻雀の点数計算問題の問題文。できるだけユニークで多様な状況を作成してください。"
    )
    hand_json = dspy.OutputField(
        desc="""Hand形式のJSON文字列。麻雀の和了形（4面子1雀頭）になるように正確に14枚の牌を指定してください。

牌の表記:
- 萬子: 1m-9m
- 筒子: 1p-9p
- 索子: 1s-9s
- 字牌: 1z(東), 2z(南), 3z(西), 4z(北), 5z(白), 6z(発), 7z(中)

正しい例（タンヤオ・ピンフ）:
{
  "tiles": ["2m", "3m", "4m", "5m", "6m", "7m", "2p", "3p", "4p", "5s", "6s", "7s", "8s", "8s"],
  "win_tile": "8s",
  "is_tsumo": false,
  "is_riichi": false,
  "player_wind": "east",
  "round_wind": "east"
}

正しい例（鳴きあり：ポン・チー・カンを含む）:
{
  "tiles": ["1m", "1m", "1m", "1m", "5m", "6m", "7m", "5z", "5z", "5z", "6p", "7p", "8p", "9s", "9s"],
  "win_tile": "9s",
  "melds": [
    {"type": "pon", "tiles": ["5z", "5z", "5z"]},
    {"type": "chi", "tiles": ["6p", "7p", "8p"]},
    {"type": "kan", "tiles": ["1m", "1m", "1m", "1m"]}
  ],
  "is_tsumo": false,
  "is_riichi": false,
  "player_wind": "south",
  "round_wind": "east"
}

注意事項:
1. tilesは14枚以上にしてください（カンがある場合は14枚から追加で枚数が増えます）
2. win_tileはtilesに含まれている必要があります
3. 和了形（4面子1雀頭）になるようにしてください
4. meldsを使う場合、その牌もtilesに含めてください
5. 難易度に応じた問題:
   - easy: タンヤオ、ピンフなど基本役のみ（字牌・端牌なし）
   - medium: リーチ、ドラ、役牌などを含む
   - hard: 複雑な役の組み合わせ、カン、特殊な状況役を含む
6. 各問題で異なる牌の組み合わせ、異なる役、異なる点数になるように多様性を持たせてください
7. 同じ数牌の色（萬子・筒子・索子）ばかり使わず、バランスよく使用してください
"""
    )
    expected_score = dspy.OutputField(
        desc="期待される点数（整数値）"
    )


class MahjongQuestionModule(dspy.Module):
    """DSPyを使った麻雀問題生成モジュール"""

    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(MahjongQuestionSignature)

    def forward(self, difficulty: str, variation_hint: str = ""):
        result = self.generate(difficulty=difficulty, variation_hint=variation_hint)
        return dspy.Prediction(
            question=result.question,
            hand_json=result.hand_json,
            expected_score=result.expected_score,
        )
