import json
import pytest
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class SBOMComponent(BaseModel):
    name: str
    version: str
    license: str

class SBOMReport(BaseModel):
    bom_format: str = "CycloneDX"
    spec_version: str = "1.5"
    components: List[SBOMComponent] = []

class ReleaseGateVerifier:
    @staticmethod
    def evaluate_gate(
        p0_tests_passed: bool,
        security_tests_passed: bool,
        static_analysis_clean: bool,
        container_scan_ok: bool,
        secret_scan_clean: bool
    ) -> bool:
        """Production release gate verification policy (Section 45)."""
        return all([
            p0_tests_passed,
            security_tests_passed,
            static_analysis_clean,
            container_scan_ok,
            secret_scan_clean
        ])

def test_release_gates_policy():
    # If all criteria are met, release gate passes
    assert ReleaseGateVerifier.evaluate_gate(
        p0_tests_passed=True,
        security_tests_passed=True,
        static_analysis_clean=True,
        container_scan_ok=True,
        secret_scan_clean=True
    ) is True

    # If P0 tests fail, release is blocked (Section 2 & 45 requirement)
    assert ReleaseGateVerifier.evaluate_gate(
        p0_tests_passed=False,
        security_tests_passed=True,
        static_analysis_clean=True,
        container_scan_ok=True,
        secret_scan_clean=True
    ) is False

    # If secret scans fail, release is blocked
    assert ReleaseGateVerifier.evaluate_gate(
        p0_tests_passed=True,
        security_tests_passed=True,
        static_analysis_clean=True,
        container_scan_ok=True,
        secret_scan_clean=False
    ) is False

def test_sbom_generation_format():
    # CycloneDX specification validation (Section 42 requirement)
    sbom = SBOMReport(
        components=[
            SBOMComponent(name="fastapi", version="0.111.0", license="MIT"),
            SBOMComponent(name="sqlalchemy", version="2.0.29", license="MIT")
        ]
    )
    serialized = sbom.model_dump()
    assert serialized["bom_format"] == "CycloneDX"
    assert len(serialized["components"]) == 2
    assert serialized["components"][0]["name"] == "fastapi"
