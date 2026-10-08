#!/usr/bin/env python3
"""Validate every connector entry in the StreamWright hub.

Enforces supply-chain guardrails:
  * schema conformance (schema/connector.schema.json)
  * source allowlist + mandatory pinning (git ref / image digest)
  * unique, non-typosquatting keys
  * nothing listed in denylist.yaml

Exit code is non-zero if any entry fails. Run in CI on every PR.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
CONNECTORS = ROOT / "connectors"
SCHEMA = ROOT / "schema" / "connector.schema.json"
DENYLIST = ROOT / "denylist.yaml"

# Only these sources are allowed. git must be https GitHub/GitLab; images from these registries.
GIT_HOST = re.compile(r"^git\+https://(github\.com|gitlab\.com)/")
GIT_REF = re.compile(r"@([0-9a-f]{7,40}|v?\d+\.\d+\.\d+[\w.\-]*|[\w\-]+-v?\d+\.\d+\.\d+[\w.\-]*)(#|$)")
MUTABLE_REF = re.compile(r"@(main|master|HEAD|latest|develop)(#|$)")
IMAGE_OK = re.compile(r"^(ghcr\.io|docker\.io|registry\.gitlab\.com|public\.ecr\.aws)/\S+@sha256:[0-9a-f]{64}$")
PIP_URLISH = re.compile(r"(https?://|git\+|@\s*http|file:)")


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def load_denylist() -> list[dict]:
    if not DENYLIST.exists():
        return []
    data = yaml.safe_load(DENYLIST.read_text()) or {}
    denied = data.get("denied") or []
    return [d for d in denied if isinstance(d, dict)]


def check_install(install: dict, errors: list[str], where: str) -> None:
    if "git" in install:
        url = install["git"]
        if not GIT_HOST.match(url):
            errors.append(f"{where}: git source must be git+https://github.com/… or gitlab.com/…")
        if MUTABLE_REF.search(url):
            errors.append(f"{where}: git ref is a mutable branch (main/master/HEAD) — pin a tag or commit SHA")
        elif not GIT_REF.search(url):
            errors.append(f"{where}: git source must be pinned to a commit SHA or version tag (…@<ref>#subdirectory=…)")
    elif "image" in install:
        if not IMAGE_OK.match(install["image"]):
            errors.append(f"{where}: image must be from an allowed registry and pinned by digest (…@sha256:<64 hex>)")
    elif "pip" in install:
        if PIP_URLISH.search(install["pip"]):
            errors.append(f"{where}: pip source must be a plain PyPI requirement (no URLs / direct refs)")


def check_denied(entry: dict, denied: list[dict], errors: list[str], where: str) -> None:
    install = entry.get("install", {})
    for d in denied:
        if d.get("key") and d["key"] == entry.get("key"):
            errors.append(f"{where}: key is on the denylist ({d.get('reason','')})")
        if d.get("pip") and install.get("pip", "").startswith(d["pip"]):
            errors.append(f"{where}: pip source is on the denylist ({d.get('reason','')})")
        if d.get("git") and install.get("git", "").startswith(d["git"]):
            errors.append(f"{where}: git source is on the denylist ({d.get('reason','')})")
        if d.get("image") and install.get("image", "").startswith(d["image"]):
            errors.append(f"{where}: image is on the denylist ({d.get('reason','')})")


def main() -> int:
    validator = Draft7Validator(json.loads(SCHEMA.read_text()))
    denied = load_denylist()
    errors: list[str] = []
    entries: dict[str, dict] = {}

    for path in sorted(CONNECTORS.glob("*.yaml")):
        where = f"connectors/{path.name}"
        try:
            entry = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            errors.append(f"{where}: invalid YAML: {exc}")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{where}: must be a mapping")
            continue

        for err in sorted(validator.iter_errors(entry), key=lambda e: e.path):
            errors.append(f"{where}: {err.message}")

        key = entry.get("key")
        if key:
            if key in entries:
                errors.append(f"{where}: duplicate key '{key}' (also in {entries[key]['_file']})")
            if path.stem != key:
                errors.append(f"{where}: filename must match key '{key}.yaml'")
            entry["_file"] = where
            entries.setdefault(key, entry)

        if isinstance(entry.get("install"), dict):
            check_install(entry["install"], errors, where)
        check_denied(entry, denied, errors, where)

    # Typosquat / confusable keys (edit distance 1 between different keys).
    keys = list(entries)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if levenshtein(a, b) == 1:
                errors.append(f"confusable keys '{a}' and '{b}' (edit distance 1) — pick a clearly distinct name")

    if errors:
        print(f"✗ {len(errors)} problem(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✓ {len(entries)} connector(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
