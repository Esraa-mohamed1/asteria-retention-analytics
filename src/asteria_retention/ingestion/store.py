"""Raw payload store.

Every payload is kept exactly as received (`<stamp>.json`) beside a metadata
file (`<stamp>.meta.json`: url, params, retrieved_at, sha256, origin). Snapshots
are append-only, so a rerun never destroys earlier evidence. Reads re-hash the
body and refuse a file whose content no longer matches its recorded checksum.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asteria_retention.errors import ContractViolation
from asteria_retention.ingestion.base import RawPayload, canonical_json, sha256_of


def _stamp(retrieved_at: str) -> str:
    return retrieved_at.replace(":", "").replace("-", "")


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _dir(self, provider: str, indicator_id: str) -> Path:
        return self.root / provider / indicator_id

    def save(self, payload: RawPayload) -> Path:
        directory = self._dir(payload.provider, payload.indicator_id)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = _stamp(payload.retrieved_at)
        body_path = directory / f"{stamp}.json"
        body_path.write_text(canonical_json(payload.body), encoding="utf-8")
        meta: dict[str, Any] = {
            "provider": payload.provider,
            "indicator_id": payload.indicator_id,
            "url": payload.url,
            "params": payload.params,
            "retrieved_at": payload.retrieved_at,
            "sha256": payload.sha256,
            "origin": payload.origin,
        }
        (directory / f"{stamp}.meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )
        return body_path

    def latest(
        self, provider: str, indicator_id: str, origin_override: str | None = None
    ) -> RawPayload | None:
        directory = self._dir(provider, indicator_id)
        if not directory.exists():
            return None
        metas = sorted(directory.glob("*.meta.json"))
        if not metas:
            return None
        meta_path = max(metas, key=lambda p: json.loads(p.read_text(encoding="utf-8"))["retrieved_at"])
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".json"))
        try:
            body = json.loads(body_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ContractViolation(f"Cannot read stored payload {body_path}: {exc}") from exc
        if sha256_of(body) != meta["sha256"]:
            raise ContractViolation(
                f"Stored payload {body_path} does not match its recorded checksum; refusing to use it."
            )
        return RawPayload(
            provider=meta["provider"],
            indicator_id=meta["indicator_id"],
            url=meta["url"],
            params=meta["params"],
            retrieved_at=meta["retrieved_at"],
            body=body,
            origin=origin_override or meta["origin"],
            sha256=meta["sha256"],
        )
