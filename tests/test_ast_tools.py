import ast
from textwrap import dedent

from hypothesis import assume, given, strategies as st

from developer.ast_tools import rename_function


_identifier_start = st.sampled_from(list("abcdefghijklmnopqrstuvwxyz_"))
_identifier_body = st.text(alphabet=list("abcdefghijklmnopqrstuvwxyz_0123456789"), min_size=0, max_size=6)
identifiers = st.builds(lambda start, rest: start + rest, _identifier_start, _identifier_body)


@given(old=identifiers, new=identifiers)
def test_rename_function_preserves_calls_and_definitions(old: str, new: str) -> None:
    assume(old not in {"inner", "caller"})
    assume(new not in {"inner", "caller"})
    assume(old != new)

    source = dedent(
        f"""
        def {old}(value):
            def inner():
                return value

            if value:
                return {old}(value - 1)
            return value

        def caller():
            return {old}(3)
        """
    )

    renamed = rename_function(source, old, new)

    tree = ast.parse(renamed)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert new in function_names
    assert old not in function_names
    assert "inner" in function_names

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != old

    compile(renamed, "<test>", "exec")
