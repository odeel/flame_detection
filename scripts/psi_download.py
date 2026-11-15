"""
Download NASA PSI documents (PDF reports, science and engineering documents...) and index them.

    python scripts/psi_download.py                                   # Reports + Science Documents, all investigations
    python scripts/psi_download.py --categories Reports "Engineering Documents" --max-mb 25
    python scripts/psi_download.py --accessions PSI-69 PSI-159 --limit 10
    python scripts/psi_download.py --no-index                         # download only

Files go to backend-fastapi/data/psi-docs/<accession>/ (FIF_DOCUMENTS_DIR) with a manifest.json
(SHA-256, size, S3 version). Re-running skips files already downloaded and documents already indexed.
"""
import argparse
import json

from _common import run, services

CATS = ["Reports", "Science Documents", "Engineering Documents", "Presentations", "Reference Data", "Analyzed Data"]


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--accessions", nargs="*")
    ap.add_argument("--categories", nargs="*", choices=CATS, default=["Reports", "Science Documents"])
    ap.add_argument("--max-mb", type=float, default=40)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-index", action="store_true", help="download only (index later with index_documents.py)")
    a = ap.parse_args()
    s = await services()
    try:
        if a.no_index:
            from app.psi_client import PsiClient, read_manifest, write_manifest
            from app import store
            root, manifest, client = s.settings.documents_dir, None, PsiClient()
            manifest = read_manifest(root)
            try:
                for inv in await store.investigations(s.pool):
                    if a.accessions and inv["accession"] not in a.accessions:
                        continue
                    for f in PsiClient.document_files(await client.investigation(inv["accession"]), a.categories, int(a.max_mb * 1048576)):
                        got = await client.download(inv["accession"], f, root / inv["accession"])
                        manifest["files"][f"{inv['accession']}/{f['file_name']}"] = {k: got[k] for k in ("category", "bytes", "version", "s3_version_id", "s3_path", "sha256")} | {"path": f"{inv['accession']}/{got['path'].split('/')[-1]}"}
                        print(("downloaded " if got["downloaded"] else "present    ") + got["path"])
                write_manifest(root, manifest)
            finally:
                await client.close()
        else:
            out = await s.run_job("documents", lambda: s.ingest_documents(accessions=a.accessions, categories=a.categories, max_mb=a.max_mb, limit=a.limit, log_fn=print))
            print(json.dumps(out, indent=1, default=str))
            await s.ensure_derived(force=True)
    finally:
        await s.close()


run(main)
