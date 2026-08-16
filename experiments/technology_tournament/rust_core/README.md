# Rust core contender

Build and run with the MSVC toolchain:

```powershell
cargo build --release --locked
target\release\baxy-rust-slice.exe --server
```

`serde_json` is the only direct dependency and is fixed by `Cargo.lock`. The
release profile enables thin LTO, one codegen unit, abort-on-panic and symbol
stripping; the exact binary hash is recorded by the harness.

The checked-in Cargo target configuration links the MSVC C runtime statically,
so the packaged slice does not depend on a separately installed VC++
Redistributable.
