import argparse
import asyncio
import csv
import json
import logging
import random
from pathlib import Path
from datetime import datetime

from mahjong_ai_agent.generator import QuestionGenerator
from mahjong_ai_agent.verifier import QuestionVerifier

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
        questions = await generator.generate_question(num_questions=args.num)

    # 検証器の初期化（BAML統合版）
    verifier = QuestionVerifier(use_baml=True)
    print("\n生成した問題を自動検証します...\n")

    # 並列バリデーションの実行（非同期）
    # HandオブジェクトをJSON文字列に変換（Noneの場合はスキップ）
    verification_details = []
    for q in questions:
        if q.generation_error:
            # 問題生成に失敗した場合
            details = {'is_verified': 0, 'error': f'Generation failed: {q.generation_error}', 'score': None}
        elif q.hand:
            hand_json = q.hand.model_dump_json()
            details = (await verifier.verify_batch([hand_json], [None]))[0]
        else:
            # Hand抽出に失敗した場合
            details = {'is_verified': 0, 'error': 'Hand extraction failed', 'score': None}
        verification_details.append(details)

    # 計算された点数をexpected_scoreとして設定
    for q, details in zip(questions, verification_details):
        if details.get('score') is not None:
            q.expected_score = details['score']

    # 指示適合性の判定（CSV生成時のみ）
    compliance_results = []
    has_instructions = any(q.instruction for q in questions)

    if has_instructions:
        logger.info("Judging instruction compliance with LLM...")

        for q, details in zip(questions, verification_details):
            if q.instruction and details.get('score') is not None:
                compliance_result = await verifier.judge_instruction_compliance(
                    q.instruction, details
                )
                compliance_results.append(compliance_result)
            else:
                compliance_results.append(None)

    return questions, verification_details, compliance_results


def generate_command(args):
    """問題生成コマンド"""
    import asyncio
    questions, verification_details, compliance_results = asyncio.run(generate_command_async(args))

    # 結果を表示
    verification_results = []
    for i, (q, details) in enumerate(zip(questions, verification_details), 1):
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
        result = details.get('is_verified', 0)
        validation_status = "✓ 正しい" if result == 1 else "✗ 間違っている"
        print(f"検証結果: {validation_status} (スコア: {result})")

        # 指示適合性の判定結果を表示
        if compliance_results and i-1 < len(compliance_results) and compliance_results[i-1]:
            print(f"指示適合性: {compliance_results[i-1]}")

        print()

        verification_results.append({
            "question_number": i,
            "is_verified": result == 1,
            "score": result,
            "calculated": details.get('score') is not None  # 点数計算ができたか
        })

        # エラーメッセージがあれば表示
        if details.get('error'):
            print(f"エラー: {details['error']}")
            print()

        # 詳細な検証結果を表示
        # 役は常に表示する（指示適合性判定のため）
        if details.get('yaku'):
            print(f"  役: {', '.join(details.get('yaku', []))}")
            print()

        # その他の詳細情報はverboseまたはエラー時のみ表示
        if args.verbose or result != 1:
            # エラーでない場合、または詳細情報がある場合のみ表示
            has_details = (details.get('score') is not None or
                          details.get('expected_score') is not None or
                          details.get('han') is not None or
                          details.get('fu') is not None)

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
                print()

    # ファイルに保存
    output_data = {
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

    # 検証結果と点数計算結果も含める
    for i, (val_result, details) in enumerate(zip(verification_results, verification_details)):
        output_data["questions"][i]["validation"] = val_result
        # 点数計算ツールの結果を追加
        output_data["questions"][i]["calculator_result"] = {
            "score": details.get('score'),
            "han": details.get('han'),
            "fu": details.get('fu'),
            "yaku": details.get('yaku', []),
            "error": details.get('error')
        }

    # 出力パスの決定
    if args.output:
        output_path = Path(args.output)
    else:
        # デフォルトでdistディレクトリに保存
        dist_dir = Path("dist")
        dist_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = dist_dir / f"questions_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # 統計情報を表示
    print(f"\n{'='*60}")
    print("検証統計:")
    print(f"{'='*60}")
    total = len(verification_results)
    generation_failed = sum(1 for q in questions if q.generation_error)
    calculated = sum(1 for r in verification_results if r["calculated"])
    correct = sum(1 for r in verification_results if r["is_verified"])
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


async def repeated_sampling_async_with_instances(generator, verifier, args):
    """Repeated Sampling実装（非同期版、インスタンスを受け取る）"""
    # 指示を取得
    instruction = args.instruction if hasattr(args, 'instruction') and args.instruction else ""
    num_candidates = args.candidates if hasattr(args, 'candidates') else 10

    print(f"\n{'='*60}")
    print(f"Repeated Sampling開始")
    print(f"{'='*60}")
    print(f"指示: {instruction if instruction else '(デフォルト)'}")
    print(f"候補数: {num_candidates}")
    print(f"モデル: {args.model}")
    print(f"{'='*60}\n")

    # 並列で候補を生成
    logger.info(f"Generating {num_candidates} candidates in parallel...")
    candidates = await generator.generate_question(
        num_questions=num_candidates,
        instruction=instruction
    )

    # 生成に成功した候補をフィルタリング
    valid_questions = []
    candidate_indices = []
    candidate_results = []  # 全候補の結果を保存（表示用）
    
    for i, candidate in enumerate(candidates, 1):
        if candidate.generation_error:
            candidate_results.append({
                'candidate_number': i,
                'status': 'generation_failed',
                'error': candidate.generation_error
            })
            continue
        if not candidate.question:
            candidate_results.append({
                'candidate_number': i,
                'status': 'generation_failed',
                'error': '問題文が生成されませんでした'
            })
            continue
        
        valid_questions.append(candidate.question)
        candidate_indices.append(i)

    # Verifierで全ての候補を並列で検証（BAML→Python→LLM-as-a-Judge）
    if valid_questions:
        logger.info(f"Verifying {len(valid_questions)} candidates in parallel (BAML→Python→LLM-as-a-Judge)...")
        instructions_list = [instruction] * len(valid_questions)
        verification_details = await verifier.verify_batch_from_questions(
            valid_questions, instructions_list, [None] * len(valid_questions)
        )
        
        # 検証結果を処理
        valid_candidates = []
        for question, details, candidate_index in zip(valid_questions, verification_details, candidate_indices):
            # 候補オブジェクトを取得
            candidate = candidates[candidate_index - 1]
            
            # 結果をcandidate_resultsに追加
            if details.get('baml_extracted'):
                if details.get('calculation_success'):
                    candidate.expected_score = details.get('score')
                    valid_candidates.append({
                        'candidate': candidate,
                        'details': details,
                        'candidate_number': candidate_index
                    })
                    candidate_results.append({
                        'candidate_number': candidate_index,
                        'status': 'verified',
                        'score': details.get('score'),
                        'yaku': details.get('yaku', []),
                        'baml_extracted': True,
                        'calculation_success': True,
                        'compliance_judged': details.get('compliance_judged', False),
                        'compliance': details.get('compliance_result')
                    })
                else:
                    error_msg = details.get('calculation_error', '不明なエラー')
                    candidate_results.append({
                        'candidate_number': candidate_index,
                        'status': 'calculation_failed',
                        'error': error_msg,
                        'baml_extracted': True,
                        'calculation_success': False,
                        'compliance_judged': False
                    })
            else:
                error_msg = details.get('baml_error', '不明なエラー')
                candidate_results.append({
                    'candidate_number': candidate_index,
                    'status': 'baml_extraction_failed',
                    'error': error_msg,
                    'baml_extracted': False,
                    'calculation_success': False,
                    'compliance_judged': False
                })
    else:
        valid_candidates = []

    return valid_candidates, len(candidates), candidate_results


async def repeated_sampling_async(args):
    """Repeated Sampling実装（非同期版）"""
    generator = QuestionGenerator(
        model=args.model,
        enable_langfuse=args.langfuse if hasattr(args, 'langfuse') else False
    )
    verifier = QuestionVerifier(use_baml=True)
    
    return await repeated_sampling_async_with_instances(generator, verifier, args)


async def _process_single_instruction(generator, verifier, args, instruction, instruction_index):
    """単一の指示を処理するヘルパー関数"""
    logger.info(f"Processing instruction {instruction_index}/{len(args.instructions)}: {instruction}")

    # argsを一時的に更新
    temp_args = argparse.Namespace(**vars(args))
    temp_args.instruction = instruction

    valid_candidates, total_candidates, candidate_results = await repeated_sampling_async_with_instances(
        generator, verifier, temp_args
    )
    
    # 指示適合性が"Yes"の候補数を集計（LLM-as-a-Judgeが実行され、適合と判断した候補）
    compliant_candidates_for_instruction = [
        cand for cand in valid_candidates
        if (cand.get('details', {}).get('compliance_judged', False) and
            cand.get('details', {}).get('compliance_result') and
            "Yes" in str(cand.get('details', {}).get('compliance_result', '')))
    ]

    # 有効な候補から指示適合性が高いものを優先的に選択
    # 指示適合性が"Yes"の候補を優先（LLM-as-a-Judgeが実行され、適合と判断した候補）
    compliant_candidates = [
        cand for cand in valid_candidates
        if (cand.get('details', {}).get('compliance_judged', False) and
            cand.get('details', {}).get('compliance_result') and
            "Yes" in str(cand.get('details', {}).get('compliance_result', '')))
    ]
    
    selected = None
    details = None
    compliance_result = None
    
    if compliant_candidates:
        # 指示適合性が"Yes"の候補からランダムに選択
        selected = random.choice(compliant_candidates)
        logger.info(f"Selected from {len(compliant_candidates)} compliant candidates")
        
        candidate = selected['candidate']
        details = selected['details']
        compliance_result = details.get('compliance_result', 'N/A')

        result = {
            "instruction": instruction,
            "total_candidates": total_candidates,
            "valid_candidates": len(valid_candidates),
            "compliant_candidates": len(compliant_candidates),
            "success": True,  # LLM-as-a-Judgeが適合と判断した候補が見つかった
            "selected_candidate_number": selected['candidate_number'],
            "question": candidate.question,
            "hand_json": details.get('hand_json', '{}'),  # detailsからhand_jsonを取得
            "expected_score": details.get('score'),  # detailsからscoreを取得
            "calculator_result": {
                "score": details.get('score'),
                "han": details.get('han'),
                "fu": details.get('fu'),
                "yaku": details.get('yaku', []),
            },
            "compliance_result": compliance_result
        }
        success = True
    elif valid_candidates:
        # 計算成功した候補はあるが、LLM-as-a-Judgeが適合と判断した候補がない場合
        # フォールバックとして全てからランダムに選択
        selected = random.choice(valid_candidates)
        logger.info(f"No compliant candidates found, selected from all {len(valid_candidates)} candidates")
        
        candidate = selected['candidate']
        details = selected['details']
        compliance_result = details.get('compliance_result', 'N/A')

        result = {
            "instruction": instruction,
            "total_candidates": total_candidates,
            "valid_candidates": len(valid_candidates),
            "compliant_candidates": 0,
            "success": False,  # LLM-as-a-Judgeが適合と判断した候補が見つからなかった
            "selected_candidate_number": selected['candidate_number'],
            "question": candidate.question,
            "hand_json": details.get('hand_json', '{}'),
            "expected_score": details.get('score'),
            "calculator_result": {
                "score": details.get('score'),
                "han": details.get('han'),
                "fu": details.get('fu'),
                "yaku": details.get('yaku', []),
            },
            "compliance_result": compliance_result
        }
        success = False
    else:
        # 計算成功した候補が1つもない場合
        result = {
            "instruction": instruction,
            "total_candidates": total_candidates,
            "valid_candidates": 0,
            "compliant_candidates": 0,
            "success": False
        }
        success = False

    instruction_result = {
        'instruction_number': instruction_index,
        'instruction': instruction,
        'total_candidates': total_candidates,
        'valid_candidates': len(valid_candidates),
        'compliant_candidates': len(compliant_candidates_for_instruction) if valid_candidates else 0,
        'candidate_results': candidate_results,
        'selected_candidate': selected if valid_candidates else None,
        'selected_details': details if valid_candidates else None,
        'compliance_result': compliance_result if valid_candidates else None
    }
    
    return result, instruction_result, total_candidates, len(valid_candidates), len(compliant_candidates_for_instruction), success


async def repeated_sampling_csv_async(args, instructions):
    """CSV指示リストに対してRepeated Samplingを実行（非同期版）"""
    # 一時的にinstructionsをargsに追加（_process_single_instructionで使用）
    args.instructions = instructions
    
    # GeneratorとVerifierのインスタンスを一度だけ作成して共有
    generator = QuestionGenerator(
        model=args.model,
        enable_langfuse=args.langfuse if hasattr(args, 'langfuse') else False
    )
    verifier = QuestionVerifier(use_baml=True)
    
    # 全ての指示を並列で処理
    logger.info(f"Processing {len(instructions)} instructions in parallel...")
    tasks = [
        _process_single_instruction(generator, verifier, args, instruction, i + 1)
        for i, instruction in enumerate(instructions)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 結果を集計
    all_results = []
    total_success = 0
    total_failure = 0
    total_candidates_generated = 0
    total_valid_candidates = 0
    total_compliant_candidates = 0
    instruction_results = []  # 各指示の結果を保存（表示用）

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error processing instruction {i+1}: {result}", exc_info=True)
            # エラーが発生した場合のデフォルト結果
            all_results.append({
                "instruction": instructions[i],
                "total_candidates": 0,
                "valid_candidates": 0,
                "compliant_candidates": 0,
                "success": False
            })
            instruction_results.append({
                'instruction_number': i + 1,
                'instruction': instructions[i],
                'total_candidates': 0,
                'valid_candidates': 0,
                'compliant_candidates': 0,
                'candidate_results': [],
                'selected_candidate': None,
                'selected_details': None,
                'compliance_result': None
            })
            total_failure += 1
        else:
            result_dict, instruction_result, total_candidates, valid_count, compliant_count, success = result
            all_results.append(result_dict)
            instruction_results.append(instruction_result)
            total_candidates_generated += total_candidates
            total_valid_candidates += valid_count
            total_compliant_candidates += compliant_count
            if success:
                total_success += 1
            else:
                total_failure += 1

    return all_results, total_success, total_failure, total_candidates_generated, total_valid_candidates, total_compliant_candidates, instruction_results


def repeated_sampling_command(args):
    """Repeated Samplingコマンド"""
    import asyncio

    # CSVから指示を読み込む場合
    if hasattr(args, 'csv') and args.csv:
        # CSVファイルを読み込む
        instructions = []
        with open(args.csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                instructions.append(row['instruction'])

        logger.info(f"Loaded {len(instructions)} instructions from {args.csv}")

        # -nオプションが指定されている場合、ランダムに選択
        if hasattr(args, 'num') and args.num > 0 and args.num < len(instructions):
            instructions = random.sample(instructions, args.num)
            logger.info(f"Randomly selected {args.num} instructions from CSV")

        # 全ての指示を一つの非同期関数で処理
        all_results, total_success, total_failure, total_candidates_generated, total_valid_candidates, total_compliant_candidates, instruction_results = asyncio.run(
            repeated_sampling_csv_async(args, instructions)
        )

        # 各指示の結果を表示
        for inst_result in instruction_results:
            print(f"\n{'='*60}")
            print(f"指示 {inst_result['instruction_number']}/{len(instructions)}")
            print(f"{'='*60}")
            print(f"指示内容: {inst_result['instruction']}")
            print()
            
            # 各候補の結果を表示
            for cand_result in inst_result['candidate_results']:
                if cand_result['status'] == 'generation_failed':
                    print(f"候補 {cand_result['candidate_number']}: 生成失敗 - {cand_result['error']}")
                elif cand_result['status'] == 'baml_extraction_failed':
                    print(f"候補 {cand_result['candidate_number']}: ✗ BAML抽出失敗 - {cand_result['error']}")
                elif cand_result['status'] == 'calculation_failed':
                    print(f"候補 {cand_result['candidate_number']}: ✓ BAML抽出成功, ✗ 計算失敗 - {cand_result['error']}")
                elif cand_result['status'] == 'verified':
                    compliance_status = ""
                    compliance_reason = ""
                    if 'compliance' in cand_result and cand_result['compliance']:
                        compliance_text = cand_result['compliance'].strip()
                        compliance_lines = [line.strip() for line in compliance_text.split('\n') if line.strip()]
                        first_line = compliance_lines[0] if compliance_lines else ""
                        
                        # プレフィックス（「回答形式:」「回答形式」など）を除去
                        first_line_clean = first_line
                        for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
                            if first_line_clean.startswith(prefix):
                                first_line_clean = first_line_clean[len(prefix):].strip()
                                break
                        
                        # 「Yes」または「No」を抽出（大文字小文字を区別しない）
                        first_line_upper = first_line_clean.upper()
                        if first_line_upper.startswith('YES'):
                            compliance_status = "Yes"
                        elif first_line_upper.startswith('NO'):
                            compliance_status = "No"
                        else:
                            # 最初の行に「Yes」または「No」がない場合、レスポンス全体から検索
                            compliance_clean = compliance_text
                            for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
                                compliance_clean = compliance_clean.replace(prefix, '').strip()
                            
                            compliance_upper = compliance_clean.upper()
                            yes_pos = compliance_upper.find("YES")
                            no_pos = compliance_upper.find("NO")
                            
                            if yes_pos != -1 and (no_pos == -1 or yes_pos < no_pos):
                                compliance_status = "Yes"
                            elif no_pos != -1:
                                compliance_status = "No"
                            else:
                                compliance_status = first_line_clean if first_line_clean else "Unknown"
                        
                        # 理由を抽出（"理由:"以降）
                        for line in compliance_lines[1:]:
                            if '理由' in line or 'reason' in line.lower():
                                compliance_reason = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
                                break
                        if not compliance_reason and len(compliance_lines) > 1:
                            compliance_reason = '\n'.join(compliance_lines[1:]).strip()
                    
                    print(f"候補 {cand_result['candidate_number']}: ✓ BAML抽出成功, ✓ 計算成功 (点数: {cand_result['score']}, 役: {', '.join(cand_result['yaku'])})")
                    if compliance_status:
                        print(f"  指示適合性: {compliance_status}")
                        if compliance_reason:
                            print(f"  理由: {compliance_reason}")
            
            # 結果の統計を表示
            print(f"\n{'='*60}")
            print(f"指示 {inst_result['instruction_number']} の結果:")
            print(f"{'='*60}")
            print(f"総候補数: {inst_result['total_candidates']}")
            
            # 3つの成功率を計算
            baml_success = sum(1 for cr in inst_result['candidate_results'] if cr.get('baml_extracted', False))
            calculation_success = sum(1 for cr in inst_result['candidate_results'] if cr.get('calculation_success', False))
            compliance_judged = sum(1 for cr in inst_result['candidate_results'] if cr.get('compliance_judged', False))
            compliant_count = sum(1 for cr in inst_result['candidate_results'] 
                                 if (cr.get('compliance_judged', False) and
                                     cr.get('compliance') and
                                     "Yes" in str(cr.get('compliance', ''))))
            
            baml_rate = (baml_success / inst_result['total_candidates'] * 100) if inst_result['total_candidates'] > 0 else 0
            calculation_rate = (calculation_success / baml_success * 100) if baml_success > 0 else 0
            compliance_rate = (compliant_count / compliance_judged * 100) if compliance_judged > 0 else 0
            
            print(f"BAML抽出成功: {baml_success}")
            print(f"BAML抽出成功率: {baml_rate:.1f}%")
            print(f"点数計算成功: {calculation_success}")
            print(f"点数計算成功率: {calculation_rate:.1f}%")
            if compliance_judged > 0:
                print(f"LLM-as-a-Judge実行: {compliance_judged}")
                print(f"指示適合候補: {compliant_count}")
                print(f"LLM-as-a-Judge成功率: {compliance_rate:.1f}%")
            else:
                print(f"LLM-as-a-Judge実行: 0")
                print(f"LLM-as-a-Judge成功率: N/A (計算成功した候補がありません)")
            
            # 選択された候補を表示
            if inst_result['selected_candidate']:
                selected = inst_result['selected_candidate']
                details = inst_result['selected_details']
                print(f"\n選択された候補 {selected['candidate_number']}:")
                print(f"点数: {details.get('score')}, 役: {', '.join(details.get('yaku', []))}")
                if inst_result.get('compliance_result'):
                    print(f"指示適合性: {inst_result['compliance_result']}")

        # 全体の統計を表示
        print(f"\n{'='*60}")
        print("全体の統計:")
        print(f"{'='*60}")
        print(f"総指示数: {len(instructions)}")
        print(f"採取成功: {total_success} (LLM-as-a-Judgeが適合と判断した候補が1つ以上見つかった指示の数)")
        print(f"採取失敗: {total_failure} (LLM-as-a-Judgeが適合と判断した候補が1つも見つからなかった指示の数)")
        print(f"採取成功率: {total_success / len(instructions) * 100:.1f}%")
        print(f"総候補生成数: {total_candidates_generated}")
        print(f"平均候補数/指示: {total_candidates_generated / len(instructions):.1f}")
        
        # 全体の3つの成功率を計算
        total_baml_success = sum(
            sum(1 for cr in inst_result['candidate_results'] if cr.get('baml_extracted', False))
            for inst_result in instruction_results
        )
        total_calculation_success = sum(
            sum(1 for cr in inst_result['candidate_results'] if cr.get('calculation_success', False))
            for inst_result in instruction_results
        )
        total_compliance_judged = sum(
            sum(1 for cr in inst_result['candidate_results'] if cr.get('compliance_judged', False))
            for inst_result in instruction_results
        )
        total_compliant_count = sum(
            sum(1 for cr in inst_result['candidate_results'] 
                if (cr.get('compliance_judged', False) and
                    cr.get('compliance') and
                    "Yes" in str(cr.get('compliance', ''))))
            for inst_result in instruction_results
        )

        overall_baml_rate = (total_baml_success / total_candidates_generated * 100) if total_candidates_generated > 0 else 0
        overall_calculation_rate = (total_calculation_success / total_baml_success * 100) if total_baml_success > 0 else 0
        overall_compliance_rate = (total_compliant_count / total_compliance_judged * 100) if total_compliance_judged > 0 else 0
        
        print(f"\n全体の成功率:")
        print(f"BAML抽出成功: {total_baml_success}")
        print(f"BAML抽出成功率: {overall_baml_rate:.1f}%")
        print(f"点数計算成功: {total_calculation_success}")
        print(f"点数計算成功率: {overall_calculation_rate:.1f}%")
        if total_compliance_judged > 0:
            print(f"LLM-as-a-Judge実行: {total_compliance_judged}")
            print(f"指示適合候補: {total_compliant_count}")
            print(f"LLM-as-a-Judge成功率: {overall_compliance_rate:.1f}%")
        else:
            print(f"LLM-as-a-Judge実行: 0")
            print(f"LLM-as-a-Judge成功率: N/A (計算成功した候補がありません)")

        # ファイルに保存
        output_data = {
            "model": args.model,
            "total_instructions": len(instructions),
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": total_success / len(instructions) * 100 if len(instructions) > 0 else 0,
            "total_candidates_generated": total_candidates_generated,
            "results": all_results
        }

        # 出力パスの決定
        if args.output:
            output_path = Path(args.output)
        else:
            dist_dir = Path("dist")
            dist_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = dist_dir / f"repeated_sampling_csv_{timestamp}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"結果を {output_path} に保存しました")
        print(f"{'='*60}")

    else:
        # 単一の指示の場合（既存のロジック）
        valid_candidates, total_candidates, candidate_results = asyncio.run(repeated_sampling_async(args))

        # 各候補の結果を表示
        for cand_result in candidate_results:
            if cand_result['status'] == 'generation_failed':
                print(f"候補 {cand_result['candidate_number']}: 生成失敗 - {cand_result['error']}")
            elif cand_result['status'] == 'baml_extraction_failed':
                print(f"候補 {cand_result['candidate_number']}: ✗ BAML抽出失敗 - {cand_result['error']}")
            elif cand_result['status'] == 'calculation_failed':
                print(f"候補 {cand_result['candidate_number']}: ✓ BAML抽出成功, ✗ 計算失敗 - {cand_result['error']}")
            elif cand_result['status'] == 'verified':
                compliance_status = ""
                compliance_reason = ""
                if 'compliance' in cand_result and cand_result['compliance']:
                    compliance_text = cand_result['compliance'].strip()
                    compliance_lines = [line.strip() for line in compliance_text.split('\n') if line.strip()]
                    first_line = compliance_lines[0] if compliance_lines else ""
                    
                    # プレフィックス（「回答形式:」「回答形式」など）を除去
                    first_line_clean = first_line
                    for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
                        if first_line_clean.startswith(prefix):
                            first_line_clean = first_line_clean[len(prefix):].strip()
                            break
                    
                    # 「Yes」または「No」を抽出（大文字小文字を区別しない）
                    first_line_upper = first_line_clean.upper()
                    if first_line_upper.startswith('YES'):
                        compliance_status = "Yes"
                    elif first_line_upper.startswith('NO'):
                        compliance_status = "No"
                    else:
                        # 最初の行に「Yes」または「No」がない場合、レスポンス全体から検索
                        compliance_clean = compliance_text
                        for prefix in ['回答形式:', '回答形式', '回答:', '回答']:
                            compliance_clean = compliance_clean.replace(prefix, '').strip()
                        
                        compliance_upper = compliance_clean.upper()
                        yes_pos = compliance_upper.find("YES")
                        no_pos = compliance_upper.find("NO")
                        
                        if yes_pos != -1 and (no_pos == -1 or yes_pos < no_pos):
                            compliance_status = "Yes"
                        elif no_pos != -1:
                            compliance_status = "No"
                        else:
                            compliance_status = first_line_clean if first_line_clean else "Unknown"
                    
                    # 理由を抽出（"理由:"以降）
                    for line in compliance_lines[1:]:
                        if '理由' in line or 'reason' in line.lower():
                            compliance_reason = line.split(':', 1)[-1].strip() if ':' in line else line.strip()
                            break
                    if not compliance_reason and len(compliance_lines) > 1:
                        compliance_reason = '\n'.join(compliance_lines[1:]).strip()
                
                print(f"候補 {cand_result['candidate_number']}: ✓ BAML抽出成功, ✓ 計算成功 (点数: {cand_result['score']}, 役: {', '.join(cand_result['yaku'])})")
                if compliance_status:
                    print(f"  指示適合性: {compliance_status}")
                    if compliance_reason:
                        print(f"  理由: {compliance_reason}")

        # 結果の統計を表示
        print(f"\n{'='*60}")
        print("Repeated Sampling結果:")
        print(f"{'='*60}")
        print(f"総候補数: {total_candidates}")
        
        # 3つの成功率を計算
        baml_success = sum(1 for cr in candidate_results if cr.get('baml_extracted', False))
        calculation_success = sum(1 for cr in candidate_results if cr.get('calculation_success', False))
        compliance_judged = sum(1 for cr in candidate_results if cr.get('compliance_judged', False))
        # 指示適合性が"Yes"の候補数を表示（LLM-as-a-Judgeが実行され、適合と判断した候補）
        compliant_candidates = [
            cand for cand in valid_candidates
            if (cand.get('details', {}).get('compliance_judged', False) and
                cand.get('details', {}).get('compliance_result') and
                "Yes" in str(cand.get('details', {}).get('compliance_result', '')))
        ]
        compliant_count = len(compliant_candidates)
        
        baml_rate = (baml_success / total_candidates * 100) if total_candidates > 0 else 0
        calculation_rate = (calculation_success / baml_success * 100) if baml_success > 0 else 0
        compliance_rate = (compliant_count / compliance_judged * 100) if compliance_judged > 0 else 0
        
        print(f"BAML抽出成功: {baml_success}")
        print(f"BAML抽出成功率: {baml_rate:.1f}%")
        print(f"点数計算成功: {calculation_success}")
        print(f"点数計算成功率: {calculation_rate:.1f}%")
        if compliance_judged > 0:
            print(f"LLM-as-a-Judge実行: {compliance_judged}")
            print(f"指示適合候補: {compliant_count}")
            print(f"LLM-as-a-Judge成功率: {compliance_rate:.1f}%")
        else:
            print(f"LLM-as-a-Judge実行: 0")
            print(f"LLM-as-a-Judge成功率: N/A (計算成功した候補がありません)")

        # 有効な候補から指示適合性が高いものを優先的に選択
        if valid_candidates:
            if compliant_candidates:
                # 指示適合性が"Yes"の候補からランダムに選択
                selected = random.choice(compliant_candidates)
                logger.info(f"Selected from {len(compliant_candidates)} compliant candidates")
            else:
                # 適合性が"Yes"の候補がない場合は全てからランダムに選択
                selected = random.choice(valid_candidates)
                logger.info(f"No compliant candidates found, selected from all {len(valid_candidates)} candidates")
            
            candidate = selected['candidate']
            details = selected['details']
            candidate_number = selected['candidate_number']
            compliance_result = details.get('compliance_result', 'N/A')

            print(f"\n{'='*60}")
            print(f"最終選択結果 (候補 {candidate_number}):")
            print(f"{'='*60}")

            print(f"計算された点数: {details.get('score')}")
            print(f"翻数: {details.get('han')}")
            print(f"符: {details.get('fu')}")
            print(f"役: {', '.join(details.get('yaku', []))}")
            if compliance_result and compliance_result != 'N/A':
                print(f"指示適合性: {compliance_result}")

            # ファイルに保存
            output_data = {
                "model": args.model,
                "instruction": args.instruction if hasattr(args, 'instruction') and args.instruction else "",
                "total_candidates": total_candidates,
                "valid_candidates": len(valid_candidates),
                "compliant_candidates": len(compliant_candidates) if compliant_candidates else 0,
                "selected_candidate_number": candidate_number,
                "question": candidate.question,
                "hand_json": details.get('hand_json', '{}'),  # detailsからhand_jsonを取得
                "expected_score": details.get('score'),  # detailsからscoreを取得
                "calculator_result": {
                    "score": details.get('score'),
                    "han": details.get('han'),
                    "fu": details.get('fu'),
                    "yaku": details.get('yaku', []),
                },
                "compliance_result": compliance_result if compliance_result != 'N/A' else None
            }

            # 出力パスの決定
            if args.output:
                output_path = Path(args.output)
            else:
                dist_dir = Path("dist")
                dist_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = dist_dir / f"repeated_sampling_{timestamp}.json"

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            print(f"\n{'='*60}")
            print(f"結果を {output_path} に保存しました")
            print(f"{'='*60}")
            print("\n✓ 成功: 有効な候補が見つかりました")
        else:
            print("\n✗ 失敗: 有効な候補が見つかりませんでした")
            print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="麻雀点数計算問題の生成・検証・最適化ツール"
    )
    subparsers = parser.add_subparsers(dest="command", help="コマンド")

    # 生成コマンド
    generate_parser = subparsers.add_parser("generate", help="問題を生成する")
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

    # Repeated Samplingコマンド
    repeated_sampling_parser = subparsers.add_parser(
        "repeated-sampling",
        help="Repeated Samplingで問題を生成する"
    )
    repeated_sampling_parser.add_argument(
        "-c", "--candidates", type=int, default=10,
        help="生成する候補数（デフォルト: 10）"
    )
    repeated_sampling_parser.add_argument(
        "-i", "--instruction", type=str, default="",
        help="問題生成の指示（自然言語）"
    )
    repeated_sampling_parser.add_argument(
        "-n", "--num", type=int, default=0,
        help="CSVから取り出す指示の数。0の場合は全ての指示を使用（デフォルト: 0）"
    )
    repeated_sampling_parser.add_argument(
        "-m", "--model", default="gpt-4o-mini", help="使用するモデル"
    )
    repeated_sampling_parser.add_argument(
        "-o", "--output", help="結果を保存するJSONファイルのパス"
    )
    repeated_sampling_parser.add_argument(
        "--csv", help="指示パターンを定義したCSVファイルのパス。指定された場合、CSVの各指示に対してRepeated Samplingを実行します。"
    )
    repeated_sampling_parser.add_argument(
        "--langfuse", action="store_true", help="Langfuseトレーシングを有効化"
    )
    repeated_sampling_parser.set_defaults(func=repeated_sampling_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
