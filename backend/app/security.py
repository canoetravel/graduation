import re
from typing import Tuple, Optional


def validate_code_security(
    code: str,
    assignment_type: str,
    syscall_allowlist: Optional[list] = None,
    syscall_denylist: Optional[list] = None,
) -> Tuple[bool, str]:
    """根据作业类型验证代码安全性。"""
    if not code or len(code.strip()) < 10:
        return False, "代码过短或不完整"

    code_lower = code.lower()

    if "int main" not in code_lower and "void main" not in code_lower:
        return False, "未找到 main 函数"

    compact = code_lower.replace(" ", "").replace("\n", "").replace("\t", "")
    if "while(1)" in compact:
        return False, "检测到无限循环"

    base_dangerous = [
        (r"system\s*\(", "禁止使用 system() 函数"),
        (r"popen\s*\(", "禁止使用 popen() 函数"),
        (r"#include\s*<sys/socket.h>", "禁止网络编程"),
        (r"socket\s*\(|connect\s*\(|bind\s*\(", "禁止网络 socket 操作"),
        (r"chmod\s*\(|chown\s*\(", "禁止修改文件权限"),
        (r"unlink\s*\(|remove\s*\(", "禁止删除文件"),
    ]

    allowed_by_type = {
        "process": [
            r"fork\s*\(",
            r"exec[lv]?p?e?\s*\(",
            r"wait\s*\(|waitpid\s*\(",
            r"kill\s*\(",
            r"#include\s*<unistd.h>",
            r"#include\s*<sys/wait.h>",
        ],
        "normal": [],
        "file": [],
        "memory": [],
    }

    dangerous_patterns = base_dangerous.copy()
    if assignment_type in allowed_by_type:
        allowed_patterns = set(allowed_by_type[assignment_type])
        dangerous_patterns = [
            (pattern, msg)
            for pattern, msg in dangerous_patterns
            if pattern not in allowed_patterns
        ]

    allowlist = set(syscall_allowlist or [])
    if allowlist:
        dangerous_patterns = [
            (pattern, msg)
            for pattern, msg in dangerous_patterns
            if pattern not in allowlist
        ]

    denylist = list(syscall_denylist or [])
    for pattern in denylist:
        if re.search(pattern, code, re.IGNORECASE):
            return False, f"安全检查失败: 禁止调用匹配 {pattern}"

    for pattern, error_msg in dangerous_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            return False, f"安全检查失败: {error_msg}"

    return True, "代码安全检查通过"
