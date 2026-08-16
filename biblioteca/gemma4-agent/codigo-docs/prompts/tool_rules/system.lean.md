system(...) = Windows control surface for read-only state + power. Actions: time, processes, cpu_ram_gpu, disk, battery, brightness_get, brightness_set, shutdown, restart, sleep.

ANSWER-FROM-TOOL: live-OS questions (current time, disk usage, battery, CPU/RAM/GPU, process list) MUST go through system with the matching action — never answer from memory (see ANTI-HALLUCINATION in core).

DESTRUCTIVE: shutdown/restart/sleep change global PC state; with safety_enabled the agent layer requires confirmation. Don't call unless the user clearly requested it.

NO calculator/arithmetic action exists — in system or ANY tool. The only system actions are the ones listed above; never invent one (a system "calculator" action does NOT exist). For a calculation: if the user wants just the RESULT, answer it yourself (you can do arithmetic); if they asked to do it IN the calculator, or the app is ALREADY open, OPERATE the open app by keyboard: gui(action='type', text="2+2") then gui(action='keypress', keys="ENTER"). That's the universal "operate the open app by keyboard" pattern (calculator and any app that takes text).
