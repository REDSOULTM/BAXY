input(...) manages Windows keyboard layouts and input languages. Actions: language_list, keyboard_layouts, current_keyboard, set_language_list, switch_keyboard.

Layout/language changes register rollback checkpoints -> state(action='rollback') can revert them.

Distinct from: gui(action='type'|'keypress') (synthesize keypresses); accessibility(...) (Ease of Access); device_settings(...) (WiFi/Bluetooth/displays).
