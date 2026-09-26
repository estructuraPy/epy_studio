"""The ONE canonical Rule 9 variadic-kwargs check, and the only place its
narrow exemption is edited.

WHAT IT CHECKS
--------------
No function or method signature in ``src/`` may declare ``**name`` (variadic
keyword arguments), regardless of the identifier -- ``**kwargs``, ``**data``,
``**fields`` all fail. Explicit parameters are the suite's DNA law: a variadic
signature hides which inputs exist, so a caller's typo becomes a silent no-op
instead of a ``TypeError``.

THE ONE EXEMPTION -- bpy.props RNA shims (an AST PROOF, not an allow-list)
--------------------------------------------------------------------------
epy_blender must import inside AND outside Blender. Outside, ``bpy`` is
absent, so its modules shadow Blender's own property constructors::

    try:
        import bpy
        from bpy.props import StringProperty
    except ImportError:
        def StringProperty(**kw):
            return ""

That ``**kw`` mirrors *Blender's* API surface (name, description, default,
items, min, max, subtype, update, ... -- varying per property type and per
Blender version), so "make the parameters explicit" is not available:
enumerating them creates a maintenance liability that breaks on every Blender
upgrade. The exemption is therefore granted by PROOF, re-derived on every run,
never by a path list (which would blind the rule to whole files) and never by
an inline tag (24 hand-written assertions nobody re-verifies). A shim is
exempt only when ALL THREE clauses hold:

1. **Fallback position** -- the function sits inside an ``except ImportError``
   / ``except ModuleNotFoundError`` handler (a bare ``except:`` does not
   qualify) whose ``try`` body imports ``bpy`` or ``bpy.props``.
2. **RNA identity** -- the function's name is bound by a
   ``from bpy.props import ...`` inside that same ``try`` body, OR the module
   assigns it onto a props namespace (``props.StringProperty = fn``), which is
   how a fake-bpy factory registers its constructors.
3. **Inert body** -- the body is a lone docstring plus a single ``return`` of
   a constant or of one of the function's own parameters. One line of real
   logic and the proof fails, so the violation returns by itself.

SYNC CONTRACT
-------------
Housekeepers load this file by path (``spec_from_file_location``) with a LOUD
fallback -- a silently skipped rule is worse than none. Rule 13's history is
the reason this is one canonical file: five injected copies drifted apart and
four differed in behaviour before it was centralized.
"""

from __future__ import annotations

import ast
from pathlib import Path

_BPY_PROPS = frozenset({
    "BoolProperty", "BoolVectorProperty", "CollectionProperty", "EnumProperty",
    "FloatProperty", "FloatVectorProperty", "IntProperty", "IntVectorProperty",
    "PointerProperty", "StringProperty",
})


def _try_imports_bpy(try_node: ast.Try) -> bool:
    """Whether the ``try`` body imports ``bpy`` or ``bpy.props``."""
    for stmt in try_node.body:
        if isinstance(stmt, ast.Import):
            if any(a.name == "bpy" or a.name.startswith("bpy.") for a in stmt.names):
                return True
        if isinstance(stmt, ast.ImportFrom):
            if stmt.module and (stmt.module == "bpy" or stmt.module.startswith("bpy.")):
                return True
    return False


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """``except ImportError`` / ``ModuleNotFoundError`` only -- never bare."""
    t = handler.type
    if t is None:
        return False
    names = [t] if not isinstance(t, ast.Tuple) else list(t.elts)
    for n in names:
        if isinstance(n, ast.Name) and n.id in ("ImportError", "ModuleNotFoundError"):
            return True
    return False


def _rna_names_imported(stmts: list) -> set[str]:
    """Names bound from ``bpy.props`` among ``stmts``."""
    out: set[str] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "bpy.props":
            for a in stmt.names:
                out.add(a.asname or a.name)
    return out


def _if_tests_bpy(if_node: ast.If) -> bool:
    """Whether the ``if`` test compares a name ending in ``bpy`` with None
    (``if bpy is not None:`` / ``if bpy is None:``) -- the central-import
    idiom (``from epy_blender._core._bpy import bpy`` exporting None outside
    Blender), which replaces a local try/except in most addon modules."""
    test = if_node.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]
    names = [n for n in (left, right) if isinstance(n, ast.Name)]
    consts = [c for c in (left, right) if isinstance(c, ast.Constant) and c.value is None]
    return bool(consts) and any(n.id == "bpy" or n.id.endswith("_bpy") for n in names)


def _props_assigned_names(tree: ast.Module) -> dict[str, str]:
    """``{function_name: rna_attr}`` for ``<ns>.<RnaProp> = <function>``
    assignments anywhere in the module -- the fake-bpy factory idiom."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Attribute) and target.attr in _BPY_PROPS
                and isinstance(node.value, ast.Name)):
            out[node.value.id] = target.attr
    return out


def _body_is_inert(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A lone docstring plus one ``return`` that only ECHOES an input: a
    constant, one of the function's own parameters, or
    ``<own kwarg>.get("<key>"[, <constant>])`` -- the RNA stand-in evaluating
    to its declared default. Any other expression is real logic."""
    body = list(func.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    value = body[0].value
    params = {a.arg for a in func.args.args + func.args.kwonlyargs}
    kwarg = func.args.kwarg.arg if func.args.kwarg is not None else None
    if value is None or isinstance(value, ast.Constant):
        return True
    if isinstance(value, ast.Name):
        return value.id in params or value.id == kwarg
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
            and value.func.attr == "get"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == kwarg
            and 1 <= len(value.args) <= 2
            and all(isinstance(a, ast.Constant) for a in value.args)
            and not value.keywords):
        return True
    return False


def _is_rna_property_shim(
    func,
    position,
    props_assigned: dict,
) -> bool:
    """The three-clause proof. See the module docstring.

    ``position`` is where the def sits: ``("except", (Try, handler))`` for
    the try/ImportError fallback, ``("else", If)`` for the shim branch of an
    ``if bpy is not None:`` / ``if bpy is None:``. A fake-bpy FACTORY needs
    no such position: its RNA identity is the module's own ``props.X = fn``
    binding, which is clause 1+2 in one act -- but its body must still be
    inert (clause 3)."""
    if func.name in props_assigned:
        return _body_is_inert(func)
    if position is None:
        return False
    kind, node = position
    if kind == "except":
        try_node, handler = node
        if not _handler_catches_import_error(handler):
            return False
        if not _try_imports_bpy(try_node):
            return False
        rna_names = _rna_names_imported(try_node.body)
    elif kind == "else":
        if not _if_tests_bpy(node):
            return False
        rna_names = _rna_names_imported(node.body) | _rna_names_imported(node.orelse)
    else:
        return False
    if func.name not in rna_names and func.name not in _BPY_PROPS:
        return False
    return _body_is_inert(func)


def collect_kwargs_signature_violations(py_file: Path, rel: Path) -> list[str]:
    """Every ``**name`` signature in ``py_file`` that is not a proven RNA shim."""
    try:
        text = py_file.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    props_assigned = _props_assigned_names(tree)

    # Map every def to its qualifying position (except-handler / bpy-if branch).
    context: dict = {}

    def visit(node, current) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(node, ast.Try) and isinstance(child, ast.ExceptHandler):
                visit(child, ("except", (node, child)))
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                context[id(child)] = current
                # Inner defs of a shim are not shims themselves:
                visit(child, None)
                continue
            visit(child, current)

    visit(tree, None)

    # Seed the bpy-if branches: defs in the SHIM branch of a bpy/None test
    # (orelse of `if bpy is not None:`, body of `if bpy is None:`).
    for child in ast.walk(tree):
        if isinstance(child, ast.If) and _if_tests_bpy(child):
            is_not = any(isinstance(op, ast.IsNot) for op in child.test.ops)
            branch = child.orelse if is_not else child.body
            for stmt in branch:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    context[id(stmt)] = ("else", child)

    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kw = node.args.kwarg
            if kw is None:
                continue
            if _is_rna_property_shim(node, context.get(id(node)), props_assigned):
                continue
            out.append(
                f"{rel}:{kw.lineno}: forbidden `**{kw.arg}` in signature of "
                f"`{node.name}` — all parameters must be explicit (Rule 9)."
            )
    return out


def _self_test() -> int:
    """Both directions of the shim proof. Run: ``python rule9_kwargs_block.py``."""
    import textwrap

    def check(src: str) -> list[str]:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "probe.py"
            p.write_text(textwrap.dedent(src), encoding="utf-8")
            return collect_kwargs_signature_violations(p, Path("probe.py"))

    cases: list[tuple[str, str, bool]] = [
        ("shim in ImportError fallback", """
            try:
                import bpy
                from bpy.props import StringProperty
            except ImportError:
                def StringProperty(**kw):
                    return ""
        """, True),
        ("body with real logic", """
            try:
                import bpy
                from bpy.props import StringProperty
            except ImportError:
                def StringProperty(**kw):
                    return _resolve(kw)
        """, False),
        ("bare except does not qualify", """
            try:
                import bpy
                from bpy.props import StringProperty
            except Exception:
                def StringProperty(**kw):
                    return ""
        """, False),
        ("module level, no try", """
            def StringProperty(**kw):
                return ""
        """, False),
        ("fake factory registers onto props namespace", """
            try:
                import bpy
            except ImportError:
                def _fake_string_property(default="", **_kw):
                    return default
                props.StringProperty = _fake_string_property
        """, True),
        ("fake without the props assignment", """
            try:
                import bpy
            except ImportError:
                def _fake_string_property(default="", **_kw):
                    return default
        """, False),
        ("non-RNA name in ImportError block", """
            try:
                import bpy
            except ImportError:
                def build(**kwargs):
                    return ""
        """, False),
        ("central-import if/else shim", """
            from epy_blender._core._bpy import bpy
            if bpy is not None:
                from bpy.props import StringProperty
            else:
                def StringProperty(**_kwargs):
                    return _kwargs.get("default", "")
        """, True),
        ("if/else shim with real logic", """
            from epy_blender._core._bpy import bpy
            if bpy is not None:
                from bpy.props import StringProperty
            else:
                def StringProperty(**_kwargs):
                    return resolve(_kwargs)
        """, False),
        ("shim in the WRONG branch (bpy present)", """
            from epy_blender._core._bpy import bpy
            if bpy is not None:
                def StringProperty(**_kwargs):
                    return ""
            else:
                pass
        """, False),
        ("non-RNA name in the else branch", """
            from epy_blender._core._bpy import bpy
            if bpy is not None:
                from bpy.props import StringProperty
            else:
                def helper(**kwargs):
                    return ""
        """, False),
        ("kwarg .get with keyword args is real logic", """
            try:
                import bpy
                from bpy.props import StringProperty
            except ImportError:
                def StringProperty(**kw):
                    return kw.get("default", factory())
        """, False),
    ]

    failures: list[str] = []
    for label, src, expect_exempt in cases:
        violations = check(src)
        exempt = not violations
        if exempt != expect_exempt:
            failures.append(f"{label}: expected exempt={expect_exempt}, got {violations}")

    # Regression pin: a repo with NO shims must report the same set the
    # inline rule reports -- proves the extraction did not weaken anything.
    towers = Path(__file__).resolve().parent.parent.parent / "epy_towers"
    if (towers / "src").is_dir():
        count = 0
        for py in (towers / "src").rglob("*.py"):
            count += len(collect_kwargs_signature_violations(py, py.relative_to(towers)))
        if count != 0:
            failures.append(f"epy_towers src must report 0 kwargs violations, got {count}")
        print(f"regression pin: epy_towers src -> {count} violations")

    for f in failures:
        print("FAIL:", f)
    if failures:
        return 1
    print(f"OK - {len(cases)} shim-proof cases pass in both directions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
