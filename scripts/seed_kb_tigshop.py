#!/usr/bin/env python3
"""Seed the knowledge base with TigShop documentation."""

import sys
from pathlib import Path

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
API = f"{BASE_URL}/api/knowledge"

MD_FILE = Path(__file__).resolve().parent.parent / "docs" / "kb-seeds" / "tigshop.md"


def main():
    content = MD_FILE.read_text(encoding="utf-8")
    print(f"Read {len(content)} chars from {MD_FILE.name}")

    resp = httpx.post(
        f"{API}/documents/text",
        json={"title": "TigShop 开源商城系统", "content": content, "file_type": "md"},
        timeout=30,
    )

    if resp.status_code == 200:
        data = resp.json()
        print(f"Created document: id={data.get('id')}, status={data.get('status')}")
        print("Document will be chunked and embedded in background.")
    else:
        print(f"Failed ({resp.status_code}): {resp.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
