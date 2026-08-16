Vision rule: vision(...) is the Gemma-4-vision / OCR bridge. Actions: describe_screen, find_element, ocr, compare_before_after.

OCR uses local Tesseract when available. Screenshots are also re-injected for native Gemma 4 visual reasoning — so you can SEE what the user sees on screen.

Distinct from gui(action='screenshot') (raw bitmap, no description) and from uia(...) (structured control tree, not visual). Use vision when the user asks "what's on screen?" or wants you to compare a before / after image.
