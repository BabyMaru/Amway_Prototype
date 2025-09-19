import pandas as pd
from groq import Groq
from sqlalchemy import create_engine, text
import os
import json
import hashlib
from typing import Optional, List, Dict

class HealthRAGSystem:
    def __init__(self, groq_api_key: str):
        self.groq_client = Groq(api_key=groq_api_key)
        
        # Streamlit secrets에서 데이터베이스 설정 가져오기
        try:
            import streamlit as st
            self.db_config = {
                'DB_NAME': st.secrets["DB_NAME"],
                'DB_USER': st.secrets["DB_USER"],
                'DB_PASS': st.secrets["DB_PASS"],
                'DB_HOST': st.secrets["DB_HOST"],
                'DB_PORT': st.secrets["DB_PORT"]
            }
        except (KeyError, ImportError):
            # 로컬 개발용 fallback
            self.db_config = {
                'DB_NAME': os.getenv('DB_NAME', 'Amway_DB'),
                'DB_USER': os.getenv('DB_USER', 'postgres'),
                'DB_PASS': os.getenv('DB_PASS', '990910'),
                'DB_HOST': os.getenv('DB_HOST', 'localhost'),
                'DB_PORT': os.getenv('DB_PORT', '5432')
            }
        
        conn_str = f"postgresql+psycopg2://{self.db_config['DB_USER']}:{self.db_config['DB_PASS']}@{self.db_config['DB_HOST']}:{self.db_config['DB_PORT']}/{self.db_config['DB_NAME']}"
        self.engine = create_engine(conn_str)
        # LLM 응답 캐시 디렉토리 설정
        self.cache_dir = os.path.join(os.getcwd(), ".llm_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    # --------------------------
    # 캐싱 유틸리티
    # --------------------------
    def _stable_serialize(self, data: Dict) -> str:
        """딕셔너리를 정렬된 JSON 문자열로 직렬화(한글 보존)."""
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _build_cache_key(self, payload: Dict, prefix: str) -> str:
        serialized = self._stable_serialize(payload).encode("utf-8")
        digest = hashlib.sha256(serialized).hexdigest()
        return f"{prefix}-{digest}"

    def _read_cache(self, key: str) -> Optional[str]:
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return obj.get("content")
        except Exception:
            return None

    def _write_cache(self, key: str, content: str) -> None:
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"content": content}, f, ensure_ascii=False)
        except Exception:
            pass

    def get_products_from_classification(self, health_indicators: List[str], physiology_network: List[str], health_concerns: List[str]) -> tuple:
        """분류기준 테이블에서 건강지표 조합에 맞는 제품들을 가져오고 우선순위를 적용 - 최종 최적화 버전"""
        
        if not health_indicators:
            return [], {}
        
        # 전체 테이블 조회 (안정성 우선) - 원료 컬럼 추가
        query = """
        SELECT "제품명", "건강지표", "관리 필요 영역", "원료"
        FROM "분류기준"
        ORDER BY "제품명", "건강지표"
        """
        
        try:
            classification_df = pd.read_sql(query, con=self.engine)
        except Exception as e:
            return [], {}
        
        if classification_df.empty:
            return [], {}
        
        # 집합 연산 최적화
        health_indicators_set = set(health_indicators)
        physiology_set = set(physiology_network)
        concerns_set = set(health_concerns)
        all_selected_areas = physiology_set | concerns_set
        
        # 제품별 데이터 구조화
        product_data = {}
        
        for _, row in classification_df.iterrows():
            product_name = row['제품명']
            health_indicator_combo = row['건강지표']
            management_area = row['관리 필요 영역']
            
            if product_name not in product_data:
                product_data[product_name] = {
                    'combos': [],
                    'areas': set(),
                    'physiology_matches': 0,
                    'concern_matches': 0
                }
            
            product_data[product_name]['combos'].append(health_indicator_combo)
            product_data[product_name]['areas'].add(management_area)
            
            # 관리영역 매칭 카운트
            if management_area in physiology_set:
                product_data[product_name]['physiology_matches'] += 1
            if management_area in concerns_set:
                product_data[product_name]['concern_matches'] += 1
        
        # 각 제품의 최적 조합 찾기
        final_products = []
        
        for product_name, data in product_data.items():
            best_match_count = 0
            best_combo = ''
            best_combo_size = float('inf')
            best_is_exact = False
            
            for combo in data['combos']:
                combo_indicators = [ind.strip() for ind in combo.split(',')]
                combo_set = set(combo_indicators)
                
                # 매칭 계산
                match_count = len(combo_set & health_indicators_set)
                if match_count == 0:
                    continue
                
                combo_size = len(combo_set)
                is_exact_match = combo_set.issubset(health_indicators_set)
                
                # 우선순위 결정: 정확한 매칭 > 매칭 개수 > 조합 크기 작음
                is_better = False
                if is_exact_match and not best_is_exact:
                    is_better = True
                elif is_exact_match == best_is_exact:
                    if match_count > best_match_count:
                        is_better = True
                    elif match_count == best_match_count and combo_size < best_combo_size:
                        is_better = True
                
                if is_better:
                    best_match_count = match_count
                    best_combo = combo
                    best_combo_size = combo_size
                    best_is_exact = is_exact_match
            
            if best_match_count > 0:
                # 관리영역 매칭 점수 (낮은 가중치)
                area_matches = len(data['areas'] & all_selected_areas)
                area_score = area_matches if all_selected_areas else 0
                
                # 최종 점수 계산 - 건강지표 정확성 절대 우선
                if best_is_exact:
                    # 정확한 매칭: 조합 크기가 작을수록 높은 점수
                    combo_bonus = max(0, 10 - best_combo_size) * 100
                    final_score = 10000 + best_match_count * 1000 + combo_bonus + area_score
                else:
                    # 부정확한 매칭: 낮은 기본 점수
                    final_score = best_match_count * 100 + area_score
                
                final_products.append((
                    product_name,
                    {
                        'best_match_count': best_match_count,
                        'best_combo': best_combo,
                        'best_combo_size': best_combo_size,
                        'best_is_exact_match': best_is_exact,
                        'physiology_matches': data['physiology_matches'],
                        'concern_matches': data['concern_matches'],
                        'management_areas': data['areas'],
                        'final_score': final_score
                    }
                ))
        
        # 점수순 정렬 및 상위 7개 선택
        final_products.sort(key=lambda x: x[1]['final_score'], reverse=True)
        top_products = final_products[:7]
        
        selected_products = [p[0] for p in top_products]
        product_scores = {p[0]: p[1] for p in top_products}
        
        return selected_products, product_scores

    def get_product_details(self, product_names: List[str]) -> pd.DataFrame:
        """제품정보와 분류기준 테이블에서 제품 상세 정보 조회"""
        if not product_names:
            return pd.DataFrame()
        
        product_filter = ', '.join(f"'{name}'" for name in product_names)
        
        # 제품정보 테이블에서 기본 정보 조회 (제품명, 관리 필요 영역 제외)
        query = f"""
        SELECT DISTINCT
            pi."식품유형",
            pi."제품명",
            pi."식약처 인정 기능성",
            pi."주요 특징",
            pi."섭취 방법",
            pi."주의사항",
            pi."원재료",
            pi."영양성분",
            pi."글로벌/로컬 제품구분(제조사)",
            al."알레르겐_정보"
        FROM "제품정보" pi
        LEFT JOIN (
            SELECT "제품명", STRING_AGG("카테고리" || ' - ' || "분류" || ' (' || "알레르기 유발물질" || ')', ', ') AS 알레르겐_정보
            FROM "제품_알레르겐"
            GROUP BY "제품명"
        ) al ON pi."제품명" = al."제품명"
        WHERE pi."제품명" IN ({product_filter})
        """
        
        product_info_df = pd.read_sql(query, con=self.engine)
        
        # 분류기준 테이블에서 관리 필요 영역 조회
        classification_query = f"""
        SELECT "제품명", STRING_AGG(DISTINCT "관리 필요 영역", ', ') as "관리 필요 영역"
        FROM "분류기준"
        WHERE "제품명" IN ({product_filter})
        GROUP BY "제품명"
        """
        
        classification_df = pd.read_sql(classification_query, con=self.engine)
        
        # 두 DataFrame을 제품명으로 병합
        if not product_info_df.empty and not classification_df.empty:
            result_df = pd.merge(product_info_df, classification_df, on='제품명', how='left')
        else:
            result_df = product_info_df
        
        return result_df

    def get_product_classification_info(self, product_names: List[str]) -> Dict[str, Dict]:
        """분류기준 테이블에서 제품별 건강지표와 관리 필요 영역 정보 조회"""
        if not product_names:
            return {}
        
        product_filter = ', '.join(f"'{name}'" for name in product_names)
        
        query = f"""
        SELECT "제품명", "건강지표", "관리 필요 영역", "원료"
        FROM "분류기준"
        WHERE "제품명" IN ({product_filter})
        """
        
        classification_df = pd.read_sql(query, con=self.engine)
        
        # 제품별로 건강지표, 관리 필요 영역, 원료 그룹화
        product_classification = {}
        for _, row in classification_df.iterrows():
            product_name = row['제품명']
            if product_name not in product_classification:
                product_classification[product_name] = {
                    'health_indicators': set(),
                    'management_areas': set(),
                    'ingredients': set()
                }
            
            product_classification[product_name]['health_indicators'].add(row['건강지표'])
            product_classification[product_name]['management_areas'].add(row['관리 필요 영역'])
            
            # 원료 정보 추가 (null이 아닌 경우에만)
            if pd.notna(row.get('원료')):
                product_classification[product_name]['ingredients'].add(row['원료'])
        
        return product_classification

    def get_health_indicator_relationships(self) -> Dict[str, List[str]]:
        """그래프 테이블에서 건강지표와 관리 필요 영역의 연관 관계 조회"""
        query = """
        SELECT DISTINCT "건강지표", "관리 필요 영역"
        FROM "그래프"
        WHERE "건강지표" IS NOT NULL AND "관리 필요 영역" IS NOT NULL
        """
        
        graph_df = pd.read_sql(query, con=self.engine)
        
        # 건강지표별로 관리 필요 영역들을 그룹화
        health_relationships = {}
        for _, row in graph_df.iterrows():
            health_indicator = row['건강지표']
            management_area = row['관리 필요 영역']
            
            if health_indicator not in health_relationships:
                health_relationships[health_indicator] = []
            
            if management_area not in health_relationships[health_indicator]:
                health_relationships[health_indicator].append(management_area)
        
        return health_relationships

    def create_health_status_explanation(self, assessments: Dict[str, str], physiology_network: List[str], health_concerns: List[str], recommended_products_df: pd.DataFrame = None) -> str:
        """사용자의 건강 상태에 대한 설명 텍스트 생성"""
        
        # 그래프 테이블에서 건강지표와 관리 필요 영역 연관 관계 조회
        health_relationships = self.get_health_indicator_relationships()
        
        # '좋음'이 아닌 건강지표만 필터링
        problematic_indicators = {k: v for k, v in assessments.items() if v in ["주의", "관리"]}
        
        if not problematic_indicators:
            return ""
        
        explanation_parts = []
        
        # 전체 상태 요약을 더 부드럽고 자세하게 작성
        explanation_parts.append(f"**🔍 건강 상태 분석**")
        explanation_parts.append("")
        
        # 주의/관리가 필요한 지표들 분석
        attention_indicators = [k for k, v in problematic_indicators.items() if v == "주의"]
        management_indicators = [k for k, v in problematic_indicators.items() if v == "관리"]
        
        # 추천된 제품들의 관리 필요 영역 수집
        all_product_areas = set()
        if recommended_products_df is not None and not recommended_products_df.empty:
            for _, row in recommended_products_df.iterrows():
                # 분류기준 테이블의 관리 필요 영역
                if row.get('해당_관리영역'):
                    areas_from_classification = [area.strip() for area in row['해당_관리영역'].split(',')]
                    all_product_areas.update(areas_from_classification)
                
                # 제품정보 테이블의 관리 필요 영역
                if row.get('관리 필요 영역'):
                    areas_from_product_info = [area.strip() for area in row['관리 필요 영역'].split(',')]
                    all_product_areas.update(areas_from_product_info)
        
        # 사용자가 선택한 영역과 제품 관리 영역의 교집합
        all_selected_areas = set(physiology_network + health_concerns)
        priority_areas = []
        
        # 각 건강지표와 연관된 영역 중에서 사용자가 선택한 것들과 제품 영역들 찾기
        for indicator in problematic_indicators.keys():
            if indicator in health_relationships:
                related_areas = health_relationships[indicator]
                matching_areas = [area for area in related_areas if area in all_selected_areas or area in all_product_areas]
                priority_areas.extend(matching_areas)
        
        # 중복 제거하고 우선순위 영역 선택 (최대 2개)
        unique_priority_areas = list(set(priority_areas))[:2]
        
        # 부드러운 톤으로 건강 상태 설명 (더 자세하게)
        status_description = "사용자님은 최근 건강점수에서 "
        
        if attention_indicators and management_indicators:
            status_description += f"{', '.join(attention_indicators + management_indicators)}는 각각 '주의'와 '관리'로 나타나 "
        elif attention_indicators:
            status_description += f"{', '.join(attention_indicators)}는 '주의'로 나타나 "
        elif management_indicators:
            status_description += f"{', '.join(management_indicators)}는 '관리'로 나타나 "
        
        if unique_priority_areas:
            status_description += f"**{', '.join(unique_priority_areas)} 관리**가 우선입니다."
        else:
            status_description += "전반적인 건강 관리가 필요한 상태입니다."
        
        explanation_parts.append(status_description)
        explanation_parts.append("")
        
        # 더 자세한 건강 상태 분석 추가
        detailed_analysis = []
        
        # 각 건강지표별 상세 분석
        for indicator, status in problematic_indicators.items():
            if indicator in health_relationships:
                related_areas = health_relationships[indicator]
                # 해당 건강지표와 연관된 영역 중 제품이나 사용자 선택과 매칭되는 것들
                relevant_areas = [area for area in related_areas if area in all_product_areas or area in all_selected_areas]
                
                if relevant_areas:
                    if indicator == "노화 억제 분석지수":
                        detailed_analysis.append(f"노화 억제와 관련하여 {', '.join(relevant_areas[:3])} 등의 영역에서 개선이 필요한 상황입니다.")
                    elif indicator == "만성질환 억제 분석지수":
                        detailed_analysis.append(f"만성질환 예방을 위해 {', '.join(relevant_areas[:3])} 등의 관리가 중요한 시점입니다.")
                    elif indicator == "근육 밸런스 분석지수":
                        detailed_analysis.append(f"근육 건강 유지를 위해 {', '.join(relevant_areas[:3])} 등의 영역에 특별한 관심이 필요합니다.")
        
        if detailed_analysis:
            explanation_parts.extend(detailed_analysis)
            explanation_parts.append("")
        
        # 추가 설명 - 다른 연관 영역들에 대한 설명 (더 풍부하게)
        other_areas = []
        for indicator in problematic_indicators.keys():
            if indicator in health_relationships:
                related_areas = health_relationships[indicator]
                # 우선순위 영역을 제외한 다른 영역들
                other_related = [area for area in related_areas if area not in unique_priority_areas and (area in all_selected_areas or area in all_product_areas)]
                other_areas.extend(other_related)
        
        # 중복 제거
        unique_other_areas = list(set(other_areas))
        
        if unique_other_areas:
            other_areas_text = ', '.join(unique_other_areas[:4])  # 최대 4개까지
            explanation_parts.append(f"이와 함께 {other_areas_text} 등의 영역도 종합적으로 관리하시면 더욱 효과적인 건강 개선을 기대할 수 있습니다. 특히 이러한 영역들은 서로 연관되어 있어 함께 관리할 때 시너지 효과를 얻을 수 있습니다.")
            explanation_parts.append("")
        
        # 생활습관 개선 권장사항 추가
        lifestyle_recommendations = []
        if "혈행 개선" in all_product_areas or "혈행 개선" in all_selected_areas:
            lifestyle_recommendations.append("규칙적인 유산소 운동")
        if "항산화" in all_product_areas or "항산화" in all_selected_areas:
            lifestyle_recommendations.append("충분한 수면과 스트레스 관리")
        if "근력(근육)" in all_product_areas or "근력(근육)" in all_selected_areas:
            lifestyle_recommendations.append("적절한 단백질 섭취와 근력 운동")
        if "혈중 지질 개선" in all_product_areas or "혈중 지질 개선" in all_selected_areas:
            lifestyle_recommendations.append("균형 잡힌 식단과 금연")
        
        explanation_parts.append("---")
        explanation_parts.append("")
        
        return '\n'.join(explanation_parts)

    def recommend_products(self, assessments: Dict[str, str], physiology_network: List[str], health_concerns: List[str], user_input: str = "", user_data: Dict = None) -> tuple:
        """새로운 추천 로직의 메인 함수 - DataFrame과 LLM 설명을 함께 반환"""
        
        # '좋음'이 아닌 건강지표만 필터링
        active_health_indicators = [k for k, v in assessments.items() if v in ["주의", "관리"]]
        
        # 모든 건강 지표가 '좋음'인 경우 특별 처리
        if not active_health_indicators:
            # 건강 지표는 고려하지 않고 인체 생리 네트워크와 건강 분야만으로 추천
            final_products = self._recommend_for_all_good_health(physiology_network, health_concerns)
            # 모든 건강지표가 좋음인 경우의 LLM 설명 생성
            llm_explanation = self._generate_explanation_for_good_health(physiology_network, health_concerns, final_products)
            return final_products, llm_explanation
        
        # 분류기준 테이블에서 제품 추천
        selected_products, product_scores = self.get_products_from_classification(
            active_health_indicators, physiology_network, health_concerns
        )
        
        # 제품 상세 정보 조회
        product_details = self.get_product_details(selected_products)
        
        # 분류기준 정보 조회
        product_classification = self.get_product_classification_info(selected_products)
        
        # 최종 제품 리스트 (최대 7개 제한)
        final_products = pd.DataFrame()
        seen_products = set()
        
        # 점수 정보를 DataFrame에 추가
        if not product_details.empty:
            # 실제 final_score를 우선순위 점수로 사용
            product_details['우선순위_점수'] = product_details['제품명'].map(
                lambda x: product_scores.get(x, {}).get('final_score', 0)
            )
            product_details['매칭_근거'] = product_details['제품명'].map(
                lambda x: self._create_matching_reason(x, product_scores.get(x, {}), physiology_network, health_concerns)
            )
            product_details['해당_건강지표'] = product_details['제품명'].map(
                lambda x: ', '.join(product_classification.get(x, {}).get('health_indicators', set()))
            )
            product_details['해당_관리영역'] = product_details['제품명'].map(
                lambda x: ', '.join(product_classification.get(x, {}).get('management_areas', set()))
            )
            product_details['해당_원료'] = product_details['제품명'].map(
                lambda x: ', '.join(product_classification.get(x, {}).get('ingredients', set()))
            )
            
            # selected_products 순서를 유지하면서 정렬
            # selected_products는 final_score 순으로 정렬되어 있음
            product_details['원본_순서'] = product_details['제품명'].map(
                lambda x: selected_products.index(x) if x in selected_products else 999
            )
            product_details = product_details.sort_values('원본_순서')
            
            # 최대 7개까지만 선택
            for _, product in product_details.iterrows():
                if len(final_products) < 7 and product['제품명'] not in seen_products:
                    final_products = pd.concat([final_products, pd.DataFrame([product])], ignore_index=True)
                    seen_products.add(product['제품명'])
                    
                if len(final_products) >= 7:
                    break
        
        # LLM을 활용한 개인화된 추천 근거 생성
        llm_explanation = ""
        if not final_products.empty:
            recommended_product_names = final_products['제품명'].tolist()
            llm_explanation = self.generate_personalized_recommendation_explanation(
                assessments, physiology_network, health_concerns, recommended_product_names, product_scores, user_data
            )
        
        return final_products, llm_explanation
    
    def _create_matching_reason(self, product_name: str, score_data: Dict, physiology_network: List[str], health_concerns: List[str]) -> str:
        """매칭 근거 텍스트 생성"""
        reasons = []
        
        if '노화 억제 분석지수' in score_data.get('health_indicators', set()) and '만성질환 억제 분석지수' in score_data.get('health_indicators', set()):
            reasons.append("1순위: 노화억제+만성질환 모두 포함")
        elif '노화 억제 분석지수' in score_data.get('health_indicators', set()) or '만성질환 억제 분석지수' in score_data.get('health_indicators', set()):
            reasons.append("2순위: 노화억제/만성질환 중 하나 포함")
        
        physiology_matches = score_data.get('physiology_matches', 0)
        if physiology_matches == len(physiology_network) and len(physiology_network) > 0:
            reasons.append(f"인체생리네트워크 모두 매칭({physiology_matches}개)")
        elif physiology_matches > 0:
            reasons.append(f"인체생리네트워크 일부 매칭({physiology_matches}개)")
        
        concern_matches = score_data.get('concern_matches', 0)
        if concern_matches > 0:
            reasons.append(f"건강분야 매칭({concern_matches}개)")
        
        return ", ".join(reasons) if reasons else "기타 매칭"

    def _create_matching_reason_safe(self, product_name: str, score_data: Dict, physiology_network: List[str], health_concerns: List[str]) -> str:
        """안전한 매칭 근거 텍스트 생성 (오류 방지)"""
        try:
            reasons = []
            
            # 건강지표 매칭 확인 (안전한 방식)
            best_combo = score_data.get('best_combo', '')
            if best_combo:
                if '노화 억제 분석지수' in best_combo and '만성질환 억제 분석지수' in best_combo:
                    reasons.append("1순위: 노화억제+만성질환 모두 포함")
                elif '노화 억제 분석지수' in best_combo or '만성질환 억제 분석지수' in best_combo:
                    reasons.append("2순위: 노화억제/만성질환 중 하나 포함")
                else:
                    reasons.append("건강지표 매칭")
            
            # 관리영역 매칭 확인
            physiology_matches = score_data.get('physiology_matches', 0)
            if physiology_matches == len(physiology_network) and len(physiology_network) > 0:
                reasons.append(f"인체생리네트워크 완전매칭({physiology_matches}개)")
            elif physiology_matches > 0:
                reasons.append(f"인체생리네트워크 매칭({physiology_matches}개)")
            
            concern_matches = score_data.get('concern_matches', 0)
            if concern_matches > 0:
                reasons.append(f"건강분야 매칭({concern_matches}개)")
            
            # 정확한 매칭 여부 표시
            if score_data.get('best_is_exact_match', False):
                reasons.append("정확한 매칭")
            
            return ", ".join(reasons) if reasons else "기본 매칭"
            
        except Exception as e:
            return f"매칭 정보 처리 중 오류: {str(e)}"

    def _recommend_for_all_good_health(self, physiology_network: List[str], health_concerns: List[str]) -> pd.DataFrame:
        """모든 건강 지표가 '좋음'인 경우 인체 생리 네트워크와 건강 분야만으로 제품 추천"""
        
        # 선택된 모든 관리 영역
        all_selected_areas = set(physiology_network + health_concerns)
        
        if not all_selected_areas:
            return pd.DataFrame()
        
        # 분류기준 테이블에서 선택된 관리 영역에 해당하는 제품들 조회 (건강지표 포함)
        areas_filter = ', '.join(f"'{area}'" for area in all_selected_areas)
        
        query = f"""
        SELECT "제품명", "건강지표", "관리 필요 영역", "원료"
        FROM "분류기준"
        WHERE "관리 필요 영역" IN ({areas_filter})
        """
        
        classification_df = pd.read_sql(query, con=self.engine)
        
        if classification_df.empty:
            return pd.DataFrame()
        
        # 제품별 관리 영역 매칭 점수 계산 및 건강지표 수집
        product_scores = {}
        
        for _, row in classification_df.iterrows():
            product_name = row['제품명']
            health_indicator = row['건강지표']
            management_area = row['관리 필요 영역']
            
            if product_name not in product_scores:
                product_scores[product_name] = {
                    'management_areas': set(),
                    'health_indicators': set(),  # 건강지표 추가
                    'ingredients': set(),  # 원료 추가
                    'physiology_matches': 0,
                    'concern_matches': 0,
                    'total_matches': 0
                }
            
            product_scores[product_name]['management_areas'].add(management_area)
            product_scores[product_name]['health_indicators'].add(health_indicator)  # 건강지표 저장
            
            # 원료 정보 추가 (null이 아닌 경우에만)
            if pd.notna(row.get('원료')):
                product_scores[product_name]['ingredients'].add(row['원료'])
            
            # 인체 생리 네트워크 매칭
            if management_area in physiology_network:
                product_scores[product_name]['physiology_matches'] += 1
            
            # 신경 써야 할 건강 분야 매칭
            if management_area in health_concerns:
                product_scores[product_name]['concern_matches'] += 1
            
            # 전체 매칭 개수
            product_scores[product_name]['total_matches'] += 1
        
        # 점수 기반으로 제품 정렬
        sorted_products = []
        
        for product_name, score_data in product_scores.items():
            # 최종 점수 계산 (인체 생리 네트워크에 더 높은 가중치)
            final_score = (
                score_data['physiology_matches'] * 10 +  # 인체 생리 네트워크 가중치
                score_data['concern_matches'] * 5 +      # 건강 분야 가중치
                score_data['total_matches'] * 2          # 전체 매칭 보너스
            )
            
            score_data['final_score'] = final_score
            sorted_products.append((product_name, score_data))
        
        # 점수순으로 정렬
        sorted_products.sort(key=lambda x: x[1]['final_score'], reverse=True)
        
        # 상위 7개 제품 선택
        top_products = sorted_products[:7]
        selected_product_names = [product[0] for product in top_products]
        
        # 제품 상세 정보 조회
        product_details = self.get_product_details(selected_product_names)
        
        # 분류기준 정보 조회
        product_classification = self.get_product_classification_info(selected_product_names)
        
        if not product_details.empty:
            # 점수 정보를 DataFrame에 추가
            product_details['우선순위_점수'] = product_details['제품명'].map(
                lambda x: next((score_data['final_score'] for name, score_data in top_products if name == x), 0)
            )
            product_details['매칭_근거'] = product_details['제품명'].map(
                lambda x: self._create_matching_reason_for_good_health(x, product_scores.get(x, {}), physiology_network, health_concerns)
            )
            product_details['해당_건강지표'] = product_details['제품명'].map(
                lambda x: ', '.join(product_scores.get(x, {}).get('health_indicators', set()))
            )
            product_details['해당_관리영역'] = product_details['제품명'].map(
                lambda x: ', '.join(product_classification.get(x, {}).get('management_areas', set()))
            )
            product_details['해당_원료'] = product_details['제품명'].map(
                lambda x: ', '.join(product_scores.get(x, {}).get('ingredients', set()))
            )
            
            # 우선순위 점수순으로 정렬
            product_details = product_details.sort_values('우선순위_점수', ascending=False)
        
        return product_details

    def _create_matching_reason_for_good_health(self, product_name: str, score_data: Dict, physiology_network: List[str], health_concerns: List[str]) -> str:
        """모든 건강 지표가 '좋음'인 경우의 매칭 근거 텍스트 생성"""
        reasons = []
        
        physiology_matches = score_data.get('physiology_matches', 0)
        if physiology_matches == len(physiology_network) and len(physiology_network) > 0:
            reasons.append(f"인체생리네트워크 완전매칭({physiology_matches}개)")
        elif physiology_matches > 0:
            reasons.append(f"인체생리네트워크 매칭({physiology_matches}개)")
        
        concern_matches = score_data.get('concern_matches', 0)
        if concern_matches == len(health_concerns) and len(health_concerns) > 0:
            reasons.append(f"건강분야 완전매칭({concern_matches}개)")
        elif concern_matches > 0:
            reasons.append(f"건강분야 매칭({concern_matches}개)")
        
        if not reasons:
            reasons.append("건강 유지 및 예방 목적")
        
        return ", ".join(reasons)


    def analyze_user_health_data(self, user_data: Dict) -> Dict[str, str]:
        """사용자의 실제 건강 데이터를 분석하여 구체적인 건강 상태 설명 생성"""
        analysis = {}
        
        # 기본 정보
        age = user_data.get('age', 0)
        sex = user_data.get('sex', 1)  # 1: 남성, 2: 여성
        bmi = user_data.get('he_bmi', 0)
        
        # 혈압 분석
        sbp = user_data.get('sbp', 0)  # 수축기 혈압
        dbp = user_data.get('dbp', 0)  # 이완기 혈압
        
        if sbp >= 140 or dbp >= 90:
            analysis['혈압'] = f"수축기 혈압 {sbp}mmHg, 이완기 혈압 {dbp}mmHg로 고혈압 범위에 해당하여 혈압 조절이 필요합니다."
        elif sbp >= 130 or dbp >= 80:
            analysis['혈압'] = f"수축기 혈압 {sbp}mmHg, 이완기 혈압 {dbp}mmHg로 고혈압 전단계로 혈압 관리가 권장됩니다."
        
        # 간 기능 분석
        gpt = user_data.get('gpt', 0)  # ALT
        got = user_data.get('got', 0)  # AST
        
        if gpt > 40 or got > 40:
            analysis['간건강'] = f"ALT {gpt}U/L, AST {got}U/L로 정상 범위를 초과하여 간 기능 개선이 필요합니다."
        elif gpt > 30 or got > 30:
            analysis['간건강'] = f"ALT {gpt}U/L, AST {got}U/L로 정상 상한에 근접하여 간 건강 관리가 권장됩니다."
        
        # 혈중 지질 분석
        tc = user_data.get('tc', 0)  # 총 콜레스테롤
        ldl = user_data.get('ldl', 0)  # LDL 콜레스테롤
        hdl = user_data.get('hdl', 0)  # HDL 콜레스테롤
        tg = user_data.get('tg', 0)  # 중성지방
        
        lipid_issues = []
        if tc >= 240:
            lipid_issues.append(f"총 콜레스테롤 {tc}mg/dL (고위험)")
        elif tc >= 200:
            lipid_issues.append(f"총 콜레스테롤 {tc}mg/dL (경계)")
            
        if ldl >= 160:
            lipid_issues.append(f"LDL 콜레스테롤 {ldl}mg/dL (고위험)")
        elif ldl >= 130:
            lipid_issues.append(f"LDL 콜레스테롤 {ldl}mg/dL (경계)")
            
        if (sex == 1 and hdl < 40) or (sex == 2 and hdl < 50):
            lipid_issues.append(f"HDL 콜레스테롤 {hdl}mg/dL (낮음)")
            
        if tg >= 200:
            lipid_issues.append(f"중성지방 {tg}mg/dL (높음)")
        elif tg >= 150:
            lipid_issues.append(f"중성지방 {tg}mg/dL (경계)")
        
        if lipid_issues:
            analysis['혈중지질'] = "혈중 지질 개선이 필요합니다: " + ", ".join(lipid_issues)
        
        # 혈당 분석
        glu = user_data.get('glu', 0)
        if glu >= 126:
            analysis['혈당'] = f"공복혈당 {glu}mg/dL로 당뇨병 범위에 해당하여 혈당 조절이 시급합니다."
        elif glu >= 100:
            analysis['혈당'] = f"공복혈당 {glu}mg/dL로 당뇨병 전단계로 혈당 관리가 필요합니다."
        
        # 체중 및 체성분 분석
        if bmi >= 30:
            analysis['체중'] = f"BMI {bmi}로 비만 상태로 체지방 감소가 필요합니다."
        elif bmi >= 25:
            analysis['체중'] = f"BMI {bmi}로 과체중 상태로 체중 관리가 권장됩니다."
        elif bmi < 18.5:
            analysis['체중'] = f"BMI {bmi}로 저체중 상태로 영양 균형과 근력 증진이 필요합니다."
        
        # 근육량 분석
        skeletal_muscle = user_data.get('skeletal_muscle_mass', 0)
        per_bodyfat = user_data.get('per_bodyfat', 0)
        
        if per_bodyfat > 25 and sex == 1:  # 남성
            analysis['근육'] = f"체지방률 {per_bodyfat}%로 높아 근력 증진과 체지방 감소가 필요합니다."
        elif per_bodyfat > 30 and sex == 2:  # 여성
            analysis['근육'] = f"체지방률 {per_bodyfat}%로 높아 근력 증진과 체지방 감소가 필요합니다."
        
        # 생활습관 분석
        smok_dur = user_data.get('smok_dur', 0)
        sleep_time = user_data.get('sleep_time', 0)
        
        lifestyle_issues = []
        if smok_dur > 0:
            lifestyle_issues.append(f"{smok_dur}년간의 흡연으로 항산화 및 혈행 개선이 중요합니다")
        
        if sleep_time < 7:
            lifestyle_issues.append(f"수면시간 {sleep_time}시간으로 부족하여 수면 건강 관리가 필요합니다")
        
        if lifestyle_issues:
            analysis['생활습관'] = ". ".join(lifestyle_issues)
        
        return analysis

    def generate_personalized_recommendation_explanation(self, assessments: Dict[str, str], physiology_network: List[str], health_concerns: List[str], recommended_products: List[str], product_scores: Dict, user_data: Dict = None) -> str:
        """LLM을 활용하여 개인화된 제품 추천 근거 생성 - 사용자 데이터 기반 개인화"""
        
        # 문제가 있는 건강지표만 추출
        problematic_indicators = {k: v for k, v in assessments.items() if v in ["주의", "관리"]}
        
        # 사용자 데이터 분석 (있는 경우)
        user_health_analysis = {}
        if user_data:
            user_health_analysis = self.analyze_user_health_data(user_data)
        
        # 제품별 상세 정보 조회
        product_details = self.get_product_details(recommended_products)
        product_classification = self.get_product_classification_info(recommended_products)
        
        # 건강지표와 관리영역 연관관계 조회
        health_relationships = self.get_health_indicator_relationships()
        
        # 프롬프트 생성
        prompt = f"""
사용자의 건강 상태 분석:
- 건강 지표: {', '.join([f"{k}({v})" for k, v in problematic_indicators.items()])}
- 인체 생리 네트워크 관심 영역: {', '.join(physiology_network) if physiology_network else '없음'}
- 고려하고 싶은 건강 분야: {', '.join(health_concerns) if health_concerns else '없음'}
"""

        # 사용자 실제 건강 데이터 분석 결과 추가
        if user_health_analysis:
            prompt += f"""
사용자의 실제 건강 데이터 분석:
"""
            if user_data:
                age = user_data.get('age', 0)
                sex = "남성" if user_data.get('sex', 1) == 1 else "여성"
                prompt += f"- 기본정보: {age}세 {sex}\n"
            
            for category, analysis in user_health_analysis.items():
                prompt += f"- {category}: {analysis}\n"

        prompt += """
건강지표별 연관 관리영역:
"""
        
        # 각 건강지표와 연관된 관리영역 정보 추가
        for indicator, status in problematic_indicators.items():
            if indicator in health_relationships:
                related_areas = health_relationships[indicator]
                prompt += f"- {indicator}({status}): {', '.join(related_areas)}\n"
        
        prompt += f"""

추천된 제품들과 상세 정보:
"""
        
        # 제품을 기본 베이스(1-3위)와 추가 보강(4-7위)으로 구분
        base_products = recommended_products[:3]
        additional_products = recommended_products[3:7] if len(recommended_products) > 3 else []
        
        prompt += "기본 베이스 제품 (1-3위):\n"
        for i, product_name in enumerate(base_products, 1):
            if product_name in product_scores:
                score_data = product_scores[product_name]
                product_info = product_details[product_details['제품명'] == product_name].iloc[0] if not product_details.empty else None
                classification_info = product_classification.get(product_name, {})
                
                prompt += f"""
{i}. {product_name}
   - 해당 건강지표: {', '.join(classification_info.get('health_indicators', set()))}
   - 관리 필요 영역: {', '.join(classification_info.get('management_areas', set()))}
   - **분류기준 테이블 주요 원료**: {', '.join(classification_info.get('ingredients', set())) if classification_info.get('ingredients') else '정보 없음'}
   - 식약처 인정 기능성: {product_info['식약처 인정 기능성'] if product_info is not None else '정보 없음'}
   - 주요 특징: {product_info['주요 특징'] if product_info is not None else '정보 없음'}
   - 원재료: {product_info['원재료'] if product_info is not None else '정보 없음'}
   - 건강지표 매칭: {score_data.get('best_match_count', 0)}개
   - 인체생리네트워크 매칭: {score_data.get('physiology_matches', 0)}개
   - 건강분야 매칭: {score_data.get('concern_matches', 0)}개
"""
        
        if additional_products:
            prompt += "\n추가 보강 제품 (4-7위):\n"
            for i, product_name in enumerate(additional_products, 4):
                if product_name in product_scores:
                    score_data = product_scores[product_name]
                    product_info = product_details[product_details['제품명'] == product_name].iloc[0] if not product_details.empty else None
                    classification_info = product_classification.get(product_name, {})
                    
                    prompt += f"""
{i}. {product_name}
   - 해당 건강지표: {', '.join(classification_info.get('health_indicators', set()))}
   - 관리 필요 영역: {', '.join(classification_info.get('management_areas', set()))}
   - **분류기준 테이블 주요 원료**: {', '.join(classification_info.get('ingredients', set())) if classification_info.get('ingredients') else '정보 없음'}
   - 식약처 인정 기능성: {product_info['식약처 인정 기능성'] if product_info is not None else '정보 없음'}
   - 주요 특징: {product_info['주요 특징'] if product_info is not None else '정보 없음'}
   - 원재료: {product_info['원재료'] if product_info is not None else '정보 없음'}
   - 건강지표 매칭: {score_data.get('best_match_count', 0)}개
   - 인체생리네트워크 매칭: {score_data.get('physiology_matches', 0)}개
   - 건강분야 매칭: {score_data.get('concern_matches', 0)}개
"""
        
        # 기본 제품과 보강 제품의 차별점 분석을 위한 정보
        if additional_products:
            prompt += f"""

기본 제품 vs 보강 제품 차별점 분석:
"""
            # 기본 제품들의 원료와 관리영역 수집
            base_ingredients = set()
            base_management_areas = set()
            base_health_indicators = set()
            
            for product_name in base_products:
                if product_name in product_classification:
                    base_ingredients.update(product_classification[product_name].get('ingredients', set()))
                    base_management_areas.update(product_classification[product_name].get('management_areas', set()))
                    base_health_indicators.update(product_classification[product_name].get('health_indicators', set()))
            
            prompt += f"기본 제품들이 커버하는 영역:\n"
            prompt += f"- 주요 원료: {', '.join(base_ingredients) if base_ingredients else '정보 없음'}\n"
            prompt += f"- 관리 영역: {', '.join(base_management_areas) if base_management_areas else '정보 없음'}\n"
            prompt += f"- 건강지표: {', '.join(base_health_indicators) if base_health_indicators else '정보 없음'}\n"
            
            # 보강 제품들만의 고유한 특징 분석
            prompt += f"\n보강 제품들의 추가 보완 영역:\n"
            for product_name in additional_products:
                if product_name in product_classification:
                    classification_info = product_classification[product_name]
                    
                    # 기본 제품에 없는 고유 원료
                    unique_ingredients = classification_info.get('ingredients', set()) - base_ingredients
                    # 기본 제품에 없는 고유 관리영역
                    unique_areas = classification_info.get('management_areas', set()) - base_management_areas
                    
                    if unique_ingredients or unique_areas:
                        prompt += f"- {product_name}: "
                        if unique_ingredients:
                            prompt += f"고유 원료({', '.join(unique_ingredients)}) "
                        if unique_areas:
                            prompt += f"추가 관리영역({', '.join(unique_areas)})"
                        prompt += "\n"

        # 개인화된 추천 로직 설명을 위한 추가 정보
        prompt += f"""

추천 로직 개인화 정보:
- 총 추천 제품 수: {len(recommended_products)}개
- 기본 베이스 제품: {len(base_products)}개
- 추가 보강 제품: {len(additional_products)}개
- 사용자 건강지표 문제 개수: {len(problematic_indicators)}개
- 선택한 관심영역 총 개수: {len(physiology_network) + len(health_concerns)}개
"""

        # 제품별 매칭 점수 분석
        if product_scores:
            prompt += "\n제품별 개인 맞춤 점수 분석:\n"
            for i, product_name in enumerate(recommended_products[:5], 1):  # 상위 5개만
                if product_name in product_scores:
                    score_data = product_scores[product_name]
                    prompt += f"- {product_name}: 총점 {score_data.get('final_score', 0)}점 (건강지표 {score_data.get('best_match_count', 0)}개 매칭, 관심영역 {score_data.get('physiology_matches', 0) + score_data.get('concern_matches', 0)}개 매칭)\n"

        prompt += """

다음과 같이 사용자 개인 데이터에 기반한 통합된 맞춤형 설명을 작성해주세요:

## 🔍 진단 결과

사용자님의 실제 건강 데이터(혈압, 간기능, 혈중지질, 혈당, 체성분 등)를 바탕으로 건강지표 분석 결과를 구체적으로 설명하고, 
왜 특정 관리영역이 우선적으로 필요한지 의학적 근거와 함께 명시하세요. 또한 사용자님의 개인 데이터를 분석하여 
맞춤형 추천 로직을 적용한 구체적인 추천 근거와 우선순위 결정 과정을 설명해주세요:
- 우선순위를 정하는 기준 명확하게 설명하고 시작하세요.
- 각각의 우선순위 결정 근거
- 선택하신 관심 영역과 실제 건강 상태의 연관성 분석
- 모든 관심 영역을 나열하지 말고 사용자가 선택한 관심 영역만 중심으로 설명하세요.
- 실제 건강 데이터(혈압, 간기능, 혈중지질 등)가 제품 선택에 미친 영향
- 사용자님만의 건강 관리 우선순위와 제품 매칭 과정

## 💊 기본 베이스 제품

각 제품마다 ### 제품명 작성 후 한 단락의 서술식으로 작성하세요. 다음을 자연스럽게 녹여 쓰되, 각 제품마다 문장과 표현을 매번 다르게 구성하여 중복을 피하세요:
- 제품명과 핵심 기능성
- 분류기준 테이블의 주요 원료와 각 원료의 구체적 효과(해당 건강지표와의 연계 포함)
- 식약처 인정 기능성, 주요 특징
- 건강지표 매칭 및 선택 근거를 원료의 효과와 연결
- 사용자 상황에 맞춘 적용 포인트(관심 영역과의 연결)
- 각 기본 베이스 제품에 매칭된 건강지표와 관리 필요 영역을 문장 속에서 반드시 언급해야 합니다.

## 💪🏻 보강 제품

각 보강 제품도 ### 제품명 작성 후 한 단락의 서술식으로 작성하세요. 다음을 담되, 기본 베이스와의 차별점을 중심으로 각 제품마다 중복 없이 전개하세요:
- 기본 베이스와의 차이와 보완 포인트
- 고유 원료(분류기준 테이블 기준)와 그 원료가 제공하는 추가 효과(해당 건강지표와의 연계 포함)
- 기본 제품으로 커버되지 않는 영역을 어떻게 보완하는지와 시너지
- 식약처 인정 기능성, 주요 특징
 - 원료를 나열만 하지 말고, 최소 2개 이상의 "원료→효과" 문장을 반드시 포함하세요. 예) "루테인은 청색광으로 인한 망막 산화 스트레스를 낮춰 시각 기능 유지에 기여합니다. 아스타잔틴은 강한 항산화력으로 노화 억제 지표 개선에 효과적입니다."
 - 각 보강 제품에 매칭된 건강지표와 관리 필요 영역을 문장 속에서 반드시 언급해야 합니다.
 - 사용자 관심 영역과의 연결 및 적용 포인트
 - 동일한 문장/표현/근거 반복 금지

작성 규칙:
- "~하는 데 도움을 줄 수 있습니다" 표현 금지 (최대 1회만 사용)
- "개선", "효과적" 등 다양한 표현 활용
- 중복 표현 최소화 (같은 단어/문장 패턴 반복 금지)
- 같은 내용을 다른 제품에서 반복 설명하지 말 것(내용·표현·근거 모두 중복 금지)
- 제품별로 독립된 문단 구성
- 각 문단은 3-4문장 이내로 제한
- 각 제품 문단은 150자 이상으로 작성
- 자연스럽고 다양한 문체 사용

필수 준수사항:
- 반드시 '건강기능식품'이라는 용어만 사용 ('건강 기능 보조제' 금지)
- 식약처 인정 기능성을 바탕으로만 효과 설명
- 과학적·규제 근거가 불명확한 표현 사용 금지
- 데이터베이스에 명시된 원료만 언급
- 기능성, 원료, 원재료 등에서 얻는 효과를 간단명료하게 명시할 것
- 외국어 절대 사용 금지(영어, 한국어만 허용)
- 각 제품 설명에는 '식약처 인정 기능성', '주요 특징', '원재료'(제품정보), '원료'(분류기준)를 반드시 포함
"""

        try:
            # 캐시 조회
            cache_payload = {
                "model": "llama-3.3-70b-versatile",
                "system": "당신은 개인 맞춤형 건강 제품 추천 전문가입니다.",
                "prompt": prompt,
                "temperature": 0.4,
            }
            cache_key = self._build_cache_key(cache_payload, prefix="personalized")
            cached = self._read_cache(cache_key)
            if cached:
                return cached.strip()

            chat_completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # 더 정교한 분석을 위해 큰 모델 사용
                messages=[
                    {"role": "system", "content": """당신은 개인 맞춤형 건강 제품 추천 전문가입니다.

핵심 원칙:
- 사용자 개인 데이터에 기반한 맞춤형 추천 로직 설명
- 각 사용자의 건강 상태, 관심 영역, 실제 건강 수치를 반영한 개인화된 근거 제시
- **분류기준 테이블의 원료 정보를 중심으로 한 제품 설명**
- 제품별로 독립된 문단으로 구성하여 읽기 쉽게 작성
- 다양한 표현을 사용하여 중복 방지
- 각 제품의 고유한 특징과 개인별 선택 근거를 명확히 구분

개인화 요구사항:
- 추천 로직 설명은 반드시 해당 사용자의 구체적인 데이터를 반영해야 함
- 건강지표 상태, 선택한 관심 영역, 실제 건강 수치가 제품 선택에 미친 영향을 구체적으로 설명
- 동일한 제품이라도 사용자에 따라 다른 추천 근거와 우선순위 설명 제공
- 사용자별 건강 관리 우선순위와 제품 매칭 과정을 개인화하여 설명

보강 제품 차별점 설명 요구사항:
- 보강 제품은 기본 베이스 제품과의 명확한 차별점을 제시해야 함
- **분류기준 테이블 기준으로 기본 제품에 없는 고유 원료와 그 원료의 추가적인 건강 효과를 구체적으로 설명**
- 기본 제품으로 커버되지 않는 건강 영역을 어떻게 보완하는지 명시
- 기본 제품과 보강 제품의 시너지 효과나 상호 보완 관계를 설명
- 사용자의 건강 상태에서 보강 제품이 필요한 구체적인 이유를 제시

규제 및 용어 준수:
- 반드시 '건강기능식품'이라는 용어를 사용하세요 ('건강 기능 보조제' 사용 금지)
- 식약처에서 인정한 기능성만을 바탕으로 설명하세요
- 과학적·규제 근거가 불명확한 표현은 사용하지 마세요
- 데이터베이스에 없는 원료나 성분은 언급하지 마세요
- 한자나 일본어는 절대 사용하지 마세요

표현 다양화:
- "도움을 줄 수 있습니다" 대신 "효과적입니다", "개선됩니다" 등 활용
- "개선하는 데" 대신 "향상시키며", "강화하고", "관리하여" 등 사용
- 같은 패턴의 문장 구조 반복 금지
- 자연스럽고 다양한 문체로 작성

금지사항:
- "~하는 데 도움을 줄 수 있습니다" 과도한 반복 (최대 1회)
- "각기 다른 건강 효과를 지원한다"와 같은 포괄적/모호한 표현
- "영향을 미치는 영역입니다" 같은 반복 표현
- 모든 제품에 동일한 설명 패턴 적용
- 같은 동사나 형용사의 연속 사용
- 한자, 일본어, 중국어 사용
- "추가적인 지원을 받으실 수 있습니다" 같은 부자연스러운 표현
- 같은 문장이나 구문의 반복
- 내용이 중간에 끊기거나 미완성으로 끝나는 것
 - 원료·기능성·원재료를 단순 나열만 하고 효과를 서술하지 않는 행위

작성 완성도:
- 반드시 완전한 문장으로 끝내야 함
- 모든 섹션을 빠짐없이 작성해야 함
- 자연스럽고 읽기 쉬운 한국어 사용
- 불필요한 군더더기 제거, 간결하고 밀도 있게 작성"""},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1600,  # 토큰 절감(내용 유지에 충분)
                temperature=0.4   # 자연스러운 표현을 위해 적절히 조정
            )
            
            content = chat_completion.choices[0].message.content.strip()
            self._write_cache(cache_key, content)
            return content
            
        except Exception as e:
            return f"개인화된 추천 근거 생성 중 오류가 발생했습니다: {str(e)}"

    def _generate_explanation_for_good_health(self, physiology_network: List[str], health_concerns: List[str], final_products: pd.DataFrame) -> str:
        """모든 건강지표가 좋음인 경우의 LLM 설명 생성"""
        
        if final_products.empty:
            return "추천할 제품이 없습니다."
        
        prompt = f"""
사용자의 건강 상태:
- 모든 건강 지표(노화 억제 분석지수, 근육 밸런스 분석지수, 만성질환 억제 분석지수)가 '좋음' 상태
- 인체 생리 네트워크 관심 영역: {', '.join(physiology_network) if physiology_network else '없음'}
- 고려하고 싶은 건강 분야: {', '.join(health_concerns) if health_concerns else '없음'}

추천된 제품들:
"""
        
        for i, (_, row) in enumerate(final_products.iterrows(), 1):
            prompt += f"""
{i}. {row['제품명']}
   - 해당 관리영역: {row.get('해당_관리영역', '정보 없음')}
   - 주요 원료: {row.get('해당_원료', '정보 없음')}
   - 원재료: {row.get('원재료', '정보 없음')}
   - 식약처 인정 기능성: {row.get('식약처 인정 기능성', '정보 없음')}
   - 주요 특징: {row.get('주요 특징', '정보 없음')}
"""
        
        prompt += """
위 정보를 바탕으로 다음과 같이 통합된 설명을 작성해주세요:

## 🔍 진단 결과

현재 건강 상태가 양호한 사용자에게 이러한 제품들이 왜 도움이 되는지 예방 및 유지 관점에서 설명하고, 선택된 관심 영역과 제품 추천 로직을 구체적으로 설명해주세요.

## 💊 개인 맞춤 건강 제품 추천

각 추천 제품은 한 단락의 서술식으로 작성하세요. 다음을 자연스럽게 녹여 쓰고, 제품 간 중복을 피하세요:
- 분류기준 테이블의 주요 원료와 각 원료의 구체적 효과(해당 건강지표와의 연계 포함)
- 식약처 인정 기능성, 주요 특징, 원재료(제품정보 테이블)
+ - 해당 제품에 매칭된 건강지표와 관리 필요 영역을 문장 속에서 분명히 언급
 - 사용자 관심 영역과의 연결 및 적용 포인트
 - 동일한 문장/표현/근거 반복 금지

## 📋 개인별 건강 관리 방향

선택된 관심 영역과 제품들의 연관성을 원료 중심으로 설명하고, 장기적인 건강 관리 전략을 원료의 효과와 연결하여 제시해주세요.

설명은 예방 의학적 관점에서 전문적이면서도 이해하기 쉽게 작성해주세요.
"""

        try:
            # 캐시 조회
            cache_payload = {
                "model": "llama-3.3-70b-versatile",
                "system": "당신은 예방 의학 전문가입니다.",
                "prompt": prompt,
                "temperature": 0.4,
            }
            cache_key = self._build_cache_key(cache_payload, prefix="goodhealth")
            cached = self._read_cache(cache_key)
            if cached:
                return cached.strip()

            chat_completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "당신은 예방 의학 전문가입니다. 건강한 사용자에게 건강 유지 및 예방을 위한 제품 추천 근거를 논리적으로 설명해주세요."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,  # 토큰 절감(내용 유지)
                temperature=0.4   # 자연스러운 표현
            )
            
            content = chat_completion.choices[0].message.content.strip()
            self._write_cache(cache_key, content)
            return content
            
        except Exception as e:
            return f"건강 유지 추천 근거 생성 중 오류가 발생했습니다: {str(e)}"





    def format_recommendations(self, result_df: pd.DataFrame, llm_explanation: str = "") -> str:
        """추천 결과를 웹 페이지용 텍스트로 포맷팅"""
        if result_df.empty:
            return "추천할 제품이 없습니다."
        
        formatted_output = ""
        
        # LLM 설명이 있으면 먼저 표시 (진단 + 추천 로직 + 기본 제품 + 보강 제품 + 개인별 관리 방향)
        if llm_explanation:
            formatted_output += f"{llm_explanation}\n\n"
        
        return formatted_output