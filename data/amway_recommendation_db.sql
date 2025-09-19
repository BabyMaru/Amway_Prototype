-- 암웨이 뉴트리라이트 제품 추천 시스템 PostgreSQL DB 설계
-- LLM+RAG 챗봇을 위한 구조

-- 1. 제품 기본 정보 테이블
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    product_code VARCHAR(50) UNIQUE,
    category VARCHAR(50) NOT NULL, -- 건강기능식품, 일반식품, 체중조절용조제식품 등
    subcategory VARCHAR(50), -- 기초영양, 영양건강, 기능성 등
    food_type VARCHAR(100), -- 식품유형
    manufacturer VARCHAR(100),
    is_global BOOLEAN DEFAULT FALSE, -- 글로벌/로컬 구분
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 기능성 원료/성분 마스터 테이블
CREATE TABLE functional_ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    ingredient_name_kr VARCHAR(100) NOT NULL,
    ingredient_name_en VARCHAR(100),
    ingredient_type VARCHAR(50), -- 비타민, 미네랄, 식물추출물 등
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 건강 영역 마스터 테이블 (식약처 인정 기능성)
CREATE TABLE health_areas (
    area_id SERIAL PRIMARY KEY,
    area_name VARCHAR(100) NOT NULL UNIQUE,
    area_category VARCHAR(50), -- 항산화, 혈당조절, 근력증진 등
    description TEXT,
    is_kfda_approved BOOLEAN DEFAULT TRUE, -- 식약처 인정 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 제품-원료 관계 테이블
CREATE TABLE product_ingredients (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    ingredient_id INTEGER REFERENCES functional_ingredients(ingredient_id),
    amount VARCHAR(50), -- 함량 정보
    unit VARCHAR(20), -- mg, g, IU 등
    daily_value_percentage DECIMAL(5,2), -- 일일권장량 대비 %
    is_main_ingredient BOOLEAN DEFAULT FALSE, -- 주요 성분 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 제품-건강영역 관계 테이블 (식약처 인정 기능성)
CREATE TABLE product_health_functions (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    area_id INTEGER REFERENCES health_areas(area_id),
    function_description TEXT, -- 구체적인 기능성 설명
    evidence_level VARCHAR(20), -- 근거 수준
    is_primary_function BOOLEAN DEFAULT FALSE, -- 주요 기능성 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. 건강 지표 마스터 테이블 (웰니스 보고서 항목)
CREATE TABLE health_indicators (
    indicator_id SERIAL PRIMARY KEY,
    indicator_name VARCHAR(100) NOT NULL,
    indicator_category VARCHAR(50), -- 체성분, 혈액검사, 설문조사 등
    measurement_unit VARCHAR(20),
    normal_range_min DECIMAL(10,2),
    normal_range_max DECIMAL(10,2),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 건강 점수 마스터 테이블
CREATE TABLE health_scores (
    score_id SERIAL PRIMARY KEY,
    score_name VARCHAR(100) NOT NULL, -- 노화억제분석지수, 만성질환억제분석지수, 근육밸런스지수
    score_category VARCHAR(50),
    description TEXT,
    calculation_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. 건강 지표-영향 영역 관계 테이블
CREATE TABLE indicator_health_impact (
    id SERIAL PRIMARY KEY,
    indicator_id INTEGER REFERENCES health_indicators(indicator_id),
    area_id INTEGER REFERENCES health_areas(area_id),
    impact_level VARCHAR(20) NOT NULL, -- 주의, 관리
    correlation_strength DECIMAL(3,2), -- 연관성 강도 (0.0-1.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. 건강 점수-영향 영역 관계 테이블
CREATE TABLE score_health_impact (
    id SERIAL PRIMARY KEY,
    score_id INTEGER REFERENCES health_scores(score_id),
    area_id INTEGER REFERENCES health_areas(area_id),
    impact_level VARCHAR(20) NOT NULL, -- 주의, 관리
    priority_weight DECIMAL(3,2), -- 우선순위 가중치
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. 제품 상세 정보 테이블
CREATE TABLE product_details (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    intake_method TEXT, -- 섭취 방법
    precautions TEXT, -- 주의사항
    nutritional_info JSONB, -- 영양성분 정보 (JSON 형태)
    ingredients_list TEXT, -- 원재료명
    calories_per_serving DECIMAL(6,2),
    serving_size VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. 알레르기 정보 테이블
CREATE TABLE allergen_info (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    allergen_name VARCHAR(50) NOT NULL, -- 대두, 우유, 밀 등
    allergen_type VARCHAR(20), -- 함유, 혼입가능성
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. 제품 추천 규칙 테이블 (LLM 학습용)
CREATE TABLE recommendation_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    condition_type VARCHAR(50), -- 건강지표기반, 건강점수기반, 생활습관기반
    condition_criteria JSONB, -- 조건 (JSON 형태)
    recommended_products JSONB, -- 추천 제품 목록
    rule_priority INTEGER DEFAULT 1,
    rule_description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. 생활습관-영양소 매핑 테이블
CREATE TABLE lifestyle_nutrition_mapping (
    id SERIAL PRIMARY KEY,
    lifestyle_category VARCHAR(50), -- 식생활, 운동, 수면
    lifestyle_item VARCHAR(100), -- 잡곡류, 근력운동, 수면시간 등
    required_nutrients JSONB, -- 필요 영양소 목록
    recommended_products JSONB, -- 추천 제품
    nutrition_rationale TEXT, -- 추천 근거
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. 기능성 조합 분류 테이블 (7가지 기능성 조합)
CREATE TABLE functional_combinations (
    combination_id SERIAL PRIMARY KEY,
    combination_name VARCHAR(100) NOT NULL,
    antioxidant_function BOOLEAN DEFAULT FALSE,
    metabolic_function BOOLEAN DEFAULT FALSE,
    muscle_function BOOLEAN DEFAULT FALSE,
    description TEXT,
    target_health_scores JSONB, -- 대상 건강점수
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 15. 제품-기능성조합 관계 테이블
CREATE TABLE product_functional_combinations (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    combination_id INTEGER REFERENCES functional_combinations(combination_id),
    primary_mechanism TEXT, -- 주요 작용 기전
    supporting_evidence TEXT, -- 지원 근거
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. 과학적 근거 테이블 (참고문헌)
CREATE TABLE scientific_evidence (
    evidence_id SERIAL PRIMARY KEY,
    ingredient_id INTEGER REFERENCES functional_ingredients(ingredient_id),
    area_id INTEGER REFERENCES health_areas(area_id),
    study_title TEXT,
    journal_name VARCHAR(200),
    publication_year INTEGER,
    doi VARCHAR(100),
    pmid VARCHAR(20),
    study_type VARCHAR(50), -- RCT, 메타분석, 관찰연구 등
    evidence_level VARCHAR(20), -- A, B, C 등급
    key_findings TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 17. RAG용 벡터 임베딩 테이블
CREATE TABLE product_embeddings (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    content_type VARCHAR(50), -- 제품설명, 기능성, 성분 등
    content_text TEXT NOT NULL,
    embedding vector(1536), -- OpenAI embedding 차원
    metadata JSONB, -- 추가 메타데이터
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 18. 추천 로그 테이블 (학습 개선용)
CREATE TABLE recommendation_logs (
    log_id SERIAL PRIMARY KEY,
    session_id VARCHAR(100),
    user_health_data JSONB, -- 사용자 건강 데이터
    recommended_products JSONB, -- 추천된 제품들
    recommendation_reason TEXT, -- 추천 이유
    user_feedback INTEGER, -- 사용자 피드백 점수
    llm_model_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX idx_products_category ON products(category, subcategory);
CREATE INDEX idx_product_ingredients_product ON product_ingredients(product_id);
CREATE INDEX idx_product_health_functions_product ON product_health_functions(product_id);
CREATE INDEX idx_product_health_functions_area ON product_health_functions(area_id);
CREATE INDEX idx_indicator_health_impact_indicator ON indicator_health_impact(indicator_id);
CREATE INDEX idx_indicator_health_impact_area ON indicator_health_impact(area_id);
CREATE INDEX idx_score_health_impact_score ON score_health_impact(score_id);
CREATE INDEX idx_score_health_impact_area ON score_health_impact(area_id);
CREATE INDEX idx_allergen_info_product ON allergen_info(product_id);
CREATE INDEX idx_product_embeddings_product ON product_embeddings(product_id);
CREATE INDEX idx_recommendation_logs_session ON recommendation_logs(session_id);

-- 벡터 유사도 검색을 위한 인덱스 (pgvector 확장 필요)
-- CREATE EXTENSION IF NOT EXISTS vector;
-- CREATE INDEX idx_product_embeddings_vector ON product_embeddings USING ivfflat (embedding vector_cosine_ops);

-- 샘플 데이터 삽입 예시 (기본 건강 영역)
INSERT INTO health_areas (area_name, area_category) VALUES 
('항산화', '기초건강'),
('혈당 조절', '대사건강'),
('혈중 지질 개선', '대사건강'),
('혈압 조절', '심혈관건강'),
('근력(근육)', '근골격건강'),
('체지방 감소', '체중관리'),
('면역 기능', '면역건강'),
('눈 건강', '감각기관'),
('간 건강', '장기건강'),
('장 건강', '소화기건강'),
('수면 건강', '생활건강'),
('피로 개선', '에너지'),
('운동수행능력', '체력'),
('갱년기 여성 건강', '호르몬건강'),
('전립선 건강', '남성건강');

-- 건강 점수 기본 데이터
INSERT INTO health_scores (score_name, score_category, description) VALUES 
('노화 억제 분석지수', '산화스트레스', '체내 산화 스트레스 수준과 항산화 방어력을 종합 평가'),
('만성질환 억제 분석지수', '대사건강', '혈당, 지질, 혈압 등 대사 관련 지표의 종합 평가'),
('근육 밸런스 지수', '근골격건강', '근력, 근육량, 체력 등 근골격계 건강 종합 평가');

-- 기능성 조합 기본 데이터 (7가지 조합)
INSERT INTO functional_combinations (combination_name, antioxidant_function, metabolic_function, muscle_function, description) VALUES 
('항산화 중심', TRUE, FALSE, FALSE, '항산화 기능을 중심으로 하고, 대사나 근육 기능 관련 주작용이 없음'),
('대사 중심', FALSE, TRUE, FALSE, '혈당, 지방 대사, 체중 관리, 혈중 지질 등 대사 관련 기능 중심으로 작용'),
('근육 중심', FALSE, FALSE, TRUE, '근육 합성, 회복, 에너지 대사 등 근육과 체력 회복 중심'),
('항산화+대사', TRUE, TRUE, FALSE, '항산화 기능과 대사 기능이 모두 포함됨'),
('항산화+근육', TRUE, FALSE, TRUE, '항산화 기능과 근육 기능을 동시에 갖춘 제품'),
('대사+근육', FALSE, TRUE, TRUE, '대사 기능과 근육 회복을 동시에 고려한 제품'),
('종합 기능', TRUE, TRUE, TRUE, '세 가지 기능을 모두 포괄하여, 전반적인 건강 유지/활력 향상 목적의 종합 제품');