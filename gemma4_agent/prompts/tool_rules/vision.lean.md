vision(...) = Gemma-4-vision / OCR bridge. Actions: describe_screen, find_element, ocr, compare_before_after.

OCR uses local Tesseract when available. Screenshots are re-injected for native Gemma 4 visual reasoning -> you can SEE what the user sees on screen.

Distinct from: gui(action='screenshot') (raw bitmap, no description); uia(...) (structured control tree, not visual). Use vision for "what's on screen?" or to compare a before/after image.
