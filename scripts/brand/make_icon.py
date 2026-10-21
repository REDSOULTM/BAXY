"""BAXY's Windows icon (design v5): the Higgsfield app icon of the handoff (baxy-icon-256.png, beside this script),
exported to the sizes Windows asks for — 16, 24, 32 and 48 px for lists, the taskbar and the notification area (20 and
40 px too, the tray's small icon at 125 % and 250 %) and 256 px for large views. The window, the tray and the Windows
notifications all use it (Baxy.App/Assets/baxy.ico). make_icon.py <out.ico>"""
import sys
from pathlib import Path

from PIL import Image

SIZES = [16, 20, 24, 32, 40, 48, 256]
source = Image.open(Path(__file__).with_name("baxy-icon-256.png")).convert("RGBA")
source.save(sys.argv[1], format="ICO", sizes=[(s, s) for s in SIZES])
print(sys.argv[1], SIZES)
