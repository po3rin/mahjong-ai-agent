import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
import os

from openai import OpenAI

from mahjong_ai_agent.generator import QuestionGenerator
from mahjong_ai_agent.validator import QuestionValidator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def generate_command_async(args):
    """問題生成コマンド（非同期版）"""
    generator = QuestionGenerator(
        model=args.model,
        enable_langfuse=args.langfuse if hasattr(args, 'langfuse') else False
    )

    # CSVから生成するか、通常の方法で生成するか
    if hasattr(args, 'csv') and args.csv:
        # CSV生成時も--nが指定されていればそれを使う
        questions = await generator.generate_questions_from_csv(
            args.csv,
            num_questions=args.num if args.num > 1 else None
        )
    else:
        questions = await generator.generate_question(
            difficulty=args.difficulty, num_questions=args.num
        )

    # 検証器の初期化（BAML統合版）
    validator = QuestionValidator(use_baml=True)
    print("\n生成した問題を自動検証します...\n")

    # 並列バリデーションの実行（非同期）
    # HandオブジェクトをJSON文字列に変換（Noneの場合はスキップ）
    validation_details = []
    for q in questions:
        if q.generation_error:
            # 問題生成に失敗した場合
            details = {'is_valid': 0, 'error': f'Generation failed: {q.generation_error}', 'score': None}
        elif q.hand:
            hand_json = q.hand.model_dump_json()
            details = (await validator.validate_batch([hand_json], [None]))[0]
        else:
            # Hand抽出に失敗した場合
            details = {'is_valid': 0, 'error': 'Hand extraction failed', 'score': None}
        validation_details.append(details)

    # 計算された点数をexpected_scoreとして設定
    for q, details in zip(questions, validation_details):
        if details.get('score') is not None:
            q.expected_score = details['score']

    # 指示適合性の判定（CSV生成時のみ）
    compliance_results = []
    has_instructions = any(q.instruction for q in questions)

    if has_instructions:
        logger.info("Judging instruction compliance with LLM...")

        # OpenAIクライアントを直接使用（DSPyは不要）
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        for q, details in zip(questions, validation_details):
            if q.instruction and details.get('score') is not None:
                # プロンプトを構築
                prompt = f"""生成された麻雀問題が指示に従っているかを評価してください。

指示: {q.instruction}

実際の結果:
- 計算された点数: {details.get('score', 'N/A')}
- 翻数: {details.get('han', 'N/A')}
- 符数: {details.get('fu', 'N/A')}
- 役: {details.get('yaku', [])}

判定基準:
1. 指示に「答えがN点」と指定されている場合、計算された点数がN点と一致するか
2. 指示に「M翻N符」と指定されている場合、翻数がM翻、符数がN符と一致するか
3. 指示に特定の役（例：タンヤオ、三色同順など）が指定されている場合、役リストにその役が含まれているか
4. 指示に「暗刻がN個」などの構成が指定されている場合、それが満たされているか（役リストから推測）

上記全ての条件が満たされている場合のみ「Yes」、一つでも満たされていない場合は「No」と回答してください。
理由も簡潔に説明してください。

回答形式: Yes/No
理由: （簡潔な説明）"""

                # OpenAI APIを直接呼び出し
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0
                )

                compliance_result = response.choices[0].message.content
                compliance_results.append(compliance_result)
            else:
                compliance_results.append(None)

    return questions, validation_details, compliance_results


def generate_command(args):
    """問題生成コマンド"""
    import asyncio
    questions, validation_details, compliance_results = asyncio.run(generate_command_async(args))

    # 結果を表示
    validation_results = []
    for i, (q, details) in enumerate(zip(questions, validation_details), 1):
        print(f"\n{'='*60}")
        print(f"問題 {i}:")
        print(f"{'='*60}")

        # 指示があれば表示
        if q.instruction:
            print(f"指示: {q.instruction}")
            print()

        # 生成エラーがあれば表示
        if q.generation_error:
            print(f"⚠️  問題生成エラー: {q.generation_error}\n")
        elif q.question:
            print(f"{q.question}\n")

            # 抽出されたHandオブジェクトを表示
            if q.hand:
                print("抽出された手牌情報:")
                print(json.dumps(json.loads(q.hand.model_dump_json()), indent=2, ensure_ascii=False))
                print()
        else:
            print("問題文が生成されませんでした\n")

        if args.verbose and q.expected_score:
            print(f"計算された点数: {q.expected_score}\n")

        # 検証結果を表示
        result = details.get('is_valid', 0)
        validation_status = "✓ 正しい" if result == 1 else "✗ 間違っている"
        print(f"検証結果: {validation_status} (スコア: {result})")

        # 指示適合性の判定結果を表示
        if compliance_results and i-1 < len(compliance_results) and compliance_results[i-1]:
            print(f"指示適合性: {compliance_results[i-1]}")

        print()

        validation_results.append({
            "question_number": i,
            "is_valid": result == 1,
            "score": result,
            "calculated": details.get('score') is not None  # 点数計算ができたか
        })

        # エラーメッセージがあれば表示
        if details.get('error'):
            print(f"エラー: {details['error']}")
            print()

        # 詳細な検証結果を表示
        if args.verbose or result != 1:
            # エラーでない場合、または詳細情報がある場合のみ表示
            has_details = (details.get('score') is not None or
                          details.get('expected_score') is not None or
                          details.get('han') is not None or
                          details.get('fu') is not None or
                          details.get('yaku'))

            if has_details:
                if result != 1:
                    print("詳細情報:")
                if details.get('score') is not None:
                    print(f"  計算された点数: {details.get('score')}")
                if details.get('expected_score') is not None:
                    print(f"  期待される点数: {details.get('expected_score')}")
                    if details.get('score') is not None:
                        if details.get('score') == details.get('expected_score'):
                            print("  → 点数が一致しています！")
                        else:
                            print(f"  → 点数が一致しません (差分: {details.get('score') - details.get('expected_score')})")
                if details.get('han') is not None:
                    print(f"  翻数: {details.get('han')}")
                if details.get('fu') is not None:
                    print(f"  符: {details.get('fu')}")
                if details.get('yaku'):
                    print(f"  役: {', '.join(details.get('yaku', []))}")
                print()

    # ファイルに保存
    output_data = {
        "difficulty": args.difficulty,
        "model": args.model,
        "questions": [
            {
                "question": q.question,
                "hand_json": q.hand.model_dump_json() if q.hand else "{}",
                "expected_score": q.expected_score,
            }
            for q in questions
        ]
    }

    # 検証結果も含める
    for i, val_result in enumerate(validation_results):
        output_data["questions"][i]["validation"] = val_result

    # 出力パスの決定
    if args.output:
        output_path = Path(args.output)
    else:
        # デフォルトでdistディレクトリに保存
        dist_dir = Path("dist")
        dist_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = dist_dir / f"questions_{args.difficulty}_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 統計情報を表示
    print(f"\n{'='*60}")
    print("検証統計:")
    print(f"{'='*60}")
    total = len(validation_results)
    generation_failed = sum(1 for q in questions if q.generation_error)
    calculated = sum(1 for r in validation_results if r["calculated"])
    correct = sum(1 for r in validation_results if r["is_valid"])
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    calc_rate = (calculated / total * 100) if total > 0 else 0

    print(f"総問題数: {total}")
    if generation_failed > 0:
        print(f"問題生成失敗: {generation_failed}")
    print(f"点数計算成功: {calculated} ({calc_rate:.1f}%)")
    print(f"点数一致: {correct}")
    print(f"点数不一致: {incorrect}")
    print(f"正答率: {accuracy:.1f}%")

    # 指示適合性の統計
    if compliance_results:
        compliant_count = sum(1 for c in compliance_results if c and "Yes" in c)
        non_compliant_count = sum(1 for c in compliance_results if c and "No" in c)
        compliance_rate = (compliant_count / len([c for c in compliance_results if c]) * 100) if any(compliance_results) else 0
        print(f"\n指示適合性:")
        print(f"適合: {compliant_count}")
        print(f"不適合: {non_compliant_count}")
        print(f"適合率: {compliance_rate:.1f}%")

    print(f"\n{'='*60}")
    print(f"生成した問題を {output_path} に保存しました")
    print(f"{'='*60}")


async def validate_command_async(args):
    """検証コマンド（非同期版）"""
    validator = QuestionValidator(use_baml=True)

    # JSONファイルから読み込むか、直接指定
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            file_data = json.load(f)

        # ファイルが複数の問題を含むかチェック
        if "questions" in file_data:
            # 複数の問題を含むファイル（generate コマンドで生成されたファイル）
            questions = file_data["questions"]
            hand_jsons = []
            expected_scores = []

            for q in questions:
                hand_jsons.append(q["hand_json"])
                expected_scores.append(q.get("expected_score"))

            # バッチ検証を実行（非同期）
            validation_details = await validator.validate_batch(hand_jsons, expected_scores)

            # 各問題の検証結果を表示
            for i, (q, details) in enumerate(zip(questions, validation_details), 1):
                print(f"\n{'='*60}")
                print(f"問題 {i}")
                print(f"{'='*60}")

                if q.get("question"):
                    print(f"問題文: {q['question']}\n")

                # Hand JSONの内容をそのまま表示
                print("Hand JSON:")
                print(json.dumps(json.loads(q["hand_json"]), indent=2, ensure_ascii=False))
                print()

                # 検証結果を直接表示
                result = details.get('is_valid', 0)
                validation_status = "✓ 正しい" if result == 1 else "✗ 間違っている"
                print(f"検証結果: {validation_status} (スコア: {result})")
                print()

                # エラーメッセージがあれば表示
                if details.get('error'):
                    print(f"エラー: {details['error']}")
                    print()

                # 詳細情報を表示
                if details.get('score') is not None:
                    print(f"計算された点数: {details.get('score')}")
                if details.get('han') is not None:
                    print(f"翻数: {details.get('han')}")
                if details.get('fu') is not None:
                    print(f"符: {details.get('fu')}")
                if details.get('yaku'):
                    print(f"役: {', '.join(details.get('yaku', []))}")
                if details.get('expected_score') is not None:
                    print(f"期待される点数: {details.get('expected_score')}")
                    if details.get('score') is not None:
                        if details.get('score') == details.get('expected_score'):
                            print("→ 点数が一致しています！")
                        else:
                            print(f"→ 点数が一致しません (差分: {details.get('score') - details.get('expected_score')})")
                print()

            # 統計情報を表示
            print(f"\n{'='*60}")
            print("検証統計")
            print(f"{'='*60}")
            total = len(validation_details)
            correct = sum(1 for d in validation_details if d.get('is_valid') == 1)
            calculated = sum(1 for d in validation_details if d.get('score') is not None)
            accuracy = (correct / total * 100) if total > 0 else 0
            calc_rate = (calculated / total * 100) if total > 0 else 0

            print(f"総問題数: {total}")
            print(f"点数計算成功: {calculated} ({calc_rate:.1f}%)")
            print(f"点数一致: {correct}")
            print(f"点数不一致: {total - correct}")
            print(f"正答率: {accuracy:.1f}%")
            print(f"{'='*60}\n")
        else:
            # 単一の問題（Hand形式のJSON）
            hand_json = json.dumps(file_data)
            details = await validator.validate_with_details(hand_json, args.expected_score)
            _print_validation_details(details)
    else:
        # 直接JSON文字列を指定
        hand_json = args.hand_json
        details = await validator.validate_with_details(hand_json, args.expected_score)
        _print_validation_details(details)


def validate_command(args):
    """検証コマンド"""
    import asyncio
    asyncio.run(validate_command_async(args))


def _print_validation_details(details):
    """検証結果の詳細を表示するヘルパー関数"""
    result = details.get('is_valid', 0)

    print(f"\n{'='*60}")
    print("検証結果")
    print(f"{'='*60}")

    # 検証結果の表示
    validation_status = "✓ 正しい" if result == 1 else "✗ 間違っている"
    print(f"ステータス: {validation_status} (スコア: {result})")
    print()

    # エラーメッセージがあれば表示
    if details.get('error'):
        print(f"エラー: {details['error']}")
    else:
        # 正常な場合は詳細情報を表示
        print(f"計算された点数: {details.get('score', 'N/A')}")
        print(f"翻数: {details.get('han', 'N/A')}")
        print(f"符: {details.get('fu', 'N/A')}")
        if details.get('yaku'):
            print(f"役: {', '.join(details.get('yaku', []))}")
        if details.get('expected_score') is not None:
            print(f"期待される点数: {details.get('expected_score')}")
            if details.get('score') is not None:
                if details.get('score') == details.get('expected_score'):
                    print("→ 点数が一致しています！")
                else:
                    print(f"→ 点数が一致しません (差分: {details.get('score') - details.get('expected_score')})")

    print(f"{'='*60}\n")




def main():
    parser = argparse.ArgumentParser(
        description="麻雀点数計算問題の生成・検証・最適化ツール"
    )
    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # 生成コマンド
    generate_parser = subparsers.add_parser("generate", help="問題を生成する")
    generate_parser.add_argument(
        "-d",
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="難易度",
    )
    generate_parser.add_argument(
        "-n", "--num", type=int, default=1, help="生成する問題数"
    )
    generate_parser.add_argument(
        "-m", "--model", default="gpt-4o-mini", help="使用するモデル"
    )
    generate_parser.add_argument(
        "-v", "--verbose", action="store_true", help="詳細情報を表示"
    )
    generate_parser.add_argument(
        "-o", "--output", help="生成した問題を保存するJSONファイルのパス"
    )
    generate_parser.add_argument(
        "--csv", help="指示パターンを定義したCSVファイルのパス。指定された場合、CSVから問題を生成します。"
    )
    generate_parser.add_argument(
        "--langfuse", action="store_true", help="Langfuseトレーシングを有効化"
    )
    generate_parser.set_defaults(func=generate_command)

    # 検証コマンド
    validate_parser = subparsers.add_parser("validate", help="問題を検証する")
    validate_parser.add_argument(
        "-f", "--file", help="検証するJSONファイルのパス"
    )
    validate_parser.add_argument(
        "-j", "--hand-json", help="Hand形式のJSON文字列"
    )
    validate_parser.add_argument(
        "-s", "--expected-score", type=int, help="期待される点数"
    )
    validate_parser.set_defaults(func=validate_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
