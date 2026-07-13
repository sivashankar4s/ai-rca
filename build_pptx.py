#!/usr/bin/env python
"""Build the AI-RCA client deck as a designed, editable dark-theme PPTX."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from datetime import datetime
from pathlib import Path

# ── palette ─────────────────────────────────────────────
BG      = RGBColor(0x0A, 0x0F, 0x1E)
CARD    = RGBColor(0x1E, 0x2D, 0x47)
CARD2   = RGBColor(0x16, 0x20, 0x36)
BORDER  = RGBColor(0x2A, 0x3F, 0x5E)
TEXT    = RGBColor(0xE8, 0xF0, 0xFE)
MUTED   = RGBColor(0x8F, 0xA8, 0xC8)
ACCENT  = RGBColor(0x00, 0xB4, 0xD8)
ROCHE   = RGBColor(0x00, 0x5D, 0xAB)
AMBER   = RGBColor(0xF0, 0xA5, 0x00)
GREEN   = RGBColor(0x22, 0xC5, 0x5E)
RED     = RGBColor(0xEF, 0x44, 0x44)
PURPLE  = RGBColor(0xA8, 0x55, 0xF7)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
SW, SH = prs.slide_width, prs.slide_height

def slide():
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = BG
    r.line.fill.background()
    r.shadow.inherit = False
    return s

def no_line(shape):
    shape.line.fill.background()
    shape.shadow.inherit = False

def box(s, l, t, w, h, fill=None, line=None, radius=0.10):
    shp = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if fill is not None else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = Pt(1)
    shp.shadow.inherit = False
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    return shp

def text(s, l, t, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         space_after=4, line_spacing=1.05):
    """runs: list of paragraphs; each paragraph is list of (txt,size,color,bold)."""
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("left","right","top","bottom"):
        setattr(tf, f"margin_{m}", Emu(0))
    for pi, para in enumerate(runs):
        p = tf.paragraphs[0] if pi == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space_after); p.space_before = Pt(0)
        p.line_spacing = line_spacing
        for (txt, size, color, bold) in para:
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
            r.font.name = "Segoe UI"
    return tb

def kicker(s, txt):
    text(s, 0.9, 0.6, 11, 0.4, [[(txt.upper(), 12, ACCENT, True)]])

def title(s, lines, size=34, top=1.05):
    runs = [[(ln, size, TEXT, True)] for ln in lines]
    text(s, 0.9, top, 11.5, 1.4, runs, line_spacing=1.0)

def lead(s, txt, top, w=11.0):
    text(s, 0.9, top, w, 0.8, [[(txt, 14, MUTED, False)]], line_spacing=1.15)

def card(s, l, t, w, h, icon, head, body, accent=ACCENT, fill=CARD):
    box(s, l, t, w, h, fill=fill, line=BORDER)
    pad = 0.22
    text(s, l+pad, t+pad-0.02, w-2*pad, 0.4, [[(icon, 17, accent, False)]])
    text(s, l+pad, t+pad+0.42, w-2*pad, 0.4, [[(head, 13.5, TEXT, True)]])
    text(s, l+pad, t+pad+0.86, w-2*pad, h-pad-0.9,
         [[(body, 10.8, MUTED, False)]], line_spacing=1.12)

def footer(s, n):
    text(s, 0.9, 7.02, 6, 0.3, [[("Sentinel AI · Roche DS Platform", 9, MUTED, False)]])
    text(s, 11.6, 7.02, 1.4, 0.3, [[(f"{n:02d} / 15", 9, MUTED, False)]], align=PP_ALIGN.RIGHT)

# ═══════════════════════════════════════════════════════════════
# 1 · COVER
# ═══════════════════════════════════════════════════════════════
s = slide()
box(s, 0, 0, 13.333, 7.5, fill=None)  # keep bg
# glow accent block
g = box(s, 0, 0, 5.5, 7.5, fill=ROCHE); g.fill.fore_color.rgb = RGBColor(0x0C,0x1A,0x33);
text(s, 0.9, 1.0, 10, 0.4, [[("⚙  ROCHE DS PLATFORM · AI-POWERED RELIABILITY", 12, ACCENT, True)]])
text(s, 0.85, 1.9, 11.5, 2.2, [[("Sentinel", 60, TEXT, True)],
                               [("AI", 60, ACCENT, True)]], line_spacing=0.98)
text(s, 0.9, 4.5, 10.6, 1.0,
     [[("Watch every pipeline service, then go from a raw failure to the exact root cause, the fix, "
        "and a one-click log deep-link — in 60 seconds, not hours. No AWS expertise required.", 16, MUTED, False)]],
     line_spacing=1.2)
pills = ["Built & running today", "Service Health monitoring", "Claude AI RCA", "GitHub Code Intelligence"]
x = 0.9
for p in pills:
    w = 0.3 + 0.115*len(p)
    box(s, x, 5.9, w, 0.5, fill=CARD, line=BORDER, radius=0.5)
    text(s, x, 5.99, w, 0.35, [[(p, 11.5, TEXT, False)]], align=PP_ALIGN.CENTER)
    x += w + 0.2

# ═══════════════════════════════════════════════════════════════
# 2 · PROBLEM
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "The Problem")
title(s, ["Manual RCA is slow, error-prone", "& expert-only detective work"])
lead(s, "When dp_monitor_db11224 lights up with FAILED records, an on-call engineer repeats four "
        "manual steps — each needing deep platform knowledge.", 2.05)
pains = [
    ("1", "Query Athena by hand", "Write SQL, guess the time window, filter for FAILED — 10–20 min each."),
    ("2", "Author CloudWatch queries from scratch", "Must know log-group names, fields, error codes. One slip = zero results."),
    ("3", "Read hundreds of log lines", "Correlate trace IDs, device IDs, error codes by eye. Easy to miss the pattern."),
    ("4", "Write the RCA report", "Document cause, impact, fix, escalation — another 30–60 min of work."),
]
ty = 2.75
for num, h, b in pains:
    box(s, 0.9, ty, 11.5, 0.82, fill=RGBColor(0x1C,0x18,0x24), line=RGBColor(0x4A,0x2A,0x2E))
    box(s, 1.08, ty+0.21, 0.42, 0.42, fill=RGBColor(0x3A,0x20,0x24), line=None, radius=0.5)
    text(s, 1.08, ty+0.27, 0.42, 0.35, [[(num, 14, RED, True)]], align=PP_ALIGN.CENTER)
    text(s, 1.7, ty+0.11, 10.5, 0.35, [[(h, 13.5, TEXT, True)]])
    text(s, 1.7, ty+0.44, 10.5, 0.35, [[(b, 11, MUTED, False)]])
    ty += 0.95
box(s, 0.9, 6.62, 11.5, 0.001, fill=None)
text(s, 0.9, 6.68, 11.5, 0.4,
     [[("Total: ", 12.5, TEXT, True), ("1–3 hours of senior-engineer time per incident — the biggest drag on on-call.", 12.5, MUTED, False)]])
footer(s, 2)

# ═══════════════════════════════════════════════════════════════
# 3 · USERS & USE CASES
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Who It's For · Use Cases")
title(s, ["One tool, three audiences — zero prerequisite knowledge"])
personas = [
    ("👨‍💻", "PLATFORM ENGINEER", "On-Call SRE",
     "Paged at 2 AM for 50+ failing records. Needs the root cause now — without touching Athena or CloudWatch by hand."),
    ("📊", "QA / TEST ENGINEER", "QA Analyst",
     "Validates pipeline health after each deploy. Confirms no new failure patterns crept in — no deep AWS skills needed."),
    ("🧑‍💼", "TECH LEAD / MANAGER", "Engineering Lead",
     "Reads the executive summary at stand-up and shares a stakeholder-ready status — without opening a console."),
]
cw = 3.7; gap = 0.28; x = 0.9
for icon, role, name, body in personas:
    box(s, x, 2.2, cw, 2.55, fill=CARD, line=BORDER)
    text(s, x+0.24, 2.42, cw-0.4, 0.5, [[(icon, 24, TEXT, False)]])
    text(s, x+0.24, 3.05, cw-0.4, 0.3, [[(role, 10.5, ACCENT, True)]])
    text(s, x+0.24, 3.35, cw-0.4, 0.35, [[(name, 15, TEXT, True)]])
    text(s, x+0.24, 3.78, cw-0.4, 0.9, [[(body, 11, MUTED, False)]], line_spacing=1.12)
    x += cw + gap
box(s, 0.9, 5.05, 11.5, 1.55, fill=RGBColor(0x0E,0x1F,0x38), line=RGBColor(0x1E,0x4A,0x6E))
text(s, 1.15, 5.25, 11.0, 0.35, [[("The barrier removed", 13, TEXT, True)]])
text(s, 1.15, 5.62, 11.0, 0.9,
     [[("No need to know Athena SQL, CloudWatch Insights syntax, log-group paths, or which error codes "
        "map to which components. A junior engineer can now run a full RCA — the only prerequisite is "
        "read-only AWS credentials, supplied live in the app.", 12, MUTED, False)]], line_spacing=1.2)
footer(s, 3)

# ═══════════════════════════════════════════════════════════════
# 4 · SOLUTION / FEATURES
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "The Solution · What You Get Today")
title(s, ["A two-step web app that runs the whole investigation for you"])
feats = [
    ("🔍", "1 · Fetch failures", "Pick a range (1h/1d/1w or custom) + optional filters. Athena returns a paginated FAILED table in seconds."),
    ("🧠", "2 · Analyze", "Select the rows that matter, click Analyze. The AI hunts the logs and returns grouped root causes."),
    ("📋", "Failure groups", "Error pattern, root cause, category, impact count, immediate action, likely fix, affected files, escalation."),
    ("📝", "Executive summary", "A 2–3 sentence, stakeholder-ready report generated automatically. Copy, paste into a ticket, done."),
    ("🔗", "One-click log deep-links", "Every group carries a ready-made CloudWatch / Grafana link — right query, log group, and time window."),
    ("🕑", "Recurring-issue memory", "Repeat failures auto-link to a persistent RCA case, so 'we've seen this before' is flagged for you."),
]
cols = 3; cw = 3.7; ch = 1.62; gx = 0.28; gy = 0.28; x0 = 0.9; y0 = 2.05
for idx, (ic, h, b) in enumerate(feats):
    r, c = divmod(idx, cols)
    card(s, x0 + c*(cw+gx), y0 + r*(ch+gy), cw, ch, ic, h, b,
         accent=[ACCENT,ACCENT,GREEN,AMBER,PURPLE,RED][idx])
box(s, 0.9, 5.75, 11.5, 0.9, fill=RGBColor(0x0E,0x1F,0x38), line=RGBColor(0x1E,0x4A,0x6E))
text(s, 1.15, 5.92, 11.0, 0.6,
     [[("How to use it — 4 clicks:  ", 12.5, TEXT, True),
       ("open the app → choose a time range → Fetch Failures → tick rows → Analyze Root Cause.", 12.5, MUTED, False)]],
     line_spacing=1.15)
footer(s, 4)

# ═══════════════════════════════════════════════════════════════
# 5 · WORKFLOW
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "How It Works")
title(s, ["From alert to actionable RCA in under 60 seconds"])
def flowrow(s, y, steps, label):
    text(s, 0.9, y, 11, 0.3, [[(label, 10.5, MUTED, True)]])
    n = len(steps); cw = 2.15; gap = (11.5 - n*cw)/(n-1)
    x = 0.9
    for num, h, b, col in steps:
        box(s, x, y+0.35, cw, 1.35, fill=CARD, line=BORDER)
        box(s, x+cw/2-0.24, y+0.5, 0.48, 0.48, fill=col, line=None, radius=0.5)
        text(s, x+cw/2-0.24, y+0.58, 0.48, 0.35, [[(num, 14, RGBColor(0xFF,0xFF,0xFF), True)]], align=PP_ALIGN.CENTER)
        text(s, x+0.12, y+1.05, cw-0.24, 0.3, [[(h, 11.5, TEXT, True)]], align=PP_ALIGN.CENTER)
        text(s, x+0.12, y+1.34, cw-0.24, 0.35, [[(b, 9, MUTED, False)]], align=PP_ALIGN.CENTER, line_spacing=1.0)
        x += cw + gap
flowrow(s, 1.95, [
    ("1","Open & range","Default last 1h",ROCHE),
    ("2","Fetch","Athena query runs",ROCHE),
    ("3","Select","Tick rows / all",ROCHE),
    ("4","Analyze","AI pipeline runs",ACCENT),
    ("5","Read","Groups + links",GREEN),
], "WHAT THE USER DOES")
flowrow(s, 4.35, [
    ("A","Summarize","Find error codes",ACCENT),
    ("B","Gen queries","3 log queries",ACCENT),
    ("C","Run queries","Parallel search",AMBER),
    ("D","Group","Correlate → causes",ACCENT),
    ("E","Render","Show in UI",GREEN),
], "WHAT THE SYSTEM DOES AUTOMATICALLY (BEHIND STEP 4)")
footer(s, 5)

# ═══════════════════════════════════════════════════════════════
# 6 · ARCHITECTURE
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Architecture")
title(s, ["A clean three-layer design"])
lead(s, "Browser SPA → FastAPI orchestrator → pluggable AWS & AI backends. Each layer swappable "
        "without touching the others.", 1.75)
def layer(s, y, h, label, lcol, chips):
    box(s, 0.9, y, 11.5, h, fill=CARD2, line=lcol)
    box(s, 1.15, y-0.14, 0.28+0.1*len(label), 0.3, fill=BG, line=lcol, radius=0.5)
    text(s, 1.25, y-0.11, 4, 0.25, [[(label.upper(), 9.5, lcol, True)]])
    x = 1.2
    for c in chips:
        w = 0.35 + 0.1*len(c)
        box(s, x, y+0.32, w, 0.44, fill=RGBColor(0x14,0x1D,0x30), line=BORDER)
        text(s, x, y+0.4, w, 0.3, [[(c, 10.5, TEXT, False)]], align=PP_ALIGN.CENTER)
        x += w + 0.15
layer(s, 2.55, 0.95, "Frontend · Browser SPA", PURPLE,
      ["🖥 HTML/CSS/JS", "📋 Failure table", "📊 RCA results", "🔗 Log deep-links", "⚙ Config drawer"])
text(s, 0.9, 3.55, 11.5, 0.25, [[("↕  REST JSON · POST /api/failures · POST /api/analyze", 10, MUTED, False)]], align=PP_ALIGN.CENTER)
layer(s, 3.85, 0.95, "Backend · FastAPI (Python 3.13)", ACCENT,
      ["🎼 Orchestrator", "🧩 Plugin registry", "🗄 Data strategy", "📜 Log strategy", "🤖 LLM strategy", "💾 Postgres"])
text(s, 0.9, 4.85, 11.5, 0.25, [[("↕  boto3 (AWS SDK) · HTTPS (Claude API) · MCP (GitHub)", 10, MUTED, False)]], align=PP_ALIGN.CENTER)
box(s, 0.9, 5.15, 5.6, 0.95, fill=CARD2, line=AMBER)
box(s, 1.15, 5.01, 1.5, 0.3, fill=BG, line=AMBER, radius=0.5); text(s, 1.25, 5.04, 3, 0.25, [[("AWS SERVICES", 9.5, AMBER, True)]])
for i,c in enumerate(["🏛 Athena","📡 CloudWatch","📁 S3","🔑 IAM"]):
    box(s, 1.2+i*1.28, 5.47, 1.18, 0.44, fill=RGBColor(0x14,0x1D,0x30), line=BORDER)
    text(s, 1.2+i*1.28, 5.55, 1.18, 0.3, [[(c, 9.5, TEXT, False)]], align=PP_ALIGN.CENTER)
box(s, 6.8, 5.15, 5.6, 0.95, fill=CARD2, line=GREEN)
box(s, 7.05, 5.01, 2.4, 0.3, fill=BG, line=GREEN, radius=0.5); text(s, 7.15, 5.04, 4, 0.25, [[("AI & CODE INTELLIGENCE", 9.5, GREEN, True)]])
for i,c in enumerate(["🧠 Claude (Anthropic)","🔗 GitHub MCP server"]):
    box(s, 7.1+i*2.6, 5.47, 2.45, 0.44, fill=RGBColor(0x14,0x1D,0x30), line=BORDER)
    text(s, 7.1+i*2.6, 5.55, 2.45, 0.3, [[(c, 10, TEXT, False)]], align=PP_ALIGN.CENTER)
footer(s, 6)

# ═══════════════════════════════════════════════════════════════
# 7 · DESIGN PATTERNS
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Design Patterns · Why It's Built to Last")
title(s, ["Strategy + Plugin Registry = swap any backend in one file"])
pts = [
    ("🧩", "Strategy pattern", "The orchestrator depends only on three interfaces — DataSource, LLM, LogAnalysis. It never knows which backend runs."),
    ("🔌", "Plugin registry", "Providers wired at request time from config. Athena↔local file, CloudWatch↔Loki, Claude↔any model — flipped by env var."),
    ("➕", "Open for extension", "A new backend = one new provider file. Orchestrator and API routes never change. Zero regression risk."),
    ("🧪", "Testable by design", "Local-file + fake-LLM providers run the whole pipeline with no AWS, no keys — ideal for CI and demos."),
]
y = 2.15
for ic, h, b in pts:
    box(s, 0.9, y, 0.5, 0.5, fill=RGBColor(0x0E,0x24,0x30), line=None, radius=0.25)
    text(s, 0.9, y+0.06, 0.5, 0.35, [[(ic, 15, ACCENT, False)]], align=PP_ALIGN.CENTER)
    text(s, 1.55, y-0.02, 5.6, 0.35, [[(h, 14, TEXT, True)]])
    text(s, 1.55, y+0.34, 5.6, 0.7, [[(b, 11, MUTED, False)]], line_spacing=1.1)
    y += 1.15
# code panel
box(s, 7.4, 2.15, 5.0, 4.4, fill=RGBColor(0x0D,0x14,0x24), line=BORDER)
code = [
    [("# Orchestrator depends on abstractions", 11, RGBColor(0x5B,0x6B,0x85), False)],
    [("class ", 11.5, PURPLE, True), ("RCAOrchestrator:", 11.5, ACCENT, False)],
    [("  def __init__(self, data, llm, logs):", 11.5, MUTED, False)],
    [("    self.data = data   ", 11.5, MUTED, False), ("# DataSource", 10.5, RGBColor(0x5B,0x6B,0x85), False)],
    [("    self.llm  = llm    ", 11.5, MUTED, False), ("# LLM", 10.5, RGBColor(0x5B,0x6B,0x85), False)],
    [("    self.logs = logs   ", 11.5, MUTED, False), ("# LogAnalysis", 10.5, RGBColor(0x5B,0x6B,0x85), False)],
    [("", 6, MUTED, False)],
    [("# Registry picks providers from .env", 11, RGBColor(0x5B,0x6B,0x85), False)],
    [("data = registry.", 11.5, MUTED, False), ("data_source", 11.5, ACCENT, False), ("(\"athena\")", 11.5, GREEN, False)],
    [("llm  = registry.", 11.5, MUTED, False), ("llm", 11.5, ACCENT, False), ("(\"anthropic\")", 11.5, GREEN, False)],
    [("logs = registry.", 11.5, MUTED, False), ("log_backend", 11.5, ACCENT, False), ("(\"cloudwatch\")", 11.5, GREEN, False)],
    [("", 6, MUTED, False)],
    [("# Swap a backend? Add ONE file.", 11, RGBColor(0x5B,0x6B,0x85), False)],
]
text(s, 7.7, 2.45, 4.5, 3.9, code, line_spacing=1.15, space_after=2)
footer(s, 7)

# ═══════════════════════════════════════════════════════════════
# 8 · AI PIPELINE
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Inside the AI")
title(s, ["The LLM runs 5 precise jobs — each grounded in real failure data"])
jobs = [
    ("①","Summarize failures","Reads up to 50 records; finds failing components, error codes, stage clustering, time-based bursts.",ACCENT),
    ("②","Generate log queries","Writes 3 targeted queries: error-code search, component+ERROR filter, trace-ID correlation.",ACCENT),
    ("③","Execute & collect","Runs the queries in parallel against the configured log backend and gathers relevant lines.",AMBER),
    ("④","RCA + grouping","Correlates records + logs into structured groups with real field values — no vague 'check the logs'.",GREEN),
    ("⑤","Executive summary","Distills all groups into a leadership-ready paragraph, ready to paste into an incident update.",PURPLE),
    ("🛡","Guardrails","Prompts demand actual values (component, error_code, stage). Robust JSON parsing tolerates markdown.",ACCENT),
]
cw=3.7; ch=1.85; gx=0.28; gy=0.3; x0=0.9; y0=2.1
for idx,(ic,h,b,col) in enumerate(jobs):
    r,c = divmod(idx,3)
    fill = RGBColor(0x11,0x22,0x30) if idx==5 else CARD
    card(s, x0+c*(cw+gx), y0+r*(ch+gy), cw, ch, ic, h, b, accent=col, fill=fill)
footer(s, 8)

# ═══════════════════════════════════════════════════════════════
# 9 · CODE INTELLIGENCE
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Beyond RCA · Source Code Intelligence")
title(s, ["From 'why did it fail' to 'is the fix any good'"])
lead(s, "A GitHub MCP integration brings repo, branch, and PR awareness into the same app — and an "
        "AI reviewer inspects the diff.", 1.75)
ci = [
    ("🔗","Repo & PR browser","Lists repo info, branches, and pull requests via the GitHub MCP server — no console-hopping.",ACCENT),
    ("🛡","AI code review","One click fetches a PR/branch diff and sends it to Claude for a severity-ranked review.",AMBER),
    ("🔀","Related code changes","Surfaces the commits & PRs in the failure's time window — the likely change that broke things.",GREEN),
]
for i,(ic,h,b,col) in enumerate(ci):
    card(s, 0.9+i*3.98, 2.55, 3.7, 1.75, ic, h, b, accent=col)
labels = ["🛡 Security & secrets","🗄 SQL injection","📐 SonarQube smells","🎨 Formatting","💡 Feature ideas"]
x=0.9
for lab in labels:
    w = 0.4 + 0.12*len(lab)
    box(s, x, 4.75, w, 0.55, fill=CARD, line=BORDER)
    text(s, x, 4.87, w, 0.3, [[(lab, 11.5, TEXT, False)]], align=PP_ALIGN.CENTER)
    x += w + 0.2
text(s, 0.9, 5.7, 11.5, 0.4, [[("The AI reviewer checks every diff for the five categories above — ranked critical → info.", 12, MUTED, False)]])
footer(s, 9)

# ═══════════════════════════════════════════════════════════════
# 10 · SERVICE HEALTH
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Beyond RCA · Proactive Service Health")
title(s, ["See every pipeline service at a glance —", "then drill into exactly why it failed"])
hfeats = [
    ("🩺", "Health at a glance", "Glue jobs, workflows, Lambdas & DataSync tasks each show up/down + a failure count, colour-coded, with a running total."),
    ("🗂", "Monitoring profiles", "Group resources into named profiles (e.g. 'Prod ETL') and switch between them — each team watches just its own pipelines."),
    ("📅", "Any time window", "Count failures over 1h / 24h / 7d or a custom date range — the same range carries into the drill-down."),
    ("🔎", "Run-history drill-down", "Click a service to see its individual runs / invocations — success or failure — with timestamps and error detail."),
    ("🧠", "Fetch failure reasons", "One click pulls the CloudWatch log reasons behind the failures — the same detector that powers RCA."),
    ("🔑", "Zero console-hopping", "All from read-only AWS credentials supplied in-app — no Glue, Lambda, or DataSync console needed."),
]
cols = 3; cw = 3.7; ch = 1.62; gx = 0.28; gy = 0.28; x0 = 0.9; y0 = 2.05
haccents = [ACCENT, ROCHE, PURPLE, GREEN, AMBER, RED]
for idx, (ic, h, b) in enumerate(hfeats):
    r, c = divmod(idx, cols)
    card(s, x0 + c*(cw+gx), y0 + r*(ch+gy), cw, ch, ic, h, b, accent=haccents[idx])
box(s, 0.9, 5.75, 11.5, 0.9, fill=RGBColor(0x0E,0x1F,0x38), line=RGBColor(0x1E,0x4A,0x6E))
text(s, 1.15, 5.92, 11.0, 0.6,
     [[("Reactive RCA, meet proactive monitoring:  ", 12.5, TEXT, True),
       ("Service Health surfaces failing jobs, workflows, and functions on demand — and drills down "
        "to the root-cause logs in the same app.", 12.5, MUTED, False)]],
     line_spacing=1.15)
footer(s, 10)

# ═══════════════════════════════════════════════════════════════
# 11 · ALL-FEATURE WORKFLOW (DIAGRAM)
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "End-to-End · How Every Feature Flows")
title(s, ["One app, three workflows —", "from setup to resolved incident"])
box(s, 0.9, 2.0, 11.5, 0.6, fill=RGBColor(0x0E,0x1F,0x38), line=RGBColor(0x1E,0x4A,0x6E))
text(s, 1.15, 2.15, 11.0, 0.4,
     [[("①  Setup (once):  ", 11.5, TEXT, True),
       ("AWS credentials, CloudWatch log groups, health profiles, GitHub repo — all in the Config tab.",
        11.5, MUTED, False)]])


def lane(s, y, col, label, steps):
    box(s, 0.9, y, 11.5, 0.72, fill=CARD, line=BORDER)
    text(s, 1.12, y+0.22, 2.2, 0.32, [[(label, 12.5, col, True)]])
    x = 3.35
    bw = 1.96
    for i, st in enumerate(steps):
        box(s, x, y+0.16, bw, 0.4, fill=RGBColor(0x14,0x1D,0x30), line=BORDER)
        text(s, x, y+0.235, bw, 0.3, [[(st, 8.5, TEXT, False)]], align=PP_ALIGN.CENTER)
        x += bw
        if i < len(steps) - 1:
            text(s, x, y+0.2, 0.28, 0.3, [[("→", 12, ACCENT, True)]], align=PP_ALIGN.CENTER)
            x += 0.28


lane(s, 2.8, ACCENT, "🩺 Service Health",
     ["Pick profile + window", "Up/down + counts", "Drill into service", "Fetch CW reasons"])
lane(s, 3.62, PURPLE, "🧠 Root Cause Analysis",
     ["Fetch failures", "Select records", "AI analyzes logs", "Causes + log links"])
lane(s, 4.44, AMBER, "🔗 Code Intelligence",
     ["Browse repo / PRs", "AI code review", "Ranked findings", "Related change"])
box(s, 0.9, 5.5, 11.5, 0.95, fill=RGBColor(0x11,0x22,0x30), line=BORDER)
text(s, 1.15, 5.7, 11.0, 0.6,
     [[("The payoff:  ", 12, GREEN, True),
       ("failures caught early on the Health dashboard, root-caused in seconds, and the suspect code "
        "change reviewed — without leaving the app or opening an AWS console.", 12, MUTED, False)]],
     line_spacing=1.15)
footer(s, 11)

# ═══════════════════════════════════════════════════════════════
# 12 · ADVANTAGES
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Why Sentinel AI")
title(s, ["The advantages that matter to you"])
adv = [
    ("~98%","Faster to root cause","1–3 hours of manual work collapses to under 2 minutes."),
    ("0","Prerequisite knowledge","No Athena SQL, no CloudWatch syntax, no tribal knowledge."),
    ("1","File to add a backend","Vendor-flexible by design — swap AWS, log source, or model."),
    ("Live","Runtime config","Credentials, region, DB, and model changed in-app — no restart."),
]
for i,(n,h,b) in enumerate(adv):
    x = 0.9+i*2.95
    box(s, x, 2.15, 2.72, 1.85, fill=CARD, line=BORDER)
    text(s, x+0.22, 2.35, 2.4, 0.6, [[(n, 34, ACCENT, True)]])
    text(s, x+0.22, 3.0, 2.4, 0.35, [[(h, 12.5, TEXT, True)]])
    text(s, x+0.22, 3.35, 2.4, 0.6, [[(b, 10.5, MUTED, False)]], line_spacing=1.1)
card(s, 0.9, 4.3, 5.75, 2.0, "🔒", "Secure & auditable",
     "Secrets are write-only in the UI (never returned to the browser). Every fetch is snapshotted; "
     "every RCA is persisted with a case history for a full audit trail.", accent=GREEN)
card(s, 6.85, 4.3, 5.55, 2.0, "🧭", "Consistent & repeatable",
     "The same rigorous 5-step investigation runs every time — no steps skipped under pressure, "
     "no variation between engineers, day or night.", accent=ACCENT)
footer(s, 12)

# ═══════════════════════════════════════════════════════════════
# 13 · IMPACT
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Impact")
title(s, ["Time saved per incident"])
lead(s, "Measured against the manual 4-step RCA for a typical 50-record pipeline failure.", 1.75)
mets = [
    ("Manual: 15–30 min","<30s","Failure discovery","✓ Instant on click",GREEN),
    ("Manual: 20–45 min","<60s","Log query + review","✓ Auto-generated",AMBER),
    ("Manual: 30–60 min","<90s","Full RCA report","✓ Instant after Analyze",ACCENT),
]
for i,(bef,big,lab,aft,col) in enumerate(mets):
    x=0.9+i*3.98
    box(s, x, 2.35, 3.7, 2.0, fill=CARD, line=BORDER)
    text(s, x, 2.55, 3.7, 0.3, [[(bef, 11.5, RED, True)]], align=PP_ALIGN.CENTER)
    text(s, x, 2.85, 3.7, 0.7, [[(big, 40, col, True)]], align=PP_ALIGN.CENTER)
    text(s, x, 3.62, 3.7, 0.3, [[(lab, 12, MUTED, False)]], align=PP_ALIGN.CENTER)
    text(s, x, 3.95, 3.7, 0.3, [[(aft, 11.5, GREEN, True)]], align=PP_ALIGN.CENTER)
box(s, 0.9, 4.6, 11.5, 1.9, fill=CARD, line=BORDER)
text(s, 1.2, 4.8, 6, 0.3, [[("Manual investigation", 12.5, TEXT, False)]])
text(s, 8.5, 4.8, 3.6, 0.3, [[("1 – 3 hours", 12.5, RED, True)]], align=PP_ALIGN.RIGHT)
box(s, 1.2, 5.15, 10.9, 0.22, fill=RED, line=None, radius=0.5)
text(s, 1.2, 5.5, 6, 0.3, [[("Sentinel AI (end-to-end)", 12.5, TEXT, False)]])
text(s, 8.5, 5.5, 3.6, 0.3, [[("60 – 120 seconds", 12.5, GREEN, True)]], align=PP_ALIGN.RIGHT)
box(s, 1.2, 5.85, 0.5, 0.22, fill=GREEN, line=None, radius=0.5)
text(s, 1.2, 6.15, 11, 0.3, [[("~98% ", 15, GREEN, True), ("reduction in mean time to root cause — and the knowledge barrier is gone entirely.", 12, MUTED, False)]])
footer(s, 13)

# ═══════════════════════════════════════════════════════════════
# 14 · ROADMAP
# ═══════════════════════════════════════════════════════════════
s = slide(); kicker(s, "Future Possibilities")
title(s, ["Built today · designed to grow"])
lead(s, "The strategy/plugin architecture means each item below is an add-on, not a rewrite.", 1.75)
rm = [
    ("DONE", GREEN, "AI RCA · service health monitoring · runtime config · direct Claude · code intelligence",
     "The investigation pipeline, the proactive Glue/Lambda/DataSync health dashboard with profiles, live config, and GitHub code review are shipped and running."),
    ("NEXT", AMBER, "Auto-link RCA → PR & inline review comments",
     "Surface the pull request that fixes a failure, and post AI findings straight onto the PR at the right line."),
    ("NEXT", AMBER, "Full repository scan & failure-trend dashboard",
     "Run the review checklist across the whole repo; aggregate snapshots into trends, top errors, and MTTR."),
    ("VISION", PURPLE, "Integration hub — Jira · Slack · Email",
     "Auto-raise tickets, notify channels, and alert stakeholders when failures cross a threshold. No copy-paste."),
    ("VISION", PURPLE, "Predictive failure detection & auto-remediation",
     "Learn from history to flag components likely to fail — and one-click re-submit failed records."),
]
y=2.35
for badge,col,h,b in rm:
    box(s, 0.9, y+0.02, 1.05, 0.42, fill=None, line=col, radius=0.5)
    text(s, 0.9, y+0.09, 1.05, 0.3, [[(badge, 9.5, col, True)]], align=PP_ALIGN.CENTER)
    text(s, 2.15, y, 10.2, 0.3, [[(h, 13.5, TEXT, True)]])
    text(s, 2.15, y+0.33, 10.2, 0.4, [[(b, 11, MUTED, False)]], line_spacing=1.05)
    y += 0.92
footer(s, 14)

# ═══════════════════════════════════════════════════════════════
# 15 · CLOSE
# ═══════════════════════════════════════════════════════════════
s = slide()
text(s, 0, 1.6, 13.333, 0.8, [[("⚙", 46, ACCENT, False)]], align=PP_ALIGN.CENTER)
text(s, 0, 2.5, 13.333, 0.4, [[("ROCHE DS PLATFORM · SENTINEL AI", 13, ACCENT, True)]], align=PP_ALIGN.CENTER)
text(s, 0, 3.0, 13.333, 1.4, [[("From failure to fix", 46, TEXT, True)],
                              [("in 60 seconds.", 46, ACCENT, True)]], align=PP_ALIGN.CENTER, line_spacing=1.0)
text(s, 0, 4.9, 13.333, 0.5,
     [[("FastAPI · Athena · CloudWatch Insights · Glue/Lambda/DataSync health · Claude AI · GitHub MCP", 13, MUTED, False)]],
     align=PP_ALIGN.CENTER)
pills = ["~98% faster RCA","Proactive service health","Pluggable & future-ready","Running today"]
total_w = sum(0.3+0.115*len(p) for p in pills) + 0.2*(len(pills)-1)
x = (13.333-total_w)/2
for p in pills:
    w = 0.3+0.115*len(p)
    box(s, x, 5.6, w, 0.5, fill=CARD, line=BORDER, radius=0.5)
    text(s, x, 5.69, w, 0.35, [[(p, 11.5, TEXT, False)]], align=PP_ALIGN.CENTER)
    x += w+0.2

out = Path(r"C:\Users\sivashankar\Documents\i2i\idea\ai-rca\presentation\AI-RCA-Client-Overview.pptx")
try:
    prs.save(str(out))
    print("saved", str(out), "slides:", len(prs.slides._sldIdLst))
except PermissionError:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fallback = out.with_name(f"{out.stem}_{ts}{out.suffix}")
    prs.save(str(fallback))
    print("target file is open/locked; saved fallback", str(fallback), "slides:", len(prs.slides._sldIdLst))
