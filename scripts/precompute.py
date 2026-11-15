"""
Pre-compute everything the offline demo needs and store it in PostgreSQL:
normalized test rows, PSI metadata passages, investigation summaries and the six habitat briefs.

    python scripts/precompute.py            # extractive summaries (no API key needed)
    python scripts/precompute.py --claude   # also grounded Claude summaries (needs ANTHROPIC_API_KEY)
"""
import argparse
import json

from _common import run, services


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude", action="store_true")
    ap.add_argument("--accessions", nargs="*")
    a = ap.parse_args()
    s = await services()
    try:
        print(json.dumps(await s.ensure_derived(force=True), indent=1))
        if a.claude:
            print(json.dumps(await s.run_job("summaries", lambda: s.claude_summaries(a.accessions)), indent=1, default=str))
    finally:
        await s.close()


run(main)
