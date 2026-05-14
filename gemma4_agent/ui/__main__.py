"""Module runner: `python -m gemma4_agent.ui`."""
from __future__ import annotations

import sys

from .app import main


if __name__ == "__main__":
    sys.exit(main())
