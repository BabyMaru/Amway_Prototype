#!/usr/bin/env python3
"""
분류기준 테이블에 원료 컬럼을 추가하는 스크립트
"""

import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 데이터베이스 연결 설정
DB_CONFIG = {
    'dbname': 'Amway_DB',
    'user': 'postgres',
    'password': '990910',
    'host': 'localhost',
    'port': '5432'
}

def add_ingredient_column():
    """분류기준 테이블에 원료 컬럼 추가"""
    try:
        # 데이터베이스 연결
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("데이터베이스에 연결되었습니다.")
        
        # 원료 컬럼 추가 (이미 존재하면 무시)
        add_column_query = '''
        ALTER TABLE "분류기준" 
        ADD COLUMN IF NOT EXISTS "원료" TEXT;
        '''
        
        cur.execute(add_column_query)
        print("원료 컬럼이 추가되었습니다.")
        
        # 컬럼에 대한 설명 추가
        comment_query = '''
        COMMENT ON COLUMN "분류기준"."원료" IS '제품의 주요 기능성 원료 정보';
        '''
        
        cur.execute(comment_query)
        print("컬럼 설명이 추가되었습니다.")
        
        # 인덱스 추가 (검색 성능 향상)
        index_query = '''
        CREATE INDEX IF NOT EXISTS idx_classification_ingredient 
        ON "분류기준"("원료");
        '''
        
        cur.execute(index_query)
        print("인덱스가 추가되었습니다.")
        
        # 변경사항 커밋
        conn.commit()
        print("✅ 분류기준 테이블에 원료 컬럼이 성공적으로 추가되었습니다!")
        
        # 테이블 구조 확인
        cur.execute('''
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = '분류기준' 
        ORDER BY ordinal_position;
        ''')
        
        columns = cur.fetchall()
        print("\n📋 현재 분류기준 테이블 구조:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]}) {'NULL 허용' if col[2] == 'YES' else 'NOT NULL'}")
        
    except psycopg2.Error as e:
        print(f"❌ 데이터베이스 오류: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"❌ 일반 오류: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
        print("데이터베이스 연결이 종료되었습니다.")

if __name__ == "__main__":
    add_ingredient_column()