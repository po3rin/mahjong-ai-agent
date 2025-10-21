"""BAMLを使って問題文やJSON文字列をHand型に確実にパースするモジュール"""
import json
import logging
import os
from typing import Optional

from baml.baml_client import b as async_b
from baml.baml_client.sync_client import b as sync_b
from baml.baml_client.types import Hand as BAMLHand, MeldInfo as BAMLMeldInfo
from tools.entity import Hand, MeldInfo

# BAMLのINFOログを抑制（エラーログのみ表示）
os.environ.setdefault('BAML_LOG', 'error')

logger = logging.getLogger(__name__)


def baml_hand_to_entity_hand(baml_hand: BAMLHand) -> Hand:
    """
    BAMLのHand型をtools.entity.Hand型に変換する

    Args:
        baml_hand: BAMLが生成したHand型

    Returns:
        Hand: tools/entity.pyのHand型
    """
    # MeldInfoの変換
    melds = None
    if baml_hand.melds is not None:
        melds = [
            MeldInfo(tiles=meld.tiles, is_open=meld.is_open)
            for meld in baml_hand.melds
        ]

    return Hand(
        tiles=baml_hand.tiles,
        melds=melds,
        win_tile=baml_hand.win_tile,
        dora_indicators=baml_hand.dora_indicators,
        is_riichi=baml_hand.is_riichi,
        is_tsumo=baml_hand.is_tsumo,
        is_ippatsu=baml_hand.is_ippatsu,
        is_rinshan=baml_hand.is_rinshan,
        is_chankan=baml_hand.is_chankan,
        is_haitei=baml_hand.is_haitei,
        is_houtei=baml_hand.is_houtei,
        is_daburu_riichi=baml_hand.is_daburu_riichi,
        is_nagashi_mangan=baml_hand.is_nagashi_mangan,
        is_tenhou=baml_hand.is_tenhou,
        is_chiihou=baml_hand.is_chiihou,
        is_renhou=baml_hand.is_renhou,
        is_open_riichi=baml_hand.is_open_riichi,
        player_wind=baml_hand.player_wind,
        round_wind=baml_hand.round_wind,
        paarenchan=baml_hand.paarenchan,
        kyoutaku_number=baml_hand.kyoutaku_number,
        tsumi_number=baml_hand.tsumi_number,
    )


async def parse_hand_with_baml(hand_json: str) -> Hand:
    """
    BAMLを使ってJSON文字列を確実にHand型にパースする

    Args:
        hand_json: Hand形式のJSON文字列

    Returns:
        Hand: パース済みのHand型オブジェクト

    Raises:
        Exception: パースに失敗した場合
    """
    try:
        logger.info("Parsing hand JSON with BAML...")

        # BAMLで構造化パース（非同期版）
        baml_hand = await async_b.ParseHandFromJSON(hand_json)

        # tools/entity.Hand型に変換
        hand = baml_hand_to_entity_hand(baml_hand)

        logger.info("Successfully parsed hand with BAML")
        return hand

    except Exception as e:
        logger.error(f"BAML parsing failed: {str(e)}")
        # フォールバック: 従来のJSONパース（エラー時のみ）
        logger.warning("Falling back to standard JSON parsing...")
        hand_data = json.loads(hand_json)
        return Hand(**hand_data)


def parse_hand_with_baml_sync(hand_json: str) -> Hand:
    """
    BAMLを使ってJSON文字列を確実にHand型にパースする（同期版）

    Args:
        hand_json: Hand形式のJSON文字列

    Returns:
        Hand: パース済みのHand型オブジェクト

    Raises:
        Exception: パースに失敗した場合
    """
    try:
        logger.info("Parsing hand JSON with BAML (sync)...")

        # BAMLの同期クライアントを使用
        baml_hand = sync_b.ParseHandFromJSON(hand_json)

        # tools/entity.Hand型に変換
        hand = baml_hand_to_entity_hand(baml_hand)

        logger.info("Successfully parsed hand with BAML (sync)")
        return hand

    except Exception as e:
        logger.error(f"BAML parsing failed: {str(e)}")
        # フォールバック: 従来のJSONパース（エラー時のみ）
        logger.warning("Falling back to standard JSON parsing...")
        hand_data = json.loads(hand_json)
        return Hand(**hand_data)


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
        logger.info("Extracting hand from question with BAML...")

        # BAMLで問題文から構造化データを抽出（非同期版）
        baml_hand = await async_b.ExtractHandFromQuestion(question)

        # tools/entity.Hand型に変換
        hand = baml_hand_to_entity_hand(baml_hand)

        logger.info("Successfully extracted hand from question with BAML")
        return hand

    except Exception as e:
        # エラーメッセージを簡潔に（プロンプト全文は含めない）
        error_msg = str(e).split('\nPrompt:')[0]  # プロンプト以降を削除
        logger.error(f"BAML extraction failed: {error_msg[:200]}")
        # 例外を投げずにNoneを返す（処理を続行）
        return None
