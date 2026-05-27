import json
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative_path: str) -> dict[str, Any]:
    raw_data: object = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(raw_data, dict), relative_path
    return cast(dict[str, Any], raw_data)


def parse_skill_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    parts = text.split("---", 2)
    assert len(parts) == 3, path
    raw_data: object = yaml.safe_load(parts[1])
    assert isinstance(raw_data, dict), path
    return cast(dict[str, Any], raw_data)


def assert_non_empty_string(value: object, label: str) -> None:
    assert isinstance(value, str), label
    assert value.strip(), label


def assert_relative_child_path(base: Path, raw_path: object, label: str) -> Path:
    assert isinstance(raw_path, str), label
    assert raw_path.strip(), label
    pure_path = PurePosixPath(raw_path)
    assert not pure_path.is_absolute(), label
    assert ".." not in pure_path.parts, label

    relative = raw_path[2:] if raw_path.startswith("./") else raw_path
    resolved = (base / relative).resolve()
    base_resolved = base.resolve()
    assert resolved == base_resolved or base_resolved in resolved.parents, label
    assert resolved.exists(), label
    return resolved


def test_agent_skill_front_matter_and_index_cover_local_skill_roots() -> None:
    skill_root = ROOT / ".agents" / "skills"
    index = (skill_root / "SKILL_INDEX.md").read_text(encoding="utf-8")
    skill_dirs = sorted(path for path in skill_root.iterdir() if path.is_dir())
    seen_skill_names: set[str] = set()

    assert skill_dirs

    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        assert skill_file.is_file(), skill_dir
        metadata = parse_skill_front_matter(skill_file)
        skill_name = metadata.get("name")
        assert_non_empty_string(skill_name, f"{skill_file}: name")
        assert skill_name not in seen_skill_names, f"duplicate skill name: {skill_name}"
        seen_skill_names.add(cast(str, skill_name))
        assert_non_empty_string(metadata.get("description"), f"{skill_file}: description")
        assert index.count(f"`{skill_dir.name}`") == 1, skill_dir.name


def test_plugin_registry_and_manifest_paths_are_structural() -> None:
    marketplace = read_json(".agents/plugins/marketplace.json")
    plugins = marketplace.get("plugins")
    assert isinstance(plugins, list)

    if not plugins:
        return

    seen_plugin_names: set[str] = set()

    for plugin_entry in plugins:
        assert isinstance(plugin_entry, dict)
        plugin_name = plugin_entry.get("name")
        assert_non_empty_string(plugin_name, "plugin name")
        assert plugin_name not in seen_plugin_names
        seen_plugin_names.add(cast(str, plugin_name))

        source = plugin_entry.get("source")
        assert isinstance(source, dict), plugin_name
        raw_plugin_path = source.get("path")
        assert isinstance(raw_plugin_path, str), f"{plugin_name}: source.path"
        assert raw_plugin_path.strip(), f"{plugin_name}: source.path"
        pure_plugin_path = PurePosixPath(raw_plugin_path)
        assert not pure_plugin_path.is_absolute(), f"{plugin_name}: source.path"
        assert ".." not in pure_plugin_path.parts, f"{plugin_name}: source.path"

        relative_plugin_path = (
            raw_plugin_path[2:] if raw_plugin_path.startswith("./") else raw_plugin_path
        )
        plugin_dir = (ROOT / relative_plugin_path).resolve()
        assert ROOT.resolve() / "plugins" in plugin_dir.parents

        if not plugin_dir.exists():
            continue

        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        mcp_path = plugin_dir / ".mcp.json"
        assert manifest_path.is_file(), manifest_path
        assert mcp_path.is_file(), mcp_path

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert isinstance(manifest, dict), manifest_path
        assert manifest.get("name") == plugin_name
        assert_non_empty_string(manifest.get("version"), f"{manifest_path}: version")
        assert_non_empty_string(manifest.get("description"), f"{manifest_path}: description")

        assert_relative_child_path(plugin_dir, manifest.get("skills"), f"{plugin_name}: skills")
        assert_relative_child_path(
            plugin_dir,
            manifest.get("mcpServers"),
            f"{plugin_name}: mcpServers",
        )

        interface = manifest.get("interface")
        assert isinstance(interface, dict), f"{manifest_path}: interface"
        assert_relative_child_path(
            plugin_dir,
            interface.get("composerIcon"),
            f"{plugin_name}: interface.composerIcon",
        )
        assert_relative_child_path(
            plugin_dir,
            interface.get("logo"),
            f"{plugin_name}: interface.logo",
        )

        mcp_config = json.loads(mcp_path.read_text(encoding="utf-8"))
        assert isinstance(mcp_config, dict), mcp_path
        mcp_servers = mcp_config.get("mcpServers")
        assert isinstance(mcp_servers, dict), mcp_path
        assert mcp_servers
        for server_name, server_config in mcp_servers.items():
            assert_non_empty_string(server_name, f"{mcp_path}: server name")
            assert isinstance(server_config, dict), server_name
            assert_non_empty_string(server_config.get("command"), f"{server_name}: command")
            args = server_config.get("args")
            assert isinstance(args, list), f"{server_name}: args"
            assert all(isinstance(arg, str) and arg for arg in args), f"{server_name}: args"


def test_default_plugin_registry_does_not_advertise_missing_payloads() -> None:
    marketplace = read_json(".agents/plugins/marketplace.json")

    assert marketplace.get("plugins") == []


def test_plugin_skill_front_matter_is_parseable() -> None:
    plugin_skill_files = sorted((ROOT / "plugins").glob("*/skills/*/SKILL.md"))

    seen_plugin_skill_names: set[str] = set()

    for skill_file in plugin_skill_files:
        metadata = parse_skill_front_matter(skill_file)
        skill_name = metadata.get("name")
        assert_non_empty_string(skill_name, f"{skill_file}: name")
        assert_non_empty_string(metadata.get("description"), f"{skill_file}: description")
        assert skill_name not in seen_plugin_skill_names
        seen_plugin_skill_names.add(cast(str, skill_name))
