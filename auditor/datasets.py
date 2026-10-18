"""Download the public datasets into data/raw/ (gitignored).

* ABCD (ASAPP), MIT licence: the conversations and the agent guidelines that
  serve as the written policy.
* CallCenterEN (AIxBlock), CC BY-NC 4.0: real call transcripts, one zip per
  domain. Non-commercial use only; the raw files are never committed.
"""

import urllib.request
from pathlib import Path

from . import config

ABCD_BASE = "https://raw.githubusercontent.com/asappresearch/abcd/master/data"
ABCD_FILES = ["abcd_v1.1.json.gz", "guidelines.json", "ontology.json", "kb.json"]

CALLCENTER_BASE = "https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english/resolve/main"
# Domain zips in the dataset, smallest first (sizes as listed in October 2026).
CALLCENTER_DOMAINS = {
    "medical_equipment_outbound": "medical_equipment_outbound.zip",  # 13.5 MB
    "auto_insurance_customer_service_inbound": "auto_insurance_customer_service_inbound.zip",  # 36.6 MB
    "customer_service_general_inbound": "customer_service_general_inbound.zip",  # 43.0 MB
    "insurance_outbound": "insurance_outbound.zip",  # 55.3 MB
}


def _fetch(url: str, dest: Path) -> bool:
    """Download url to dest unless it already exists. Returns True if downloaded."""
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dest)
    return True


def download_abcd() -> list[Path]:
    paths = []
    for name in ABCD_FILES:
        dest = config.ABCD_DIR / name
        _fetch(f"{ABCD_BASE}/{name}", dest)
        paths.append(dest)
    return paths


def download_callcenter(domain: str) -> Path:
    if domain not in CALLCENTER_DOMAINS:
        raise ValueError(f"unknown domain {domain!r}; choose from {', '.join(CALLCENTER_DOMAINS)}")
    name = CALLCENTER_DOMAINS[domain]
    dest = config.CALLCENTER_DIR / name
    _fetch(f"{CALLCENTER_BASE}/{name}", dest)
    return dest
