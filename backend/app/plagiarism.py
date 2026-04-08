import hashlib
import re
from typing import Any, Dict, List, Set, Tuple

#定义C语言的关键字
C_KEYWORDS = {
    "auto",
    "break",
    "case",
    "char",
    "const",
    "continue",
    "default",
    "do",
    "double",
    "else",
    "enum",
    "extern",
    "float",
    "for",
    "goto",
    "if",
    "inline",
    "int",
    "long",
    "register",
    "restrict",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "struct",
    "switch",
    "typedef",
    "union",
    "unsigned",
    "void",
    "volatile",
    "while",
}


def _strip_comments_and_strings(code: str) -> str:
    # 去除字面量
    code = re.sub(r"\"(\\.|[^\"\\])*\"", " ", code)
    code = re.sub(r"'(\\.|[^'\\])*'", " ", code)
    # 去除注释
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)
    code = re.sub(r"//.*?$", " ", code, flags=re.M)
    return code

#去处理每一个学生提交的代码
def tokenize_c(code: str) -> List[str]:
    code = _strip_comments_and_strings(code)
    raw_tokens = re.findall(
        r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|->|[{}()\[\];,=+\-*/%<>!&|]",
        code,
    )
    tokens: List[str] = []
    for token in raw_tokens:
        if re.match(r"[A-Za-z_]\w*$", token) and token not in C_KEYWORDS:#非关键字的标识符
            tokens.append("ID")
        elif re.match(r"\d+$", token):#数字
            tokens.append("NUM")
        else:
            tokens.append(token)#其余token
    return tokens

#压缩为指纹集合
def winnowing_fingerprints(tokens: List[str], k: int = 5, w: int = 4) -> Set[int]:
    if len(tokens) < k:
        return set()
    kgrams = [" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)]
    hashes = [int(hashlib.sha1(kg.encode("utf-8")).hexdigest()[:16], 16) for kg in kgrams]
    if len(hashes) <= w:
        return set(hashes)
    fingerprints = set()
    for i in range(len(hashes) - w + 1):
        window = hashes[i : i + w]
        fingerprints.add(min(window))
    return fingerprints

#算分函数
def similarity_score(code_a: str, code_b: str, k: int = 5, w: int = 4) -> float:
    tokens_a = tokenize_c(code_a)
    tokens_b = tokenize_c(code_b)
    fp_a = winnowing_fingerprints(tokens_a, k=k, w=w)
    fp_b = winnowing_fingerprints(tokens_b, k=k, w=w)
    if not fp_a and not fp_b:
        return 0.0
    inter = fp_a.intersection(fp_b)
    union = fp_a.union(fp_b)
    return len(inter) / len(union)#采用与iou类似的算法计算相似度

#证据提取器
def _common_ngrams(tokens_a: List[str], tokens_b: List[str], n: int = 8, top_n: int = 3) -> List[str]:
    if len(tokens_a) < n or len(tokens_b) < n:
        return []
    ngrams_a = {" ".join(tokens_a[i : i + n]) for i in range(len(tokens_a) - n + 1)}
    ngrams_b = {" ".join(tokens_b[i : i + n]) for i in range(len(tokens_b) - n + 1)}
    common = sorted(ngrams_a.intersection(ngrams_b), key=len, reverse=True)
    snippets: List[str] = []
    for gram in common:
        pretty = gram.replace(" ID ", " <id> ").replace(" NUM ", " <num> ")
        if pretty not in snippets:
            snippets.append(pretty)
        if len(snippets) >= top_n:
            break
    return snippets

#计算相似度并返回证据
def similarity_with_evidence(code_a: str, code_b: str, k: int = 5, w: int = 4) -> Dict[str, Any]:
    tokens_a = tokenize_c(code_a)
    tokens_b = tokenize_c(code_b)
    fp_a = winnowing_fingerprints(tokens_a, k=k, w=w)
    fp_b = winnowing_fingerprints(tokens_b, k=k, w=w)
    if not fp_a and not fp_b:
        score = 0.0
        inter: Set[int] = set()
        union: Set[int] = set()
    else:
        inter = fp_a.intersection(fp_b)
        union = fp_a.union(fp_b)
        score = len(inter) / len(union) if union else 0.0

    return {
        "score": score,
        "evidence": {
            "token_count_a": len(tokens_a),
            "token_count_b": len(tokens_b),
            "fingerprints_a": len(fp_a),
            "fingerprints_b": len(fp_b),
            "shared_fingerprints": len(inter),
            "shared_snippets": _common_ngrams(tokens_a, tokens_b),
        },
    }

#将提交的代码两两查重，是批量查重的主函数
def pairwise_similarity(
    submissions: List[Tuple[int, str, Dict[str, Any]]],
    threshold: float = 0.7,
    k: int = 5,
    w: int = 4,
    include_evidence: bool = True,
) -> List[dict]:
    results = []
    for i in range(len(submissions)):
        id_a, code_a, meta_a = submissions[i]
        for j in range(i + 1, len(submissions)):
            id_b, code_b, meta_b = submissions[j]
            if (meta_a.get("student") or "").strip() == (meta_b.get("student") or "").strip():
                continue
            detail = similarity_with_evidence(code_a, code_b, k=k, w=w)
            score = detail["score"]
            if score >= threshold:
                item = {
                    "submission_a": id_a,
                    "submission_b": id_b,
                    "score": round(score, 4),
                    "student_a": meta_a.get("student"),
                    "student_b": meta_b.get("student"), 
                    "problem_id": meta_a.get("problem_id"),
                }
                if include_evidence:
                    item["evidence"] = detail["evidence"]  
                results.append(item)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
