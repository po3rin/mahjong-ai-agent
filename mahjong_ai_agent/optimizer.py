import logging
import os
from typing import Optional

import dspy
from dotenv import load_dotenv

from mahjong_ai_agent.dspy_modules import MahjongQuestionModule
from mahjong_ai_agent.validator import QuestionValidator

logger = logging.getLogger(__name__)

# .envファイルを読み込む
load_dotenv()


class QuestionMetric:
    """問題の評価メトリック"""

    def __init__(self):
        self.validator = QuestionValidator()

    def __call__(self, example, prediction, trace=None) -> float:
        """
        生成された問題を評価する

        評価基準:
        - 点数計算がエラーなく実行できた: 1.0点
        - エラーが発生した: 0.0点

        Args:
            example: 入力例
            prediction: 生成された問題
            trace: トレース情報

        Returns:
            float: 評価スコア (0.0 or 1.0)
        """
        try:
            # 入力引数をログに記録
            logger.info("=== Metric Evaluation ===")
            logger.info(f"Input hand_json: {prediction.hand_json}")
            if hasattr(prediction, 'expected_score'):
                logger.info(f"Expected score: {prediction.expected_score}")
            if hasattr(prediction, 'question'):
                logger.info(f"Question: {prediction.question}")

            # 問題の検証（expected_scoreは検証に使用しない）
            validation_result = self.validator.validate_with_details(
                prediction.hand_json,
                expected_score=None,  # 期待点数との一致は評価しない
            )

            # 検証結果をログに記録
            logger.info(f"Validation result: {validation_result}")

            # エラーがない場合は1.0点、それ以外は0.0点
            if "error" not in validation_result:
                logger.info("✓ Validation passed - Score: 1.0")
                return 1.0
            else:
                logger.warning(f"✗ Validation failed - Error: {validation_result.get('error')} - Score: 0.0")
                return 0.0

        except Exception as e:
            logger.error(f"Error evaluating question: {str(e)}", exc_info=True)
            logger.error(f"Failed prediction: {prediction}")
            return 0.0


class QuestionOptimizer:
    """DSPyを使った問題生成プロンプトの最適化クラス"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        """
        Args:
            api_key: OpenAI API key。Noneの場合は環境変数から取得
            model: 使用するモデル名
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        # DSPyのLMを設定（並列化対応）
        lm = dspy.LM(model=f"openai/{model}", api_key=self.api_key)
        dspy.configure(lm=lm, async_max_workers=16)

        self.generator = MahjongQuestionModule()
        self.metric = QuestionMetric()

    def optimize(
        self,
        trainset: list[dspy.Example],
        optimizer_type: str = "bootstrap",
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 4,
        num_candidates: int = 10,
        init_temperature: float = 1.0,
    ):
        """
        問題生成プロンプトを最適化する

        Args:
            trainset: トレーニングデータセット
            optimizer_type: 最適化手法 ("bootstrap", "mipro", "copro")
                - bootstrap: Few-shot examplesを追加
                - mipro: プロンプトテンプレート自体を書き換え（推奨）
                - copro: CoordinatePromptOptimizer（プロンプト座標最適化）
            max_bootstrapped_demos: ブートストラップされるデモの最大数（bootstrap用）
            max_labeled_demos: ラベル付きデモの最大数（bootstrap用）
            num_candidates: 候補プロンプト数（mipro用）
            init_temperature: 初期temperature（mipro用）

        Returns:
            MahjongQuestionModule: 最適化されたジェネレーター
        """
        logger.info(f"Starting optimization with {optimizer_type} optimizer")

        if optimizer_type == "bootstrap":
            # BootstrapFewShotを使用して最適化
            optimizer = dspy.BootstrapFewShot(
                metric=self.metric,
                max_bootstrapped_demos=max_bootstrapped_demos,
                max_labeled_demos=max_labeled_demos,
            )
        elif optimizer_type == "mipro":
            # MIPROを使用してプロンプトテンプレート自体を最適化
            optimizer = dspy.MIPROv2(
                metric=self.metric,
                num_candidates=num_candidates,
                init_temperature=init_temperature,
            )
        elif optimizer_type == "copro":
            # CoordinatePromptOptimizerを使用
            optimizer = dspy.COPRO(
                metric=self.metric,
            )
        else:
            raise ValueError(
                f"Unknown optimizer type: {optimizer_type}. "
                f"Choose from: bootstrap, mipro, copro"
            )

        # 最適化を実行
        optimized_generator = optimizer.compile(
            self.generator,
            trainset=trainset,
        )

        logger.info("Optimization completed")
        return optimized_generator

    def create_trainset(self, difficulties: list[str]) -> list[dspy.Example]:
        """
        トレーニングデータセットを作成する

        Args:
            difficulties: 難易度のリスト

        Returns:
            list[dspy.Example]: トレーニングデータセット
        """
        trainset = []
        for difficulty in difficulties:
            trainset.append(
                dspy.Example(difficulty=difficulty).with_inputs("difficulty")
            )
        return trainset


if __name__ == "__main__":
    # 使用例
    logging.basicConfig(level=logging.INFO)

    optimizer = QuestionOptimizer()

    # トレーニングデータセットを作成
    trainset = optimizer.create_trainset(
        ["easy", "easy", "medium", "medium", "hard"]
    )

    # 最適化を実行
    optimized_generator = optimizer.optimize(
        trainset=trainset,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )

    # 最適化されたジェネレーターを使用して問題を生成
    result = optimized_generator(difficulty="medium")
    print(f"\n生成された問題:")
    print(f"質問: {result.question}")
    print(f"Hand JSON: {result.hand_json}")
    print(f"期待される点数: {result.expected_score}")
