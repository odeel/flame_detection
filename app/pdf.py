"""
HTML -> PDF with the Chromium browser already on the machine (Microsoft Edge or Google Chrome, headless).

Used for the downloadable materials risk report: the browser prints FlameAtlas's own HTML report, so the PDF looks
exactly like the page (charts, colours, tables). Safety while rendering:
  * <script> blocks are removed and a Content-Security-Policy meta tag (default-src 'none') is added first in <head>,
    so the page cannot run code or load anything from the network (only inline styles and data: images)
  * a fresh, throw-away browser profile in a temporary folder, deleted afterwards
  * at most two conversions at a time, each stopped after PDF_TIMEOUT seconds
Set FIF_PDF_BROWSER to the browser's path if it is not in a standard location.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

PDF_TIMEOUT = 60
_sem = asyncio.Semaphore(2)
_cache: OrderedDict[str, bytes] = OrderedDict()

_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
_NAMES = ["msedge", "microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]

LOCKDOWN = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; '
            'img-src data:; font-src data:">')
PRINT_CSS = ("<style>@page{size:A4;margin:12mm 10mm}"
             "html,body{background:#fff!important;color:#1d1d1f!important}body{max-width:none!important;padding:0!important}"
             ".scroll{overflow:visible!important}tr,.card,.figs img{break-inside:avoid}h1,h2{break-after:avoid}"
             "*{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style>")


class PdfUnavailable(Exception):
    pass


def find_browser() -> str | None:
    env = os.environ.get("FIF_PDF_BROWSER", "").strip()
    if env:
        return env if Path(env).is_file() else None
    for p in _CANDIDATES:
        if Path(p).is_file():
            return p
    for n in _NAMES:
        if (p := shutil.which(n)):
            return p
    return None


def prepare(html: str) -> str:
    """Adds the lockdown policy as the first thing in <head> and the print styles; removes any <script> blocks."""
    html = re.sub(r"(?is)<script\b.*?</script\s*>", "", html)
    m = re.search(r"(?i)<head[^>]*>", html)
    if m:
        return html[:m.end()] + LOCKDOWN + html[m.end():].replace("</head>", PRINT_CSS + "</head>", 1)
    return "<!doctype html><html><head><meta charset=utf-8>" + LOCKDOWN + PRINT_CSS + "</head><body>" + html + "</body></html>"


def _render(browser: str, html: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="fif-pdf-") as tmp:
        src, out = Path(tmp) / "report.html", Path(tmp) / "report.pdf"
        src.write_text(prepare(html), encoding="utf-8")
        args = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking", "--disable-sync",
                "--no-pdf-header-footer",
                f"--user-data-dir={Path(tmp) / 'profile'}", f"--print-to-pdf={out}", src.as_uri()]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")                 # Chromium refuses to run as root in containers otherwise
        try:
            subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=PDF_TIMEOUT, check=False)
        except subprocess.TimeoutExpired as e:
            raise PdfUnavailable("The PDF took too long to create. Try again.") from e
        data = out.read_bytes() if out.is_file() else b""
        if not data.startswith(b"%PDF"):
            raise PdfUnavailable("The browser could not create the PDF.")
        return data


def is_cached(key: str) -> bool:
    return key in _cache


async def html_to_pdf(html: str, key: str | None = None) -> bytes:
    if key and key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    browser = find_browser()
    if not browser:
        raise PdfUnavailable("PDF export needs Microsoft Edge or Google Chrome on the server (or FIF_PDF_BROWSER set to one).")
    async with _sem:
        data = await asyncio.to_thread(_render, browser, html)
    if key:
        _cache[key] = data
        while len(_cache) > 20:
            _cache.popitem(last=False)
    return data
