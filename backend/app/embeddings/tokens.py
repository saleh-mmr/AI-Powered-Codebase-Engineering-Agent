from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    # Repository text containing special-token strings is still ordinary data.
    return len(encoding().encode(text, disallowed_special=()))


def token_parts(text: str, limit: int = 4096) -> list[list[int]]:
    ids = encoding().encode(text, disallowed_special=())
    return [ids[i : i + limit] for i in range(0, len(ids), limit)]


if __name__ == "__main__":
    encoding()
    print("cl100k_base tokenizer is cached and ready")
