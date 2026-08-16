# Vision Setup

## Current routing order

Carter probes vision backends once at startup and uses this order:

1. `LLM_VISION`
2. `OMNIPARSER`
3. `PYTESSERACT`
4. `NONE`

Startup prints a line like:

```text
[vision] llm_vision=disabled omniparser=missing pytesseract=missing -> vision tier: NONE
```

## Option 1: Enable LLM vision

Set these environment variables or add them to `Carter_v2/.env`:

```env
CARTER_USE_LLM_VISION=true
CARTER_LLM_BASE_URL=http://localhost:1234/v1
CARTER_LLM_MODEL=<vision-capable-model>
```

If your endpoint requires authentication, also set:

```env
CARTER_LLM_API_KEY=<token>
```

Notes:

- The endpoint must implement an OpenAI-compatible `chat/completions` API.
- The selected model must accept image input.
- `CARTER_USE_LLM_VISION=false` disables this tier even if the endpoint exists.

## Option 2: Install Tesseract OCR

Windows:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Common default install path:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

Carter auto-detects the common Windows install locations. No extra config is required when Tesseract is installed there.

## Option 3: Enable OmniParser

If you already have OmniParser locally:

- Install the Python package so Carter can import it directly, or
- Run the HTTP server and point Carter at it with `OMNIPARSER_URL`

Example:

```env
OMNIPARSER_URL=http://localhost:7861
```

## Failure behavior

When no tier is available:

- `vision_read_text_visual` returns `ok=False`
- GUI visual fallback returns `ok=False`
- Carter does not fake OCR output
- The reply includes a next-step hint telling you to install Tesseract or configure a vision-capable LLM endpoint
