import docker
import requests
import json

# 测试Docker
print("1. 测试Docker连接...")
try:
    client = docker.from_env()
    print(f"✅ Docker版本: {client.version()['Version']}")
except Exception as e:
    print(f"❌ Docker错误: {e}")

# 测试后端API
print("\n2. 测试后端API...")
try:
    resp = requests.get("http://localhost:8000/")
    print(f"✅ 后端状态: {resp.status_code}")
    print(f"   响应: {resp.text}")
except Exception as e:
    print(f"❌ 后端错误: {e}")

# 测试评测接口
print("\n3. 测试评测功能...")
try:
    code = '#include <stdio.h>\nint main(){ printf("Hello"); }'
    resp = requests.post("http://localhost:8000/judge", 
                        json={"code": code, "timeout": 3})
    print(f"✅ 评测状态: {resp.status_code}")
    print(f"   结果: {resp.text}")
except Exception as e:
    print(f"❌ 评测错误: {e}")

# 测试前端
print("\n4. 测试前端访问...")
try:
    resp = requests.get("http://localhost:8080/")
    print(f"✅ 前端状态: {resp.status_code}")
    if len(resp.text) < 100:
        print(f"   响应: {resp.text[:100]}...")
    else:
        print("   前端页面正常")
except Exception as e:
    print(f"❌ 前端错误: {e}")