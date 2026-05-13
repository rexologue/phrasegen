"""Load callback functions from user-provided Python files."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

from phrasegen.callbacks.contracts import PostValidationCallback, PreExtensionCallback
from phrasegen.config.entities import CallbackSpec


class CallbackLoader:
    """Loads and caches callback functions by file and function name."""

    def __init__(self) -> None:
        """Initialize an empty callback cache."""
        self._cache: dict[tuple[str, str], Callable[..., Any]] = {}

    def load_pre_extension(self, spec: CallbackSpec) -> PreExtensionCallback:
        """Load a pre-extension callback."""
        callback = self._load(spec)
        return callback

    def load_post_validation(self, spec: CallbackSpec) -> PostValidationCallback:
        """Load a post-validation callback."""
        callback = self._load(spec)
        return callback

    def _load(self, spec: CallbackSpec) -> Callable[..., Any]:
        """Load one callback function from disk or cache."""
        self._ensure_valid_path(spec.path)
        key = (str(spec.path.resolve()), spec.function)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        module = self._load_module(spec.path, spec.function)
        callback = getattr(module, spec.function, None)
        if callback is None:
            raise AttributeError(f"Callback function '{spec.function}' not found in {spec.path}")
        if not callable(callback):
            raise TypeError(f"Callback '{spec.function}' from {spec.path} is not callable")
        self._cache[key] = callback
        return callback

    def _load_module(self, path: Path, function_name: str) -> Any:
        """Load a Python module under an isolated generated module name."""
        module_hash = hashlib.sha1(f"{path.resolve()}::{function_name}".encode("utf-8")).hexdigest()
        module_name = f"_phrasegen_callback_{module_hash}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load callback file: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _ensure_valid_path(self, path: Path) -> None:
        """Raise an error if a callback path is not a regular file."""
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Callback file is invalid: {path}")
