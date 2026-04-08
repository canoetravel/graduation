from typing import Any, Dict, Optional

import docker


client = docker.from_env()


def _run_in_container(
    source_name: str,
    code: str,
    timeout: int,
    pids_limit: Optional[int] = None,
    mem_limit: Optional[str] = "256m",
    file_size_limit_kb: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        code_escaped = code.replace("'", "'\"'\"'")
        limit_cmd = ""
        if file_size_limit_kb:
            limit_cmd = f"ulimit -f {int(file_size_limit_kb)}"

        docker_command = f"""
        cd /tmp
        {limit_cmd}
        echo '{code_escaped}' > {source_name}
        gcc -o main {source_name} 2> compile.log
        if [ $? -eq 0 ]; then
            timeout {timeout} ./main
        else
            echo "COMPILE_ERROR:"
            cat compile.log
        fi
        """

        container = client.containers.run(
            "gcc:latest",
            ["bash", "-c", docker_command],
            mem_limit=mem_limit,
            pids_limit=pids_limit,
            remove=True,
            stdout=True,
            stderr=True,
        )

        output = container.decode("utf-8", errors="ignore").strip()
        return {"success": True, "output": output, "exit_code": 0}
    except docker.errors.ContainerError as exc:
        error_msg = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else str(exc)
        if "timeout" in str(exc).lower() or exc.exit_status == 124:
            return {
                "success": False,
                "message": f"运行超时(>{timeout}秒)",
                "output": error_msg,
            }
        if "error:" in error_msg or "COMPILE_ERROR" in error_msg:
            return {
                "success": False,
                "message": f"编译错误: {error_msg[:200]}",
                "output": error_msg,
            }
        return {
            "success": False,
            "message": f"运行时错误: {error_msg[:200]}",
            "output": error_msg,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"系统错误: {str(exc)[:200]}",
            "output": "",
        }


def run_normal_code(
    code: str,
    timeout: int,
    mem_limit: Optional[str] = "256m",
    pids_limit: Optional[int] = None,
    file_size_limit_kb: Optional[int] = None,
) -> Dict[str, Any]:
    return _run_in_container(
        "main.c",
        code,
        timeout,
        pids_limit=pids_limit,
        mem_limit=mem_limit,
        file_size_limit_kb=file_size_limit_kb,
    )


def run_process_code(
    code: str,
    timeout: int,
    mem_limit: Optional[str] = "256m",
    pids_limit: Optional[int] = 20,
    file_size_limit_kb: Optional[int] = None,
) -> Dict[str, Any]:
    return _run_in_container(
        "process.c",
        code,
        timeout,
        pids_limit=pids_limit,
        mem_limit=mem_limit,
        file_size_limit_kb=file_size_limit_kb,
    )
