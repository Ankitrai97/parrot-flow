"""Explicit, whole-phrase spelling replacements, applied once after cleanup."""
import re


def parse_rules(source: str) -> dict[str, str]:
    if not isinstance(source, str) or len(source) > 12000:
        raise ValueError("Dictionary must be text, at most 12,000 characters")
    rules = {}
    for line in source.splitlines():
        if not line.strip():
            continue
        before, separator, after = line.partition("=>")
        before, after = before.strip(), after.strip()
        if not separator or not before or not after or max(len(before), len(after)) > 120:
            raise ValueError("Use one heard phrase => preferred spelling per line (120 characters each)")
        if before.lower() in rules:
            raise ValueError("Duplicate dictionary phrase: " + before)
        rules[before.lower()] = after
    if len(rules) > 100:
        raise ValueError("Dictionary supports up to 100 phrases")
    return rules


def apply_dictionary(text: str, source: str) -> str:
    rules = parse_rules(source)
    if not rules:
        return text
    pattern = r"(?<!\w)(?:" + "|".join(re.escape(k) for k in sorted(rules, key=len, reverse=True)) + r")(?!\w)"
    return re.sub(pattern, lambda match: rules.get(match.group().lower(), match.group()), text, flags=re.IGNORECASE)
