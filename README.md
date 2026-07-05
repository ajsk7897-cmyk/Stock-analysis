# 💝 나만의 똑똑한 주식 비서 (Smart Stock Analyzer)

단일 주식 종목의 펀더멘털, 수급, 공시 모멘텀, 뉴스 AI 감성 분석 결과를 통합하여 매력도를 100점 만점으로 평가해주는 스마트 비서 애플리케이션입니다. 

## 기능 (Features)
- 📊 **펀더멘털 분석**: 네이버 금융(PER, PBR, ROE) 데이터 스크래핑
- 🤝 **수급 동향**: 최근 5일간 외국인/기관 매매 동향 분석
- 📣 **DART 모멘텀**: 수주 계약, 호실적 등 주요 공시 실시간 확인
- 🤖 **뉴스 AI 감성 분석**: 구글 뉴스 RSS와 Gemini API를 활용한 뉴스 긍정/부정(0~100점) 점수화
- 🎯 **매매 전략**: 이동평균선(20일, 60일) 기반 분할 매수 및 관망 타점 제시

## 설치 및 실행 방법 (Local Run)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## API 키 설정
Streamlit Cloud 배포 시 **Settings > Secrets**에 다음 키를 추가해야 합니다.
```toml
DART_API_KEY = "당신의_DART_API_키"
GEMINI_API_KEY = "당신의_GEMINI_API_키"
```
