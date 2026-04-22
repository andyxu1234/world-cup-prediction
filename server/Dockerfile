FROM python:3.12-slim

WORKDIR /app

# 使用阿里云镜像源加速 apt
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 系统依赖 + 编译工具（asyncmy 的 C 扩展需要 gcc + 头文件）
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-client \
    gcc \
    libc6-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（利用缓存层，requirements.txt 不变则不重新安装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码
COPY . .

# 入口脚本：等待 MySQL 就绪 → 执行迁移 → 导入种子数据 → 启动应用
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
