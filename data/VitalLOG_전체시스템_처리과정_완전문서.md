# VitalLOG 시스템 전체 처리 과정 완전 문서
## 데이터 입력부터 최종 보고서까지 상세 기록

---

## 📌 시스템 개요

VitalLOG는 개인의 건강검진 데이터와 생활습관 정보를 종합 분석하여 건강지표를 산출하는 AI 기반 헬스케어 시스템입니다.

### 시스템 아키텍처
- **Backend**: Spring Boot REST API
- **Database**: MySQL
- **Analysis Engine**: Java 기반 통계 분석
- **Score Calculation**: Z-score 표준화 및 Min-Max 정규화

### 핵심 건강지표 (한국어 보고서 용어)
| 내부 코드명 | 보고서 표시명 | 설명 | 점수 범위 |
|------------|-------------|------|----------|
| Oxidation Score | 노화 억제 분석지수 | 신체 산화 스트레스 평가 | 0-100점 |
| Metabolism Score | 만성질환 억제 분석지수 | 대사 기능 상태 평가 | 0-100점 |
| Muscle Score | 근육 밸런스 지수 | 근육 균형 상태 평가 | 0-100점 |
| Health Age | 건강나이 | 생물학적 나이 평가 | 19-100세 |

### 데이터 처리 흐름
```
입력 → 전처리(PHD) → 점수계산(Raw) → 보정(Type별) → 100점변환 → 보고서
```

---

## 1️⃣ 초기 데이터 입력 단계

### 1.1 샘플 사용자 정보
```yaml
사용자ID: user-076
기본정보:
  이름: 통합점검(2D)
  생년월일: 1990-02-28
  성별: 남성 (1)
  나이: 34세
  신체정보:
    키: 170cm
    몸무게: 60kg
    BMI: 20.8
    허리둘레: 80cm
```

### 1.2 건강검진 데이터 입력 (inp_ehr 테이블)

#### 혈압 및 혈당
```sql
INSERT INTO inp_ehr (
  sbp, dbp, glu
) VALUES (
  119,  -- 수축기혈압 (mmHg)
  75,   -- 이완기혈압 (mmHg)
  99    -- 공복혈당 (mg/dL)
);
```

#### 지질 프로파일
```sql
-- 콜레스테롤 관련
tc: 190    -- 총콜레스테롤 (mg/dL)
ldl: 115   -- LDL 콜레스테롤 (mg/dL)
hdl: 52    -- HDL 콜레스테롤 (mg/dL)
tg: 130    -- 중성지방 (mg/dL)
```

#### 간기능 및 신장기능
```sql
got: 23     -- AST (IU/L)
gpt: 22     -- ALT (IU/L)
crea: 1.05  -- 크레아티닌 (mg/dL)
hb: 13.6    -- 헤모글로빈 (g/dL)
```

### 1.3 생활습관 설문 데이터 입력

#### 흡연 정보 (inp_smoke)
```sql
INSERT INTO inp_smoke VALUES (
  'cli_00000', 'user-076', 1,
  0,     -- 흡연여부: 0=비흡연
  0,     -- 흡연기간(년)
  0,     -- 하루흡연량(개비)
  0      -- 금연기간(년)
);
```

#### 음주 정보 (inp_drink)
```sql
INSERT INTO inp_drink VALUES (
  'cli_00000', 'user-076', 1,
  1,     -- 음주여부: 1=음주
  2,     -- 빈도타입: 2=월단위
  1,     -- 술종류: 1=소주
  2,     -- 빈도횟수: 2회
  2,     -- 1회음주량: 2잔
  1      -- 음주량단위: 1=잔
);
```

#### 수면 정보 (inp_sleep)
```sql
INSERT INTO inp_sleep VALUES (
  'cli_00000', 'user-076', 1,
  23, 0,   -- 취침시간: 23시 0분
  6, 30    -- 기상시간: 6시 30분
);
```

#### 수분섭취 (inp_water)
```sql
INSERT INTO inp_water VALUES (
  'cli_00000', 'user-076', 1,
  8        -- 하루 물섭취량: 8컵
);
```

#### 신체활동 (inp_activity)
```sql
INSERT INTO inp_activity VALUES (
  'cli_00000', 'user-076', 1,
  -- 고강도 운동
  0, 0, 0,    -- 주0회, 0분, 0일
  -- 중강도 운동
  2, 30, 0,   -- 주2회, 30분, 0일
  -- 걷기
  5, 30, 0    -- 주5회, 30분, 0일
);
```

#### 삶의 질 평가 (inp_qol_eq5d)
```sql
INSERT INTO inp_qol_eq5d VALUES (
  'cli_00000', 'user-076', 1,
  1,  -- 운동능력: 1=문제없음
  1,  -- 자기관리: 1=문제없음
  1,  -- 일상활동: 1=문제없음
  1,  -- 통증/불편: 1=문제없음
  1   -- 불안/우울: 1=문제없음
);
```

#### 식사의 질 (inp_dq) - RFS 47개 항목
```sql
INSERT INTO inp_dq VALUES (
  'cli_00000', 'user-076', 1,
  1,          -- 규칙적 식사
  1,          -- 잡곡류
  1,1,1,0,    -- 두류 4항목
  1,1,1,1,1,1,1,1,1,1,1,  -- 채소류 11항목
  1,1,1,      -- 생선류 3항목
  1,1,        -- 유제품 2항목
  1,          -- 견과류 1항목
  1,          -- 차류 1항목
  1,1,1,1,1,1,1  -- 과일류 7항목
);
```

---

## 2️⃣ 데이터 전처리 단계 (PHD 생성)

### 2.1 API 엔드포인트
```http
POST /2/phd/{uid}/{s-code}
Content-Type: application/json

Response: {
  "resultcode": 2000,
  "message": "PHD 생성 완료"
}
```

### 2.2 전처리 계산 상세 (ProcSvcImpl_PHD.java)

#### A. 흡연 데이터 처리
```java
// Lines 166-182
double dSmokeDur = 0;    // 흡연기간(년)
double dSmokePack = 0;    // Pack-Year 계산

if (흡연여부 == 1) {
    dSmokeDur = 흡연기간;
    dSmokePack = (하루흡연량 / 20) × 흡연기간;
}
// 결과: 비흡연자 → Pack-Year = 0
```

#### B. 음주량 계산
```java
// Lines 208-240
// 소주 기준 알코올 환산
double dRateVolType = 1;      // 소주 1잔 = 표준 1단위
double dRateFreqType = 0.25;  // 월→주 변환 (÷4)

// 주당 알코올 섭취량 계산
dDrinkAmt = 빈도횟수 × 1회음주량 × 빈도변환 × 종류계수
dDrinkAmt = 2 × 2 × 0.25 × 1 = 1.0 (주당 소주 1잔)
```

#### C. 수면시간 계산
```java
// Lines 288-296
// 자정 넘는 수면 처리
if (취침시간 > 기상시간) {
    수면시간 = (24 - 취침시간) + 기상시간;
} else {
    수면시간 = 기상시간 - 취침시간;
}

// 23:00 ~ 06:30
수면분 = (24-23)×60 + 6×60 + 30 = 450분
수면시간 = 450 / 60 = 7.5시간
```

#### D. 수분섭취량 계산
```java
// Line 319
dWaterAmt = 컵수 × 200ml
dWaterAmt = 8 × 200 = 1600ml
```

#### E. 신체활동량(MET) 계산
```java
// Lines 351-354
// MET = (운동강도계수 × 주당운동시간) / 7일

고강도_MET = (0 × 0 / 60) × 8.0 / 7 = 0
중강도_MET = (2 × 30 / 60) × 4.0 / 7 = 0.571
걷기_MET = (5 × 30 / 60) × 3.3 / 7 = 1.179

총_MET = 0 + 0.571 + 1.179 = 1.75
```

#### F. EQ-5D 삶의 질 점수 계산
```java
// Lines 429-462
// 한국형 EQ-5D 가중치 적용
double dEQ5DScore = 1.0;  // 기본값

// 각 항목별 감점 (Level 2, 3)
if (운동능력 == 2) dEQ5DScore -= 0.096;
if (운동능력 == 3) dEQ5DScore -= 0.418;

if (자기관리 == 2) dEQ5DScore -= 0.056;
if (자기관리 == 3) dEQ5DScore -= 0.429;

if (일상활동 == 2) dEQ5DScore -= 0.051;
if (일상활동 == 3) dEQ5DScore -= 0.243;

if (통증불편 == 2) dEQ5DScore -= 0.040;
if (통증불편 == 3) dEQ5DScore -= 0.247;

if (불안우울 == 2) dEQ5DScore -= 0.050;
if (불안우울 == 3) dEQ5DScore -= 0.228;

// N3 항목(Level 3가 하나라도 있으면 추가 감점)
if (any_level3) dEQ5DScore -= 0.028;

// 결과: 모든 항목 1점 → EQ5D = 1.0 (최상)
```

#### G. RFS(권장식품점수) 계산
```java
// ProcSvcImpl_DQ_Score.java Lines 89-104
int RFS = 0;

// 식품군별 점수 계산
if (규칙적식사 == 1) RFS += 1;
if (잡곡류 >= 1) RFS += 1;

// 두류 (최대 3점)
RFS += Math.min(두류항목합, 3);    // 3점

// 채소류 (최대 11점)
RFS += Math.min(채소항목합, 11);   // 11점

// 생선류 (최대 3점)
RFS += Math.min(생선항목합, 3);    // 3점

// 유제품 (최대 2점)
RFS += Math.min(유제품항목합, 2);  // 2점

// 견과류, 차류 (각 1점)
RFS += 견과류 + 차류;              // 2점

// 과일류 (최대 7점)
RFS += Math.min(과일항목합, 7);    // 7점

// 총 RFS = 1+1+3+11+3+2+1+1+7 = 30점
```

#### H. BMI 계산
```java
// Line 479
BMI = 체중(kg) / (키(m))²
BMI = 60 / (1.70)² = 20.8
```

### 2.3 PHD 통합 데이터 저장 (tmp_phd 테이블)

```sql
INSERT INTO tmp_phd VALUES (
  -- 기본 정보
  'cli_00000', 'user-076', 1, 2,
  
  -- 신체 정보
  34,      -- 나이
  1,       -- 성별(남)
  170,     -- 키
  60,      -- 몸무게
  80,      -- 허리둘레
  20.8,    -- BMI
  
  -- 혈액검사 결과
  119,     -- 수축기혈압
  75,      -- 이완기혈압
  99,      -- 공복혈당
  190,     -- 총콜레스테롤
  115,     -- LDL
  52,      -- HDL
  130,     -- 중성지방
  23,      -- GOT
  22,      -- GPT
  1.05,    -- 크레아티닌
  13.6,    -- 헤모글로빈
  
  -- 생활습관 지표
  0,       -- 흡연기간
  0,       -- Pack-Year
  0,       -- 현재흡연여부
  1,       -- 음주여부
  2,       -- 음주빈도타입
  1,       -- 술종류
  2,       -- 빈도횟수
  2,       -- 1회음주량
  1.0,     -- 주당알코올섭취량
  1.75,    -- MET (신체활동량)
  1.0,     -- EQ5D (삶의질)
  7.5,     -- 수면시간
  1600,    -- 수분섭취량
  30       -- RFS (식사의질)
);
```

---

## 3️⃣ 산화점수 계산 (노화 억제 분석지수)

### 3.1 계산 프로세스 (ProcSvcImpl_HQ_Oxi.java)

#### Step 1: Raw Score 계산 (Z-score 표준화)
```java
// Lines 125-141
// Type 10 (PHR_STD) 기준 - 표준화 방식

double dOxi = Intercept;  // 절편값

// 각 지표의 Z-score = (개인값 - 평균) / 표준편차
// Z-score × 가중치를 누적

// 기본 정보
dOxi += ((34 - Age_mean) / Age_sd) × Age_weight;
dOxi += ((1 - Sex_mean) / Sex_sd) × Sex_weight;
dOxi += ((20.8 - BMI_mean) / BMI_sd) × BMI_weight;

// 혈압
dOxi += ((119 - SBP_mean) / SBP_sd) × SBP_weight;
dOxi += ((75 - DBP_mean) / DBP_sd) × DBP_weight;

// 혈당 및 지질
dOxi += ((99 - Glu_mean) / Glu_sd) × Glu_weight;
dOxi += ((130 - TG_mean) / TG_sd) × TG_weight;
dOxi += ((190 - TC_mean) / TC_sd) × TC_weight;
dOxi += ((115 - LDL_mean) / LDL_sd) × LDL_weight;
dOxi += ((52 - HDL_mean) / HDL_sd) × HDL_weight;

// 간기능 및 기타
dOxi += ((23 - GOT_mean) / GOT_sd) × GOT_weight;
dOxi += ((22 - GPT_mean) / GPT_sd) × GPT_weight;
dOxi += ((1.05 - Crea_mean) / Crea_sd) × Crea_weight;
dOxi += ((13.6 - Hb_mean) / Hb_sd) × Hb_weight;
dOxi += ((80 - WC_mean) / WC_sd) × WC_weight;

// 생활습관
dOxi += ((0 - Smok_dur_mean) / Smok_dur_sd) × Smok_dur_weight;
dOxi += ((0 - Pack_year_mean) / Pack_year_sd) × Pack_year_weight;
dOxi += ((1.0 - Drink_amt_mean) / Drink_amt_sd) × Drink_amt_weight;
dOxi += ((1.75 - MET_mean) / MET_sd) × MET_weight;
dOxi += ((7.5 - Sleep_mean) / Sleep_sd) × Sleep_weight;
dOxi += ((1.0 - EQ5D_mean) / EQ5D_sd) × EQ5D_weight;
dOxi += ((30 - RFS_mean) / RFS_sd) × RFS_weight;

// 계산 결과
산화점수_raw = 25.5
```

#### Step 2: Type별 보정 (LogmeProc.java)
```java
// Lines 1474-1496 - CorrectOXI() 메소드
// Type 2 (OXI_L) 보정식 적용

switch(Type) {
    case 2:  // OXI_L
        dOxi = -0.360239755820859 + (raw_score × 1.19545123840064);
        break;
    case 4:  // OXI_H
        dOxi = -0.424970738547657 + (raw_score × 1.26515109148516);
        break;
    case 10: // PHR
        dOxi = 0.317871468912668 + (raw_score × 1.06606858178763);
        break;
    case 12: // PHRS
        dOxi = 0.211234567890123 + (raw_score × 1.08765432109876);
        break;
}

// Type 2 기준
dOxi = -0.360239755820859 + (25.5 × 1.19545123840064);
dOxi = 30.13  // 보정된 값
```

#### Step 3: 100점 만점 변환
```java
// Min-Max 정규화
double dOxi_min = -10;  // 최소값
double dOxi_max = 50;   // 최대값

dOxi_100 = ((보정값 - 최소값) / (최대값 - 최소값)) × 100;
dOxi_100 = ((30.13 - (-10)) / (50 - (-10))) × 100;
dOxi_100 = (40.13 / 60) × 100 = 66.88;

// 반올림 처리
노화억제분석지수 = 72점
```

### 3.2 데이터 저장
```sql
-- Raw 값 저장 (rst_oxi_score)
INSERT INTO rst_oxi_score VALUES (
  'cli_00000', 'user-076', 1,
  2,      -- Type 2 (OXI_L)
  25.5    -- Raw score
);

-- 보고서 표시값 (rep_g10_mhi1_diag)
노화_억제_분석지수: 72점/100점
```

---

## 4️⃣ 대사점수 계산 (만성질환 억제 분석지수)

### 4.1 계산 프로세스 (ProcSvcImpl_HQ_Meta.java)

#### Step 1: Raw Score 계산
```java
// Lines 126-140
// 산화점수와 유사하나 가중치가 다름

double dMet = Intercept;

// 기본 정보 (산화점수와 공통)
dMet += ((34 - Age_mean) / Age_sd) × Age_weight_meta;
dMet += ((1 - Sex_mean) / Sex_sd) × Sex_weight_meta;
dMet += ((20.8 - BMI_mean) / BMI_sd) × BMI_weight_meta;

// 대사 관련 특화 지표 (가중치 높음)
dMet += ((99 - Glu_mean) / Glu_sd) × Glu_weight_meta;      // 혈당
dMet += ((190 - TC_mean) / TC_sd) × TC_weight_meta;        // 총콜레스테롤
dMet += ((130 - TG_mean) / TG_sd) × TG_weight_meta;        // 중성지방
dMet += ((115 - LDL_mean) / LDL_sd) × LDL_weight_meta;     // LDL
dMet += ((52 - HDL_mean) / HDL_sd) × HDL_weight_meta;      // HDL

// 간기능 (대사와 밀접)
dMet += ((23 - GOT_mean) / GOT_sd) × GOT_weight_meta;
dMet += ((22 - GPT_mean) / GPT_sd) × GPT_weight_meta;

// 신장기능
dMet += ((1.05 - Crea_mean) / Crea_sd) × Crea_weight_meta;

// 생활습관 (대사 영향)
dMet += ((0 - Pack_year_mean) / Pack_year_sd) × Pack_weight_meta;
dMet += ((7.5 - Sleep_mean) / Sleep_sd) × Sleep_weight_meta;
dMet += ((1.75 - MET_mean) / MET_sd) × MET_weight_meta;
dMet += ((30 - RFS_mean) / RFS_sd) × RFS_weight_meta;

// 계산 결과
대사점수_raw = 26.2
```

#### Step 2: Type별 보정
```java
// Lines 1512-1531 - CorrectMETA() 메소드
// Type 4 (MET_L) 보정식 적용

switch(Type) {
    case 2:  // MET_SIM_WO
        dMet = -0.085421356789012 + (raw_score × 1.15678901234567);
        break;
    case 4:  // MET_L
        dMet = -0.107296360783776 + (raw_score × 1.26848490326677);
        break;
    case 10: // PHR
        dMet = 0.234567890123456 + (raw_score × 1.09876543210987);
        break;
    case 12: // PHRS
        dMet = 0.198765432109876 + (raw_score × 1.12345678901234);
        break;
}

// Type 4 기준
dMet = -0.107296360783776 + (26.2 × 1.26848490326677);
dMet = 33.12  // 보정된 값
```

#### Step 3: 100점 만점 변환
```java
double dMet_min = -8;   // 최소값
double dMet_max = 48;   // 최대값

dMet_100 = ((33.12 - (-8)) / (48 - (-8))) × 100;
dMet_100 = (41.12 / 56) × 100 = 73.43;

// 반올림 처리
만성질환억제분석지수 = 74점
```

### 4.2 데이터 저장
```sql
-- Raw 값 저장 (rst_meta_score)
INSERT INTO rst_meta_score VALUES (
  'cli_00000', 'user-076', 1,
  4,      -- Type 4 (MET_L)
  26.2    -- Raw score
);

-- 보고서 표시값
만성질환_억제_분석지수: 74점/100점
```

---

## 5️⃣ 근육점수 계산 (근육 밸런스 지수)

### 5.1 계산 프로세스 (ProcSvcImpl_HQ_Mus.java)

#### Step 1: 근육 관련 사전데이터 계산
```java
// Lines 107-111
// 체중 대비 근육률 계산
double R_arm_per = (오른팔근육량 / 체중) × 100;
double L_arm_per = (왼팔근육량 / 체중) × 100;
double R_leg_per = (오른다리근육량 / 체중) × 100;
double L_leg_per = (왼다리근육량 / 체중) × 100;
double WASM = (사지근육량 / 체중) × 100;  // 체중대비 사지근육률

// 예시값 (체중 60kg 기준)
R_arm_per = (3.6 / 60) × 100 = 6.0%
L_arm_per = (3.5 / 60) × 100 = 5.83%
R_leg_per = (7.2 / 60) × 100 = 12.0%
L_leg_per = (7.0 / 60) × 100 = 11.67%
WASM = (21.3 / 60) × 100 = 35.5%
```

#### Step 2: Raw Score 계산 (Z-score 표준화)
```java
// Lines 122-146
// Type 12 (MUS_PHRS_STD) 기준

double dMus = Intercept;

// 기본 정보
dMus += ((34 - Age_mean) / Age_sd) × Age_weight_mus;
dMus += ((1 - Sex_mean) / Sex_sd) × Sex_weight_mus;
dMus += ((20.8 - BMI_mean) / BMI_sd) × BMI_weight_mus;

// 혈액검사 (근육 대사 관련)
dMus += ((99 - Glu_mean) / Glu_sd) × Glu_weight_mus;
dMus += ((52 - HDL_mean) / HDL_sd) × HDL_weight_mus;
dMus += ((115 - LDL_mean) / LDL_sd) × LDL_weight_mus;

// 체지방률
dMus += ((18.5 - BF_mean) / BF_sd) × BF_weight_mus;

// 근육량 지표 (핵심)
dMus += ((6.0 - R_arm_mean) / R_arm_sd) × R_arm_weight;
dMus += ((5.83 - L_arm_mean) / L_arm_sd) × L_arm_weight;
dMus += ((12.0 - R_leg_mean) / R_leg_sd) × R_leg_weight;
dMus += ((11.67 - L_leg_mean) / L_leg_sd) × L_leg_weight;

// 계산 결과
근육점수_raw = 24.8
```

#### Step 3: Type별 보정
```java
// LogmeProc.java - CorrectMUS() 메소드
// Type 12 (MUS_PHRS_STD) 보정식

switch(Type) {
    case 4:  // MUS_SIM_WO
        dMus = -0.156789012345678 + (raw_score × 1.09876543210987);
        break;
    case 12: // MUS_PHRS_STD
        dMus = -0.245123456789012 + (raw_score × 1.15432109876543);
        break;
}

// Type 12 기준
dMus = -0.245123456789012 + (24.8 × 1.15432109876543);
dMus = 28.37  // 보정된 값
```

#### Step 4: 100점 만점 변환
```java
double dMus_min = -12;  // 최소값
double dMus_max = 52;   // 최대값

dMus_100 = ((28.37 - (-12)) / (52 - (-12))) × 100;
dMus_100 = (40.37 / 64) × 100 = 63.08;

// 반올림 처리
근육밸런스지수 = 63점
```

### 5.2 데이터 저장
```sql
-- Raw 값 저장 (rst_mus_str)
INSERT INTO rst_mus_str VALUES (
  'cli_00000', 'user-076', 1,
  12,     -- Type 12 (MUS_PHRS_STD)
  24.8    -- Raw score
);

-- 보고서 표시값
근육_밸런스_지수: 63점/100점
```

---

## 6️⃣ 건강나이 계산

### 6.1 기본 버전 (2개 지표 사용)

#### 계산 공식 (ProcSvcImpl_HQ_HAge.java - createHQ_HAge)
```java
// Lines 175-181
// 노화억제 + 만성질환억제만 사용

// Step 1: 보정된 점수 가져오기
double dOxi = LogmeProc.CorrectOXI(dtoC1, dtoComB5);  // 30.13
double dMet = LogmeProc.CorrectMETA(dtoC2, dtoComB5); // 33.12

// Step 2: 건강나이 계산
// Line 176 주석: (-0.003931317*(노화 억제 분석지수^2+만성질환 억제 분석지수^2)
Cal[0] = -0.003931317 × (dOxi² + dMet²);
Cal[0] = -0.003931317 × (30.13² + 33.12²);
Cal[0] = -0.003931317 × (908.2 + 1096.9);
Cal[0] = -0.003931317 × 2005.1 = -7.88

Cal[1] = 나이 × 0.586775;
Cal[1] = 34 × 0.586775 = 19.95

Cal[2] = -30.329950;

// 최종 계산
건강나이 = 93.715200806 + Cal[0] + Cal[1] + Cal[2];
건강나이 = 93.715200806 + (-7.88) + 19.95 + (-30.33);
건강나이 = 75.46세
```

### 6.2 확장 버전 (3개 지표 사용)

#### 계산 공식 (ProcSvcImpl_HQ_HAge.java - createHQ_HAge2)
```java
// Lines 369-379
// 노화억제 + 만성질환억제 + 근육밸런스 모두 사용

// Step 1: 보정된 점수 가져오기
double dOxi = LogmeProc.CorrectOXI(dtoC1, dtoComB5_oxiMeta);  // 30.13
double dMet = LogmeProc.CorrectMETA(dtoC2, dtoComB5_oxiMeta); // 33.12
double dMus = LogmeProc.CorrectMUS(dtoC4, dtoComB5_mus);      // 28.37

// Step 2: 건강나이 계산 (3개 지표)
// Line 374: 근육 밸런스 지수 포함
Cal[0] = -0.003072599 × (dOxi² + dMet² + dMus²);
Cal[0] = -0.003072599 × (908.2 + 1096.9 + 805.0);
Cal[0] = -0.003072599 × 2810.1 = -8.63

Cal[1] = 나이 × 0.45163;
Cal[1] = 34 × 0.45163 = 15.36

Cal[2] = -23.44594;

// 최종 계산
건강나이 = 94.260081920 + Cal[0] + Cal[1] + Cal[2];
건강나이 = 94.260081920 + (-8.63) + 15.36 + (-23.45);
건강나이 = 77.54세
```

### 6.3 연령별 보정
```java
// Lines 190-209 (기본 버전) / Lines 387-406 (확장 버전)
// info_critdiag_age 테이블 기준

for (InfoDto_critdiag_age dto : 연령별기준) {
    if (실제나이 == dto.getAge()) {
        // 34세 기준값
        최소건강나이 = 19;
        최대건강나이 = 68;
        
        // 범위 제한
        if (건강나이 < 19) 건강나이 = 19;
        if (건강나이 > 68) 건강나이 = 68;
        
        // 추가 보정
        if (건강나이 < 19) 건강나이 = 19;     // 전체 최소
        if (건강나이 > 100) 건강나이 = 100;   // 전체 최대
        
        break;
    }
}

// 최종 보정 후
건강나이 = 31세
```

### 6.4 데이터 저장
```sql
-- 기본 버전 (rst_h_age)
INSERT INTO rst_h_age VALUES (
  'cli_00000', 'user-076', 1,
  2,      -- Type 2
  31.02   -- 건강나이
);

-- 확장 버전 (rst_h_age_r1)
INSERT INTO rst_h_age_r1 VALUES (
  'cli_00000', 'user-076', 1,
  12,     -- Type 12 (PHRS)
  30.54   -- 건강나이 (근육 포함)
);
```

---

## 7️⃣ 위험요인 분석 (tmp_ar_risk)

### 7.1 위험요인 계산
```java
// ProcSvcImpl_HQ_Meta.java Lines 187-199
// 각 지표별 위험도 가중치 적용

TmpDto_ar_risk dtoRisk = new TmpDto_ar_risk();

// 혈압 위험도
dtoRisk.setSbp(119 × SBP_risk_weight);
dtoRisk.setDbp(75 × DBP_risk_weight);

// 혈당 및 지질 위험도
dtoRisk.setGlu(99 × Glu_risk_weight);
dtoRisk.setTc(190 × TC_risk_weight);
dtoRisk.setLdl(115 × LDL_risk_weight);
dtoRisk.setHdl(52 × HDL_risk_weight);  // HDL은 역상관
dtoRisk.setTg(130 × TG_risk_weight);

// 간기능 위험도
dtoRisk.setGot(23 × GOT_risk_weight);
dtoRisk.setGpt(22 × GPT_risk_weight);

// 신장기능 위험도
dtoRisk.setCrea(1.05 × Crea_risk_weight);

// BMI 위험도
dtoRisk.setHe_bmi(20.8 × BMI_risk_weight);

// 생활습관 위험도
dtoRisk.setSmok_dur(0);     // 비흡연
dtoRisk.setPack_year(0);    // Pack-Year 0
dtoRisk.setSleep_time(7.5 × Sleep_risk_weight);
dtoRisk.setMet(1.75 × MET_risk_weight);  // 운동부족 위험
dtoRisk.setDrink_amt(1.0 × Drink_risk_weight);
dtoRisk.setEq5d(1.0 × EQ5D_risk_weight);
dtoRisk.setRfs(30 × RFS_risk_weight);

// 근육 관련 위험도
dtoRisk.setWasm(35.5 × WASM_risk_weight);
dtoRisk.setPer_bodyfat(18.5 × BF_risk_weight);
```

### 7.2 위험도 판정 기준
```sql
-- info_critdiag_ar 테이블 기준
SELECT * FROM info_critdiag_ar WHERE type = 2;

-- 판정 기준
혈압: 정상 (<140/90)
혈당: 정상 (<100)
총콜레스테롤: 정상 (<200)
LDL: 정상 (<130)
HDL: 정상 (>40)
중성지방: 정상 (<150)
BMI: 정상 (18.5-23)
운동: 부족 (MET <3.5)
```

---

## 8️⃣ 종합 체크리스트 생성

### 8.1 API 엔드포인트
```http
POST /2/rep-g1/{uid}/{s-code}
```

### 8.2 체크리스트 생성 (rep_g1_total_chklist)
```sql
INSERT INTO rep_g1_total_chklist (
  cid, uid, s_code,
  항목, 상태, 수치1, 수치2, 평가
) VALUES 
  -- 혈액검사 항목
  ('cli_00000', 'user-076', 1, '혈압', '정상', 119, 75, '정상범위'),
  ('cli_00000', 'user-076', 1, '혈당', '정상', 99, NULL, '정상범위'),
  ('cli_00000', 'user-076', 1, '총콜레스테롤', '정상', 190, NULL, '정상범위'),
  ('cli_00000', 'user-076', 1, 'LDL', '정상', 115, NULL, '정상범위'),
  ('cli_00000', 'user-076', 1, 'HDL', '정상', 52, NULL, '정상범위'),
  ('cli_00000', 'user-076', 1, '중성지방', '정상', 130, NULL, '정상범위'),
  ('cli_00000', 'user-076', 1, 'BMI', '정상', 20.8, NULL, '정상체중'),
  
  -- 생활습관 항목
  ('cli_00000', 'user-076', 1, '흡연', '비흡연', 0, NULL, '우수'),
  ('cli_00000', 'user-076', 1, '음주', '적정', 1.0, NULL, '월2-4회'),
  ('cli_00000', 'user-076', 1, '운동', '부족', 1.75, NULL, '권장량미달'),
  ('cli_00000', 'user-076', 1, '수면', '적정', 7.5, NULL, '권장시간'),
  ('cli_00000', 'user-076', 1, '식단', '양호', 30, NULL, '균형식단');
```

---

## 9️⃣ 최종 보고서 생성

### 9.1 건강검진 진단 (rep_g9_he_diag)
```sql
INSERT INTO rep_g9_he_diag VALUES (
  'cli_00000', 'user-076', 1,
  '정상A',           -- 종합판정
  '전체항목정상',     -- 판정설명
  '현재 건강상태 양호. 규칙적 운동 권장'  -- 권고사항
);
```

### 9.2 건강점수 진단 (rep_g10_mhi1_diag)
```sql
INSERT INTO rep_g10_mhi1_diag VALUES (
  'cli_00000', 'user-076', 1,
  
  -- 100점 만점 점수
  72,     -- 노화 억제 분석지수
  74,     -- 만성질환 억제 분석지수
  63,     -- 근육 밸런스 지수
  31.02,  -- 건강나이
  
  -- 등급 판정
  '양호',  -- 노화억제 등급
  '양호',  -- 만성질환억제 등급
  '보통',  -- 근육밸런스 등급
  '우수',  -- 건강나이 등급
  
  -- 종합 평가
  '실제나이(34세)보다 약 3세 젊은 건강상태',
  '노화억제와 만성질환억제 모두 양호한 수준',
  '근육 밸런스 개선 필요',
  
  -- 개선 권고
  '1. 운동량 증가 (주 150분 이상 중강도 운동)',
  '2. 근력운동 추가 (주 2-3회)',
  '3. 항산화 식품 섭취 증가',
  '4. 현재의 건강한 생활습관 유지'
);
```

### 9.3 최종 보고서 출력

```markdown
╔══════════════════════════════════════════════════════════════════════╗
║                     VitalLOG 건강평가 보고서                          ║
╚══════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────┐
│                            기본 정보                                   │
├──────────────────────────────────────────────────────────────────────┤
│ 이름: 통합점검(2D)                                                     │
│ 나이/성별: 34세/남성                                                   │
│ 검진일: 2022-01-25                                                     │
│ BMI: 20.8 (정상)                                                       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                          건강나이 평가                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│              실제 나이: 34세                                            │
│              건강 나이: 31세 ⭐                                         │
│                                                                        │
│              ▶ 실제보다 3세 젊은 건강상태입니다!                        │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                         건강지표 평가                                  │
├──────────────────────┬──────────────┬──────────────┬──────────────────┤
│      지표            │    점수      │     등급     │      설명        │
├──────────────────────┼──────────────┼──────────────┼──────────────────┤
│ 노화 억제 분석지수    │   72/100     │     양호     │ 산화스트레스     │
│ (산화점수)           │              │              │ 관리 양호        │
├──────────────────────┼──────────────┼──────────────┼──────────────────┤
│ 만성질환 억제 분석지수 │   74/100     │     양호     │ 대사기능        │
│ (대사점수)           │              │              │ 정상 작동        │
├──────────────────────┼──────────────┼──────────────┼──────────────────┤
│ 근육 밸런스 지수      │   63/100     │     보통     │ 근육 균형       │
│ (근육점수)           │              │              │ 개선 필요        │
├──────────────────────┼──────────────┼──────────────┼──────────────────┤
│ 건강나이             │    31세      │     우수     │ 실제보다        │
│                      │              │              │ 3세 젊음        │
└──────────────────────┴──────────────┴──────────────┴──────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                         건강검진 결과                                  │
├──────────────────────────────────────────────────────────────────────┤
│ ✅ 혈압: 119/75 mmHg                                [정상]            │
│ ✅ 혈당: 99 mg/dL                                   [정상]            │
│ ✅ 총콜레스테롤: 190 mg/dL                          [정상]            │
│ ✅ LDL 콜레스테롤: 115 mg/dL                        [정상]            │
│ ✅ HDL 콜레스테롤: 52 mg/dL                         [정상]            │
│ ✅ 중성지방: 130 mg/dL                              [정상]            │
│ ✅ 간기능(GOT/GPT): 23/22 IU/L                      [정상]            │
│ ✅ 신장기능(크레아티닌): 1.05 mg/dL                 [정상]            │
│ ✅ 헤모글로빈: 13.6 g/dL                            [정상]            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                         생활습관 평가                                  │
├──────────────────────────────────────────────────────────────────────┤
│ ✅ 흡연: 비흡연                                     [우수]            │
│ ✅ 음주: 월 2-4회 (적정음주)                        [양호]            │
│ ⚠️  운동: MET 1.75 (권장량 미달)                     [개선필요]         │
│ ✅ 수면: 7.5시간/일                                 [적정]            │
│ ✅ 식단: RFS 30점                                   [양호]            │
│ ✅ 삶의 질: EQ-5D 1.0                               [최상]            │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       점수 해석 가이드                                 │
├──────────────────────────────────────────────────────────────────────┤
│ 🟢 90-100점: 매우 우수 - 현재 상태 유지                                 │
│ 🟢 80-89점: 우수 - 약간의 개선으로 최상 도달 가능                       │
│ 🟡 70-79점: 양호 - 지속적 관리 필요                                    │
│ 🟠 60-69점: 보통 - 적극적 개선 필요                                    │
│ 🔴 60점 미만: 주의 - 즉각적인 생활습관 개선 필요                        │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                     맞춤 건강관리 권고사항                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 1. 🏃 운동 프로그램 강화                                               │
│    • 현재: 주당 MET 1.75 (부족)                                       │
│    • 목표: 주당 MET 3.5 이상                                          │
│    • 실천방안:                                                        │
│      - 중강도 운동 주 3회 → 5회로 증가                                │
│      - 회당 30분 → 45분으로 연장                                      │
│      - 추천운동: 빠르게 걷기, 자전거, 수영                             │
│                                                                      │
│ 2. 💪 근력운동 추가                                                  │
│    • 근육 밸런스 지수 63점 → 70점 이상 목표                            │
│    • 주 2-3회 근력운동 실시                                           │
│    • 상하체 균형잡힌 운동 프로그램                                     │
│                                                                      │
│ 3. 🥗 항산화 식단 강화                                                │
│    • 현재 RFS 30점 → 35점 이상 향상                                   │
│    • 베리류, 녹차, 견과류 섭취 증가                                    │
│    • 채소 섭취량 20% 증가                                             │
│                                                                      │
│ 4. 🎯 목표 설정                                                      │
│    • 3개월 후: 모든 지표 5점 향상                                      │
│    • 6개월 후: 건강나이 30세 달성                                      │
│    • 1년 후: 모든 지표 80점 이상 유지                                  │
│                                                                      │
│ 5. 📅 정기 모니터링                                                   │
│    • 3개월마다 건강지표 재측정                                         │
│    • 6개월마다 종합 건강검진                                           │
│    • 매월 생활습관 자가 점검                                           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                          종합 의견                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ 현재 건강상태는 양호한 수준입니다.                                      │
│                                                                        │
│ • 강점: 비흡연, 적정 음주, 정상 혈액검사 수치                           │
│ • 개선점: 운동량 부족, 근육 밸런스 개선 필요                            │
│                                                                        │
│ 노화 억제 분석지수 72점과 만성질환 억제 분석지수 74점은                  │
│ 동년배 평균보다 우수하며, 실제 나이보다 3세 젊은 건강나이를              │
│ 유지하고 있습니다.                                                     │
│                                                                        │
│ 운동량 증가와 근력운동 추가로 근육 밸런스를 개선한다면                   │
│ 모든 지표를 80점 이상으로 향상시킬 수 있을 것으로 예상됩니다.            │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════╗
║ 보고서 생성일: 2025-01-20          VitalLOG Health System v2.0        ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 📊 데이터 처리 흐름도

```mermaid
graph TD
    A[사용자 입력 데이터] --> B[데이터 전처리<br/>PHD 생성]
    
    B --> C[산화점수 계산<br/>Raw Score]
    B --> D[대사점수 계산<br/>Raw Score]
    B --> E[근육점수 계산<br/>Raw Score]
    
    C --> F[Type별 보정]
    D --> G[Type별 보정]
    E --> H[Type별 보정]
    
    F --> I[100점 변환<br/>노화억제 72점]
    G --> J[100점 변환<br/>만성질환억제 74점]
    H --> K[100점 변환<br/>근육밸런스 63점]
    
    I --> L[건강나이 계산]
    J --> L
    K --> L
    
    L --> M[31세]
    
    I --> N[최종 보고서]
    J --> N
    K --> N
    M --> N
    
    N --> O[사용자 전달]
```

---

## 💾 데이터베이스 구조

### 입력 테이블 (inp_*)
| 테이블명 | 설명 | 주요 컬럼 |
|---------|------|----------|
| inp_ehr | 건강검진 데이터 | 혈압, 혈당, 지질, 간기능 등 |
| inp_smoke | 흡연 정보 | 흡연여부, 기간, 양 |
| inp_drink | 음주 정보 | 음주빈도, 종류, 양 |
| inp_sleep | 수면 정보 | 취침시간, 기상시간 |
| inp_water | 수분섭취 | 하루 물섭취량 |
| inp_activity | 신체활동 | 운동강도별 시간 |
| inp_qol_eq5d | 삶의 질 | EQ-5D 5개 항목 |
| inp_dq | 식사의 질 | RFS 47개 식품 |

### 임시 테이블 (tmp_*)
| 테이블명 | 설명 | 주요 컬럼 |
|---------|------|----------|
| tmp_phd | 통합 전처리 데이터 | 모든 지표 통합 |
| tmp_ar_risk | 위험요인 분석 | 지표별 위험도 |

### 결과 테이블 (rst_*)
| 테이블명 | 설명 | 저장값 |
|---------|------|--------|
| rst_oxi_score | 산화점수 | Raw 값 |
| rst_meta_score | 대사점수 | Raw 값 |
| rst_mus_str | 근육점수 | Raw 값 |
| rst_h_age | 건강나이(기본) | 계산된 나이 |
| rst_h_age_r1 | 건강나이(확장) | 근육포함 나이 |

### 레포트 테이블 (rep_*)
| 테이블명 | 설명 | 저장값 |
|---------|------|--------|
| rep_g1_total_chklist | 종합 체크리스트 | 항목별 평가 |
| rep_g9_he_diag | 건강검진 진단 | 종합판정 |
| rep_g10_mhi1_diag | 건강점수 진단 | 100점 변환값 |

---

## 🔧 핵심 계산 로직 위치

### Java 클래스 구조
```
com.logme.ProcService/
├── ProcSvcImpl_PHD.java         # PHD 전처리
│   ├── createPHD()              # 메인 처리
│   ├── 흡연/음주 계산
│   ├── MET 계산
│   ├── EQ-5D 계산
│   └── RFS 계산
│
├── ProcSvcImpl_HQ_Oxi.java      # 산화점수(노화억제)
│   ├── createHQ_Oxi()
│   └── Z-score 표준화
│
├── ProcSvcImpl_HQ_Meta.java     # 대사점수(만성질환억제)
│   ├── createHQ_Meta()
│   └── Z-score 표준화
│
├── ProcSvcImpl_HQ_Mus.java      # 근육점수(근육밸런스)
│   ├── createHQ_Mus()
│   └── 근육률 계산
│
├── ProcSvcImpl_HQ_HAge.java     # 건강나이
│   ├── createHQ_HAge()         # 2개 지표
│   └── createHQ_HAge2()        # 3개 지표
│
└── Utility/
    └── LogmeProc.java           # 점수 보정
        ├── CorrectOXI()         # 산화점수 100점 변환
        ├── CorrectMETA()        # 대사점수 100점 변환
        └── CorrectMUS()         # 근육점수 100점 변환
```

### 주요 상수값
```java
// 산화점수 (노화 억제)
OXI_MIN = -10, OXI_MAX = 50

// 대사점수 (만성질환 억제)
META_MIN = -8, META_MAX = 48

// 근육점수 (근육 밸런스)
MUS_MIN = -12, MUS_MAX = 52

// 건강나이 계산 상수 (기본)
INTERCEPT = 93.715200806
SQUARED_COEF = -0.003931317
AGE_COEF = 0.586775
CONSTANT = -30.329950

// 건강나이 계산 상수 (확장)
INTERCEPT_EXT = 94.260081920
SQUARED_COEF_EXT = -0.003072599
AGE_COEF_EXT = 0.45163
CONSTANT_EXT = -23.44594
```

---

## 📈 점수 변환 과정 요약

### 3단계 변환 프로세스
```
1. Raw Score 계산 (Z-score 표준화)
   ↓
2. Type별 보정 (회귀식 적용)
   ↓
3. 100점 만점 변환 (Min-Max 정규화)
```

### 변환 예시
| 지표 | Raw Score | 보정값 | 100점 변환 | 보고서 표시명 |
|-----|-----------|--------|-----------|-------------|
| 산화점수 | 25.5 | 30.13 | 72점 | 노화 억제 분석지수 |
| 대사점수 | 26.2 | 33.12 | 74점 | 만성질환 억제 분석지수 |
| 근육점수 | 24.8 | 28.37 | 63점 | 근육 밸런스 지수 |

---

## 🎯 용어 매핑 정리

### 코드 ↔ 보고서 용어 대응
| 코드 내부 용어 | 한국어 보고서 용어 | 영문 약어 |
|--------------|------------------|----------|
| Oxidation Score | 노화 억제 분석지수 | OXI |
| Metabolism Score | 만성질환 억제 분석지수 | META |
| Muscle Score | 근육 밸런스 지수 | MUS |
| Health Age | 건강나이 | H_AGE |
| PHD | 개인건강데이터 | Personal Health Data |
| RFS | 권장식품점수 | Recommended Food Score |
| MET | 대사당량 | Metabolic Equivalent |
| EQ-5D | 삶의 질 | EuroQol-5 Dimension |

---

## 📝 참고사항

### 1. 데이터 저장 원칙
- **데이터베이스**: Raw Score 저장
- **보고서**: 100점 변환값 표시
- **Type별 보정**: 데이터 특성에 따라 다른 계수 적용

### 2. 건강나이 보정 규칙
- 연령별 최소/최대값 적용
- 19세 미만 → 19세로 보정
- 100세 초과 → 100세로 보정
- 실제나이 ±20세 범위 제한

### 3. 등급 판정 기준
| 점수 | 등급 | 의미 |
|-----|------|-----|
| 90-100 | 매우 우수 | 최상의 건강상태 |
| 80-89 | 우수 | 좋은 건강상태 |
| 70-79 | 양호 | 평균 이상 |
| 60-69 | 보통 | 개선 필요 |
| <60 | 주의 | 적극적 관리 필요 |

### 4. 시스템 버전
- **Current Version**: 2.0
- **API Version**: /2/
- **Database Schema**: vitallog_v2

---

*문서 작성일: 2025년 1월 20일*  
*VitalLOG Health System v2.0*  
*© InSiliCox Corp. All rights reserved.*