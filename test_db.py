import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# 1. 加载 .env 文件
# 默认会查找同目录下的 .env 文件
load_dotenv()  # 默认加载 .env
# 或指定文件
# load_dotenv(".env.example")

# 2. 读取环境变量
config = {
    'host': os.getenv('MYSQL_SERVER', 'localhost'),  # 第二个参数是默认值
    'port': 3306,  # 注意：POSTGRES 默认 5432，MySQL 默认 3306
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DB', 'cms')
}

print("从 .env 文件读取配置:")
for key, value in config.items():
    if key != 'password':  # 不打印密码
        print(f"  {key}: {value}")

# 3. 连接数据库
try:
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    cursor.execute("SELECT * from city")
    result = cursor.fetchone()
    result = cursor.fetchall()  # 读取所有结果
    for row in result:
        print(row)
    print(f"\n✅ 连接成功！")
    
    cursor.close()
    connection.close()
    
except Error as e:
    print(f"❌ 连接失败: {e}")