import asyncio
import csv
import logging
import os
import random
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel

from baml.baml_client.types import Hand

logger = logging.getLogger(__name__)

# .envファイルを読み込む
load_dotenv()


# プロンプトテンプレート
MAHJONG_QUESTION_PROMPT = """麻雀の点数計算問題の問題文を1問だけ生成してください。できるだけユニークで多様な状況を作成してください。

**入力された指示に必ず従ってください:**
{instruction}

問題文には必ず以下の情報を含めてください：
1. 場の状態（東場/南場、本場数、自風）
2. ドラ情報（ドラ表示牌とドラ）
3. 和了方法（ツモ/ロン）
4. **手牌の具体的な牌構成（例：1m, 2m, 3m, 4p, 5p, 6p...）を明記**
   - **重要: 手牌には和了牌を含めて14枚にしてください**
   - 和了牌も手牌の一部として記載する必要があります
   - **牌の有効範囲:**
     * 萬子(m): 1m, 2m, 3m, 4m, 5m, 6m, 7m, 8m, 9m
     * 筒子(p): 1p, 2p, 3p, 4p, 5p, 6p, 7p, 8p, 9p
     * 索子(s): 1s, 2s, 3s, 4s, 5s, 6s, 7s, 8s, 9s
     * 字牌(z): 1z(東), 2z(南), 3z(西), 4z(北), 5z(白), 6z(発), 7z(中) **のみ。8z, 9zは存在しません！**
5. 鳴きがある場合は、その内容（ポン/チー/カンと牌の種類）も明記
6. 和了牌を明示（この牌は手牌にも含まれている必要があります）
7. 求めるもの（最終的な得点）

**麻雀の和了形のパターン（必読）:**
麻雀には以下の和了形があります：

パターン1: 通常の和了形（4面子1雀頭）
- 面子（メンツ）: 順子(123mなど連続3枚)または刻子(111mなど同じ牌3枚) × 4組
  **重要**: 順子は数牌(1-9m, 1-9p, 1-9s)のみ。字牌(1z-7z)は順子を作れません！
  字牌で面子を作る場合は必ず刻子（同じ牌3枚）にしてください。
- 雀頭（ジャントウ）: 同じ牌2枚 × 1組
- 合計: 3×4 + 2 = 14枚

パターン2: 七対子（チートイツ）
- 同じ牌2枚のペア × 7組
- 合計: 2×7 = 14枚
- これ自体が役になります

パターン3: 国士無双（コクシムソウ）
- 么九牌13種類（1m,9m,1p,9p,1s,9s,1z,2z,3z,4z,5z,6z,7z）を各1枚+どれか1枚
- 合計: 14枚
- これ自体が役満になります

**手牌を作成する手順（通常の和了形の場合）:**
1. まず雀頭を決める（同じ牌2枚、例: 1m1m）
2. 次に4つの面子を決める：
   - 順子の例: 123m, 456p, 789s
   - 刻子の例: 111m, 555z, 777p
3. 和了牌は既に手牌に含まれている牌から選ぶ
4. 役を決める（下記参照）

**重要: 必ず役（ヤク）がある手牌を作成してください。役なしの手牌は無効です。**

役の例:
- タンヤオ（2-8のみの牌、鳴きなし）、役牌（5z=白, 6z=発, 7z=中を3枚）、リーチ
- 複数役の組み合わせ、ピンフ、イーペーコー、ドラ
- 三色同順、一気通貫、七対子、対々和、カン、特殊役

良い例1（タンヤオのみ、鳴きなし）:
「東場0本場、あなたは東家。ドラ表示牌は3m（ドラは4m）。ツモで和了しました。
手牌は以下の通り：2m, 3m, 4m, 5m, 6m, 7m, 2p, 3p, 4p, 5s, 6s, 7s, 8s, 8s
和了牌は8s。最終的な得点を計算してください。」
→ 構成: [2m3m4m][5m6m7m][2p3p4p][5s6s7s][8s8s] = 4面子1雀頭 ✓

良い例2（役牌のみ）:
「南場1本場、あなたは南家。ドラ表示牌は9m（ドラは1m）。ツモで和了しました。
手牌は以下の通り：1m, 2m, 3m, 4p, 5p, 6p, 5z, 5z, 5z, 6s, 7s, 8s, 9s, 9s
和了牌は9s。最終的な得点を計算してください。」
→ 構成: [1m2m3m][4p5p6p][5z5z5z][6s7s8s][9s9s] = 4面子1雀頭 ✓（5z=白は役牌）

良い例3（役牌2つ、鳴きあり）:
「東場0本場、あなたは東家。ドラ表示牌は1z（ドラは2z）。ツモで和了しました。
手牌は以下の通り：5z, 5z, 5z, 6z, 6z, 6z, 2m, 3m, 4m, 5s, 5s
5pをポン。
和了牌は5s。最終的な得点を計算してください。」
→ 構成: [5z5z5z][6z6z6z][2m3m4m][5p5p5p(ポン)][5s5s] = 4面子1雀頭 ✓（5z=白, 6z=発は役牌）

良い例4（七対子）:
「東場0本場、あなたは東家。ドラ表示牌は3m（ドラは4m）。ツモで和了しました。
手牌は以下の通り：1m, 1m, 3m, 3m, 5m, 5m, 2p, 2p, 4p, 4p, 6s, 6s, 8s, 8s
和了牌は8s。最終的な得点を計算してください。」
→ 構成: [1m1m][3m3m][5m5m][2p2p][4p4p][6s6s][8s8s] = 7対子 ✓（七対子は役）

良い例5（国士無双）:
「東場0本場、あなたは東家。ドラ表示牌は5m（ドラは6m）。ツモで和了しました。
手牌は以下の通り：1m, 9m, 1p, 9p, 1s, 9s, 1z, 2z, 3z, 4z, 5z, 6z, 7z, 1m
和了牌は1m。最終的な得点を計算してください。」
→ 構成: 13種類の么九牌+1枚 ✓（国士無双は役満）

このように、具体的な牌を列挙して、誰が見ても手牌の内容が分かるようにしてください。

**最重要ルール:**
1. 手牌は必ず和了牌を含めて正確に14枚以上の牌を明記してください
2. 和了牌は必ず手牌の中に既に存在する牌から選んでください
3. 例えば、手牌に「5z, 5z, 5z」があれば、和了牌として「5z」を選べます
4. 手牌に存在しない牌を和了牌として指定しないでください

問題文のみを出力してください。説明や構成の解説は不要です。"""


class MahjongQuestion(BaseModel):
    """麻雀の問題と回答を表すデータクラス"""

    question: Optional[str] = None  # 問題文
    hand: Optional[Hand] = None  # BAMLで抽出されたHandオブジェクト
    expected_score: Optional[int] = None  # 計算された正解点数（validatorで設定）
    instruction: Optional[str] = None  # 問題生成時の指示（CSV生成時に使用）
    generation_error: Optional[str] = None  # 問題生成時のエラーメッセージ


class QuestionGenerator:
    """OpenAIを使って麻雀の点数計算問題を生成するクラス"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", load_from: Optional[str] = None, enable_langfuse: bool = False):
        """
        Args:
            api_key: OpenAI API key。Noneの場合は環境変数から取得
            model: 使用するモデル名
            load_from: 未使用（後方互換性のため残す）
            enable_langfuse: Langfuseトレーシングを有効にするか
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self.model = model
        self.enable_langfuse = enable_langfuse

        # Langfuseの設定
        if self.enable_langfuse:
            from langfuse.openai import openai
            self.client = openai.OpenAI(api_key=self.api_key)
            self.async_client = openai.AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = OpenAI(api_key=self.api_key)
            self.async_client = AsyncOpenAI(api_key=self.api_key)

    async def _generate_single_question(self, instruction: str) -> str:
        """単一の問題文を生成"""
        prompt = MAHJONG_QUESTION_PROMPT.format(instruction=instruction)

        # Reasoning models (o1-*, gpt-5) require temperature=1
        reasoning_models = ["o1-preview", "o1-mini", "gpt-5"]
        is_reasoning_model = any(self.model.startswith(rm) for rm in reasoning_models)

        if is_reasoning_model:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0
            )
        else:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )

        return response.choices[0].message.content

    async def generate_question(
        self,
        num_questions: int = 1,
        instruction: str = ""
    ) -> list[MahjongQuestion]:
        """
        麻雀の点数計算問題を生成する

        Args:
            num_questions: 生成する問題数
            instruction: 問題生成の指示（自然言語）。指定されている場合はこちらを優先

        Returns:
            list[MahjongQuestion]: 生成された問題のリスト
        """
        try:
            # 指示を準備
            instructions = []
            for i in range(num_questions):
                if not instruction:
                    inst = f"バリエーション{i+1}として前の問題とは異なる牌の組み合わせと役を使用した問題を作成してください。"
                else:
                    inst = instruction
                instructions.append(inst)

            # 並列で問題文を生成
            tasks = [self._generate_single_question(inst) for inst in instructions]
            question_texts = await asyncio.gather(*tasks, return_exceptions=True)

            # MahjongQuestionオブジェクトを作成
            questions = []
            for i, result in enumerate(question_texts):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate question {i+1}: {result}")
                    questions.append(MahjongQuestion(
                        generation_error=f"Generation failed: {str(result)}"
                    ))
                else:
                    questions.append(MahjongQuestion(question=result))

            # BAML抽出はVerifier内で実行されるため、ここでは問題文のみを返す
            return questions

        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}", exc_info=True)
            raise

    async def generate_questions_from_csv(
        self, csv_path: str, num_questions: Optional[int] = None
    ) -> list[MahjongQuestion]:
        """
        CSVファイルから指示パターンを読み込んで問題を生成する

        Args:
            csv_path: CSVファイルのパス
            num_questions: 生成する問題数。Noneの場合は全ての指示から生成。
                          指定された場合は、CSVからランダムにN個選んで生成

        Returns:
            list[MahjongQuestion]: 生成された問題のリスト

        CSV形式:
            instruction
            難易度easyで、タンヤオの問題を作成してください
            難易度mediumで、答えが2000点になる問題を作成してください
            難易度hardで、4翻30符の問題を作成してください
        """
        try:
            # CSVファイルを読み込む
            instructions = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                instructions.extend(row['instruction'] for row in reader)

            # num_questionsが指定されている場合はランダムに選択
            if num_questions is not None and num_questions < len(instructions):
                instructions = random.sample(instructions, num_questions)

            # 並列で問題文を生成
            tasks = [self._generate_single_question(inst) for inst in instructions]
            question_texts = await asyncio.gather(*tasks, return_exceptions=True)

            # MahjongQuestionオブジェクトを作成（instructionも保持）
            questions = []
            failed_count = 0
            for i, (result, inst) in enumerate(zip(question_texts, instructions)):
                if isinstance(result, Exception):
                    error_msg = f"Generation failed: {str(result)}"
                    logger.warning(f"Failed to generate question {i+1}/{len(instructions)}: {inst}")
                    questions.append(MahjongQuestion(
                        instruction=inst,
                        generation_error=error_msg
                    ))
                    failed_count += 1
                else:
                    questions.append(MahjongQuestion(question=result, instruction=inst))

            if failed_count > 0:
                logger.warning(f"Failed to generate {failed_count}/{len(instructions)} questions")

            return questions

        except Exception as e:
            logger.error(f"Error generating questions from CSV: {str(e)}", exc_info=True)
            raise


if __name__ == "__main__":
    # 使用例
    logging.basicConfig(level=logging.INFO)

    async def main():
        generator = QuestionGenerator()
        questions = await generator.generate_question(num_questions=2)

        for i, q in enumerate(questions, 1):
            print(f"\n問題 {i}:")
            print(f"質問: {q.question}")
            if q.hand:
                print(f"抽出されたHand: {q.hand}")
            if q.expected_score:
                print(f"正解点数: {q.expected_score}")

    asyncio.run(main())
