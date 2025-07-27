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
from create_db import search_companies
from finance_analysis import analyze_financial_data

# 한글 폰트 설정
def set_korean_font():
    try:
        # Docker 환경에서는 기본 폰트 사용
        if os.path.exists('/app'):
            # Docker 환경
            plt.rc('font', family='DejaVu Sans')
        # 윈도우의 경우 맑은 고딕 폰트 사용
        elif sys.platform == 'win32':
            font_path = "C:/Windows/Fonts/malgun.ttf"
            if os.path.exists(font_path):
                font_name = font_manager.FontProperties(fname=font_path).get_name()
                plt.rc('font', family=font_name)
            else:
                plt.rc('font', family='DejaVu Sans')
        # Mac의 경우 애플고딕 폰트 사용
        elif sys.platform == 'darwin':
            rc('font', family='AppleGothic')
        # 리눅스의 경우 나눔고딕 폰트 사용
        else:
            rc('font', family='NanumGothic')
        
        # 마이너스 기호 표시 설정
        matplotlib.rcParams['axes.unicode_minus'] = False
        return True
    except Exception as e:
        print(f"한글 폰트 설정에 실패했습니다: {e}")
        # 기본 폰트로 설정
        plt.rc('font', family='DejaVu Sans')
        matplotlib.rcParams['axes.unicode_minus'] = False
        return False

# .env 파일에서 환경변수 로드
load_dotenv()

# API 키 가져오기
API_KEY = os.getenv('OPEN_DART_API_KEY')

if not API_KEY:
    print("Error: OPEN_DART_API_KEY가 .env 파일에 설정되지 않았습니다.")
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
        return None
    
    data = response.json()
    
    if data['status'] != '000':
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
        return None, None, None, None
    
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
                
                # 시각화
                fig, ax = plt.subplots(figsize=(16, 12))
                
                # 제목
                ax.text(0.5, 0.95, '자산 = 부채 + 자본', fontsize=24, fontweight='bold', ha='center', va='center', color='#2c3e50')
                ax.text(0.5, 0.9, '회사의 모든 자산은 부채와 자본으로 구성됩니다', fontsize=16, ha='center', va='center', color='#7f8c8d')
                
                # 왼쪽: 자산 (큰 박스)
                rect_assets = plt.Rectangle((0.05, 0.4), 0.35, 0.4, linewidth=3, edgecolor='#3498db', facecolor='#3498db', alpha=0.1)
                ax.add_patch(rect_assets)
                ax.text(0.225, 0.75, '자산', fontsize=20, fontweight='bold', ha='center', va='center', color='#2c3e50')
                ax.text(0.225, 0.7, f'{assets:,}억원', fontsize=16, ha='center', va='center', color='#3498db', fontweight='bold')
                
                # 자산 세부
                if assets > 0:
                    # 유동자산 (작은 박스)
                    rect_current_assets = plt.Rectangle((0.08, 0.45), 0.12, 0.15, linewidth=2, edgecolor='#27ae60', facecolor='#27ae60', alpha=0.7)
                    ax.add_patch(rect_current_assets)
                    ax.text(0.14, 0.55, '유동자산', fontsize=12, fontweight='bold', ha='center', va='center', color='white')
                    ax.text(0.14, 0.5, f'{current_assets:,}억원', fontsize=10, ha='center', va='center', color='white')
                    
                    # 비유동자산 (작은 박스)
                    rect_non_current_assets = plt.Rectangle((0.25, 0.45), 0.12, 0.15, linewidth=2, edgecolor='#f39c12', facecolor='#f39c12', alpha=0.7)
                    ax.add_patch(rect_non_current_assets)
                    ax.text(0.31, 0.55, '비유동자산', fontsize=12, fontweight='bold', ha='center', va='center', color='white')
                    ax.text(0.31, 0.5, f'{non_current_assets:,}억원', fontsize=10, ha='center', va='center', color='white')
                
                # 등호
                ax.text(0.5, 0.6, '=', fontsize=40, fontweight='bold', ha='center', va='center', color='#2c3e50')
                
                # 오른쪽: 부채 + 자본 (큰 박스)
                rect_liabilities_equity = plt.Rectangle((0.6, 0.4), 0.35, 0.4, linewidth=3, edgecolor='#e74c3c', facecolor='#e74c3c', alpha=0.1)
                ax.add_patch(rect_liabilities_equity)
                ax.text(0.775, 0.75, '부채 + 자본', fontsize=18, fontweight='bold', ha='center', va='center', color='#2c3e50')
                ax.text(0.775, 0.7, f'{liabilities + equity:,}억원', fontsize=16, ha='center', va='center', color='#e74c3c', fontweight='bold')
                
                # 부채 세부
                if liabilities > 0:
                    # 유동부채 (작은 박스)
                    rect_current_liabilities = plt.Rectangle((0.63, 0.45), 0.12, 0.15, linewidth=2, edgecolor='#e67e22', facecolor='#e67e22', alpha=0.7)
                    ax.add_patch(rect_current_liabilities)
                    ax.text(0.69, 0.55, '유동부채', fontsize=12, fontweight='bold', ha='center', va='center', color='white')
                    ax.text(0.69, 0.5, f'{current_liabilities:,}억원', fontsize=10, ha='center', va='center', color='white')
                    
                    # 비유동부채 (작은 박스)
                    rect_non_current_liabilities = plt.Rectangle((0.8, 0.45), 0.12, 0.15, linewidth=2, edgecolor='#c0392b', facecolor='#c0392b', alpha=0.7)
                    ax.add_patch(rect_non_current_liabilities)
                    ax.text(0.86, 0.55, '비유동부채', fontsize=12, fontweight='bold', ha='center', va='center', color='white')
                    ax.text(0.86, 0.5, f'{non_current_liabilities:,}억원', fontsize=10, ha='center', va='center', color='white')
                
                # 자본 (별도 박스)
                rect_equity = plt.Rectangle((0.63, 0.25), 0.12, 0.12, linewidth=2, edgecolor='#27ae60', facecolor='#27ae60', alpha=0.7)
                ax.add_patch(rect_equity)
                ax.text(0.69, 0.31, '자본', fontsize=12, fontweight='bold', ha='center', va='center', color='white')
                ax.text(0.69, 0.26, f'{equity:,}억원', fontsize=10, ha='center', va='center', color='white')
                
                # 설명
                ax.text(0.5, 0.2, '자산 = 부채 + 자본', fontsize=18, fontweight='bold', ha='center', va='center', color='#2c3e50')
                ax.text(0.5, 0.15, f'{assets:,} = {liabilities:,} + {equity:,}', fontsize=16, ha='center', va='center', color='#7f8c8d')
                
                # 추가 설명
                ax.text(0.5, 0.08, '💡 자산: 회사가 보유한 모든 재산', fontsize=14, ha='center', va='center', color='#3498db')
                ax.text(0.5, 0.05, '💡 부채: 회사가 갚아야 할 모든 빚', fontsize=14, ha='center', va='center', color='#e74c3c')
                ax.text(0.5, 0.02, '💡 자본: 회사 소유주가 투자한 돈', fontsize=14, ha='center', va='center', color='#27ae60')
                
                # 축 제거
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.axis('off')
                
                plt.tight_layout()
                balance_img = fig_to_base64(fig)
            except Exception as e:
                print(f"자산-부채-자본 관계 그래프 생성 중 오류 발생: {e}")
        
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
        
        # 4. 주요 재무비율 계산 및 시각화 (5각형)
        if not bs_data.empty and not is_data.empty:
            try:
                # 이미 숫자로 변환된 데이터 사용
                total_assets = bs_data.loc[bs_data['account_nm'] == '자산총계', 'thstrm_amount'].values[0]
                total_equity = bs_data.loc[bs_data['account_nm'] == '자본총계', 'thstrm_amount'].values[0]
                total_liabilities = bs_data.loc[bs_data['account_nm'] == '부채총계', 'thstrm_amount'].values[0]
                
                sales = is_data.loc[is_data['account_nm'] == '매출액', 'thstrm_amount'].values[0]
                operating_profit = is_data.loc[is_data['account_nm'] == '영업이익', 'thstrm_amount'].values[0]
                net_income = is_data.loc[is_data['account_nm'] == '당기순이익', 'thstrm_amount'].values[0]
                
                # 재무비율 계산
                debt_ratio = (total_liabilities / total_equity) * 100  # 부채비율
                roe = (net_income / total_equity) * 100  # 자기자본이익률
                roa = (net_income / total_assets) * 100  # 총자산이익률
                operating_margin = (operating_profit / sales) * 100  # 영업이익률
                net_profit_margin = (net_income / sales) * 100  # 순이익률
                
                # 5각형 레이더 차트 생성
                categories = ['부채비율', 'ROE', 'ROA', '영업이익률', '순이익률']
                values = [debt_ratio, roe, roa, operating_margin, net_profit_margin]
                
                # 각도 계산
                angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
                values += values[:1]  # 첫 번째 값을 마지막에 추가하여 닫힌 도형 만들기
                angles += angles[:1]  # 첫 번째 각도를 마지막에 추가
                
                fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
                
                # 5각형 그리기
                ax.plot(angles, values, 'o-', linewidth=2, color='#3498db', markersize=8)
                ax.fill(angles, values, alpha=0.25, color='#3498db')
                
                # 축 레이블 설정
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels(categories, fontsize=12, fontweight='bold')
                
                # 그리드 설정
                ax.grid(True, alpha=0.3)
                
                # 제목
                plt.title('주요 재무비율 (5각형)', fontsize=16, fontweight='bold', pad=20)
                
                # 값 표시
                for i, (angle, value) in enumerate(zip(angles[:-1], values[:-1])):
                    ax.text(angle, value + max(values) * 0.05, f'{value:.2f}%', 
                           ha='center', va='center', fontweight='bold', fontsize=10)
                
                plt.tight_layout()
                ratio_img = fig_to_base64(fig)
            except (IndexError, ValueError) as e:
                print(f"재무비율 계산 중 오류 발생: {e}")
    except Exception as e:
        print(f"그래프 생성 중 오류 발생: {e}")
    
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
    corp_code = request.form.get('corp_code')
    corp_name = request.form.get('corp_name')
    bsns_year = request.form.get('bsns_year')
    reprt_code = request.form.get('reprt_code')
    
    if not all([corp_code, corp_name, bsns_year, reprt_code]):
        return jsonify({'error': '모든 필수 항목을 입력해주세요.'})
    
    financial_data = get_financial_data(corp_code, bsns_year, reprt_code)
    
    if not financial_data:
        return jsonify({'error': '재무제표 데이터를 가져오는데 실패했습니다.'})
    
    # 동기 함수로 직접 호출
    analysis_result = analyze_financial_data(financial_data)
    
    return jsonify({
        'analysis': analysis_result,
        'corp_name': corp_name,
        'bsns_year': bsns_year
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 