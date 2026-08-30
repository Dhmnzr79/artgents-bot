"""Eval-only hook registry with guaranteed restoration (architecture compare LIVE prep)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator

_HookFn = Callable[..., Any]
_ACTIVE_HOOKS: dict[str, _HookFn] = {}


def install_eval_hook(name: str, hook: _HookFn) -> _HookFn | None:
    previous = _ACTIVE_HOOKS.get(name)
    _ACTIVE_HOOKS[name] = hook
    return previous


def get_eval_hook(name: str) -> _HookFn | None:
    return _ACTIVE_HOOKS.get(name)


def restore_eval_hooks() -> None:
    _ACTIVE_HOOKS.clear()


def active_eval_hook_names() -> tuple[str, ...]:
    return tuple(sorted(_ACTIVE_HOOKS))


@contextmanager
def eval_hook_scope(hooks: dict[str, _HookFn]) -> Iterator[None]:
    previous: dict[str, _HookFn | None] = {}
    try:
        for name, hook in hooks.items():
            previous[name] = install_eval_hook(name, hook)
        yield
    finally:
        restore_eval_hooks()
        for name, hook in previous.items():
            if hook is not None:
                _ACTIVE_HOOKS[name] = hook
