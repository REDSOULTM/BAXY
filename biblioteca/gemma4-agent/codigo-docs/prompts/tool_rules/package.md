Package rule: package(...) installs/uninstalls/updates desktop applications via winget. Actions: list, search, install, uninstall. Distinct from dependency(...) (Python modules / system binaries needed by the agent itself).

CONFIRM BEFORE INSTALL: if the user requests an install of a tool that has a paid edition (e.g. PyCharm Professional vs Community), confirm which edition. If the tool is paid only, surface the purchase-guard before proceeding.
