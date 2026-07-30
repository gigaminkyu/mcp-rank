"""한국 MCP 서버를 발굴·수집하고 점수를 매겨 data.json 과 하루치 스냅샷을 떨군다.

후보는 두 갈래에서 온다. 하나는 awesome-mcp-korea README, 다른 하나는 GitHub 검색이다.
전자만 쓰면 그 저장소가 멈추는 순간 순위도 같이 멈춘다 — 실제로 2026-05-13 이후 손이
안 닿아 있다. 그래서 검색으로 직접 훑어 새 서버를 스스로 주워온다.

순위 변동(▲▼)과 별 증가량은 history/ 에 쌓이는 날짜별 스냅샷에서 계산한다. GitHub 가
과거 별 기록(stargazers 의 starred_at)을 안 열어주므로 소급해서 만들 수 없다 —
안 돌린 날은 영구히 빈다.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HIST = ROOT / "history"
SOURCE = "https://raw.githubusercontent.com/darjeeling/awesome-mcp-korea/main/README.md"
SOURCE_REPO = "darjeeling/awesome-mcp-korea"

ITEM = re.compile(r"^\*\*\[([^\]]+)\]\(https://github\.com/([^)]+?)/?\)\*\*\s*[–\-—]\s*(.+)$")
HEADING = re.compile(r"^### (.+)$")

# 검색으로 후보를 긁어온다. 겹치는 건 어차피 저장소 이름으로 합쳐지니 넉넉히 던진다.
QUERIES = [
    "mcp korean",
    "mcp-server korea",
    "mcp 한국",
    "topic:mcp topic:korea",
    "topic:mcp-server topic:korean",
    "korea mcp in:name,description",
    "korean mcp in:name,description",
    "한국 mcp in:name,description,readme",
]

HANGUL = re.compile(r"[가-힣]")
# 이름·설명에 이 중 하나는 있어야 '한국' 서버로 인정한다. 토픽은 안 본다 —
# 번역기가 지원 언어로 달아둔 korean 토픽까지 한국 서버로 세면 목록이 오염된다.
KOREA = (
    "korea", "korean", "한국", "한글", "국내", "hangul", "seoul", "서울",
    "naver", "네이버", "kakao", "카카오", "coupang", "쿠팡", "toss", "토스",
    "krx", "kospi", "dart", "hwp", "공공데이터", "행정안전부", "기상청",
)
# 서버가 아닌 것들. 목록·템플릿·스킬 모음·클라이언트는 여기서 다룰 물건이 아니다.
NOT_SERVER = (
    "awesome", "curated", "directory", "boilerplate", "tutorial", "example",
    "template", "starter", "skills", "plugins", "marketplace", "client", "docs",
)
# MCP 서버라는 근거. mcp 토픽 하나로는 안 된다 — 실행 방식 중 하나로 MCP 를 지원할 뿐인
# 대형 저장소(PDF 번역기, 증권사 공식 API)가 그 구멍으로 상위권에 올라온다.
MCP_NAME = re.compile(r"(^|[-_])mcp([-_]|$)")
MCP_DESC = re.compile(r"mcp[\s-]?(server|서버)", re.I)

# 발굴한 저장소를 awesome 목록과 같은 분야로 떨군다. 위에서부터 먼저 걸리는 쪽을 쓴다 —
# "api" 같은 흔한 단어는 아래로 미뤄야 법령 서버가 공공데이터로 새지 않는다.
CATEGORIES = [
    ("📜 Legal & Government", ("law", "legal", "법령", "판례", "국회", "assembly", "government", "정부", "행정", "민원", "입법")),
    ("🏦 Finance & Tax", ("stock", "finance", "financial", "금융", "주식", "증권", "tax", "세금", "국세", "krx", "kospi", "dart", "bank", "은행", "투자", "환율")),
    ("🏠 Real Estate", ("real-estate", "realestate", "부동산", "아파트", "청약", "전월세", "등기")),
    ("🌦 Weather", ("weather", "날씨", "기상", "미세먼지", "대기", "kma")),
    ("🗺 Maps & Address", ("map", "지도", "address", "주소", "도로명", "geocod", "route", "경로", "지하철", "버스", "transit")),
    ("🛒 Commerce & Retail", ("commerce", "shop", "쇼핑", "커머스", "mall", "coupang", "쿠팡", "다이소", "daiso", "편의점", "배달")),
    ("🌏 Tourism & Travel", ("tour", "travel", "여행", "관광", "숙박", "항공")),
    ("🔤 Korean NLP & Language", ("nlp", "형태소", "맞춤법", "한글", "hangul", "hwp", "konlpy", "번역", "translit", "romaniz")),
    ("🤝 Collaboration & Communication", ("slack", "notion", "jira", "dooray", "kakaowork", "협업", "메신저", "confluence", "calendar", "일정")),
    ("🔎 Search & Trends", ("search", "검색", "trend", "트렌드", "datalab", "뉴스", "news")),
    ("📊 Public Data", ("public-data", "공공데이터", "opendata", "open-data", "통계", "statistic", "data.go.kr", "api")),
]
FALLBACK_CAT = "🧩 Miscellaneous"

# README 에서 설치 방법을 뽑는다. 에이전트 사용자가 가장 먼저 찾는 정보다.
#   \w 는 한글도 잡는다 — README 의 한국어 설명이 패키지명으로 딸려오지 않게 ASCII 로 못박는다.
PKG = r"@?[A-Za-z0-9][A-Za-z0-9._/-]*"
INSTALL = [
    ("npx", re.compile(rf"\bnpx\s+(?:-y\s+)?({PKG})")),
    ("uvx", re.compile(rf"\buvx\s+({PKG})")),
    ("pip", re.compile(rf"\bpip3?\s+install\s+({PKG}(?:\[[A-Za-z0-9,_-]+\])?)")),
    ("docker", re.compile(r"\bdocker\s+run\b")),
]


def gh(path: str) -> dict | list | None:
    try:
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


def parse_list(md: str) -> list[dict]:
    items, cat = [], FALLBACK_CAT
    for line in md.splitlines():
        h = HEADING.match(line)
        if h:
            cat = h.group(1).strip()
            continue
        m = ITEM.match(line.strip())
        if m:
            items.append(
                {"repo": m.group(2), "desc": m.group(3).strip(), "category": cat, "source": "목록"}
            )
    return items


def guess_category(name: str, blob: str) -> str:
    """이름을 먼저 본다. korea-finance-mcp 가 설명에 '법령'을 한 번 흘렸다고
    법률 분야로 가면 안 된다."""
    for source in (name, blob):
        for cat, keys in CATEGORIES:
            if any(k in source for k in keys):
                return cat
    return FALLBACK_CAT


def is_korean_mcp(meta: dict) -> bool:
    """검색 결과에서 진짜 후보만 남긴다. 애매하면 버린다 — 목록이 지저분해지면
    순위 자체를 안 믿게 된다."""
    if meta.get("fork") or meta.get("archived"):
        return False
    name = (meta.get("name") or "").lower()
    if any(k in name for k in NOT_SERVER):
        return False
    if meta.get("stargazers_count", 0) < 2:
        return False
    desc = meta.get("description") or ""
    topics = meta.get("topics") or []
    if not (MCP_NAME.search(name) or "mcp-server" in topics or MCP_DESC.search(desc)):
        return False
    text = f"{name} {desc}".lower()
    return any(k in text for k in KOREA) or bool(HANGUL.search(text))


def discover() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for q in QUERIES:
        res = gh(f"search/repositories?q={urllib.parse.quote(q)}&per_page=100&sort=stars")
        hits = (res or {}).get("items") or []
        kept = 0
        for meta in hits:
            if meta["full_name"] in found or not is_korean_mcp(meta):
                continue
            found[meta["full_name"]] = meta
            kept += 1
        print(f"  '{q}' — {len(hits)}건 중 {kept}건 채택")
    return found


def readme_of(full_name: str) -> str:
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            continue
    return ""


def install_hint(readme: str, repo_name: str) -> str:
    """README 에는 남의 서버 설정 예시도 흔히 섞여 있다. 저장소 이름과 겹치는 패키지만
    설치 명령으로 인정한다 — 엉뚱한 명령을 '붙이는 법'이라고 띄우느니 비워두는 게 낫다."""
    key = repo_name.lower().replace("_", "-")
    docker = False
    for kind, pat in INSTALL:
        for m in pat.finditer(readme):
            if not m.groups():
                docker = True
                continue
            pkg = m.group(1)
            tail = pkg.rsplit("/", 1)[-1].lower().replace("_", "-")
            if key in tail or tail in key:
                return f"{kind} {pkg}"
    return "docker" if docker else ""


def score(stars: int, days_idle: int, readme_len: int, has_license: bool, releases: int) -> dict:
    """40 + 30 + 20 + 10 = 100. 각 항목을 그대로 사이트에 노출한다."""
    popularity = min(40.0, 10.0 * math.log10(stars + 1))
    if days_idle <= 30:
        upkeep = 30.0
    elif days_idle <= 90:
        upkeep = 20.0
    elif days_idle <= 180:
        upkeep = 12.0
    elif days_idle <= 365:
        upkeep = 5.0
    else:
        upkeep = 0.0
    docs = 20.0 if readme_len >= 8000 else 14.0 if readme_len >= 3000 else 8.0 if readme_len >= 1000 else 3.0 if readme_len else 0.0
    trust = (5.0 if has_license else 0.0) + (5.0 if releases else 0.0)
    return {
        "total": round(popularity + upkeep + docs + trust, 1),
        "popularity": round(popularity, 1),
        "upkeep": upkeep,
        "docs": docs,
        "trust": trust,
    }


def fetch(it: dict, meta: dict | None, now: datetime) -> dict | None:
    """검색으로 이미 받아둔 meta 가 있으면 재사용한다 — 같은 걸 두 번 부를 이유가 없다."""
    meta = meta or gh(f"repos/{it['repo']}")
    if not meta or "stargazers_count" not in meta:
        return None
    readme = readme_of(meta["full_name"])
    pushed = datetime.fromisoformat(meta["pushed_at"].replace("Z", "+00:00"))
    idle = (now - pushed).days
    rel = gh(f"repos/{meta['full_name']}/releases?per_page=1") or []
    blob = " ".join(
        [meta["name"], meta.get("description") or "", " ".join(meta.get("topics") or []), it.get("desc", "")]
    ).lower()
    return {
        **it,
        "repo": meta["full_name"],  # 리다이렉트된 이름으로 교정
        "name": meta["name"],
        "owner": meta["owner"]["login"],
        "desc": it.get("desc") or meta.get("description") or "설명이 없다.",
        "category": it.get("category") or guess_category(meta["name"].lower(), blob),
        "stars": meta["stargazers_count"],
        "forks": meta["forks_count"],
        "issues": meta["open_issues_count"],
        "language": meta.get("language") or "",
        "license": (meta.get("license") or {}).get("spdx_id") or "",
        "topics": meta.get("topics") or [],
        "gh_desc": meta.get("description") or "",
        "homepage": meta.get("homepage") or "",
        "pushed_at": meta["pushed_at"][:10],
        "created_at": meta["created_at"][:10],
        "days_idle": idle,
        "readme_len": len(readme),
        "releases": len(rel),
        "install": install_hint(readme, meta["name"]),
        "score": score(meta["stargazers_count"], idle, len(readme), bool(meta.get("license")), len(rel)),
    }


def snapshots() -> list[tuple[date, dict]]:
    """history/ 의 날짜별 스냅샷을 오래된 순으로 읽는다."""
    out = []
    for p in sorted(HIST.glob("*.json")):
        try:
            out.append((date.fromisoformat(p.stem), json.loads(p.read_text())))
        except Exception:
            continue
    return out


def apply_history(rows: list[dict], today: date) -> dict:
    """어제 대비 순위 변동과 일주일 전 대비 별 증가를 붙인다.

    스냅샷이 하나도 없는 첫 실행에서는 전부 비운다 — 54개 전부에 NEW 를 다는 건 거짓말이다.
    """
    past = [(d, s) for d, s in snapshots() if d < today]
    prev = past[-1] if past else None
    # 7일 이상 지난 것 중 가장 최근. 없으면 가진 것 중 가장 오래된 것으로 대신한다.
    old = next((x for x in reversed(past) if (today - x[0]).days >= 7), past[0] if past else None)

    for r in rows:
        r["rank_delta"] = None
        r["is_new"] = False
        r["star_delta"] = None
        r["star_delta_days"] = None
        if prev:
            was = prev[1]["servers"].get(r["repo"])
            if was:
                r["rank_delta"] = was["rank"] - r["rank"]
            else:
                r["is_new"] = True
        if old:
            was = old[1]["servers"].get(r["repo"])
            if was:
                r["star_delta"] = r["stars"] - was["stars"]
                r["star_delta_days"] = (today - old[0]).days

    return {
        "prev": prev[0].isoformat() if prev else None,
        "baseline": old[0].isoformat() if old else None,
        "days": len(past) + 1,
    }


def main() -> None:
    with urllib.request.urlopen(SOURCE, timeout=30) as r:
        md = r.read().decode("utf-8", "ignore")
    listed = parse_list(md)
    print(f"목록 {len(listed)}건")

    print("검색으로 발굴")
    found = discover()
    seen = {i["repo"].lower() for i in listed}
    extra = [
        {"repo": full, "desc": "", "category": "", "source": "발굴"}
        for full in found
        if full.lower() not in seen
    ]
    print(f"발굴 {len(found)}건 중 목록에 없는 {len(extra)}건 추가 → 후보 {len(listed) + len(extra)}건")

    now = datetime.now(timezone.utc)
    cand = listed + extra
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda c: fetch(c, found.get(c["repo"]), now), cand))

    rows, dead = [], []
    for it, res in zip(cand, results):
        if res is None:
            dead.append(it["repo"])
            print(f"  {it['repo']} — 접근 불가, 제외")
            continue
        rows.append(res)

    # 리다이렉트 때문에 같은 저장소가 두 번 들어올 수 있다. 목록 쪽 설명을 남긴다.
    uniq: dict[str, dict] = {}
    for r in rows:
        if r["repo"] not in uniq or r["source"] == "목록":
            uniq[r["repo"]] = r
    rows = list(uniq.values())

    rows.sort(key=lambda r: (-r["score"]["total"], -r["stars"]))
    for rank, r in enumerate(rows, 1):
        r["rank"] = rank

    today = date.today()
    hist = apply_history(rows, today)

    out = {
        "generated": today.isoformat(),
        "source": {"repo": SOURCE_REPO, "url": f"https://github.com/{SOURCE_REPO}"},
        "count": len(rows),
        "listed": sum(1 for r in rows if r["source"] == "목록"),
        "found": sum(1 for r in rows if r["source"] == "발굴"),
        "dropped": dead,
        "history": hist,
        "servers": rows,
    }
    (ROOT / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

    HIST.mkdir(exist_ok=True)
    snap = {
        "date": today.isoformat(),
        "servers": {
            r["repo"]: {"rank": r["rank"], "stars": r["stars"], "score": r["score"]["total"]}
            for r in rows
        },
    }
    (HIST / f"{today.isoformat()}.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1))

    print(f"\ndata.json — {len(rows)}건 (목록 {out['listed']} + 발굴 {out['found']}), {len(dead)}건 제외")
    print(f"history/{today.isoformat()}.json — 스냅샷 {hist['days']}일치 보유")


if __name__ == "__main__":
    main()
