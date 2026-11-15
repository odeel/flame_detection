"""Re-parse the PDFs already downloaded (from data/psi-docs/manifest.json) into passages; no network needed."""
import json

from _common import run, services


async def main():
    s = await services()
    try:
        out = await s.run_job("documents", lambda: s.index_local_documents(log_fn=print))
        print(json.dumps(out, indent=1, default=str))
        await s.ensure_derived(force=True)
    finally:
        await s.close()


run(main)
