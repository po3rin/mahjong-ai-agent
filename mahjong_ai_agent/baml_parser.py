"""BAMLを使って問題文やJSON文字列をHand型に確実にパースするモジュール"""
import json
import logging
import os

from baml.baml_client import b as async_b
from baml.baml_client.sync_client import b as sync_b
from baml.baml_client.types import Hand

# BAMLのINFOログを抑制（エラーログのみ表示）
os.environ.setdefault('BAML_LOG', 'error')

logger = logging.getLogger(__name__)


async def parse_hand_with_baml(hand_json: str) -> Hand:
    """
    JSON文字列を確実にHand型にパースする

    Note: 以前はBAMLのParseHandFromJSONを使っていたが、
    LLMがwin_tileをtilesに追加してしまう問題があったため、
    直接JSONパースに変更

    Args:
        hand_json: Hand形式のJSON文字列

    Returns:
        Hand: パース済みのHand型オブジェクト

    Raises:
        Exception: パースに失敗した場合
    """
    try:
        # 直接JSONパース（BAMLを使わない）
        hand_data = json.loads(hand_json)
        return Hand(**hand_data)

    except Exception as e:
        logger.error(f"JSON parsing failed: {str(e)}")
        raise


def parse_hand_with_baml_sync(hand_json: str) -> Hand:
    """
    JSON文字列を確実にHand型にパースする（同期版）

    Note: 以前はBAMLのParseHandFromJSONを使っていたが、
    LLMがwin_tileをtilesに追加してしまう問題があったため、
    直接JSONパースに変更

    Args:
        hand_json: Hand形式のJSON文字列

    Returns:
        Hand: パース済みのHand型オブジェクト

    Raises:
        Exception: パースに失敗した場合
    """
    try:
        # 直接JSONパース（BAMLを使わない）
        hand_data = json.loads(hand_json)
        return Hand(**hand_data)

    except Exception as e:
        logger.error(f"JSON parsing failed: {str(e)}")
        raise


async def extract_hand_from_question(question: str) -> Hand:
    """
    BAMLを使って自然言語の問題文からHand型を抽出する

    Args:
        question: 麻雀問題の問題文（日本語）

    Returns:
        Hand: 抽出されたHand型オブジェクト

    Raises:
        Exception: 抽出に失敗した場合
    """
    try:
        # BAMLで問題文から構造化データを抽出（非同期版）
        hand = await async_b.ExtractHandFromQuestion(question)

        # 修正: カンがない場合に15枚以上の場合、win_tileが重複している可能性があるので修正
        has_kan = hand.melds and any(len(meld.tiles) == 4 for meld in hand.melds)
        if (
            not has_kan
            and len(hand.tiles) > 14
            and hand.tiles[-1] == hand.win_tile
        ):
            logger.warning(f"Detected duplicate win_tile at end of tiles. Removing last tile. Before: {len(hand.tiles)} tiles")
            hand.tiles = hand.tiles[:-1]

        return hand

    except Exception as e:
        # エラーメッセージを簡潔に（プロンプト全文は含めない）
        error_msg = str(e).split('\nPrompt:')[0]  # プロンプト以降を削除
        logger.error(f"BAML extraction failed: {error_msg[:200]}")
        # 例外を投げずにNoneを返す（処理を続行）
        return None
