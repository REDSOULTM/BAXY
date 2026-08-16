Local-search rule: local_search(...) finds files by name (and optionally small file contents) under a local root, no cloud involved. Actions: status, search, recent.

Distinct from filesystem(action='search') (single-directory glob, no cross-tree index) and from web(...) / browser(...) (internet). When the user wants to locate a file they remember writing earlier, prefer local_search.
