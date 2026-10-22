# Portfolio changes

- Preserve the existing dark/orange CriSpy design, typography, hero, and section order.
- Make small, targeted improvements. A replacement theme or broad redesign requires an explicit request.
- Treat reference portfolios as inspiration for individual details; adapt them to the current design.
- Keep the static site simple: HTML, inline CSS/JavaScript, local assets, no mandatory build step.
- Keep original artwork intact. Generate optimized previews separately.
- Use the existing checkout; do not create a worktree unless requested.
- Preserve the CRLF line endings in `index.html`; use Git's `cr-at-eol` whitespace option when checking it.
- Browser checks: `python3 tools/smoke_test.py` (optional Playwright + Chromium development tooling).
