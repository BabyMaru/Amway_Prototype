def get_css_styles():
    return """
    <style>
        .chat-input {
            position: fixed;
            bottom: 2rem;
            width: 100%;
        }
        .chat-box {
            margin-bottom: 6rem;
        }
        .center-logo {
            display: flex;
            justify-content: center;
            margin-top: 2rem;
            margin-bottom: 2rem;
        }
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
            min-height: 70px;
        }
        .shopping-link {
            display: flex;
            align-items: flex-start;
            margin-top: 0px;
            margin-left: 15px
        }
        .shopping-link a {
            text-decoration: none !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s ease;
            box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
            white-space: nowrap;
            display: inline-block;
            vertical-align: top;
        }
        
        /* Streamlit 이미지와 컬럼의 기본 마진/패딩 제거 */
        [data-testid="column"] > div {
            padding-top: 0 !important;
        }
        
        [data-testid="stImage"] {
            margin-top: 0 !important;
            padding-top: 0 !important;
        }
        
        .top-brand {
            display: flex;
            align-items: flex-start;
            font-size: 30px;
            font-weight: 700;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-top: 10px;
            margin-bottom: 20px;
            padding-top: 0;
        }
        .shopping-link a:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
        }
        .header-container {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 30px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .main-title {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
            text-align: center;
        }
        .subtitle {
            font-size: 1.1rem !important;
            color: #4a5568;
            font-weight: 500;
            text-align: center;
            margin-bottom: 20px;
        }
        .description {
            font-size: 1rem;
            color: #718096;
            line-height: 1.6;
            text-align: center;
            background: rgba(255, 255, 255, 0.7);
            padding: 15px 20px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
        }
        .health-indicators {
            display: inline-block;
            # background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            # -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 550;
            color: black;
        }
        .header-text {
            flex: 1;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            margin-left: 0px;
        }
        .section-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 600;
            font-size: 0.5rem;
            margin-bottom: 20px;
            white-space: nowrap;
        }
        .logo-center {
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 20px 0;
            width: 100%;
        }
        .logo-center img {
            border-radius: 15px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.15);
            transition: transform 0.3s ease;
        }
        .logo-center img:hover {
            transform: scale(1.05);
        }
        .top-row {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            width: 100%;
            margin-bottom: 20px;
        }
        .top-logo {
            display: flex;
            align-items: flex-start;
        }
        .top-logo img {
            height: 35px;
            width: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        .loading-spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .loading-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 200px;
        }
        .loading-content {
            text-align: center;
        }
        .loading-text {
            color: #666;
            font-size: 16px;
            margin-top: 20px;
        }
        .health-status-container {
            margin: 20px 0;
            padding: 15px;
            background-color: #fafafa;
            border-radius: 10px;
        }
        .health-status-title {
            margin-bottom: 15px;
            color: black !important;
        }
        .health-status-grid {
            display: flex;
            gap: 15px;
            justify-content: space-between;
        }
        .health-status-item {
            flex: 1;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
        }
        .health-status-icon {
            font-size: 24px;
            margin-bottom: 5px;
        }
        .health-status-label {
            font-weight: bold;
            font-size: 14px;
        }
        .health-status-value {
            font-size: 16px;
            font-weight: bold;
            margin-top: 5px;
        }
        .status-warning {
            background-color: #ffebee;
            border: 2px solid #f44336;
            color: #d32f2f;
        }
        .status-good {
            background-color: #e8f5e8;
            border: 2px solid #4caf50;
            color: #2e7d32;
        }
        .status-unselected {
            background-color: #f5f5f5;
            border: 2px solid #ccc;
            color: #666;
        }
        .section-header-load {
            font-size: 1.8rem !important;
            font-weight: 600 !important;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            -webkit-background-clip: text !important;
            # -webkit-text-fill-color: transparent !important;
            background-clip: text !important;
            margin-bottom: 6px !important;
            display: block !important;
        }
        /* 멀티셀렉트 선택된 항목 배경색 */
        .stMultiSelect [data-baseweb="tag"] {
            background-color: #139e39 !important;
            color: white !important;
        }
        
        /* 멀티셀렉트 드롭다운 옵션 배경색 */
        .stMultiSelect [data-baseweb="popover"] [role="option"] {
            background-color: #139e39 !important;
            color: white !important;
        }
        
        /* 멀티셀렉트 드롭다운 옵션 호버 효과 */
        .stMultiSelect [data-baseweb="popover"] [role="option"]:hover {
            background-color: #003d7a !important;
            color: white !important;
        }
        
        /* 셀렉트박스 옵션 배경색 */
        .stSelectbox [data-baseweb="popover"] [role="option"] {
            background-color: #002F5F !important;
            color: white !important;
        }
        
        /* 셀렉트박스 옵션 호버 효과 */
        .stSelectbox [data-baseweb="popover"] [role="option"]:hover {
            background-color: #003d7a !important;
            color: white !important;
        }
    </style>
    """