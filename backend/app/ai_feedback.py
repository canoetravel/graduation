import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List


DEFAULT_PROVIDER = (
    os.getenv("AI_FEEDBACK_PROVIDER")
    or os.getenv("AI_PLAGIARISM_PROVIDER")
    or "heuristic"
).strip()
DEFAULT_MODEL = (
    os.getenv("AI_FEEDBACK_MODEL")
    or os.getenv("AI_PLAGIARISM_MODEL")
    or "heuristic-feedback-v1"
).strip()
DEFAULT_BASE_URL = (
    os.getenv("AI_FEEDBACK_BASE_URL")
    or os.getenv("AI_PLAGIARISM_BASE_URL")
    or ""
).strip()
DEFAULT_API_KEY = (
    os.getenv("AI_FEEDBACK_API_KEY")
    or os.getenv("AI_PLAGIARISM_API_KEY")
    or ""
).strip()
DEFAULT_TIMEOUT = int(
    os.getenv("AI_FEEDBACK_TIMEOUT")
    or os.getenv("AI_PLAGIARISM_TIMEOUT")
    or "30"
)


def _truncate_text(text: str, max_len: int = 5000) -> str:
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n[truncated]"


def _normalize_feedback(report: Dict[str, Any], provider: str) -> Dict[str, Any]:
    report["provider"] = provider
    report["model"] = DEFAULT_MODEL
    report.setdefault("summary", "未生成摘要。")
    report.setdefault("strengths", [])
    report.setdefault("problems", [])
    report.setdefault("next_steps", [])
    report.setdefault("study_suggestions", [])
    report.setdefault("teacher_view", "")
    report.setdefault("progress_trend", "stable")
    report.setdefault("overall_summary", report.get("summary", ""))
    report.setdefault("recurring_issues", report.get("problems", []))
    return report


def _build_version_heuristic(context: Dict[str, Any]) -> Dict[str, Any]:
    report = context.get("report") or {}
    items = context.get("items") or []
    total_score = int(context.get("total_score") or 0)
    max_score = sum(int(item.get("score") or 0) for item in items) or total_score
    statuses = [str(item.get("status") or "") for item in items]
    strengths: List[str] = []
    problems: List[str] = []
    next_steps: List[str] = []
    study_suggestions: List[str] = []

    if any(status == "AC" for status in statuses):
        strengths.append("部分题目已经达到正确结果，说明基础实现方向是对的。")
    if total_score > 0:
        strengths.append("当前版本已经有可工作的代码提交，具备继续迭代的基础。")
    if any(status in {"CE", "RE"} for status in statuses):
        problems.append("当前版本仍存在编译错误或运行时错误，需要先保证程序能稳定运行。")
        next_steps.append("优先修复编译错误和运行错误，再继续优化功能细节。")
        study_suggestions.append("复习 C 语言编译错误定位和基本调试方法。")
    if any(status in {"WA", "PA"} for status in statuses):
        problems.append("部分测试点未通过，说明功能正确性或边界处理仍需加强。")
        next_steps.append("对照未通过题目的输出结果，逐个检查条件分支和边界情况。")
    if not problems:
        next_steps.append("可以继续优化代码结构、注释和异常情况处理。")
        study_suggestions.append("复习代码规范和鲁棒性设计，提高程序可维护性。")
    if not strengths:
        strengths.append("已经完成了一次可评测提交，具备继续改进的基础。")

    test_points = report.get("test_points") or {}
    passed = int(test_points.get("passed") or 0)
    total = int(test_points.get("total") or 0)
    summary = (
        f"本次版本总分 {total_score}。"
        + (f" 测试点通过 {passed}/{total}。" if total else "")
    )
    teacher_view = (
        "建议先关注基础正确性和运行稳定性，再引导学生优化边界情况与代码规范。"
        if problems
        else "当前版本整体较稳定，可引导学生继续优化代码质量和复杂场景处理。"
    )

    return _normalize_feedback(
        {
            "summary": summary,
            "strengths": strengths[:3],
            "problems": problems[:3],
            "next_steps": next_steps[:3],
            "study_suggestions": study_suggestions[:3],
            "teacher_view": teacher_view,
        },
        "heuristic",
    )


def _build_student_heuristic(context: Dict[str, Any]) -> Dict[str, Any]:
    versions = context.get("versions") or []
    final_version = context.get("final_version") or {}
    scores = [int(v.get("total_score") or 0) for v in versions]
    strengths: List[str] = []
    recurring_issues: List[str] = []
    study_suggestions: List[str] = []

    if len(scores) >= 2 and scores[0] >= scores[-1]:
        progress_trend = "improving"
        strengths.append("从版本变化看，学生整体有持续改进趋势。")
    elif len(scores) >= 2:
        progress_trend = "fluctuating"
        recurring_issues.append("不同版本之间表现波动较大，说明知识点掌握还不够稳定。")
    else:
        progress_trend = "early"
        recurring_issues.append("当前版本样本较少，建议继续提交更多版本观察学习趋势。")

    if final_version:
        strengths.append(
            f"当前最终参考版本为 v{final_version.get('version_no')}，总分 {final_version.get('total_score')}。"
        )

    recent_summaries = [str(v.get("status_summary") or "") for v in versions[:3] if v.get("status_summary")]
    if recent_summaries:
        recurring_issues.append("近期版本的状态摘要显示，仍需要持续关注未通过题目的共性问题。")

    study_suggestions.extend(
        [
            "针对反复未通过的题目，总结错误模式并建立自己的调试清单。",
            "结合版本记录回顾每次改动是否真正解决了问题，避免重复试错。",
        ]
    )

    overall_summary = (
        f"该学生在当前作业下共提交 {len(versions)} 个版本，"
        + (f"分数区间为 {min(scores)} 到 {max(scores)}。" if scores else "暂时还没有有效版本数据。")
    )
    teacher_view = (
        "可结合版本轨迹观察学生是否存在重复性错误，并据此给出针对性的知识点辅导建议。"
    )

    return _normalize_feedback(
        {
            "overall_summary": overall_summary,
            "summary": overall_summary,
            "progress_trend": progress_trend,
            "strengths": strengths[:3],
            "recurring_issues": recurring_issues[:3],
            "problems": recurring_issues[:3],
            "next_steps": [
                "优先解决最近版本中仍未通过的题目。",
                "对照历史版本，确认每次改动是否带来了稳定提升。",
            ],
            "study_suggestions": study_suggestions[:3],
            "teacher_view": teacher_view,
        },
        "heuristic",
    )


def _build_version_prompt(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task": "Provide formative feedback for a student's programming submission.",
        "instructions": [
            "请聚焦学习反馈，而不仅仅是分数说明。",
            "请给出具体、建设性的建议。",
            "所有输出内容必须使用简体中文。",
            "只返回严格 JSON。",
        ],
        "output_schema": {
            "summary": "short summary",
            "strengths": ["point 1"],
            "problems": ["point 1"],
            "next_steps": ["step 1"],
            "study_suggestions": ["topic 1"],
            "teacher_view": "teacher-facing note",
        },
        "context": {
            "assignment_id": context.get("assignment_id"),
            "student": context.get("student"),
            "version_no": context.get("version_no"),
            "total_score": context.get("total_score"),
            "previous_version": context.get("previous_version"),
            "report": context.get("report"),
            "items": context.get("items"),
        },
    }


def _build_student_prompt(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task": "Summarize a student's learning progress across multiple versions in one assignment.",
        "instructions": [
            "请聚焦进步趋势、反复出现的问题和学习建议。",
            "所有输出内容必须使用简体中文。",
            "只返回严格 JSON。",
        ],
        "output_schema": {
            "overall_summary": "short summary",
            "progress_trend": "improving|stable|fluctuating|early",
            "strengths": ["point 1"],
            "recurring_issues": ["issue 1"],
            "next_steps": ["step 1"],
            "study_suggestions": ["topic 1"],
            "teacher_view": "teacher-facing note",
        },
        "context": {
            "assignment_id": context.get("assignment_id"),
            "student": context.get("student"),
            "version_count": len(context.get("versions") or []),
            "versions": context.get("versions"),
            "final_version": context.get("final_version") or context.get("latest_version"),
        },
    }


def _call_openai_compatible(prompt_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not DEFAULT_BASE_URL or not DEFAULT_API_KEY:
        raise RuntimeError("AI provider config missing")

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是 C 语言编程作业的学习反馈助手。所有输出内容必须使用简体中文，并且只返回严格 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        DEFAULT_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEFAULT_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return json.loads(raw["choices"][0]["message"]["content"])


def _call_ollama(prompt_payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = DEFAULT_BASE_URL or "http://host.docker.internal:11434/api/chat"
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是 C 语言编程作业的学习反馈助手。所有输出内容必须使用简体中文，并且只返回严格 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=False),
            },
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return json.loads(raw["message"]["content"])


def analyze_version_feedback(context: Dict[str, Any]) -> Dict[str, Any]:
    provider = DEFAULT_PROVIDER.lower()
    prompt_payload = _build_version_prompt(
        {
            **context,
            "report": _truncate_text(json.dumps(context.get("report") or {}, ensure_ascii=False), 3000),
            "items": _truncate_text(json.dumps(context.get("items") or [], ensure_ascii=False), 4000),
        }
    )
    try:
        if provider == "openai_compatible":
            return _normalize_feedback(_call_openai_compatible(prompt_payload), "openai-compatible")
        if provider == "ollama":
            return _normalize_feedback(_call_ollama(prompt_payload), "ollama")
    except (RuntimeError, KeyError, ValueError, urllib.error.URLError, urllib.error.HTTPError):
        report = _build_version_heuristic(context)
        report["fallback"] = f"{provider} 调用失败，已回退到启发式建议。"
        return report
    return _build_version_heuristic(context)


def analyze_student_feedback(context: Dict[str, Any]) -> Dict[str, Any]:
    provider = DEFAULT_PROVIDER.lower()
    versions = context.get("versions") or []
    compact_versions = [
        {
            "version_no": item.get("version_no"),
            "total_score": item.get("total_score"),
            "status_summary": item.get("status_summary"),
            "created_at": item.get("created_at"),
        }
        for item in versions[-8:]
    ]
    latest_version = context.get("latest_version") or {}
    prompt_payload = _build_student_prompt(
        {
            **context,
            "versions": _truncate_text(
                json.dumps(compact_versions, ensure_ascii=False, default=str),
                2200,
            ),
            "final_version": _truncate_text(
                json.dumps(latest_version, ensure_ascii=False, default=str),
                1200,
            ),
        }
    )
    try:
        if provider == "openai_compatible":
            return _normalize_feedback(_call_openai_compatible(prompt_payload), "openai-compatible")
        if provider == "ollama":
            return _normalize_feedback(_call_ollama(prompt_payload), "ollama")
    except (RuntimeError, KeyError, ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout):
        report = _build_student_heuristic(context)
        report["fallback"] = f"{provider} 调用失败，已回退到启发式建议。"
        return report
    return _build_student_heuristic(context)
