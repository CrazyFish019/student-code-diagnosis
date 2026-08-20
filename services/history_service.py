from __future__ import annotations

import json
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from models.history import (
    DiagnosisRecord,
    ExplanationRecord,
    HistoricalStudent,
    HistoricalTask,
    SubmissionRecord,
    TaskRecord,
)
from models.workbench import ClassAnalysisResult, StudentAnalysis, StudentSource
from repositories import (
    DiagnosisRepository,
    ExplanationRepository,
    SQLiteDatabase,
    SubmissionRepository,
    TaskRepository,
)


class HistoryServiceError(RuntimeError):
    """Raised when historical data cannot be stored or loaded reliably."""


class HistoryService:
    """Coordinates transactional metadata storage and task-owned result files."""

    def __init__(self, database: SQLiteDatabase | None = None) -> None:
        self._database = database or SQLiteDatabase()
        try:
            self._database.initialize()
        except Exception as exc:
            raise HistoryServiceError("历史记录初始化失败。") from exc

    @property
    def database_path(self) -> Path:
        return self._database.path

    def save_analysis_result(
        self,
        *,
        title: str,
        result: ClassAnalysisResult,
        sources: Sequence[StudentSource],
    ) -> TaskRecord:
        title = self._required_text(title, "title")
        source_by_name = {source.student_name: source for source in sources}
        missing = [
            analysis.student_name
            for analysis in result.students
            if analysis.student_name not in source_by_name
        ]
        if missing:
            raise HistoryServiceError(
                f"缺少学生源码，无法保存历史记录：{'、'.join(missing)}"
            )

        task_id = self._new_task_id()
        task = TaskRecord(
            id=task_id,
            title=title,
            problem_id=result.problem_id,
            created_at=datetime.now(timezone.utc),
            student_count=len(result.students),
        )
        tasks_root = self._database.tasks_root
        tasks_root.mkdir(parents=True, exist_ok=True)
        staging_path = Path(tempfile.mkdtemp(prefix=".task-", dir=tasks_root))
        final_path = tasks_root / task_id
        moved = False

        try:
            students_dir = staging_path / "students"
            results_dir = staging_path / "results"
            students_dir.mkdir()
            results_dir.mkdir()
            records: list[
                tuple[SubmissionRecord, DiagnosisRecord | None, ExplanationRecord | None]
            ] = []

            for index, analysis in enumerate(result.students, start=1):
                source = source_by_name[analysis.student_name]
                stem = f"{index:04d}_{self._safe_filename(analysis.student_name)}"
                source_path = students_dir / f"{stem}.cpp"
                result_path = results_dir / f"{stem}.json"
                source_path.write_text(source.source_code, encoding="utf-8", newline="")
                result_path.write_text(
                    json.dumps(
                        self._result_payload(analysis), ensure_ascii=False, indent=2
                    ),
                    encoding="utf-8",
                    newline="\n",
                )

                persisted_id = f"{task_id}:{analysis.submission_id}"
                judge = analysis.judge_result
                submission = SubmissionRecord(
                    id=persisted_id,
                    task_id=task_id,
                    student_name=analysis.student_name,
                    status=judge.final_status.value if judge else "PROCESSING_ERROR",
                    passed_count=judge.passed_count if judge else 0,
                    total_count=judge.total_count if judge else 0,
                    source_file_path=self._relative_data_path(
                        final_path / "students" / source_path.name
                    ),
                    result_file_path=self._relative_data_path(
                        final_path / "results" / result_path.name
                    ),
                    error_message=analysis.error_message,
                )
                records.append(
                    (
                        submission,
                        self._diagnosis_record(persisted_id, analysis),
                        self._explanation_record(persisted_id, analysis),
                    )
                )

            with self._database.transaction() as connection:
                TaskRepository(connection).create_task(task)
                submissions = SubmissionRepository(connection)
                diagnoses = DiagnosisRepository(connection)
                explanations = ExplanationRepository(connection)
                for submission, diagnosis, explanation in records:
                    submissions.save_submission(submission)
                    if diagnosis is not None:
                        diagnoses.save_diagnosis(diagnosis)
                    if explanation is not None:
                        explanations.save_explanation(explanation)
                staging_path.replace(final_path)
                moved = True
            return task
        except HistoryServiceError:
            self._remove_tree(final_path if moved else staging_path)
            raise
        except Exception as exc:
            self._remove_tree(final_path if moved else staging_path)
            raise HistoryServiceError("历史记录保存失败。") from exc

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        try:
            with self._database.read_connection() as connection:
                return TaskRepository(connection).list_tasks()
        except Exception as exc:
            raise HistoryServiceError("历史记录读取失败。") from exc

    def get_task(self, task_id: str) -> HistoricalTask | None:
        try:
            with self._database.read_connection() as connection:
                task = TaskRepository(connection).get_task(task_id)
                if task is None:
                    return None
                submissions = SubmissionRepository(connection).list_submissions(task_id)
                diagnoses = DiagnosisRepository(connection)
                explanations = ExplanationRepository(connection)
                students = tuple(
                    HistoricalStudent(
                        submission=submission,
                        diagnosis=diagnoses.get_diagnosis(submission.id),
                        explanation=explanations.get_explanation(submission.id),
                        result_data=self._read_result_file(submission.result_file_path),
                    )
                    for submission in submissions
                )
                return HistoricalTask(task=task, students=students)
        except HistoryServiceError:
            raise
        except Exception as exc:
            raise HistoryServiceError("历史记录读取失败。") from exc

    def update_task_title(self, task_id: str, title: str) -> TaskRecord | None:
        title = self._required_text(title, "title")
        try:
            with self._database.transaction() as connection:
                repository = TaskRepository(connection)
                if not repository.update_title(task_id, title):
                    return None
                return repository.get_task(task_id)
        except Exception as exc:
            raise HistoryServiceError("历史任务更新失败。") from exc

    def delete_task(self, task_id: str) -> bool:
        try:
            with self._database.transaction() as connection:
                deleted = TaskRepository(connection).delete_task(task_id)
            if deleted:
                self._remove_tree(self._database.tasks_root / task_id)
            return deleted
        except Exception as exc:
            raise HistoryServiceError("历史任务删除失败。") from exc

    @staticmethod
    def _diagnosis_record(
        submission_id: str, analysis: StudentAnalysis
    ) -> DiagnosisRecord | None:
        report = analysis.diagnosis_report
        if report is None:
            return None
        primary = report.primary_diagnosis
        return DiagnosisRecord(
            id=None,
            submission_id=submission_id,
            category=primary.category if primary else None,
            summary=primary.summary if primary else "",
            detail=primary.detail if primary else "",
            confidence=primary.confidence if primary else 0.0,
            evidence=primary.evidence if primary else (),
            related_lines=primary.related_lines if primary else (),
            secondary_evidence=report.secondary_evidence,
        )

    @staticmethod
    def _explanation_record(
        submission_id: str, analysis: StudentAnalysis
    ) -> ExplanationRecord | None:
        result = analysis.explanation_result
        if result is None:
            return None
        explanation = result.explanation
        return ExplanationRecord(
            id=None,
            submission_id=submission_id,
            status=result.status.value,
            teacher_explanation=explanation.teacher_explanation if explanation else None,
            student_explanation=explanation.student_explanation if explanation else None,
            confidence_note=explanation.confidence_note if explanation else None,
            error_message=result.error_message,
        )

    @staticmethod
    def _result_payload(analysis: StudentAnalysis) -> dict[str, Any]:
        judge = analysis.judge_result
        payload: dict[str, Any] = {
            "submission_id": analysis.submission_id,
            "student_name": analysis.student_name,
            "error_message": analysis.error_message,
        }
        if judge is None:
            payload.update(
                {"status": "PROCESSING_ERROR", "passed_count": 0, "total_count": 0}
            )
            return payload
        payload.update(
            {
                "problem_id": judge.problem_id,
                "status": judge.final_status.value,
                "passed_count": judge.passed_count,
                "total_count": judge.total_count,
                "compile_stdout": judge.compile_stdout,
                "compile_stderr": judge.compile_stderr,
                "testcase_results": [
                    {
                        "testcase_id": case.testcase_id,
                        "status": case.status.value,
                        "execution_time_ms": case.execution_time_ms,
                        "stdout": case.stdout,
                        "stderr": case.stderr,
                        "exit_code": case.exit_code,
                    }
                    for case in judge.testcase_results
                ],
            }
        )
        return payload

    def _read_result_file(self, relative_path: str) -> dict[str, Any]:
        path = self._resolve_data_path(relative_path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise HistoryServiceError("历史结果文件不可用。") from exc
        if not isinstance(data, dict):
            raise HistoryServiceError("历史结果文件格式无效。")
        return data

    def _relative_data_path(self, path: Path) -> str:
        return path.relative_to(self._database.path.parent).as_posix()

    def _resolve_data_path(self, relative_path: str) -> Path:
        root = self._database.path.parent.resolve()
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root):
            raise HistoryServiceError("历史文件路径无效。")
        return path

    @staticmethod
    def _new_task_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"task-{timestamp}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _safe_filename(name: str) -> str:
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
        if not sanitized:
            sanitized = "student"
        reserved = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{index}" for index in range(1, 10)),
            *(f"LPT{index}" for index in range(1, 10)),
        }
        if sanitized.upper() in reserved:
            sanitized = f"_{sanitized}"
        return sanitized[:80]

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise HistoryServiceError(f"{field_name} 不能为空。")
        return value.strip()

    @staticmethod
    def _remove_tree(path: Path) -> None:
        try:
            shutil.rmtree(path)
        except (FileNotFoundError, OSError):
            pass
