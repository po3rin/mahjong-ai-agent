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
        desc="""麻雀の点数計算問題の問題文。できるだけユニークで多様な状況を作成してください。

問題文には必ず以下の情報を含めてください：
1. 場の状態（東場/南場、本場数、自風、ドラ情報など）
2. 和了方法（ツモ/ロン）
3. **手牌の具体的な牌構成（例：1m, 2m, 3m, 4p, 5p, 6p...）を明記**
4. 鳴きがある場合は、その内容（ポン/チー/カンと牌の種類）も明記
5. 求めるもの（最終支払い点数など）

例：
「東場0本場、あなたは東家。ドラ表示牌は3m（ドラは4m）。自摸（ツモ）で和了。
手牌は以下の通り：1m, 2m, 3m, 4m, 5m, 6m, 2p, 3p, 4p, 7s, 7s, 5z, 5z, 5z
最終的な得点を計算してください。」

このように、具体的な牌を列挙して、誰が見ても手牌の内容が分かるようにしてください。
"""
    )
    hand_json = dspy.OutputField(
        desc="""Hand形式のJSON文字列。麻雀の和了形（4面子1雀頭）になるように正確に14枚の牌を指定してください。

**重要: 必ず役（ヤク）がある手牌を生成してください。役なしの手牌は無効です。**

牌の表記:
- 萬子: 1m-9m
- 筒子: 1p-9p
- 索子: 1s-9s
- 字牌: 1z(東), 2z(南), 3z(西), 4z(北), 5z(白), 6z(発), 7z(中)

**字牌の重要なルール:**
- 字牌は順子（シュンツ）を作れません！ 必ず刻子（コーツ）として使用してください
- 例: 1z, 2z, 3z は順子にならない
- 例: 1z, 1z, 1z は刻子になる

正しい例（タンヤオ・ピンフ - 必ず2-8の牌のみ使用）:
{
  "tiles": ["2m", "3m", "4m", "5m", "6m", "7m", "2p", "3p", "4p", "5s", "6s", "7s", "8s", "8s"],
  "win_tile": "8s",
  "is_tsumo": false,
  "is_riichi": true,
  "player_wind": "east",
  "round_wind": "east"
}
→ この手牌の役: リーチ、タンヤオ、ピンフ

正しい例（役牌 - 白の刻子で確実に役がある）:
{
  "tiles": ["2m", "3m", "4m", "5p", "6p", "7p", "5z", "5z", "5z", "6s", "7s", "8s", "9s", "9s"],
  "win_tile": "9s",
  "is_tsumo": false,
  "is_riichi": false,
  "player_wind": "east",
  "round_wind": "east"
}
→ この手牌の役: 役牌（白）

正しい例（鳴きあり：役牌の刻子を含む）:
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
→ この手牌の役: 役牌（白）、カン

注意事項:
1. tilesは14枚以上にしてください（カンがある場合は14枚から追加で枚数が増えます）
2. win_tileはtilesに含まれている必要があります
3. 和了形（4面子1雀頭）になるようにしてください
4. meldsを使う場合、その牌もtilesに含めてください
5. **必ず役（ヤク）がある手牌を作成してください:**
   - easy: リーチ+タンヤオ、役牌（5z, 6z, 7z）など確実な役
   - medium: 複数役の組み合わせ、ドラ付き
   - hard: 複雑な役の組み合わせ、カン、特殊な状況役
6. 各問題で異なる牌の組み合わせ、異なる役、異なる点数になるように多様性を持たせてください
7. 同じ数牌の色（萬子・筒子・索子）ばかり使わず、バランスよく使用してください
8. **タンヤオを使う場合は、必ず2-8の牌のみで構成し、1, 9, 字牌を含めないでください**
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


class LLMJudge(dspy.Signature):
    """生成された麻雀問題の品質を評価する"""

    assessed_question = dspy.InputField(desc="評価対象の問題文")
    assessed_hand = dspy.InputField(desc="評価対象の手牌JSON")
    assessment_question = dspy.InputField(
        desc="評価のための質問（例：この問題は正しい和了形になっていますか？）"
    )

    assessment_answer = dspy.OutputField(
        desc="評価結果（Yes/No）とその理由を含む回答"
    )
