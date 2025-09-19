import pandas as pd
from sqlalchemy import create_engine

# DB 연결 정보 입력
db_user = 'postgres'           # 기본 사용자
db_password = '990910'  # 설치 시 지정한 비번
db_host = 'localhost'
db_port = '5432'
db_name = 'Amway_DB'          # 아까 만든 DB 이름

# SQLAlchemy 연결 객체 생성
engine = create_engine(f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

# 엑셀 파일 경로 설정
excel_path = 'Amway_AIsolution_DB.xlsx'
xlsx = pd.ExcelFile(excel_path)

# 각 시트를 테이블로 변환
for sheet in xlsx.sheet_names:
    df = pd.read_excel(xlsx, sheet_name=sheet)
    table_name = sheet.strip().lower()
    df.to_sql(table_name, con=engine, if_exists='replace', index=False)
    print(f"테이블 생성 완료: {table_name}")