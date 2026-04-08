import json
import csv
import io
import time
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

from .db import get_db_connection, init_db
from .ai_feedback import analyze_student_feedback, analyze_version_feedback
from .ai_plagiarism import analyze_plagiarism_pair
from .evaluator import evaluate_memory_assignment, evaluate_process_assignment
from .models import (
    AssignmentCreateRequest,
    AssignmentSubmitRequest,
    CodeRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from .plagiarism import pairwise_similarity
from .runner import run_normal_code, run_process_code
from .security import validate_code_security

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)


def _query_all(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()


def _query_one(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _query_all(sql, params)
    return rows[0] if rows else None

#数据库执行
def _execute(sql: str, params: tuple = ()) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.lastrowid


def _execute_statement(sql: str, params: tuple = ()) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)


def _now() -> datetime:
    return datetime.utcnow()

#按给定盐值把密码算成哈希
def _hash_password(password: str, salt: str) -> str:
    #用 sha256 计算哈希，并转成十六进制字符串
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()

#生成新盐值，并得到要存库的哈希结果
def _make_password_record(password: str) -> tuple[str, str]:
    salt = os.urandom(16).hex()#os.urandom(16)
    return salt, _hash_password(password, salt)

#检查身份是否合法
def _sanitize_role(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in {"student", "teacher"}:
        raise HTTPException(status_code=400, detail="role must be student or teacher")
    return normalized

#返回一个安全的用户视图
def _user_public_view(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "username": row.get("username"),
        "role": row.get("role"),
        "created_at": row.get("created_at"),
    }


def _normalize_deadline(deadline_at: Optional[datetime]) -> Optional[datetime]:
    if not deadline_at:
        return None
    if deadline_at.tzinfo is None:
        return deadline_at
    return deadline_at.astimezone(timezone.utc).replace(tzinfo=None)


def _evaluate_with_test_cases(
    output: str, test_cases: List[Dict[str, Any]], max_points: int
) -> Dict[str, Any]:
    if not test_cases:
        return {"score": max_points, "details": "No test cases configured", "tests": []}

    score = 0
    tests = []
    for index, case in enumerate(test_cases, start=1):
        case_type = case.get("type", "contains")
        expected = case.get("value", "")
        case_score = int(case.get("score", 0))
        passed = output.strip() == expected.strip() if case_type == "exact" else expected in output
        tests.append(
            {
                "test_id": index,
                "type": case_type,
                "value": expected,
                "passed": passed,
                "score": case_score if passed else 0,
            }
        )
        if passed:
            score += case_score

    score = min(score, max_points)
    details = f"Matched {sum(1 for t in tests if t['passed'])}/{len(tests)} test points"
    return {"score": score, "details": details, "tests": tests}


def _run_problem(problem: Dict[str, Any], code: str, timeout: int) -> Dict[str, Any]:
    problem_type = problem["problem_type"]
    max_points = int(problem["points"])
    memory_limit_mb = problem.get("memory_limit")
    pids_limit = problem.get("pids_limit")
    file_size_limit_mb = problem.get("file_size_limit")
    mem_limit = f"{int(memory_limit_mb)}m" if memory_limit_mb else "256m"
    file_size_limit_kb = int(file_size_limit_mb) * 1024 if file_size_limit_mb else None
    limits = {
        "time_limit": timeout,
        "memory_limit_mb": memory_limit_mb,
        "pids_limit": pids_limit,
        "file_size_limit_mb": file_size_limit_mb,
    }

    if problem_type == "process":
        run_result = run_process_code(
            code,
            timeout,
            mem_limit=mem_limit,
            pids_limit=pids_limit if pids_limit is not None else 20,
            file_size_limit_kb=file_size_limit_kb,
        )
    else:
        run_result = run_normal_code(
            code,
            timeout,
            mem_limit=mem_limit,
            pids_limit=pids_limit,
            file_size_limit_kb=file_size_limit_kb,
        )

    if not run_result["success"]:
        message = run_result.get("message", "Run failed")
        status = "TLE" if "超时" in message else ("CE" if "编译错误" in message else "RE")
        return {
            "status": status,
            "message": message,
            "score": 0,
            "output": run_result.get("output", ""),
            "test_results": [],
            "problem_type": problem_type,
            "limits": limits,
        }

    if problem_type == "process":
        eval_result = evaluate_process_assignment(code, run_result["output"])
        score = min(eval_result["total_score"], max_points)
        status = "AC" if score == max_points else ("PA" if score > 0 else "WA")
        return {
            "status": status,
            "message": eval_result["details"],
            "score": score,
            "output": run_result["output"],
            "test_results": eval_result["results"],
            "problem_type": problem_type,
            "limits": limits,
        }

    if problem_type == "memory":
        eval_result = evaluate_memory_assignment(code, run_result["output"])
        score = round(eval_result["total_score"] * max_points / 100)
        status = "AC" if score == max_points else ("PA" if score > 0 else "WA")
        return {
            "status": status,
            "message": eval_result["details"],
            "score": score,
            "output": run_result["output"],
            "test_results": eval_result["results"],
            "problem_type": problem_type,
            "limits": limits,
        }

    eval_result = _evaluate_with_test_cases(
        run_result["output"], problem.get("test_cases") or [], max_points
    )
    status = (
        "AC"
        if eval_result["score"] == max_points
        else ("PA" if eval_result["score"] > 0 else "WA")
    )
    return {
        "status": status,
        "message": eval_result["details"],
        "score": eval_result["score"],
        "output": run_result["output"],
        "test_results": eval_result["tests"],
        "problem_type": problem_type,
        "limits": limits,
    }


def _build_submission_report(
    assignment_id: int,
    student: str,
    total_score: int,
    time_used: float,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_tests = 0
    passed_tests = 0
    type_stats: Dict[str, Dict[str, int]] = {}
    limits_snapshot = []

    for item in items:
        tests = item.get("test_results") or []
        total_tests += len(tests)
        passed_tests += sum(1 for test in tests if test.get("passed"))
        problem_type = item.get("problem_type", "unknown")
        if problem_type not in type_stats:
            type_stats[problem_type] = {"count": 0, "score": 0}
        type_stats[problem_type]["count"] += 1
        type_stats[problem_type]["score"] += int(item.get("score", 0))
        limits_snapshot.append(
            {
                "problem_id": item.get("problem_id"),
                "problem_type": problem_type,
                "limits": item.get("limits", {}),
                "status": item.get("status"),
            }
        )

    suggestions = []
    if any(item.get("status") in {"CE", "RE"} for item in items):
        suggestions.append("Fix compilation/runtime errors first, then tune outputs.")
    if total_tests > 0 and passed_tests < total_tests:
        suggestions.append("Check unpassed test points and adjust implementation.")
    if not suggestions:
        suggestions.append("All checks passed. Keep improving code robustness.")

    summary = (
        f"Total score {total_score}, matched {passed_tests}/{total_tests} test points."
        if total_tests > 0
        else f"Total score {total_score}, no test points configured."
    )

    return {
        "assignment_id": assignment_id,
        "student": student,
        "total_score": total_score,
        "time_used_sec": round(time_used, 2),
        "test_points": {"total": total_tests, "passed": passed_tests},
        "problem_type_stats": type_stats,
        "limits_snapshot": limits_snapshot,
        "items": items,
        "suggestions": suggestions,
        "summary_text": summary,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

#找到学生在某个作业下当前最大的版本号
def _next_version_no(assignment_id: int, student: str) -> int:
    row = _query_one(
        "SELECT COALESCE(MAX(version_no), 0) AS max_no FROM submission_versions WHERE assignment_id=%s AND student=%s",
        (assignment_id, student),
    )
    return int((row or {}).get("max_no") or 0) + 1

#模拟一个提交哈希
def _build_commit_hash(assignment_id: int, student: str, items: List[Dict[str, Any]]) -> str:
    payload = {
        "assignment_id": assignment_id,
        "student": student,
        "items": [
            {"problem_id": item.get("problem_id"), "status": item.get("status"), "score": item.get("score")}
            for item in items
        ],
        "t": time.time_ns(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _build_status_summary(items: List[Dict[str, Any]]) -> str:
    counts: Dict[str, int] = {}
    for item in items:
        status = item.get("status") or "UNKNOWN"
        counts[status] = counts.get(status, 0) + 1
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))


def _collect_plagiarism_pairs(
    assignment_id: int, threshold: float = 0.7, k: int = 5, w: int = 4
) -> List[Dict[str, Any]]:
    rows = _query_all(
        """
        SELECT
            s.id AS submission_id,
            s.student AS student,
            si.problem_id AS problem_id,
            si.code AS code
        FROM submissions s
        JOIN submission_items si ON si.submission_id = s.id
        WHERE s.assignment_id = %s
        ORDER BY si.problem_id ASC, s.id ASC
        """,
        (assignment_id,),
    )

    grouped: Dict[int, List[tuple]] = {}
    for row in rows:
        problem_id = int(row["problem_id"])
        grouped.setdefault(problem_id, []).append(
            (
                int(row["submission_id"]),
                row.get("code") or "",
                {"student": row.get("student"), "problem_id": problem_id},
            )
        )

    pairs: List[Dict[str, Any]] = []
    for _, submissions in grouped.items():
        if len(submissions) < 2:
            continue
        pairs.extend(pairwise_similarity(submissions, threshold=threshold, k=k, w=w))
    pairs.sort(key=lambda item: item["score"], reverse=True)
    return pairs


def _plagiarism_csv(assignment_id: int, threshold: float, k: int, w: int, pairs: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "assignment_id",
            "threshold",
            "k",
            "w",
            "problem_id",
            "submission_a",
            "student_a",
            "submission_b",
            "student_b",
            "score",
            "shared_fingerprints",
            "fingerprints_a",
            "fingerprints_b",
            "token_count_a",
            "token_count_b",
            "shared_snippets",
        ]
    )

    for pair in pairs:
        evidence = pair.get("evidence") or {}
        writer.writerow(
            [
                assignment_id,
                threshold,
                k,
                w,
                pair.get("problem_id"),
                pair.get("submission_a"),
                pair.get("student_a") or "",
                pair.get("submission_b"),
                pair.get("student_b") or "",
                pair.get("score"),
                evidence.get("shared_fingerprints", 0),
                evidence.get("fingerprints_a", 0),
                evidence.get("fingerprints_b", 0),
                evidence.get("token_count_a", 0),
                evidence.get("token_count_b", 0),
                " | ".join(evidence.get("shared_snippets") or []),
            ]
        )
    return output.getvalue()


def _plagiarism_txt(assignment_id: int, threshold: float, k: int, w: int, pairs: List[Dict[str, Any]]) -> str:
    lines = [
        "Plagiarism Detection Report",
        f"assignment_id: {assignment_id}",
        f"threshold: {threshold}",
        f"k: {k}",
        f"w: {w}",
        f"pair_count: {len(pairs)}",
        "",
    ]
    for idx, pair in enumerate(pairs, start=1):
        evidence = pair.get("evidence") or {}
        lines.append(f"[{idx}] problem_id={pair.get('problem_id')} score={pair.get('score')}")
        lines.append(
            f"  A: submission={pair.get('submission_a')} student={pair.get('student_a') or ''}"
        )
        lines.append(
            f"  B: submission={pair.get('submission_b')} student={pair.get('student_b') or ''}"
        )
        lines.append(
            "  fingerprints(shared/a/b)="
            f"{evidence.get('shared_fingerprints', 0)}/"
            f"{evidence.get('fingerprints_a', 0)}/"
            f"{evidence.get('fingerprints_b', 0)}"
        )
        lines.append(
            "  tokens(a/b)="
            f"{evidence.get('token_count_a', 0)}/"
            f"{evidence.get('token_count_b', 0)}"
        )
        snippets = evidence.get("shared_snippets") or []
        if snippets:
            lines.append("  snippets:")
            for snippet in snippets:
                lines.append(f"    - {snippet}")
        lines.append("")
    return "\n".join(lines)

#把某学生某作业下的所有版本导出成 CSV
def _versions_csv(
    assignment_id: int,
    student: str,
    versions: List[Dict[str, Any]],
) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "assignment_id",
            "student",
            "version_id",
            "version_no",
            "submission_id",
            "commit_hash",
            "commit_message",
            "total_score",
            "status_summary",
            "created_at",
        ]
    )
    for v in versions:
        writer.writerow(
            [
                assignment_id,
                student,
                v.get("id"),
                v.get("version_no"),
                v.get("submission_id"),
                v.get("commit_hash"),
                v.get("commit_message") or "",
                v.get("total_score"),
                v.get("status_summary") or "",
                v.get("created_at"),
            ]
        )
    return output.getvalue()


def _save_version_feedback(
    version_id: int,
    assignment_id: int,
    student: str,
    report: Dict[str, Any],
) -> None:
    _execute_statement(
        """
        INSERT INTO version_feedback
        (version_id, assignment_id, student, provider, model_name, summary_text, feedback_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            provider = VALUES(provider),
            model_name = VALUES(model_name),
            summary_text = VALUES(summary_text),
            feedback_json = VALUES(feedback_json)
        """,
        (
            version_id,
            assignment_id,
            student,
            report.get("provider", "heuristic"),
            report.get("model", "heuristic-feedback-v1"),
            report.get("summary", ""),
            json.dumps(report, ensure_ascii=False),
        ),
    )


def _load_version_feedback(version_id: int) -> Optional[Dict[str, Any]]:
    row = _query_one(
        """
        SELECT provider, model_name, summary_text, feedback_json, updated_at
        FROM version_feedback
        WHERE version_id=%s
        """,
        (version_id,),
    )
    if not row:
        return None
    report = json.loads(row.get("feedback_json") or "{}")
    report["provider"] = row.get("provider")
    report["model"] = row.get("model_name")
    report["summary"] = report.get("summary") or row.get("summary_text") or ""
    report["updated_at"] = row.get("updated_at")
    return report


def _contains_chinese_text(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value or ""))


def _feedback_needs_chinese_refresh(report: Optional[Dict[str, Any]]) -> bool:
    if not report:
        return False
    provider = str(report.get("provider") or "").lower()
    if provider not in {"ollama", "openai-compatible", "openai_compatible"}:
        return False
    samples = [
        str(report.get("summary") or ""),
        str(report.get("overall_summary") or ""),
        " ".join(str(item) for item in (report.get("problems") or [])[:2]),
        " ".join(str(item) for item in (report.get("reasons") or [])[:2]),
    ]
    text = " ".join(item for item in samples if item).strip()
    if not text:
        return False
    return not _contains_chinese_text(text) and bool(re.search(r"[A-Za-z]", text))


def _save_student_feedback(
    assignment_id: int,
    student: str,
    version_count: int,
    report: Dict[str, Any],
) -> None:
    _execute_statement(
        """
        INSERT INTO student_feedback
        (assignment_id, student, based_on_version_count, provider, model_name, summary_text, feedback_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            based_on_version_count = VALUES(based_on_version_count),
            provider = VALUES(provider),
            model_name = VALUES(model_name),
            summary_text = VALUES(summary_text),
            feedback_json = VALUES(feedback_json)
        """,
        (
            assignment_id,
            student,
            version_count,
            report.get("provider", "heuristic"),
            report.get("model", "heuristic-feedback-v1"),
            report.get("overall_summary") or report.get("summary", ""),
            json.dumps(report, ensure_ascii=False),
        ),
    )


def _load_student_feedback(assignment_id: int, student: str) -> Optional[Dict[str, Any]]:
    row = _query_one(
        """
        SELECT based_on_version_count, provider, model_name, summary_text, feedback_json, updated_at
        FROM student_feedback
        WHERE assignment_id=%s AND student=%s
        """,
        (assignment_id, student),
    )
    if not row:
        return None
    report = json.loads(row.get("feedback_json") or "{}")
    report["provider"] = row.get("provider")
    report["model"] = row.get("model_name")
    report["overall_summary"] = report.get("overall_summary") or row.get("summary_text") or ""
    report["based_on_version_count"] = row.get("based_on_version_count") or 0
    report["updated_at"] = row.get("updated_at")
    return report


def _build_version_feedback_context(version_id: int) -> Dict[str, Any]:
    version = _query_one(
        """
        SELECT id, assignment_id, student, version_no, submission_id, total_score, commit_hash, commit_message, report_json, created_at
        FROM submission_versions
        WHERE id=%s
        """,
        (version_id,),
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    items = _query_all(
        """
        SELECT problem_id, code, output, score, status
        FROM submission_version_items
        WHERE version_id=%s ORDER BY id ASC
        """,
        (version_id,),
    )
    previous_version = _query_one(
        """
        SELECT id, version_no, total_score, status_summary, created_at
        FROM submission_versions
        WHERE assignment_id=%s AND student=%s AND version_no < %s
        ORDER BY version_no DESC
        LIMIT 1
        """,
        (version["assignment_id"], version["student"], version["version_no"]),
    )
    return {
        "version_id": version_id,
        "assignment_id": version["assignment_id"],
        "student": version["student"],
        "version_no": version["version_no"],
        "total_score": version["total_score"],
        "commit_hash": version.get("commit_hash"),
        "commit_message": version.get("commit_message"),
        "created_at": version.get("created_at"),
        "report": json.loads(version.get("report_json") or "{}"),
        "items": items,
        "previous_version": previous_version,
    }


def _generate_and_store_version_feedback(version_id: int) -> Dict[str, Any]:
    context = _build_version_feedback_context(version_id)
    report = analyze_version_feedback(context)
    _save_version_feedback(version_id, context["assignment_id"], context["student"], report)
    return report


def _build_student_feedback_context(assignment_id: int, student: str) -> Dict[str, Any]:
    versions = _query_all(
        """
        SELECT id, version_no, total_score, commit_hash, commit_message, status_summary, created_at
        FROM submission_versions
        WHERE assignment_id=%s AND student=%s
        ORDER BY version_no ASC
        """,
        (assignment_id, student),
    )
    if not versions:
        raise HTTPException(status_code=404, detail="No versions found for student")

    latest_version_id = int(versions[-1]["id"])
    latest_context = _build_version_feedback_context(latest_version_id)
    return {
        "assignment_id": assignment_id,
        "student": student,
        "versions": versions,
        "latest_version": latest_context,
    }


def _generate_and_store_student_feedback(assignment_id: int, student: str) -> Dict[str, Any]:
    context = _build_student_feedback_context(assignment_id, student)
    report = analyze_student_feedback(context)
    _save_student_feedback(assignment_id, student, len(context["versions"]), report)
    return report


def _submission_code_map(assignment_id: int) -> Dict[tuple, str]:
    rows = _query_all(
        """
        SELECT s.id AS submission_id, si.problem_id AS problem_id, si.code AS code
        FROM submissions s
        JOIN submission_items si ON si.submission_id = s.id
        WHERE s.assignment_id = %s
        """,
        (assignment_id,),
    )
    result: Dict[tuple, str] = {}
    for row in rows:
        result[(int(row["submission_id"]), int(row["problem_id"]))] = row.get("code") or ""
    return result


def _save_ai_report(
    assignment_id: int,
    problem_id: int,
    submission_a: int,
    submission_b: int,
    similarity_score: float,
    report: Dict[str, Any],
) -> None:
    _execute_statement(
        """
        INSERT INTO plagiarism_ai_reports
        (assignment_id, problem_id, submission_a, submission_b, similarity_score, provider, model_name, risk_level, summary_text, report_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            similarity_score = VALUES(similarity_score),
            provider = VALUES(provider),
            model_name = VALUES(model_name),
            risk_level = VALUES(risk_level),
            summary_text = VALUES(summary_text),
            report_json = VALUES(report_json)
        """,
        (
            assignment_id,
            problem_id,
            submission_a,
            submission_b,
            similarity_score,
            report.get("provider", "heuristic"),
            report.get("model", "heuristic-v1"),
            report.get("risk_level", "low"),
            report.get("summary", ""),
            json.dumps(report, ensure_ascii=False),
        ),
    )


def _load_ai_report(
    assignment_id: int,
    problem_id: int,
    submission_a: int,
    submission_b: int,
) -> Optional[Dict[str, Any]]:
    row = _query_one(
        """
        SELECT provider, model_name, risk_level, summary_text, report_json, updated_at
        FROM plagiarism_ai_reports
        WHERE assignment_id=%s AND problem_id=%s AND submission_a=%s AND submission_b=%s
        """,
        (assignment_id, problem_id, submission_a, submission_b),
    )
    if not row:
        return None
    report = json.loads(row.get("report_json") or "{}")
    report["provider"] = row.get("provider")
    report["model"] = row.get("model_name")
    report["risk_level"] = row.get("risk_level")
    report["summary"] = report.get("summary") or row.get("summary_text") or ""
    report["updated_at"] = row.get("updated_at")
    return report


def _ai_review_csv(assignment_id: int, pairs: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "assignment_id",
            "problem_id",
            "submission_a",
            "student_a",
            "submission_b",
            "student_b",
            "similarity_score",
            "provider",
            "model",
            "risk_level",
            "summary",
            "verdict",
        ]
    )
    for pair in pairs:
        ai = pair.get("ai_report") or {}
        writer.writerow(
            [
                assignment_id,
                pair.get("problem_id"),
                pair.get("submission_a"),
                pair.get("student_a"),
                pair.get("submission_b"),
                pair.get("student_b"),
                pair.get("score"),
                ai.get("provider", ""),
                ai.get("model", ""),
                ai.get("risk_level", ""),
                ai.get("summary", ""),
                ai.get("verdict", ""),
            ]
        )
    return output.getvalue()


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup():
        error = init_db()
        if error:
            print(f"Database init failed: {error}")

    @app.get("/")
    def home():
        return {"message": "OS Judge backend running", "version": "2.1"}
    
    #注册功能实现
    @app.post("/auth/register")
    def register_user(payload: UserRegisterRequest):
        username = (payload.username or "").strip()
        password = payload.password or ""
        role = _sanitize_role(payload.role)

        if not username or not password:
            raise HTTPException(status_code=400, detail="username and password are required")
        if len(username) > 50:
            raise HTTPException(status_code=400, detail="username is too long")
        if len(password) < 4:
            raise HTTPException(status_code=400, detail="password must be at least 4 characters")

        #看用户名是否重复
        existing = _query_one("SELECT id FROM users WHERE username=%s", (username,))
        if existing:
            raise HTTPException(status_code=409, detail="username already exists")

        salt, password_hash = _make_password_record(password)
        user_id = _execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (%s, %s, %s, %s)",
            (username, password_hash, salt, role),
        )
        user = _query_one(
            "SELECT id, username, role, created_at FROM users WHERE id=%s",
            (user_id,),
        )
        return {"user": _user_public_view(user or {"id": user_id, "username": username, "role": role})}

    #登录功能实现
    @app.post("/auth/login")
    def login_user(payload: UserLoginRequest):
        username = (payload.username or "").strip()
        password = payload.password or ""
        role_selected = (payload.role or "auto").strip().lower()

        if not username or not password:
            raise HTTPException(status_code=400, detail="username and password are required")

        user = _query_one(
            "SELECT id, username, password_hash, salt, role, created_at FROM users WHERE username=%s",
            (username,),
        )
        if not user:
            raise HTTPException(status_code=401, detail="invalid username or password")

        expected_hash = _hash_password(password, user["salt"])
        if expected_hash != user["password_hash"]:
            raise HTTPException(status_code=401, detail="invalid username or password")

        if role_selected not in {"auto", user["role"]}:
            raise HTTPException(status_code=400, detail="selected role does not match the registered role")

        return {"user": _user_public_view(user)}

    @app.post("/judge")
    def judge_code(request: CodeRequest) -> Dict[str, Any]:
        start_time = time.time()
        is_valid, error_msg = validate_code_security(request.code, request.assignment_type)
        if not is_valid:
            used = time.time() - start_time
            return {
                "status": "CE",
                "message": error_msg,
                "score": 0,
                "time_used": f"{used:.2f}s",
                "assignment_type": request.assignment_type,
                "output": "",
            }

        if request.assignment_type == "process":
            run_result = run_process_code(request.code, request.timeout)
        else:
            run_result = run_normal_code(request.code, request.timeout)

        used = time.time() - start_time
        if not run_result["success"]:
            message = run_result.get("message", "Run failed")
            status = "TLE" if "超时" in message else ("CE" if "编译错误" in message else "RE")
            return {
                "status": status,
                "message": message,
                "score": 0,
                "time_used": f"{used:.2f}s",
                "assignment_type": request.assignment_type,
                "output": run_result.get("output", ""),
            }

        if request.assignment_type == "process":
            eval_result = evaluate_process_assignment(request.code, run_result["output"])
            score = eval_result["total_score"]
            status = "AC" if score == eval_result["max_score"] else ("PA" if score > 0 else "WA")
            return {
                "status": status,
                "message": eval_result["details"],
                "score": score,
                "max_score": eval_result["max_score"],
                "time_used": f"{used:.2f}s",
                "assignment_type": request.assignment_type,
                "output": run_result["output"],
                "test_results": eval_result["results"],
            }

        if request.assignment_type == "memory":
            eval_result = evaluate_memory_assignment(request.code, run_result["output"])
            score = eval_result["total_score"]
            status = "AC" if score == eval_result["max_score"] else ("PA" if score > 0 else "WA")
            return {
                "status": status,
                "message": eval_result["details"],
                "score": score,
                "max_score": eval_result["max_score"],
                "time_used": f"{used:.2f}s",
                "assignment_type": request.assignment_type,
                "output": run_result["output"],
                "test_results": eval_result["results"],
            }

        output = run_result["output"].strip()
        return {
            "status": "AC",
            "message": "Run success",
            "score": 100,
            "max_score": 100,
            "time_used": f"{used:.2f}s",
            "assignment_type": request.assignment_type,
            "output": output,
        }

    @app.get("/assignment-types")
    def get_assignment_types():
        return {
            "types": ["normal", "process", "file", "memory"],
            "descriptions": {
                "normal": "Normal C programming assignment",
                "process": "Process management assignment",
                "file": "File system assignment",
                "memory": "Memory management assignment (malloc/free/null/runtime checks)",
            },
        }

    @app.get("/template/{type_name}")
    def get_template(type_name: str):
        template_files = {
            "normal": "normal.txt",
            "file": "normal.txt",
            "process": "process.txt",
            "memory": "memory.txt",
        }
        if type_name not in template_files:
            raise HTTPException(status_code=404, detail="Template type not found")
        template_file = TEMPLATES_DIR / template_files[type_name]
        if not template_file.exists():
            raise HTTPException(status_code=404, detail=f"Template not found: {template_file}")
        code = template_file.read_text(encoding="utf-8")
        return {"code": code, "type": type_name}

    @app.post("/assignments")
    def create_assignment(payload: AssignmentCreateRequest):
        if not payload.problems:#确认至少有一道题
            raise HTTPException(status_code=400, detail="Assignment must include problems")
        normalized_deadline = _normalize_deadline(payload.deadline_at)

        #将整体信息写入作业表
        assignment_id = _execute(
            "INSERT INTO assignments (title, description, teacher, deadline_at) VALUES (%s, %s, %s, %s)",
            (
                payload.title,
                payload.description,
                payload.teacher,
                normalized_deadline.strftime("%Y-%m-%d %H:%M:%S") if normalized_deadline else None,
            ),
        )

        #将作业里的每一道题插入题目表
        for problem in payload.problems:
            test_cases = json.dumps([case.dict() for case in problem.test_cases], ensure_ascii=False)
            _execute(
                """
                INSERT INTO problems
                (assignment_id, title, description, problem_type, points, test_cases, time_limit, memory_limit, pids_limit, file_size_limit, syscall_allowlist, syscall_denylist)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    assignment_id,
                    problem.title,
                    problem.description,
                    problem.problem_type,
                    problem.points,
                    test_cases,
                    problem.time_limit,
                    problem.memory_limit,
                    problem.pids_limit,
                    problem.file_size_limit,
                    json.dumps(problem.syscall_allowlist, ensure_ascii=False),
                    json.dumps(problem.syscall_denylist, ensure_ascii=False),
                ),
            )
        return {"assignment_id": assignment_id}

    @app.get("/assignments")
    def list_assignments():
        rows = _query_all(
            """
            SELECT a.id, a.title, a.description, a.teacher, a.deadline_at, a.created_at,
                   (SELECT COUNT(*) FROM problems p WHERE p.assignment_id = a.id) AS problem_count
            FROM assignments a ORDER BY a.id DESC
            """
        )
        return {"assignments": rows}

    @app.get("/assignments/{assignment_id}")
    def get_assignment(assignment_id: int):
        assignment = _query_one(
            "SELECT id, title, description, teacher, deadline_at, created_at FROM assignments WHERE id=%s",
            (assignment_id,),
        )
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        problems = _query_all(
            """
            SELECT id, title, description, problem_type, points, test_cases, time_limit, memory_limit, pids_limit, file_size_limit, syscall_allowlist, syscall_denylist
            FROM problems WHERE assignment_id=%s ORDER BY id ASC
            """,
            (assignment_id,),
        )
        for problem in problems:
            problem["test_cases"] = json.loads(problem["test_cases"] or "[]")
            problem["syscall_allowlist"] = json.loads(problem["syscall_allowlist"] or "[]")
            problem["syscall_denylist"] = json.loads(problem["syscall_denylist"] or "[]")
        assignment["problems"] = problems
        return assignment

    @app.post("/assignments/{assignment_id}/submit")
    def submit_assignment(assignment_id: int, payload: AssignmentSubmitRequest):
        assignment = _query_one(
            "SELECT id, deadline_at FROM assignments WHERE id=%s",
            (assignment_id,),
        )
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        deadline_at = assignment.get("deadline_at")
        if deadline_at and _now() > deadline_at:
            raise HTTPException(status_code=400, detail="Assignment deadline passed")

        problems = _query_all(
            """
            SELECT id, problem_type, points, test_cases, time_limit, memory_limit, pids_limit, file_size_limit, syscall_allowlist, syscall_denylist
            FROM problems WHERE assignment_id=%s
            """,
            (assignment_id,),
        )
        problem_map: Dict[int, Dict[str, Any]] = {}
        for problem in problems:
            problem["test_cases"] = json.loads(problem["test_cases"] or "[]")
            problem["syscall_allowlist"] = json.loads(problem["syscall_allowlist"] or "[]")
            problem["syscall_denylist"] = json.loads(problem["syscall_denylist"] or "[]")
            problem_map[problem["id"]] = problem

        start_time = time.time()
        submission_results = []
        total_score = 0
        for item in payload.items:
            problem = problem_map.get(item.problem_id)
            if not problem:
                submission_results.append(
                    {
                        "problem_id": item.problem_id,
                        "status": "WA",
                        "message": "Problem not found",
                        "score": 0,
                        "output": "",
                        "test_results": [],
                        "problem_type": "unknown",
                        "limits": {},
                    }
                )
                continue

            is_valid, error_msg = validate_code_security(
                item.code,
                problem["problem_type"],
                problem.get("syscall_allowlist"),
                problem.get("syscall_denylist"),
            )
            if not is_valid:
                submission_results.append(
                    {
                        "problem_id": item.problem_id,
                        "status": "CE",
                        "message": error_msg,
                        "score": 0,
                        "output": "",
                        "test_results": [],
                        "problem_type": problem["problem_type"],
                        "limits": {},
                    }
                )
                continue

            effective_timeout = int(problem.get("time_limit") or item.timeout)
            result = _run_problem(problem, item.code, effective_timeout)
            result["problem_id"] = item.problem_id
            submission_results.append(result)
            total_score += int(result.get("score", 0))

        time_used = time.time() - start_time
        report = _build_submission_report(
            assignment_id, payload.student, total_score, time_used, submission_results
        )
        report_json = json.dumps(report, ensure_ascii=False)
        submission_id = _execute(
            "INSERT INTO submissions (assignment_id, student, total_score, report_json) VALUES (%s, %s, %s, %s)",
            (assignment_id, payload.student, total_score, report_json),
        )

        for item_result, item in zip(submission_results, payload.items):
            _execute(
                """
                INSERT INTO submission_items (submission_id, problem_id, code, output, score, status, time_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    submission_id,
                    item.problem_id,
                    item.code,
                    item_result.get("output", ""),
                    int(item_result.get("score", 0)),
                    item_result.get("status", ""),
                    f"{time_used:.2f}s",
                ),
            )

        version_no = _next_version_no(assignment_id, payload.student)
        commit_hash = _build_commit_hash(assignment_id, payload.student, submission_results)
        commit_message = (payload.commit_message or "").strip() or f"Auto submission v{version_no}"
        status_summary = _build_status_summary(submission_results)
        version_id = _execute(
            """
            INSERT INTO submission_versions
            (assignment_id, student, version_no, submission_id, commit_hash, commit_message, total_score, status_summary, report_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                assignment_id,
                payload.student,
                version_no,
                submission_id,
                commit_hash,
                commit_message,
                total_score,
                status_summary,
                report_json,
            ),
        )
        for item_result, item in zip(submission_results, payload.items):
            _execute(
                """
                INSERT INTO submission_version_items
                (version_id, problem_id, code, output, score, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    version_id,
                    item.problem_id,
                    item.code,
                    item_result.get("output", ""),
                    int(item_result.get("score", 0)),
                    item_result.get("status", ""),
                ),
            )

        version_feedback = None
        student_feedback = None
        feedback_errors: List[str] = []

        # Keep feedback generation attached to submit so students and teachers
        # can view the latest guidance immediately after a new version is created.
        try:
            version_feedback = _generate_and_store_version_feedback(version_id)
        except Exception as exc:
            feedback_errors.append(f"version_feedback: {exc}")

        try:
            student_feedback = _generate_and_store_student_feedback(assignment_id, payload.student)
        except Exception as exc:
            feedback_errors.append(f"student_feedback: {exc}")

        return {
            "submission_id": submission_id,
            "version_id": version_id,
            "version_no": version_no,
            "commit_hash": commit_hash,
            "assignment_id": assignment_id,
            "student": payload.student,
            "total_score": total_score,
            "time_used": f"{time_used:.2f}s",
            "items": submission_results,
            "report": report,
            "version_feedback": version_feedback,
            "student_feedback": student_feedback,
            "feedback_errors": feedback_errors,
        }

    @app.get("/assignments/{assignment_id}/submissions")
    def list_submissions(assignment_id: int, student: Optional[str] = None):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        if student:
            rows = _query_all(
                "SELECT id, assignment_id, student, total_score, created_at FROM submissions WHERE assignment_id=%s AND student=%s ORDER BY id DESC",
                (assignment_id, student),
            )
        else:
            rows = _query_all(
                "SELECT id, assignment_id, student, total_score, created_at FROM submissions WHERE assignment_id=%s ORDER BY id DESC",
                (assignment_id,),
            )
        return {"submissions": rows}

    @app.get("/submissions/{submission_id}")
    def get_submission(submission_id: int):
        submission = _query_one(
            "SELECT id, assignment_id, student, total_score, created_at, report_json FROM submissions WHERE id=%s",
            (submission_id,),
        )
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        items = _query_all(
            "SELECT problem_id, score, status, time_used, output FROM submission_items WHERE submission_id=%s ORDER BY id ASC",
            (submission_id,),
        )
        submission["items"] = items
        submission["report"] = json.loads(submission.get("report_json") or "{}")
        return submission

    @app.get("/assignments/{assignment_id}/versions")
    def list_versions(assignment_id: int, student: str):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        rows = _query_all(
            """
            SELECT id, assignment_id, student, version_no, submission_id, commit_hash, commit_message,
                   total_score, status_summary, created_at
            FROM submission_versions
            WHERE assignment_id=%s AND student=%s
            ORDER BY version_no DESC
            """,
            (assignment_id, student),
        )
        return {"versions": rows}

    @app.get("/assignments/{assignment_id}/versions/export")
    def export_versions(assignment_id: int, student: str):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        rows = _query_all(
            """
            SELECT id, assignment_id, student, version_no, submission_id, commit_hash, commit_message,
                   total_score, status_summary, created_at
            FROM submission_versions
            WHERE assignment_id=%s AND student=%s
            ORDER BY version_no DESC
            """,
            (assignment_id, student),
        )
        content = _versions_csv(assignment_id, student, rows)
        filename = f"versions_assignment_{assignment_id}_{student}.csv"
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/assignments/{assignment_id}/version-students")
    def list_version_students(assignment_id: int):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        rows = _query_all(
            """
            SELECT student, COUNT(*) AS version_count, MAX(created_at) AS last_submit_at
            FROM submission_versions
            WHERE assignment_id=%s
            GROUP BY student
            ORDER BY last_submit_at DESC
            """,
            (assignment_id,),
        )
        return {"students": rows}

    @app.get("/versions/{version_id}")
    def get_version(version_id: int):
        version = _query_one(
            """
            SELECT id, assignment_id, student, version_no, submission_id, commit_hash, commit_message,
                   total_score, status_summary, report_json, created_at
            FROM submission_versions WHERE id=%s
            """,
            (version_id,),
        )
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        items = _query_all(
            """
            SELECT problem_id, score, status, output
            FROM submission_version_items
            WHERE version_id=%s ORDER BY id ASC
            """,
            (version_id,),
        )
        version["items"] = items
        version["report"] = json.loads(version.get("report_json") or "{}")
        version["feedback"] = _load_version_feedback(version_id)
        if _feedback_needs_chinese_refresh(version["feedback"]):
            version["feedback"] = _generate_and_store_version_feedback(version_id)
        return version

    @app.get("/versions/{version_id}/feedback")
    def get_version_feedback(version_id: int):
        if not _query_one("SELECT id FROM submission_versions WHERE id=%s", (version_id,)):
            raise HTTPException(status_code=404, detail="Version not found")
        report = _load_version_feedback(version_id)
        if _feedback_needs_chinese_refresh(report):
            report = _generate_and_store_version_feedback(version_id)
        return {"version_id": version_id, "feedback": report}

    @app.post("/versions/{version_id}/feedback/generate")
    def generate_version_feedback(version_id: int, refresh: bool = False):
        if not _query_one("SELECT id FROM submission_versions WHERE id=%s", (version_id,)):
            raise HTTPException(status_code=404, detail="Version not found")
        report = None if refresh else _load_version_feedback(version_id)
        if not report:
            report = _generate_and_store_version_feedback(version_id)
        return {"version_id": version_id, "feedback": report}

    @app.get("/assignments/{assignment_id}/final-score")
    def get_final_score(assignment_id: int, student: str, policy: str = "last"):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        if policy not in {"last", "best"}:
            raise HTTPException(status_code=400, detail="policy must be last or best")

        order_sql = "ORDER BY version_no DESC LIMIT 1" if policy == "last" else "ORDER BY total_score DESC, version_no DESC LIMIT 1"
        row = _query_one(
            f"""
            SELECT id, assignment_id, student, version_no, submission_id, total_score, commit_hash, created_at
            FROM submission_versions
            WHERE assignment_id=%s AND student=%s
            {order_sql}
            """,
            (assignment_id, student),
        )
        if not row:
            return {"assignment_id": assignment_id, "student": student, "policy": policy, "final": None}
        return {"assignment_id": assignment_id, "student": student, "policy": policy, "final": row}

    @app.get("/assignments/{assignment_id}/students/{student}/feedback")
    def get_student_feedback(assignment_id: int, student: str):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        report = _load_student_feedback(assignment_id, student)
        if _feedback_needs_chinese_refresh(report):
            report = _generate_and_store_student_feedback(assignment_id, student)
        return {"assignment_id": assignment_id, "student": student, "feedback": report}

    @app.post("/assignments/{assignment_id}/students/{student}/feedback/generate")
    def generate_student_feedback(assignment_id: int, student: str, refresh: bool = False):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        report = None if refresh else _load_student_feedback(assignment_id, student)
        if not report:
            report = _generate_and_store_student_feedback(assignment_id, student)
        return {"assignment_id": assignment_id, "student": student, "feedback": report}

    @app.get("/assignments/{assignment_id}/plagiarism")
    def plagiarism_check(assignment_id: int, threshold: float = 0.7, k: int = 5, w: int = 4):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        pairs = _collect_plagiarism_pairs(assignment_id, threshold=threshold, k=k, w=w)
        return {"assignment_id": assignment_id, "threshold": threshold, "k": k, "w": w, "pairs": pairs}

    @app.post("/assignments/{assignment_id}/plagiarism/ai-review")
    def plagiarism_ai_review(
        assignment_id: int,
        threshold: float = 0.7,
        k: int = 5,
        w: int = 4,
        refresh: bool = False,
    ):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")

        pairs = _collect_plagiarism_pairs(assignment_id, threshold=threshold, k=k, w=w)
        code_map = _submission_code_map(assignment_id)
        reviewed_pairs: List[Dict[str, Any]] = []

        for pair in pairs:
            problem_id = int(pair["problem_id"])
            submission_a = int(pair["submission_a"])
            submission_b = int(pair["submission_b"])

            ai_report = None if refresh else _load_ai_report(
                assignment_id,
                problem_id,
                submission_a,
                submission_b,
            )
            if not ai_report:
                code_a = code_map.get((submission_a, problem_id), "")
                code_b = code_map.get((submission_b, problem_id), "")
                ai_report = analyze_plagiarism_pair(code_a, code_b, pair)
                _save_ai_report(
                    assignment_id,
                    problem_id,
                    submission_a,
                    submission_b,
                    float(pair.get("score") or 0.0),
                    ai_report,
                )
            enriched = dict(pair)
            enriched["ai_report"] = ai_report
            reviewed_pairs.append(enriched)

        return {
            "assignment_id": assignment_id,
            "threshold": threshold,
            "k": k,
            "w": w,
            "pairs": reviewed_pairs,
        }

    @app.get("/assignments/{assignment_id}/plagiarism/ai-review/export")
    def plagiarism_ai_review_export(
        assignment_id: int,
        threshold: float = 0.7,
        k: int = 5,
        w: int = 4,
    ):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        pairs = _collect_plagiarism_pairs(assignment_id, threshold=threshold, k=k, w=w)
        enriched_pairs: List[Dict[str, Any]] = []
        for pair in pairs:
            ai_report = _load_ai_report(
                assignment_id,
                int(pair["problem_id"]),
                int(pair["submission_a"]),
                int(pair["submission_b"]),
            )
            enriched = dict(pair)
            enriched["ai_report"] = ai_report or {}
            enriched_pairs.append(enriched)
        filename = f"plagiarism_ai_assignment_{assignment_id}.csv"
        return Response(
            content=_ai_review_csv(assignment_id, enriched_pairs),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/assignments/{assignment_id}/plagiarism/export")
    def plagiarism_export(
        assignment_id: int,
        threshold: float = 0.7,
        k: int = 5,
        w: int = 4,
        format: str = "csv",
    ):
        if not _query_one("SELECT id FROM assignments WHERE id=%s", (assignment_id,)):
            raise HTTPException(status_code=404, detail="Assignment not found")
        pairs = _collect_plagiarism_pairs(assignment_id, threshold=threshold, k=k, w=w)
        export_format = (format or "csv").lower()

        if export_format == "txt":
            content = _plagiarism_txt(assignment_id, threshold, k, w, pairs)
            filename = f"plagiarism_assignment_{assignment_id}.txt"
            return PlainTextResponse(
                content=content,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        if export_format == "csv":
            content = _plagiarism_csv(assignment_id, threshold, k, w, pairs)
            filename = f"plagiarism_assignment_{assignment_id}.csv"
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        raise HTTPException(status_code=400, detail="Unsupported format, use csv or txt")

    return app
