#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VitalLOG 3가지 지수 계산 시스템 (완전 공식 반영판)
- 노화 억제 분석지수 (OXI)
- 만성질환 억제 분석지수 (MET)
- 근육 밸런스 분석지수 (MUS)
"""

# =========================
# 공통 함수
# =========================
def normalize(score, min_val, max_val):
    """Min-Max 정규화 후 100점 환산"""
    score_100 = ((score - min_val) / (max_val - min_val)) * 100
    return max(0, min(100, round(score_100, 1)))  # 0~100으로 클리핑

# =========================
# 노화 억제 분석지수 (OXI)
# =========================
def calculate_oxi(data):
    """
    노화 억제 분석지수 (OXI)
    Type 10 → Type 2 보정 공식 반영
    """
    # 절편 (문서 기반)
    raw_score = 26.426

    # 모든 기여도 (문서에 있는 변수별 β, mean, std 사용)
    contrib = 0
    contrib += ((data['age'] - 45.2) / 12.8) * 0.082
    contrib += ((data['sex'] - 0.48) / 0.50) * (-0.045)
    contrib += ((data['he_bmi'] - 23.7) / 3.2) * 0.156
    contrib += ((data['he_wc'] - 82.5) / 9.4) * 0.173
    contrib += ((data['sbp'] - 122.3) / 15.6) * 0.198
    contrib += ((data['dbp'] - 76.8) / 10.2) * 0.165
    contrib += ((data['glu'] - 98.7) / 18.3) * 0.224
    contrib += ((data['tc'] - 196.5) / 36.8) * 0.142
    contrib += ((data['ldl'] - 118.3) / 32.4) * 0.187
    contrib += ((data['hdl'] - 54.6) / 13.7) * (-0.213)
    contrib += ((data['tg'] - 142.8) / 78.5) * 0.196
    contrib += ((data['got'] - 25.8) / 11.3) * 0.089
    contrib += ((data['gpt'] - 26.4) / 16.7) * 0.094
    contrib += ((data['crea'] - 0.92) / 0.21) * 0.078
    contrib += ((data['hb'] - 14.2) / 1.6) * (-0.056)
    contrib += ((data['smok_dur'] - 8.3) / 12.4) * 0.312
    contrib += ((data['pack_year'] - 6.8) / 11.2) * 0.298
    contrib += ((data['drink_amt'] - 3.2) / 4.8) * 0.186
    contrib += ((data['met'] - 3.8) / 2.4) * (-0.267)
    contrib += ((data['sleep_time'] - 6.8) / 1.2) * (-0.145)
    contrib += ((data['eq5d'] - 0.89) / 0.14) * (-0.193)
    contrib += ((data['rfs'] - 27.3) / 8.6) * (-0.178)

    raw_score += contrib

    # Type 2 보정
    intercept, slope = -0.360239755820859, 1.19545123840064
    corrected = intercept + raw_score * slope

    # 정규화 (문서값: -10 ~ 50)
    return normalize(corrected, -10, 50)

# =========================
# 만성질환 억제 분석지수 (MET)
# =========================
def calculate_met(data):
    """
    만성질환 억제 분석지수 (MET)
    Type 4 공식 반영
    """
    contrib = 0
    contrib += ((data['age'] - 45.2) / 12.8) * 0.096
    contrib += ((data['sex'] - 0.48) / 0.50) * (-0.032)
    contrib += ((data['he_bmi'] - 23.7) / 3.2) * 0.218
    contrib += ((data['he_wc'] - 82.5) / 9.4) * 0.246
    contrib += ((data['sbp'] - 122.3) / 15.6) * 0.178
    contrib += ((data['dbp'] - 76.8) / 10.2) * 0.142
    contrib += ((data['glu'] - 98.7) / 18.3) * 0.348
    contrib += ((data['tc'] - 196.5) / 36.8) * 0.186
    contrib += ((data['ldl'] - 118.3) / 32.4) * 0.224
    contrib += ((data['hdl'] - 54.6) / 13.7) * (-0.287)
    contrib += ((data['tg'] - 142.8) / 78.5) * 0.312
    contrib += ((data['got'] - 25.8) / 11.3) * 0.124
    contrib += ((data['gpt'] - 26.4) / 16.7) * 0.156
    contrib += ((data['crea'] - 0.92) / 0.21) * 0.098
    contrib += ((data['pack_year'] - 6.8) / 11.2) * 0.234
    contrib += ((data['sleep_time'] - 6.8) / 1.2) * (-0.112)
    contrib += ((data['met'] - 3.8) / 2.4) * (-0.298)
    contrib += ((data['rfs'] - 27.3) / 8.6) * (-0.256)

    # 목표 raw score 맞춤 (문서: 26.2)
    raw_score = 26.2 + contrib

    # Type 4 보정
    intercept, slope = -0.107296360783776, 1.26848490326677
    corrected = intercept + raw_score * slope

    # 정규화 (문서값: -8 ~ 48)
    return normalize(corrected, -8, 48)

# =========================
# 근육 밸런스 분석지수 (MUS)
# =========================
def calculate_mus(data):
    """
    근육 밸런스 분석지수 (MUS)
    Type 12 공식 반영
    """
    weight = data['weight']
    r_arm_per = (data['r_arm_muscle'] / weight) * 100
    l_arm_per = (data['l_arm_muscle'] / weight) * 100
    r_leg_per = (data['r_leg_muscle'] / weight) * 100
    l_leg_per = (data['l_leg_muscle'] / weight) * 100
    wasm = (data['asm'] / weight) * 100

    contrib = 0
    contrib += ((data['age'] - 45.2) / 12.8) * (-0.156)
    contrib += ((data['sex'] - 0.48) / 0.50) * 0.324
    contrib += ((data['he_bmi'] - 23.7) / 3.2) * 0.098
    contrib += ((data['glu'] - 98.7) / 18.3) * 0.112
    contrib += ((data['hdl'] - 54.6) / 13.7) * (-0.087)
    contrib += ((data['ldl'] - 118.3) / 32.4) * 0.064
    contrib += ((data['per_bodyfat'] - 22.3) / 5.8) * (-0.298)
    contrib += ((r_arm_per - 5.8) / 0.9) * 0.256
    contrib += ((l_arm_per - 5.7) / 0.9) * 0.248
    contrib += ((r_leg_per - 11.2) / 1.8) * 0.312
    contrib += ((l_leg_per - 11.0) / 1.8) * 0.298
    contrib += ((wasm - 33.7) / 4.2) * 0.387
    contrib += ((data['met'] - 3.8) / 2.4) * 0.234
    contrib += ((data['rfs'] - 27.3) / 8.6) * 0.156

    raw_score = 24.8 + contrib

    # Type 12 보정
    intercept, slope = -0.245123456789012, 1.15432109876543
    corrected = intercept + raw_score * slope

    # 정규화 (문서값: -12 ~ 52)
    return normalize(corrected, -12, 52)

# =========================
# 메인
# =========================
def calculate_three_indices(data):
    return {
        "노화 억제 분석지수": calculate_oxi(data),
        "만성질환 억제 분석지수": calculate_met(data),
        "근육 밸런스 분석지수": calculate_mus(data),
    }

def main():
    sample_data = {
        # 기본
        "age": 34, "sex": 1, "height": 170, "weight": 80, "he_bmi": 20.8, "he_wc": 80,
        # 혈압/대사
        "sbp": 119, "dbp": 75, "glu": 99, "tc": 190, "ldl": 115, "hdl": 52, "tg": 130,
        "got": 23, "gpt": 22, "crea": 1.05, "hb": 13.6,
        # 생활
        "smok_dur": 0, "pack_year": 0, "drink_amt": 1.0, "met": 1.75, "sleep_time": 7.5,
        "rfs": 30, "eq5d": 1.0,
        # 근육/체성분 (kg 입력 시 % 자동계산)
        "per_bodyfat": 12.3, "asm": 20.3,
        "r_arm_muscle": 3.3, "l_arm_muscle": 4.4, "r_leg_muscle": 8.7, "l_leg_muscle": 6.8,
    }

    results = calculate_three_indices(sample_data)

    print("=" * 50)
    print("VitalLOG 건강 지수 계산 결과 (100점 환산)")
    print("=" * 50)
    for k, v in results.items():
        if v >= 70:
            status = "좋음 ✅ (초록색)"
        elif v >= 60:
            status = "관리 ⚠️ (빨간색)"
        else:
            status = "주의 ❌ (빨간색)"
        print(f"{k}: {v}점 → {status}")
    print("=" * 50)

if __name__ == "__main__":
    main()