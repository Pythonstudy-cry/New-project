FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    fontconfig \
    fonts-dejavu \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-nanum \
    fonts-nanum-coding \
    fonts-nanum-extra \
    && rm -rf /var/lib/apt/lists/*

# 폰트 캐시 업데이트
RUN fc-cache -fv

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 포트 노출
EXPOSE 5000

# 환경변수 설정
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg

# 애플리케이션 실행 (더 안정적인 설정)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "300", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "100", "--log-level", "info", "app:app"] 