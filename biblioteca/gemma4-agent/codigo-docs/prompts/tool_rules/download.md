Download rule: download(...) fetches a URL to disk with integrity checks. Actions: fetch, hash, signature.

fetch uses Invoke-WebRequest, then verifies SHA256 and Authenticode for executables. Without an expected_hash or a valid signature it returns needs_verification — do not claim the download is safe in that state.

Distinct from filesystem(action='copy') (local-only) and from browser(action='open') (just opens a URL, no file). For routine web research, prefer web(action='research').
