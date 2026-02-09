"""
Phase 4 – Duplicate & Validation Logic for Order Upload
======================================================

Pure in-memory duplicate detection for extracted order lines.

Rules (from spec):
- Same S.N          → skip
- Same normalized PART NAME → skip
- Same PART NUMBER → skip
- Same model, different colour → allowed

Clarifications applied here:
- \"Same S.N\" is treated as **same S.N + same normalized PART NAME**
  so that split multi-colour lines with the same S.N but different
  part names (e.g. \"Duet Grey\" vs \"Duet White\") are allowed.
- Normalized PART NAME uses lowercase and collapsed whitespace; colours
  remain part of the name so different colours are different names.

This module:
- Does NOT import config or touch any production logic.
- Can be used from dev flows or future services.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Set
import re


@dataclass
class DedupeLine:
    sn: int
    part_name: str
    qty: int
    source_page: int
    part_number: str | None = None  # optional, may be set after price matching

    def to_dict(self) -> Dict:
        return asdict(self)


def _normalize_name(name: str) -> str:
    """Normalize part name for duplicate comparison."""
    s = (name or "").lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def dedupe_lines(lines: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Apply duplicate rules to intermediate extracted lines.

    Args:
        lines: List of dicts with keys:
            - sn (int)
            - part_name (str)
            - qty (int)
            - source_page (int)
            - part_number (optional str)

    Returns:
        (kept, skipped) where:
        - kept: list of line dicts that passed dedupe.
        - skipped: list of line dicts with an extra key 'dup_reasons'
          describing why they were skipped.
    """
    kept: List[Dict] = []
    skipped: List[Dict] = []

    seen_names: Set[str] = set()
    seen_part_numbers: Set[str] = set()
    sn_to_names: Dict[int, Set[str]] = {}

    for raw in lines:
        sn = int(raw.get("sn", 0))
        part_name = str(raw.get("part_name", "")).strip()
        part_number = (raw.get("part_number") or "").strip()

        norm_name = _normalize_name(part_name)
        norm_pn = part_number.upper()

        reasons: List[str] = []

        # Same S.N + same normalized name -> duplicate of that serial line
        existing_for_sn = sn_to_names.get(sn, set())
        if norm_name and norm_name in existing_for_sn:
            reasons.append("DUP_SN")

        # Same normalized PART NAME anywhere in the order
        if norm_name and norm_name in seen_names:
            reasons.append("DUP_PART_NAME")

        # Same PART NUMBER anywhere in the order
        if norm_pn and norm_pn in seen_part_numbers:
            reasons.append("DUP_PART_NUMBER")

        if reasons:
            dup = dict(raw)
            dup["dup_reasons"] = reasons
            skipped.append(dup)
            continue

        # Keep this line and update tracking sets
        kept.append(raw)
        if norm_name:
            seen_names.add(norm_name)
            sn_to_names.setdefault(sn, set()).add(norm_name)
        if norm_pn:
            seen_part_numbers.add(norm_pn)

    return kept, skipped


