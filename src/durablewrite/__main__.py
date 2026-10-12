"""Allow ``python -m durablewrite``."""

from __future__ import annotations

import sys

from ._cli import main

sys.exit(main())
