"""
NASA Physical Sciences Informatics (PSI) client.

  * Metadata:  https://psi.nasa.gov/geode-py/ws/repo/search and /repo/investigations/{accession}
  * Files:     PSI stores data in its AWS S3 bucket (psi-repo-prod). /studies/{acc}/download returns a
               presigned S3 URL for one file, which is then streamed to disk. This is the same object the
               guide's boto3 step reads, without needing AWS credentials.

Downloads are resumable (skipped when the file on disk has the expected size), verified with SHA-256,
and recorded in a manifest. Requests retry with exponential backoff and honour HTTPS_PROXY / SSL_CERT_FILE.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

import httpx


BASE = "https://psi.nasa.gov/geode-py/ws"
S3_URL = re.compile(r"^https://[a-z0-9.-]+\.amazonaws\.com/")
DOC_CATEGORIES = ["Reports", "Science Documents", "Engineering Documents", "Presentations", "Reference Data", "Analyzed Data"]
log = logging.getLogger("fif.psi")
# Presigned S3 URLs carry temporary credentials: never log request URLs.
logging.getLogger("httpx").setLevel(logging.WARNING)


def _redact(msg: str) -> str:
    return re.sub(r"\?[^\s'\"]*", "?<redacted>", str(msg))


class PsiClient:
    def __init__(self, timeout: float = 60.0):
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15.0), follow_redirects=True,
                                      headers={"User-Agent": "flame-in-freefall/2.0 (NASA Space Apps)"})

    async def close(self):
        await self.http.aclose()

    async def _get(self, url: str, *, json_body: bool = True):
        last = None
        for attempt in range(4):
            try:
                r = await self.http.get(url, headers={"Accept": "application/json"} if json_body else None)
                r.raise_for_status()
                return r.json() if json_body else r.text
            except (httpx.HTTPError, ValueError) as e:
                last = e
                await asyncio.sleep(0.8 * 2 ** attempt)
        raise RuntimeError(f"{url.split('?')[0]}: {_redact(last)}")

    async def search(self, research_area: str = "combustion science") -> list[dict]:
        q = httpx.QueryParams({"ffield": "Research Area", "fvalue": research_area, "size": "500", "type": "investigation"})
        data = await self._get(f"{BASE}/repo/search?{q}")
        return [h["_source"] for h in data["hits"]["hits"]]

    async def investigation(self, accession: str) -> dict:
        return await self._get(f"{BASE}/repo/investigations/{quote(accession)}")

    async def signed_url(self, accession: str, file_name: str, version) -> str:
        q = httpx.QueryParams({"file": file_name, "version": str(version or 1), "redirect": "false"})
        url = (await self._get(f"{BASE}/studies/{quote(accession)}/download?{q}", json_body=False)).strip().strip('"')
        if not S3_URL.match(url):
            raise RuntimeError(f"unexpected download URL for {file_name}")
        return url

    @staticmethod
    def document_files(detail: dict, categories=None, max_bytes: int = 40 * 1024 * 1024, extensions=(".pdf",)) -> list[dict]:
        cats = set(categories or DOC_CATEGORIES)
        out = []
        for f in detail.get("added") or []:
            name = f.get("file_name") or ""
            parts = str(f.get("remote_path") or "").split("/")
            cat = parts[4] if len(parts) > 5 else ""
            if cat in cats and name.lower().endswith(extensions) and 0 < (f.get("file_size") or 0) <= max_bytes and not f.get("restricted"):
                out.append({"file_name": name, "category": cat, "bytes": f["file_size"], "version": f.get("version") or 1,
                            "s3_version_id": f.get("s3_version_id") or "", "s3_path": f.get("s3_path") or ""})
        return out

    async def download(self, accession: str, f: dict, dest_dir: Path) -> dict:
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w .()-]+", "_", f["file_name"]).strip()
        path = dest_dir / safe
        if path.exists() and path.stat().st_size == f["bytes"]:
            return {**f, "path": str(path), "sha256": sha256_file(path), "downloaded": False}
        url = await self.signed_url(accession, f["file_name"], f["version"])
        tmp = path.with_suffix(path.suffix + ".part")
        h = hashlib.sha256()
        for attempt in range(4):
            try:
                h = hashlib.sha256()
                async with self.http.stream("GET", url) as r:
                    r.raise_for_status()
                    with tmp.open("wb") as out:
                        async for chunk in r.aiter_bytes(1 << 16):
                            out.write(chunk)
                            h.update(chunk)
                break
            except httpx.HTTPError as e:
                if attempt == 3:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(f"download failed for {f['file_name']}: {_redact(e)}") from None
                await asyncio.sleep(1.5 * 2 ** attempt)
        tmp.replace(path)
        return {**f, "path": str(path), "sha256": h.hexdigest(), "downloaded": True}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(root: Path) -> dict:
    p = root / "manifest.json"
    return json.loads(p.read_text()) if p.exists() else {"files": {}}


def write_manifest(root: Path, manifest: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / "manifest.json.part"
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    tmp.replace(root / "manifest.json")
