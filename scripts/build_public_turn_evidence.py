"""Build the reviewed public assistant-evidence corpus for BAXY.

Compatibility entry point. The implementation remains in
``build_presto_turn_evidence.py`` because it was introduced with the first
source; that implementation now also promotes MASSIVE under the same gates.
"""

from build_presto_turn_evidence import main


if __name__ == "__main__":
    raise SystemExit(main())
