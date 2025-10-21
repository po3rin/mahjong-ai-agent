# Mahjong AI Agent

**DSPy + BAML による麻雀点数計算問題の生成・検証・最適化ツール**

Mahjong AI Agentは、DSPyとBAMLを組み合わせた完全分離アーキテクチャにより、高品質な麻雀点数計算問題を自動生成するツールです。DSPyは問題文生成に、BAMLは構造化データ抽出に特化し、それぞれの強みを最大限に活用します。

## 特徴

### 🎯 完全分離アーキテクチャ

```
DSPy (問題文生成)
  ↓ 自然言語の問題文
BAML (構造化抽出)
  ↓ Hand型オブジェクト
Validator (点数計算・検証)
```

1. **DSPy: 問題文生成に集中**
   - 自然言語での問題文生成に特化
   - プロンプト最適化で問題文の品質向上
   - 難易度別の多様な問題生成（easy/medium/hard）

2. **BAML: 構造化データ抽出**
   - 問題文から手牌データを確実に抽出
   - 型安全な構造化出力
   - デフォルト値の自動補完
   - パースエラーの完全排除

3. **厳格な検証システム**
   - mahjongライブラリによる正確な点数計算
   - 手牌の形式検証（牌の枚数、鳴きの整合性など）
   - 役の存在確認
   - 詳細なエラーメッセージの表示

4. **DSPyによるプロンプト最適化**
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

```bash
# 基本的な使い方（medium難易度の問題を1問生成）
uv run python main.py generate

# 難易度を指定して複数問生成
uv run python main.py generate -d easy -n 3

# 詳細情報を表示
uv run python main.py generate -d hard -n 2 -v

# モデルを指定
uv run python main.py generate -m gpt-4o -n 1

# カスタムパスに保存
uv run python main.py generate -d medium -n 5 -o custom/path/questions.json

# 最適化されたプロンプトを使用
uv run python main.py generate -d medium -n 5 --load-optimized optimized_mipro.json
```

### 生成される問題の形式

```json
{
  "difficulty": "medium",
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

### 問題の検証

```bash
# JSONファイルから検証
uv run python main.py validate -f questions.json

# 単一の手牌を検証
uv run python main.py validate -f hand.json

# 期待点数を指定して検証
uv run python main.py validate -f hand.json -s 5200
```

### プロンプトの最適化

DSPyを使用して、問題生成プロンプトを自動的に最適化します。

```bash
# 基本的な使い方（デフォルト: MIPRO）
uv run python main.py optimize

# MIPROを使用（推奨）
uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5 --hard 3

# Bootstrapを使用
uv run python main.py optimize --optimizer-type bootstrap --easy 4 --medium 4 --hard 2

# COPROを使用
uv run python main.py optimize --optimizer-type copro --easy 4 --medium 4 --hard 2

# 最適化後にテスト生成
uv run python main.py optimize --optimizer-type mipro -t

# カスタムパスに保存
uv run python main.py optimize --optimizer-type mipro -o my_optimized.json
```

#### 最適化されたプロンプトの使用

```bash
# 最適化なし（初期プロンプト）
uv run python main.py generate -d medium -n 5

# 最適化されたプロンプトで問題生成
uv run python main.py generate -d medium -n 5 --load-optimized optimized_mipro.json
```

## プロジェクト構成

```
mahjong-ai-agent/
├── main.py                      # CLIエントリーポイント
├── mahjong_ai_agent/
│   ├── __init__.py
│   ├── dspy_modules.py          # DSPy問題文生成モジュール
│   ├── generator.py             # DSPy+BAML統合ジェネレーター
│   ├── validator.py             # BAML統合バリデーター
│   ├── optimizer.py             # DSPyプロンプト最適化
│   └── baml_parser.py           # BAML統合ヘルパー
├── baml_src/
│   └── mahjong.baml             # BAML型定義と関数
├── baml/
│   └── baml_client/             # BAML自動生成クライアント
├── tools/
│   ├── __init__.py
│   ├── entity.py                # データクラス定義（Hand等）
│   ├── exceptions.py            # カスタム例外定義
│   └── calculator.py            # 点数計算ロジック
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

#### 1. DSPy問題文生成 (`mahjong_ai_agent/dspy_modules.py`)

**役割**: 自然言語での問題文生成に特化

```python
class MahjongQuestionSignature(dspy.Signature):
    difficulty = dspy.InputField(desc="問題の難易度")
    variation_hint = dspy.InputField(desc="バリエーションヒント")
    question = dspy.OutputField(desc="麻雀の点数計算問題の問題文")
```

**特徴**:
- 問題文のみを生成（構造化データはBAMLが担当）
- ChainOfThoughtによる推論
- プロンプト最適化で品質向上

#### 2. BAML構造化抽出 (`baml_src/mahjong.baml`)

**役割**: 問題文から手牌データを確実に抽出

```baml
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
- 型安全な構造化出力
- すべてのフィールドにデフォルト値を自動補完
- パースエラーの完全排除

#### 3. 統合ジェネレーター (`mahjong_ai_agent/generator.py`)

**役割**: DSPyとBAMLを統合

```python
async def generate_question(self, difficulty: str, num_questions: int):
    # 1. DSPyで問題文生成
    result = self.generator(difficulty=difficulty, ...)

    # 2. BAMLで構造化データ抽出
    hand = await extract_hand_from_question(result.question)

    return MahjongQuestion(question=result.question, hand=hand)
```

**特徴**:
- 非同期並列処理
- DSPyとBAMLのシームレスな統合
- 各コンポーネントの強みを活用

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
1. User Input (難易度, 問題数)
   ↓
2. QuestionGenerator.generate_question()
   ↓
3. DSPy: 問題文生成
   ├─ MahjongQuestionModule(difficulty, variation_hint)
   ├─ ChainOfThought (推論)
   └─ OpenAI API → 問題文（自然言語）
   ↓
4. BAML: 構造化データ抽出
   ├─ ExtractHandFromQuestion(問題文)
   ├─ GPT-4o-mini → Hand型JSON
   └─ Pydantic Hand オブジェクト
   ↓
5. Validator: 検証と点数計算
   ├─ parse_hand_with_baml (再パース)
   ├─ validate_hand (形式検証)
   ├─ calculate_score (点数計算)
   └─ 検証結果を問題に追加
   ↓
6. Output: JSON ファイルに保存
   └─ dist/questions_{difficulty}_{timestamp}.json
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
   uv run python main.py generate -v -d easy -n 1
   ```

### 最適化時

1. **十分なトレーニングデータ**: 各難易度で5問以上推奨
   ```bash
   uv run python main.py optimize --easy 5 --medium 5 --hard 3
   ```

2. **MIPROの活用**: 最も効果的な最適化
   ```bash
   uv run python main.py optimize --optimizer-type mipro --num-candidates 20
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

### 問題: 最適化が改善されない

**解決策**:
1. トレーニングデータを増やす（各難易度10問以上）
2. num_candidatesを増やす（MIPRO）
   ```bash
   uv run python main.py optimize --optimizer-type mipro --num-candidates 30
   ```

## ライセンス

MIT
