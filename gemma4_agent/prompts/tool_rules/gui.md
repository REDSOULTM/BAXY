GUI rule: gui(...) is the mouse/keyboard/screen synthesis layer. Actions: screenshot, click, double_click, right_click, type, keypress, hotkey, scroll, drag, wait_for, locate_text, click_text, locate_image.

PREFER uia(...) over raw gui(...) clicks whenever the target is a standard Windows app control — UI Automation returns names, control types, automation ids and bounds, which are far more stable than pixel coordinates.

locate_text / click_text use local OCR when available and return screen_x / screen_y in screen-space. Distinct from vision(...) which describes a screenshot but does not click.
