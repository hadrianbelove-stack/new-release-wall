from flask import Flask, render_template_string, request, redirect, url_for
import json, os, math

app = Flask(__name__)
BASE_FILE = "output/data.json"
CORE_FILE = "output/data_core.json"
CURATED_FILE = "curated_selections.json"

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def load_movies():
    base = load_json(BASE_FILE) or []
    core = {str(m.get("id")): m for m in (load_json(CORE_FILE) or [])}
    merged = []
    for m in base:
        mid = str(m.get("id"))
        mm = dict(m)
        if mid in core:
            # overlay core fields
            for k,v in core[mid].items():
                if v not in (None, [], {}, ""):
                    mm[k] = v
        merged.append(mm)
    return merged

def load_curated():
    if os.path.exists(CURATED_FILE):
        with open(CURATED_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_curated(cur):
    with open(CURATED_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2, ensure_ascii=False)

def movie_status(curated, mid):
    return curated.get(str(mid), "pending")

def provider_badges(m):
    prov = m.get("providers") or {}
    def names(items):
        out=[]
        for it in items or []:
            n = it.get("provider_name") or it.get("provider") or "?"
            out.append(n)
        # unique preserve order
        seen=set(); out2=[]
        for n in out:
            if n not in seen:
                out2.append(n); seen.add(n)
        return out2
    return {
        "stream": names(prov.get("stream")),
        "rent": names(prov.get("rent")),
        "buy": names(prov.get("buy")),
    }

@app.route("/")
def index():
    q = (request.args.get("q") or "").strip().lower()
    status = request.args.get("status") or "all"   # all|pending|approve|reject
    page = max(1, int(request.args.get("page") or 1))
    per_page = min(60, int(request.args.get("per_page") or 24))

    movies = load_movies()
    curated = load_curated()

    # filter
    def match(m):
        if q:
            hay = " ".join(str(m.get(k) or "") for k in ("title","overview","studio")).lower()
            if q not in hay:
                return False
        if status != "all" and movie_status(curated, m.get("id")) != status:
            return False
        return True

    filtered = [m for m in movies if match(m)]
    total = len(filtered)
    pages = max(1, math.ceil(total/per_page))
    page = min(page, pages)
    start = (page-1)*per_page
    batch = filtered[start:start+per_page]

    tmpl = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Curator Admin</title>
<style>
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 16px; background: #0b0f14; color: #e6e9ef;}
h1 { margin: 0 0 12px 0; font-weight: 700; }
.topbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
input[type=search]{ padding:8px 10px; border-radius:10px; border:1px solid #2a2f3a; background:#11161d; color:#e6e9ef; width:280px;}
select, button { padding:8px 10px; border-radius:10px; border:1px solid #2a2f3a; background:#11161d; color:#e6e9ef; cursor:pointer;}
button.primary{ background:#1f6feb; border-color:#1f6feb; }
.grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(220px,1fr)); gap:16px; margin-top:16px;}
.card { perspective: 1000px; }
.flip { position:relative; width:100%; height:360px; transform-style: preserve-3d; transition: transform .35s ease; }
.card:hover .flip{ transform: rotateY(180deg); }
.face { position:absolute; inset:0; backface-visibility: hidden; border-radius:14px; overflow:hidden; box-shadow: 0 4px 18px rgba(0,0,0,.35); }
.front { background: #0f141b; display:flex; flex-direction:column;}
.poster { flex:1; background:#0b0f14 center/cover no-repeat; }
.meta { padding:10px 12px; display:flex; flex-direction:column; gap:6px;}
.title { font-weight:700; font-size:14px; line-height:1.2;}
.kv { font-size:12px; color:#aab2bf;}
.badges { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px;}
.badge { font-size:11px; padding:3px 8px; border-radius:999px; border:1px solid #303643; background:#141a23;}
.status { font-size:11px; padding:3px 8px; border-radius:999px; }
.status.pending{ background:#3a3f4a; }
.status.approve{ background:#1a7f37; }
.status.reject{ background:#8b0000; }
.back { background:#0f141b; transform: rotateY(180deg); padding:12px; display:flex; flex-direction:column; gap:8px;}
.actions { display:flex; gap:8px; }
.actions a { text-decoration:none; }
.btn { border:1px solid #303643; background:#141a23; color:#e6e9ef; padding:8px 10px; border-radius:10px; display:inline-block;}
.btn.approve{ background:#1a7f37; border-color:#1a7f37;}
.btn.reject{ background:#8b0000; border-color:#8b0000;}
.pagination { margin-top:16px; display:flex; gap:8px; align-items:center; }
.count { opacity:.8; font-size:12px;}
.topbar form {display:flex; gap:8px; align-items:center;}
hr.sep{border:none; border-top:1px solid #2a2f3a; margin:12px 0;}
.small { font-size:12px; color:#aab2bf;}
</style>
</head>
<body>
  <div class="topbar">
    <h1>Curator Admin</h1>
    <span class="count">{{total}} results</span>
    <form method="get" action="/">
      <input type="search" name="q" value="{{q}}" placeholder="Search title, studio, overview"/>
      <select name="status">
        <option value="all" {% if status=='all' %}selected{% endif %}>All</option>
        <option value="pending" {% if status=='pending' %}selected{% endif %}>Pending</option>
        <option value="approve" {% if status=='approve' %}selected{% endif %}>Approved</option>
        <option value="reject" {% if status=='reject' %}selected{% endif %}>Rejected</option>
      </select>
      <select name="per_page">
        {% for n in [12,24,36,48,60] %}
          <option value="{{n}}" {% if per_page==n %}selected{% endif %}>{{n}} / page</option>
        {% endfor %}
      </select>
      <button type="submit" class="primary">Filter</button>
    </form>
    <form method="post" action="{{url_for('bulk')}}">
      <input type="hidden" name="q" value="{{q}}"/>
      <input type="hidden" name="status" value="{{status}}"/>
      <input type="hidden" name="scope_count" value="{{total}}"/>
      <button name="action" value="approve" class="btn approve">Bulk Approve (filtered)</button>
      <button name="action" value="reject" class="btn reject">Bulk Reject (filtered)</button>
    </form>
  </div>

  <div class="grid">
    {% for m in batch %}
      {% set mid = m.get('id') %}
      {% set st = curated.get(mid|string, 'pending') %}
      {% set prov = providers[m.get('id')|string] %}
      <div class="card">
        <div class="flip">
          <div class="face front">
            <div class="poster" style="background-image:url('{{m.get('poster_url') or ''}}')"></div>
            <div class="meta">
              <div class="title">{{m.get('title') or 'Untitled'}}</div>
              <div class="kv">{{m.get('year') or ''}} • {{m.get('studio') or 'Studio n/a'}}</div>
              <div class="badges">
                {% for n in prov.stream %}<span class="badge">▶ {{n}}</span>{% endfor %}
                {% for n in prov.rent   %}<span class="badge">⟲ {{n}}</span>{% endfor %}
                {% for n in prov.buy    %}<span class="badge">⤓ {{n}}</span>{% endfor %}
                <span class="status {{st}}">{{st}}</span>
              </div>
            </div>
          </div>
          <div class="face back">
            <div><b>Directors:</b> {{ (m.get('credits') or {}).get('director') or [] }}</div>
            <div><b>Cast:</b> {{ (m.get('credits') or {}).get('cast') or [] }}</div>
            <div><b>Runtime:</b> {{ m.get('runtime') or 'n/a' }} min</div>
            <div class="small">{{ (m.get('overview') or '')[:240] }}</div>
            <hr class="sep"/>
            <div class="actions">
              <a class="btn approve" href="{{url_for('curate', mid=mid, action='approve', q=q, status=status, page=page, per_page=per_page)}}">✓ Approve</a>
              <a class="btn reject"  href="{{url_for('curate', mid=mid, action='reject',  q=q, status=status, page=page, per_page=per_page)}}">✗ Reject</a>
              <a class="btn"         href="{{url_for('curate', mid=mid, action='pending', q=q, status=status, page=page, per_page=per_page)}}">• Pending</a>
            </div>
          </div>
        </div>
      </div>
    {% endfor %}
  </div>

  <div class="pagination">
    {% if page>1 %}<a class="btn" href="{{url_for('index', q=q, status=status, page=page-1, per_page=per_page)}}">Prev</a>{% endif %}
    <span class="small">Page {{page}} / {{pages}}</span>
    {% if page<pages %}<a class="btn" href="{{url_for('index', q=q, status=status, page=page+1, per_page=per_page)}}">Next</a>{% endif %}
  </div>
</body>
</html>
    """
    prov_map = {str(m.get("id")): provider_badges(m) for m in batch}
    return render_template_string(
        tmpl,
        movies=load_movies(),
        curated=load_curated(),
        providers=prov_map,
        batch=batch,
        total=total, page=page, pages=pages, per_page=per_page,
        q=q, status=status
    )

@app.route("/curate/<int:mid>/<action>")
def curate(mid, action):
    q = request.args.get("q") or ""
    status = request.args.get("status") or "all"
    page = request.args.get("page") or "1"
    per_page = request.args.get("per_page") or "24"
    cur = load_curated()
    cur[str(mid)] = action
    save_curated(cur)
    return redirect(url_for("index", q=q, status=status, page=page, per_page=per_page))

@app.post("/bulk")
def bulk():
    action = request.form.get("action")
    q = (request.form.get("q") or "").strip().lower()
    status = request.form.get("status") or "all"
    movies = load_movies()
    cur = load_curated()
    def match(m):
        if q:
            hay = " ".join(str(m.get(k) or "") for k in ("title","overview","studio")).lower()
            if q not in hay:
                return False
        if status != "all" and movie_status(cur, m.get("id")) != status:
            return False
        return True
    count = 0
    for m in movies:
        if match(m):
            cur[str(m.get("id"))] = action
            count += 1
    save_curated(cur)
    return redirect(url_for("index", q=q, status=status))

if __name__ == "__main__":
    app.run(port=5000, debug=True)