"""Deterministic YAML writer for interpretations and eval cases (R9.2).

Dependency-free: the oss profile does not require PyYAML. This writer emits the
restricted YAML subset our register uses (the same subset ``aca.register.yamlio``
reads), so a round-trip (write then validate) is stable. Output is deterministic
(sorted where order is not meaningful) so a recorded interpretation produces the
same bytes on every run, which keeps review diffs clean.
"""

from __future__ import annotations

from typing import Any


def _emit_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    # Quote when the scalar could otherwise be misread (leading/trailing space,
    # contains a colon+space, or looks like a different type).
    needs_quote = (
        text != text.strip()
        or ": " in text
        or text in ("null", "true", "false", "yes", "no", "~", "")
        or text.lstrip("-").isdigit()
    )
    if needs_quote:
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def dump_mapping(data: dict, field_order: list[str] | None = None) -> str:
    """Serialise a flat/nested mapping. Lists become block sequences.

    ``field_order`` fixes the key order for the top-level mapping; any remaining
    keys follow in sorted order. Nested dict values are not used by our records,
    so only scalars and lists of scalars/maps are supported.
    """
    lines: list[str] = []
    keys = list(field_order or [])
    for k in sorted(data):
        if k not in keys:
            keys.append(k)

    for key in keys:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
                continue
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    sub = dump_mapping(item).splitlines()
                    if sub:
                        lines.append(f"  - {sub[0]}")
                        for extra in sub[1:]:
                            lines.append(f"    {extra}")
                else:
                    lines.append(f"  - {_emit_scalar(item)}")
        else:
            lines.append(f"{key}: {_emit_scalar(value)}")
    return "\n".join(lines) + "\n"
