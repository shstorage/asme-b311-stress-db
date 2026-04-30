from pathlib import Path

PDF_PATH = Path(__file__).parent.parent / "ASME-B31.1.pdf"
DATA_DIR = Path(__file__).parent.parent / "data"
PAGES_DIR = DATA_DIR / "pages"
ITALIC_DIR = DATA_DIR / "italic_spans"
RAW_VLM_DIR = DATA_DIR / "raw_vlm"
MERGED_DIR = DATA_DIR / "merged"
DB_PATH = Path(__file__).parent.parent / "asme_b311.db"

VLM_URL = "http://localhost:8080/v1"
VLM_MODEL = "PaddleOCR-VL-1.5-0.9B"

# (part_a_page, part_b_page) — 1-indexed PDF page numbers
TABLE_RANGES = {
    "A-1": {
        "name": "Carbon Steel",
        "pairs": [(147,148),(149,150),(151,152),(153,154),(155,156),(157,158)],
        "temps": [100,200,300,400,500,600,650,700,750,800],
    },
    "A-2": {
        "name": "Low and Intermediate Alloy Steel",
        "pairs": [(161,162),(163,164),(165,166),(167,168),(169,170)],
        "temps": [100,200,300,400,500,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200],
    },
    "A-3": {
        "name": "Stainless Steels",
        "pairs": [
            (173,174),(175,176),(177,178),(179,180),(181,182),(183,184),
            (185,186),(187,188),(189,190),(191,192),(193,194),(195,196),
            (197,198),(199,200),(201,202),(203,204),(205,206),
        ],
        "temps": [100,200,300,400,500,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200],
    },
    "A-4": {
        "name": "Nickel and High Nickel Alloys",
        "pairs": [(209,210),(211,212),(213,214),(215,216),(217,218),(219,220)],
        "temps": [100,200,300,400,500,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200],
    },
    "A-5": {
        "name": "Cast Iron",
        "pairs": [(223,224)],
        "temps": [400,450,500,600,650],
    },
    "A-6": {
        "name": "Copper and Copper Alloys",
        "pairs": [(227,228),(229,230)],
        "temps": [100,150,200,250,300,350,400,450,500,550,600,650,700,750,800],
    },
    "A-7": {
        "name": "Aluminum and Aluminum Alloys",
        "pairs": [(233,234),(235,236),(237,238)],
        "temps": [100,150,200,250,300,350,400],
    },
    "A-8": {
        "name": "Temperatures 1200F and Above",
        "pairs": [(241,242),(243,244),(245,246)],
        "temps": [1200,1250,1300,1350,1400,1450,1500],
        "ef_on_partb": True,  # E/F column is on Part B page, not Part A
    },
    "A-9": {
        "name": "Titanium and Titanium Alloys",
        "pairs": [(249,250)],
        "temps": [100,150,200,250,300,350,400,450,500,550,600],
    },
    "A-10": {
        "name": "Bolts Nuts and Studs",
        "pairs": [(253,254),(255,256),(257,258)],
        "temps": [100,200,300,350,400,450,500,600,650,700,750,800,850,900,950,1000,1050,1100,1150,1200],
        "no_ef": True,  # bolts have no E/F column
    },
}
