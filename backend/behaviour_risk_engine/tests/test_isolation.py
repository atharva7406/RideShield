"""No file in behaviour_risk_engine may import ml_incident_engine — the
crash-detection engine and the behaviour-risk engine are separate systems
per the Phase 4 spec."""

import ast
from pathlib import Path

import pytest

MODULE_FILES = [
    p for p in Path(__file__).resolve().parents[1].glob("*.py")
    if p.name != "__init__.py"
]


@pytest.mark.parametrize("module_path", MODULE_FILES, ids=lambda p: p.name)
def test_module_does_not_import_ml_incident_engine(module_path):
    with open(module_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert not any("ml_incident_engine" in m for m in imported_modules), (
        f"{module_path.name} imports ml_incident_engine — behaviour risk "
        f"engine must stay isolated from the crash-detection engine"
    )
