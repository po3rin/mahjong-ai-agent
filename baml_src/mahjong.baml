// BAML型定義: 麻雀の手牌構造

// 自動生成ファイルの出力先設定
generator baml_client {
  output_type "python/pydantic"
  output_dir "../baml"
  version "0.211.2"
}

// 牌の種類を列挙型で定義
enum TileType {
  // 萬子（マンズ）
  ONE_M @alias("1m")
  TWO_M @alias("2m")
  THREE_M @alias("3m")
  FOUR_M @alias("4m")
  FIVE_M @alias("5m")
  SIX_M @alias("6m")
  SEVEN_M @alias("7m")
  EIGHT_M @alias("8m")
  NINE_M @alias("9m")

  // 筒子（ピンズ）
  ONE_P @alias("1p")
  TWO_P @alias("2p")
  THREE_P @alias("3p")
  FOUR_P @alias("4p")
  FIVE_P @alias("5p")
  SIX_P @alias("6p")
  SEVEN_P @alias("7p")
  EIGHT_P @alias("8p")
  NINE_P @alias("9p")

  // 索子（ソーズ）
  ONE_S @alias("1s")
  TWO_S @alias("2s")
  THREE_S @alias("3s")
  FOUR_S @alias("4s")
  FIVE_S @alias("5s")
  SIX_S @alias("6s")
  SEVEN_S @alias("7s")
  EIGHT_S @alias("8s")
  NINE_S @alias("9s")

  // 字牌
  EAST @alias("1z")   // 東
  SOUTH @alias("2z")  // 南
  WEST @alias("3z")   // 西
  NORTH @alias("4z")  // 北
  WHITE @alias("5z")  // 白
  GREEN @alias("6z")  // 発
  RED @alias("7z")    // 中
}

// 風牌の種類
enum WindType {
  EAST @alias("east")
  SOUTH @alias("south")
  WEST @alias("west")
  NORTH @alias("north")
}

// 鳴き(メンツ)の情報
class MeldInfo {
  tiles TileType[] @description("鳴いた牌のリスト (例: ['1m', '2m', '3m'])")
  is_open bool @description("true: 鳴き(ポン/チー/明カン), false: 暗カン")
}

// 麻雀の手牌情報
class Hand {
  tiles TileType[] @description("手牌の牌リスト。和了牌(win_tile)を含む14枚。鳴いた牌は含めない。形式: '1m', '2p', '3s', '1z'など") @assert(min_tiles, {{ this|length >= 14 }})
  melds MeldInfo[] | null @description("鳴いた牌のリスト。ポン/チー/カンがある場合に設定。ない場合はnull")
  win_tile TileType @description("アガリ牌。tilesにも含まれている必要がある (例: '1m')")
  dora_indicators TileType[] | null @description("ドラ表示牌のリスト")
  // 状況フラグ(デフォルト: false)
  is_riichi bool @description("リーチをかけているか")
  is_tsumo bool @description("ツモアガリか(falseの場合はロン)")
  is_ippatsu bool @description("一発か")
  is_rinshan bool @description("嶺上開花か")
  is_chankan bool @description("槍槓か")
  is_haitei bool @description("海底摸月か")
  is_houtei bool @description("河底撈魚か")
  is_daburu_riichi bool @description("ダブルリーチか")
  is_nagashi_mangan bool @description("流し満貫か")
  is_tenhou bool @description("天和か")
  is_chiihou bool @description("地和か")
  is_renhou bool @description("人和か")
  is_open_riichi bool @description("オープンリーチか")
  player_wind WindType | null @description("自風: 'east'(東家), 'south'(南家), 'west'(西家), 'north'(北家)")
  round_wind WindType | null @description("場風: 'east'(東場), 'south'(南場), 'west'(西場), 'north'(北場)")
  paarenchan int @description("本場数")
  kyoutaku_number int @description("供託本数")
  tsumi_number int @description("積み棒の数")
}

// OpenAI GPTクライアント設定
client<llm> GPT4oMini {
  provider openai
  options {
    model "gpt-4o-mini"
    api_key env.OPENAI_API_KEY
  }
}

// JSON文字列を確実にHand型に変換する関数
function ParseHandFromJSON(json_string: string) -> Hand {
  client GPT4oMini
  prompt #"
    以下のJSON文字列をHand型のオブジェクトに変換してください。
    不足しているフィールドはデフォルト値で埋めてください。

    入力JSON:
    {{ json_string }}

    出力に含める必須フィールド:
    - tiles: 牌の配列。和了牌(win_tile)を含む14枚。
    - melds: nullまたはMeldInfoの配列
    - win_tile: アガリ牌。tilesの中にも必ず含まれている必要がある。
    - dora_indicators: nullまたはドラ表示牌の配列
    - is_riichi, is_tsumo, is_ippatsu, is_rinshan, is_chankan, is_haitei, is_houtei, is_daburu_riichi, is_nagashi_mangan, is_tenhou, is_chiihou, is_renhou, is_open_riichi: boolean型 (デフォルト: false)
    - player_wind, round_wind: nullまたは文字列 (east/south/west/north)
    - paarenchan, kyoutaku_number, tsumi_number: 整数 (デフォルト: 0)

    重要: win_tileはtilesの中に必ず存在する必要があります。

    Hand型に適合する有効なJSONオブジェクトとして出力してください。
    コメントや説明文は含めないでください。
    JSONオブジェクトのみを出力してください。
  "#
}

// 自然言語の問題文から手牌データを構造化抽出する関数
function ExtractHandFromQuestion(question: string) -> Hand {
  client GPT4oMini
  prompt #"
    以下の日本語の麻雀問題文から手牌情報を抽出し、完全なJSONオブジェクトとして出力してください。

    問題文:
    {{ question }}

    出力形式(全てのフィールドを含めること):
    {
      "tiles": [...],  // 問題文から抽出した手牌。和了牌を含む14枚。鳴いた牌は含めない。
      "melds": null,  // 鳴き情報。ポン/チー/カンがある場合は配列で設定
      "win_tile": "...",  // アガリ牌。tilesの中にも必ず含まれている必要がある。
      "dora_indicators": null,  // ドラ表示牌がある場合は配列で設定
      "is_riichi": false,  // リーチが言及されていればtrue
      "is_tsumo": false,  // ツモ/自摸ならtrue、ロンならfalse
      "is_ippatsu": false,  // 一発が言及されていない限りfalse
      "is_rinshan": false,  // 嶺上開花が言及されていない限りfalse
      "is_chankan": false,  // 槍槓が言及されていない限りfalse
      "is_haitei": false,  // 海底摸月が言及されていない限りfalse
      "is_houtei": false,  // 河底撈魚が言及されていない限りfalse
      "is_daburu_riichi": false,  // ダブルリーチが言及されていない限りfalse
      "is_nagashi_mangan": false,  // 流し満貫が言及されていない限りfalse
      "is_tenhou": false,  // 天和が言及されていない限りfalse
      "is_chiihou": false,  // 地和が言及されていない限りfalse
      "is_renhou": false,  // 人和が言及されていない限りfalse
      "is_open_riichi": false,  // オープンリーチが言及されていない限りfalse
      "player_wind": null,  // 東家なら"east", 南家なら"south", 西家なら"west", 北家なら"north"
      "round_wind": null,  // 東場なら"east", 南場なら"south", 西場なら"west", 北場なら"north"
      "paarenchan": 0,  // "X本場"から抽出
      "kyoutaku_number": 0,  // 供託本数(言及されていない限り0)
      "tsumi_number": 0  // 積み棒の数(言及されていない限り0)
    }

    tilesとwin_tileの関係について重要な注意事項:
    - tilesは和了牌(win_tile)を含む14枚である必要があります
    - win_tileはtilesの中に必ず存在する必要があります

    和了形のパターン:
    1. 通常の和了形（4面子1雀頭）:
       例: 手牌「1m, 2m, 3m, 4m, 5m, 6m, 7m, 8m, 9m, 1p, 1p, 1p, 1s, 1s」で和了牌「1s」
       → tiles: ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "1p", "1p", "1s", "1s"]
       → win_tile: "1s"

    2. 七対子（7組の対子）:
       例: 手牌「1m, 1m, 2m, 2m, 3m, 3m, 4m, 4m, 5m, 5m, 6m, 6m, 7m, 7m」で和了牌「2m」
       → tiles: ["1m", "1m", "2m", "2m", "3m", "3m", "4m", "4m", "5m", "5m", "6m", "6m", "7m", "7m"]
       → win_tile: "2m"

    3. 国士無双（13種の么九牌+1枚）:
       例: 手牌「1m, 9m, 1p, 9p, 1s, 9s, 1z, 2z, 3z, 4z, 5z, 6z, 7z」で和了牌「1m」
       → tiles: ["1m", "9m", "1p", "9p", "1s", "9s", "1z", "2z", "3z", "4z", "5z", "6z", "7z", "1m"]
       → win_tile: "1m"

    どのパターンでも、win_tileは必ずtilesに含まれている必要があります。

    鳴き(melds)について重要な注意事項:
    - ポン、チー、カン(明カン/暗カン)が問題文に言及されている場合、必ずmeldsフィールドに配列として設定してください
    - 各鳴きは MeldInfo オブジェクトとして以下の形式で記述:
      * "tiles": 鳴いた牌のリスト (例: ポンなら["1m", "1m", "1m"]、チーなら["1m", "2m", "3m"])
      * "is_open": ポン/チー/明カンの場合はtrue、暗カンの場合はfalse
    - 例1: "1mをポン"の場合 → "melds": [{"tiles": ["1m", "1m", "1m"], "is_open": true}]
    - 例2: "2pをチー、5sをポン"の場合 → "melds": [{"tiles": ["2p", "3p", "4p"], "is_open": true}, {"tiles": ["5s", "5s", "5s"], "is_open": true}]
    - 鳴きがない場合のみ null を設定

    重要:
    - 全てのフィールドを出力に含めること
    - 言及されていないフィールドはデフォルト値を設定 (boolはfalse, intは0, オプショナルはnull)
    - JSONオブジェクトのみを出力し、説明文は含めないこと
  "#
}
