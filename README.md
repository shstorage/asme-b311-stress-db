# ASME B31.1 Allowable Stress DB

ASME B31.1 *Power Piping* 의 **Allowable Stress Tables (Appendix A)** 를 PDF에서 파싱하여  
SQLite DB 및 CSV로 만드는 파이프라인입니다.  
배관 두께 계산식 `t = PD / (2(SE + PY))` 에 필요한 허용응력을 프로그램에서 조회하는 것이 목적입니다.

---

## 결과물 미리보기

| 파일 | 설명 |
|------|------|
| `asme_b311.db` | SQLite DB — `materials` + `stress_values` + `stress_lookup` VIEW |
| `output/stress_wide.csv` | ASME 표 그대로 wide-format (온도별 열, `*` = creep 구간) |
| `output/materials.csv` | 재료 스펙만 |
| `output/stress_values.csv` | 온도별 허용응력 (long-format) |

DB 통계: **1,572개 재료 × 24,190개 허용응력 값**, 온도 범위 100 ~ 1500°F

---

## 아키텍처

```
ASME-B31.1.pdf
      │
      ▼
render_pages.py   ── PDF p147~258 → PNG 300DPI + 이탤릭 span 추출
      │
      ▼
parse_text.py     ── 좌표 기반 텍스트 파싱 (Part A: 재질 스펙 / Part B: 온도별 응력)
      │
      ▼
merge_pairs.py    ── Part A + Part B 병합 → data/merged/*.json
      │
      ▼
build_db.py       ── SQLite DB 생성 (asme_b311.db)
      │
      ▼
export_csv.py     ── CSV 내보내기 (output/*.csv)
```

- VLM/OCR 불사용 — PyMuPDF 좌표 기반 파싱 (결정적, 빠름)
- 이탤릭 폰트(Cambria-Italic) 감지로 creep 구간 자동 표시
- 전체 실행 약 **2분 이내**

---

## ⚠️ 다른 연도/판 사용 시 — TABLE_RANGES 수정 필수

`extract/config.py` 의 `TABLE_RANGES` 는 **ASME B31.1 2022년판 PDF 한정**으로 작성되어 있습니다.  
연도판마다 테이블 위치(PDF 페이지 번호), 온도 열 구성이 다를 수 있으므로, **다른 판을 사용한다면 반드시 이 딕셔너리를 먼저 수정해야 합니다.**

### TABLE_RANGES 만드는 방법

Adobe Acrobat, 브라우저 PDF 뷰어 등에서 본인의 PDF를 열고 Appendix A 테이블 시작/끝 페이지를 확인한 뒤, 아래 프롬프트를 Claude / ChatGPT / Gemini 에 붙여넣으세요.

---

**AI 프롬프트 (복사해서 사용):**

```
나는 ASME B31.1 [연도판 입력, 예: 2024] Power Piping PDF를 가지고 있습니다.
Appendix A의 Allowable Stress Tables 구조를 분석해서
아래 Python 딕셔너리 형식으로 TABLE_RANGES를 만들어주세요.

규칙:
- 각 테이블(A-1, A-2, ... A-10)마다 항목 하나
- "pairs": Part A 페이지(재질 스펙, 홀수)와 Part B 페이지(온도별 응력, 짝수)의 쌍을 리스트로
- "temps": 해당 테이블의 온도 열 헤더에 적힌 온도값(°F)을 오름차순 정수 리스트로
- A-8(High Temperature)은 "ef_on_partb": True 추가
- A-10(Bolts)은 "no_ef": True 추가
- PDF 페이지 번호 기준 (표지=1페이지)

출력 형식 예시:
TABLE_RANGES = {
    "A-1": {
        "name": "Carbon Steel",
        "pairs": [(147,148),(149,150)],
        "temps": [100,200,300,400,500,600,650,700,750,800],
    },
    ...
}

내 PDF의 Appendix A 테이블 범위: [여기에 시작 페이지~끝 페이지 입력, 예: 147~259페이지]
각 테이블별 페이지 범위: [여기에 직접 확인한 정보 입력, 예: A-1은 147~158, A-2는 161~170 ...]
```

생성된 딕셔너리를 `extract/config.py` 의 `TABLE_RANGES` 부분에 덮어쓰면 됩니다.

---

## 사전 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.11 이상 |
| [uv](https://docs.astral.sh/uv/) | 최신 |
| ASME B31.1 PDF | 직접 구매 후 프로젝트 루트에 `ASME-B31.1.pdf` 로 배치 |

> **PDF는 저작권 파일이므로 이 저장소에 포함되어 있지 않습니다.**  
> ASME 공식 사이트 또는 기관 라이선스를 통해 구매하세요.

---

## 설치 및 실행

> **이 파이프라인은 GPU/Docker/VLM 없이 순수 PyMuPDF 텍스트 파싱만으로 동작합니다.**  
> Python + uv만 있으면 바로 실행 가능합니다.

### Ubuntu (권장)

#### 1. uv 설치

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # 또는 새 터미널 열기
```

#### 2. 저장소 클론 및 의존성 설치

```bash
git clone https://github.com/shstorage/asme-b311-stress-db.git
cd asme-b311-stress-db

uv sync   # pyproject.toml 기반으로 가상환경 + 패키지 자동 설치
```

#### 3. PDF 배치

```bash
# 구매한 ASME-B31.1.pdf 를 프로젝트 루트에 복사
cp /path/to/ASME-B31.1.pdf .
```

#### 4. 파이프라인 실행

```bash
# Step 1: PDF → PNG 렌더링 + 이탤릭 span 추출 (~1분)
uv run python -m extract.render_pages

# Step 2: Part A + Part B 병합 (~수 초)
uv run python -m extract.merge_pairs

# Step 3: SQLite DB 빌드 (~수 초)
uv run python -m extract.build_db

# Step 4: CSV 내보내기
uv run python export_csv.py

# Step 5: 검증
uv run python validate.py
```

정상 완료 시 마지막 줄에 `Validation passed.` 출력

---

### Windows — WSL2 + Docker 사용

Windows에서는 **WSL2(Windows Subsystem for Linux)** 환경에서 실행합니다.

#### 1. WSL2 설치

PowerShell을 **관리자 권한**으로 열고:

```powershell
wsl --install
```

설치 완료 후 **PC 재시작** → Ubuntu 터미널이 자동으로 열리면 사용자명/비밀번호 설정.

> 이미 WSL1이 설치되어 있다면 버전 업그레이드:
> ```powershell
> wsl --set-default-version 2
> wsl --update
> ```

#### 2. Docker Desktop 설치

1. [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) 다운로드 후 설치
2. Docker Desktop 실행 → **Settings > Resources > WSL Integration** 에서 Ubuntu 토글 **ON**
3. Ubuntu WSL 터미널에서 확인:
   ```bash
   docker --version   # Docker version 2x.x.x 출력되면 성공
   ```

#### 3. WSL Ubuntu 터미널에서 uv 설치

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

#### 4. 저장소 클론 및 의존성 설치

WSL Ubuntu 터미널에서:

```bash
# WSL 홈 디렉토리에 클론 (Windows 경로 /mnt/c/... 보다 WSL 내부가 훨씬 빠름)
cd ~
git clone https://github.com/shstorage/asme-b311-stress-db.git
cd asme-b311-stress-db

uv sync
```

#### 5. PDF 배치

Windows 탐색기에서 PDF를 복사하려면 WSL 경로를 사용:

```
탐색기 주소창에 입력: \\wsl$\Ubuntu\home\<사용자명>\asme-b311-stress-db
```

해당 폴더에 `ASME-B31.1.pdf` 붙여넣기. 또는 WSL 터미널에서:

```bash
cp /mnt/c/Users/<윈도우사용자명>/Downloads/ASME-B31.1.pdf .
```

#### 6. 파이프라인 실행

Ubuntu와 동일:

```bash
uv run python -m extract.render_pages
uv run python -m extract.merge_pairs
uv run python -m extract.build_db
uv run python export_csv.py
uv run python validate.py
```

#### 7. 결과물 확인 (Windows 탐색기에서)

```
탐색기 주소창: \\wsl$\Ubuntu\home\<사용자명>\asme-b311-stress-db\output
```

`stress_wide.csv` 등을 Excel로 바로 열 수 있습니다.

---

## DB 사용 예시

```python
import sqlite3

con = sqlite3.connect("asme_b311.db")

# A53 Grade B Seamless, 설계온도 600°F 에서의 허용응력 조회
row = con.execute("""
    SELECT stress_ksi, is_creep
    FROM stress_lookup
    WHERE spec_no = 'A53' AND grade = 'B' AND type_or_class = 'S'
      AND temp_f <= 600
    ORDER BY temp_f DESC
    LIMIT 1
""").fetchone()

print(f"허용응력: {row[0]} ksi  (creep 구간: {bool(row[1])})")
con.close()
```

```python
# pandas로 읽기
import pandas as pd, sqlite3
con = sqlite3.connect("asme_b311.db")
df = pd.read_sql("SELECT * FROM stress_lookup WHERE spec_no='A106'", con)
con.close()
```

---

## 데이터 범위

| 테이블 | 설명 | 재료 수 |
|--------|------|---------|
| A-1 | Carbon Steel | 186 |
| A-2 | Low and Intermediate Alloy Steel | 172 |
| A-3 | Stainless Steels | 608 |
| A-4 | Nickel and High Nickel Alloys | 214 |
| A-5 | Cast Iron | 26 |
| A-6 | Copper and Copper Alloys | 60 |
| A-7 | Aluminum and Aluminum Alloys | 97 |
| A-8 | High Temperature (≥1200°F) | 86 |
| A-9 | Titanium and Titanium Alloys | 37 |
| A-10 | Bolts, Nuts and Studs | 86 |

---

## 주의사항

- 이 저장소는 파싱 코드만 포함합니다. **ASME B31.1 PDF는 포함되지 않습니다.**
- 파싱 결과는 검증 스팟체크를 통과하였으나, 안전 관련 설계에 사용 시 원본 ASME 문서와 반드시 대조하세요.
- `*` 표시 값은 creep/stress rupture 지배 구간 (원본에서 이탤릭체로 표기된 값)입니다.

---

## 스캔 문서(이미지 PDF)인 경우 — VLM 사용 권장

이 파이프라인은 **텍스트 레이어가 있는 디지털 PDF** 전용입니다.  
ASME 공식 구매본은 텍스트 레이어가 있어서 PyMuPDF로 바로 읽히지만,  
**종이를 스캔한 PDF나 이미지로만 구성된 PDF** 라면 텍스트 좌표를 읽을 수 없으므로 이 방식이 동작하지 않습니다.

### 스캔 문서 판별 방법

PDF를 열고 텍스트를 마우스로 드래그해서 선택이 되면 → 디지털 PDF (이 파이프라인 사용 가능)  
텍스트가 선택되지 않고 그림처럼만 보이면 → 스캔 문서 (VLM 필요)

### 스캔 문서일 때: PaddleOCR-VL vLLM 서버 사용

NVIDIA GPU가 있는 환경에서 아래 명령으로 PaddleOCR-VL 추론 서버를 기동합니다.

```bash
docker run \
    --rm \
    --gpus all \
    --network host \
    ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlepaddle/paddleocr-genai-vllm-server:latest-nvidia-gpu \
    paddleocr genai_server \
        --model_name PaddleOCR-VL-1.5-0.9B \
        --host 0.0.0.0 \
        --port 8080 \
        --backend vllm
```

로그에 `Application startup complete` 가 뜨면 서버 준비 완료.  
이후 `http://localhost:8080` 에서 OpenAI 호환 API로 이미지를 넘겨 텍스트를 추출할 수 있습니다.

```python
from openai import OpenAI
import base64

client = OpenAI(base_url="http://localhost:8080/v1", api_key="dummy")

with open("page.png", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="PaddleOCR-VL-1.5-0.9B",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": "이 표에서 재료명, 허용응력 값을 JSON으로 추출해주세요."},
        ],
    }],
)
print(response.choices[0].message.content)
```

> Windows WSL2 사용자는 Docker Desktop이 실행 중인 상태에서 WSL Ubuntu 터미널에서 위 명령을 실행하세요.
