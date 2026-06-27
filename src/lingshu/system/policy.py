from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import wraps
from types import MappingProxyType
from typing import Any

from lingshu.response import json_response
from lingshu.system.execution import CancellationReason, current_execution_context


class RoutePolicyError(ValueError):
    pass


_ALLOWED_FIELDS = {"public", "auth_required", "maintenance_check", "timeout", "body_limit", "audit_level"}


@dataclass(frozen=True)
class RoutePolicyDefinition:
    public: bool | None = None
    auth_required: bool | None = None
    maintenance_check: bool | None = None
    timeout: float | None = None
    body_limit: int | None = None
    audit_level: str | None = None

    def __post_init__(self):
        if self.timeout is not None and self.timeout <= 0:
            raise RoutePolicyError("timeout must be greater than zero")
        if self.body_limit is not None and self.body_limit <= 0:
            raise RoutePolicyError("body_limit must be greater than zero")
        if self.public is True and self.auth_required is True:
            raise RoutePolicyError("public route cannot set auth_required=True")

    @classmethod
    def from_mapping(cls, values: dict[str, Any]):
        unknown = set(values) - _ALLOWED_FIELDS
        if unknown:
            raise RoutePolicyError(f"unknown route policy field(s): {', '.join(sorted(unknown))}")
        return cls(**values)

    @classmethod
    def from_legacy(cls, policy):
        auth_required = bool(getattr(policy, "auth_required", True))
        return cls(
            public=not auth_required,
            auth_required=auth_required,
            maintenance_check=bool(getattr(policy, "maintenance_check", True)),
        )

    def merge(self, override: "RoutePolicyDefinition | None") -> "RoutePolicyDefinition":
        if override is None:
            return self
        return RoutePolicyDefinition(
            public=self.public if override.public is None else override.public,
            auth_required=self.auth_required if override.auth_required is None else override.auth_required,
            maintenance_check=self.maintenance_check
            if override.maintenance_check is None
            else override.maintenance_check,
            timeout=self.timeout if override.timeout is None else override.timeout,
            body_limit=self.body_limit if override.body_limit is None else override.body_limit,
            audit_level=self.audit_level if override.audit_level is None else override.audit_level,
        )

    def compile(self, route_name: str) -> "CompiledRoutePolicy":
        public = bool(self.public) if self.public is not None else False
        auth_required = bool(self.auth_required) if self.auth_required is not None else not public
        return CompiledRoutePolicy(
            route_name=route_name,
            public=public,
            auth_required=auth_required,
            maintenance_check=True if self.maintenance_check is None else bool(self.maintenance_check),
            timeout=10.0 if self.timeout is None else float(self.timeout),
            body_limit=self.body_limit,
            audit_level=self.audit_level or "none",
        )


@dataclass(frozen=True)
class CompiledRoutePolicy:
    route_name: str
    public: bool
    auth_required: bool
    maintenance_check: bool
    timeout: float
    body_limit: int | None
    audit_level: str


class CompiledRoutePolicies:
    def __init__(self, policies: dict[str, CompiledRoutePolicy]):
        self._policies = MappingProxyType(dict(policies))

    def for_route(self, route_name: str) -> CompiledRoutePolicy:
        try:
            return self._policies[route_name]
        except KeyError as exc:
            raise RoutePolicyError(f"No compiled route policy for {route_name}") from exc

    def items(self):
        return self._policies.items()

    def __contains__(self, route_name: str) -> bool:
        return route_name in self._policies


class RoutePolicyRegistry:
    def __init__(self, defaults: RoutePolicyDefinition | None = None):
        self.defaults = defaults or RoutePolicyDefinition(timeout=10.0, maintenance_check=True)


def set_route_policy(handler, policy: RoutePolicyDefinition):
    setattr(handler, "__lingshu_route_policy__", policy)
    return handler


def _normalize_definition(value) -> RoutePolicyDefinition | None:
    if value is None:
        return None
    if isinstance(value, RoutePolicyDefinition):
        return value
    return RoutePolicyDefinition.from_legacy(value)


class RoutePolicyCompiler:
    def __init__(self, registry: RoutePolicyRegistry | None = None):
        self.registry = registry or RoutePolicyRegistry()

    def compile_app(self, app) -> CompiledRoutePolicies:
        policies: dict[str, CompiledRoutePolicy] = {}
        for route in app.router.routes:
            if getattr(route, "extra", None) and route.extra.static:
                continue
            handler = getattr(route, "handler", None)
            route_name = self._normalized_route_name(app, route, handler)
            if not route_name:
                raise RoutePolicyError("Route policy route_name cannot be empty")
            if route_name in policies:
                raise RoutePolicyError(f"Duplicate route policy route_name: {route_name}")
            blueprint = self._blueprint_for_route(app, route)
            blueprint_policy = _normalize_definition(getattr(getattr(blueprint, "ctx", None), "route_policy", None))
            route_policy = _normalize_definition(getattr(handler, "__lingshu_route_policy__", None))
            definition = self.registry.defaults.merge(blueprint_policy).merge(route_policy)
            compiled = definition.compile(route_name)
            policies[route_name] = compiled
            if handler is not None:
                setattr(handler, "__lingshu_compiled_policy__", compiled)
                self._wrap_handler(route, handler, compiled)
        return CompiledRoutePolicies(policies)

    def _wrap_handler(self, route, handler, compiled: CompiledRoutePolicy):
        if getattr(handler, "__lingshu_deadline_wrapped__", False):
            return

        @wraps(handler)
        async def deadline_wrapper(request, *args, **kwargs):
            from lingshu.system.sanic_adapter import finalize_request_context

            execution = current_execution_context()
            remaining = execution.remaining

            if remaining <= 0:
                execution.cancel(CancellationReason.REQUEST_TIMEOUT)
                await finalize_request_context(request)
                return json_response(
                    {"request_id": execution.request_id},
                    code=990002,
                    msg="Request deadline exceeded",
                    status=504,
                )

            handler_task = asyncio.ensure_future(handler(request, *args, **kwargs))
            try:
                done, _pending = await asyncio.wait((handler_task,), timeout=remaining)
                if handler_task in done:
                    return await handler_task
                execution.cancel(CancellationReason.REQUEST_TIMEOUT)
                handler_task.cancel()
                await asyncio.gather(handler_task, return_exceptions=True)
                return json_response(
                    {"request_id": execution.request_id},
                    code=990002,
                    msg="Request deadline exceeded",
                    status=504,
                )
            except asyncio.CancelledError:
                if execution.cancel_reason is None:
                    execution.cancel(CancellationReason.CLIENT_DISCONNECT)
                if not handler_task.done():
                    handler_task.cancel()
                    await asyncio.gather(handler_task, return_exceptions=True)
                raise
            finally:
                await finalize_request_context(request)

        deadline_wrapper.__lingshu_deadline_wrapped__ = True
        deadline_wrapper.__lingshu_route_policy__ = getattr(handler, "__lingshu_route_policy__", None)
        deadline_wrapper.__lingshu_compiled_policy__ = compiled
        route.handler = deadline_wrapper

    def _normalized_route_name(self, app, route, handler) -> str:
        route_name = getattr(route, "name", None)
        if route_name is None:
            route_name = getattr(handler, "__name__", "")
        prefix = f"{app.name}."
        if route_name.startswith(prefix):
            return route_name[len(prefix) :]
        return route_name

    def _blueprint_for_route(self, app, route):
        route_name = getattr(route, "name", "")
        prefix = f"{app.name}."
        if not route_name.startswith(prefix):
            return None
        parts = route_name[len(prefix) :].split(".")
        if len(parts) < 2:
            return None
        return app.blueprints.get(parts[0])
