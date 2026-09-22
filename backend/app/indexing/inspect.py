"""Offline inspection: python -m app.indexing.inspect tests/fixtures/indexing/sample.py"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.indexing.pipeline import PIPELINE_VERSION, index_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect static symbols and exact source chunks")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    with args.file.open("rb") as stream:
        data = stream.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        parser.error("file exceeds 256 KiB")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        parser.error("file must be UTF-8")
    result = index_source(content, "python" if args.file.suffix in {".py", ".pyi"} else "text")
    print(json.dumps({"pipeline_version": PIPELINE_VERSION, **asdict(result)}, indent=2))


if __name__ == "__main__":
    main()
