Desktop-layout rule: desktop_layout(...) snapshots and restores top-level window positions. Actions: status, windows, list_windows, displays, snapshot, restore.

snapshot captures rect/pid/process for visible windows via Win32 EnumWindows; restore replays positions via MoveWindow. Pass snapshot_id or an explicit windows list to restore.

Distinct from window(...) (single-window operations) and from desktop_layout's snapshot vs gui(action='screenshot') (image bitmap, not positions).
