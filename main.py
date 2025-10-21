import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

from mahjong_ai_agent.generator import QuestionGenerator
from mahjong_ai_agent.optimizer import QuestionOptimizer
from mahjong_ai_agent.validator import QuestionValidator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def generate_command_async(args):
    """問題生成コマンド（非同期版）"""
    generator = QuestionGenerator(
        model=args.model,
        load_from=args.load_optimized if hasattr(args, 'load_optimized') else None,
        enable_langfuse=args.langfuse if hasattr(args, 'langfuse') else False
    )
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
        if q.hand:
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

    return questions, validation_details


def generate_command(args):
    """問題生成コマンド"""
    import asyncio
    questions, validation_details = asyncio.run(generate_command_async(args))

    # 結果を表示
    validation_results = []
    for i, (q, details) in enumerate(zip(questions, validation_details), 1):
        print(f"\n{'='*60}")
        print(f"問題 {i}:")
        print(f"{'='*60}")
        print(f"{q.question}\n")

        # 抽出されたHandオブジェクトを表示
        if q.hand:
            print("抽出された手牌情報:")
            print(json.dumps(json.loads(q.hand.model_dump_json()), indent=2, ensure_ascii=False))
            print()

        if args.verbose and q.expected_score:
            print(f"計算された点数: {q.expected_score}\n")

        # 検証結果を表示
        result = details.get('is_valid', 0)
        validation_status = "✓ 正しい" if result == 1 else "✗ 間違っている"
        print(f"検証結果: {validation_status} (スコア: {result})")
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
    calculated = sum(1 for r in validation_results if r["calculated"])
    correct = sum(1 for r in validation_results if r["is_valid"])
    incorrect = total - correct
    accuracy = (correct / total * 100) if total > 0 else 0
    calc_rate = (calculated / total * 100) if total > 0 else 0

    print(f"総問題数: {total}")
    print(f"点数計算成功: {calculated} ({calc_rate:.1f}%)")
    print(f"点数一致: {correct}")
    print(f"点数不一致: {incorrect}")
    print(f"正答率: {accuracy:.1f}%")

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


def optimize_command(args):
    """最適化コマンド"""
    optimizer = QuestionOptimizer(model=args.model)

    # トレーニングデータセットを作成
    difficulties = []
    for _ in range(args.easy):
        difficulties.append("easy")
    for _ in range(args.medium):
        difficulties.append("medium")
    for _ in range(args.hard):
        difficulties.append("hard")

    trainset = optimizer.create_trainset(difficulties)

    print(f"トレーニングデータセット: {len(trainset)}件")
    print("最適化を開始します...")

    # 最適化を実行
    optimized_generator = optimizer.optimize(
        trainset=trainset,
        optimizer_type=args.optimizer_type,
        max_bootstrapped_demos=args.max_bootstrapped_demos,
        max_labeled_demos=args.max_labeled_demos,
        num_candidates=args.num_candidates,
        init_temperature=args.init_temperature,
    )

    print("最適化が完了しました！")

    # 最適化されたモジュールを保存
    output_path = args.output if args.output else f"optimized_{args.optimizer_type}.json"
    optimized_generator.save(output_path)
    print(f"\n最適化されたプロンプトを {output_path} に保存しました")

    # サンプル生成
    if args.test:
        print("\n最適化されたジェネレーターでテスト生成:")
        result = optimized_generator(difficulty="medium")
        print(f"質問: {result.question}")
        print(f"Hand JSON: {result.hand_json}")
        print(f"LLMが考えた答え: {result.expected_score}")


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
        "--load-optimized", help="最適化されたプロンプトのパス（optimize コマンドで保存したファイル）"
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

    # 最適化コマンド
    optimize_parser = subparsers.add_parser(
        "optimize", help="問題生成プロンプトを最適化する"
    )
    optimize_parser.add_argument(
        "--easy", type=int, default=3, help="easyの問題数（デフォルト: 3）"
    )
    optimize_parser.add_argument(
        "--medium", type=int, default=3, help="mediumの問題数（デフォルト: 3）"
    )
    optimize_parser.add_argument(
        "--hard", type=int, default=2, help="hardの問題数（デフォルト: 2）"
    )
    optimize_parser.add_argument(
        "--optimizer-type",
        choices=["bootstrap", "mipro", "copro"],
        default="mipro",
        help="最適化手法（デフォルト: mipro）- bootstrap: Few-shot追加, mipro: プロンプト書き換え（推奨）, copro: プロンプト座標最適化",
    )
    optimize_parser.add_argument(
        "--max-bootstrapped-demos",
        type=int,
        default=4,
        help="ブートストラップされるデモの最大数（bootstrap用、デフォルト: 4）",
    )
    optimize_parser.add_argument(
        "--max-labeled-demos",
        type=int,
        default=4,
        help="ラベル付きデモの最大数（bootstrap用、デフォルト: 4）",
    )
    optimize_parser.add_argument(
        "--num-candidates",
        type=int,
        default=15,
        help="候補プロンプト数（mipro用、デフォルト: 15）",
    )
    optimize_parser.add_argument(
        "--init-temperature",
        type=float,
        default=1.0,
        help="初期temperature（mipro用）",
    )
    optimize_parser.add_argument(
        "-m", "--model", default="gpt-4o-mini", help="使用するモデル"
    )
    optimize_parser.add_argument(
        "-t", "--test", action="store_true", help="最適化後にテスト生成を実行"
    )
    optimize_parser.add_argument(
        "-o", "--output", help="最適化されたプロンプトの保存先（デフォルト: optimized_{optimizer_type}.json）"
    )
    optimize_parser.set_defaults(func=optimize_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
