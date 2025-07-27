# 재무제표 시각화 웹 애플리케이션

Open DART API를 활용한 한국 기업 재무제표 시각화 및 AI 분석 웹 애플리케이션입니다.

## 주요 기능

- 🔍 **회사 검색**: 회사명으로 기업 검색 및 코드 조회
- 📊 **재무제표 시각화**: 
  - 재무상태표 (Balance Sheet)
  - 손익계산서 (Income Statement)
  - 자산=부채+자본 관계 시각화
  - 주요 재무비율 (5각형 레이더 차트)
- 🤖 **AI 분석**: Gemini API를 활용한 재무 데이터 분석
- 📈 **직관적인 시각화**: 색상 구분과 박스 구조로 이해하기 쉬운 시각화

## 기술 스택

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, JavaScript, Bootstrap
- **Data**: Open DART API, SQLite
- **AI**: Google Gemini API
- **Visualization**: Matplotlib, Seaborn
- **Deployment**: Render

## 로컬 실행 방법

1. **환경 설정**
   ```bash
   pip install -r requirements.txt
   ```

2. **환경변수 설정**
   `.env` 파일을 생성하고 다음 내용을 추가:
   ```
   OPEN_DART_API_KEY=your_dart_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. **데이터베이스 생성**
   ```bash
   python create_db.py
   ```

4. **애플리케이션 실행**
   ```bash
   python app.py
   ```

5. **브라우저에서 접속**
   ```
   http://127.0.0.1:5000
   ```

## 배포 방법 (Render)

1. **GitHub에 코드 업로드**
   - 이 프로젝트를 GitHub 저장소에 업로드

2. **Render에서 새 서비스 생성**
   - Render 대시보드에서 "New Web Service" 선택
   - GitHub 저장소 연결

3. **환경변수 설정**
   Render 대시보드에서 다음 환경변수 설정:
   - `OPEN_DART_API_KEY`: Open DART API 키
   - `GEMINI_API_KEY`: Google Gemini API 키

4. **배포 설정**
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

5. **배포 완료**
   - Render에서 제공하는 URL로 접속 가능

## API 키 발급 방법

### Open DART API
1. [Open DART](https://opendart.fss.or.kr/) 사이트 접속
2. 회원가입 및 로그인
3. API 키 발급 신청
4. 승인 후 API 키 확인

### Google Gemini API
1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. Google 계정으로 로그인
3. API 키 생성

## 파일 구조

```
├── app.py                 # 메인 Flask 애플리케이션
├── create_db.py           # 데이터베이스 생성 스크립트
├── finance_analysis.py    # AI 분석 모듈
├── download_corp_codes.py # 회사 코드 다운로드 스크립트
├── requirements.txt       # Python 패키지 의존성
├── Procfile              # 배포 설정 (Render)
├── runtime.txt           # Python 버전 명시
├── .env                  # 환경변수 (로컬용)
├── .gitignore           # Git 제외 파일 목록
├── templates/
│   └── index.html       # 웹 페이지 템플릿
└── corp_codes.db        # 회사 코드 데이터베이스
```

## 사용 방법

1. **회사 검색**: 회사명을 입력하여 기업 검색
2. **재무 데이터 선택**: 사업연도와 보고서 종류 선택
3. **시각화**: 재무제표 시각화 확인
4. **AI 분석**: AI 분석 버튼을 클릭하여 재무 상태 분석

## 주의사항

- Open DART API는 일일 요청 제한이 있습니다
- Gemini API는 월별 사용량 제한이 있습니다
- 배포 시 환경변수 설정을 반드시 확인하세요

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 