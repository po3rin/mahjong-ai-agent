import logging
import os
from typing import Optional

import dspy
from dotenv import load_dotenv
from pydantic import BaseModel

from mahjong_ai_agent.dspy_modules import MahjongQuestionModule

logger = logging.getLogger(__name__)

# .envファイルを読み込む
load_dotenv()


class MahjongQuestion(BaseModel):
    """麻雀の問題と回答を表すデータクラス"""

    question: str  # 問題文
    hand_json: str  # Hand形式のJSON
    expected_score: int  # LLMが考えた答え


class QuestionGenerator:
    """DSPyを使って麻雀の点数計算問題を生成するクラス"""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", load_from: Optional[str] = None, enable_langfuse: bool = False):
        """
        Args:
            api_key: OpenAI API key。Noneの場合は環境変数から取得
            model: 使用するモデル名
            load_from: 最適化されたプロンプトのパス。指定された場合、保存されたモジュールを読み込む
            enable_langfuse: Langfuseトレーシングを有効にするか
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self.enable_langfuse = enable_langfuse

        # DSPyのLMを設定
        # Reasoning models (o1-*, gpt-5) require specific parameters
        reasoning_models = ["o1-preview", "o1-mini", "gpt-5"]
        is_reasoning_model = any(model.startswith(rm) for rm in reasoning_models)

        if is_reasoning_model:
            lm = dspy.LM(
                model=f"openai/{model}",
                api_key=self.api_key,
                temperature=1.0,
                max_tokens=16000
            )
        else:
            lm = dspy.LM(
                model=f"openai/{model}",
                api_key=self.api_key,
                temperature=0.8,  # 多様性のために高めに設定
                cache=False  # キャッシュを無効化
            )

        # 並列化の設定（デフォルト8から増やす）
        dspy.configure(lm=lm, async_max_workers=16)

        # Langfuseの設定
        if self.enable_langfuse:
            from langfuse.openai import openai

            # LangfuseでラップされたOpenAIクライアントを作成
            langfuse_client = openai.OpenAI(api_key=self.api_key)

            # DSPyのLMにLangfuseクライアントを設定
            if is_reasoning_model:
                lm = dspy.LM(
                    model=f"openai/{model}",
                    api_key=self.api_key,
                    temperature=1.0,
                    max_tokens=16000,
                    client=langfuse_client
                )
            else:
                lm = dspy.LM(
                    model=f"openai/{model}",
                    api_key=self.api_key,
                    temperature=0.8,
                    cache=False,
                    client=langfuse_client
                )

            dspy.configure(lm=lm, async_max_workers=16)
            logger.info("Langfuse tracing enabled")

        # 最適化されたモジュールを読み込むか、新規作成
        if load_from:
            logger.info(f"Loading optimized module from {load_from}")
            self.generator = MahjongQuestionModule()
            self.generator.load(load_from)
            logger.info("Optimized module loaded successfully")
        else:
            self.generator = MahjongQuestionModule()

    def generate_question(
        self, difficulty: str = "medium", num_questions: int = 1
    ) -> list[MahjongQuestion]:
        """
        麻雀の点数計算問題を生成する（並列化対応）

        Args:
            difficulty: 難易度 (easy, medium, hard)
            num_questions: 生成する問題数

        Returns:
            list[MahjongQuestion]: 生成された問題のリスト
        """
        try:
            if num_questions == 1:
                # 1問のみの場合は並列化不要
                variation_hint = "ユニークな牌の組み合わせと役を使用してください。"
                result = self.generator(difficulty=difficulty, variation_hint=variation_hint)
                return [
                    MahjongQuestion(
                        question=result.question,
                        hand_json=result.hand_json,
                        expected_score=int(result.expected_score),
                    )
                ]

            # 複数問の場合はbatch()を使って並列生成
            logger.info(f"Generating {num_questions} questions in parallel...")

            # バッチ入力を準備（各問題に異なるバリエーションヒントを付与）
            # dspy.Exampleオブジェクトとして作成
            inputs = []
            for i in range(num_questions):
                variation_hint = f"バリエーション{i+1}: 前の問題とは異なる牌の組み合わせと役を使用してください。"
                inputs.append(
                    dspy.Example(
                        difficulty=difficulty,
                        variation_hint=variation_hint
                    ).with_inputs("difficulty", "variation_hint")
                )

            # 並列実行
            results = self.generator.batch(inputs)

            # 結果を変換
            questions = []
            for result in results:
                questions.append(
                    MahjongQuestion(
                        question=result.question,
                        hand_json=result.hand_json,
                        expected_score=int(result.expected_score),
                    )
                )

            logger.info(f"Generated {len(questions)} questions in parallel")
            return questions

        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}", exc_info=True)
            raise


if __name__ == "__main__":
    # 使用例
    logging.basicConfig(level=logging.INFO)
    generator = QuestionGenerator()
    questions = generator.generate_question(difficulty="medium", num_questions=2)

    for i, q in enumerate(questions, 1):
        print(f"\n問題 {i}:")
        print(f"質問: {q.question}")
        print(f"Hand JSON: {q.hand_json}")
        print(f"LLMが考えた答え: {q.expected_score}")
