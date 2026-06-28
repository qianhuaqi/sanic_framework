from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest
from lingshu.core import RoutingError
from lingshu.http import (
    Request,
    Response,
    RouteDeclaration,
    RouteMatchKind,
    compile_router,
)


async def handler(request: Request) -> Response:
    del request
    return Response.text("ok")


def test_static_specificity_precedes_dynamic_before_method_selection() -> None:
    dynamic = RouteDeclaration("/users/{user_id}", ("GET",), handler, name="user")
    static = RouteDeclaration("/users/me", ("POST",), handler, name="me")
    router = compile_router((dynamic, static))

    selected = router.match("POST", "/users/me")
    assert selected.kind is RouteMatchKind.MATCH
    assert selected.route is static
    assert selected.path_params == {}

    shadowed = router.match("GET", "/users/me")
    assert shadowed.kind is RouteMatchKind.METHOD_NOT_ALLOWED
    assert tuple(method.value for method in shadowed.allowed_methods) == ("POST",)

    dynamic_match = router.match("GET", "/users/42")
    assert dynamic_match.route is dynamic
    assert dynamic_match.path_params == {"user_id": "42"}
    with pytest.raises(TypeError):
        dynamic_match.path_params["user_id"] = "43"  # type: ignore[index]

    assert router.match("GET", "/missing").kind is RouteMatchKind.NOT_FOUND
    assert router.get_named("user") is dynamic


def test_same_shape_disjoint_methods_keep_selected_parameter_names() -> None:
    read = RouteDeclaration("/items/{item_id}", ("GET",), handler)
    write = RouteDeclaration("/items/{slug}", ("POST",), handler)
    router = compile_router((read, write))

    assert router.match("GET", "/items/7").path_params == {"item_id": "7"}
    assert router.match("POST", "/items/7").path_params == {"slug": "7"}
    denied = router.match("DELETE", "/items/7")
    assert denied.kind is RouteMatchKind.METHOD_NOT_ALLOWED
    assert tuple(method.value for method in denied.allowed_methods) == ("GET", "POST")


def test_router_compilation_rejects_conflicts_before_publication() -> None:
    with pytest.raises(RoutingError) as duplicate_name:
        compile_router(
            (
                RouteDeclaration("/a", ("GET",), handler, name="same"),
                RouteDeclaration("/b", ("GET",), handler, name="same"),
            )
        )
    assert duplicate_name.value.code == "routing.duplicate_name"

    with pytest.raises(RoutingError) as method_conflict:
        compile_router(
            (
                RouteDeclaration("/a", ("GET",), handler),
                RouteDeclaration("/a", ("GET",), handler),
            )
        )
    assert method_conflict.value.code == "routing.method_conflict"

    with pytest.raises(RoutingError) as ambiguity:
        compile_router(
            (
                RouteDeclaration("/a/{first}", ("GET",), handler),
                RouteDeclaration("/a/{second}", ("GET",), handler),
            )
        )
    assert ambiguity.value.code == "routing.ambiguous_template"


@pytest.mark.parametrize(
    "template",
    (
        "relative",
        "/trailing/",
        "/double//segment",
        "/bad/{not-valid}",
        "/duplicate/{value}/{value}",
        "/partial/prefix{value}",
        "/query?value=1",
    ),
)
def test_invalid_route_templates_fail_safely(template: str) -> None:
    with pytest.raises(RoutingError):
        RouteDeclaration(template, ("GET",), handler)


def test_invalid_and_duplicate_methods_fail_as_route_configuration() -> None:
    with pytest.raises(RoutingError) as invalid:
        RouteDeclaration("/a", ("BAD METHOD",), handler)
    assert invalid.value.code == "routing.invalid_method"

    with pytest.raises(RoutingError) as duplicate:
        RouteDeclaration("/a", ("GET", "get"), handler)
    assert duplicate.value.code == "routing.duplicate_method"


def test_router_and_declarations_are_immutable_and_concurrent_read_safe() -> None:
    route = RouteDeclaration("/values/{value}", ("GET",), handler)
    router = compile_router((route,))

    with pytest.raises(FrozenInstanceError):
        setattr(route, "name", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(router, "_routes", ())

    with ThreadPoolExecutor(max_workers=8) as executor:
        matches = list(
            executor.map(
                lambda value: router.match("GET", f"/values/{value}"),
                range(100),
            )
        )
    assert tuple(match.path_params["value"] for match in matches) == tuple(
        str(value) for value in range(100)
    )
