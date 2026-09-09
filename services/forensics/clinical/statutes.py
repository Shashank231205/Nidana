"""Reading an archived medico-legal citation after the statute was renumbered.

The BNS replaced the IPC on 1 July 2024 and renumbered comprehensively: 511
sections became 358, and none kept its number. A report written in June cites
IPC 320 and one written in July cites BNS 116 for the same provision, and an
archive holds both.

What this module does is translate a number. What it does not do — and the
distinction is the whole point of the module — is decide which section applies
to an injury. That is the legal classification question the service README
lists as blocked, it needs a lawyer, and nothing here narrows it. A function
that returned "this laceration is grievous hurt" would be practising law from
a lookup table.

The correspondence table this reads is transcribed from the Bureau of Police
Research and Development's published table, which says of itself that it is a
reference document carrying no legal force. That caveat travels with every
answer this module gives: see `Correspondence.legally_reviewed`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml

STATUTE_MAP: Final[Path] = (
    Path(__file__).resolve().parents[1] / "rules" / "statutes" / "ipc_bns_map.yaml"
)

BNS_COMMENCEMENT: Final[str] = "2024-07-01"
"""The day the BNS replaced the IPC.

A report dated before this cites IPC numbering and one dated after cites BNS,
which is what makes a stored citation ambiguous without its date.
"""


class StatuteMapError(RuntimeError):
    """Raised when the correspondence table is missing or malformed."""


@dataclass(frozen=True)
class Correspondence:
    """One provision, under both numberings.

    `legally_reviewed` is always False and is carried on every result rather
    than documented once. A caller rendering this into a report needs the
    caveat at the point of use, not in a file it may never read.
    """

    ipc: str
    bns: str | None
    title: str
    changed: bool = False
    note: str | None = None
    repealed: bool = False
    legally_reviewed: bool = False

    @property
    def needs_legal_check(self) -> bool:
        """Whether this row carries more than a renumbering.

        A section the table marks as changed has different wording, not just a
        different number, so a clinical input that satisfied the IPC test may
        not satisfy the BNS one. Repealed sections have no counterpart at all.
        """
        return self.changed or self.repealed


class StatuteMap:
    """The IPC-to-BNS correspondence, in both directions.

    The reverse direction is deliberately a tuple rather than a single result:
    the BNS merged provisions, so one BNS subsection can correspond to more
    than one IPC section. Returning the first would silently drop the other.
    """

    def __init__(self, entries: tuple[Correspondence, ...]) -> None:
        self._entries = entries
        self._by_ipc: dict[str, Correspondence] = {}
        for entry in entries:
            key = _normalise(entry.ipc)
            if key in self._by_ipc:
                raise StatuteMapError(
                    f"IPC section {entry.ipc} appears twice in the correspondence table; "
                    f"one row would be silently ignored"
                )
            self._by_ipc[key] = entry
        self._by_bns: dict[str, list[Correspondence]] = {}
        for entry in entries:
            if entry.bns is not None:
                self._by_bns.setdefault(_normalise(entry.bns), []).append(entry)

    def __len__(self) -> int:
        return len(self._entries)

    def from_ipc(self, section: str) -> Correspondence | None:
        """What an IPC section is called under the BNS, if anything."""
        return self._by_ipc.get(_normalise(section))

    def from_bns(self, section: str) -> tuple[Correspondence, ...]:
        """Which IPC sections a BNS section corresponds to.

        More than one where the BNS merged provisions — BNS 70(2) covers both
        IPC 376DA and 376DB. A caller resolving an archived citation needs to
        see that the mapping is not one-to-one.
        """
        return tuple(self._by_bns.get(_normalise(section), ()))

    @property
    def repealed(self) -> tuple[Correspondence, ...]:
        """Sections the BNS deleted with no counterpart."""
        return tuple(entry for entry in self._entries if entry.repealed)


def _normalise(section: str) -> str:
    """Compare section numbers regardless of spacing and case.

    '376 DA', '376da' and '376DA' are the same section, and a report typed by
    hand contains all three.
    """
    return "".join(section.split()).upper()


def load_statute_map(path: Path | None = None) -> StatuteMap:
    """Read the correspondence table.

    Raises rather than returning an empty map. A silently empty table would
    make every archived citation look unrecognised, which reads as "this
    section does not exist" — the opposite of the truth.
    """
    source = path or STATUTE_MAP
    if not source.is_file():
        raise StatuteMapError(
            f"no statute correspondence table at {source}. It ships with the service; "
            f"a missing file means the installation is incomplete"
        )
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise StatuteMapError(f"{source} is not valid YAML: {error}") from error

    if not isinstance(document, dict):
        raise StatuteMapError(f"{source} does not contain a mapping")

    entries: list[Correspondence] = []
    for row in document.get("sections") or ():
        entries.append(
            Correspondence(
                ipc=str(row["ipc"]),
                bns=str(row["bns"]),
                title=str(row["title"]),
                changed=bool(row.get("changed", False)),
                note=row.get("note"),
            )
        )
    for row in document.get("repealed") or ():
        entries.append(
            Correspondence(
                ipc=str(row["ipc"]),
                bns=None,
                title=str(row["title"]),
                repealed=True,
                note=row.get("note"),
            )
        )
    if not entries:
        raise StatuteMapError(f"{source} lists no sections")
    return StatuteMap(tuple(entries))


@lru_cache(maxsize=1)
def statute_map() -> StatuteMap:
    """The correspondence table, read once.

    Cached because it is a static document read on every archived report, and
    parsing YAML per citation would be a measurable cost for a file that
    changes when Parliament acts.
    """
    return load_statute_map()
