from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MeldInfo(BaseModel):
    tiles: List[str] = Field(
        ...,
        description="Meld tiles. Array in 136 format. Examples: ['1m', '2m', '3m'] (Chii), ['5p', '5p', '5p'] (Pon), ['1z', '1z', '1z', '1z'] (Kan)",
    )
    is_open: bool = Field(
        True,
        description="Whether the meld is open or closed. True: Open meld (Minkan, Pon, Chii), False: Closed meld (Ankan only). Note: Pon and Chii are always open (True), only Kan can be closed (False).",
    )


class Hand(BaseModel):
    tiles: List[str] = Field(
        ...,
        description="""Array in 136 format representing the hand at the time of winning.
        Important: Must include all tiles in the hand, including those specified in melds.
        Example: For 10 hand tiles + 4 Ankan tiles + 1 winning tile, specify all 15 tiles like tiles=['1m', '2m', '3m', '4m', '4m', '5p', '5p', '5p', '7p', '8p', '1z', '1z', '1z', '1z', '1s'].
""",
    )
    melds: Optional[List[MeldInfo]] = Field(
        None,
        description="""Meld information. Only MeldInfo format supported:
        MeldInfo(tiles=['1z', '1z', '1z', '1z'], is_open=False)
        - tiles: Meld tiles (136 format). These tiles must also be included in the tiles field.
        - is_open: True=Open meld (Minkan, Pon, Chii), False=Closed meld (Ankan only). Note: Pon/Chii are always True, only Kan can be False
        
        Important: Tiles specified in melds must also be included in the tiles field.
        Example: For Ankan
            tiles=['1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '1s', '1z', '1z', '1z', '1z', '1s'] (15 tiles)
            melds=[MeldInfo(tiles=['1z', '1z', '1z', '1z'], is_open=False)]
            win_tile='1s'
""",
    )
    win_tile: str = Field(..., description="Winning tile. Example: '1m'")
    dora_indicators: Optional[List[str]] = Field(
        None, description="List of dora indicator tiles"
    )
    is_riichi: bool = Field(
        False,
        description="Whether riichi has been declared. Cannot riichi after calling. Always False when melds is not None.",
    )
    is_tsumo: bool = Field(False, description="Whether it's a self-draw win (tsumo)")
    is_ippatsu: bool = Field(False, description="Whether it's ippatsu")
    is_rinshan: bool = Field(False, description="Whether it's rinshan kaihou")
    is_chankan: bool = Field(False, description="Whether it's chankan")
    is_haitei: bool = Field(False, description="Whether it's haitei raoyue")
    is_houtei: bool = Field(False, description="Whether it's houtei raoyui")
    is_daburu_riichi: bool = Field(False, description="Whether it's double riichi")
    is_nagashi_mangan: bool = Field(False, description="Whether it's nagashi mangan")
    is_tenhou: bool = Field(False, description="Whether it's tenhou (heavenly hand)")
    is_chiihou: bool = Field(False, description="Whether it's chiihou (earthly hand)")
    is_renhou: bool = Field(False, description="Whether it's renhou (hand of man)")
    is_open_riichi: bool = Field(False, description="Whether it's open riichi")
    player_wind: Optional[str] = Field(
        None, description="Player wind (east, south, west, north)"
    )
    round_wind: Optional[str] = Field(
        None, description="Round wind (east, south, west, north)"
    )
    paarenchan: int = Field(0, description="Number of paarenchan")
    kyoutaku_number: int = Field(
        0, description="Number of riichi deposits (in 1000 point units)"
    )
    tsumi_number: int = Field(
        0, description="Number of continuation sticks (in 100 point units)"
    )


class ScoreRequest(BaseModel):
    hand: Hand


class ScoreResponse(BaseModel):
    han: Optional[int] = Field(None, description="Number of han")
    fu: Optional[int] = Field(None, description="Number of fu")
    score: Optional[int] = Field(None, description="Score points")
    yaku: Optional[List[str]] = Field(None, description="List of yaku")
    fu_details: Optional[List[Dict[str, Any]]] = Field(
        None, description="Fu calculation details"
    )
    error: Optional[str] = Field(None, description="Error message")
