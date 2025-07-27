import os
import json
import sqlite3
from dotenv import load_dotenv

def create_database():
    """
    corp_codes.json 파일에서 회사 정보를 읽어 SQLite 데이터베이스를 생성합니다.
    """
    # 데이터베이스 파일 경로
    db_path = 'corp_codes.db'
    
    # 이미 존재하는 경우 기존 DB 삭제
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 테이블 생성
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        corp_code TEXT NOT NULL UNIQUE,
        corp_name TEXT NOT NULL,
        stock_code TEXT,
        modify_date TEXT
    )
    ''')
    
    # 인덱스 생성
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_corp_name ON companies (corp_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_code ON companies (stock_code)')
    
    try:
        # JSON 파일 로드
        with open('corp_codes.json', 'r', encoding='utf-8') as f:
            corp_codes = json.load(f)
        
        # 데이터 삽입
        for company in corp_codes:
            cursor.execute(
                'INSERT INTO companies (corp_code, corp_name, stock_code, modify_date) VALUES (?, ?, ?, ?)',
                (
                    company.get('corp_code', ''),
                    company.get('corp_name', ''),
                    company.get('stock_code', ''),
                    company.get('modify_date', '')
                )
            )
        
        # 변경사항 저장
        conn.commit()
        print(f"데이터베이스 생성 완료: {len(corp_codes)}개 회사 정보가 저장되었습니다.")
    
    except Exception as e:
        print(f"데이터베이스 생성 중 오류 발생: {e}")
        conn.rollback()
    
    finally:
        # 연결 종료
        conn.close()

def search_companies(query, limit=10):
    """
    회사명으로 데이터베이스를 검색합니다.
    
    Args:
        query: 검색할 회사명
        limit: 최대 결과 수
        
    Returns:
        검색 결과 목록
    """
    # 데이터베이스 연결
    conn = sqlite3.connect('corp_codes.db')
    conn.row_factory = sqlite3.Row  # 결과를 딕셔너리 형태로 반환
    cursor = conn.cursor()
    
    try:
        # 검색 쿼리 실행
        cursor.execute(
            'SELECT * FROM companies WHERE corp_name LIKE ? ORDER BY CASE WHEN stock_code IS NOT NULL AND stock_code != "" THEN 0 ELSE 1 END, corp_name LIMIT ?',
            (f'%{query}%', limit)
        )
        
        # 결과 가져오기
        results = [dict(row) for row in cursor.fetchall()]
        return results
    
    except Exception as e:
        print(f"회사 검색 중 오류 발생: {e}")
        return []
    
    finally:
        # 연결 종료
        conn.close()

if __name__ == '__main__':
    # 데이터베이스 생성
    create_database() 