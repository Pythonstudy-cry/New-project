import os
import json
import requests
import pandas as pd
import matplotlib
# 스레드 안전을 위해 Matplotlib 백엔드를 'Agg'로 설정 (반드시 pyplot 임포트 전에 설정)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import base64
import sqlite3
import asyncio
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from matplotlib import font_manager, rc
import sys
import numpy as np
import logging
from create_db import search_companies
from finance_analysis import analyze_financial_data

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 한글 폰트 설정
def set_korean_font():
    try:
        # 폰트 경고 무시 설정
        import warnings
        warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
        
        # Docker 환경에서는 Noto Sans CJK 폰트 사용
        if os.path.exists('/app'):
            # Docker 환경 - Noto Sans CJK 사용
            plt.rc('font', family='Noto Sans CJK KR')
            logger.info("Docker 환경에서 Noto Sans CJK KR 폰트 사용")
        # 윈도우의 경우 맑은 고딕 폰트 사용
        elif sys.platform == 'win32':
            font_path = "C:/Windows/Fonts/malgun.ttf"
            if os.path.exists(font_path):
                font_name = font_manager.FontProperties(fname=font_path).get_name()
                plt.rc('font', family=font_name)
                logger.info(f"Windows 환경에서 {font_name} 폰트 사용")
            else:
                plt.rc('font', family='DejaVu Sans')
                logger.info("Windows 환경에서 DejaVu Sans 폰트 사용")
        # Mac의 경우 애플고딕 폰트 사용
        elif sys.platform == 'darwin':
            rc('font', family='AppleGothic')
            logger.info("Mac 환경에서 AppleGothic 폰트 사용")
        # 리눅스의 경우 Noto Sans CJK 폰트 사용
        else:
            rc('font', family='Noto Sans CJK KR')
            logger.info("Linux 환경에서 Noto Sans CJK KR 폰트 사용")
        
        # 마이너스 기호 표시 설정
        matplotlib.rcParams['axes.unicode_minus'] = False
        
        # 폰트 크기 및 스타일 설정
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['axes.labelsize'] = 10
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9
        plt.rcParams['figure.titlesize'] = 14
        
        # 그래프 스타일 설정
        plt.style.use('default')
        sns.set_palette("husl")
        
        # 폰트 캐시 초기화
        font_manager._rebuild()
        
        return True
    except Exception as e:
        logger.error(f"한글 폰트 설정에 실패했습니다: {e}")
        # 기본 폰트로 설정 (한글 지원 폰트 우선)
        try:
            plt.rc('font', family='Noto Sans CJK KR')
            logger.info("fallback: Noto Sans CJK KR 폰트 사용")
        except:
            try:
                plt.rc('font', family='NanumGothic')
                logger.info("fallback: NanumGothic 폰트 사용")
            except:
                plt.rc('font', family='DejaVu Sans')
                logger.info("fallback: DejaVu Sans 폰트 사용")
        
        matplotlib.rcParams['axes.unicode_minus'] = False
        return False

# .env 파일에서 환경변수 로드
load_dotenv()

# API 키 가져오기
API_KEY = os.getenv('OPEN_DART_API_KEY')

if not API_KEY:
    logger.error("Error: OPEN_DART_API_KEY가 .env 파일에 설정되지 않았습니다.")
    exit(1)

# Flask 앱 생성
app = Flask(__name__)

# 한글 폰트 설정 실행
set_korean_font()

# 데이터베이스 존재 여부 확인
def check_database():
    if not os.path.exists('corp_codes.db'):
        if os.path.exists('corp_codes.json'):
            from create_db import create_database
            create_database()
        else:
            return False
    return True

# 회사 검색 함수
def search_company_db(company_name, limit=10):
    """
    데이터베이스에서 회사명으로 검색합니다.
    """
    if not check_database():
        return []
    
    return search_companies(company_name, limit)

# 재무제표 데이터 가져오기
def get_financial_data(corp_code, bsns_year, reprt_code):
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': bsns_year,
        'reprt_code': reprt_code
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        logger.error(f"재무제표 데이터 요청 실패 (Status Code: {response.status_code})")
        return None
    
    data = response.json()
    
    if data['status'] != '000':
        logger.error(f"재무제표 데이터 요청 실패 (Status: {data['status']})")
        return None
    
    return data

# 그래프를 이미지로 변환
def fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_str

# 재무제표 데이터 처리 및 시각화
def process_and_visualize(financial_data):
    if not financial_data or 'list' not in financial_data:
        logger.warning("재무제표 데이터가 비어있거나 예상과 다릅니다.")
        return None, None, None, None
    
    # 폰트 경고 무시 설정
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
    
    # 데이터프레임 생성
    df = pd.DataFrame(financial_data['list'])
    
    # 연결 재무제표만 필터링
    cfs_df = df[df['fs_div'] == 'CFS']
    if cfs_df.empty:
        cfs_df = df[df['fs_div'] == 'OFS']
    
    # 필요한 계정과목 선택 (재무상태표 - 기본)
    bs_accounts = ['자산총계', '부채총계', '자본총계']
    bs_data = cfs_df[cfs_df['account_nm'].isin(bs_accounts)].copy()
    
    # 자산=부채+자본 관계용 세부 계정과목
    balance_accounts = ['자산총계', '부채총계', '자본총계', '유동자산', '비유동자산', '유동부채', '비유동부채']
    balance_data = cfs_df[cfs_df['account_nm'].isin(balance_accounts)].copy()
    
    # 필요한 계정과목 선택 (손익계산서)
    is_accounts = ['매출액', '영업이익', '당기순이익']
    is_data = cfs_df[cfs_df['account_nm'].isin(is_accounts)].copy()
    
    # 한글 폰트 설정
    set_korean_font()
    
    # 결과 저장할 이미지 변수
    bs_img = None
    is_img = None
    ratio_img = None
    balance_img = None
    
    try:
        # 1. 재무상태표 시각화 (당기, 전기만) - 이전과 동일
        if not bs_data.empty:
            # 문자열 금액을 숫자로 변환
            for col in ['thstrm_amount', 'frmtrm_amount']:
                if col in bs_data.columns:
                    bs_data.loc[:, col] = bs_data[col].str.replace(',', '').astype(float) / 1_000_000_000  # 10억 단위로 변환
            
            # 당기, 전기 데이터만 준비
            current_year = bs_data[['account_nm', 'thstrm_amount']].rename(columns={'thstrm_amount': '당기'})
            prev_year = bs_data[['account_nm', 'frmtrm_amount']].rename(columns={'frmtrm_amount': '전기'})
            
            # 데이터 병합
            merged_data = current_year.merge(prev_year, on='account_nm')
            merged_data = merged_data.set_index('account_nm')
            
            # 그래프 그리기
            fig, ax = plt.subplots(figsize=(10, 6))
            merged_data.plot(kind='bar', ax=ax, color=['#3498db', '#e74c3c'])
            plt.title('재무상태표 (단위: 10억원)', fontsize=16, fontweight='bold')
            plt.ylabel('금액 (10억원)')
            plt.xticks(rotation=0)
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # 값 표시
            for container in ax.containers:
                ax.bar_label(container, fmt='%.1f')
            
            plt.tight_layout()
            bs_img = fig_to_base64(fig)
            
            # 2. 자산 = 부채 + 자본 관계 시각화
            try:
                # 당기 데이터 추출 (10억원 단위)
                balance_current_year = balance_data[['account_nm', 'thstrm_amount']].rename(columns={'thstrm_amount': '당기'})
                
                # 문자열 금액을 숫자로 변환 (10억 단위)
                balance_current_year.loc[:, '당기'] = balance_current_year['당기'].str.replace(',', '').astype(float) / 1_000_000_000
                
                assets = balance_current_year.loc[balance_current_year['account_nm'] == '자산총계', '당기'].values[0]
                liabilities = balance_current_year.loc[balance_current_year['account_nm'] == '부채총계', '당기'].values[0]
                equity = balance_current_year.loc[balance_current_year['account_nm'] == '자본총계', '당기'].values[0]
                
                # 세부 항목 추출
                current_assets = balance_current_year.loc[balance_current_year['account_nm'] == '유동자산', '당기'].values[0] if '유동자산' in balance_current_year['account_nm'].values else 0
                non_current_assets = balance_current_year.loc[balance_current_year['account_nm'] == '비유동자산', '당기'].values[0] if '비유동자산' in balance_current_year['account_nm'].values else 0
                current_liabilities = balance_current_year.loc[balance_current_year['account_nm'] == '유동부채', '당기'].values[0] if '유동부채' in balance_current_year['account_nm'].values else 0
                non_current_liabilities = balance_current_year.loc[balance_current_year['account_nm'] == '비유동부채', '당기'].values[0] if '비유동부채' in balance_current_year['account_nm'].values else 0
                
                # 반올림
                assets = round(assets)
                liabilities = round(liabilities)
                equity = round(equity)
                current_assets = round(current_assets)
                non_current_assets = round(non_current_assets)
                current_liabilities = round(current_liabilities)
                non_current_liabilities = round(non_current_liabilities)
                
                # 자산 = 부채 + 자본 관계 시각화 (텍스트 기반)
                fig, ax = plt.subplots(figsize=(12, 8))
                ax.axis('off')
                
                # 배경 박스 그리기
                rect = plt.Rectangle((0.1, 0.1), 0.8, 0.8, linewidth=3, edgecolor='#2c3e50', facecolor='none')
                ax.add_patch(rect)
                
                # 제목
                ax.text(0.5, 0.95, '자산 = 부채 + 자본', fontsize=20, fontweight='bold', 
                       ha='center', va='center', color='#2c3e50')
                
                # 자산 부분 (왼쪽)
                ax.text(0.25, 0.75, '자산', fontsize=16, fontweight='bold', 
                       ha='center', va='center', color='#2c3e50')
                ax.text(0.25, 0.65, f'{assets:,}억원', fontsize=14, 
                       ha='center', va='center', color='#2c3e50')
                
                # 자산 세부 내역
                ax.text(0.25, 0.55, f'유동자산: {current_assets:,}억원', fontsize=12, 
                       ha='center', va='center', color='#3498db')
                ax.text(0.25, 0.45, f'비유동자산: {non_current_assets:,}억원', fontsize=12, 
                       ha='center', va='center', color='#e74c3c')
                
                # 부채 + 자본 부분 (오른쪽)
                ax.text(0.75, 0.75, '부채 + 자본', fontsize=16, fontweight='bold', 
                       ha='center', va='center', color='#2c3e50')
                ax.text(0.75, 0.65, f'{liabilities + equity:,}억원', fontsize=14, 
                       ha='center', va='center', color='#2c3e50')
                
                # 부채 세부 내역
                ax.text(0.75, 0.55, f'유동부채: {current_liabilities:,}억원', fontsize=12, 
                       ha='center', va='center', color='#f39c12')
                ax.text(0.75, 0.45, f'비유동부채: {non_current_liabilities:,}억원', fontsize=12, 
                       ha='center', va='center', color='#9b59b6')
                
                # 자본
                ax.text(0.75, 0.35, f'자본: {equity:,}억원', fontsize=12, 
                       ha='center', va='center', color='#27ae60')
                
                # 등호 표시
                ax.text(0.5, 0.25, '=', fontsize=24, fontweight='bold', 
                       ha='center', va='center', color='#e74c3c')
                
                # 검증 메시지
                if abs(assets - (liabilities + equity)) < 1:  # 1억원 이내 차이
                    ax.text(0.5, 0.15, '✓ 자산 = 부채 + 자본 (균형)', fontsize=12, 
                           ha='center', va='center', color='#27ae60', fontweight='bold')
                else:
                    ax.text(0.5, 0.15, f'⚠ 차이: {abs(assets - (liabilities + equity)):,.0f}억원', fontsize=12, 
                           ha='center', va='center', color='#e74c3c', fontweight='bold')
                
                plt.tight_layout()
                balance_img = fig_to_base64(fig)
            except Exception as e:
                logger.error(f"자산-부채-자본 관계 그래프 생성 중 오류 발생: {e}")
            
            # 3. 손익계산서 시각화 (당기, 전기만)
            if not is_data.empty:
                # 문자열 금액을 숫자로 변환
                for col in ['thstrm_amount', 'frmtrm_amount']:
                    if col in is_data.columns:
                        is_data.loc[:, col] = is_data[col].str.replace(',', '').astype(float) / 1_000_000_000  # 10억 단위로 변환
                
                # 당기, 전기 데이터만 준비
                current_year = is_data[['account_nm', 'thstrm_amount']].rename(columns={'thstrm_amount': '당기'})
                prev_year = is_data[['account_nm', 'frmtrm_amount']].rename(columns={'frmtrm_amount': '전기'})
                
                # 데이터 병합
                merged_data = current_year.merge(prev_year, on='account_nm')
                merged_data = merged_data.set_index('account_nm')
                
                # 그래프 그리기
                fig, ax = plt.subplots(figsize=(10, 6))
                merged_data.plot(kind='bar', ax=ax, color=['#3498db', '#e74c3c'])
                plt.title('손익계산서 (단위: 10억원)', fontsize=16, fontweight='bold')
                plt.ylabel('금액 (10억원)')
                plt.xticks(rotation=0)
                plt.grid(axis='y', linestyle='--', alpha=0.7)
                
                # 값 표시
                for container in ax.containers:
                    ax.bar_label(container, fmt='%.1f')
                
                plt.tight_layout()
                is_img = fig_to_base64(fig)
            
            # 4. 주요 재무비율 시각화 (5각형 레이더 차트)
            try:
                # 재무비율 계산
                if not bs_data.empty and not is_data.empty:
                    # 당기 데이터 추출
                    bs_current = bs_data[['account_nm', 'thstrm_amount']].set_index('account_nm')
                    is_current = is_data[['account_nm', 'thstrm_amount']].set_index('account_nm')
                    
                    # 문자열 금액을 숫자로 변환
                    for df in [bs_current, is_current]:
                        df['thstrm_amount'] = df['thstrm_amount'].str.replace(',', '').astype(float)
                    
                    # 재무비율 계산
                    total_assets = bs_current.loc['자산총계', 'thstrm_amount']
                    total_liabilities = bs_current.loc['부채총계', 'thstrm_amount']
                    total_equity = bs_current.loc['자본총계', 'thstrm_amount']
                    sales = is_current.loc['매출액', 'thstrm_amount']
                    operating_income = is_current.loc['영업이익', 'thstrm_amount']
                    net_income = is_current.loc['당기순이익', 'thstrm_amount']
                    
                    # 재무비율 계산
                    debt_ratio = (total_liabilities / total_equity) * 100  # 부채비율
                    roa = (net_income / total_assets) * 100  # ROA
                    roe = (net_income / total_equity) * 100  # ROE
                    operating_margin = (operating_income / sales) * 100  # 영업이익률
                    net_margin = (net_income / sales) * 100  # 순이익률
                    
                    # 레이더 차트 그리기
                    categories = ['부채비율', 'ROA', 'ROE', '영업이익률', '순이익률']
                    values = [debt_ratio, roa, roe, operating_margin, net_margin]
                    
                    # 각도 계산
                    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
                    values += values[:1]  # 첫 번째 값을 마지막에 추가하여 닫힌 도형 만들기
                    angles += angles[:1]
                    
                    fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(projection='polar'))
                    ax.plot(angles, values, 'o-', linewidth=2, color='#3498db')
                    ax.fill(angles, values, alpha=0.25, color='#3498db')
                    
                    # 축 레이블 설정
                    ax.set_xticks(angles[:-1])
                    ax.set_xticklabels(categories)
                    
                    # 그리드 설정
                    ax.grid(True)
                    
                    # 제목
                    plt.title('주요 재무비율 (5각형 레이더 차트)', fontsize=16, fontweight='bold', pad=20)
                    
                    # 값 표시
                    for i, (angle, value) in enumerate(zip(angles[:-1], values[:-1])):
                        ax.text(angle, value + max(values) * 0.1, f'{value:.1f}%', 
                               ha='center', va='center', fontweight='bold')
                    
                    plt.tight_layout()
                    ratio_img = fig_to_base64(fig)
            except (IndexError, ValueError) as e:
                logger.error(f"재무비율 계산 중 오류 발생: {e}")
    except Exception as e:
        logger.error(f"그래프 생성 중 오류 발생: {e}")
    
    return bs_img, is_img, ratio_img, balance_img

# 메인 페이지
@app.route('/')
def index():
    return render_template('index.html')

# 회사 검색 API
@app.route('/api/search', methods=['POST'])
def search():
    company_name = request.form.get('company_name')
    
    if not company_name:
        return jsonify({'error': '회사명을 입력해주세요.'})
    
    results = search_company_db(company_name)
    
    if not results:
        return jsonify({'error': f"'{company_name}'에 해당하는 회사를 찾을 수 없습니다."})
    
    return jsonify({'companies': results})

# 재무제표 시각화 API
@app.route('/api/visualize', methods=['POST'])
def visualize():
    corp_code = request.form.get('corp_code')
    corp_name = request.form.get('corp_name')
    bsns_year = request.form.get('bsns_year')
    reprt_code = request.form.get('reprt_code')
    
    if not all([corp_code, corp_name, bsns_year, reprt_code]):
        return jsonify({'error': '모든 필수 항목을 입력해주세요.'})
    
    financial_data = get_financial_data(corp_code, bsns_year, reprt_code)
    
    if not financial_data:
        return jsonify({'error': '재무제표 데이터를 가져오는데 실패했습니다.'})
    
    bs_img, is_img, ratio_img, balance_img = process_and_visualize(financial_data)
    
    return jsonify({
        'bs_img': bs_img,
        'is_img': is_img,
        'ratio_img': ratio_img,
        'balance_img': balance_img,
        'corp_name': corp_name,
        'bsns_year': bsns_year
    })

# AI 재무 분석 API
@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        corp_code = request.form.get('corp_code')
        corp_name = request.form.get('corp_name')
        bsns_year = request.form.get('bsns_year')
        reprt_code = request.form.get('reprt_code')
        
        if not all([corp_code, corp_name, bsns_year, reprt_code]):
            return jsonify({'error': '모든 필수 항목을 입력해주세요.'})
        
        financial_data = get_financial_data(corp_code, bsns_year, reprt_code)
        
        if not financial_data:
            return jsonify({'error': '재무제표 데이터를 가져오는데 실패했습니다.'})
        
        # AI 분석 실행 (fallback 포함)
        analysis_result = analyze_financial_data(financial_data)
        
        # 분석 결과가 오류 메시지인지 확인
        if analysis_result and not analysis_result.startswith('재무 데이터를 분석할 수 없습니다'):
            return jsonify({
                'analysis': analysis_result,
                'corp_name': corp_name,
                'bsns_year': bsns_year
            })
        else:
            # fallback 분석이 제공된 경우
            return jsonify({
                'analysis': analysis_result,
                'corp_name': corp_name,
                'bsns_year': bsns_year,
                'note': '기본 재무 분석이 제공되었습니다.'
            })
            
    except Exception as e:
        logger.error(f"AI 분석 API 오류: {e}")
        return jsonify({
            'error': 'AI 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
            'corp_name': corp_name if 'corp_name' in locals() else '',
            'bsns_year': bsns_year if 'bsns_year' in locals() else ''
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 