# StreamWright Hub

The connector registry for [StreamWright](https://github.com/karthick-jaganathan/streamwright).
It's a **static index** — one YAML file per connector, compiled into `index.json`
and served over HTTPS. The `streamwright` CLI reads it to discover and install connectors.

The hub holds **metadata only** (where to install a connector from). Connector
**code** lives in its own repo (or the StreamWright monorepo) — the hub just points to it.

## Layout

```
connectors/<key>.yaml      one entry per connector (key = provider/sdk name)
schema/connector.schema.json
denylist.yaml              revoke a compromised/malicious connector instantly
scripts/validate.py        schema + source allowlist + pinning + typosquat + denylist
scripts/build_index.py     connectors/*.yaml -> index.json
```

## A connector entry

```yaml
key: postgres                 # the provider/sdk name used in source YAML
title: PostgreSQL
family: readers               # readers | ads | crm | analytics | warehouse | other
summary: Read-only SELECT queries on PostgreSQL
trust: official               # official | verified | community
homepage: https://github.com/karthick-jaganathan/streamwright
maintainer: karthick-jaganathan
install:                      # exactly one of pip | git | image
  git: "git+https://github.com/karthick-jaganathan/streamwright.git@<commit-sha>#subdirectory=connectors/readers/postgres"
  # pip:   "streamwright-postgres>=0.1,<0.2"
  # image: "ghcr.io/org/streamwright-postgres@sha256:<digest>"
```

## Contributing a connector

1. Open a PR adding `connectors/<key>.yaml`.
2. CI validates it (schema, allowed source, **pinned** ref/digest, no typosquat, not denied).
3. A maintainer (`CODEOWNERS`) reviews and merges.
4. The index republishes automatically.

## Security guardrails

- **Review-gated**: every entry needs maintainer approval; nothing auto-merges.
- **Source allowlist**: only `pip` (PyPI), `git` (https GitHub/GitLab), or `image`
  (allowed registries) — no arbitrary hosts.
- **Mandatory pinning**: git refs must be a **commit SHA or tag** (no `main`/`master`);
  images must be pinned by **`@sha256:` digest**. What's reviewed = what installs.
- **Typosquat detection**: keys confusingly close to an existing one are rejected.
- **Trust tiers**: `official` / `verified` / `community`; the CLI warns and asks for
  confirmation before installing anything not `official`.
- **Instant revocation**: add to `denylist.yaml` to block a connector immediately.

> A connector runs code on install/use. Prefer running untrusted (`community`)
> connectors in a container/K8s sandbox with least-privilege, scoped secrets.
