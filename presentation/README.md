# Sentinel AI — Client Presentation

Client-facing overview of **Sentinel AI** (Roche DS Platform) — proactive service
health monitoring plus AI root-cause analysis.
Three formats, same 15-slide story — pick whichever fits the room.

| File | Format | Use it when… |
|------|--------|--------------|
| `ai-rca-client-deck.html` | Interactive slide deck | **Presenting live.** Open in any browser, press **F** for fullscreen. |
| `AI-RCA-Client-Overview.pdf` | PDF (13 landscape pages) | Emailing ahead, printing, or read-only sharing. Pixel-identical to the HTML. |
| `AI-RCA-Client-Overview.pptx` | PowerPoint (16:9, editable) | You need to tweak wording/branding, or the client expects a PPT. |

## Presenting the HTML deck

- **→ / Space / Page-Down** — next slide
- **← / Page-Up** — previous slide
- **F** — toggle fullscreen
- **Home / End** — jump to first / last slide
- Click the left/right edge of the screen to move between slides
- Deep-link a slide with a hash, e.g. `…ai-rca-client-deck.html#7`

## Slide flow (15)

1. Cover
2. The Problem — why manual RCA hurts
3. Who it's for & use cases — 3 personas, zero prerequisite knowledge
4. The Solution — features you get today + how to use it (4 clicks)
5. How it works — the RCA workflow
6. Architecture — clean three-layer design
7. Design patterns — Strategy + Plugin Registry (extensibility)
8. Inside the AI — the 5-step pipeline
9. Source Code Intelligence — GitHub MCP + AI code review
10. Proactive Service Health — Glue/Lambda/DataSync dashboard, profiles, drill-down + failure reasons
11. End-to-end workflow diagram — how Health, RCA & Code Intelligence flow together
12. Advantages — the wins that matter
13. Impact — time saved (~98% MTRC reduction)
14. Future possibilities — roadmap & extensibility
15. Close

## Regenerating the PDF / PPTX

The HTML is the source of truth. If you edit it, regenerate the others:

```bash
# PDF — headless Chrome print (exact visual match)
"C:/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --no-pdf-header-footer --no-margins \
  --print-to-pdf="AI-RCA-Client-Overview.pdf" \
  "file:///.../presentation/ai-rca-client-deck.html"
```

The PPTX is built by `build_pptx.py` in this folder (needs `python-pptx`):

```bash
pip install python-pptx
python presentation/build_pptx.py   # rewrites AI-RCA-Client-Overview.pptx
```

> Deeper technical deck: see the original `../presentation.html` (hackathon build log).
