"""Loading complaint family field registries from `rules/fields/`.

Adding a field is a schema change: it happens in a registry file, never inside
a prompt. This loader is what makes that enforceable, because a finding naming
a field no registry declares is rejected downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import ValidationError

from spine.schemas.registry import ComplaintFamily, FamilyRegistry

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def rules_root(service: str) -> Path:
    """The rules directory belonging to `service`.

    The spine holds the engine, not the rules. Each service owns its own rule
    set, so the loader is told which service's rules to read rather than
    assuming Consult's.
    """
    return REPO_ROOT / "services" / service / "rules"


def fields_dir(service: str = "consult") -> Path:
    return rules_root(service) / "fields"


class RegistryLoadError(RuntimeError):
    """Raised when a registry file is absent, malformed, or self-contradictory."""


def load_family(family: ComplaintFamily, directory_override: Path | None = None) -> FamilyRegistry:
    """Load and validate one complaint family's field registry."""
    directory = directory_override if directory_override is not None else fields_dir()
    path = directory / f"{family.value}.yaml"
    if not path.is_file():
        raise RegistryLoadError(
            f"no field registry for complaint family {family.value!r}; create "
            f"{path} declaring its required and optional fields"
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise RegistryLoadError(f"{path} is not valid YAML: {error}") from error

    if not isinstance(raw, dict):
        raise RegistryLoadError(
            f"{path} must contain a mapping with keys 'family', 'required' and "
            f"optionally 'optional'; found {type(raw).__name__}"
        )
    declared = raw.get("family")
    if declared != family.value:
        raise RegistryLoadError(
            f"{path} declares family {declared!r} but is named for {family.value!r}; "
            f"rename the file or correct the 'family' key so the two agree"
        )
    try:
        return FamilyRegistry.model_validate(raw)
    except ValidationError as error:
        raise RegistryLoadError(f"{path} is not a valid field registry: {error}") from error


def load_all(directory_override: Path | None = None) -> dict[ComplaintFamily, FamilyRegistry]:
    """Load every complaint family that has a registry file.

    A family declared in the enum without a file is reported rather than
    skipped: silently having no required fields would make every record for
    that family report as sufficient.
    """
    directory = directory_override if directory_override is not None else fields_dir()
    if not directory.is_dir():
        raise RegistryLoadError(
            f"field registry directory {directory} does not exist; it holds one YAML "
            f"file per complaint family"
        )
    loaded: dict[ComplaintFamily, FamilyRegistry] = {}
    missing: list[str] = []
    for family in ComplaintFamily:
        if (directory / f"{family.value}.yaml").is_file():
            loaded[family] = load_family(family, directory)
        else:
            missing.append(family.value)
    if missing:
        raise RegistryLoadError(
            f"complaint families declared with no field registry: "
            f"{', '.join(sorted(missing))}. Without a registry a record for that "
            f"family has no required fields and reports as sufficient while empty. "
            f"Create rules/fields/<family>.yaml for each"
        )
    return loaded


def known_fields(registries: dict[ComplaintFamily, FamilyRegistry]) -> frozenset[str]:
    """Every field name any registry declares."""
    return frozenset(
        spec.field
        for registry in registries.values()
        for spec in (*registry.required, *registry.optional)
    )
