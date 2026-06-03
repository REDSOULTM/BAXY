peripheral(...) inspects/toggles USB/HID devices via Get-PnpDevice. Actions: status, usb_list, hid_list, controller_status, device_manager_problems, device_disable, device_enable.

controller_status matches Xbox / PlayStation / Joy-Con / etc. keywords against connected devices.

Vendor RGB SDKs (Logitech, Razer, Corsair) intentionally deferred -> do NOT promise per-key lighting control.

Distinct from: device_settings(...) (WiFi/Bluetooth/displays/power); audio(action='devices') (audio output endpoints only).
