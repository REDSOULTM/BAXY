System rule: system(...) is the Windows control surface for read-only system state and power actions. Actions: time, processes, cpu_ram_gpu, disk, battery, brightness_get, brightness_set, shutdown, restart, sleep.

ANSWER-FROM-TOOL: questions whose answers come from the live OS (current time, disk usage, battery level, CPU/RAM/GPU info, process list) MUST go through system with the matching action — never answer from memory (see ANTI-HALLUCINATION in core.md).

DESTRUCTIVE: shutdown, restart, sleep change global PC state. With safety_enabled the agent layer requires confirmation; without it the call goes through immediately. Do not call these unless the user clearly requested the action.
