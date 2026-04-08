# OS 作业自动评阅平台（阶段一）

## 1. 启动

```bash
docker-compose up -d --build
```

- 前端地址：`http://localhost:18080`
- 后端地址：`http://localhost:19000`

## 2. 页面

- `login.html`：登录/注册
- `teacher.html`：教师发布作业、查看作业、抄袭检测、版本轨迹查看与导出
- `student.html`：学生加载作业、提交代码、查看版本历史与最终分

## 3. 支持作业类型

- `process`：进程管理
- `file`：文件系统
- `memory`：内存管理

## 4. 阶段一能力（版本管理）

- 作业支持 `deadline_at`（可选截止时间）
- 学生可在截止前多次提交，系统为每次提交生成版本
- 每个版本记录：
  - `version_no`
  - `commit_hash`（当前自动生成，后续可替换为真实 Git hash）
  - `commit_message`（学生可填写）
  - 评测得分与状态摘要
- 支持最终分策略：
  - `last`：最后一次版本
  - `best`：最高分版本

## 5. 主要后端接口

### 作业与提交

- `POST /api/assignments`：发布作业（支持 `deadline_at`）
- `GET /api/assignments`：作业列表
- `GET /api/assignments/{id}`：作业详情
- `POST /api/assignments/{id}/submit`：提交作业（生成新版本）
- `GET /api/assignments/{id}/submissions?student=...`：提交历史
- `GET /api/submissions/{id}`：提交详情与报告

### 版本管理（阶段一）

- `GET /api/assignments/{id}/versions?student=...`：学生版本历史
- `GET /api/versions/{version_id}`：版本详情
- `GET /api/assignments/{id}/final-score?student=...&policy=last|best`：最终分
- `GET /api/assignments/{id}/version-students`：教师查看该作业有版本提交的学生
- `GET /api/assignments/{id}/versions/export?student=...`：导出该学生版本轨迹 CSV

### 抄袭检测

- `GET /api/assignments/{id}/plagiarism?threshold=0.7`：抄袭检测
- `GET /api/assignments/{id}/plagiarism/export?threshold=0.7&format=csv|txt`：导出抄袭结果

## 6. 快速排错

查看后端日志：

```bash
docker-compose logs --tail=200 backend
```

查看服务状态：

```bash
docker-compose ps
```
