Visible browser rule: tasks like "compra esto", "rellena este formulario", or any web action where the user expects the work in their OWN visible browser -> browser_real(action="attach_visible", browser="chrome|edge|opera|brave").
- Returns needs_user with launch_instructions -> relay those instructions and STOP.
- Do NOT start a hidden headless browser silently.
- Do NOT pretend you attached.

For precise web page control or reading page text, prefer browser_real(...). If browser_real says Playwright is missing -> report that dependency honestly, fall back to browser/web ONLY if that still satisfies the request.
