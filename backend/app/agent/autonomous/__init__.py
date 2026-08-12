"""
Canonical Autonomous Coding, Verification, and Self-Repair Package.
"""

from .change_validator import ChangeSetValidator, ValidationFinding, ValidationResult
from .execution_planner import ExecutionPlan, ExecutionPlanner, PlanStep, StepStatus
from .failure_analyzer import FailureAnalyzer, FailureCategory, VerificationFailure
from .policy_engine import CommandRiskLevel, ExecutionMode, PolicyEngine
from .reviewer import AgentReviewer, ReviewFinding, ReviewResult
from .self_repair import RepairRoundRecord, SelfRepairLoop
from .session_recovery import SessionRecoveryManager, SessionStateSnapshot
from .task_contract import AgentTaskContract, TaskContractGenerator
from .verification_engine import VerificationEngine, VerificationProfile, VerificationResult

__all__ = [
    "AgentTaskContract",
    "TaskContractGenerator",
    "ExecutionPlan",
    "ExecutionPlanner",
    "PlanStep",
    "StepStatus",
    "VerificationEngine",
    "VerificationProfile",
    "VerificationResult",
    "FailureAnalyzer",
    "FailureCategory",
    "VerificationFailure",
    "SelfRepairLoop",
    "RepairRoundRecord",
    "ChangeSetValidator",
    "ValidationFinding",
    "ValidationResult",
    "AgentReviewer",
    "ReviewFinding",
    "ReviewResult",
    "PolicyEngine",
    "ExecutionMode",
    "CommandRiskLevel",
    "SessionRecoveryManager",
    "SessionStateSnapshot",
]
