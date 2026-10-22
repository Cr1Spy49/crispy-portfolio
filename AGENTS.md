# Portfolio changes

- Preserve the dark/orange CriSpy palette, artwork, hero composition, and section order.
- The approved direction is soft street style: local Onest/Rubik fonts, compact spacing, hand-drawn background graffiti, upper-right comets, and a star behind the portrait.
- Stars use the clean hollow four-point shape ✧. Keep the portrait star high and partly behind the left edge; the header uses an outlined graffiti wordmark with a matching star.
- Keep ambient animation gentle, behind the content, noninteractive, pausable, and compatible with reduced motion. Do not move or replace existing sections.
- Make small, targeted improvements. A replacement theme or broad redesign requires an explicit request.
- Treat reference portfolios as inspiration for individual details; adapt them to the current design.
- Keep the static site simple: HTML, inline CSS/JavaScript, local assets, no mandatory build step.
- Keep original artwork intact. Generate optimized previews separately.
- Use the existing checkout; do not create a worktree unless requested.
- Preserve the CRLF line endings in `index.html`; use Git's `cr-at-eol` whitespace option when checking it.
- Browser checks: `python3 tools/smoke_test.py` (optional Playwright + Chromium development tooling).
