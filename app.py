import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import requests
import urllib.parse
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import json

try:
    import OpenDartReader
    import_error_msg = ""
except Exception as e:
    import traceback
    OpenDartReader = None
    import_error_msg = traceback.format_exc()

# ---------------------------------------------------------
# Page Configuration & UI/UX CSS
# ---------------------------------------------------------
st.set_page_config(page_title="💝 나만의 똑똑한 주식 비서", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    html, body, .stApp {
        font-family: 'Pretendard', sans-serif;
        background-color: #F8FAFC;
        color: #334155;
        word-break: break-word; /* 모바일에서 텍스트 잘림 방지 */
        overflow-wrap: break-word;
    }
    h1, h2, h3 {
        color: #1e293b;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        font-size: clamp(1.3rem, 5vw, 2.2rem) !important; /* 화면 크기에 맞게 자동 조절 */
    }
    
    .stButton>button {
        background: #005EB8;
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-weight: 700;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        width: 100%;
        box-shadow: 0 4px 6px -1px rgba(0, 94, 184, 0.3);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        background: #004a94;
        box-shadow: 0 10px 15px -3px rgba(0, 94, 184, 0.4), 0 4px 6px -2px rgba(0, 94, 184, 0.2);
    }

    [data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #F1F5F9;
        border-radius: 12px;
        border-top: 4px solid #005EB8;
        padding: 1.2rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.02);
    }
    [data-testid="stMetricValue"] > div {
        color: #005EB8 !important;
        font-weight: 800 !important;
        font-size: clamp(1rem, 3.5vw, 1.6rem) !important; /* 수급동향 등 긴 텍스트 잘림 방지 */
        word-break: keep-all;
    }
    [data-testid="stMetricLabel"] > div {
        color: #64748b !important;
        font-size: clamp(0.8rem, 2.5vw, 1rem) !important;
    }
    
    .card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
        border: 1px solid #F1F5F9;
    }
    
    /* 표(테이블) 스타일링 */
    [data-testid="stTable"] table {
        width: 100%;
    }
    [data-testid="stTable"] th {
        background-color: #e6f7e6 !important; /* 연두색 */
        text-align: center !important;
        color: #1e293b !important;
        font-weight: 700 !important;
    }
    [data-testid="stTable"] td {
        text-align: center !important;
    }
    
    /* -------------------------------------------------------------------------- */
    /* UI/UX 레이아웃 교정 (픽셀 매칭 및 줄바꿈 방지)                           */
    /* -------------------------------------------------------------------------- */
    
    /* 1. 절대 줄바꿈 금지 (No-Wrap 강제) - overflow: hidden 추가 */
    .stButton > button, 
    .stButton > button *,
    [data-baseweb="tab"], 
    [data-baseweb="tab"] *, 
    td, th, 
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *, 
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * {
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* 2. 입력창 및 버튼 규격(높이) 완벽 통일 */
    .stTextInput > div > div > input, 
    .stNumberInput > div > div > input, 
    .stSelectbox > div > div > div[data-baseweb="select"],
    .stDateInput > div > div > input,
    .stButton > button {
        height: 42px !important;
        min-height: 42px !important;
        max-height: 42px !important;
        line-height: 42px !important;
        margin: 0 !important;
        box-sizing: border-box !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    /* 3. 대시보드 메트릭 박스(KPI) 동일 높이화 */
    [data-testid="metric-container"] {
        min-height: 130px !important;
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        overflow: hidden !important;
    }
    /* -------------------------------------------------------------------------- */
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Keys & Init
# ---------------------------------------------------------
def init_api_keys():
    dart_key = ""
    gemini_key = ""
    try:
        dart_key = st.secrets.get("DART_API_KEY", "")
        gemini_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass  # st.secrets에서 키를 찾지 못하거나 파일이 없을 때 예외 발생 가능

    try:
        # 만약 st.secrets에서 키를 찾지 못했다면 현재 파일 경로의 secrets.toml을 직접 읽음
        if not dart_key or not gemini_key:
            import os
            import re
            local_secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
            if os.path.exists(local_secrets_path):
                with open(local_secrets_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    dart_match = re.search(r'DART_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                    gemini_match = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                    if dart_match and not dart_key:
                        dart_key = dart_match.group(1)
                    if gemini_match and not gemini_key:
                        gemini_key = gemini_match.group(1)

        if OpenDartReader is None:
            st.error(f"⚠️ 서버 문제: OpenDartReader 모듈을 불러오지 못했습니다.\n\n에러 상세 내용:\n```\n{import_error_msg}\n```\nrequirements.txt를 확인하세요.")
        elif not dart_key:
            st.error("⚠️ 설정 문제: DART_API_KEY 값을 찾을 수 없습니다. (Secrets 오타 확인)")

        dart_reader = OpenDartReader(dart_key) if OpenDartReader and dart_key else None
        return dart_reader, gemini_key
    except Exception as e:
        st.error(f"⚠️ API 초기화 에러: {str(e)}")
        return None, None

dart, GEMINI_API_KEY = init_api_keys()

# ---------------------------------------------------------
# Functions
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_stock_list():
    try:
        # Streamlit Cloud 환경에서 KOSPI 개별 호출 시 종종 연결 에러가 발생하므로 KRX 전체를 호출하여 필터링
        df = fdr.StockListing('KRX')
        # KOSPI, KOSDAQ 종목만 필터링 (필요시 KOSDAQ GLOBAL 등 포함 가능)
        if 'Market' in df.columns:
            df = df[df['Market'].isin(['KOSPI', 'KOSDAQ', 'KOSDAQ GLOBAL'])]
        return df
    except Exception as e:
        try:
            # KRX 호출 실패 시 기존 방식(KOSPI, KOSDAQ 개별 호출)으로 재시도
            df_kospi = fdr.StockListing('KOSPI')
            df_kosdaq = fdr.StockListing('KOSDAQ')
            return pd.concat([df_kospi, df_kosdaq])
        except Exception as e2:
            # 3순위: DART API를 활용하여 종목 목록 가져오기 (KRX 서버 전체 차단 시)
            if dart is not None:
                try:
                    corp_codes = dart.corp_codes
                    df_dart = corp_codes[corp_codes['stock_code'].notna() & (corp_codes['stock_code'] != '')].copy()
                    df_dart.rename(columns={'stock_code': 'Code', 'corp_name': 'Name'}, inplace=True)
                    return df_dart
                except Exception:
                    pass
            st.error(f"⚠️ 종목 데이터를 불러올 수 없습니다. (KRX 에러: {str(e2)}) 잠시 후 다시 시도해주세요.")
            return pd.DataFrame(columns=['Code', 'Name'])

def find_ticker(name_or_ticker, df):
    if name_or_ticker.isdigit() and len(name_or_ticker) == 6:
        match = df[df['Code'] == name_or_ticker]
        if not match.empty: return name_or_ticker, match.iloc[0]['Name']
    
    match = df[df['Name'].str.contains(name_or_ticker, case=False, na=False)]
    if not match.empty:
        exact_match = match[match['Name'] == name_or_ticker]
        if not exact_match.empty:
            return exact_match.iloc[0]['Code'], exact_match.iloc[0]['Name']
        return match.iloc[0]['Code'], match.iloc[0]['Name']
    return None, None

@st.cache_data(ttl=3600)
def get_naver_fundamental(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    try:
        res = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        per_el = soup.select_one('#_per')
        pbr_el = soup.select_one('#_pbr')
        
        per = float(per_el.text.replace(',', '')) if per_el and per_el.text.strip() else -1
        pbr = float(pbr_el.text.replace(',', '')) if pbr_el and pbr_el.text.strip() else -1
        
        roe = -999.0
        table = soup.find('table', class_='tb_type1_ifrs')
        if table:
            for tr in table.find_all('tr'):
                th = tr.find('th')
                if th and 'ROE' in th.text:
                    tds = tr.find_all('td')
                    for td in reversed(tds):
                        val = td.text.strip().replace(',', '')
                        if val and val != '-':
                            try:
                                roe = float(val)
                                break
                            except:
                                pass
                    break

        return per, pbr, roe
    except:
        return -1, -1, -999.0

@st.cache_data(ttl=3600)
def get_investor_trend(ticker):
    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    try:
        res = requests.get(url, headers={'User-agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        trs = soup.select('.type2')[1].select('tr')
        f_sum, i_sum = 0, 0
        count = 0
        for tr in trs:
            if count >= 5: break
            tds = tr.select('td')
            if len(tds) >= 7 and "colspan" not in tds[0].attrs:
                try:
                    inst = int(tds[5].text.strip().replace(',', ''))
                    forg = int(tds[6].text.strip().replace(',', ''))
                    i_sum += inst
                    f_sum += forg
                    count += 1
                except:
                    pass
                    
        trend = []
        trend.append("외인매수" if f_sum > 0 else "외인매도")
        trend.append("기관매수" if i_sum > 0 else "기관매도")
        return "/".join(trend)
    except:
        return "수급확인불가"

@st.cache_data(ttl=3600)
def check_dart_momentum(ticker):
    if not dart: return "DART 연동 실패"
    try:
        end = datetime.today()
        start = end - timedelta(days=90)
        
        df = dart.list(ticker, start=start.strftime('%Y%m%d'), end=end.strftime('%Y%m%d'))
        if df is None or df.empty: return "특이 공시 없음"
        
        pts = set()
        for title in df['report_nm']:
            title_nospace = title.replace(' ', '')
            if '단일판매ㆍ공급계약' in title_nospace or '단일판매·공급계약' in title_nospace:
                pts.add('수주 모멘텀')
            if '매출액또는손익구조30%' in title_nospace:
                pts.add('호실적 모멘텀')
                
        if pts:
            return "🌟 " + ", ".join(pts)
        return "일반공시 위주"
    except:
        return "공시 확인 불가"

@st.cache_data(ttl=3600)
def analyze_news_sentiment(name):
    if not GEMINI_API_KEY: return "AI 분석 꺼짐 (API Key 필요)"
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(name)}&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, timeout=3)
        soup = BeautifulSoup(res.text, 'xml')
        
        titles = [item.title.text for item in soup.find_all('item')[:5]]
        if not titles:
            return "최근 관련 뉴스 없음"
            
        news_text = "\n".join(titles)
        prompt = f"다음은 '{name}' 종목의 최근 뉴스 헤드라인 5개입니다.\n{news_text}\n\n이 뉴스들을 종합하여 긍정/부정 스코어(0~100점, 100점이 가장 긍정적)를 매기고, 10단어 이내로 아주 짧게 핵심 요약평을 작성해줘. 반드시 '스코어: [점수]점 / [요약]' 형태의 한 줄로만 대답해줘."
        
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{"parts":[{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0}
        }
        
        gemini_res = requests.post(gemini_url, headers=headers, json=data, timeout=10)
        if gemini_res.status_code == 200:
            return gemini_res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('\n', ' ')
        elif gemini_res.status_code == 429:
            return "💡 일일 한도 초과"
        else:
            return f"💡 에러 {gemini_res.status_code}"
    except Exception as e:
        return f"💡 네트워크 에러"

def calculate_score(per, roe, trend, momentum, sentiment_text):
    score = 0
    # 1. PER (10점 만점)
    if per <= 0 or per > 30: per_score = 1
    elif per > 25: per_score = 2
    elif per > 20: per_score = 3
    elif per > 15: per_score = 4
    elif per > 12: per_score = 5
    elif per > 10: per_score = 6
    elif per > 8: per_score = 7
    elif per > 6: per_score = 8
    elif per > 4: per_score = 9
    else: per_score = 10
    score += per_score * 1.0 # 10%
    
    # 2. ROE (20점 만점)
    if roe > 20: roe_score = 10
    elif roe > 15: roe_score = 8
    elif roe > 10: roe_score = 6
    elif roe > 5: roe_score = 4
    elif roe > 0: roe_score = 2
    else: roe_score = 1
    score += roe_score * 2.0 # 20%
    
    # 3. 수급 (25점 만점)
    if "외인매수/기관매수" in trend: trend_score = 10
    elif "매수" in trend: trend_score = 6
    else: trend_score = 1
    score += trend_score * 2.5 # 25%
    
    # 4. 공시/모멘텀 (20점 만점)
    if '호실적' in momentum and '수주' in momentum: mom_score = 10
    elif '호실적' in momentum: mom_score = 8
    elif '수주' in momentum: mom_score = 6
    elif '일반공시' in momentum: mom_score = 3
    else: mom_score = 1
    score += mom_score * 2.0 # 20%
    
    # 5. 뉴스 AI 감성 (25점 만점)
    m = re.search(r'(\d+)점', sentiment_text)
    if m:
        sent_val = int(m.group(1))
        raw_sent = (sent_val - 50) / 5.0
        raw_sent = max(-10, min(10, raw_sent))
        sent_score = raw_sent
    else:
        sent_score = 0
    score += sent_score * 2.5 # 25% (음수 포함 가능)
    
    return max(0, min(100, round(score, 1)))

def get_dca_strategy(ticker):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=180) 
    try:
        df_ohlcv = fdr.DataReader(ticker, start_date, end_date)
        if df_ohlcv.empty: return "데이터 부족", "-"
            
        df_ohlcv['MA20'] = df_ohlcv['Close'].rolling(window=20).mean()
        df_ohlcv['MA60'] = df_ohlcv['Close'].rolling(window=60).mean()
        
        current_price = df_ohlcv['Close'].iloc[-1]
        ma20 = df_ohlcv['MA20'].iloc[-1]
        ma60 = df_ohlcv['MA60'].iloc[-1]
        
        if pd.isna(ma20) or pd.isna(ma60):
            return "데이터 부족", "-"
            
        if current_price < ma60:
            return "🔴 적극 매수 구간", f"{int(ma60):,}원 이하 (60일선 지지)"
        elif ma60 <= current_price < ma20:
            return "🟡 1차 분할 매수", f"{int(ma20):,}원 이하 (20일선 접근)"
        else: 
            return "⚪ 관망 대기 (고평가/조정대기)", "-"
    except:
        return "데이터 확인 불가", "-"

# ---------------------------------------------------------
# Main UI
# ---------------------------------------------------------
st.title("📈 인텔리전트 주식 분석 리포트")
st.write("원하시는 주식 종목명이나 코드를 입력하시면, 펀더멘털 및 AI 기반 심층 분석 리포트를 제공합니다.")

if not GEMINI_API_KEY and dart is None:
    st.info("💡 일부 기능(뉴스 AI 요약, DART 공시 확인)은 API Key를 설정하면 활성화됩니다.")
elif not GEMINI_API_KEY:
    st.info("💡 구글 Gemini API Key를 설정하면 뉴스 AI 요약 기능이 활성화됩니다.")
elif dart is None:
    st.info("💡 DART API Key를 설정하면 공시 모멘텀 확인 기능이 활성화됩니다.")

df_stock = get_stock_list()

def load_daily_scores():
    import os
    score_path = os.path.join(os.path.dirname(__file__), "daily_top_scores.json")
    if os.path.exists(score_path):
        try:
            with open(score_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

daily_data = load_daily_scores()
if daily_data:
    st.markdown(f"### 🏆 코스피/코스닥 시장 동향 ({daily_data.get('date', '')} 기준)")
    col1, col2 = st.columns(2, vertical_alignment="top")
    with col1:
        st.metric("📊 코스피 평균 펀더멘털 점수", f"{daily_data.get('kospi_avg', 0)}점")
    with col2:
        st.metric("📊 코스닥 평균 펀더멘털 점수", f"{daily_data.get('kosdaq_avg', 0)}점")
        
    st.markdown("#### 🔥 오늘의 AI 종합 매력도 Top 10")
    col1, col2 = st.columns(2, vertical_alignment="top")
    with col1:
        st.markdown("##### 📈 KOSPI Top 10")
        if daily_data.get('kospi_top_10'):
            df_kospi = pd.DataFrame(daily_data['kospi_top_10'])
            df_kospi.index = df_kospi.index + 1
            df_kospi_disp = df_kospi[['Name', 'Code', 'Score']].rename(columns={'Name': '종목명', 'Code': '코드', 'Score': '점수'})
            st.table(df_kospi_disp)
    with col2:
        st.markdown("##### 📉 KOSDAQ Top 10")
        if daily_data.get('kosdaq_top_10'):
            df_kosdaq = pd.DataFrame(daily_data['kosdaq_top_10'])
            df_kosdaq.index = df_kosdaq.index + 1
            df_kosdaq_disp = df_kosdaq[['Name', 'Code', 'Score']].rename(columns={'Name': '종목명', 'Code': '코드', 'Score': '점수'})
            st.table(df_kosdaq_disp)
    st.divider()

with st.form("search_form"):
    user_input = st.text_input("🔍 종목명 또는 종목코드 입력", placeholder="예: 삼성전자, 005930")
    submitted = st.form_submit_button("분석 시작!")

if submitted and user_input:
    with st.spinner("해당 종목 데이터를 수집하고 AI 분석을 진행 중입니다. 잠시만 기다려주세요..."):
        ticker, name = find_ticker(user_input, df_stock)
        
        if not ticker:
            st.error("해당 종목을 찾을 수 없습니다. 올바른 종목명이나 코드를 입력해 주세요.")
        else:
            per, pbr, roe = get_naver_fundamental(ticker)
            trend = get_investor_trend(ticker)
            momentum = check_dart_momentum(ticker)
            sentiment = analyze_news_sentiment(name)
            score = calculate_score(per, roe, trend, momentum, sentiment)
            strategy, target_price = get_dca_strategy(ticker)
            
            st.success(f"**{name} ({ticker})** 분석 완료! 🎉")
            
            st.markdown(f"<div class='card'><h3 style='text-align:center; word-break: keep-all;'>✨ AI 종합 매력도: {score}점 / 100점 ✨</h3></div>", unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3, vertical_alignment="top")
            col1.metric("📊 PER (주가수익비율)", f"{per:.1f}배" if per > 0 else "N/A")
            col2.metric("📈 ROE (자기자본이익률)", f"{roe:.1f}%" if roe != -999.0 else "N/A")
            col3.metric("🤝 수급 동향 (5일)", trend)
            
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("### 📰 핵심 요약 리포트")
            st.write(f"**📣 공시 모멘텀:** {momentum}")
            st.write(f"**🤖 뉴스 AI 감성:** {sentiment}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("### 🎯 기술적 매매 전략")
            st.write(f"**현재 판정:** {strategy}")
            if target_price != "-":
                st.write(f"**추천 매수 타점:** {target_price}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if score >= 80:
                st.info("💡 **AI 종합 코멘트:** 현재 펀더멘털 및 모멘텀이 매우 우수한 종목으로 평가됩니다. 긍정적인 매수 검토가 가능합니다.")
            elif score >= 60:
                st.info("💡 **AI 종합 코멘트:** 전반적으로 양호한 지표를 보이고 있습니다. 분할 매수를 통한 보수적 접근을 권장합니다.")
            else:
                st.warning("💡 **AI 종합 코멘트:** 현재 여러 지표에서 리스크가 감지됩니다. 신규 진입보다는 관망하는 것을 권장합니다.")
