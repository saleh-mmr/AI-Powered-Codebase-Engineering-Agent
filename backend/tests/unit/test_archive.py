import gzip
import io
import tarfile

import pytest

from app.indexing.archive import ArchiveLimits, read_archive
from app.indexing.errors import ImportFailure


def archive(entries: list[tuple[str, bytes, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(content) if kind == tarfile.REGTYPE else 0
            if kind == tarfile.SYMTYPE:
                info.linkname = "/etc/passwd"
            tar.addfile(info, io.BytesIO(content) if kind == tarfile.REGTYPE else None)
    return buffer.getvalue()


def test_safe_source_and_exclusions() -> None:
    blob = archive(
        [
            (name, content, kind)
            for name, content, kind in [
                ("repo/main.py", b"print('safe data')", tarfile.REGTYPE),
                ("repo/.env.local", b"SECRET=value", tarfile.REGTYPE),
                ("repo/node_modules/a.js", b"ignored", tarfile.REGTYPE),
                ("repo/keys.pem", b"secret", tarfile.REGTYPE),
                ("repo/binary.py", b"a\x00b", tarfile.REGTYPE),
                ("repo/link.py", b"", tarfile.SYMTYPE),
                ("repo/lfs.txt", b"version https://git-lfs.github.com/spec/v1", tarfile.REGTYPE),
            ]
        ]
    )
    result = read_archive(blob)
    assert [file.path for file in result.files] == ["main.py"]
    assert result.files[0].content == "print('safe data')"
    assert result.scanned == 7 and result.skipped == 6


@pytest.mark.parametrize(
    "path",
    [
        "/root/evil.py",
        "root/../evil.py",
        "root/./evil.py",
        "root/a\\evil.py",
        "root/a:evil.py",
        "root/a\x01.py",
    ],
)
def test_unsafe_paths(path: str) -> None:
    with pytest.raises(ImportFailure, match="unsafe path"):
        read_archive(archive([(path, b"x", tarfile.REGTYPE)]))


def test_duplicates_rejected() -> None:
    with pytest.raises(ImportFailure, match="duplicate"):
        read_archive(
            archive([("r/a.py", b"1", tarfile.REGTYPE), ("r/a.py", b"2", tarfile.REGTYPE)])
        )


def test_expansion_limit_includes_ignored_files() -> None:
    with pytest.raises(ImportFailure, match="Expanded archive"):
        read_archive(
            archive([("r/node_modules/a.js", b"a" * 100000, tarfile.REGTYPE)]),
            ArchiveLimits(expanded_bytes=20000),
        )


def test_storage_and_entry_limits() -> None:
    blob = archive([("r/a.py", b"123456", tarfile.REGTYPE), ("r/b.py", b"123456", tarfile.REGTYPE)])
    with pytest.raises(ImportFailure, match="storage limit"):
        read_archive(blob, ArchiveLimits(stored_bytes=10))
    with pytest.raises(ImportFailure, match="entry count"):
        read_archive(blob, ArchiveLimits(members=1))


def test_oversized_files_skipped_and_invalid_archives_rejected() -> None:
    result = read_archive(
        archive(
            [("r/large.py", b"123456", tarfile.REGTYPE), ("r/small.py", b"x", tarfile.REGTYPE)]
        ),
        ArchiveLimits(file_bytes=3),
    )
    assert [item.path for item in result.files] == ["small.py"]
    with pytest.raises(ImportFailure, match="invalid or truncated"):
        read_archive(b"not gzip")
    with pytest.raises(ImportFailure):
        read_archive(gzip.compress(b"not a tar archive"))
