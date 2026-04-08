# 最简单的Dockerfile
FROM python:3.9-slim
WORKDIR /app

# 1. 先复制依赖文件
COPY requirements.txt .

# 2. 安装依赖
RUN pip install -r requirements.txt

# 3. 再复制代码
COPY . .

# 4. 最后设置启动命令
CMD ["python", "main.py"]