import os
import json
import google.generativeai as genai
import pandas as pd
from dotenv import load_dotenv
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 파일에서 환경변수 로드
load_dotenv()

# Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise Exception("Gemini API 키가 .env에 없습니다. 환경변수를 확인하세요.")

genai.configure(api_key=GEMINI_API_KEY)

# 모델 설정 (더 가벼운 모델 사용)
try:
    model = genai.GenerativeModel('gemini-1.5-flash')  # 더 빠르고 할당량이 적은 모델
except:
    model = genai.GenerativeModel('gemini-1.5-pro')  # fallback

def extract_financial_highlights(financial_data):
    """
    재무제표 데이터에서 주요 정보를 추출합니다.
    
    Args:
        financial_data: DART API로부터 받은 재무제표 데이터
        
    Returns:
        분석에 필요한 주요 재무 정보
    """
    if not financial_data or 'list' not in financial_data:
        return None
    
    # 데이터프레임 생성
    df = pd.DataFrame(financial_data['list'])
    
    # 연결 재무제표만 필터링
    cfs_df = df[df['fs_div'] == 'CFS']
    if cfs_df.empty:
        cfs_df = df[df['fs_div'] == 'OFS']
    
    # 필요한 계정과목 선택
    accounts = ['자산총계', '부채총계', '자본총계', '매출액', '영업이익', '당기순이익']
    filtered_data = cfs_df[cfs_df['account_nm'].isin(accounts)].copy()
    
    if filtered_data.empty:
        return None
    
    # 결과 저장할 딕셔너리
    highlights = {
        '회사정보': {
            '회사명': cfs_df['corp_name'].iloc[0] if 'corp_name' in cfs_df.columns else '정보 없음',
            '종목코드': cfs_df['stock_code'].iloc[0] if 'stock_code' in cfs_df.columns else '정보 없음',
            '보고서': cfs_df['reprt_code'].iloc[0] if 'reprt_code' in cfs_df.columns else '정보 없음',
            '연도': cfs_df['bsns_year'].iloc[0] if 'bsns_year' in cfs_df.columns else '정보 없음',
        },
        '재무상태표': {},
        '손익계산서': {},
        '재무비율': {}
    }
    
    # 재무상태표 데이터 추출
    bs_accounts = ['자산총계', '부채총계', '자본총계']
    bs_data = filtered_data[filtered_data['account_nm'].isin(bs_accounts)]
    
    # 손익계산서 데이터 추출
    is_accounts = ['매출액', '영업이익', '당기순이익']
    is_data = filtered_data[filtered_data['account_nm'].isin(is_accounts)]
    
    # 문자열 금액을 숫자로 변환하는 함수
    def parse_amount(amount_str):
        if pd.isna(amount_str) or amount_str == '':
            return 0
        return int(amount_str.replace(',', ''))
    
    # 재무상태표 데이터 저장
    for _, row in bs_data.iterrows():
        account = row['account_nm']
        highlights['재무상태표'][account] = {
            '당기': parse_amount(row['thstrm_amount']) if 'thstrm_amount' in row else 0,
            '전기': parse_amount(row['frmtrm_amount']) if 'frmtrm_amount' in row else 0,
            '전전기': parse_amount(row['bfefrmtrm_amount']) if 'bfefrmtrm_amount' in row else 0
        }
    
    # 손익계산서 데이터 저장
    for _, row in is_data.iterrows():
        account = row['account_nm']
        highlights['손익계산서'][account] = {
            '당기': parse_amount(row['thstrm_amount']) if 'thstrm_amount' in row else 0,
            '전기': parse_amount(row['frmtrm_amount']) if 'frmtrm_amount' in row else 0,
            '전전기': parse_amount(row['bfefrmtrm_amount']) if 'bfefrmtrm_amount' in row else 0
        }
    
    # 재무비율 계산
    try:
        if '자산총계' in highlights['재무상태표'] and '부채총계' in highlights['재무상태표'] and '자본총계' in highlights['재무상태표']:
            assets = highlights['재무상태표']['자산총계']['당기']
            liabilities = highlights['재무상태표']['부채총계']['당기']
            equity = highlights['재무상태표']['자본총계']['당기']
            
            if equity > 0:
                highlights['재무비율']['부채비율'] = round((liabilities / equity) * 100, 2)
            else:
                highlights['재무비율']['부채비율'] = None
                
            if assets > 0:
                highlights['재무비율']['부채비율(부채/자산)'] = round((liabilities / assets) * 100, 2)
            else:
                highlights['재무비율']['부채비율(부채/자산)'] = None
        
        if '당기순이익' in highlights['손익계산서'] and '자본총계' in highlights['재무상태표'] and '자산총계' in highlights['재무상태표']:
            net_income = highlights['손익계산서']['당기순이익']['당기']
            equity = highlights['재무상태표']['자본총계']['당기']
            assets = highlights['재무상태표']['자산총계']['당기']
            
            if equity > 0:
                highlights['재무비율']['ROE(자기자본이익률)'] = round((net_income / equity) * 100, 2)
            else:
                highlights['재무비율']['ROE(자기자본이익률)'] = None
                
            if assets > 0:
                highlights['재무비율']['ROA(총자산이익률)'] = round((net_income / assets) * 100, 2)
            else:
                highlights['재무비율']['ROA(총자산이익률)'] = None
        
        if '영업이익' in highlights['손익계산서'] and '매출액' in highlights['손익계산서']:
            operating_profit = highlights['손익계산서']['영업이익']['당기']
            net_income = highlights['손익계산서']['당기순이익']['당기']
            sales = highlights['손익계산서']['매출액']['당기']
            
            if sales > 0:
                highlights['재무비율']['영업이익률'] = round((operating_profit / sales) * 100, 2)
                highlights['재무비율']['순이익률'] = round((net_income / sales) * 100, 2)
            else:
                highlights['재무비율']['영업이익률'] = None
                highlights['재무비율']['순이익률'] = None
    except Exception as e:
        logger.error(f"재무비율 계산 중 오류 발생: {e}")
    
    return highlights

def format_currency(amount, unit='원'):
    """
    금액을 읽기 쉬운 형식으로 포맷팅합니다.
    """
    if amount is None:
        return "정보 없음"
    
    if amount >= 1_000_000_000_000:
        return f"{amount / 1_000_000_000_000:.2f}조 {unit}"
    elif amount >= 100_000_000:
        return f"{amount / 100_000_000:.2f}억 {unit}"
    elif amount >= 10000:
        return f"{amount / 10000:.2f}만 {unit}"
    else:
        return f"{amount:,} {unit}"

def prepare_financial_summary(highlights):
    """
    AI 분석을 위한 재무 정보 요약을 준비합니다.
    """
    if not highlights:
        return "재무 데이터가 없습니다."
    
    summary = []
    
    # 회사 정보
    company_info = highlights['회사정보']
    summary.append(f"회사명: {company_info['회사명']}")
    summary.append(f"종목코드: {company_info['종목코드']}")
    summary.append(f"사업연도: {company_info['연도']}")
    summary.append("")
    
    # 재무상태표
    summary.append("재무상태표 (단위: 원)")
    summary.append("-" * 50)
    for account, values in highlights['재무상태표'].items():
        current = format_currency(values['당기'])
        previous = format_currency(values['전기'])
        change = values['당기'] - values['전기'] if values['당기'] is not None and values['전기'] is not None else None
        change_percent = (change / values['전기'] * 100) if change is not None and values['전기'] != 0 else None
        
        change_str = f"(전년대비 {format_currency(change)}, {change_percent:.2f}%)" if change is not None and change_percent is not None else ""
        summary.append(f"{account}: {current} {change_str}")
    summary.append("")
    
    # 손익계산서
    summary.append("손익계산서 (단위: 원)")
    summary.append("-" * 50)
    for account, values in highlights['손익계산서'].items():
        current = format_currency(values['당기'])
        previous = format_currency(values['전기'])
        change = values['당기'] - values['전기'] if values['당기'] is not None and values['전기'] is not None else None
        change_percent = (change / values['전기'] * 100) if change is not None and values['전기'] != 0 else None
        
        change_str = f"(전년대비 {format_currency(change)}, {change_percent:.2f}%)" if change is not None and change_percent is not None else ""
        summary.append(f"{account}: {current} {change_str}")
    summary.append("")
    
    # 재무비율
    summary.append("주요 재무비율")
    summary.append("-" * 50)
    for ratio, value in highlights['재무비율'].items():
        if value is not None:
            summary.append(f"{ratio}: {value:.2f}%")
        else:
            summary.append(f"{ratio}: 정보 없음")
    
    return "\n".join(summary)

def generate_fallback_analysis(highlights):
    """
    AI API 오류 시 사용할 기본 분석을 생성합니다.
    """
    if not highlights:
        return "재무 데이터가 없습니다."
    
    analysis = []
    company_info = highlights['회사정보']
    
    analysis.append(f"📊 {company_info['회사명']} ({company_info['종목코드']}) {company_info['연도']}년 재무분석")
    analysis.append("=" * 60)
    analysis.append("")
    
    # 재무상태표 분석
    analysis.append("🏢 재무상태표 분석")
    analysis.append("-" * 30)
    
    if '자산총계' in highlights['재무상태표']:
        assets = highlights['재무상태표']['자산총계']['당기']
        prev_assets = highlights['재무상태표']['자산총계']['전기']
        assets_change = assets - prev_assets if prev_assets != 0 else 0
        assets_change_pct = (assets_change / prev_assets * 100) if prev_assets != 0 else 0
        
        analysis.append(f"• 총자산: {format_currency(assets)}")
        if prev_assets != 0:
            change_symbol = "📈" if assets_change > 0 else "📉" if assets_change < 0 else "➡️"
            analysis.append(f"  {change_symbol} 전년대비 {format_currency(assets_change)} ({assets_change_pct:+.1f}%)")
    
    if '부채총계' in highlights['재무상태표'] and '자본총계' in highlights['재무상태표']:
        liabilities = highlights['재무상태표']['부채총계']['당기']
        equity = highlights['재무상태표']['자본총계']['당기']
        
        analysis.append(f"• 총부채: {format_currency(liabilities)}")
        analysis.append(f"• 자본총계: {format_currency(equity)}")
        
        if equity > 0:
            debt_ratio = (liabilities / equity) * 100
            analysis.append(f"• 부채비율: {debt_ratio:.1f}%")
            if debt_ratio > 200:
                analysis.append("  ⚠️ 부채비율이 높아 재무위험이 있을 수 있습니다.")
            elif debt_ratio < 100:
                analysis.append("  ✅ 부채비율이 안정적입니다.")
    
    analysis.append("")
    
    # 손익계산서 분석
    analysis.append("💰 손익계산서 분석")
    analysis.append("-" * 30)
    
    if '매출액' in highlights['손익계산서']:
        sales = highlights['손익계산서']['매출액']['당기']
        prev_sales = highlights['손익계산서']['매출액']['전기']
        sales_change = sales - prev_sales if prev_sales != 0 else 0
        sales_change_pct = (sales_change / prev_sales * 100) if prev_sales != 0 else 0
        
        analysis.append(f"• 매출액: {format_currency(sales)}")
        if prev_sales != 0:
            change_symbol = "📈" if sales_change > 0 else "📉" if sales_change < 0 else "➡️"
            analysis.append(f"  {change_symbol} 전년대비 {format_currency(sales_change)} ({sales_change_pct:+.1f}%)")
    
    if '영업이익' in highlights['손익계산서'] and '매출액' in highlights['손익계산서']:
        operating_profit = highlights['손익계산서']['영업이익']['당기']
        sales = highlights['손익계산서']['매출액']['당기']
        
        analysis.append(f"• 영업이익: {format_currency(operating_profit)}")
        if sales > 0:
            operating_margin = (operating_profit / sales) * 100
            analysis.append(f"• 영업이익률: {operating_margin:.1f}%")
            if operating_margin > 10:
                analysis.append("  ✅ 높은 영업이익률을 보여 수익성이 우수합니다.")
            elif operating_margin < 5:
                analysis.append("  ⚠️ 영업이익률이 낮아 수익성 개선이 필요합니다.")
    
    if '당기순이익' in highlights['손익계산서']:
        net_income = highlights['손익계산서']['당기순이익']['당기']
        prev_net_income = highlights['손익계산서']['당기순이익']['전기']
        
        analysis.append(f"• 당기순이익: {format_currency(net_income)}")
        if prev_net_income != 0:
            net_change = net_income - prev_net_income
            net_change_pct = (net_change / prev_net_income * 100)
            change_symbol = "📈" if net_change > 0 else "📉" if net_change < 0 else "➡️"
            analysis.append(f"  {change_symbol} 전년대비 {format_currency(net_change)} ({net_change_pct:+.1f}%)")
    
    analysis.append("")
    
    # 재무비율 분석
    analysis.append("📊 주요 재무비율")
    analysis.append("-" * 30)
    
    for ratio, value in highlights['재무비율'].items():
        if value is not None:
            analysis.append(f"• {ratio}: {value:.1f}%")
    
    analysis.append("")
    analysis.append("💡 종합 평가")
    analysis.append("-" * 30)
    
    # 간단한 종합 평가
    if 'ROE(자기자본이익률)' in highlights['재무비율']:
        roe = highlights['재무비율']['ROE(자기자본이익률)']
        if roe > 15:
            analysis.append("✅ 높은 ROE로 주주가치 창출이 우수합니다.")
        elif roe > 8:
            analysis.append("➡️ 적정 수준의 ROE를 보여줍니다.")
        else:
            analysis.append("⚠️ ROE가 낮아 수익성 개선이 필요합니다.")
    
    if '부채비율' in highlights['재무비율']:
        debt_ratio = highlights['재무비율']['부채비율']
        if debt_ratio < 100:
            analysis.append("✅ 안정적인 부채비율을 유지하고 있습니다.")
        elif debt_ratio < 200:
            analysis.append("➡️ 보통 수준의 부채비율입니다.")
        else:
            analysis.append("⚠️ 높은 부채비율로 재무위험 관리가 필요합니다.")
    
    analysis.append("")
    analysis.append("📝 참고: 이 분석은 기본 재무지표를 바탕으로 작성되었습니다.")
    analysis.append("더 정확한 투자 판단을 위해서는 추가적인 분석이 필요합니다.")
    
    return "\n".join(analysis)

def analyze_financial_data(financial_data):
    """
    Gemini API를 사용하여 재무 데이터를 분석합니다.
    
    Args:
        financial_data: DART API로부터 받은 재무제표 데이터
        
    Returns:
        AI 분석 결과
    """
    # 재무 정보 추출
    highlights = extract_financial_highlights(financial_data)
    
    if not highlights:
        return "재무 데이터를 분석할 수 없습니다."
    
    # 분석을 위한 요약 정보 준비
    financial_summary = prepare_financial_summary(highlights)
    
    # Gemini API 프롬프트 생성 (더 간결하게)
    prompt = f"""
    다음은 한국 기업의 재무제표 정보입니다. 간결하고 이해하기 쉽게 분석해주세요.

    {financial_summary}

    다음 내용을 포함해주세요:
    1. 전반적인 재무 건전성 평가
    2. 전년 대비 주요 변화
    3. 투자자 관점에서 주목할 점
    4. 쉬운 용어로 설명

    전문 용어를 최소화하고 일반인이 이해하기 쉽게 작성해주세요.
    """
    
    max_retries = 3
    retry_delay = 5  # 초기 대기 시간
    
    for attempt in range(max_retries):
        try:
            # Gemini API 호출
            response = model.generate_content(prompt)
            analysis = response.text
            
            return analysis
            
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"AI 분석 시도 {attempt + 1}/{max_retries} 실패: {error_msg}")
            
            # 할당량 초과 오류인지 확인
            if "quota" in error_msg.lower() or "429" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # 지수 백오프
                    logger.info(f"할당량 초과. {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("Gemini API 할당량 초과. 기본 분석을 제공합니다.")
                    return generate_fallback_analysis(highlights)
            else:
                # 다른 오류의 경우 기본 분석 제공
                logger.error(f"AI 분석 중 오류 발생: {e}")
                return generate_fallback_analysis(highlights)
    
    # 모든 재시도 실패 시 기본 분석 제공
    return generate_fallback_analysis(highlights) 