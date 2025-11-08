# Mahjong AI Agent

**DSPy + BAML による麻雀点数計算問題の生成・検証・最適化ツール**

Mahjong AI Agentは、DSPyとBAMLを組み合わせた完全分離アーキテクチャにより、高品質な麻雀点数計算問題を自動生成するツールです。DSPyは問題文生成に、BAMLは構造化データ抽出に特化し、それぞれの強みを最大限に活用します。

## 特徴

### 🎯 完全分離アーキテクチャ

```
DSPy (問題文生成)
  ↓ 自然言語の問題文
BAML (構造化抽出)
  ↓ Hand型オブジェクト (TileType/WindType enum使用)
Validator (点数計算・検証)
  ↓ 計算結果
LLM-as-a-Judge (指示適合性判定)
```

1. **DSPy: 問題文生成に集中**
   - 自然言語での問題文生成に特化
   - プロンプト最適化で問題文の品質向上
   - 自然言語指示による柔軟な問題生成
   - CSV指示ファイルからのバッチ生成対応

2. **BAML: 構造化データ抽出**
   - 問題文から手牌データを確実に抽出
   - 型安全な構造化出力（TileType/WindType enum使用）
   - デフォルト値の自動補完
   - パースエラーの完全排除

3. **厳格な検証システム**
   - mahjongライブラリによる正確な点数計算
   - 手牌の形式検証（牌の枚数、鳴きの整合性など）
   - 役の存在確認
   - 詳細なエラーメッセージの表示

4. **LLM-as-a-Judge: 指示適合性判定**
   - 生成された問題が指示に従っているかをLLMが判定
   - 点数、翻数・符数、役の適合性をチェック
   - 適合率の統計情報を提供

5. **DSPyによるプロンプト最適化**
   - Bootstrap: Few-shot examplesを追加
   - MIPRO: プロンプトテンプレート自体を書き換え（推奨）
   - COPRO: プロンプト座標最適化

### 🏗️ アーキテクチャの利点

- **関心の分離**: 各コンポーネントが明確な責務を持つ
- **保守性**: DSPyとBAMLを独立して最適化可能
- **拡張性**: 新しい問題タイプの追加が容易
- **信頼性**: BAMLによる確実な構造化パース

## セットアップ

### 1. 依存関係のインストール

このプロジェクトはuvを使って依存関係を管理しています。

```bash
# uvで依存関係をインストール
uv sync

# BAMLクライアントを生成
uv run baml-cli generate
```

### 2. 環境変数の設定

`.env`ファイルを作成し、OpenAI API keyを設定します:

```bash
cp .env.example .env
```

`.env`ファイルを編集:

```
OPENAI_API_KEY=your_openai_api_key_here
```

## 使い方

### 問題生成

全てBAMLによる構造化チェックが走る

```bash
# 基本的な使い方（問題を1問生成）
uv run python main.py generate

# 複数問生成
uv run python main.py generate -n 3

# 詳細情報を表示
uv run python main.py generate -n 2 -v

# モデルを指定
uv run python main.py generate -m gpt-4o -n 1

# カスタムパスに保存
uv run python main.py generate -n 5 -o custom/path/questions.json
```

### CSV指示ファイルからの問題生成 🆕

自然言語の指示を記載したCSVファイルから問題を生成できます。LLM-as-a-Judgeが自動的に指示適合性を判定します。

#### CSVファイルの形式

```csv
instruction
タンヤオの問題を作成してください
答えが2000点になる問題を作成してください
三色同順の問題を作成してください
暗刻が二つあり、答えが8000点になる問題を作成してください
3翻30符の問題を作成してください
```

#### 使い方

```bash
# CSVの全ての指示から生成（20個全て）
uv run python main.py generate --csv patterns.csv

# CSVからランダムに5個選んで生成
uv run python main.py generate --csv patterns.csv -n 5

# CSVからランダムに10個選んで生成（詳細表示）
uv run python main.py generate --csv patterns.csv -n 10 -v

# 出力先を指定
uv run python main.py generate --csv patterns.csv -o dist/csv_questions.json
```

#### 出力例

```
問題 1:
============================================================
指示: 答えが2000点になる問題を作成してください

東場0本場、あなたは東家。ドラ表示牌は3m（ドラは4m）。ツモで和了しました。
手牌は以下の通り：2m, 3m, 4m, 5m, 6m, 7m, 2p, 3p, 4p, 5s, 6s, 7s, 8s, 8s
和了牌は8s。最終的な得点を計算してください。

検証結果: ✓ 正しい (スコア: 1)
指示適合性: Yes
理由: 計算された点数が2000点で指示と一致しています。

============================================================
検証統計:
============================================================
総問題数: 20
点数計算成功: 20 (100.0%)
点数一致: 18
点数不一致: 2
正答率: 90.0%

指示適合性:
適合: 17
不適合: 3
適合率: 85.0%
```

### 生成される問題の形式

```json
{
  "model": "gpt-4o-mini",
  "questions": [
    {
      "question": "東場0本場、あなたは東家。ドラ表示牌は5m（ドラは6m）。リーチをかけて、ロンで和了しました。\n手牌は以下の通り：2m, 3m, 4m, 5m, 6m, 7m, 2p, 3p, 4p, 5s, 6s, 7s, 8s, 8s\n和了牌は8s。最終的な得点を計算してください。",
      "hand_json": "{...}",
      "expected_score": 5200,
      "validation": {
        "question_number": 1,
        "is_valid": true,
        "score": 1,
        "calculated": true
      }
    }
  ]
}
```

## プロジェクト構成

```
mahjong-ai-agent/
├── main.py                      # CLIエントリーポイント
├── mahjong_ai_agent/
│   ├── __init__.py
│   ├── dspy_modules.py          # DSPy問題文生成モジュール + LLM-as-a-Judge
│   ├── generator.py             # DSPy+BAML統合ジェネレーター
│   ├── validator.py             # BAML統合バリデーター
│   ├── optimizer.py             # DSPyプロンプト最適化
│   └── baml_parser.py           # BAML統合ヘルパー
├── baml_src/
│   └── mahjong.baml             # BAML型定義と関数（TileType/WindType enum使用）
├── baml/
│   └── baml_client/             # BAML自動生成クライアント
├── tools/
│   ├── __init__.py
│   ├── entity.py                # データクラス定義（Hand等）
│   ├── exceptions.py            # カスタム例外定義
│   └── calculator.py            # 点数計算ロジック
├── patterns.csv                 # 問題生成用の指示パターン（サンプル）
├── dist/                        # 生成された問題の出力先
├── pyproject.toml               # プロジェクト設定
├── uv.lock                      # ロックファイル
├── .env.example                 # 環境変数テンプレート
└── README.md
```

## 技術詳細

### 完全分離アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│  DSPy: 問題文生成（自然言語に集中）                  │
│  - プロンプト最適化可能                              │
│  - 問題文の品質向上に専念                            │
└──────────────┬──────────────────────────────────┘
               │ 問題文（日本語）
               ↓
┌──────────────────────────────────────────────────┐
│  BAML: 構造化データ抽出                             │
│  - ExtractHandFromQuestion: 問題文 → Hand型      │
│  - ParseHandFromJSON: JSON → Hand型（後方互換）  │
│  - 型安全・確実なパース                              │
│  - デフォルト値の自動補完                            │
└──────────────┬───────────────────────────────────┘
               │ Handオブジェクト
               ↓
┌──────────────────────────────────────────────────┐
│  Validator: 点数計算・検証                          │
│  - BAMLパース済みデータを使用                        │
│  - mahjongライブラリで点数計算                       │
│  - ビジネスロジックに専念                            │
└──────────────────────────────────────────────────┘
```

### 主要コンポーネント

#### 1. LLM-as-a-Judge (`mahjong_ai_agent/verifier.py`)

**役割**: 生成された問題が指示に従っているかを判定

**特徴**:
- CSV指示生成時に自動実行
- 点数、翻数・符数、役の適合性をチェック
- 適合率の統計情報を提供

#### 2. BAML構造化抽出 (`baml_src/mahjong.baml`)

**役割**: 問題文から手牌データを確実に抽出

```baml
// 牌の種類を列挙型で定義
enum TileType {
  ONE_M @alias("1m")
  TWO_M @alias("2m")
  // ... (全ての牌)
  RED @alias("7z")
}

// 風牌の種類
enum WindType {
  EAST @alias("east")
  SOUTH @alias("south")
  WEST @alias("west")
  NORTH @alias("north")
}

// 麻雀の手牌情報
class Hand {
  tiles TileType[]        // 手牌の牌リスト（enum使用）
  win_tile TileType       // アガリ牌（enum使用）
  player_wind WindType | null  // 自風（enum使用）
  round_wind WindType | null   // 場風（enum使用）
  // ... 他のフィールド
}

// 問題文から構造化データを抽出
function ExtractHandFromQuestion(question: string) -> Hand {
  client GPT4oMini
  prompt #"
    Extract mahjong hand information from the following Japanese question text.
    Output ALL fields as a complete JSON object.
    ...
  "#
}
```

**特徴**:
- 型安全な構造化出力（TileType/WindType enum使用）
- すべてのフィールドにデフォルト値を自動補完
- パースエラーの完全排除
- 牌と風の型安全性を保証

#### 3. 統合ジェネレーター (`mahjong_ai_agent/generator.py`)

**役割**: LLMとBAMLを統合

```python
async def generate_question(self, num_questions: int):
    # 1. LLMで問題文生成
    result = await self._generate_single_question(instruction)

    # 2. BAMLで構造化データ抽出
    hand = await extract_hand_from_question(result)

    return MahjongQuestion(question=result, hand=hand)
```

**特徴**:
- 非同期並列処理
- BAMLによる構造化データ抽出
- 型安全な問題生成

#### 4. BAML統合バリデーター (`mahjong_ai_agent/validator.py`)

**役割**: Hand型の検証と点数計算

```python
async def validate_with_details(self, hand_json: str):
    # BAMLでパース
    hand = await parse_hand_with_baml(hand_json)

    # 検証と点数計算
    validate_hand(hand)
    result = calculate_score(hand)
    ...
```

**特徴**:
- BAMLによる確実なパース
- 非同期並列バリデーション
- 詳細なエラー情報

### データフロー

#### 問題生成フロー（完全分離版）

```
1. User Input
   ├─ 通常生成: 問題数
   └─ CSV生成: 指示ファイル, 問題数（オプション）
   ↓
2. QuestionGenerator.generate_question() / generate_questions_from_csv()
   ↓
3. LLM: 問題文生成
   ├─ _generate_single_question(instruction)
   ├─ instruction例: "答えが2000点になる問題を作成してください"
   └─ OpenAI API → 問題文（自然言語）
   ↓
4. BAML: 構造化データ抽出
   ├─ ExtractHandFromQuestion(問題文)
   ├─ GPT-4o-mini → Hand型JSON（TileType/WindType enum使用）
   └─ Pydantic Hand オブジェクト
   ↓
5. Validator: 検証と点数計算
   ├─ parse_hand_with_baml (再パース)
   ├─ validate_hand (形式検証)
   ├─ calculate_score (点数計算)
   └─ 検証結果を問題に追加
   ↓
6. LLM-as-a-Judge: 指示適合性判定（CSV生成時のみ）
   ├─ InstructionComplianceModule(instruction, 計算結果)
   ├─ 点数、翻数・符数、役の適合性をチェック
   └─ Yes/No + 理由
   ↓
7. Output: JSON ファイルに保存 + 統計表示
   ├─ dist/questions_{timestamp}.json
   └─ 適合率の統計情報（CSV生成時）
```

#### BAML抽出フロー

```
1. 問題文（日本語）
   「東場0本場、あなたは東家。ドラ表示牌は5m...」
   ↓
2. BAML: ExtractHandFromQuestion
   ├─ プロンプト生成
   ├─ OpenAI API (gpt-4o-mini)
   ├─ JSON応答の検証
   └─ すべてのフィールドにデフォルト値補完
   ↓
3. Hand型オブジェクト
   {
     tiles: [...],
     win_tile: "8s",
     is_riichi: true,
     is_tsumo: false,
     ...（全フィールド完備）
   }
```

### DSPy最適化の3つの手法

| 手法 | 何を最適化するか | 推奨度 | 特徴 |
|------|----------------|--------|------|
| **MIPRO** | プロンプトテンプレート | ⭐⭐⭐ | 根本的な改善 |
| **Bootstrap** | Few-shot examples | ⭐⭐ | 手軽、コスト低い |
| **COPRO** | プロンプト指示文 | ⭐⭐ | MIPROに似た効果 |

## 技術スタック

### 主要ライブラリ

| ライブラリ | バージョン | 用途 |
|----------|----------|------|
| **openai** | latest | OpenAI API経由でのLLM呼び出し |
| **dspy-ai** | >=2.0.0 | プロンプト最適化フレームワーク |
| **baml-py** | latest | 構造化出力フレームワーク |
| **mahjong** | >=1.2.0 | 麻雀の点数計算エンジン |
| **pydantic** | >=2.0.0 | データバリデーションと型安全性 |
| **python-dotenv** | latest | 環境変数管理 |

### 開発環境

- **Python**: 3.13以上
- **パッケージマネージャー**: uv
- **BAML CLI**: baml-cli (自動インストール)

## ベストプラクティス

### 問題生成時

1. **並列生成の活用**: 複数問生成で効率化
   ```bash
   uv run python main.py generate -d medium -n 10
   ```

2. **最適化プロンプトの使用**: 品質向上
   ```bash
   uv run python main.py generate --load-optimized optimized_mipro.json -n 10
   ```

3. **詳細モードでデバッグ**: 問題発生時に有効
   ```bash
   uv run python main.py generate -v -n 1
   ```

3. **定期的な再最適化**: 新しいパターンを学習

## FAQ

### Q: DSPyとBAMLをなぜ分離したのですか？

A: **関心の分離**により、各フレームワークの強みを最大限に活用できます：
- **DSPy**: 自然言語生成とプロンプト最適化に優れる
- **BAML**: 構造化出力と型安全性に優れる

### Q: BAMLのメリットは何ですか？

A:
- **型安全**: Pydanticモデルを自動生成
- **確実性**: パースエラーを完全に排除
- **保守性**: 型定義がコードと分離され管理しやすい

### Q: 生成された問題の精度は？

A: DSPyのプロンプト最適化により、継続的に品質が向上します。MIPRO最適化を使用することで、役なしエラーや点数計算ミスが大幅に減少します。

### Q: どのモデルを使うべきですか？

A:
- **問題文生成（DSPy）**: gpt-4o-mini（コスト効率が良い）
- **構造化抽出（BAML）**: gpt-4o-mini（十分な精度）
- より高品質が必要な場合: gpt-4o

## トラブルシューティング

### 問題: 役なしエラーが頻発する

**解決策**:
1. MIPROで最適化を実行
   ```bash
   uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5
   ```
2. 最適化されたプロンプトを使用
   ```bash
   uv run python main.py generate --load-optimized optimized_mipro.json
   ```

### 問題: BAMLのパースエラー

**解決策**:
1. BAMLクライアントを再生成
   ```bash
   uv run baml-cli generate
   ```
2. BAML定義ファイル（`baml_src/mahjong.baml`）を確認


## ライセンス

MIT
