"""Fail-closed safety-gate checks for the local-only Docker sandbox."""

from sandbox.safety_checks.checks import run_complete_safety_suite

__all__ = ["run_complete_safety_suite"]
