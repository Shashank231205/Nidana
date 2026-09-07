"""Verify the architectural boundaries hold.

Run in CI. These are the rules `docs/ARCHITECTURE.md` states, and they are the
kind that erode one convenient import at a time — each individually reasonable,
collectively the reason a five-service platform becomes one tangled service.

Four rules:

1. Nothing in `spine/` imports from a service. The spine is the foundation; it
   does not know who stands on it.
2. No service imports another service. Shared behaviour goes in the spine or is
   duplicated deliberately.
3. `services/*/clinical/` imports no inference client. Anything where being
   wrong causes physical harm is a rule, not a generation.
4. Forensics imports no other service's shapes. It is evidentially isolated,
   and that is enforced rather than trusted.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SPINE: Final[Path] = REPO_ROOT / "spine"
SERVICES: Final[Path] = REPO_ROOT / "services"

INFERENCE_MODULES: Final[frozenset[str]] = frozenset(
    {
        "spine.inference.adapter",
        "spine.inference.ollama",
        "spine.inference.config",
    }
)


@dataclass(frozen=True)
class Violation:
    rule: str
    path: Path
    detail: str

    def __str__(self) -> str:
        relative = self.path.relative_to(REPO_ROOT)
        return f"  {relative}: {self.detail}"


def imported_modules(path: Path) -> tuple[str, ...]:
    """Every module a file imports, as dotted names.

    Parsed rather than grepped, so a module named in a docstring or a comment
    is not mistaken for an import.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        raise SystemExit(f"{path} does not parse: {error}") from error
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def python_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def service_of(path: Path) -> str | None:
    try:
        relative = path.relative_to(SERVICES)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def check_spine_imports_no_service() -> list[Violation]:
    violations: list[Violation] = []
    for path in python_files(SPINE):
        for module in imported_modules(path):
            if module.startswith("services."):
                violations.append(
                    Violation(
                        rule="spine imports a service",
                        path=path,
                        detail=(
                            f"imports {module}. The spine is the foundation and does "
                            f"not know who stands on it; move the shape into "
                            f"spine/schemas/ if both need it"
                        ),
                    )
                )
    return violations


def check_no_service_imports_another() -> list[Violation]:
    violations: list[Violation] = []
    for path in python_files(SERVICES):
        owner = service_of(path)
        if owner is None:
            continue
        for module in imported_modules(path):
            if not module.startswith("services."):
                continue
            parts = module.split(".")
            other = parts[1] if len(parts) > 1 else None
            if other and other != owner:
                violations.append(
                    Violation(
                        rule="a service imports another service",
                        path=path,
                        detail=(
                            f"imports {module}. Shared behaviour goes in the spine, or "
                            f"is duplicated deliberately"
                        ),
                    )
                )
    return violations


def check_clinical_layers_have_no_inference() -> list[Violation]:
    violations: list[Violation] = []
    for path in python_files(SERVICES):
        if "clinical" not in path.parts:
            continue
        for module in imported_modules(path):
            if module in INFERENCE_MODULES:
                violations.append(
                    Violation(
                        rule="a clinical layer imports an inference client",
                        path=path,
                        detail=(
                            f"imports {module}. Red flags, thresholds, routing and "
                            f"interaction checks are deterministic; if this package "
                            f"needs a model, the design is wrong"
                        ),
                    )
                )
    return violations


def check_forensics_is_isolated() -> list[Violation]:
    """Forensics reads nothing from another service.

    Stronger than the general rule: a medico-legal record must be defensible as
    an independent examination, and an import is the first step toward reading
    shared data.
    """
    violations: list[Violation] = []
    forensics = SERVICES / "forensics"
    if not forensics.is_dir():
        return violations
    for path in python_files(forensics):
        for module in imported_modules(path):
            if module.startswith("services.") and not module.startswith("services.forensics"):
                violations.append(
                    Violation(
                        rule="forensics imports another service",
                        path=path,
                        detail=(
                            f"imports {module}. Forensics is evidentially isolated; "
                            f"contamination from another source is an attack surface "
                            f"in cross-examination"
                        ),
                    )
                )
    return violations


def main() -> int:
    checks = (
        check_spine_imports_no_service,
        check_no_service_imports_another,
        check_clinical_layers_have_no_inference,
        check_forensics_is_isolated,
    )
    violations = [violation for check in checks for violation in check()]
    if not violations:
        print(
            f"OK: {len(python_files(SPINE))} spine and {len(python_files(SERVICES))} "
            f"service files; every architectural boundary holds."
        )
        return 0

    by_rule: dict[str, list[Violation]] = {}
    for violation in violations:
        by_rule.setdefault(violation.rule, []).append(violation)
    for rule, found in by_rule.items():
        print(f"{rule.upper()} ({len(found)}):")
        for violation in found:
            print(violation)
    print(f"\n{len(violations)} boundary violation(s). See docs/ARCHITECTURE.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
