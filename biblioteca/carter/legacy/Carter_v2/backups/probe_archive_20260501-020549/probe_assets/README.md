# Carter probe assets

This directory is reserved for small, reproducible probe fixtures.

`probe_all_tools.py` creates binary/runtime fixtures under `../probe_assets_runtime/`
at execution time so generated PDFs, media files, git sandboxes, and outputs do not
depend on user documents or desktop files.

Use `scripts/setup_optional_probe_env.py` to inspect optional dependencies needed for
extended probe coverage.
