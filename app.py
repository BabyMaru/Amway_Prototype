import os
import requests
import streamlit as st
from dotenv import load_dotenv
from styles import get_css_styles
from prompts import create_health_assessment, parse_health_keywords, get_system_message
from data import HealthRAGSystem

# Streamlit secrets에서 API 키 가져오기
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except KeyError:
    # 로컬 개발용 fallback
    load_dotenv()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

# API 키 없을 경우 경고
if not GROQ_API_KEY:
    st.error("⚠️ GROQ_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")
    st.stop()

# Streamlit 설정
st.set_page_config(
    page_title="GROQ 챗봇 데모", 
    layout="centered",
    page_icon="amway_logo.png"
)

# CSS 스타일
st.markdown(get_css_styles(), unsafe_allow_html=True)

# 헤더 레이아웃

# 상단 브랜드 이미지와 쇼핑몰 링크
col1, col2 = st.columns([3, 1])
with col1:
    st.image("amway.png", width=120)
with col2:
    st.markdown('<div style="text-align: right;"><div class="shopping-link"><a href="https://www.amway.co.kr/shop/c/shop" target="_blank">🛒&nbsp;쇼핑몰&nbsp;바로가기</a></div></div>', unsafe_allow_html=True)



# 메인 헤더 컨테이너
st.markdown("""
<div class="header-container">
    <p class="subtitle">🌟 건강제품 추천 서비스</p>
    <div class="description">
        <span class="health-indicators">🧬 노화 억제 분석지수</span>, 
        <span class="health-indicators">💪 근육 밸런스 분석지수</span>, 
        <span class="health-indicators">🏥 만성질환 억제 분석지수</span><br>
        선택하신 후에 추가로 필요한 건강 지표를 입력해주세요.
    </div>
</div>
""", unsafe_allow_html=True)

# 채팅 히스토리 저장
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# OCR 결과 저장용 세션 상태 초기화
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None

# 점수를 기반으로 건강 상태 분류하는 함수
def score_to_status(score):
    """점수를 기반으로 건강 상태를 분류"""
    if score >= 70:
        return "좋음"
    elif score >= 60:
        return "관리"
    else:
        return "주의"

# PDF 업로드 및 저장된 데이터 불러오기 섹션
col_upload, col_saved = st.columns(2)

with col_upload:
    st.markdown('<h2 class="section-header-load">📄 건강 검진 결과 업로드</h2>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "건강 검진 결과 PDF 파일을 업로드하세요",
        type=['pdf'],
        help="PDF 파일을 업로드하면 자동으로 건강 지표를 분석합니다."
    )

with col_saved:
    st.markdown('<h2 class="section-header-load">💾 저장된 데이터 불러오기</h2>', unsafe_allow_html=True)
    
    # person_data.json에서 age 값들 로드
    try:
        import json
        with open('person_data.json', 'r', encoding='utf-8') as f:
            person_data = json.load(f)
        
        # age 값들을 옵션으로 생성
        age_options = ["선택하세요"] + [f"{person['age']}세" for person in person_data]
        
        selected_age = st.selectbox(
            "저장된 건강 데이터를 선택하세요",
            age_options,
            help="미리 저장된 건강 데이터를 불러와서 자동으로 건강 지표를 계산합니다."
        )
        
        # 선택된 age에 해당하는 데이터로 건강 지표 계산
        if selected_age != "선택하세요":
            selected_age_num = int(selected_age.replace("세", ""))
            
            # 해당 age의 데이터 찾기
            selected_person_data = None
            for person in person_data:
                if person['age'] == selected_age_num:
                    selected_person_data = person
                    break
            
            if selected_person_data:
                # calculate.py를 사용하여 건강 지표 계산
                try:
                    # calculate.py에서 필요한 추가 데이터 설정
                    calc_data = selected_person_data.copy()
                    
                    # calculate.py에서 필요하지만 person_data.json에 없는 필드들을 기본값으로 설정
                    calc_data.setdefault('pack_year', calc_data.get('smok_dur', 0) * 0.5)  # 대략적인 추정
                    calc_data.setdefault('met', 3.8)  # 기본값
                    calc_data.setdefault('rfs', 27.3)  # 기본값
                    calc_data.setdefault('eq5d', 0.89)  # 기본값
                    calc_data.setdefault('asm', calc_data.get('skeletal_muscle_mass', 0))  # ASM = 골격근량
                    
                    # calculate.py의 함수들 import 및 실행
                    from calculate import calculate_three_indices
                    
                    health_indices = calculate_three_indices(calc_data)
                    
                    # 계산 결과 표시
                    st.success(f"✅ {selected_age} 데이터의 건강 지표가 계산되었습니다!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🧬 노화 점수", f"{health_indices['노화 억제 분석지수']:.0f}점")
                    with col2:
                        st.metric("💪 근육 점수", f"{health_indices['근육 밸런스 분석지수']:.0f}점")
                    with col3:
                        st.metric("🏥 만성질환 점수", f"{health_indices['만성질환 억제 분석지수']:.0f}점")
                    
                    # 세션 상태에 계산된 값들 저장 (자동 선택용)
                    # 기존 OCR 결과 초기화 (저장된 데이터가 우선)
                    if 'auto_aging' in st.session_state:
                        del st.session_state.auto_aging
                    if 'auto_muscle' in st.session_state:
                        del st.session_state.auto_muscle
                    if 'auto_chronic' in st.session_state:
                        del st.session_state.auto_chronic
                    
                    # 계산된 값들을 세션 상태에 저장
                    st.session_state.calc_aging = score_to_status(health_indices['노화 억제 분석지수'])
                    st.session_state.calc_chronic = score_to_status(health_indices['만성질환 억제 분석지수'])
                    st.session_state.calc_muscle = score_to_status(health_indices['근육 밸런스 분석지수'])
                    st.session_state.calc_selected_age = selected_age_num
                    
                    # 자동 선택 안내 메시지
                    st.info("📋 아래 건강 지표가 자동으로 선택됩니다.")
                    
                except Exception as e:
                    st.error(f"❌ 건강 지표 계산 중 오류가 발생했습니다: {str(e)}")
            else:
                st.error("❌ 선택된 나이의 데이터를 찾을 수 없습니다.")
                
    except FileNotFoundError:
        st.error("❌ person_data.json 파일을 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"❌ 데이터 로드 중 오류가 발생했습니다: {str(e)}")

if uploaded_file is not None:
    # 업로드된 파일을 임시로 저장
    with open("temp_uploaded.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.success(f"✅ {uploaded_file.name} 파일이 업로드되었습니다.")
    
    # OCR 처리 버튼
    if st.button("🔍 건강 지표 자동 분석", type="primary"):
        with st.spinner("PDF에서 건강 지표를 분석하고 있습니다..."):
            try:
                # OCR 스크립트 실행 (stdout으로 결과 받기)
                import subprocess
                import json
                
                # ocr_pdf.py 실행 (결과를 stdout으로 받음)
                result = subprocess.run([
                    "python", "ocr_pdf.py", "temp_uploaded.pdf"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    # stdout에서 JSON 결과 파싱
                    ocr_result = json.loads(result.stdout.strip())
                    
                    st.success("✅ 건강 지표 분석이 완료되었습니다!")
                    
                    # 분석 결과 표시
                    st.markdown("### 📊 분석된 건강 지표")
                    col1, col2, col3 = st.columns(3)
                    
                    aging_score = ocr_result.get('노화억제분석지수', 0)
                    chronic_score = ocr_result.get('만성질환억제분석지수', 0)
                    muscle_score = ocr_result.get('근육밸런스지수', 0)
                    
                    with col1:
                        st.metric("🧬 노화억제분석지수", f"{aging_score:.0f}점")
                    with col2:
                        st.metric("🏥 만성질환억제분석지수", f"{chronic_score:.0f}점")
                    with col3:
                        st.metric("💪 근육밸런스지수", f"{muscle_score:.0f}점")
                    
                    # 영향준요인들 표시
                    factors = ocr_result.get('영향준요인들', [])
                    if factors:
                        st.markdown("### 🎯 주요 영향 요인")
                        for factor in factors:
                            st.markdown(f"• {factor}")
                    
                    # 세션 상태에 OCR 결과와 자동 선택값 저장
                    st.session_state.ocr_result = ocr_result
                    st.session_state.auto_aging = score_to_status(aging_score)
                    st.session_state.auto_muscle = score_to_status(muscle_score)
                    st.session_state.auto_chronic = score_to_status(chronic_score)
                    st.session_state.auto_factors = factors
                    
                    # 자동 선택 안내 메시지
                    st.info("📋 아래 건강 지표가 자동으로 선택됩니다. 페이지를 새로고침하여 확인하세요.")
                    
                    # 페이지 새로고침으로 자동 선택 적용
                    st.rerun()
                    
                else:
                    st.error(f"❌ OCR 처리 중 오류가 발생했습니다: {result.stderr}")
                    
            except Exception as e:
                st.error(f"❌ 파일 처리 중 오류가 발생했습니다: {str(e)}")

st.markdown('<br>', unsafe_allow_html=True)

# 건강 지표 선택
st.markdown('<h2 class="section-header-load">🩺 건강 지표 입력</h2>', unsafe_allow_html=True)

# OCR 결과가 있으면 자동 선택, 없으면 수동 선택
options = ["선택해주세요", "주의", "관리", "좋음"]

col1, col2, col3 = st.columns(3)
with col1:
    # 자동 선택값이 있으면 해당 인덱스로 설정 (OCR 결과 또는 계산된 결과)
    auto_aging_value = None
    if hasattr(st.session_state, 'auto_aging') and st.session_state.auto_aging:
        auto_aging_value = st.session_state.auto_aging
    elif hasattr(st.session_state, 'calc_aging') and st.session_state.calc_aging:
        auto_aging_value = st.session_state.calc_aging
    
    # 자동 선택값이 있으면 해당 인덱스로 설정, 없으면 첫 번째 옵션(선택해주세요)을 기본값으로
    auto_aging_idx = 0  # 기본값: "선택해주세요"
    if auto_aging_value and auto_aging_value in options:
        auto_aging_idx = options.index(auto_aging_value)
    
    age_sup = st.selectbox(
        "🧬 노화 억제 분석지수", 
        options, 
        index=auto_aging_idx, 
        key="aging_selectbox"
    )

with col2:
    # 자동 선택값이 있으면 해당 값으로 설정
    auto_muscle_value = None
    if hasattr(st.session_state, 'auto_muscle') and st.session_state.auto_muscle:
        auto_muscle_value = st.session_state.auto_muscle
    elif hasattr(st.session_state, 'calc_muscle') and st.session_state.calc_muscle:
        auto_muscle_value = st.session_state.calc_muscle
    
    # 자동 선택값이 있으면 해당 인덱스로 설정, 없으면 첫 번째 옵션(선택해주세요)을 기본값으로
    auto_muscle_idx = 0  # 기본값: "선택해주세요"
    if auto_muscle_value and auto_muscle_value in options:
        auto_muscle_idx = options.index(auto_muscle_value)
    
    muscle_bal = st.selectbox(
        "💪 근육 밸런스 분석지수", 
        options, 
        index=auto_muscle_idx, 
        key="muscle_selectbox"
    )

with col3:
    # 자동 선택값이 있으면 해당 값으로 설정
    auto_chronic_value = None
    if hasattr(st.session_state, 'auto_chronic') and st.session_state.auto_chronic:
        auto_chronic_value = st.session_state.auto_chronic
    elif hasattr(st.session_state, 'calc_chronic') and st.session_state.calc_chronic:
        auto_chronic_value = st.session_state.calc_chronic
    
    # 자동 선택값이 있으면 해당 인덱스로 설정, 없으면 첫 번째 옵션(선택해주세요)을 기본값으로
    auto_chronic_idx = 0  # 기본값: "선택해주세요"
    if auto_chronic_value and auto_chronic_value in options:
        auto_chronic_idx = options.index(auto_chronic_value)
    
    chronic = st.selectbox(
        "🏥 만성질환 억제 분석지수", 
        options, 
        index=auto_chronic_idx, 
        key="chronic_selectbox"
    )

# 추가 건강 지표 선택
st.markdown('<br>', unsafe_allow_html=True)

# 현재 선택된 건강지표 상태 확인
current_assessments = {
    "노화 억제 분석지수": age_sup,
    "근육 밸런스 분석지수": muscle_bal,
    "만성질환 억제 분석지수": chronic
}

# 주의/관리 상태인 건강지표만 필터링
problematic_indicators = [k for k, v in current_assessments.items() if v in ["주의", "관리"]]

# 전체 키워드 옵션
all_physiology_options = ['운동수행능력/지구력 향상', '항산화', '수면 건강', '혈당 조절', '눈 건강', '영양 균형', 
 '기억력 개선', '혈중 지질 개선', '혈행 개선', '근력(근육)', '피부 건강', '갱년기 여성 건강', '간 건강', '체지방 감소',
  '장 건강', '면역 기능', '피로 개선', '전립선 건강', '코 과민반응', '위 건강', '관절/뼈 건강', '과민 피부 상태 개선', '혈압 조절']

all_health_concern_options = ['운동수행능력/지구력 향상', '항산화', '수면 건강', '혈당 조절', '눈 건강', '영양 균형',
 '기억력 개선', '혈중 지질 개선', '혈행 개선', '근력(근육)', '피부 건강', '갱년기 여성 건강', '간 건강', '체지방 감소',
  '장 건강', '면역 기능', '피로 개선', '전립선 건강', '코 과민반응', '위 건강', '관절/뼈 건강', '과민 피부 상태 개선', '혈압 조절']

# 주의/관리 상태인 건강지표에 연관된 키워드만 필터링
filtered_physiology_options = []
filtered_health_concern_options = []

if problematic_indicators:
    try:
        # 데이터베이스에서 건강지표와 연관된 관리영역 조회
        health_system = HealthRAGSystem(GROQ_API_KEY)
        health_relationships = health_system.get_health_indicator_relationships()
        
        # 주의/관리 상태인 건강지표와 연관된 관리영역들 수집
        relevant_areas = []
        for indicator in problematic_indicators:
            if indicator in health_relationships:
                relevant_areas.extend(health_relationships[indicator])
        
        # 중복 제거
        relevant_areas = list(set(relevant_areas))
        
        # 연관된 영역만 필터링
        filtered_physiology_options = [option for option in all_physiology_options if option in relevant_areas]
        filtered_health_concern_options = [option for option in all_health_concern_options if option in relevant_areas]
        
    except Exception as e:
        # 오류 발생 시 전체 옵션 사용
        filtered_physiology_options = all_physiology_options
        filtered_health_concern_options = all_health_concern_options
else:
    # 모든 건강지표가 "좋음"이거나 미선택인 경우 전체 옵션 사용
    filtered_physiology_options = all_physiology_options
    filtered_health_concern_options = all_health_concern_options

# OCR 결과에서 영향준요인들을 기본값으로 설정 (필터링된 옵션 내에서만)
auto_factors = []
auto_health_concerns = []
if hasattr(st.session_state, 'auto_factors') and st.session_state.auto_factors:
    # OCR 결과의 영향준요인들을 필터링된 옵션에 있는 것만 선택
    auto_factors = [factor for factor in st.session_state.auto_factors if factor in filtered_physiology_options]
    auto_health_concerns = [factor for factor in st.session_state.auto_factors if factor in filtered_health_concern_options]

# 상태 메시지 표시
if problematic_indicators:
    st.info(f"💡 '{', '.join(problematic_indicators)}' 상태에 연관된 건강 관리 영역만 표시됩니다.")
else:
    st.info("💡 건강지표를 '주의' 또는 '관리'로 선택하시면 관련 건강 관리 영역이 자동으로 필터링됩니다.")

physiology_network = st.multiselect(
    "🧠 인체 생리 네트워크",
    filtered_physiology_options,
    default=auto_factors,
    placeholder="주의가 필요한 건강 지표를 선택해주세요."
)

health_concerns = st.multiselect(
    "⚠️ 고려하고 싶은 건강 분야",
    filtered_health_concern_options,
    default=auto_health_concerns,
    placeholder="신경 써야 할 건강 지표를 선택해주세요."
)

# 채팅 입력
st.markdown('<div class="chat-box">', unsafe_allow_html=True)
user_input = st.chat_input("어떤 성분이 함유된 제품을 추천받고 싶은지 작성해주세요.")
st.markdown('</div>', unsafe_allow_html=True)

# 채팅 히스토리 출력 (항상 표시)
for sender, msg in st.session_state.chat_history:
    if sender == "user":
        st.chat_message("user").markdown(msg)
    else:
        st.chat_message("assistant").markdown(msg, unsafe_allow_html=True)

# 채팅 응답 처리
if user_input:
    # 사용자 입력을 즉시 표시
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    # 건강 지표가 모두 선택되었는지 확인 ("선택해주세요"는 미선택으로 처리)
    valid_selections = [age_sup, muscle_bal, chronic]
    if not all(valid_selections) or any(selection == "선택해주세요" for selection in valid_selections):
        reply = "⚠️ 모든 건강 지표(노화 억제 분석지수, 근육 밸런스 분석지수, 만성질환 억제 분석지수)를 선택해주세요."
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.session_state.chat_history.append(("bot", reply))
    else:
        # 로딩 상태 표시
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            st.markdown("""
            <div class="loading-container">
                <div class="loading-content">
                    <div class="loading-spinner"></div>
                    <p class="loading-text">건강 제품을 추천하고 있습니다...</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        try:
            # HealthRAGSystem 초기화
            health_system = HealthRAGSystem(GROQ_API_KEY)
            
            # 건강 평가 생성
            assessments = create_health_assessment(age_sup, muscle_bal, chronic)
            
            # 사용자 데이터 가져오기 (저장된 데이터가 있는 경우)
            user_data = None
            if hasattr(st.session_state, 'calc_selected_age'):
                # person_data.json에서 해당 나이의 데이터 찾기
                try:
                    import json
                    with open('person_data.json', 'r', encoding='utf-8') as f:
                        person_data = json.load(f)
                    
                    for person in person_data:
                        if person['age'] == st.session_state.calc_selected_age:
                            user_data = person
                            break
                except Exception as e:
                    pass  # 데이터 로드 실패 시 user_data는 None으로 유지
            
            # 새로운 추천 로직 사용 (DataFrame과 LLM 설명을 함께 받음)
            result_df, llm_explanation = health_system.recommend_products(
                assessments=assessments,
                physiology_network=physiology_network,
                health_concerns=health_concerns,
                user_input=user_input,
                user_data=user_data
            )
            
            # 결과 포맷팅 (LLM 설명 포함)
            reply = health_system.format_recommendations(result_df, llm_explanation)
            
        except Exception as e:
            reply = f"⚠️ 제품 추천 중 오류가 발생했습니다: {str(e)}"
        
        # 로딩 화면 제거
        loading_placeholder.empty()
        
        # 건강 지표 입력 상태 표시 함수
        def create_health_status_display(age_sup, muscle_bal, chronic):
            """건강 지표 입력 상태를 시각적으로 표시"""
            
            def get_status_class(status):
                if status in ["주의", "관리"]:
                    return "status-warning"
                elif status == "좋음":
                    return "status-good"
                else:
                    return "status-unselected"
            
            def get_status_icon(status):
                if status in ["주의", "관리"]:
                    return "⚠️" if status == "주의" else "⚡"
                elif status == "좋음":
                    return "✅"
                else:
                    return "❓"
            
            status_html = f"""
<div class="health-status-container">
    <h4 class="health-status-title">📊 선택하신 건강 지표</h4>
    <div class="health-status-grid">
        <div class="health-status-item {get_status_class(age_sup)}">
            <div class="health-status-icon">{get_status_icon(age_sup)}</div>
            <div class="health-status-label">🧬 노화 억제 분석지수</div>
            <div class="health-status-value">{age_sup or '미선택'}</div>
        </div>
        <div class="health-status-item {get_status_class(muscle_bal)}">
            <div class="health-status-icon">{get_status_icon(muscle_bal)}</div>
            <div class="health-status-label">💪 근육 밸런스 분석지수</div>
            <div class="health-status-value">{muscle_bal or '미선택'}</div>
        </div>
        <div class="health-status-item {get_status_class(chronic)}">
            <div class="health-status-icon">{get_status_icon(chronic)}</div>
            <div class="health-status-label">🏥 만성질환 억제 분석지수</div>
            <div class="health-status-value">{chronic or '미선택'}</div>
        </div>
    </div>
</div>

"""
            return status_html
        
        # 건강 지표 상태를 제품 추천 결과와 함께 포함
        health_status_html = create_health_status_display(age_sup, muscle_bal, chronic)
        complete_reply = health_status_html + reply
        
        # 실시간 스트리밍 응답 표시
        def stream_response(text):
            import time
            import re
            
            # 마크다운 구조를 유지하면서 스트리밍하기 위해 줄 단위로 분할
            lines = text.split('\n')
            accumulated_text = ""
            
            for line in lines:
                accumulated_text += line + '\n'
                yield accumulated_text
                
                # 헤더나 구분선이 아닌 일반 텍스트 줄의 경우 추가 딜레이
                if line.strip() and not line.startswith('#') and not line.startswith('**') and line.strip() != '---':
                    time.sleep(0.3)  # 일반 텍스트 줄 딜레이
                else:
                    time.sleep(0.1)  # 헤더/포맷팅 줄 딜레이
        
        # 스트리밍 응답 표시
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            
            for partial_response in stream_response(complete_reply):
                response_placeholder.markdown(partial_response, unsafe_allow_html=True)
        
        # 응답 추가 (전체 응답 - 건강 지표 상태 포함)
        st.session_state.chat_history.append(("bot", complete_reply))
        
        # 페이지 새로고침으로 채팅 히스토리 업데이트
        st.rerun()
