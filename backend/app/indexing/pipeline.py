from dataclasses import dataclass

from app.indexing.chunks import CHUNKER_VERSION, Chunk, chunk_source
from app.indexing.errors import ImportFailure
from app.indexing.parser import PARSER_VERSION, Parsed, Symbol, parse_python

PIPELINE_VERSION = PARSER_VERSION + ":" + CHUNKER_VERSION


@dataclass(frozen=True)
class IndexedSource:
    symbols: list[Symbol]
    chunks: list[Chunk]
    diagnostic: str | None


def index_source(content: str, language: str) -> IndexedSource:
    if len(content.encode("utf-8")) > 256 * 1024:
        raise ImportFailure("index_file_limit", "Source file exceeds the indexing size limit.")
    parsed = parse_python(content) if language == "python" else Parsed([])
    mode = "fallback" if parsed.diagnostic else "module" if language == "python" else "text"
    return IndexedSource(
        parsed.symbols, chunk_source(content, parsed.symbols, mode), parsed.diagnostic
    )
