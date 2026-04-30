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
