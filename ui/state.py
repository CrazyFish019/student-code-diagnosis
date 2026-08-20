"""Small helpers for Streamlit session-state lifecycle."""

from __future__ import annotations

from collections.abc import MutableMapping
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


_DEFAULTS: dict[str, Any] = {
    "task_status": TaskStatus.IDLE,
    "analysis_result": None,
    "task_error": None,
    "upload_info": (),
    "last_history_task_id": None,
    "ai_diagnosis_running": False,
    "ai_diagnosis_requested": False,
    "ai_diagnosis_notice": None,
}


def initialize_session_state(state: MutableMapping[str, Any]) -> None:
    for key, value in _DEFAULTS.items():
        if key not in state:
            state[key] = value


def mark_task_running(
    state: MutableMapping[str, Any], *, upload_info: tuple[str, ...]
) -> None:
    state["task_status"] = TaskStatus.RUNNING
    state["task_error"] = None
    state["upload_info"] = tuple(upload_info)


def mark_task_completed(state: MutableMapping[str, Any], result: object) -> None:
    state["task_status"] = TaskStatus.COMPLETED
    state["analysis_result"] = result
    state["task_error"] = None


def mark_task_failed(state: MutableMapping[str, Any], message: str) -> None:
    state["task_status"] = TaskStatus.FAILED
    state["task_error"] = message


def clear_ai_diagnosis(state: MutableMapping[str, Any]) -> None:
    """Remove a report when its source problem or submission changes."""

    future = state.pop("ai_diagnosis_future", None)
    cancel = getattr(future, "cancel", None)
    if callable(cancel):
        cancel()
    state["ai_code_diagnosis"] = None
    state["ai_diagnosis_has_oj_evidence"] = False
    state["selected_oj_case_ids"] = ()
    state["active_oj_case_index"] = None
    state["send_selected_oj_cases"] = False
    state["ai_diagnosis_running"] = False
    state["ai_diagnosis_requested"] = False
    state["ai_diagnosis_notice"] = None
    state.pop("keep_oj_testcase_details_open", None)
    state.pop("local_selected_case_execution", None)
    for key in tuple(state.keys()):
        if isinstance(key, str) and key.startswith("oj_case_selected_"):
            del state[key]


def request_ai_diagnosis(state: MutableMapping[str, Any]) -> bool:
    """Queue one diagnosis and lock the button before Streamlit reruns."""

    if state.get("ai_diagnosis_running"):
        return False
    state["ai_diagnosis_running"] = True
    state["ai_diagnosis_requested"] = True
    state["ai_diagnosis_notice"] = None
    state["ai_code_diagnosis"] = None
    return True


def consume_ai_diagnosis_request(state: MutableMapping[str, Any]) -> bool:
    requested = bool(state.get("ai_diagnosis_requested"))
    state["ai_diagnosis_requested"] = False
    return requested


def finish_ai_diagnosis(
    state: MutableMapping[str, Any], *, level: str, message: str
) -> None:
    if level not in {"success", "error"}:
        raise ValueError("level must be success or error")
    state["ai_diagnosis_running"] = False
    state["ai_diagnosis_requested"] = False
    state["ai_diagnosis_notice"] = (level, message)


def pop_ai_diagnosis_notice(
    state: MutableMapping[str, Any],
) -> tuple[str, str] | None:
    notice = state.pop("ai_diagnosis_notice", None)
    if (
        isinstance(notice, tuple)
        and len(notice) == 2
        and notice[0] in {"success", "error"}
        and isinstance(notice[1], str)
    ):
        return notice
    return None


def keep_testcase_details_open(state: MutableMapping[str, Any]) -> None:
    """Keep the testcase expander open for the rerun caused by a card action."""

    state["keep_oj_testcase_details_open"] = True


def consume_testcase_details_open(state: MutableMapping[str, Any]) -> bool:
    return bool(state.pop("keep_oj_testcase_details_open", False))
