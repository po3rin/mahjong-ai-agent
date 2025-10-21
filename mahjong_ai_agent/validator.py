import asyncio
import json
import logging
from typing import Optional

from mahjong_ai_agent.baml_parser import parse_hand_with_baml
from tools.calculator import calculate_score, validate_hand
from tools.entity import Hand
from tools.exceptions import HandValidationError, ScoreCalculationError

logger = logging.getLogger(__name__)


class QuestionValidator:
    """麻雀の問題と回答が正しいかをチェックするクラス（BAML統合版）"""

    def __init__(self, use_baml: bool = True):
        """
        Args:
            use_baml: BAMLでJSON→Hand型変換を行うか（デフォルト: True）
        """
        self.use_baml = use_baml

    async def validate_question(
        self, hand_json: str, expected_score: Optional[int] = None
    ) -> int:
        """
        麻雀の問題の回答が正しいかチェックする（非同期版 + BAML統合）

        Args:
            hand_json: Hand形式のJSON文字列
            expected_score: 期待される点数（オプション）。指定された場合、計算結果と一致するかチェックする

        Returns:
            int: 正しい場合は1、間違っている場合は0

        Raises:
            HandValidationError: 手牌の検証に失敗した場合
            ScoreCalculationError: 点数計算に失敗した場合
        """
        try:
            # BAMLでJSONをパース
            if self.use_baml:
                hand = await parse_hand_with_baml(hand_json)
            else:
                hand_data = json.loads(hand_json)
                hand = Hand(**hand_data)

            # 手牌の検証
            validate_hand(hand)

            # 点数計算
            result = calculate_score(hand)

            # エラーがある場合は0を返す
            if result.error:
                logger.error(f"Score calculation error: {result.error}")
                return 0

            # 期待される点数が指定されている場合、一致するかチェック
            if expected_score is not None:
                if result.score != expected_score:
                    logger.warning(
                        f"Score mismatch: expected {expected_score}, got {result.score}"
                    )
                    return 0

            logger.info(
                f"Validation successful: han={result.han}, fu={result.fu}, score={result.score}"
            )
            return 1

        except HandValidationError as e:
            logger.error(f"Hand validation error: {str(e)}")
            return 0
        except ScoreCalculationError as e:
            logger.error(f"Score calculation error: {str(e)}")
            return 0
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return 0

    async def validate_with_details(
        self, hand_json: str, expected_score: Optional[int] = None
    ) -> dict:
        """
        麻雀の問題の回答が正しいかチェックし、詳細情報を返す（非同期版 + BAML統合）

        Args:
            hand_json: Hand形式のJSON文字列
            expected_score: 期待される点数（オプション）

        Returns:
            dict: 検証結果の詳細
                - is_valid: 正しいかどうか (1 or 0)
                - han: 翻数
                - fu: 符
                - score: 点数
                - yaku: 役のリスト
                - error: エラーメッセージ（エラーがある場合）
        """
        try:
            # BAMLでJSONをパース
            if self.use_baml:
                hand = await parse_hand_with_baml(hand_json)
            else:
                hand_data = json.loads(hand_json)
                hand = Hand(**hand_data)

            # 手牌の検証
            validate_hand(hand)

            # 点数計算
            result = calculate_score(hand)

            # エラーがある場合
            if result.error:
                return {
                    "is_valid": 0,
                    "error": result.error,
                }

            # 期待される点数が指定されている場合、一致するかチェック
            is_valid = 1
            error_msg = None
            if expected_score is not None and result.score != expected_score:
                is_valid = 0
                error_msg = f"Score mismatch: expected {expected_score}, got {result.score}"

            response = {
                "is_valid": is_valid,
                "han": result.han,
                "fu": result.fu,
                "score": result.score,
                "yaku": result.yaku,
                "expected_score": expected_score,
            }

            if error_msg:
                response["error"] = error_msg

            return response

        except (HandValidationError, ScoreCalculationError, json.JSONDecodeError) as e:
            return {
                "is_valid": 0,
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return {
                "is_valid": 0,
                "error": f"Unexpected error: {str(e)}",
            }

    async def validate_batch(
        self, hand_jsons: list[str], expected_scores: Optional[list[Optional[int]]] = None
    ) -> list[dict]:
        """
        複数の麻雀問題を並列でバリデーションする（非同期版 + BAML統合）

        Args:
            hand_jsons: Hand形式のJSON文字列のリスト
            expected_scores: 期待される点数のリスト（オプション）

        Returns:
            list[dict]: 検証結果の詳細のリスト
        """
        if expected_scores is None:
            expected_scores = [None] * len(hand_jsons)

        if len(hand_jsons) != len(expected_scores):
            raise ValueError("hand_jsons and expected_scores must have the same length")

        # 1つのみの場合は並列化不要
        if len(hand_jsons) == 1:
            result = await self.validate_with_details(hand_jsons[0], expected_scores[0])
            return [result]

        logger.info(f"Validating {len(hand_jsons)} questions in parallel...")

        # 非同期タスクを並列実行
        tasks = [
            self.validate_with_details(hand_json, expected_score)
            for hand_json, expected_score in zip(hand_jsons, expected_scores)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 例外をエラー辞書に変換
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error validating question at index {i}: {str(result)}", exc_info=result)
                processed_results.append({
                    "is_valid": 0,
                    "error": f"Validation failed: {str(result)}",
                })
            else:
                processed_results.append(result)

        logger.info(f"Validated {len(hand_jsons)} questions in parallel")
        return processed_results


if __name__ == "__main__":
    # 使用例
    logging.basicConfig(level=logging.INFO)

    async def main():
        # テスト用の手牌（ピンフのみ）
        test_hand = {
            "tiles": [
                "1m",
                "2m",
                "3m",
                "4m",
                "5m",
                "6m",
                "7m",
                "8m",
                "9m",
                "1s",
                "2s",
                "3s",
                "4s",
                "4s",
            ],
            "win_tile": "4s",
            "is_tsumo": False,
            "is_riichi": True,
        }

        validator = QuestionValidator()
        hand_json = json.dumps(test_hand)

        # シンプルな検証
        result = await validator.validate_question(hand_json)
        print(f"Validation result: {result}")

        # 詳細な検証
        detailed_result = await validator.validate_with_details(hand_json)
        print(f"Detailed validation result: {detailed_result}")

    asyncio.run(main())
