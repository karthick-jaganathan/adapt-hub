#!/usr/bin/env python3
"""Compile connectors/*.yaml into a single index.json served by the hub.

Runs validate.py first; refuses to build if anything is invalid.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONNECTORS = ROOT / "connectors"
OUT = ROOT / "index.json"


def main() -> int:
    # Guardrails first — never publish an invalid/denied index.
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py")])
    if result.returncode != 0:
        print("build aborted: validation failed")
        return result.returncode

    connectors = []
    for path in sorted(CONNECTORS.glob("*.yaml")):
        entry = yaml.safe_load(path.read_text())
        entry.pop("_file", None)
        connectors.append(entry)

    index = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(connectors),
        "connectors": {c["key"]: c for c in connectors},
    }
    OUT.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(f"✓ wrote {OUT.relative_to(ROOT)} with {len(connectors)} connector(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
