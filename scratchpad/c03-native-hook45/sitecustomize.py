"""Opt-in local native traces for the C03 development reproduction only."""
import faulthandler
import os
from pathlib import Path

if trace_dir := os.environ.get('C03_NATIVE_TRACE_DIR'):
    _c03_fault_file = (Path(trace_dir) / f'native-fault-{os.getpid()}.log').open('a', encoding='utf-8')
    faulthandler.enable(_c03_fault_file, all_threads=True)
    _c03_fault_file.write(f'enabled pid={os.getpid()}\n')
    _c03_fault_file.flush()
