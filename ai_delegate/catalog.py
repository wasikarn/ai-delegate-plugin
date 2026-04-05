"""
catalog.py — Agent discovery for all installed Claude Code plugins.

Scans ~/.claude/plugins/*/agents/*.md and returns AgentMetadata list.
Enforces security requirements S1-S4:
  S1: Agent name validation (command injection prevention)
  S2: Plugin trust boundary (allowlist via trust file)
  S3: Path traversal prevention (canonical path resolution)
  S4: DoS protection (100 agent cap, 5s timeout, 4096 byte frontmatter limit)
"""
from __future__ import annotations

import json
import logging
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── S1: Name validation ─────────────────────────────────────────────────────

AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_agent_name(name: str) -> str:
    """Validate agent name is safe for subprocess use.

    Raises ValueError if name contains characters outside [a-zA-Z0-9_-].
    Never use shell=True when passing agent names to subprocess.
    """
    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid agent name {name!r}: must match [a-zA-Z0-9_-]+"
        )
    return name


# ─── S4: Limits ──────────────────────────────────────────────────────────────

MAX_AGENTS_PER_PLUGIN = 100
SCAN_TIMEOUT_SECONDS = 5
MAX_FRONTMATTER_SIZE_BYTES = 4096


# ─── Domain matching ─────────────────────────────────────────────────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "security":     ["security", "owasp", "vulnerabilit", "injection", "auth", "crypto"],
    "performance":  ["performance", "complexity", "database", "memory", "bottleneck", "query"],
    "architecture": ["architecture", "design", "pattern", "solid", "coupling", "cohesion"],
    "code-quality": ["quality", "maintainab", "readab", "code smell", "refactor", "clean"],
    "testing":      ["test", "coverage", "mock", "assertion", "spec"],
    "migration":    ["migration", "migrate", "breaking change", "api contract", "deprecat"],
    "database":     ["database", "sql", "migration", "schema", "index", "query"],
}


def _detect_domains(description: str) -> list[str]:
    """Return list of domain keys whose keywords appear in description (case-insensitive)."""
    desc_lower = description.lower()
    return [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(kw in desc_lower for kw in keywords)
    ]


def _extract_plugin_name(agent_path: Path) -> str:
    """Extract plugin name from path ~/.claude/plugins/<name>/agents/<file>.md"""
    try:
        # agent_path.parents[0] = agents/
        # agent_path.parents[1] = <plugin_name>/
        return agent_path.parents[1].name
    except IndexError:
        return "unknown"


# ─── Data model ──────────────────────────────────────────────────────────────

@dataclass
class AgentMetadata:
    name: str            # validated [a-zA-Z0-9_-]+
    description: str     # raw description from frontmatter
    source_plugin: str   # e.g. "ai-delegate", "devflow"
    model: str           # default model; "" if not specified
    tools: list[str]     # e.g. ["Read", "Grep"]
    path: Path           # resolved canonical path
    domains: list[str] = field(default_factory=list)  # from _detect_domains


# ─── Frontmatter parser ──────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text.

    Tries PyYAML first; falls back to a minimal line-by-line parser.
    Returns empty dict if no frontmatter block or if YAML is malformed.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    yaml_block = text[3:end].strip()

    try:
        import yaml  # type: ignore
        result = yaml.safe_load(yaml_block)
        return result if isinstance(result, dict) else {}
    except Exception:
        pass

    # Minimal fallback parser
    result: dict = {}
    lines = yaml_block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.strip().startswith("#"):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "|":
                block_lines = []
                i += 1
                while i < len(lines) and (lines[i].startswith("  ") or lines[i] == ""):
                    block_lines.append(lines[i].strip())
                    i += 1
                result[k] = " ".join(block_lines)
                continue
            elif v.startswith("[") and v.endswith("]"):
                try:
                    result[k] = json.loads(v)
                except Exception:
                    result[k] = []  # malformed list → safe empty default
            else:
                result[k] = v
        i += 1
    return result


# ─── Main catalog ─────────────────────────────────────────────────────────────

class AgentCatalog:
    """Discover agent definitions from all installed Claude Code plugins.

    Usage:
        catalog = AgentCatalog()
        agents = catalog.scan()                    # all trusted agents
        sec_agents = catalog.for_domains(["security"])
        catalog.invalidate()                       # clear in-memory cache
    """

    def __init__(
        self,
        plugins_dir: Path | None = None,
        trust_file: Path | None = None,
        trust_all: bool = False,
    ):
        self._plugins_dir = plugins_dir or Path.home() / ".claude" / "plugins"
        self._trust_all = trust_all
        self._trusted = self._load_trust(trust_file)
        self._cache: list[AgentMetadata] | None = None

    def _load_trust(self, trust_file: Path | None) -> set[str]:
        default = Path.home() / ".claude" / "ai-delegate-trust.json"
        path = trust_file or default
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return set(data.get("trusted_plugins", []))
            except Exception:
                logger.warning(
                    "Could not parse trust file %s — trusting only ai-delegate", path
                )
        return {"ai-delegate"}

    def _is_trusted(self, source_plugin: str) -> bool:
        return self._trust_all or source_plugin in self._trusted

    def _safe_agent_path(self, candidate: Path, plugin_dir: Path) -> Path | None:
        """Return canonical path only if it is under plugin_dir.

        Rejects symlinks that resolve outside the plugin_dir boundary (S3).
        """
        try:
            resolved = candidate.resolve()
        except Exception:
            return None
        plugin_dir_resolved = plugin_dir.resolve()
        if resolved.is_relative_to(plugin_dir_resolved):
            return resolved
        logger.warning("Path traversal rejected: %s → %s", candidate, resolved)
        return None

    def _parse_agent_file(
        self, md_file: Path, agents_dir: Path, source_plugin: str
    ) -> AgentMetadata | None:
        """Parse one agent .md file. Returns None if file should be skipped."""
        # S3: path traversal check
        safe_path = self._safe_agent_path(md_file, agents_dir)
        if safe_path is None:
            return None

        # S4: frontmatter size limit (check stat without following symlinks)
        try:
            stat = md_file.stat(follow_symlinks=False)
            if stat.st_size > MAX_FRONTMATTER_SIZE_BYTES:
                logger.warning("Skipping oversized agent file: %s", md_file)
                return None
            text = md_file.read_text(errors="replace")
        except Exception as e:
            logger.warning("Could not read agent file %s: %s", md_file, e)
            return None

        try:
            fm = _parse_frontmatter(text)
        except Exception as e:
            logger.warning("Malformed frontmatter in %s: %s", md_file, e)
            return None

        # Required: name (must be a plain string, not a YAML list/dict)
        name = fm.get("name", "")
        if not name or not isinstance(name, str):
            logger.warning("Missing or non-string name field in %s — skipping", md_file)
            return None

        # S1: name validation
        try:
            validate_agent_name(name)
        except ValueError:
            logger.warning("Skipping agent with unsafe name: %r in %s", name, md_file)
            return None

        description = fm.get("description", "")
        description = description.strip() if isinstance(description, str) else ""

        model = str(fm.get("model", "") or "")
        raw_tools = fm.get("tools", [])
        tools = raw_tools if isinstance(raw_tools, list) else []
        domains = _detect_domains(description)

        return AgentMetadata(
            name=name,
            description=description,
            source_plugin=source_plugin,
            model=model,
            tools=tools,
            path=safe_path,
            domains=domains,
        )

    def _scan_all(self) -> list[AgentMetadata]:
        """Scan all trusted plugin agent directories."""
        results: list[AgentMetadata] = []

        if not self._plugins_dir.exists():
            return results

        for plugin_dir in sorted(self._plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue

            source_plugin = plugin_dir.name

            # S2: trust boundary — skip silently (no warning to avoid info leak)
            if not self._is_trusted(source_plugin):
                continue

            agents_dir = plugin_dir / "agents"
            if not agents_dir.is_dir():
                continue

            count = 0
            for md_file in sorted(agents_dir.glob("*.md")):
                # S4: enforce per-plugin agent cap
                if count >= MAX_AGENTS_PER_PLUGIN:
                    logger.warning(
                        "Plugin %s has >%d agents — loading first %d only",
                        source_plugin,
                        MAX_AGENTS_PER_PLUGIN,
                        MAX_AGENTS_PER_PLUGIN,
                    )
                    break

                metadata = self._parse_agent_file(md_file, agents_dir, source_plugin)
                if metadata is not None:
                    results.append(metadata)
                    count += 1

        return results

    def _scan_with_timeout(self) -> list[AgentMetadata]:
        """Run _scan_all with S4 timeout protection.

        Uses SIGALRM on Unix; falls back to no-timeout on Windows/other.
        """
        if not hasattr(signal, "SIGALRM"):
            return self._scan_all()

        def _handler(signum: int, frame: object) -> None:  # noqa: ARG001
            raise TimeoutError(f"Catalog scan exceeded {SCAN_TIMEOUT_SECONDS} seconds")

        old_handler = signal.signal(signal.SIGALRM, _handler)  # type: ignore[attr-defined]
        signal.alarm(SCAN_TIMEOUT_SECONDS)  # type: ignore[attr-defined]
        try:
            return self._scan_all()
        finally:
            signal.alarm(0)  # type: ignore[attr-defined]
            signal.signal(signal.SIGALRM, old_handler)  # type: ignore[attr-defined]

    def scan(self) -> list[AgentMetadata]:
        """Scan all trusted plugins for agents. Returns cached result after first call."""
        if self._cache is not None:
            return self._cache
        self._cache = self._scan_with_timeout()
        return self._cache

    def for_domains(self, domains: list[str]) -> list[AgentMetadata]:
        """Return agents whose detected domains overlap with the given domains list."""
        all_agents = self.scan()
        domains_set = set(domains)
        return [a for a in all_agents if domains_set & set(a.domains)]

    def invalidate(self) -> None:
        """Clear in-memory cache (call if plugins installed during session)."""
        self._cache = None
