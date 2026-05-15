"""Narrow merge helpers for setup-managed MCP config fragments."""

from __future__ import annotations

from dataclasses import dataclass
import json
import tomllib
from typing import Any

import tomlkit


JSON_KEY_PATH = "mcpServers.haxaml"
TOML_KEY_PATH = "mcp_servers.haxaml"


@dataclass(frozen=True)
class ConfigMergePlan:
    """Plan or result for a setup-managed config merge."""

    action: str
    merge_status: str
    reason: str
    preview: str
    content: str | None
    fragment: str


def managed_config_key_path(config_format: str) -> str:
    return TOML_KEY_PATH if config_format == "toml" else JSON_KEY_PATH


def _json_fragment_from_payload(payload: dict[str, Any]) -> str:
    return json.dumps({"mcpServers": {"haxaml": payload}}, indent=2, sort_keys=True) + "\n"


def _render_toml_fragment(payload: dict[str, Any]) -> str:
    doc = tomlkit.document()
    mcp_servers = tomlkit.table(is_super_table=True)
    haxaml = tomlkit.table()
    for key, value in payload.items():
        haxaml[key] = value
    mcp_servers["haxaml"] = haxaml
    doc["mcp_servers"] = mcp_servers
    return doc.as_string()


def _toml_fragment_from_payload(payload: dict[str, Any]) -> str:
    return _render_toml_fragment(payload)


def _to_builtin(value: Any) -> Any:
    if hasattr(value, "unwrap"):
        return value.unwrap()
    if isinstance(value, dict):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    return value


def _json_payload_from_content(content: str) -> dict[str, Any]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("JSON config must be a top-level object.")
    root = parsed.get("mcpServers")
    if not isinstance(root, dict):
        raise ValueError("JSON config must define `mcpServers.haxaml`.")
    payload = root.get("haxaml")
    if not isinstance(payload, dict):
        raise ValueError("JSON config must define `mcpServers.haxaml` as an object.")
    return payload


def _toml_payload_from_content(content: str) -> dict[str, Any]:
    parsed = tomllib.loads(content)
    mcp_servers = parsed.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        raise ValueError("TOML config must define `[mcp_servers.haxaml]`.")
    payload = mcp_servers.get("haxaml")
    if not isinstance(payload, dict):
        raise ValueError("TOML config must define `[mcp_servers.haxaml]`.")
    return payload


def extract_managed_config_fragment(content: str, config_format: str) -> str | None:
    """Return the managed config fragment from a merged config file."""
    try:
        if config_format == "json":
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return None
            mcp_servers = parsed.get("mcpServers")
            if not isinstance(mcp_servers, dict):
                return None
            payload = mcp_servers.get("haxaml")
            if not isinstance(payload, dict):
                return None
            return _json_fragment_from_payload(payload)

        doc = tomlkit.parse(content)
        mcp_servers = doc.get("mcp_servers")
        if mcp_servers is None:
            return None
        try:
            payload = mcp_servers.get("haxaml")
        except Exception:
            return None
        if payload is None:
            return None
        built = _to_builtin(payload)
        if not isinstance(built, dict):
            return None
        return _toml_fragment_from_payload(built)
    except Exception:
        return None


def plan_managed_config_write(*, existing_text: str | None, config_format: str, desired_content: str) -> ConfigMergePlan:
    """Plan a narrow merge of the Haxaml-owned MCP subtree."""
    try:
        if config_format == "json":
            desired_payload = _json_payload_from_content(desired_content)
            desired_fragment = _json_fragment_from_payload(desired_payload)
            if existing_text is None:
                return ConfigMergePlan(
                    action="create",
                    merge_status="created",
                    reason="Create a new JSON MCP config with the Haxaml server entry.",
                    preview=desired_fragment,
                    content=json.dumps({"mcpServers": {"haxaml": desired_payload}}, indent=2) + "\n",
                    fragment=desired_fragment,
                )

            parsed = json.loads(existing_text)
            if not isinstance(parsed, dict):
                raise ValueError("existing JSON config is not an object")
            mcp_servers = parsed.get("mcpServers")
            if mcp_servers is None:
                parsed["mcpServers"] = {"haxaml": desired_payload}
            elif isinstance(mcp_servers, dict):
                if mcp_servers.get("haxaml") == desired_payload:
                    return ConfigMergePlan(
                        action="skip",
                        merge_status="unchanged",
                        reason="The Haxaml JSON MCP entry already matches the planned config.",
                        preview=desired_fragment,
                        content=None,
                        fragment=desired_fragment,
                    )
                mcp_servers["haxaml"] = desired_payload
            else:
                raise ValueError("existing `mcpServers` key is not an object")
            return ConfigMergePlan(
                action="merge",
                merge_status="merged",
                reason="Merge the Haxaml server entry into the existing JSON MCP config.",
                preview=desired_fragment,
                content=json.dumps(parsed, indent=2) + "\n",
                fragment=desired_fragment,
            )

        desired_payload = _toml_payload_from_content(desired_content)
        desired_fragment = _toml_fragment_from_payload(desired_payload)
        if existing_text is None:
            return ConfigMergePlan(
                action="create",
                merge_status="created",
                reason="Create a new TOML MCP config with the Haxaml server table.",
                preview=desired_fragment,
                content=desired_fragment,
                fragment=desired_fragment,
            )

        doc = tomlkit.parse(existing_text)
        mcp_servers = doc.get("mcp_servers")
        if mcp_servers is None:
            mcp_servers = tomlkit.table(is_super_table=True)
            doc["mcp_servers"] = mcp_servers

        if not hasattr(mcp_servers, "__setitem__"):
            raise ValueError("existing `mcp_servers` key is not a TOML table")

        current_fragment = extract_managed_config_fragment(existing_text, "toml")
        if current_fragment is not None and tomllib.loads(current_fragment) == tomllib.loads(desired_fragment):
            return ConfigMergePlan(
                action="skip",
                merge_status="unchanged",
                reason="The Haxaml TOML MCP table already matches the planned config.",
                preview=desired_fragment,
                content=None,
                fragment=desired_fragment,
            )

        haxaml = tomlkit.table()
        for key, value in desired_payload.items():
            haxaml[key] = value
        mcp_servers["haxaml"] = haxaml
        return ConfigMergePlan(
            action="merge",
            merge_status="merged",
            reason="Merge the Haxaml server table into the existing TOML MCP config.",
            preview=desired_fragment,
            content=doc.as_string(),
            fragment=desired_fragment,
        )
    except Exception as exc:
        preview = desired_content if desired_content.endswith("\n") else desired_content + "\n"
        return ConfigMergePlan(
            action="manual",
            merge_status="conflict",
            reason=(
                f"Could not safely merge the Haxaml {config_format.upper()} MCP entry: {exc}. "
                f"Add `{managed_config_key_path(config_format)}` manually."
            ),
            preview=preview,
            content=None,
            fragment=preview,
        )
