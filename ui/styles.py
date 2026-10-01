"""Custom styling for the BugHunter Agent Streamlit UI."""

CSS = """
<style>
:root{
  --bg:#f4f6f2; --surface:#ffffff; --surface-soft:#edf2ee; --line:#d9e1dc;
  --text:#17231f; --muted:#64736c; --accent:#087f70; --accent-dark:#07594f;
  --ok:#18724e; --bad:#b63e37; --warn:#946311;
}
html, body, [class*="css"]{ font-family:"Aptos", "Trebuchet MS", sans-serif; color:var(--text); }
.stApp{ background-color:var(--bg); background-image:linear-gradient(rgba(8,127,112,.025) 1px, transparent 1px),linear-gradient(90deg,rgba(8,127,112,.025) 1px, transparent 1px); background-size:28px 28px; }
.block-container{ padding-top:1.4rem; max-width:1240px; }
#MainMenu, footer{ visibility:hidden; }

/* Hero */
.hero{
  background:var(--surface); border:1px solid var(--line); border-top:4px solid var(--accent);
  border-radius:6px; padding:22px 26px; margin-bottom:22px; box-shadow:0 8px 24px rgba(23,35,31,.045);
  animation:rise-in .34s ease-out both;
}
.hero h1{ margin:0; font-size:2rem; font-family:"Aptos Display", "Aptos", sans-serif; color:var(--text); }
.hero p{ margin:.4rem 0 0; color:var(--muted); font-size:.98rem; }
.hero .chips{ margin-top:14px; display:flex; gap:8px; flex-wrap:wrap; }
.chip{ font-size:.75rem; padding:4px 9px; border-radius:4px; border:1px solid var(--line);
  background:var(--surface-soft); color:var(--accent-dark); }

/* Section headers */
.step-title{ display:flex; align-items:center; gap:10px; margin:6px 0 10px; font-weight:650; font-size:1.1rem; }
.step-num{ width:28px; height:28px; border-radius:5px; display:inline-flex; align-items:center; justify-content:center;
  background:var(--accent); color:#fff; font-size:.85rem; font-weight:700; }

/* Cards */
.card{ background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:15px 17px; margin:10px 0; }
.card.step{ border-left:3px solid var(--accent); }
.card .lbl{ color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:0; margin-top:8px; }
.card .val{ font-size:.95rem; line-height:1.45; }
.card .head{ font-weight:650; margin-bottom:2px; }
.pill{ display:inline-block; padding:3px 8px; border-radius:4px; font-size:.72rem; font-weight:650; letter-spacing:0; }
.pill.ok{ background:#e6f3eb; color:var(--ok); border:1px solid #b9d9c4; }
.pill.bad{ background:#fbebe8; color:var(--bad); border:1px solid #ecc3bc; }
.pill.warn{ background:#fff4d9; color:var(--warn); border:1px solid #e7d39c; }
.pill.info{ background:#e4f1ee; color:var(--accent-dark); border:1px solid #b9d7d0; }

/* Iteration divider */
.iter{ display:flex; align-items:center; gap:12px; margin:22px 0 6px; color:var(--accent-dark); font-weight:650; }
.iter:after{ content:""; flex:1; height:1px; background:var(--line); }

/* Loop tracker */
.tracker{ display:flex; gap:6px; margin:6px 0 14px; flex-wrap:wrap; }
.tracker .ph{ flex:1; min-width:110px; text-align:center; padding:10px 6px; border-radius:5px; font-size:.82rem;
  border:1px solid var(--line); background:var(--surface); color:var(--muted); }
.tracker .ph.on{ color:white; border-color:var(--accent); background:var(--accent); font-weight:650; }
.tracker .ph.done{ color:var(--ok); border-color:#b9d9c4; background:#f2f8f3; }

/* Metrics */
.metrics{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:10px 0 16px; }
.metric{ background:var(--surface); border:1px solid var(--line); border-radius:5px; padding:12px 14px; min-width:0; }
.metric .k{ color:var(--muted); font-size:.7rem; text-transform:uppercase; letter-spacing:0; }
.metric .v{ font-size:1.15rem; font-weight:700; margin-top:3px; overflow-wrap:anywhere; }

/* Diff */
.diff-viewer{ font-family:"Cascadia Code", Consolas, monospace; font-size:.82rem; background:#18231f;
  border:1px solid var(--line); border-radius:5px; padding:10px 0; overflow-x:auto; }
.diff-viewer div{ padding:1px 14px; white-space:pre; }
.diff-add{ background:rgba(52,211,153,.14); color:#a7f3d0; }
.diff-del{ background:rgba(248,113,113,.14); color:#fecaca; }
.diff-hunk{ color:#a7d9ce; background:rgba(8,127,112,.15); }
.diff-file{ color:#f3c86b; font-weight:600; }
.diff-ctx{ color:#d2ddd7; }

/* Banner */
.banner{ border-radius:5px; padding:15px 18px; margin:14px 0; border:1px solid var(--line); background:var(--surface); }
.banner.ok{ background:#edf6f0; border-color:#b9d9c4; }
.banner.bad{ background:#fbebe8; border-color:#ecc3bc; }
.banner.warn{ background:#fff7e4; border-color:#e7d39c; }
.banner b{ font-size:1.05rem; }

/* Buttons */
.stButton>button, .stDownloadButton>button{ border-radius:5px; font-weight:600; border:1px solid var(--line); }
.stButton>button[kind="primary"]{ background:var(--accent); border:1px solid var(--accent); color:white; padding:.6rem 1.2rem; }
section[data-testid="stSidebar"]{ background:#eef2ee; border-right:1px solid var(--line); }
.stTabs [data-baseweb="tab"]{ font-weight:600; }
@media(max-width:640px){ .block-container{padding:1rem .85rem 2rem;} .hero{padding:18px;} .hero h1{font-size:1.7rem;} .tracker .ph{min-width:calc(50% - 6px);} }
@keyframes rise-in{from{opacity:0; transform:translateY(6px)} to{opacity:1; transform:translateY(0)}}
@media(prefers-reduced-motion:reduce){.hero{animation:none}}
</style>
"""
