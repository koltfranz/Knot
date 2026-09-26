# 结绳 Knot 本地服务（家庭共享）
# 账本目录 MUST 挂载为卷：docker run -v D:\我的账本:/账本 ...
FROM python:3.13-slim

ENV PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

EXPOSE 5000
CMD ["python", "-m", "knot", "服务", "--账本", "/账本/main.knot", "--host", "0.0.0.0", "--端口", "5000"]
