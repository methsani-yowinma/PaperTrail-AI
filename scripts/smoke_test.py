"""End-to-end smoke test against RUNNING servers (no mocks).

Exercises the full path a browser uses: Next.js pages and the /api/backend proxy, which
forwards to FastAPI. Uses synthetic PDFs generated on the fly.

Usage (from the repository root, with both servers running):

    backend/.venv/Scripts/python scripts/smoke_test.py            # Windows
    backend/.venv/bin/python scripts/smoke_test.py                # macOS/Linux
    python scripts/smoke_test.py --frontend http://localhost:3000

In local development mode no token is needed. With Supabase Auth enabled, pass a user
access token: --token <jwt>  (the token is sent only to the given frontend URL).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tests.pdf_factory import DROPOUT_CONTRADICT, DROPOUT_SUPPORT, make_pdf  # noqa: E402

PAGES = ["/", "/login", "/dashboard", "/library", "/verify", "/investigations", "/reports", "/settings"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend", default="http://localhost:3000")
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    client = httpx.Client(base_url=args.frontend, timeout=300, headers=headers)
    api = lambda path: f"/api/backend{path}"  # noqa: E731
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if condition else 'FAIL'}] {label}{(' - ' + detail) if detail and not condition else ''}")
        if not condition:
            failures.append(label)

    print("1. Pages render")
    for page in PAGES:
        r = client.get(page)
        check(f"GET {page} -> {r.status_code}", r.status_code == 200)

    print("2. Backend reachable through the proxy")
    status = client.get(api("/system/status"))
    check("system status", status.status_code == 200, status.text[:200])
    if status.status_code != 200:
        return 1
    s = status.json()
    print(f"     auth={s['auth_mode']} db={s['database_backend']} embeddings={s['embedding_model']} "
          f"assessment_configured={s['assessment_configured']}")

    print("3. Upload and process synthetic PDFs")
    stamp = str(time.time_ns())
    doc_ids = []
    for name, pages in (("support", DROPOUT_SUPPORT), ("contradict", DROPOUT_CONTRADICT)):
        pdf = make_pdf(pages + [[("p", f"Smoke test marker {stamp} {name}.")]], title=f"Smoke {name} {stamp}")
        r = client.post(api("/documents/upload"), files={"file": (f"smoke-{name}.pdf", pdf, "application/pdf")})
        check(f"upload {name} -> {r.status_code}", r.status_code == 202, r.text[:200])
        if r.status_code == 202:
            doc_ids.append(r.json()["id"])
    for doc_id in doc_ids:
        for _ in range(120):
            doc = client.get(api(f"/documents/{doc_id}")).json()
            if doc["processing_status"] not in ("pending", "processing"):
                break
            time.sleep(1)
        check(f"document processed ({doc['processing_status']}, {doc['chunk_count']} passages)", doc["processing_status"] == "completed")
    bad = client.post(api("/documents/upload"), files={"file": ("notes.txt", b"hello", "text/plain")})
    check("non-PDF rejected with 422", bad.status_code == 422)

    print("4. Search")
    found = client.get(api("/documents"), params={"q": stamp}).json()
    check("document search finds uploads", found["total"] == len(doc_ids))

    print("5. Verify a claim")
    inv = client.post(api("/investigations"), json={
        "claim_text": "Dropout regularization reduces overfitting in neural networks.",
        "document_ids": doc_ids, "title": f"Smoke {stamp}",
    })
    check("create investigation", inv.status_code == 201, inv.text[:200])
    result = client.post(api(f"/investigations/{inv.json()['id']}/verify")).json()
    assessment = result["assessment"]
    evidence = assessment["evidence"]
    check("retrieval returned stored passages", len(evidence) > 0)
    check("every displayed citation resolves to a stored passage",
          all(e["citation"]["valid"] and e["citation"]["passage_text"] for e in evidence))
    if s["assessment_configured"]:
        check(f"verdict produced ({assessment['verdict']})", assessment["status"] == "completed" and assessment["verdict"] is not None)
        report = client.get(api(f"/reports/{assessment['id']}"))
        check("report renders", report.status_code == 200)
        md = client.get(api(f"/reports/{assessment['id']}/export"), params={"format": "markdown"})
        check("markdown export", md.status_code == 200 and "# Evidence report" in md.text)
        check("report page renders", client.get(f"/reports/{assessment['id']}").status_code == 200)
    else:
        check("no verdict without Gemini (honest failure)", assessment["status"] == "failed" and assessment["verdict"] is None)
        check("passages marked UNASSESSED", all(e["relation"] == "UNASSESSED" for e in evidence))
    check("investigation page renders", client.get(f"/investigations/{inv.json()['id']}").status_code == 200)
    check("document page renders", client.get(f"/library/{doc_ids[0]}").status_code == 200)

    print("6. Clean up")
    check("delete investigation", client.delete(api(f"/investigations/{inv.json()['id']}")).status_code == 204)
    for doc_id in doc_ids:
        check("delete document", client.delete(api(f"/documents/{doc_id}")).status_code == 204)

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} CHECK(S) FAILED'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
