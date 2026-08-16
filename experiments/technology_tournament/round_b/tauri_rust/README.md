# Tauri + Rust integrated finalist

This Tauri 2 shell hosts the same offline HTML/CSS/JavaScript as the .NET
finalist and owns the packaged Rust core over a private UTF-8 stdin/stdout
channel. The frontend can send only invocation ID and text; the trusted Rust
shell injects the fixed LocalAppData workspace.

The project pins Tauri crate 2.11.5, Tauri CLI 2.11.4 and tauri-build 2.6.3.
Set `BAXY_ROUND_B_CORE` to the packaged Rust core and run:

```powershell
npm install
npm run tauri dev
```

No shell, filesystem, HTTP, dialog, opener or updater plugin is enabled in the
slice. The CSP permits only packaged assets and Tauri's private IPC transport.
