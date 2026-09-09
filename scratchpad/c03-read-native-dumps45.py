"""Summarize local WER dumps without copying process memory into the repo."""
from pathlib import Path
import hashlib
import json
import os
import struct
import sys

sys.path.insert(0, str(Path(os.environ['TEMP']) / 'c03-minidump-tools'))
from minidump.minidumpfile import CONTEXT, MinidumpFile

rows = []
for pid in (23360, 2740):
    path = Path(os.environ['LOCALAPPDATA']) / 'CrashDumps' / f'python.exe.{pid}.dmp'
    dump = MinidumpFile.parse(str(path))
    exception = dump.exception.exception_records[0]
    dump.file_handle.seek(exception.ThreadContext.Rva)
    context = CONTEXT.parse(dump.file_handle)
    reader = dump.get_reader().get_buffered_reader()
    reader.move(context.Rsp)
    stack = reader.read(640)
    matches = []
    for index, (pointer,) in enumerate(struct.iter_unpack('<Q', stack)):
        for module in dump.modules.modules:
            if module.baseaddress <= pointer < module.endaddress:
                matches.append({'stackOffset': hex(index * 8), 'module': Path(module.name).name, 'moduleOffset': hex(pointer - module.baseaddress)})
    rows.append({'pid': pid, 'dumpPath': str(path), 'dumpSha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'threadId': exception.ThreadId,
                 'exceptionCode': str(exception.ExceptionRecord.ExceptionCode), 'exceptionAddress': hex(context.Rip),
                 'exceptionInformation': exception.ExceptionRecord.ExceptionInformation, 'stackModulePointers': matches,
                 'interpretationLimit': 'Pointers in captured exception stack, not a symbolic unwinding. Initial PID23360 returns to libportaudio64bit.dll+0xd492 from execution of unmapped callback address. PID2740 fault occurs while faulthandler is already reporting access violation.'})
out = Path(__file__).resolve().parents[1] / 'artifacts/comprobaciones/C03/NATIVE_DUMP45.json'
out.write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps([{'pid': r['pid'], 'firstStackPointer': r['stackModulePointers'][0]} for r in rows]))
