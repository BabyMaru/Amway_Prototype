-- 분류기준 테이블에 원료 컬럼 추가
ALTER TABLE "분류기준" ADD COLUMN IF NOT EXISTS "원료" TEXT;

-- 원료 컬럼에 대한 설명 추가
COMMENT ON COLUMN "분류기준"."원료" IS '제품의 주요 기능성 원료 정보';

-- 인덱스 추가 (검색 성능 향상)
CREATE INDEX IF NOT EXISTS idx_classification_ingredient ON "분류기준"("원료");