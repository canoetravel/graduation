from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from typing import List, Dict, Any


class CodeRequest(BaseModel):
    code: str
    language: Optional[str] = "c"
    timeout: int = Field(default=3, ge=1, le=10, description="超时时间(秒)")
    assignment_type: Optional[str] = Field(
        default="file", description="作业类型: file/process"
    )


class ProblemTestCase(BaseModel):
    type: str = Field(description="测试类型: contains/exact")
    value: str = Field(description="期望输出片段或完整输出")
    score: int = Field(ge=0, description="该测试点分值")


class ProblemCreate(BaseModel):
    title: str
    description: str
    problem_type: str = Field(description="题目类型: process/file/memory")
    points: int = Field(ge=0)
    test_cases: List[ProblemTestCase] = Field(default_factory=list)
    time_limit: int = Field(default=3, ge=1, le=30, description="超时时间(秒)")
    memory_limit: Optional[int] = Field(
        default=None, ge=32, le=2048, description="内存限制(MB)"
    )
    pids_limit: Optional[int] = Field(
        default=None, ge=1, le=512, description="进程数上限"
    )
    file_size_limit: Optional[int] = Field(
        default=None, ge=1, le=1024, description="文件大小上限(MB)"
    )
    syscall_allowlist: List[str] = Field(
        default_factory=list, description="允许的系统调用/函数模式"
    )
    syscall_denylist: List[str] = Field(
        default_factory=list, description="禁止的系统调用/函数模式"
    )


class AssignmentCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    teacher: str
    deadline_at: Optional[datetime] = None
    problems: List[ProblemCreate]


class SubmissionItem(BaseModel):
    problem_id: int
    code: str
    timeout: int = Field(default=3, ge=1, le=10)


class AssignmentSubmitRequest(BaseModel):
    student: str
    commit_message: Optional[str] = None
    items: List[SubmissionItem]


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    role: str


class UserLoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "auto"
