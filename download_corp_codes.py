import os
import json
import requests
import xmltodict
from dotenv import load_dotenv
import zipfile
from io import BytesIO

# .env 파일에서 환경변수 로드
load_dotenv()

# API 키 가져오기
API_KEY = os.getenv('OPEN_DART_API_KEY')

if not API_KEY:
    print("Error: OPEN_DART_API_KEY가 .env 파일에 설정되지 않았습니다.")
    exit(1)

print(f"API 키: {API_KEY[:5]}...{API_KEY[-5:]}")

# API URL
url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}"

print("회사 코드 파일 다운로드 중...")

try:
    # API 요청
    response = requests.get(url)
    
    # 응답 상태 확인
    if response.status_code != 200:
        print(f"Error: API 요청 실패 (상태 코드: {response.status_code})")
        print(f"응답 내용: {response.text}")
        exit(1)

    # 응답 내용이 XML인지 확인
    content_type = response.headers.get('Content-Type', '')
    print(f"응답 Content-Type: {content_type}")
    
    # 응답 크기 확인
    print(f"응답 크기: {len(response.content)} bytes")

    # 응답이 XML이고 오류 메시지가 포함되어 있는지 확인
    if len(response.content) < 1000 and b'<status>' in response.content:
        try:
            error_dict = xmltodict.parse(response.content)
            status = error_dict.get('r', {}).get('status')
            message = error_dict.get('r', {}).get('message')
            print(f"API 응답 상태: {status}, 메시지: {message}")
            if status != '000':
                print("API 오류가 발생했습니다. 자세한 내용은 위의 메시지를 참조하세요.")
                exit(1)
        except Exception as e:
            print(f"응답 파싱 오류: {e}")

    # ZIP 파일로 저장
    with open('corpCode.zip', 'wb') as f:
        f.write(response.content)
    
    print("ZIP 파일 다운로드 완료")

    # ZIP 파일 압축 해제 및 XML 파싱
    try:
        with zipfile.ZipFile('corpCode.zip', 'r') as zip_ref:
            # ZIP 파일 내용 확인
            print("ZIP 파일 내용:")
            for file_info in zip_ref.filelist:
                print(f" - {file_info.filename} ({file_info.file_size} bytes)")
            
            # CORPCODE.xml 파일 읽기
            with zip_ref.open('CORPCODE.xml') as xml_file:
                xml_content = xml_file.read()
                
                # XML을 딕셔너리로 변환
                xml_dict = xmltodict.parse(xml_content)
                
                # 회사 정보만 추출
                corps = xml_dict.get('result', {}).get('list', [])
                
                # 필요한 정보만 정리
                corp_list = []
                for corp in corps:
                    corp_info = {
                        'corp_code': corp.get('corp_code', ''),
                        'corp_name': corp.get('corp_name', ''),
                        'stock_code': corp.get('stock_code', ''),
                        'modify_date': corp.get('modify_date', '')
                    }
                    corp_list.append(corp_info)
                
                # JSON 파일로 저장
                with open('corp_codes.json', 'w', encoding='utf-8') as json_file:
                    json.dump(corp_list, json_file, ensure_ascii=False, indent=2)
        
        print("JSON 파일 생성 완료 - corp_codes.json 파일을 확인해주세요.")
    except zipfile.BadZipFile:
        print("Error: 잘못된 ZIP 파일입니다.")
        # 응답 내용 확인
        print("\n응답 내용 처음 100바이트:")
        print(response.content[:100])
    
    # ZIP 파일 삭제
    if os.path.exists('corpCode.zip'):
        os.remove('corpCode.zip')
        print("임시 ZIP 파일 삭제 완료")

except requests.exceptions.RequestException as e:
    print(f"Error: API 요청 중 오류 발생: {e}")
except Exception as e:
    print(f"Error: 예상치 못한 오류 발생: {e}") 