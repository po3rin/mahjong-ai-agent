import json
import logging
from typing import List

from mahjong.hand_calculating.hand import HandCalculator
from mahjong.hand_calculating.hand_config import HandConfig
from mahjong.meld import Meld
from mahjong.tile import TilesConverter

from tools.entity import Hand, MeldInfo, ScoreResponse
from tools.exceptions import HandValidationError, ScoreCalculationError

logger = logging.getLogger(__name__)


def convert_tiles_to_136_array(tiles: List[str]) -> List[int]:
    """
    牌の表記を136形式の配列に変換する

    Args:
        tiles: 牌のリスト (例: ["1m", "2m", "3m"])

    Returns:
        List[int]: 136形式の配列
    """
    man = ""
    pin = ""
    sou = ""
    honors = ""

    for tile in tiles:
        if tile.endswith("m"):
            man += tile[0]
        elif tile.endswith("p"):
            pin += tile[0]
        elif tile.endswith("s"):
            sou += tile[0]
        elif tile.endswith("z"):
            honors += tile[0]

    result = TilesConverter.string_to_136_array(
        man=man, pin=pin, sou=sou, honors=honors
    )
    return result


def convert_melds_to_mahjong_format(
    melds: List[MeldInfo],
) -> List[Meld]:
    """
    鳴きの情報をMahjongライブラリの形式に変換する

    Args:
        melds: MeldInfo形式の鳴きの情報のリスト

    Returns:
        List[Meld]: Mahjongライブラリの形式の鳴き情報
    """
    result = []
    for meld in melds:
        if not isinstance(meld, MeldInfo):
            raise ValueError(
                f"メルドはMeldInfo型である必要があります。受け取った型: {type(meld)}"
            )

        tiles = convert_tiles_to_136_array(meld.tiles)
        meld_type = _detect_meld_type(meld.tiles)
        # カンの場合はis_openを使用、それ以外は常にTrue
        is_open = meld.is_open if meld_type == Meld.KAN else True
        result.append(Meld(meld_type=meld_type, tiles=tiles, opened=is_open))
    return result


def _detect_meld_type(tiles: List[str]) -> str:
    """
    牌のリストから鳴きの種類を判定する

    Args:
        tiles: 牌のリスト

    Returns:
        str: 鳴きの種類 (Meld.CHI, Meld.PON, Meld.KAN)
    """
    if len(tiles) == 4:
        # 4枚の場合はカン
        return Meld.KAN
    elif len(tiles) == 3:
        # 同じ牌3枚ならポン
        if tiles[0] == tiles[1] == tiles[2]:
            return Meld.PON
        # 連続する3枚ならチー
        else:
            return Meld.CHI
    else:
        # それ以外はエラー（通常はありえない）
        raise ValueError(f"Invalid meld size: {len(tiles)}")


def calculate_score(hand: Hand) -> ScoreResponse:
    """
    麻雀の点数を計算する

    Args:
        hand: 手牌の情報
        melds: 鳴きの情報

    Returns:
        ScoreResponse: 点数計算結果
    """
    try:
        calculator = HandCalculator()

        # 鳴きの情報を変換
        mahjong_melds = (
            convert_melds_to_mahjong_format(hand.melds) if hand.melds else []
        )

        # 手牌を136形式に変換（全ての牌を含める）
        tiles = convert_tiles_to_136_array(hand.tiles)

        # 和了牌を変換
        win_tile = convert_tiles_to_136_array([hand.win_tile])[0]

        # ドラ表示牌を変換
        dora_indicators = (
            convert_tiles_to_136_array(hand.dora_indicators)
            if hand.dora_indicators
            else []
        )
        logger.debug(f"Converted dora indicators: {dora_indicators}")

        # 設定を準備
        config = HandConfig(
            is_riichi=hand.is_riichi,
            is_tsumo=hand.is_tsumo,
            is_ippatsu=hand.is_ippatsu,
            is_rinshan=hand.is_rinshan,
            is_chankan=hand.is_chankan,
            is_haitei=hand.is_haitei,
            is_houtei=hand.is_houtei,
            is_daburu_riichi=hand.is_daburu_riichi,
            is_nagashi_mangan=hand.is_nagashi_mangan,
            is_tenhou=hand.is_tenhou,
            is_chiihou=hand.is_chiihou,
            is_open_riichi=hand.is_open_riichi,
            player_wind=hand.player_wind,
            round_wind=hand.round_wind,
            paarenchan=hand.paarenchan,
            kyoutaku_number=hand.kyoutaku_number,
            tsumi_number=hand.tsumi_number,
        )

        # 点数計算
        result = calculator.estimate_hand_value(
            tiles,
            win_tile,
            melds=mahjong_melds,
            dora_indicators=dora_indicators,
            config=config,
        )

        # 結果を変換
        if result is None:
            logger.error("No valid hand found")
            return ScoreResponse(
                han=0, fu=0, score=0, yaku=[], error="No valid hand found"
            )

        # 役がない場合もエラーとする
        if not result.yaku or len(result.yaku) == 0:
            logger.error("No valid yaku found")
            return ScoreResponse(
                han=result.han,
                fu=result.fu,
                score=result.cost["main"] if result.cost else 0,
                yaku=[],
                error="No valid yaku found",
            )

        return ScoreResponse(
            han=result.han,
            fu=result.fu,
            score=result.cost["main"] if result.cost else 0,
            yaku=[yaku.name for yaku in result.yaku] if result.yaku else [],
            fu_details=result.fu_details,
        )

    except Exception as e:
        logger.error(
            f"Error during score calculation: {str(e)}, result: {result if result else 'None'}",
            exc_info=True,
        )
        raise ScoreCalculationError(f"Error during score calculation: {str(e)}") from e


def validate_tiles(tiles: List[str]) -> bool:
    """
    牌の形式が正しいかチェックする

    Args:
        tiles: 牌のリスト

    Returns:
        bool: 正しい形式かどうか
    """
    try:
        logger.debug(f"Validating tiles: {tiles}")
        convert_tiles_to_136_array(tiles)
        return True
    except Exception as e:
        logger.error(f"Invalid tile format: {str(e)}")
        return False


def validate_meld(tiles: List[str], melds: List[MeldInfo]) -> bool:
    """
    鳴きの形式が正しいかチェックする

    Args:
        tiles: 手牌のリスト
        melds: MeldInfo形式の鳴きのリスト

    Returns:
        bool: 正しい形式かどうか
    """
    try:
        # 各鳴きを検証
        for meld in melds:
            if not isinstance(meld, MeldInfo):
                logger.error(
                    f"メルドはMeldInfo型である必要があります。受け取った型: {type(meld)}"
                )
                return False
            convert_tiles_to_136_array(meld.tiles)
    except Exception as e:
        logger.error(f"Invalid meld format: {str(e)}")
        return False

    # meldsに存在する牌は全てtilesに含まれているべき（枚数も正しくカウント）
    from collections import Counter
    tiles_counter = Counter(tiles)

    for meld in melds:
        meld_counter = Counter(meld.tiles)
        for tile, count in meld_counter.items():
            if tiles_counter.get(tile, 0) < count:
                logger.error(f"Invalid meld in hand. melds is not valid: {meld.tiles} - tile '{tile}' appears {count} times in meld but only {tiles_counter.get(tile, 0)} times in hand")
                return False
    return True


def validate_hand(hand: Hand):
    # Handle error cases where hand has empty tiles
    if not hand.tiles:
        raise HandValidationError("Invalid tile format in tiles. tiles is required")

    # 手牌の形式チェック
    if not validate_tiles(hand.tiles):
        raise HandValidationError("Invalid tile format in tiles. tiles is not valid")

    # ドラ表示牌の形式チェック
    if hand.dora_indicators and not validate_tiles(hand.dora_indicators):
        raise HandValidationError(
            "Invalid tile format in dora indicators. dora_indicators is not valid"
        )

    # 鳴きの形式チェック
    if hand.melds and not validate_meld(hand.tiles, hand.melds):
        raise HandValidationError("Invalid meld in hand. melds is not valid")

    # 手牌の枚数チェック
    if hand.tiles and len(hand.tiles) < 14:
        raise HandValidationError("Invalid tile count in hand. tiles is less than 14")

    # 和了牌の形式チェック
    if hand.win_tile and hand.win_tile not in hand.tiles:
        raise HandValidationError("Invalid win tile in hand. win_tile is not in tiles")


def calculate_score_with_json(json_str: str) -> ScoreResponse:
    hand_data = json.loads(json_str)
    hand = Hand(**hand_data)
    validate_hand(hand)
    return calculate_score(hand)
