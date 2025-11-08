import asyncio
import json
import logging
import os
from typing import Optional

from openai import OpenAI

from mahjong_ai_agent.baml_parser import parse_hand_with_baml
from tools.calculator import calculate_score, validate_hand
from baml.baml_client.types import Hand
from tools.exceptions import HandValidationError, ScoreCalculationError

logger = logging.getLogger(__name__)


class QuestionVerifier:
    """麻雀の問題と回答が正しいかをチェックするクラス（BAML統合版）"""

    def __init__(self, use_baml: bool = True):
        """
        Args:
            use_baml: BAMLでJSON→Hand型変換を行うか（デフォルト: True）
        """
        self.use_baml = use_baml

    async def verify_question(
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
                f"Verification successful: han={result.han}, fu={result.fu}, score={result.score}"
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

    async def verify_with_details(
        self, hand_json: str, expected_score: Optional[int] = None
    ) -> dict:
        """
        麻雀の問題の回答が正しいかチェックし、詳細情報を返す（非同期版 + BAML統合）

        Args:
            hand_json: Hand形式のJSON文字列
            expected_score: 期待される点数（オプション）

        Returns:
            dict: 検証結果の詳細
                - is_verified: 正しいかどうか (1 or 0)
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
                    "is_verified": 0,
                    "error": result.error,
                }

            # 期待される点数が指定されている場合、一致するかチェック
            is_verified = 1
            error_msg = None
            if expected_score is not None and result.score != expected_score:
                is_verified = 0
                error_msg = f"Score mismatch: expected {expected_score}, got {result.score}"

            response = {
                "is_verified": is_verified,
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

    async def verify_batch(
        self, hand_jsons: list[str], expected_scores: Optional[list[Optional[int]]] = None
    ) -> list[dict]:
        """
        複数の麻雀問題を並列で検証する（非同期版 + BAML統合）

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
            result = await self.verify_with_details(hand_jsons[0], expected_scores[0])
            return [result]

        logger.info(f"Verifying {len(hand_jsons)} questions in parallel...")

        # 非同期タスクを並列実行
        tasks = [
            self.verify_with_details(hand_json, expected_score)
            for hand_json, expected_score in zip(hand_jsons, expected_scores)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 例外をエラー辞書に変換
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error verifying question at index {i}: {str(result)}", exc_info=result)
                processed_results.append({
                    "is_verified": 0,
                    "error": f"Verification failed: {str(result)}",
                })
            else:
                processed_results.append(result)

        logger.info(f"Verified {len(hand_jsons)} questions in parallel")
        return processed_results

    async def judge_instruction_compliance(
        self, instruction: str, verification_details: dict
    ) -> str:
        """
        指示に従って問題が生成されているかを判定する

        Args:
            instruction: 問題生成時の指示
            verification_details: verify_with_detailsの返り値

        Returns:
            str: 判定結果（"Yes/No\n理由: ..."の形式）
        """
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = f"""生成された麻雀問題が指示に従っているかを評価してください。

指示: {instruction}

実際の結果:
- 計算された点数: {verification_details.get('score', 'N/A')}
- 翻数: {verification_details.get('han', 'N/A')}
- 符数: {verification_details.get('fu', 'N/A')}
- 役: {verification_details.get('yaku', [])}

判定基準:
指示に明記されている条件のみをチェックしてください。指示に含まれていない条件（点数、翻数、符数など）は判定に含めないでください。

例：
- 指示が「難易度hardで、暗刻が三つある問題を作成してください」の場合
  → 難易度がhardであること、暗刻が三つあること（役リストに三暗刻があるか）のみをチェック
  → 点数や翻数、符数は指示に含まれていないため無視する

- 指示が「タンヤオと三色同順で5200点の問題を作成してください」の場合
  → 役リストにタンヤオと三色同順が含まれているか、点数が5200点であることをチェック
  → 翻数や符数は指示に含まれていないため無視する

指示に明記されている全ての条件が満たされている場合のみ「Yes」、一つでも満たされていない場合は「No」と回答してください。
理由も簡潔に説明してください。

回答形式: Yes/No
理由: （簡潔な説明）"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        return response.choices[0].message.content


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

        verifier = QuestionVerifier()
        hand_json = json.dumps(test_hand)

        # シンプルな検証
        result = await verifier.verify_question(hand_json)
        print(f"Verification result: {result}")

        # 詳細な検証
        detailed_result = await verifier.verify_with_details(hand_json)
        print(f"Detailed verification result: {detailed_result}")

    asyncio.run(main())
