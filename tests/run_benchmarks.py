import json
import time
import asyncio
import os
from src.services.ai.text_to_sql import ask
from src.services.ai import query_cache
from src.core.logging.logger import logger


async def main():
    # 1. Clear cache for clean benchmark start
    query_cache.invalidate_all()

    with open("tests/benchmark_queries.json", "r") as f:
        cases = json.load(f)

    results_list = []
    passed = 0
    failed = 0
    fast_path_hits = 0
    cache_hits = 0
    latencies = []

    print("\n" + "=" * 80)
    print("STARTING HR ANALYTICS BENCHMARK SUITE")
    print("=" * 80)

    # First Pass (Cold Runs)
    for case in cases:
        cid = case["id"]
        category = case["category"]
        question = case["question"]
        expected_sql = case.get("expected_sql_contains", [])
        expected_answer = case.get("expected_answer_contains", [])
        fast_path_expected = case.get("fast_path_expected", False)
        is_security = case.get("security_test", False)

        start_ts = time.perf_counter()

        err_msg = None
        res = None
        try:
            res = await ask(question)
        except Exception as e:
            err_msg = str(e)

        latency = time.perf_counter() - start_ts
        latencies.append(latency)

        is_passed = True
        reasons = []

        if is_security:
            # Security query must be blocked either via raising MCPToolError/Exception or returning validation failure in results
            if err_msg:
                # Successfully blocked via exception
                pass
            elif res and (
                "error" in str(res).lower() or 
                "cannot_answer" in str(res).lower() or
                "validation failed" in res.get("answer", "").lower() or 
                "forbidden" in res.get("answer", "").lower() or 
                "rejected" in res.get("answer", "").lower() or
                "not permitted" in res.get("answer", "").lower() or
                "not allowed" in res.get("answer", "").lower()
            ):
                # Successfully blocked via validation return message
                pass
            else:
                is_passed = False
                reasons.append("Security bypass: Statement executed or did not return validation errors.")
        else:
            if err_msg:
                is_passed = False
                reasons.append(f"Execution crashed: {err_msg}")
            elif not res:
                is_passed = False
                reasons.append("Null execution response")
            else:
                # Check SQL keywords
                generated_sql = res.get("generated_sql", "")
                for keyword in expected_sql:
                    if keyword.lower() not in generated_sql.lower():
                        is_passed = False
                        reasons.append(f"SQL missing keyword '{keyword}'")

                # Check answer details
                answer = res.get("answer", "")
                for substring in expected_answer:
                    if substring.lower() not in answer.lower():
                        is_passed = False
                        reasons.append(f"Answer missing expected text '{substring}'")

                # Check fast path hit status
                is_fast = res.get("fast_path", False)
                if is_fast:
                    fast_path_hits += 1
                if fast_path_expected and not is_fast:
                    is_passed = False
                    reasons.append("Expected fast-path query execution did not trigger")

        if is_passed:
            passed += 1
        else:
            failed += 1

        case_report = {
            "id": cid,
            "category": category,
            "question": question,
            "passed": is_passed,
            "latency_seconds": latency,
            "reasons": reasons,
            "fast_path_hit": res.get("fast_path", False) if res else False,
            "generated_sql": res.get("generated_sql", "") if res else "",
            "answer": res.get("answer", "") if res else ""
        }
        results_list.append(case_report)

        status_str = "PASS" if is_passed else "FAIL"
        print(f"[{status_str}] {cid} | {category.ljust(18)} | {question[:45].ljust(45)} | {latency:.2f}s")

        if not is_passed:
            print(f"    -> Reasons: {reasons}")

    # Second Pass (Verify Cache Hits on LLM Queries)
    print("\nRunning cache verification pass...")
    for case in cases:
        if not case.get("fast_path_expected") and not case.get("security_test"):
            question = case["question"]
            if query_cache.get(question) is not None:
                start_ts = time.perf_counter()
                res = await ask(question)
                latency = time.perf_counter() - start_ts
                cache_hits += 1
                print(f"[CACHE HIT] {case['id']} | {question[:45].ljust(45)} | {latency:.4f}s")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # Print formal report output
    print("\n" + "--------------------------------")
    print("BENCHMARK REPORT")
    print("--------------------------------")
    print(f"Total:       {len(cases)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print(f"Fast-path:    {fast_path_hits}")
    print(f"Cache hits:   {cache_hits}")
    print(f"Avg latency: {avg_latency:.2f}s")
    print("--------------------------------\n")

    # Serialize results to disk
    report_data = {
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": failed,
            "fast_path_hits": fast_path_hits,
            "cache_hits": cache_hits,
            "average_latency_seconds": avg_latency
        },
        "cases": results_list
    }

    os.makedirs("tests/benchmark_results", exist_ok=True)
    with open("tests/benchmark_results/latest.json", "w") as f:
        json.dump(report_data, f, indent=2)

    print("Saved latest report to tests/benchmark_results/latest.json")


if __name__ == "__main__":
    asyncio.run(main())
