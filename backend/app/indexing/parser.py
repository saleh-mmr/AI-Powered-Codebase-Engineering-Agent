"""Static Python symbols. Source is data: never import, evaluate, or compile to bytecode."""

import ast
from dataclasses import dataclass

PARSER_VERSION = "python312-v1"
MAX_NODES = 40000


@dataclass(frozen=True)
class Symbol:
    name: str
    qualified_name: str
    kind: str
    parent: int | None
    start_line: int
    end_line: int
    signature: str | None = None
    docstring: str | None = None


@dataclass(frozen=True)
class Parsed:
    symbols: list[Symbol]
    diagnostic: str | None = None


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str | None:
    """Normalized metadata only; exact source always lives in the source slices."""
    try:
        parameters = (
            "[" + ", ".join(ast.unparse(p) for p in node.type_params) + "]"
            if node.type_params
            else ""
        )
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(p) for p in [*node.bases, *node.keywords])
            value = f"class {node.name}{parameters}({bases})"
        else:
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            returns = " -> " + ast.unparse(node.returns) if node.returns else ""
            value = f"{prefix} {node.name}{parameters}({ast.unparse(node.args)}){returns}"
        return value if len(value.encode("utf-8")) <= 8192 else None
    except RecursionError:
        return None


def parse_python(content: str) -> Parsed:
    try:
        tree = ast.parse(content, feature_version=(3, 12))
    except (SyntaxError, ValueError):
        return Parsed([], "syntax_error: cannot parse as Python 3.12; using text chunks")
    except RecursionError:
        return Parsed([], "parser_depth: syntax too deeply nested; using text chunks")
    symbols: list[Symbol] = []
    # Iterative traversal bounds Python stack use and retains lexical scopes.
    stack: list[tuple[ast.AST, int | None]] = [(tree, None)]
    visited = 0
    while stack:
        node, parent = stack.pop()
        visited += 1
        if visited > MAX_NODES:
            return Parsed([], "node_limit: AST exceeds 40000 nodes; using text chunks")
        names: list[tuple[str, str]] = []
        scope = parent
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = (
                "class"
                if isinstance(node, ast.ClassDef)
                else (
                    "method"
                    if parent is not None and symbols[parent].kind == "class"
                    else "function"
                )
            )
            names = [(node.name, kind)]
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [(alias.asname or alias.name, "import") for alias in node.names]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and (
            parent is None or symbols[parent].kind == "class"
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [
                (n.id, "variable")
                for t in targets
                for n in ast.walk(t)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            ]
        if isinstance(node, ast.stmt):
            start = node.lineno
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([start, *(d.lineno for d in node.decorator_list)])
            for name, kind in names:
                prefix = symbols[parent].qualified_name + "." if parent is not None else ""
                if len(name) > 512 or len(prefix + name) > 2048:
                    return Parsed(
                        [], "symbol_limit: identifier or scope too long; using text chunks"
                    )
                symbols.append(
                    Symbol(
                        name,
                        prefix + name,
                        kind,
                        parent,
                        start,
                        node.end_lineno or node.lineno,
                        signature(node)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        else None,
                        ast.get_docstring(node, clean=False)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                        else None,
                    )
                )
                if kind in {"class", "function", "method"}:
                    scope = len(symbols) - 1
        stack.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
    return Parsed(symbols)
