"""Import-boundary tests for optional MCP/dashboard dependencies."""

import builtins
import importlib
import sys

import pytest


def _block_mcp_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mcp" or name.startswith("mcp."):
            raise ModuleNotFoundError("No module named 'mcp'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def test_dashboard_module_import_does_not_require_mcp(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("haxaml_ui")
    for module_name in (
        "haxaml_ui.dashboard",
        "haxaml_ui",
        "haxaml.mcp",
        "haxaml.mcp.base",
        "haxaml.mcp.lifecycle_helpers",
    ):
        sys.modules.pop(module_name, None)
    _block_mcp_imports(monkeypatch)

    module = importlib.import_module("haxaml_ui.dashboard")
    assert callable(module.create_dashboard_app)


def test_haxaml_mcp_package_import_is_lazy(monkeypatch: pytest.MonkeyPatch):
    for module_name in ("haxaml.mcp", "haxaml.mcp.base"):
        sys.modules.pop(module_name, None)
    _block_mcp_imports(monkeypatch)

    module = importlib.import_module("haxaml.mcp")
    assert module.__name__ == "haxaml.mcp"
    with pytest.raises(ModuleNotFoundError):
        _ = module.mcp_app
