import os
import re
import json
import urllib.parse
from datetime import datetime, timedelta
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
import pandas as pd

try:
    from OpenDartReader import OpenDartReader
except ImportError:
    OpenDartReader = None

# --- API Keys 초기화 ---
def get_api_keys():
    dart_key, gemini_key = "", ""
    try:
        # Streamlit secrets에서 직접 읽기 시도
        local_secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(local_secrets_path):
            with open(local_secrets_path, "r", encoding="utf-8") as f:
                content = f.read()
                dart_match = re.search(r'DART_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                gemini_match = re.search(r'GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']', content)
                if dart_match: dart_key = dart_match.group(1)
                if gemini_match: gemini_key = gemini_match.group(1)
    except Exception as e:
        print(f"API Key 로드 실패: {e}")
    return dart_key, gemini_key

DART_KEY, GEMINI_API_KEY = get_api_keys()
dart = OpenDartReader(DART_KEY) if OpenDartReader and DART_KEY else None

# --- 기본 수집 함수 ---
def get_stock_list():
    df = fdr.StockListing('KRX')
    if 'Market' in df.columns:
        df = df[df['Market'].isin(['KOSPI', 'KOSDAQ', 'KOSDAQ GLOBAL'])]
    return df

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
                    i_sum += int(tds[5].text.strip().replace(',', ''))
                    f_sum += int(tds[6].text.strip().replace(',', ''))
                    count += 1
                except: pass
        trend = []
        trend.append("외인매수" if f_sum > 0 else "외인매도")
        trend.append("기관매수" if i_sum > 0 else "기관매도")
        return "/".join(trend)
    except:
        return "수급확인불가"

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
        if pts: return "🌟 " + ", ".join(pts)
        return "일반공시 위주"
    except:
        return "공시 확인 불가"

def analyze_news_sentiment(name):
    if not GEMINI_API_KEY: return "AI 분석 꺼짐"
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(name)}&hl=ko&gl=KR&ceid=KR:ko"
        res = requests.get(url, timeout=3)
        soup = BeautifulSoup(res.text, 'xml')
        titles = [item.title.text for item in soup.find_all('item')[:5]]
        if not titles: return "최근 관련 뉴스 없음"
        news_text = "\n".join(titles)
        prompt = f"다음은 '{name}' 종목의 최근 뉴스 헤드라인 5개입니다.\n{news_text}\n\n이 뉴스들을 종합하여 긍정/부정 스코어(0~100점, 100점이 가장 긍정적)를 매기고, 10단어 이내로 아주 짧게 핵심 요약평을 작성해줘. 반드시 '스코어: [점수]점 / [요약]' 형태의 한 줄로만 대답해줘."
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        data = {"contents": [{"parts":[{"text": prompt}]}]}
        gemini_res = requests.post(gemini_url, headers=headers, json=data, timeout=10)
        if gemini_res.status_code == 200:
            return gemini_res.json()['candidates'][0]['content']['parts'][0]['text'].strip().replace('\n', ' ')
        return f"💡 에러 {gemini_res.status_code}"
    except:
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
    score += per_score * 1.0
    
    # 2. ROE (20점 만점)
    if roe > 20: roe_score = 10
    elif roe > 15: roe_score = 8
    elif roe > 10: roe_score = 6
    elif roe > 5: roe_score = 4
    elif roe > 0: roe_score = 2
    else: roe_score = 1
    score += roe_score * 2.0
    
    # 3. 수급 (25점 만점)
    if "외인매수/기관매수" in trend: trend_score = 10
    elif "매수" in trend: trend_score = 6
    else: trend_score = 1
    score += trend_score * 2.5
    
    # 4. 공시/모멘텀 (20점 만점)
    if '호실적' in momentum and '수주' in momentum: mom_score = 10
    elif '호실적' in momentum: mom_score = 8
    elif '수주' in momentum: mom_score = 6
    elif '일반공시' in momentum: mom_score = 3
    else: mom_score = 1
    score += mom_score * 2.0
    
    # 5. 뉴스 AI 감성 (25점 만점)
    m = re.search(r'(\d+)점', sentiment_text)
    if m:
        sent_val = int(m.group(1))
        raw_sent = (sent_val - 50) / 5.0
        raw_sent = max(-10, min(10, raw_sent))
        sent_score = raw_sent
    else:
        sent_score = 0
    score += sent_score * 2.5
    
    return max(0, min(100, round(score, 1)))

# --- 메인 로직 ---
def fetch_basic_info(row):
    ticker = row['Code']
    per, pbr, roe = get_naver_fundamental(ticker)
    trend = get_investor_trend(ticker)
    
    # 임시 점수 계산 (PER + ROE + 수급) - 최대 55점 만점을 100점으로 환산
    temp_score = 0
    # PER
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
    temp_score += per_score * 1.0
    
    # ROE
    if roe > 20: roe_score = 10
    elif roe > 15: roe_score = 8
    elif roe > 10: roe_score = 6
    elif roe > 5: roe_score = 4
    elif roe > 0: roe_score = 2
    else: roe_score = 1
    temp_score += roe_score * 2.0
    
    # 수급
    if "외인매수/기관매수" in trend: trend_score = 10
    elif "매수" in trend: trend_score = 6
    else: trend_score = 1
    temp_score += trend_score * 2.5
    
    scaled_temp_score = round(temp_score / 55.0 * 100.0, 1)
    
    return {
        'Code': ticker,
        'Name': row['Name'],
        'Market': row['Market'],
        'PER': per,
        'ROE': roe,
        'Trend': trend,
        'BaseScore': scaled_temp_score
    }

def main():
    print("1. KRX 주식 목록 가져오기...")
    df = get_stock_list()
    
    kospi_avg = 0.0
    kosdaq_avg = 0.0
    
    print("2. 펀더멘털 및 수급 데이터 수집 시작 (Thread Pool)")
    results = []
    # 최대 쓰레드 30개로 제어
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(fetch_basic_info, row): row for _, row in df.iterrows()}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                res = future.result()
                results.append(res)
                if i > 0 and i % 100 == 0:
                    print(f"진행상황: {i} / {len(df)}")
            except Exception as e:
                pass
                
    df_results = pd.DataFrame(results)
    
    if not df_results.empty:
        kospi_avg = round(df_results[df_results['Market'] == 'KOSPI']['BaseScore'].mean(), 1)
        kosdaq_avg = round(df_results[df_results['Market'].str.contains('KOSDAQ')]['BaseScore'].mean(), 1)
    
    print(f"코스피 평균: {kospi_avg}, 코스닥 평균: {kosdaq_avg}")
    
    print("3. 상위 50개 종목 추출 및 정밀 AI/DART 분석 진행")
    top_50 = df_results.sort_values(by='BaseScore', ascending=False).head(50)
    
    final_top_list = []
    for _, row in top_50.iterrows():
        ticker = row['Code']
        name = row['Name']
        momentum = check_dart_momentum(ticker)
        sentiment = analyze_news_sentiment(name)
        
        final_score = calculate_score(row['PER'], row['ROE'], row['Trend'], momentum, sentiment)
        
        final_top_list.append({
            'Code': ticker,
            'Name': name,
            'Market': row['Market'],
            'Score': final_score,
            'Sentiment': sentiment,
            'Momentum': momentum
        })
        print(f"[{name}] 분석 완료 - {final_score}점")
        
    df_final = pd.DataFrame(final_top_list)
    df_final = df_final.sort_values(by='Score', ascending=False)
    
    kospi_top_10 = df_final[df_final['Market'] == 'KOSPI'].head(10).to_dict('records')
    kosdaq_top_10 = df_final[df_final['Market'].str.contains('KOSDAQ')].head(10).to_dict('records')
    
    output_data = {
        'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'kospi_avg': kospi_avg,
        'kosdaq_avg': kosdaq_avg,
        'kospi_top_10': kospi_top_10,
        'kosdaq_top_10': kosdaq_top_10
    }
    
    save_path = os.path.join(os.path.dirname(__file__), 'daily_top_scores.json')
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"완료! 결과가 {save_path} 에 저장되었습니다.")

if __name__ == "__main__":
    main()
