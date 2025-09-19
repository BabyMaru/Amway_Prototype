import os, re, json, argparse
from typing import List, Tuple, Dict, Optional
import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw
import cv2
import difflib

# 공통 유틸
def pdf_render_page(doc: fitz.Document, page_idx: int, zoom: float = 3.0) -> Image.Image:
    page = doc[page_idx]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

def norm2abs(box: Tuple[float, float, float, float], w: int, h: int) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return (int(round(x0 * w)), int(round(y0 * h)), int(round(x1 * w)), int(round(y1 * h)))

def crop_by_ratio(img: Image.Image, roi: Tuple[float, float, float, float]) -> Image.Image:
    w, h = img.size
    x0, y0, x1, y1 = norm2abs(roi, w, h)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return img.copy()
    return img.crop((x0, y0, x1, y1))

def expand_roi(roi: Tuple[float, float, float, float], dy: float = 0.03, dx: float = 0.0) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = roi
    x0 = max(0.0, x0 - dx)
    x1 = min(1.0, x1 + dx)
    y0 = max(0.0, y0 - dy)
    y1 = min(1.0, y1 + dy)
    return (x0, y0, x1, y1)

def save_debug_overlay(base: Image.Image, rois: Dict[str, Tuple[float, float, float, float]], out_path: str):
    img = base.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size
    colors = ["#ff3b30", "#34c759", "#007aff", "#ffcc00", "#5856d6"]
    for i, (name, r) in enumerate(rois.items()):
        x0, y0, x1, y1 = norm2abs(r, w, h)
        draw.rectangle([x0, y0, x1, y1], outline=colors[i % len(colors)], width=4)
        draw.text((x0 + 6, y0 + 6), name, fill=colors[i % len(colors)])
    img.save(out_path)

def preprocess_for_digits(img: Image.Image) -> np.ndarray:
    g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    white_ratio = (bw == 255).mean()
    if white_ratio < 0.5:
        bw = 255 - bw
    kernel = np.ones((2, 2), np.uint8)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=1)
    return bw

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

# EasyOCR 로더 (GPU/CPU 폴백)
_READER = None
def get_reader(prefer_cuda: bool = False):
    global _READER
    if _READER is not None:
        return _READER
    import easyocr
    try:
        _READER = easyocr.Reader(['ko', 'en'], gpu=prefer_cuda)
    except Exception:
        _READER = easyocr.Reader(['ko', 'en'], gpu=False)
    return _READER

# 5페이지: 점수 OCR
DEFAULT_SCORE_ROIS = {
    "노화억제분석지수":   (0.08, 0.37, 0.30, 0.63),
    "만성질환억제분석지수": (0.39, 0.37, 0.61, 0.63),
    "근육밸런스지수":     (0.70, 0.37, 0.92, 0.63)
}

def parse_first_score(easyocr_detail: List) -> Optional[int]:
    best_val, best_conf = None, -1.0
    for item in easyocr_detail:
        try:
            _, t, conf = item
        except Exception:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                t = str(item[1]); conf = float(item[2]) if len(item) > 2 else 0.0
            else:
                continue
        t = normalize_space(str(t))
        m = re.search(r"(\d{1,3})\s*[\n\r\s]*점?", t, flags=re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 0 <= val <= 100 and conf >= best_conf:
                best_val, best_conf = val, conf
    return best_val

def ocr_score_from_roi(img_roi: Image.Image, reader) -> float:
    bw = preprocess_for_digits(img_roi)
    detail = reader.readtext(bw, detail=1, paragraph=False, allowlist="0123456789점")
    cand = parse_first_score(detail)
    if cand is not None:
        return float(cand)
    detail = reader.readtext(np.array(img_roi), detail=1, paragraph=False, allowlist="0123456789점")
    cand = parse_first_score(detail)
    return float(cand) if cand is not None else 0.0

def extract_page5_scores(page_img: Image.Image, prefer_cuda: bool, debug_dir: Optional[str] = None) -> Dict[str, float]:
    reader = get_reader(prefer_cuda)
    results = {k: 0.0 for k in DEFAULT_SCORE_ROIS.keys()}
    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        save_debug_overlay(page_img, DEFAULT_SCORE_ROIS, os.path.join(debug_dir, "p5_rois.png"))
    for label, roi in DEFAULT_SCORE_ROIS.items():
        crop = crop_by_ratio(page_img, roi)
        score = ocr_score_from_roi(crop, reader)
        if score == 0.0:
            crop2 = crop_by_ratio(page_img, expand_roi(roi, dy=0.05, dx=0.0))
            score = ocr_score_from_roi(crop2, reader)
        if score == 0.0:
            crop3 = crop_by_ratio(page_img, expand_roi(roi, dy=0.10, dx=0.0))
            score = ocr_score_from_roi(crop3, reader)
        results[label] = float(score)
    return results

# 20페이지: 양쪽 사이드의 '빨간' 제목만 추출 (벡터 우선)
LEFT_MAX_FRAC  = 0.35     # 좌측 밴드 x 비율
RIGHT_MIN_FRAC = 0.65     # 우측 밴드 x 비율
TOP_FRAC, BOT_FRAC = 0.10, 0.97  # 상/하 여백 약간 넓힘

def _span_rgb(color_int: int) -> Tuple[int,int,int]:
    return ((color_int >> 16) & 255, (color_int >> 8) & 255, color_int & 255)

def _is_red_hsv(rgb: Tuple[int,int,int]) -> bool:
    # 노랑/주황 배제, 연한 톤도 일정 수준 허용
    import colorsys
    r, g, b = rgb
    if r < 130 or r <= g + 10 or r <= b + 10:
        return False
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    H, S, V = h * 360.0, s * 255.0, v * 255.0
    return ((H <= 15.0) or (H >= 345.0)) and (S >= 65.0) and (V >= 48.0)

def _inside_side_band(cx: float, cy: float, pw: float, ph: float) -> bool:
    if not (TOP_FRAC*ph <= cy <= BOT_FRAC*ph):
        return False
    xf = cx / pw
    return (xf <= LEFT_MAX_FRAC) or (xf >= RIGHT_MIN_FRAC)

def _merge_multiline(items: List[Dict]) -> List[str]:
    if not items:
        return []
    items = sorted(items, key=lambda d: ( (d['bbox'][1]+d['bbox'][3])/2.0, d['bbox'][0] ))
    merged, cur = [], None

    def overlap_ratio(a, b):
        ax0, _, ax1, _ = a; bx0, _, bx1, _ = b
        inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        uni   = max(ax1, bx1) - min(ax0, bx0) + 1e-6
        return inter/uni

    for it in items:
        t, (x0,y0,x1,y1) = it['text'], it['bbox']
        yc = (y0+y1)/2.0
        if cur is None:
            cur = {'text': t, 'bbox': [x0,y0,x1,y1]}
            continue
        _, cy0, _, cy1 = cur['bbox']
        cur_h = max(1.0, cy1 - cy0)
        close_y = abs(yc - (cy0+cy1)/2.0) <= 1.8 * cur_h  # 더 관대
        ov = overlap_ratio(cur['bbox'], (x0,y0,x1,y1))
        if close_y and ov >= 0.25:                         # 더 관대
            cur['text'] = normalize_space(cur['text'] + " " + t)
            cur['bbox'][0] = min(cur['bbox'][0], x0)
            cur['bbox'][1] = min(cur['bbox'][1], y0)
            cur['bbox'][2] = max(cur['bbox'][2], x1)
            cur['bbox'][3] = max(cur['bbox'][3], y1)
        else:
            merged.append(cur['text'])
            cur = {'text': t, 'bbox': [x0,y0,x1,y1]}
    if cur is not None:
        merged.append(cur['text'])

    clean, seen = [], set()
    for s in merged:
        s = normalize_space(re.sub(r"\s*/\s*", "/", s.replace("\n", " ")))
        if s and s not in seen:
            seen.add(s); clean.append(s)
    return clean

def _canonicalize(texts: List[str]) -> List[str]:
    """
    벡터/이미지 경로 결과를 표준 라벨로 보정.
    """
    wanted = ["운동수행능력/지구력 향상", "근력(근육)", "영양균형"]
    bag = set()

    # 1) 부분 문자열 룰
    for t in (normalize_space(x) for x in texts):
        n = re.sub(r"\s+", "", t)
        if "영양" in n:
            bag.add("영양균형")
        if ("근력" in n) or ("근육" in n):
            bag.add("근력(근육)")
        if (("운동수행" in n) or ("수행능력" in n) or ("동수행" in n) or ("운동수행능력" in n)) and (("지구력" in n) or ("지구" in n)):
            bag.add("운동수행능력/지구력 향상")
        if "운동수행능력/지구력향상" in n:
            bag.add("운동수행능력/지구력 향상")

    # 2) 퍼지 매칭(혹시 OCR 조각이 애매할 때)
    for t in texts:
        for target in wanted:
            if difflib.SequenceMatcher(None, re.sub(r"\s+","",t), re.sub(r"\s+","",target)).ratio() >= 0.55:
                bag.add(target)

    # 원하는 순서
    return [x for x in wanted if x in bag]

def extract_side_red_text_from_vector(page: fitz.Page) -> List[str]:
    info = page.get_text("dict")
    pw, ph = float(page.rect.width), float(page.rect.height)
    items = []
    for block in info.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            red_spans = []
            for sp in spans:
                x0, y0, x1, y1 = sp.get("bbox", (0,0,0,0))
                cx, cy = (x0+x1)/2.0, (y0+y1)/2.0
                if not _inside_side_band(cx, cy, pw, ph):
                    continue
                rgb = _span_rgb(int(sp.get("color", 0)))
                if _is_red_hsv(rgb):
                    red_spans.append(sp)
            if not red_spans:
                continue
            text = normalize_space("".join(sp.get("text","") for sp in red_spans))
            xs = [sp.get("bbox",(0,0,0,0))[0] for sp in red_spans] + [sp.get("bbox",(0,0,0,0))[2] for sp in red_spans]
            ys = [sp.get("bbox",(0,0,0,0))[1] for sp in red_spans] + [sp.get("bbox",(0,0,0,0))[3] for sp in red_spans]
            x0, x1 = min(xs), max(xs); y0, y1 = min(ys), max(ys)
            if text:
                items.append({'text': text, 'bbox': (x0,y0,x1,y1)})
    return _merge_multiline(items)

# 이미지(OCR) 백업 경로
def mask_red_regions(img: Image.Image) -> np.ndarray:
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 80, 50], dtype=np.uint8)
    upper1 = np.array([15,255,255], dtype=np.uint8)
    lower2 = np.array([165,80,50], dtype=np.uint8)
    upper2 = np.array([179,255,255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8), 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  np.ones((3,3), np.uint8), 1)
    return mask

def _prep_for_ocr(crop_bgr: np.ndarray) -> np.ndarray:
    # 대비 향상 + 2배 업샘플 + 그레이 + Otsu
    lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
    l,a,b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l = clahe.apply(l)
    lab = cv2.merge([l,a,b])
    enh = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    up = cv2.resize(enh, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    return bw

def ocr_on_mask(img: Image.Image, mask: np.ndarray, prefer_cuda: bool) -> List[str]:
    reader = get_reader(prefer_cuda)
    img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    texts = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w*h < 600:
            continue
        crop_bgr = img_np[y:y+h, x:x+w]
        bw = _prep_for_ocr(crop_bgr)
        out = reader.readtext(bw, detail=0, paragraph=True)
        for t in out:
            tt = normalize_space(t)
            if tt:
                texts.append(tt)
    return texts

def band_ocr_backup(band_img: Image.Image, prefer_cuda: bool) -> List[str]:
    """마스크가 약할 경우 밴드 전체를 OCR(업샘플+전처리)"""
    reader = get_reader(prefer_cuda)
    bgr = cv2.cvtColor(np.array(band_img), cv2.COLOR_RGB2BGR)
    bw = _prep_for_ocr(bgr)
    out = reader.readtext(bw, detail=0, paragraph=True)
    return [normalize_space(t) for t in out if t]

def extract_page20_red_text(doc: fitz.Document, page_idx: int, page_img: Image.Image,
                            prefer_cuda: bool, debug_dir: Optional[str] = None) -> List[str]:
    # 1) 벡터(텍스트 레이어) 우선
    vec_texts = extract_side_red_text_from_vector(doc[page_idx])
    if vec_texts:
        return _canonicalize(vec_texts)

    # 2) 백업: 이미지 OCR (좌/우 밴드만)
    W, H = page_img.size
    xL0, xL1 = 0, int(W * LEFT_MAX_FRAC)
    xR0, xR1 = int(W * RIGHT_MIN_FRAC), W
    y0, y1 = int(H * TOP_FRAC), int(H * BOT_FRAC)

    mask_full = mask_red_regions(page_img)
    left_img  = Image.fromarray(np.array(page_img)[y0:y1, xL0:xL1])
    right_img = Image.fromarray(np.array(page_img)[y0:y1, xR0:xR1])
    left_mask  = mask_full[y0:y1, xL0:xL1]
    right_mask = mask_full[y0:y1, xR0:xR1]

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "p20_mask_full.png"), mask_full)
        cv2.imwrite(os.path.join(debug_dir, "p20_left_mask.png"), left_mask)
        cv2.imwrite(os.path.join(debug_dir, "p20_right_mask.png"), right_mask)

    texts = ocr_on_mask(left_img, left_mask, prefer_cuda) + \
            ocr_on_mask(right_img, right_mask, prefer_cuda)

    labels = set(_canonicalize(texts))

    # 3) 마스크가 약해서 라벨이 부족하면 밴드 전체 OCR 백업 한 번 더
    if len(labels) < 2:
        texts2 = band_ocr_backup(left_img, prefer_cuda) + band_ocr_backup(right_img, prefer_cuda)
        for lab in _canonicalize(texts2):
            labels.add(lab)

    # 원하는 순서로 반환
    wanted_order = ["운동수행능력/지구력 향상", "근력(근육)", "영양균형"]
    return [x for x in wanted_order if x in labels]

# 실행

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs='?', default="ocr_sample.pdf", help="입력 PDF 경로")
    ap.add_argument("--page5", type=int, default=5)
    ap.add_argument("--page20", type=int, default=20)
    ap.add_argument("--out", default="result.json")
    ap.add_argument("--cuda", action="store_true", help="EasyOCR에서 GPU 우선 사용")
    ap.add_argument("--debug_dir", default=None, help="디버그 이미지 저장 폴더")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        raise FileNotFoundError(args.pdf)

    doc = fitz.open(args.pdf)
    p5 = args.page5 - 1
    p20 = args.page20 - 1
    if not (0 <= p5 < len(doc) and 0 <= p20 < len(doc)):
        raise ValueError("페이지 번호가 문서 범위를 벗어났습니다.")

    img5 = pdf_render_page(doc, p5, zoom=3.0)
    img20 = pdf_render_page(doc, p20, zoom=3.0)

    if args.debug_dir:
        os.makedirs(args.debug_dir, exist_ok=True)
        img5.save(os.path.join(args.debug_dir, "p5.png"))
        img20.save(os.path.join(args.debug_dir, "p20.png"))

    scores = extract_page5_scores(img5, prefer_cuda=args.cuda, debug_dir=args.debug_dir)
    red_texts = extract_page20_red_text(doc, p20, img20, prefer_cuda=args.cuda, debug_dir=args.debug_dir)

    result = {
        "노화억제분석지수": float(scores.get("노화억제분석지수", 0.0)),
        "만성질환억제분석지수": float(scores.get("만성질환억제분석지수", 0.0)),
        "근육밸런스지수": float(scores.get("근육밸런스지수", 0.0)),
        "영향준요인들": red_texts
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
