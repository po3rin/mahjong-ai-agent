# mjflow

**LLMを活用した麻雀点数計算問題の生成・検証・最適化ツール**

mjflowは、OpenAI APIとDSPyフレームワークを使用して、高品質な麻雀点数計算問題を自動生成するツールです。生成された問題は自動的に検証され、DSPyによる最適化によって継続的に品質が向上します。

## 特徴

### 🎯 主要機能

1. **AI駆動の問題生成**
   - **DSPyフレームワーク**を使用した構造化された問題生成
   - OpenAI GPTモデルによる自然な問題文の生成
   - 難易度別の問題生成（easy/medium/hard）
   - 手牌、役、点数を含む完全な問題データの生成
   - **デフォルトでdistディレクトリに自動保存**

2. **厳格な検証システム**
   - mahjongライブラリを使用した正確な点数計算
   - 手牌の形式検証（牌の枚数、鳴きの整合性など）
   - 役の存在確認
   - 期待点数との照合
   - **詳細なエラーメッセージの表示**

3. **DSPyによるプロンプト最適化**
   - **3種類の最適化手法**から選択可能
     - **Bootstrap**: Few-shot examplesを追加
     - **MIPRO**: プロンプトテンプレート自体を書き換え（推奨）
     - **COPRO**: プロンプト座標最適化
   - メトリクスベースの自動評価
   - 高品質な例の自動選択とプロンプトへの組み込み

### 🔍 検証エラーの種類

生成された問題は以下の観点で検証され、エラーがある場合は詳細なメッセージが表示されます：

- **手牌検証エラー**: 牌の枚数不足、無効な牌形式、鳴きの整合性など
- **点数計算エラー**: 役が存在しない、和了形でないなど
- **点数不一致エラー**: 期待される点数と実際の計算結果が異なる

## セットアップ

### 1. 依存関係のインストール

このプロジェクトはuvを使って依存関係を管理しています。

```bash
# uvで依存関係をインストール
uv sync
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

# デフォルトでdist/に保存される（ファイル名は自動生成）
uv run python main.py generate -d medium -n 5
# → dist/questions_medium_YYYYMMDD_HHMMSS.json

# カスタムパスに保存
uv run python main.py generate -d medium -n 5 -o custom/path/questions.json

# 生成後に自動検証を実行（推奨）
uv run python main.py generate -d easy -n 3 --validate

# 検証と詳細表示を組み合わせ
uv run python main.py generate -d medium -n 5 --validate -v
```

### 問題の検証

```bash
# JSON文字列を直接指定
uv run python main.py validate -j '{"tiles": ["1m", "2m", ...], "win_tile": "1m"}' -s 1000

# JSONファイルから読み込み
uv run python main.py validate -f hand.json -s 1000

# 期待点数を指定して検証
uv run python main.py validate -f hand.json -s 5200

# 生成コマンドで保存したファイルから検証
# （questions.jsonから各問題のhand_jsonを抽出して検証する場合は、
#  ファイルを加工するか、生成時に--validateオプションを使用してください）
```

#### 保存された問題ファイルの形式

`--output`オプションで保存されるJSONファイルの形式:

```json
{
  "difficulty": "medium",
  "model": "gpt-4o-mini",
  "questions": [
    {
      "question": "問題文",
      "hand_json": "{...}",
      "expected_score": 1000,
      "validation": {
        "question_number": 1,
        "is_valid": true,
        "score": 1
      }
    }
  ]
}
```

`validation`フィールドは`--validate`オプションを使用した場合のみ含まれます。

### プロンプトの最適化

DSPyを使用して、問題生成プロンプトを自動的に最適化します。

```bash
# 基本的な使い方（デフォルト: MIPRO、easy=3, medium=3, hard=2）
uv run python main.py optimize

# MIPROを使用（プロンプトテンプレート自体を書き換え・推奨）
uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5 --hard 3

# Bootstrapを使用（Few-shot examplesを追加）
uv run python main.py optimize --optimizer-type bootstrap --easy 4 --medium 4 --hard 2

# COPROを使用（プロンプト座標最適化）
uv run python main.py optimize --optimizer-type copro --easy 4 --medium 4 --hard 2

# MIPROのパラメータを調整
uv run python main.py optimize \
  --optimizer-type mipro \
  --num-candidates 20 \
  --init-temperature 1.5 \
  --easy 5 --medium 5 --hard 3

# Bootstrapのパラメータを調整
uv run python main.py optimize \
  --optimizer-type bootstrap \
  --max-bootstrapped-demos 8 \
  --max-labeled-demos 4

# 最適化後にテスト生成を実行
uv run python main.py optimize --optimizer-type mipro -t

# カスタムパスに保存
uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5 -o my_optimized.json
```

#### 最適化されたプロンプトの使用

最適化されたプロンプトは自動的に保存され、後で再利用できます。

```bash
# 【初期値を使用】最適化なし（ハードコードされたプロンプトを使用）
uv run python main.py generate -d medium -n 5

# 【最適化版を使用】最適化されたプロンプトで問題生成
uv run python main.py generate -d medium -n 5 --load-optimized optimized_mipro.json

# 【最適化版 + 検証】精度を確認しながら生成
uv run python main.py generate -d easy -n 10 --load-optimized optimized_bootstrap.json --validate
```

**使い分け**:
- `--load-optimized`なし: ハードコードされた初期プロンプトを使用（ベースライン）
- `--load-optimized`あり: 最適化で改善されたプロンプトを使用（推奨）

保存されるファイル:
- デフォルト: `optimized_{optimizer_type}.json` (例: `optimized_mipro.json`)
- カスタム: `--output` オプションで指定したパス

#### デフォルトパラメータ

最適化コマンドのデフォルト設定:

| パラメータ | デフォルト値 | 説明 |
|-----------|------------|------|
| `--optimizer-type` | `mipro` | 最も効果的なMIPROをデフォルトに設定 |
| `--easy` | `3` | トレーニング用の簡単な問題数 |
| `--medium` | `3` | トレーニング用の中難易度問題数 |
| `--hard` | `2` | トレーニング用の難しい問題数 |
| `--num-candidates` | `15` | MIPRO用の候補プロンプト数 |
| `--max-bootstrapped-demos` | `4` | Bootstrap用のデモ数 |
| `--max-labeled-demos` | `4` | Bootstrap用のラベル付きデモ数 |

これらの値は実験とベストプラクティスに基づいて設定されています。

#### DSPy最適化の3つの手法の比較

| 手法 | 何を最適化するか | アプローチ | 推奨度 | 特徴 |
|------|----------------|-----------|--------|------|
| **MIPRO** | プロンプトテンプレート | 複数候補から最良を選択 | ⭐⭐⭐ | 根本的な改善、時間はやや長い |
| **Bootstrap** | Few-shot examples | 成功例を収集・追加 | ⭐⭐ | 手軽、コスト低い、例に依存 |
| **COPRO** | プロンプト指示文 | 座標上昇法で反復改善 | ⭐⭐ | MIPROに似た効果、より反復的 |

##### 1. MIPRO (Multi-prompt Instruction Proposal Optimizer) - 推奨
**プロンプトテンプレート自体を書き換える**

- Signatureの`desc`フィールドの内容を自動的に改善
- 複数の候補プロンプトを生成して評価
- 最も高いスコアを出したプロンプトを採用
- パラメータ:
  - `--num-candidates`: 候補プロンプト数（デフォルト: 10）
  - `--init-temperature`: 初期temperature（デフォルト: 1.0）

##### 2. BootstrapFewShot
**Few-shot examplesを追加**

- 成功した生成例を収集
- 高スコアの例をプロンプトに組み込み
- 元のプロンプトは変更せず、例を追加
- パラメータ:
  - `--max-bootstrapped-demos`: デモの最大数（デフォルト: 2）
  - `--max-labeled-demos`: ラベル付きデモの最大数（デフォルト: 2）

##### 3. COPRO (Coordinate Prompt Optimizer)
**座標上昇法によるプロンプト最適化**

- **座標上昇（Hill-climbing）戦略**を使用してプロンプトを反復的に改善
- 複数の候補プロンプトを生成し、最良のものを選択
- 教師LMが新しい指示を生成→学生がその指示を使用→評価→繰り返し
- MIPROと似ているが、より反復的なアプローチ
- Few-shot examplesではなく、指示文そのものに焦点

#### 評価メトリクス

生成された問題を以下の基準でスコアリング:

```python
score = base_score + bonuses
# base_score: 0 or 1（検証通過）
# bonuses:
#   - 役あり: +0.1
#   - 点数一致: +0.5（最重要）
```

最大スコア: 1.0（完璧な問題）

この最適化により、より正確な点数計算を含む高品質な問題が生成されるようになります。

## プロジェクト構成

```
mjflow/
├── main.py                 # CLIエントリーポイント
├── mjflow/
│   ├── __init__.py
│   ├── dspy_modules.py     # DSPy共通モジュール（Signature, Module）
│   ├── generator.py        # 問題生成モジュール（DSPyベース）
│   ├── validator.py        # 問題検証モジュール
│   └── optimizer.py        # プロンプト最適化モジュール（DSPy）
├── tools/
│   ├── __init__.py
│   ├── entity.py           # データクラス定義（Hand, ScoreResponse等）
│   ├── exceptions.py       # カスタム例外定義
│   └── calculator.py       # 点数計算ロジック（mahjongライブラリ使用）
├── dist/                   # 生成された問題の出力先（自動作成）
├── pyproject.toml          # プロジェクト設定と依存関係
├── uv.lock                 # ロックファイル
├── .env.example            # 環境変数テンプレート
└── README.md
```

## 技術詳細

### アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                        │
└────────┬──────────────────────┬─────────────────────────────┘
         │                      │
    ┌────▼─────┐         ┌──────▼──────┐         ┌──────────┐
    │Generator │         │ Validator   │         │Optimizer │
    │(DSPy)    │         │             │         │(DSPy)    │
    └────┬─────┘         └──────┬──────┘         └────┬─────┘
         │                      │                     │
         │                      │                     │
         │                      │    ┌────────────────┤
         │                      │    │ QuestionMetric │
         │                      │    │ (評価関数)      │
         │                      └────▼────────────────┘
         │                           │
         │                      ┌────▼──────────────────────┐
         │                      │  tools/                   │
         │                      │  - calculator             │
         │                      │    (mahjong library)      │
         │                      │  - entity                 │
         │                      │  - exceptions             │
         │                      └───────────────────────────┘
         │
         └───────────┬───────────────┘
                     │
         ┌───────────▼─────────────────────┐
         │  DSPy Framework                 │
         │  ┌───────────────────────────┐  │
         │  │ MahjongQuestionSignature  │  │
         │  │ (プロンプト定義)           │  │
         │  └───────────────────────────┘  │
         │  ┌───────────────────────────┐  │
         │  │ MahjongQuestionModule     │  │
         │  │ (ChainOfThought)          │  │
         │  └───────────────────────────┘  │
         │  ┌───────────────────────────┐  │
         │  │ Optimizers                │  │
         │  │ - Bootstrap               │  │
         │  │ - MIPRO                   │  │
         │  │ - COPRO                   │  │
         │  └───────────────────────────┘  │
         └─────────────┬───────────────────┘
                       │
         ┌─────────────▼───────────────┐
         │  OpenAI API                 │
         │  (gpt-4o-mini/gpt-4o/gpt-5) │
         └─────────────────────────────┘

データフロー:
1. Generator → DSPy → OpenAI: 問題生成
2. Validator → tools/calculator: 問題検証
3. Optimizer → QuestionMetric → Validator → tools: 最適化評価
```

### 主要コンポーネント

#### 1. Generator (`mjflow/generator.py`)
- **クラス**: `QuestionGenerator`
- **役割**: DSPyを使用した麻雀問題の生成
- **主要メソッド**:
  - `generate_question(difficulty, num_questions)`: 問題を複数生成
- **内部構造**:
  - `MahjongQuestionModule` (DSPy Module) を使用
  - ChainOfThought で推論ステップを含む生成
  - variation_hint で多様性を確保
- **対応モデル**: gpt-4o-mini, gpt-4o, gpt-5, o1-* など
- **出力**: `MahjongQuestion` オブジェクトのリスト

#### 2. Validator (`mjflow/validator.py`)
- **クラス**: `QuestionValidator`
- **役割**: 生成された問題の検証
- **主要メソッド**:
  - `validate_question()`: シンプルな検証 (0 or 1)
  - `validate_with_details()`: 詳細な検証結果を返す
- **検証フロー**:
  1. JSONパース → Hand エンティティ
  2. validate_hand() で形式検証
  3. calculate_score() で点数計算
  4. 役の存在と点数の一致を確認
- **出力**: 検証結果の辞書 (is_valid, han, fu, score, yaku, error)

#### 3. Optimizer (`mjflow/optimizer.py`)
- **クラス**: `QuestionOptimizer`, `QuestionMetric`
- **役割**: DSPyによるプロンプト最適化
- **主要メソッド**:
  - `optimize()`: 最適化を実行
  - `create_trainset()`: トレーニングデータ作成
- **評価メトリクス** (`QuestionMetric.__call__`):
  ```python
  base_score = validation_result.get("is_valid", 0)  # 0 or 1
  bonus = 0.0
  if validation_result.get("yaku"):
      bonus += 0.1  # 役あり
  if score == expected_score:
      bonus += 0.5  # 点数一致（最重要）
  return min(base_score + bonus, 1.0)
  ```
- **対応手法**: Bootstrap, MIPRO, COPRO

#### 4. DSPy Modules (`mjflow/dspy_modules.py`)
- **Signature**: `MahjongQuestionSignature`
  - InputField: difficulty, variation_hint
  - OutputField: question, hand_json, expected_score
  - 詳細なプロンプト (desc フィールド)
- **Module**: `MahjongQuestionModule`
  - ChainOfThought を使用
  - GeneratorとOptimizerで共有
  - 最適化後は自動的に改善されたプロンプトを使用

#### 5. Calculator (`tools/calculator.py`)
- **主要関数**:
  - `calculate_score(hand)`: 点数計算を実行
  - `validate_hand(hand)`: 手牌の検証
  - `convert_tiles_to_136_array()`: 牌形式の変換
- **使用ライブラリ**: mahjong (python-mahjong)
  - `HandCalculator.estimate_hand_value()`
  - `TilesConverter.string_to_136_array()`
- **検証項目**:
  - 牌の形式と枚数 (14枚以上)
  - 鳴きの整合性
  - 和了牌の存在
  - ドラ表示牌の形式

### データフロー

#### 問題生成フロー
```
1. User Input (難易度, 問題数)
   ↓
2. QuestionGenerator.generate_question()
   ↓
3. 各問題に対してループ:
   ├─ variation_hintを生成 (多様性のため)
   ├─ MahjongQuestionModule(difficulty, variation_hint)
   │   ├─ MahjongQuestionSignature (入出力定義)
   │   ├─ ChainOfThought (推論)
   │   └─ OpenAI API 呼び出し
   └─ MahjongQuestion オブジェクト作成
       (question, hand_json, expected_score)
   ↓
4. [オプション: --validate] 各問題を検証
   ├─ QuestionValidator.validate_with_details()
   ├─ 検証結果を問題に追加
   └─ 統計情報を集計 (正答率など)
   ↓
5. Output として JSON ファイルに保存
   ├─ デフォルト: dist/questions_{difficulty}_{timestamp}.json
   └─ カスタム: --output で指定したパス

   保存形式:
   {
     "difficulty": "easy",
     "model": "gpt-4o-mini",
     "questions": [
       {
         "question": "問題文",
         "hand_json": "{...}",
         "expected_score": 1000,
         "validation": {  // --validate 使用時のみ
           "question_number": 1,
           "is_valid": true,
           "score": 1
         }
       }
     ]
   }
```

#### 検証フロー
```
1. Hand JSON (文字列)
   ↓
2. QuestionValidator.validate_with_details()
   ↓
3. JSONパース → Hand エンティティ
   ↓
4. 形式検証 (calculator.validate_hand)
   ├─ 牌の形式チェック
   ├─ 牌の枚数チェック (14枚以上)
   ├─ 鳴きの整合性チェック
   ├─ 和了牌がtilesに含まれているか
   └─ ドラ表示牌の形式チェック
   ↓
5. 点数計算 (calculator.calculate_score)
   ├─ 牌を136形式に変換 (TilesConverter)
   ├─ 鳴きをMahjong形式に変換
   ├─ HandConfig作成 (リーチ、ツモなど)
   └─ HandCalculator.estimate_hand_value()
   ↓
6. 結果検証
   ├─ 役の存在確認 (yaku != [])
   └─ 期待点数との照合 (expected_score)
   ↓
7. Output (詳細な検証結果)
   {
     "is_valid": 0 or 1,
     "han": 翻数,
     "fu": 符,
     "score": 点数,
     "yaku": 役のリスト,
     "expected_score": 期待点数,
     "error": エラーメッセージ (あれば)
   }
```

#### 最適化フロー
```
1. User Input (optimizer-type, 各難易度の問題数)
   ↓
2. QuestionOptimizer.create_trainset()
   ├─ 難易度リストから dspy.Example を作成
   └─ 例: [Example(difficulty="easy"), Example(difficulty="medium"), ...]
   ↓
3. QuestionOptimizer.optimize()
   ├─ QuestionMetric を初期化 (評価関数)
   │   └─ スコア計算: base_score + bonus
   │       - base: 検証通過 (0 or 1)
   │       - bonus: 役あり (+0.1), 点数一致 (+0.5)
   │
   └─ 選択された最適化手法を実行:

   [Bootstrap] (dspy.BootstrapFewShot)
   ├─ 各トレーニング例で問題を生成
   ├─ メトリクスでスコアリング
   ├─ 高スコアの例を選択
   │   (max_bootstrapped_demos, max_labeled_demos)
   └─ Few-shot examplesとしてModuleに組み込み

   [MIPRO] (dspy.MIPROv2)
   ├─ num_candidates 個の候補プロンプトを生成
   ├─ 各候補で問題生成・評価を実行
   ├─ 最高スコアのプロンプトを選択
   └─ MahjongQuestionSignature.desc を書き換え

   [COPRO] (dspy.COPRO)
   ├─ 教師LMが改善された指示を生成
   ├─ 学生LMがその指示で問題生成・評価
   ├─ 座標上昇法で最良の指示を選択
   └─ 複数ラウンド反復的に改善
   ↓
4. optimized_generator を返す
   ↓
5. [オプション: --test] テスト生成を実行
   └─ 最適化されたジェネレーターで1問生成・表示
```

## エラーメッセージの例

### 検証時のエラー出力

```bash
$ uv run python main.py validate -f invalid_hand.json

検証結果: ✗ 間違っている (スコア: 0)

エラー: Invalid tile count in hand. tiles is less than 14
```

```bash
$ uv run python main.py validate -f no_yaku.json

検証結果: ✗ 間違っている (スコア: 0)

エラー: No valid yaku found
```

```bash
$ uv run python main.py validate -f hand.json -s 10000

検証結果: ✗ 間違っている (スコア: 0)

エラー: Score mismatch: expected 10000, got 5200
```

### 正常な検証結果の例

```bash
$ uv run python main.py validate -f hand.json -s 5200

検証結果: ✓ 正しい (スコア: 1)

点数: 5200
翻: 3
符: 40
役: Riichi, Ittsu
期待点数: 5200
```

## 開発

### テスト実行

各モジュールには`__main__`ブロックがあり、単体でテストできます:

```bash
# 問題生成のテスト
uv run python -m mjflow.generator

# 問題検証のテスト
uv run python -m mjflow.validator

# プロンプト最適化のテスト
uv run python -m mjflow.optimizer
```

### 依存関係の追加

```bash
# パッケージを追加
uv add <package-name>

# 開発用パッケージを追加
uv add --dev <package-name>
```

### ベストプラクティス

#### 問題生成時
- **常に`--validate`オプションを使用**: 生成直後に問題の品質を確認
- **詳細モード(`-v`)の活用**: 問題のデバッグに役立つ情報を表示
- **適切な難易度の選択**:
  - `easy`: 基本的な役（平和、タンヤオ）
  - `medium`: リーチ、ドラ、役牌を含む
  - `hard`: 複雑な役の組み合わせ、特殊状況

#### 最適化時
- **十分なトレーニングデータ**: 各難易度で3問以上推奨
- **max_bootstrapped_demosの調整**: 4-8が適切（多すぎるとコスト増）
- **定期的な再最適化**: 新しい問題パターンを学習させる

#### エラー対処
- **手牌枚数エラー**: 14枚（カンありで15-18枚）を確認
- **役なしエラー**: 手牌が和了形か、役が存在するか確認
- **点数不一致**: mahjongライブラリの計算結果を信頼する

## 技術スタック

### 主要ライブラリ

| ライブラリ | バージョン | 用途 |
|----------|----------|------|
| **openai** | latest | OpenAI API経由でのLLM問題生成 |
| **dspy-ai** | latest | プロンプト最適化フレームワーク |
| **mahjong** | latest | 麻雀の点数計算エンジン |
| **pydantic** | latest | データバリデーションと型安全性 |
| **python-dotenv** | latest | 環境変数管理 |

### 開発環境

- **Python**: 3.13以上
- **パッケージマネージャー**: uv
- **フォーマット**: Black（推奨）
- **型チェック**: mypy（推奨）

## FAQ

### Q: 生成された問題の点数が間違っているのはなぜですか？

A: LLMが点数計算を誤る場合があります。そのために`--validate`オプションで自動検証を行い、エラーがある問題を検出します。**DSPyの最適化（特にMIPRO）を使用**することで、プロンプト自体が改善され、より正確な問題が生成されるようになります。

### Q: DSPyの最適化にはどのくらい時間がかかりますか？

A: トレーニングデータの数とLLMのレスポンス時間に依存します。
- **Bootstrap**: 5-10問で数分程度
- **MIPRO**: 候補プロンプト生成があるため、やや時間がかかる（10-20分程度）
- **COPRO**: Bootstrapと同程度

API使用料金にも注意してください。

### Q: どの最適化手法を使うべきですか？

A: **MIPROを推奨**します。プロンプトテンプレート自体を書き換えるため、根本的な改善が期待できます。時間やコストを抑えたい場合はBootstrapを使用してください。

### Q: どのモデルを使うべきですか？

A: `gpt-4o-mini`がコストと品質のバランスが良いです。より高品質な問題が必要な場合は`gpt-4o`を使用してください。

### Q: エラーメッセージはどこに表示されますか？

A: 検証時に自動的にコンソールに表示されます。`--detailed`オプションでJSON形式での詳細情報も取得できます。

## トラブルシューティング

### 問題: `No valid yaku found`エラーが頻発する

**原因**: LLMが和了形でない手牌や役のない手牌を生成している

**解決策**:
1. **MIPROで最適化を実行**して問題生成の品質を向上
   ```bash
   uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5
   ```
2. Signatureの`desc`を調整（`mjflow/dspy_modules.py`）
3. 難易度を下げる（easyに設定）

### 問題: API呼び出しが失敗する

**原因**: 環境変数の設定ミスまたはAPIキーの問題

**解決策**:
1. `.env`ファイルが存在し、`OPENAI_API_KEY`が設定されているか確認
2. APIキーが有効か、クォータが残っているか確認
3. インターネット接続を確認

### 問題: 最適化が改善されない

**原因**: トレーニングデータが不足または偏っている、または最適化手法が適していない

**解決策**:
1. **MIPROを試す**（Bootstrapで改善が見られない場合）
   ```bash
   uv run python main.py optimize --optimizer-type mipro --easy 5 --medium 5 --hard 2
   ```
2. 各難易度で最低5問以上のデータを用意
3. MIPROの場合は`--num-candidates`を増やす（20-30推奨）
4. Bootstrapの場合は`--max-bootstrapped-demos`を増やす（4-8推奨）
5. 異なる難易度の組み合わせを試す

## ライセンス

MIT
