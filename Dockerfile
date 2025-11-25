FROM python:3.11-slim
WORKDIR /app

# 파이썬 실행 환경 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir gunicorn

# 애플리케이션 복사
COPY . .

# 앱 포트 (기본값은 2121)
# 실제 바인드 포트는 런타임 환경변수 PORT로 제어합니다.
EXPOSE 2121

# 프로덕션용 WSGI 서버로 실행
# PORT 환경변수가 설정되어 있으면 그 값을 사용하고, 없으면 2121을 기본으로 사용합니다.
# 타임아웃을 3600초(1시간)로 설정하여 AI 분석 등 긴 작업이 끊기지 않도록 합니다.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-2121} app:app --workers 4 --timeout 3600"]


