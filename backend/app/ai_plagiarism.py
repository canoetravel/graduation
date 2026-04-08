import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .plagiarism import tokenize_c


DEFAULT_PROVIDER = os.getenv("AI_PLAGIARISM_PROVIDER", "heuristic").strip() or "heuristic"
DEFAULT_MODEL = os.getenv("AI_PLAGIARISM_MODEL", "heuristic-v1").strip() or "heuristic-v1"
DEFAULT_BASE_URL = os.getenv("AI_PLAGIARISM_BASE_URL", "").strip()
DEFAULT_API_KEY = os.getenv("AI_PLAGIARISM_API_KEY", "").strip()
DEFAULT_TIMEOUT = int(os.getenv("AI_PLAGIARISM_TIMEOUT", "30"))

#若代码太长则截断
def _truncate_code(code: str, max_len: int = 4000) -> str:
    code = code or ""
    if len(code) <= max_len:
        return code
    return code[:max_len] + "\n/* truncated */"

#无模型时的本地解释器
def _build_heuristic_report(
    code_a: str,
    code_b: str,
    pair: Dict[str, Any],
) -> Dict[str, Any]:
    evidence = pair.get("evidence") or {}
    score = float(pair.get("score") or 0.0)
    tokens_a = tokenize_c(code_a)
    tokens_b = tokenize_c(code_b)
    len_a = len(tokens_a)
    len_b = len(tokens_b)
    token_gap = abs(len_a - len_b)
    snippets = evidence.get("shared_snippets") or []
    shared_fp = int(evidence.get("shared_fingerprints") or 0)

    reasons: List[str] = []
    differences: List[str] = []

    if score >= 0.9:
        risk_level = "high"
        reasons.append("两份代码在整体结构和核心实现路径上高度重合。")
    elif score >= 0.75:
        risk_level = "high"
        reasons.append("两份代码存在较高相似度，核心逻辑和组织方式明显接近。")
    elif score >= 0.55:
        risk_level = "medium"
        reasons.append("代码存在一定结构相似性，建议结合实现细节继续复核。")
    else:
        risk_level = "low"
        reasons.append("当前仅发现有限相似特征，暂不构成明显高风险。")

    if shared_fp >= 12:
        reasons.append(f"共享指纹数量达到 {shared_fp}，重合特征较多。")
    if snippets:
        reasons.append("存在共享代码片段，且片段能够体现局部实现思路。")
    if token_gap <= 5:
        reasons.append("两份代码的 Token 规模非常接近，整体复杂度相似。")
    else:
        differences.append(f"两份代码的 Token 数量差值为 {token_gap}，存在一定规模差异。")

    if not snippets:
        differences.append("暂未提取到稳定的共享代码片段，更多依赖整体特征判断。")
    if token_gap > 20:
        differences.append("代码规模差异较大，可能存在补充功能或删减逻辑。")

    if risk_level == "high":
        verdict = "建议教师重点复核这组代码，并结合提交时间线与版本记录综合判断。"
    elif risk_level == "medium":
        verdict = "建议教师查看关键函数与共享片段，进一步确认是否属于独立完成。"
    else:
        verdict = "当前风险较低，可先保留结果，必要时再做人工抽查。"

    summary = (
        f"相似度 {score:.2f}，共享指纹 {shared_fp} 个，"
        f"Token 规模 {len_a}/{len_b}，综合风险等级为 {risk_level}。"
    )

    return {
        "provider": "heuristic",
        "model": DEFAULT_MODEL,
        "risk_level": risk_level,
        "summary": summary,
        "reasons": reasons[:4],
        "differences": differences[:3],
        "verdict": verdict,
    }

#给大模型构造提示词的函数
def _build_prompt(code_a: str, code_b: str, pair: Dict[str, Any]) -> Dict[str, Any]:
    evidence = pair.get("evidence") or {}
    return {
        "task": "比较两份 C 语言作业代码，判断是否存在抄袭风险。",
        "instructions": [
            "忽略变量改名、格式调整和注释差异。",
            "重点分析控制流、函数拆分、核心数据处理和错误路径。",
            "所有输出内容必须使用简体中文。",
            "只返回严格 JSON。",
        ],
        "output_schema": {
            "risk_level": "low|medium|high",
            "summary": "简短摘要",
            "reasons": ["原因 1", "原因 2"],
            "differences": ["差异 1"],
            "verdict": "给教师的建议",
        },
        "pair_meta": {
            "score": pair.get("score"),
            "problem_id": pair.get("problem_id"),
            "shared_fingerprints": evidence.get("shared_fingerprints"),
            "shared_snippets": evidence.get("shared_snippets") or [],
        },
        "code_a": _truncate_code(code_a),
        "code_b": _truncate_code(code_b),
    }

#统一ai输出的格式
def _normalize_json_report(report: Dict[str, Any], provider: str) -> Dict[str, Any]:
    report["provider"] = provider
    report["model"] = DEFAULT_MODEL
    report.setdefault("risk_level", "medium")
    report.setdefault("summary", "模型已返回结果，但未提供完整摘要。")
    report.setdefault("reasons", [])
    report.setdefault("differences", [])
    report.setdefault("verdict", "建议教师结合证据片段进一步进行人工复核。")
    return report

#调用 OpenAI 兼容接口
def _call_openai_compatible(code_a: str, code_b: str, pair: Dict[str, Any]) -> Dict[str, Any]:
    if not DEFAULT_BASE_URL or not DEFAULT_API_KEY:
        raise RuntimeError("AI provider config missing")

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你负责分析 C 语言作业中的可疑抄袭情况。所有输出内容必须使用简体中文，并且只返回严格 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(_build_prompt(code_a, code_b, pair), ensure_ascii=False),
            },
        ],
        "temperature": 0.1,
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

    content = raw["choices"][0]["message"]["content"]
    report = json.loads(content)
    return _normalize_json_report(report, "openai-compatible")

#调用Ollama 的 /api/chat 接口
def _call_ollama(code_a: str, code_b: str, pair: Dict[str, Any]) -> Dict[str, Any]:
    base_url = DEFAULT_BASE_URL or "http://host.docker.internal:11434/api/chat"
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你负责分析 C 语言作业中的可疑抄袭情况。所有输出内容必须使用简体中文，并且只返回严格 JSON。",
            },
            {
                "role": "user",
                "content": json.dumps(_build_prompt(code_a, code_b, pair), ensure_ascii=False),
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
        },
    }

    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    content = raw["message"]["content"]
    report = json.loads(content)
    return _normalize_json_report(report, "ollama")

#总的调用函数
def analyze_plagiarism_pair(code_a: str, code_b: str, pair: Dict[str, Any]) -> Dict[str, Any]:
    provider = DEFAULT_PROVIDER.lower()
    try:
        if provider == "openai_compatible":
            return _call_openai_compatible(code_a, code_b, pair)
        if provider == "ollama":
            return _call_ollama(code_a, code_b, pair)
    except (RuntimeError, KeyError, ValueError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout):
        report = _build_heuristic_report(code_a, code_b, pair)
        report["fallback"] = f"{provider} 调用失败，已回退到启发式复核。"
        return report
    return _build_heuristic_report(code_a, code_b, pair)
