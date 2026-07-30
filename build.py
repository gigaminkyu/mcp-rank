"""data.json → 정적 사이트(docs/). 의존성 없이 HTML 을 직접 찍는다.

목록 페이지 하나 + 서버마다 상세 페이지 하나. 상세에는 점수를 항목별로 쪼개서
보여준다 — 왜 이 순위인지 클릭 한 번으로 확인되지 않으면 순위표는 그냥 의견이다.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
SITE = "한국 MCP 서버 순위"
TAGLINE = "한국 서비스에 붙는 MCP 서버를 별 수·관리 상태·문서로 줄 세운다."

CSS = """
*{box-sizing:border-box}
:root{--bg:#0e1116;--card:#161b22;--line:#242c38;--tx:#e6edf3;--dim:#8b949e;--acc:#4c9aff;--good:#3fb950;--warn:#d29922;--bad:#f85149}
@media(prefers-color-scheme:light){:root{--bg:#f6f8fa;--card:#fff;--line:#d8dee4;--tx:#1f2328;--dim:#636c76;--acc:#0969da}}
body{margin:0;overflow-wrap:anywhere;background:var(--bg);color:var(--tx);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard",Segoe UI,sans-serif}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{max-width:960px;margin:0 auto;padding:28px 18px 80px;overflow-x:hidden}
header h1{font-size:26px;margin:0 0 6px}
header p{color:var(--dim);margin:0 0 4px;font-size:15px}
.meta{color:var(--dim);font-size:13px;margin-top:10px}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 14px}
input[type=search]{flex:1;min-width:190px;padding:10px 13px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--tx);font-size:15px}
select{padding:10px 13px;border-radius:9px;border:1px solid var(--line);background:var(--card);color:var(--tx);font-size:15px;max-width:100%}

.row{display:block;background:var(--card);border:1px solid var(--line);border-radius:11px;padding:13px 15px;margin-bottom:9px;color:inherit}
.row:hover{border-color:var(--acc);text-decoration:none}
.top{display:flex;align-items:baseline;gap:10px}
.rank{font-variant-numeric:tabular-nums;color:var(--dim);font-size:14px;min-width:2.2em}
.nm{font-weight:600;font-size:16px}
.sc{margin-left:auto;font-weight:700;font-variant-numeric:tabular-nums}
.ds{color:var(--dim);font-size:14px;margin:5px 0 7px}
.tag{display:inline-block;font-size:12px;color:var(--dim);border:1px solid var(--line);border-radius:20px;padding:1px 9px;margin-right:5px}
.d{font-size:12.5px;font-weight:700;font-variant-numeric:tabular-nums}
.up{color:var(--good)}
.down{color:var(--bad)}
.new{color:var(--acc)}
.hot{color:var(--good);border-color:var(--good)}
.old{color:var(--warn);border-color:var(--warn)}
.cold{color:var(--bad);border-color:var(--bad)}
h2{font-size:19px;margin:32px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line)}
table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:15px;margin:14px 0}
th,td{text-align:left;padding:9px 6px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:500;font-size:13px}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.bar{height:7px;border-radius:4px;background:var(--acc);display:inline-block;vertical-align:middle}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px}
pre{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:12px 14px;overflow-x:auto}
footer{margin-top:48px;padding-top:18px;border-top:1px solid var(--line);color:var(--dim);font-size:13px}
.back{font-size:14px;color:var(--dim)}
.empty{color:var(--dim);padding:26px 0}
"""

JS = """
const q=document.getElementById('q'),c=document.getElementById('c'),o=document.getElementById('o'),
 list=document.getElementById('list'),rows=[...document.querySelectorAll('.row')];
function f(){const t=(q.value||'').toLowerCase(),k=c.value;let n=0;
 rows.forEach(r=>{const ok=(!k||r.dataset.cat===k)&&(!t||r.dataset.q.includes(t));r.style.display=ok?'':'none';if(ok)n++;});
 document.getElementById('n').textContent=n;}
function s(){const key=o.value;
 [...rows].sort((a,b)=>b.dataset[key]-a.dataset[key]).forEach(r=>list.appendChild(r));}
q.addEventListener('input',f);c.addEventListener('change',f);
if(o)o.addEventListener('change',s);
"""


def e(s: str) -> str:
    return html.escape(str(s), quote=True)


def slug(repo: str) -> str:
    return repo.replace("/", "__")


def freshness(days: int) -> tuple[str, str]:
    if days <= 30:
        return "hot", f"{days}일 전 커밋"
    if days <= 180:
        return "old", f"{days}일 전 커밋"
    return "cold", f"{days}일 방치"


def page(title: str, body: str, depth: int = 0) -> str:
    up = "../" * depth
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(TAGLINE)}">
<style>{CSS}</style></head><body><div class="wrap">{body}
<footer>목록 출처는 <a href="https://github.com/darjeeling/awesome-mcp-korea">awesome-mcp-korea</a>,
수치는 GitHub API 원본이다. 점수 산식은 <a href="{up}about.html">여기</a>에 전부 적어놨다.</footer>
</div></body></html>"""


def delta_mark(s: dict) -> str:
    """어제 대비 순위 변동. 스냅샷이 없던 첫날은 아무것도 안 붙는다."""
    if s.get("is_new"):
        return '<span class="d new">NEW</span>'
    n = s.get("rank_delta")
    if not n:
        return ""
    return f'<span class="d {"up" if n > 0 else "down"}">{"▲" if n > 0 else "▼"}{abs(n)}</span>'


def index(d: dict) -> str:
    servers = d["servers"]
    cats = sorted({s["category"] for s in servers})
    opts = "".join(f'<option value="{e(c)}">{e(c)}</option>' for c in cats)
    movers = any(s.get("star_delta") for s in servers)

    rows = []
    for s in servers:
        cls, label = freshness(s["days_idle"])
        blob = f"{s['repo']} {s['desc']} {s['gh_desc']} {' '.join(s['topics'])}".lower()
        tags = [f'<span class="tag {cls}">{e(label)}</span>', f'<span class="tag">★ {s["stars"]:,}</span>']
        if s.get("star_delta"):
            tags.append(f'<span class="tag up">{s["star_delta"]:+,} / {s["star_delta_days"]}일</span>')
        if s["language"]:
            tags.append(f'<span class="tag">{e(s["language"])}</span>')
        if s["install"]:
            tags.append(f'<span class="tag">{e(s["install"].split()[0])}</span>')
        rows.append(
            f'<a class="row" href="s/{slug(s["repo"])}.html" data-cat="{e(s["category"])}" data-q="{e(blob)}"'
            f' data-score="{s["score"]["total"]}" data-gain="{s.get("star_delta") or 0}">'
            f'<div class="top"><span class="rank">{s["rank"]}</span>'
            f'<span class="nm">{e(s["name"])}</span>{delta_mark(s)}'
            f'<span class="sc">{s["score"]["total"]:.0f}</span></div>'
            f'<div class="ds">{e(s["desc"])}</div>'
            f'<div>{"".join(tags)}</div></a>'
        )

    sort = (
        '<select id="o"><option value="score">점수순</option><option value="gain">급상승순</option></select>'
        if movers
        else ""
    )
    hist = d.get("history") or {}
    note = (
        f" · 어제({hist['prev']}) 대비 변동 표시"
        if hist.get("prev")
        else " · 순위 변동은 내일부터 표시된다"
    )

    return page(
        SITE,
        f"""<header><h1>{SITE}</h1><p>{TAGLINE}</p>
<div class="meta">{d['generated']} 기준 · {d['count']}개{note}</div></header>
<div class="tools"><input type="search" id="q" placeholder="이름·설명·토픽 검색 (예: 부동산, 날씨, 법령)">
<select id="c"><option value="">전체 분야</option>{opts}</select>{sort}</div>
<div class="meta"><span id="n">{d['count']}</span>개 표시 중</div>
<div style="margin-top:12px" id="list">{''.join(rows)}</div>""",
    )


def detail(s: dict, d: dict) -> str:
    sc = s["score"]
    cls, label = freshness(s["days_idle"])
    parts = [
        ("인기", sc["popularity"], 40, f"별 {s['stars']:,}개 (로그 환산)"),
        ("관리", sc["upkeep"], 30, label),
        ("문서", sc["docs"], 20, f"README {s['readme_len']:,}자"),
        ("신뢰", sc["trust"], 10, f"{s['license'] or '라이선스 없음'} · 릴리스 {s['releases']}건"),
    ]
    bars = "".join(
        f'<tr><td>{n}<div style="color:var(--dim);font-size:12.5px">{e(note)}</div></td>'
        f'<td class=n style="width:5.5em">{v:.1f} / {m}</td>'
        f'<td style="width:34%"><span class="bar" style="width:{max(2, v / m * 100):.0f}%"></span></td></tr>'
        for n, v, m, note in parts
    )

    install = ""
    if s["install"]:
        cmd = s["install"]
        if cmd.startswith("npx"):
            block = f'"command": "npx",\n  "args": ["-y", "{cmd.split()[1]}"]'
        elif cmd.startswith("uvx"):
            block = f'"command": "uvx",\n  "args": ["{cmd.split()[1]}"]'
        elif cmd.startswith("pip"):
            block = f'"command": "python",\n  "args": ["-m", "{cmd.split()[1]}"]'
        else:
            block = f'"command": "{cmd}"'
        install = f"""<h2>붙이는 법</h2>
<p style="color:var(--dim);font-size:14px">README 에서 찾은 실행 명령이다. 정확한 인자는 저장소를 확인할 것.</p>
<pre>{{
  {e(block)}
}}</pre>"""

    topics = "".join(f'<span class="tag">{e(t)}</span>' for t in s["topics"][:10])

    moves = ""
    if s.get("is_new"):
        moves += '<tr><th>순위 변동</th><td class=n><span class="d new">NEW</span> 오늘 처음 잡혔다</td></tr>'
    elif s.get("rank_delta"):
        n = s["rank_delta"]
        moves += f'<tr><th>순위 변동</th><td class=n>어제 {s["rank"] + n}위 → {s["rank"]}위 {delta_mark(s)}</td></tr>'
    if s.get("star_delta"):
        moves += f'<tr><th>별 증가</th><td class=n>{s["star_delta"]:+,} ({s["star_delta_days"]}일간)</td></tr>'

    return page(
        f"{s['name']} — {SITE}",
        f"""<div class="back"><a href="../index.html">← 전체 순위</a></div>
<header style="margin-top:14px"><h1>{e(s['name'])} <span style="color:var(--dim);font-size:17px">#{s['rank']}</span></h1>
<p>{e(s['desc'])}</p>
<div class="meta">{e(s['category'])} · <a href="https://github.com/{e(s['repo'])}">{e(s['repo'])}</a>
{f' · <a href="{e(s["homepage"])}">홈페이지</a>' if s['homepage'] else ''}</div></header>

<h2>점수 {sc['total']:.1f} / 100</h2>
<table>{bars}</table>

<h2>저장소 상태</h2>
<table>
<tr><th>별 / 포크</th><td class=n>{s['stars']:,} / {s['forks']:,}</td></tr>
{moves}<tr><th>마지막 커밋</th><td class=n>{e(s['pushed_at'])} ({s['days_idle']}일 전)</td></tr>
<tr><th>첫 커밋</th><td class=n>{e(s['created_at'])}</td></tr>
<tr><th>언어 / 라이선스</th><td class=n>{e(s['language'] or '-')} / {e(s['license'] or '없음')}</td></tr>
<tr><th>열린 이슈 / 릴리스</th><td class=n>{s['issues']:,} / {s['releases']}</td></tr>
<tr><th>수집 경로</th><td class=n>{'awesome-mcp-korea 목록' if s['source'] == '목록' else 'GitHub 검색으로 발굴'}</td></tr>
</table>
{f'<div style="margin:10px 0">{topics}</div>' if topics else ''}
{f'<p style="color:var(--dim);font-size:14px">GitHub 소개: {e(s["gh_desc"])}</p>' if s['gh_desc'] else ''}
{install}

<h2>고를 때 볼 것</h2>
<p style="font-size:15px">{e(advice(s))}</p>""",
        depth=1,
    )


def advice(s: dict) -> str:
    """수집한 값에서만 뽑는다 — 안 본 코드를 평가하지 않는다."""
    out = []
    if s["days_idle"] > 180:
        out.append(f"{s['days_idle']}일째 커밋이 없다. MCP 규격이 자주 바뀌는 시기라 그대로 붙으면 깨질 수 있다.")
    elif s["days_idle"] <= 30:
        out.append("최근 한 달 안에 손이 닿았다.")
    if not s["license"]:
        out.append("라이선스가 없다. 업무에 쓰려면 저자에게 확인이 필요하다.")
    if s["readme_len"] < 1000:
        out.append("README 가 짧아 설치·인증 방법을 코드에서 직접 읽어야 할 가능성이 크다.")
    if not s["install"]:
        out.append("README 에서 npx·uvx·pip 실행 줄을 못 찾았다. 직접 클론해 돌리는 형태일 수 있다.")
    if s["stars"] < 5:
        out.append("사용자가 거의 없다 — 먼저 써 보고 이슈를 남겨야 하는 쪽에 가깝다.")
    return " ".join(out) or "눈에 띄는 경고 신호는 없다. 실제 도구 목록은 저장소에서 확인할 것."


def about(d: dict) -> str:
    dropped = "".join(f"<li>{e(r)}</li>" for r in d["dropped"]) or "<li>없음</li>"
    return page(
        f"점수 산식 — {SITE}",
        f"""<div class="back"><a href="index.html">← 전체 순위</a></div>
<header style="margin-top:14px"><h1>어떻게 줄 세웠나</h1>
<p>점수는 사람 손을 안 탄다. 아래 네 항목을 GitHub API 값으로 계산한 합계다.</p></header>

<h2>배점</h2>
<table>
<tr><th>항목</th><th>만점</th><th>계산</th></tr>
<tr><td>인기</td><td class=n>40</td><td>10 × log₁₀(별+1), 40 에서 자름</td></tr>
<tr><td>관리</td><td class=n>30</td><td>마지막 커밋 30일 이내 30 / 90일 20 / 180일 12 / 1년 5 / 그 이상 0</td></tr>
<tr><td>문서</td><td class=n>20</td><td>README 8000자↑ 20 / 3000자↑ 14 / 1000자↑ 8 / 그 외 3</td></tr>
<tr><td>신뢰</td><td class=n>10</td><td>라이선스 5 + 릴리스 존재 5</td></tr>
</table>

<h2>일부러 안 넣은 것</h2>
<p>코드 품질, 도구 개수, 실제 동작 여부는 점수에 없다. 자동으로 확인할 방법이 없는 걸
점수에 섞으면 순위가 의견이 된다. 별 수가 곧 품질이 아니라는 점도 그대로 남겨둔다 —
로그를 씌운 이유가 그거다.</p>

<h2>후보를 어디서 모으나</h2>
<p>두 갈래다. <a href="{e(d['source']['url'])}">{e(d['source']['repo'])}</a> 목록에서 {d['listed']}개,
GitHub 검색을 직접 훑어 {d['found']}개를 주워왔다. 남의 목록 한 장에만 기대면 그쪽이 멈추는 순간
이 순위도 같이 멈추기 때문이다.</p>
<p>검색 결과를 다 넣지는 않는다. 이름에 <code>mcp</code> 가 있거나 <code>mcp-server</code> 토픽이
달렸거나 설명이 스스로 MCP 서버라고 말하는 것만 남긴다. 실행 방식 중 하나로 MCP 를 지원할 뿐인
큰 저장소가 별 수만으로 상위권에 올라오는 걸 막기 위해서다. 한국 여부도 토픽이 아니라 이름과
설명에서만 본다 — 번역기가 지원 언어로 달아둔 <code>korean</code> 토픽은 근거가 못 된다.</p>

<h2>순위 변동은 어떻게 나오나</h2>
<p>매일 그날의 순위·별·점수를 <code>history/</code> 에 한 파일로 남긴다. ▲▼ 는 어제 파일과 비교한
결과고, 별 증가량은 일주일 전 파일과 비교한 결과다. GitHub 이 과거 별 기록을 안 열어주므로
소급해서 만들 수 없다 — 안 돌린 날은 영구히 빈칸이다. 지금 {d['history']['days']}일치를 갖고 있다.</p>

<h2>이번에 빠진 저장소</h2>
<p style="color:var(--dim);font-size:14px">후보에는 있는데 GitHub 에서 접근이 안 됐다(삭제·비공개 추정).</p>
<ul>{dropped}</ul>

<h2>틀린 게 있으면</h2>
<p>분야가 잘못 붙었거나, 서버가 아닌 게 섞였거나, 있어야 할 게 빠졌으면 이슈로 알려주면 고친다.
점수를 손으로 올려주지는 않는다 — 그 순간 이 표는 의견이 된다.</p>""",
    )


def main() -> None:
    d = json.loads((ROOT / "data.json").read_text())
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "s").mkdir(parents=True)

    (DOCS / "index.html").write_text(index(d).replace("</body>", f"<script>{JS}</script></body>"))
    (DOCS / "about.html").write_text(about(d))
    for s in d["servers"]:
        (DOCS / "s" / f"{slug(s['repo'])}.html").write_text(detail(s, d))
    (DOCS / ".nojekyll").write_text("")

    print(f"docs/ — 목록 1 + 상세 {d['count']} + about 1")


if __name__ == "__main__":
    main()
