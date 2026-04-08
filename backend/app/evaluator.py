from typing import Any, Dict, List
import re


def evaluate_process_assignment(code: str, output: str) -> Dict[str, Any]:
    test_cases = [
        {
            "id": 1,
            "name": "进程创建测试",
            "description": "检查是否使用 fork() 创建进程",
            "pattern": r"fork\s*\(",
            "score": 20,
            "type": "static",
        },
        {
            "id": 2,
            "name": "斐波那契计算测试",
            "description": "检查是否计算并输出斐波那契数列前 10 项",
            "expected_parts": ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"],
            "score": 20,
            "type": "dynamic",
        },
        {
            "id": 3,
            "name": "阶乘计算测试",
            "description": "检查是否计算 5! = 120",
            "expected_output": "5! = 120",
            "score": 20,
            "type": "dynamic",
        },
        {
            "id": 4,
            "name": "进程等待测试",
            "description": "检查是否使用 wait()/waitpid() 等待子进程",
            "pattern": r"wait\s*\(|waitpid\s*\(",
            "score": 20,
            "type": "static",
        },
        {
            "id": 5,
            "name": "进程通信测试",
            "description": "检查父子进程是否都有输出",
            "expected_parts": ["Child", "Parent"],
            "score": 20,
            "type": "dynamic",
        },
    ]

    results: List[Dict[str, Any]] = []
    total_score = 0

    for test in [test_cases[0], test_cases[3]]:
        if re.search(test["pattern"], code, re.IGNORECASE):
            results.append(
                {
                    "test_id": test["id"],
                    "name": test["name"],
                    "passed": True,
                    "score": test["score"],
                    "message": f"{test['description']} - 通过",
                }
            )
            total_score += test["score"]
        else:
            results.append(
                {
                    "test_id": test["id"],
                    "name": test["name"],
                    "passed": False,
                    "score": 0,
                    "message": f"{test['description']} - 未通过",
                }
            )

    fib_test = test_cases[1]
    fib_passed = True
    fib_missing = []
    for num in fib_test["expected_parts"]:
        if num not in output:
            fib_passed = False
            fib_missing.append(num)
    if fib_passed:
        results.append(
            {
                "test_id": fib_test["id"],
                "name": fib_test["name"],
                "passed": True,
                "score": fib_test["score"],
                "message": f"{fib_test['description']} - 通过",
            }
        )
        total_score += fib_test["score"]
    else:
        results.append(
            {
                "test_id": fib_test["id"],
                "name": fib_test["name"],
                "passed": False,
                "score": 0,
                "message": f"{fib_test['description']} - 缺少数字: "
                f"{', '.join(fib_missing[:3])}{'...' if len(fib_missing) > 3 else ''}",
            }
        )

    fact_test = test_cases[2]
    if fact_test["expected_output"] in output:
        results.append(
            {
                "test_id": fact_test["id"],
                "name": fact_test["name"],
                "passed": True,
                "score": fact_test["score"],
                "message": f"{fact_test['description']} - 通过",
            }
        )
        total_score += fact_test["score"]
    else:
        results.append(
            {
                "test_id": fact_test["id"],
                "name": fact_test["name"],
                "passed": False,
                "score": 0,
                "message": f"{fact_test['description']} - 未找到 '{fact_test['expected_output']}'",
            }
        )

    comm_test = test_cases[4]
    comm_passed = True
    comm_missing = []
    for part in comm_test["expected_parts"]:
        if part not in output:
            comm_passed = False
            comm_missing.append(part)
    if comm_passed:
        results.append(
            {
                "test_id": comm_test["id"],
                "name": comm_test["name"],
                "passed": True,
                "score": comm_test["score"],
                "message": f"{comm_test['description']} - 通过",
            }
        )
        total_score += comm_test["score"]
    else:
        results.append(
            {
                "test_id": comm_test["id"],
                "name": comm_test["name"],
                "passed": False,
                "score": 0,
                "message": f"{comm_test['description']} - 缺少: {', '.join(comm_missing)}",
            }
        )

    if "wait" not in code.lower() and "waitpid" not in code.lower():
        details = "注意：可能产生僵尸进程，建议使用 wait/waitpid。"
    else:
        details = "进程管理实现正确"

    return {
        "total_score": total_score,
        "max_score": 100,
        "results": results,
        "details": details,
    }


def evaluate_memory_assignment(code: str, output: str) -> Dict[str, Any]:
    test_cases = [
        {
            "id": 1,
            "name": "动态分配检查",
            "pattern": r"malloc\s*\(|calloc\s*\(|realloc\s*\(",
            "score": 30,
            "message": "使用了动态内存分配函数",
        },
        {
            "id": 2,
            "name": "内存释放检查",
            "pattern": r"free\s*\(",
            "score": 30,
            "message": "使用了 free() 释放内存",
        },
        {
            "id": 3,
            "name": "空指针检查",
            "pattern": r"==\s*NULL|!=\s*NULL|if\s*\(\s*!\s*[A-Za-z_]\w*\s*\)",
            "score": 20,
            "message": "包含空指针判断逻辑",
        },
        {
            "id": 4,
            "name": "运行输出检查",
            "score": 20,
            "message": "程序输出非空且无明显崩溃信息",
        },
    ]

    results: List[Dict[str, Any]] = []
    total_score = 0

    for test in test_cases[:3]:
        passed = re.search(test["pattern"], code, re.IGNORECASE) is not None
        results.append(
            {
                "test_id": test["id"],
                "name": test["name"],
                "passed": passed,
                "score": test["score"] if passed else 0,
                "message": test["message"] if passed else f"{test['name']}未通过",
            }
        )
        if passed:
            total_score += test["score"]

    output_clean = (output or "").strip()
    crash_keywords = ["segmentation fault", "core dumped", "invalid pointer"]
    crash_found = any(keyword in output_clean.lower() for keyword in crash_keywords)
    output_passed = bool(output_clean) and not crash_found
    results.append(
        {
            "test_id": test_cases[3]["id"],
            "name": test_cases[3]["name"],
            "passed": output_passed,
            "score": test_cases[3]["score"] if output_passed else 0,
            "message": test_cases[3]["message"] if output_passed else "输出为空或包含崩溃信息",
        }
    )
    if output_passed:
        total_score += test_cases[3]["score"]

    details = "内存管理评测完成"
    return {
        "total_score": total_score,
        "max_score": 100,
        "results": results,
        "details": details,
    }
