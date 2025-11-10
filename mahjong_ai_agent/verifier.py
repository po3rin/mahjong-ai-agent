import asyncio
import json
import logging
import os
from typing import Optional

from openai import OpenAI

from mahjong_ai_agent.baml_parser import parse_hand_with_baml, extract_hand_from_question
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
            if expected_score is not None and result.score != expected_score:
                logger.warning(
                    f"Score mismatch: expected {expected_score}, got {result.score}"
                )
                return 0

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

        return processed_results

    async def verify_from_question(
        self, question: str, instruction: Optional[str] = None, expected_score: Optional[int] = None
    ) -> dict:
        """
        問題文から検証まで一貫して処理する（BAML→Python→LLM-as-a-Judge）
        
        Args:
            question: 問題文（自然言語）
            instruction: 問題生成時の指示（LLM-as-a-Judgeで使用）
            expected_score: 期待される点数（オプション）
        
        Returns:
            dict: 検証結果の詳細
                - baml_extracted: BAML抽出が成功したか (bool)
                - baml_error: BAML抽出エラー（失敗時）
                - calculation_success: 点数計算が成功したか (bool)
                - calculation_error: 点数計算エラー（失敗時）
                - compliance_judged: LLM-as-a-Judgeが実行されたか (bool)
                - compliance_result: LLM-as-a-Judgeの結果（実行時）
                - is_verified: 正しいかどうか (1 or 0)
                - han: 翻数
                - fu: 符
                - score: 点数
                - yaku: 役のリスト
                - error: エラーメッセージ（エラーがある場合）
        """
        result = {
            'baml_extracted': False,
            'calculation_success': False,
            'compliance_judged': False,
            'is_verified': 0
        }
        
        # Step 1: BAML - 問題文からHand型を抽出
        try:
            hand = await extract_hand_from_question(question)
            if hand is None:
                result['baml_extracted'] = False
                result['baml_error'] = 'Hand extraction returned None'
                return result
            
            result['baml_extracted'] = True
            hand_json = hand.model_dump_json()
            result['hand_json'] = hand_json  # hand_jsonを結果に含める
        except Exception as e:
            result['baml_extracted'] = False
            result['baml_error'] = str(e)
            return result
        
        # Step 2: Python - 点数計算、役の特定、飜数、符数の計算
        try:
            # BAMLでJSONをパース
            if self.use_baml:
                hand_obj = await parse_hand_with_baml(hand_json)
            else:
                hand_data = json.loads(hand_json)
                hand_obj = Hand(**hand_data)
            
            # 手牌の検証
            validate_hand(hand_obj)
            
            # 点数計算
            calc_result = calculate_score(hand_obj)
            
            if calc_result.error:
                result['calculation_success'] = False
                result['calculation_error'] = calc_result.error
                return result
            
            result['calculation_success'] = True
            result['han'] = calc_result.han
            result['fu'] = calc_result.fu
            result['score'] = calc_result.score
            result['yaku'] = calc_result.yaku
            
            # 期待される点数が指定されている場合、一致するかチェック
            if expected_score is not None and calc_result.score != expected_score:
                result['is_verified'] = 0
                result['error'] = f"Score mismatch: expected {expected_score}, got {calc_result.score}"
            else:
                result['is_verified'] = 1
                
        except (HandValidationError, ScoreCalculationError, json.JSONDecodeError) as e:
            result['calculation_success'] = False
            result['calculation_error'] = str(e)
            return result
        except Exception as e:
            result['calculation_success'] = False
            result['calculation_error'] = f"Unexpected error: {str(e)}"
            return result
        
        # Step 3: LLM-as-a-Judge - 指示適合性を判定
        if instruction and result['calculation_success']:
            try:
                verification_details = {
                    'han': result.get('han'),
                    'fu': result.get('fu'),
                    'score': result.get('score'),
                    'yaku': result.get('yaku', [])
                }
                compliance_result = await self.judge_instruction_compliance(instruction, verification_details)
                result['compliance_judged'] = True
                result['compliance_result'] = compliance_result
            except Exception as e:
                result['compliance_judged'] = False
                result['compliance_error'] = str(e)
        
        return result

    async def verify_batch_from_questions(
        self, questions: list[str], instructions: Optional[list[Optional[str]]] = None,
        expected_scores: Optional[list[Optional[int]]] = None
    ) -> list[dict]:
        """
        複数の問題文を並列で検証する（BAML→Python→LLM-as-a-Judge）
        
        Args:
            questions: 問題文のリスト
            instructions: 問題生成時の指示のリスト（オプション）
            expected_scores: 期待される点数のリスト（オプション）
        
        Returns:
            list[dict]: 検証結果の詳細のリスト
        """
        if instructions is None:
            instructions = [None] * len(questions)
        if expected_scores is None:
            expected_scores = [None] * len(questions)
        
        if len(questions) != len(instructions) or len(questions) != len(expected_scores):
            raise ValueError("questions, instructions, and expected_scores must have the same length")
        
        # 1つのみの場合は並列化不要
        if len(questions) == 1:
            result = await self.verify_from_question(questions[0], instructions[0], expected_scores[0])
            return [result]

        # 非同期タスクを並列実行
        tasks = [
            self.verify_from_question(question, instruction, expected_score)
            for question, instruction, expected_score in zip(questions, instructions, expected_scores)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 例外をエラー辞書に変換
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error verifying question at index {i}: {str(result)}", exc_info=result)
                processed_results.append({
                    "baml_extracted": False,
                    "baml_error": f"Exception: {str(result)}",
                    "calculation_success": False,
                    "compliance_judged": False,
                    "is_verified": 0,
                })
            else:
                processed_results.append(result)

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

        yaku_list = verification_details.get('yaku', [])
        prompt = f"""生成された麻雀問題が指示に従っているかを評価してください。

指示: {instruction}

実際の結果:
- 計算された点数: {verification_details.get('score', 'N/A')}
- 翻数: {verification_details.get('han', 'N/A')}
- 符数: {verification_details.get('fu', 'N/A')}
- 役: {yaku_list}

**重要: 役名の日本語・英語対応表**
- Toitoi = 対々和
- Tanyao = タンヤオ/断么九
- Pinfu = ピンフ/平和
- Iipeiko = イーペーコー/一盃口
- Ryanpeikou = リャンペーコー/二盃口
- Sanshoku = 三色同順
- Sanshoku Dokou = 三色同刻
- Ittsu = イッツー/一気通貫
- Chiitoitsu = チートイツ/七対子
- Honitsu = ホンイツ/混一色
- Chinitsu = チンイツ/清一色
- Honroutou = 混老頭
- Chanta = チャンタ/混全帯么九
- Junchan = ジュンチャン/純全帯么九
- Yakuhai = 役牌 (haku=白, hatsu=発, chun=中, wind of place=自風, wind of round=場風)
- Sanankou = サンアンコー/三暗刻
- Sankantsu = サンカンツ/三槓子
- Shousangen = ショウサンゲン/小三元
- Dora = ドラ
- Riichi = リーチ/立直
- Ippatsu = イッパツ/一発
- Rinshan kaihou = リンシャンカイホー/嶺上開花
- Chankan = チャンカン/槍槓
- Haitei raoyue = ハイテイ/海底摸月
- Houtei raoyui = ホウテイ/河底撈魚
- Double riichi = ダブルリーチ/ダブル立直
- Tenhou = 天和
- Chiihou = 地和

判定基準:
指示に明記されている条件のみをチェックしてください。指示に含まれていない条件（点数、翻数、符数など）は判定に含めないでください。

例：
- 指示が「難易度hardで、暗刻が三つある問題を作成してください」の場合
  → 難易度がhardであること、暗刻が三つあること（役リストに「Sanankou」があるか）のみをチェック
  → 点数や翻数、符数は指示に含まれていないため無視する

- 指示が「タンヤオと三色同順で5200点の問題を作成してください」の場合
  → 役リストに「Tanyao」と「Sanshoku」が含まれているか、点数が5200点であることをチェック
  → 翻数や符数は指示に含まれていないため無視する

- 指示が「対々和の問題を作成してください」の場合
  → 役リストに「Toitoi」という文字列が含まれているかをチェック
  → 点数や翻数、符数は指示に含まれていないため無視する

**重要な注意事項:**
- 役リストは配列形式で渡されます（例: ['Yakuhai (haku)', 'Toitoi', 'Dora']）
- 配列の要素を一つずつ確認して、指定された役が含まれているか判定してください
- 大文字小文字を区別せずに判定してください

指示に明記されている全ての条件が満たされている場合のみ「Yes」、一つでも満たされていない場合は「No」と回答してください。
理由も簡潔に説明してください。

**重要: 回答形式を厳密に守ってください**
回答は必ず以下の形式で出力してください。最初の行には「Yes」または「No」という単語のみを出力してください（「回答形式:」などのプレフィックスは不要です）。2行目以降に理由を記載してください。

回答形式:
Yes
理由: （簡潔な説明）

または

No
理由: （簡潔な説明）

**注意: 最初の行には「Yes」または「No」という単語のみを出力してください。他の文字列（「回答形式:」など）は含めないでください。**"""

        response = client.chat.completions.create(
            model="gpt-4o",  # より高性能なモデルに変更
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )

        raw_response = response.choices[0].message.content.strip()

        # レスポンスをパースして、最初の行から「Yes」または「No」を正確に抽出
        lines = [line.strip() for line in raw_response.split('\n') if line.strip()]
        first_line = lines[0] if lines else ""

        # 最初の行から「Yes」または「No」を抽出
        # プレフィックス（「回答形式:」「回答形式」など）を除去
        first_line_clean = first_line
        for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
            if first_line_clean.startswith(prefix):
                first_line_clean = first_line_clean[len(prefix):].strip()
                break

        # 「Yes」または「No」を抽出（大文字小文字を区別しない）
        first_line_upper = first_line_clean.upper()
        if first_line_upper.startswith('YES'):
            status = "Yes"
        elif first_line_upper.startswith('NO'):
            status = "No"
        else:
            # 最初の行に「Yes」または「No」がない場合、レスポンス全体から検索
            response_upper = raw_response.upper()
            # プレフィックスを除去
            response_clean = raw_response
            for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
                response_clean = response_clean.replace(prefix, '').strip()

            response_clean_upper = response_clean.upper()
            # 「Yes」と「No」の最初の出現位置を確認
            yes_pos = response_clean_upper.find("YES")
            no_pos = response_clean_upper.find("NO")

            if yes_pos != -1 and (no_pos == -1 or yes_pos < no_pos):
                status = "Yes"
            elif no_pos != -1:
                status = "No"
            else:
                # どちらも見つからない場合は、最初の行をそのまま使用（フォールバック）
                status = first_line_clean or "Unknown"

        reason = next(
            (
                line.split(':', 1)[-1].strip() if ':' in line else line.strip()
                for line in lines[1:]
                if '理由' in line or 'reason' in line.lower()
            ),
            "",
        )
        # 理由が見つからない場合は、2行目以降をすべて理由として使用
        if not reason and len(lines) > 1:
            reason = '\n'.join(lines[1:]).strip()

        # フォーマットされたレスポンスを返す
        return f"{status}\n理由: {reason}" if reason else status


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
