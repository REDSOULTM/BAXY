desktop_layout(...): snapshot/restore posiciones de ventanas top-level. Actions: status, windows, list_windows, displays, snapshot, restore.
snapshot: captura rect/pid/process de ventanas visibles vía Win32 EnumWindows. restore: replica posiciones vía MoveWindow; pasá snapshot_id o lista windows explícita.
!= window (ops de una sola ventana); snapshot (de desktop_layout) != gui screenshot (bitmap de imagen, NO posiciones).
