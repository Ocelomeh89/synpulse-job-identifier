from __future__ import annotations
import re


def find_skill_matches(description: str, pattern: str) -> list[str]:
    rx = re.compile(pattern, re.IGNORECASE)
    canonical: set[str] = set()
    for m in rx.finditer(description):
        token = m.group(1) if m.groups() else m.group(0)
        for opt in re.findall(r"[A-Za-z]+", pattern):
            if opt.lower() == token.lower():
                canonical.add(opt)
                break
    return sorted(canonical)


def build_excerpt(description: str, skill_matches: list[str], width: int = 200) -> str:
    if not description:
        return ""
    if not skill_matches:
        return description[:width]
    rx = re.compile(
        r"\b(" + "|".join(re.escape(s) for s in skill_matches) + r")\b",
        re.IGNORECASE,
    )
    m = rx.search(description)
    if not m:
        return description[:width]
    start = max(0, m.start() - width // 2)
    end = min(len(description), start + width)
    snippet = description[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(description) else ""
    return f"{prefix}{snippet}{suffix}"
