"""Custom styling for the BugHunter Agent Streamlit UI."""

CSS = """
<style>
:root{
  --bg:#0b1020; --card:#111833; --card2:#161f42; --line:#232c4d;
  --text:#e6e9f5; --muted:#8f9bc4; --accent:#6366f1; --accent2:#22d3ee;
  --ok:#34d399; --bad:#f87171; --warn:#fbbf24;
}
html, body, [class*="css"]{ font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif; }
.block-container{ padding-top:1.6rem; max-width:1180px; }
#MainMenu, footer{ visibility:hidden; }

/* Hero */
.hero{
  background: radial-gradient(1200px 300px at 0% 0%, rgba(99,102,241,.35), transparent 60%),
              radial-gradient(900px 300px at 100% 0%, rgba(34,211,238,.22), transparent 60%),
              var(--card);
  border:1px solid var(--line); border-radius:20px; padding:28px 32px; margin-bottom:22px;
}
.hero h1{ margin:0; font-size:2.1rem; letter-spacing:-.02em;
  background:linear-gradient(90deg,#c7d2fe,#67e8f9); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.hero p{ margin:.4rem 0 0; color:var(--muted); font-size:1.02rem; }
.hero .chips{ margin-top:14px; display:flex; gap:8px; flex-wrap:wrap; }
.chip{ font-size:.75rem; padding:4px 10px; border-radius:999px; border:1px solid var(--line);
  background:rgba(255,255,255,.04); color:#c7d2fe; }

/* Section headers */
.step-title{ display:flex; align-items:center; gap:10px; margin:6px 0 10px; font-weight:650; font-size:1.15rem; }
.step-num{ width:28px; height:28px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center;
  background:linear-gradient(135deg,var(--accent),var(--accent2)); color:#fff; font-size:.85rem; font-weight:700; }

/* Cards */
.card{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin:10px 0; }
.card.step{ border-left:4px solid var(--accent); }
.card .lbl{ color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; margin-top:8px; }
.card .val{ font-size:.95rem; line-height:1.45; }
.card .head{ font-weight:650; margin-bottom:2px; }
.pill{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:.72rem; font-weight:650; letter-spacing:.03em; }
.pill.ok{ background:rgba(52,211,153,.15); color:var(--ok); border:1px solid rgba(52,211,153,.4); }
.pill.bad{ background:rgba(248,113,113,.15); color:var(--bad); border:1px solid rgba(248,113,113,.4); }
.pill.warn{ background:rgba(251,191,36,.13); color:var(--warn); border:1px solid rgba(251,191,36,.4); }
.pill.info{ background:rgba(99,102,241,.16); color:#a5b4fc; border:1px solid rgba(99,102,241,.45); }

/* Iteration divider */
.iter{ display:flex; align-items:center; gap:12px; margin:22px 0 6px; color:#c7d2fe; font-weight:650; }
.iter:after{ content:""; flex:1; height:1px; background:linear-gradient(90deg,var(--line),transparent); }

/* Loop tracker */
.tracker{ display:flex; gap:6px; margin:6px 0 14px; flex-wrap:wrap; }
.tracker .ph{ flex:1; min-width:110px; text-align:center; padding:10px 6px; border-radius:12px; font-size:.82rem;
  border:1px solid var(--line); background:var(--card); color:var(--muted); }
.tracker .ph.on{ color:#fff; border-color:transparent; background:linear-gradient(135deg,var(--accent),var(--accent2));
  box-shadow:0 6px 22px rgba(99,102,241,.35); font-weight:650; }
.tracker .ph.done{ color:var(--ok); border-color:rgba(52,211,153,.35); }

/* Metrics */
.metrics{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:10px 0 16px; }
.metric{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }
.metric .k{ color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; }
.metric .v{ font-size:1.5rem; font-weight:700; margin-top:2px; }

/* Diff */
.diff-viewer{ font-family: "JetBrains Mono", "Fira Code", Consolas, monospace; font-size:.82rem; background:#0a0f22;
  border:1px solid var(--line); border-radius:12px; padding:10px 0; overflow-x:auto; }
.diff-viewer div{ padding:1px 14px; white-space:pre; }
.diff-add{ background:rgba(52,211,153,.14); color:#a7f3d0; }
.diff-del{ background:rgba(248,113,113,.14); color:#fecaca; }
.diff-hunk{ color:#93c5fd; background:rgba(59,130,246,.08); }
.diff-file{ color:#fcd34d; font-weight:600; }
.diff-ctx{ color:#b6bfdc; }

/* Banner */
.banner{ border-radius:16px; padding:16px 20px; margin:14px 0; border:1px solid var(--line); }
.banner.ok{ background:rgba(52,211,153,.10); border-color:rgba(52,211,153,.4); }
.banner.bad{ background:rgba(248,113,113,.10); border-color:rgba(248,113,113,.4); }
.banner.warn{ background:rgba(251,191,36,.09); border-color:rgba(251,191,36,.4); }
.banner b{ font-size:1.05rem; }

/* Buttons */
.stButton>button, .stDownloadButton>button{ border-radius:12px; font-weight:600; border:1px solid var(--line); }
.stButton>button[kind="primary"]{ background:linear-gradient(135deg,var(--accent),#4f46e5); border:none; padding:.6rem 1.2rem; }
section[data-testid="stSidebar"]{ background:#0d1430; border-right:1px solid var(--line); }
.stTabs [data-baseweb="tab"]{ font-weight:600; }
</style>
"""
