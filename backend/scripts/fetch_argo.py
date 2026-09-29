#!/usr/bin/env python3
"""Download the INCOIS ARGO analysis used for independent validation.

ARGO is the observational reference for OceanEmbed and is never used for training.
The bundled file (``backend/data/argo/argo_2020-01.nc``) covers January 2020 so the
demo works with no network access. Use this script to pull a different window, for
example a genuinely out-of-sample year once one is available.

Usage
-----
    python3 backend/scripts/fetch_argo.py --start 2020-01-01 --end 2020-01-31
    python3 backend/scripts/fetch_argo.py --start 2021-01-01 --end 2021-12-31 \\
        --lat-min 5 --lat-max 30 --lon-min 45 --lon-max 105 \\
        --output backend/data/argo/argo_2021.nc

The INCOIS ERDDAP endpoint is public and needs no credentials. Its TLS chain is not
always in the system store, so the download falls back to ``certifi`` when the
default context fails.
"""

from __future__ import annotations

import argparse
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATASET = "incois_argo_10day_McCreary"
VARIABLE = "T_ANALYZED"
ERDDAP_BASE = "https://erddap.incois.gov.in/erddap/griddap"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "backend" / "data" / "argo" / "argo_2020-01.nc"


def build_url(
    start: str,
    end: str,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    depth_min: float,
    depth_max: float,
) -> str:
    """Assemble an ERDDAP griddap request for a time/depth/space window.

    ERDDAP writes constraints as ``[start:stride:stop]``. The square brackets must be
    percent-encoded: the INCOIS server sits behind Tomcat, which rejects raw ``[`` and
    ``]`` in the request target with HTTP 400 ("Invalid character found in the request
    target"). Colons, parentheses and periods are all legal and are left alone.
    """
    # ERDDAP requires the strides to be written as (start):stride:(stop).
    query = (
        f"{VARIABLE}"
        f"[({start}):1:({end})]"
        f"[({depth_min}):1:({depth_max})]"
        f"[({lat_min}):1:({lat_max})]"
        f"[({lon_min}):1:({lon_max})]"
    )
    query = query.replace("[", "%5B").replace("]", "%5D")
    return f"{ERDDAP_BASE}/{DATASET}.nc?{query}"


def _open(url: str, timeout: int, context: ssl.SSLContext | None = None):
    request = urllib.request.Request(url, headers={"User-Agent": "oceanembed-fetch-argo/1.0"})
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def _is_tls_failure(exc: BaseException) -> bool:
    """True when the failure is a certificate-verification problem."""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLCertVerificationError)


def download(url: str, destination: Path, *, timeout: int = 180, insecure: bool = False) -> int:
    """Fetch ``url`` to ``destination``, returning the number of bytes written.

    TLS verification is attempted with the system store and then with ``certifi``.
    The INCOIS chain is not always complete in either, so ``insecure`` is offered as
    an explicit opt-in rather than a silent fallback: this endpoint is a public,
    read-only archive, but a caller should still choose to skip verification.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    contexts: list[tuple[str, ssl.SSLContext | None]] = [("system trust store", None)]
    try:
        import certifi

        contexts.append(("certifi bundle", ssl.create_default_context(cafile=certifi.where())))
    except ImportError:
        pass

    last_error: BaseException | None = None
    for label, context in contexts:
        try:
            with _open(url, timeout, context) as response, destination.open("wb") as handle:
                handle.write(response.read())
            return destination.stat().st_size
        except Exception as exc:  # noqa: BLE001 - decide based on the failure type
            if not _is_tls_failure(exc):
                raise
            last_error = exc
            print(f"TLS verification failed using the {label}.", file=sys.stderr)

    if not insecure:
        raise SystemExit(
            "Could not verify the INCOIS TLS certificate with either the system trust store or "
            "certifi.\nRe-run with --insecure to download without verification (public read-only "
            "archive), or fetch the file in a browser and save it under backend/data/argo/.\n"
            f"Last error: {last_error}"
        )

    print("WARNING: TLS verification disabled (--insecure).", file=sys.stderr)
    with _open(url, timeout, ssl._create_unverified_context()) as response, destination.open("wb") as handle:
        handle.write(response.read())
    return destination.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2020-01-01", help="Start date (YYYY-MM-DD).")
    parser.add_argument("--end", default="2020-01-31", help="End date (YYYY-MM-DD).")
    parser.add_argument("--lat-min", type=float, default=5.0)
    parser.add_argument("--lat-max", type=float, default=30.0)
    parser.add_argument("--lon-min", type=float, default=45.0)
    parser.add_argument("--lon-max", type=float, default=105.0)
    parser.add_argument("--depth-min", type=float, default=5.0, help="ARGO has no 0 m level; 5 m is the shallowest.")
    parser.add_argument("--depth-max", type=float, default=2000.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS verification. Needed on some machines because the INCOIS certificate chain is incomplete.",
    )
    args = parser.parse_args(argv)

    url = build_url(
        args.start,
        args.end,
        args.lat_min,
        args.lat_max,
        args.lon_min,
        args.lon_max,
        args.depth_min,
        args.depth_max,
    )
    print(f"GET {urllib.parse.unquote(url)}")
    size = download(url, args.output, insecure=args.insecure)
    print(f"wrote {args.output} ({size:,} bytes)")

    if size < 10_000:
        print(
            "The response is suspiciously small; ERDDAP may have returned an error document. "
            f"Inspect {args.output} before committing it.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
