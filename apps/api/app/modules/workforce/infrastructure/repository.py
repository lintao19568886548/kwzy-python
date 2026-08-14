"""Tenant- and park-scoped workforce persistence boundary."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.database.models.attachment import Attachment
from app.infrastructure.database.models.identity import User
from app.infrastructure.database.models.park_property import Park
from app.infrastructure.database.models.workflow import ApprovalRequest
from app.infrastructure.database.models.workforce import (
    AttendanceDailySummary,
    AttendanceLocation,
    AttendancePolicy,
    AttendancePunch,
    EmployeeQualification,
    PerformanceCycle,
    PerformanceGoal,
    PerformanceReview,
    QualificationEvent,
    QualificationType,
    ShiftAssignment,
    ShiftTemplate,
    ShiftTemplateVersion,
    WorkforceEmployee,
    WorkforceEmployeeEvent,
    WorkforceLeaveRequest,
)
from app.modules.identity.infrastructure.authorization_repository import AuthorizationRepository
from app.shared.tenant_context import ParkScopeMode, TenantContext


class WorkforceRepository:
    """The only workforce layer that imports ORM models."""

    def __init__(self, session: Session, ctx: TenantContext) -> None:
        self.session = session
        self.ctx = ctx

    @property
    def tenant_id(self) -> int:
        return int(self.ctx.tenant_id)

    def _scope(self, stmt, model):  # type: ignore[no-untyped-def]
        stmt = stmt.where(model.tenant_id == self.tenant_id)
        if hasattr(model, "park_id"):
            if self.ctx.park_scope_mode == ParkScopeMode.ALL:
                return stmt
            if self.ctx.park_scope_mode == ParkScopeMode.LIST and self.ctx.park_ids:
                return stmt.where(model.park_id.in_(list(self.ctx.park_ids)))
            return stmt.where(False)
        return stmt

    def _lock(self, stmt, enabled: bool):  # type: ignore[no-untyped-def]
        if (
            enabled
            and self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            return stmt.with_for_update()
        return stmt

    def _add(self, model):  # type: ignore[no-untyped-def]
        model.tenant_id = self.tenant_id
        self.session.add(model)
        self.session.flush()
        return model

    def save(self, model):  # type: ignore[no-untyped-def]
        if int(model.tenant_id) != self.tenant_id:
            raise AppError("租户不匹配", code="TENANT_MISMATCH", status_code=403)
        if hasattr(model, "park_id") and not self.ctx.allows_park(int(model.park_id)):
            raise AppError("无该园区数据权限", code="PARK_SCOPE_DENIED", status_code=403)
        self.session.add(model)
        self.session.flush()
        return model

    def park_exists(self, park_id: int) -> bool:
        return bool(
            self.session.scalar(
                select(Park.id).where(
                    Park.tenant_id == self.tenant_id,
                    Park.id == int(park_id),
                    Park.is_deleted.is_(False),
                )
            )
        )

    def active_user(self, user_id: int, park_id: int) -> User | None:
        user = self.session.scalar(
            select(User).where(
                User.tenant_id == self.tenant_id, User.id == int(user_id), User.status == "ACTIVE"
            )
        )
        if user is None:
            return None
        _, park_ids, mode = AuthorizationRepository(self.session).resolve_authorization(user)
        return user if mode == ParkScopeMode.ALL or int(park_id) in park_ids else None

    # Employees
    def list_employees(
        self,
        *,
        offset: int,
        limit: int,
        park_id: int | None,
        status: str | None,
        keyword: str | None,
    ) -> Sequence[WorkforceEmployee]:
        stmt = self._scope(select(WorkforceEmployee), WorkforceEmployee)
        if park_id is not None:
            stmt = stmt.where(WorkforceEmployee.park_id == int(park_id))
        if status:
            stmt = stmt.where(WorkforceEmployee.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    WorkforceEmployee.employee_no.ilike(pattern),
                    WorkforceEmployee.display_name.ilike(pattern),
                    WorkforceEmployee.department_name.ilike(pattern),
                )
            )
        return list(
            self.session.scalars(
                stmt.order_by(WorkforceEmployee.employee_no).offset(offset).limit(limit)
            ).all()
        )

    def count_employees(
        self, *, park_id: int | None, status: str | None, keyword: str | None
    ) -> int:
        stmt = self._scope(select(func.count()).select_from(WorkforceEmployee), WorkforceEmployee)
        if park_id is not None:
            stmt = stmt.where(WorkforceEmployee.park_id == int(park_id))
        if status:
            stmt = stmt.where(WorkforceEmployee.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    WorkforceEmployee.employee_no.ilike(pattern),
                    WorkforceEmployee.display_name.ilike(pattern),
                    WorkforceEmployee.department_name.ilike(pattern),
                )
            )
        return int(self.session.scalar(stmt) or 0)

    def get_employee(
        self, employee_id: int, *, for_update: bool = False
    ) -> WorkforceEmployee | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(WorkforceEmployee).where(WorkforceEmployee.id == int(employee_id)),
                    WorkforceEmployee,
                ),
                for_update,
            )
        )

    def create_employee(self, **values: Any) -> WorkforceEmployee:
        return self._add(WorkforceEmployee(**values))

    def create_employee_event(self, **values: Any) -> WorkforceEmployeeEvent:
        return self._add(WorkforceEmployeeEvent(**values))

    def employee_events(self, employee_id: int) -> Sequence[WorkforceEmployeeEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(WorkforceEmployeeEvent).where(
                        WorkforceEmployeeEvent.employee_id == int(employee_id)
                    ),
                    WorkforceEmployeeEvent,
                ).order_by(
                    WorkforceEmployeeEvent.occurred_at.desc(), WorkforceEmployeeEvent.id.desc()
                )
            ).all()
        )

    # Shift and roster
    def list_shift_templates(self, park_id: int | None = None) -> Sequence[ShiftTemplate]:
        stmt = self._scope(select(ShiftTemplate), ShiftTemplate)
        if park_id is not None:
            stmt = stmt.where(ShiftTemplate.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(ShiftTemplate.code)).all())

    def get_shift_template(
        self, template_id: int, *, for_update: bool = False
    ) -> ShiftTemplate | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(ShiftTemplate).where(ShiftTemplate.id == int(template_id)), ShiftTemplate
                ),
                for_update,
            )
        )

    def create_shift_template(self, **values: Any) -> ShiftTemplate:
        return self._add(ShiftTemplate(**values))

    def create_shift_version(self, **values: Any) -> ShiftTemplateVersion:
        return self._add(ShiftTemplateVersion(**values))

    def get_shift_version(self, version_id: int) -> ShiftTemplateVersion | None:
        return self.session.scalar(
            self._scope(
                select(ShiftTemplateVersion).where(ShiftTemplateVersion.id == int(version_id)),
                ShiftTemplateVersion,
            )
        )

    def shift_versions(self, template_id: int) -> Sequence[ShiftTemplateVersion]:
        return list(
            self.session.scalars(
                self._scope(
                    select(ShiftTemplateVersion).where(
                        ShiftTemplateVersion.template_id == int(template_id)
                    ),
                    ShiftTemplateVersion,
                ).order_by(ShiftTemplateVersion.version_no.desc())
            ).all()
        )

    def list_assignments(
        self, *, employee_id: int | None, date_from: date, date_to: date
    ) -> Sequence[ShiftAssignment]:
        stmt = self._scope(
            select(ShiftAssignment).where(
                ShiftAssignment.work_date >= date_from, ShiftAssignment.work_date <= date_to
            ),
            ShiftAssignment,
        )
        if employee_id is not None:
            stmt = stmt.where(ShiftAssignment.employee_id == int(employee_id))
        return list(
            self.session.scalars(
                stmt.order_by(ShiftAssignment.work_date, ShiftAssignment.employee_id)
            ).all()
        )

    def active_assignment(
        self, employee_id: int, work_date: date, *, for_update: bool = False
    ) -> ShiftAssignment | None:
        stmt = self._scope(
            select(ShiftAssignment).where(
                ShiftAssignment.employee_id == int(employee_id),
                ShiftAssignment.work_date == work_date,
                ShiftAssignment.status == "ACTIVE",
            ),
            ShiftAssignment,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def get_assignment(
        self, assignment_id: int, *, for_update: bool = False
    ) -> ShiftAssignment | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(ShiftAssignment).where(ShiftAssignment.id == int(assignment_id)),
                    ShiftAssignment,
                ),
                for_update,
            )
        )

    def create_assignment(self, **values: Any) -> ShiftAssignment:
        return self._add(ShiftAssignment(**values))

    # Attendance
    def list_policies(self, park_id: int | None = None) -> Sequence[AttendancePolicy]:
        stmt = self._scope(select(AttendancePolicy), AttendancePolicy)
        if park_id is not None:
            stmt = stmt.where(AttendancePolicy.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(AttendancePolicy.code)).all())

    def create_policy(self, **values: Any) -> AttendancePolicy:
        return self._add(AttendancePolicy(**values))

    def list_locations(self, park_id: int | None = None) -> Sequence[AttendanceLocation]:
        stmt = self._scope(select(AttendanceLocation), AttendanceLocation)
        if park_id is not None:
            stmt = stmt.where(AttendanceLocation.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(AttendanceLocation.code)).all())

    def get_location(self, location_id: int) -> AttendanceLocation | None:
        return self.session.scalar(
            self._scope(
                select(AttendanceLocation).where(
                    AttendanceLocation.id == int(location_id), AttendanceLocation.status == "ACTIVE"
                ),
                AttendanceLocation,
            )
        )

    def create_location(self, **values: Any) -> AttendanceLocation:
        return self._add(AttendanceLocation(**values))

    def punch_by_key(self, key: str) -> AttendancePunch | None:
        return self.session.scalar(
            select(AttendancePunch).where(
                AttendancePunch.tenant_id == self.tenant_id, AttendancePunch.idempotency_key == key
            )
        )

    def create_punch(self, **values: Any) -> AttendancePunch:
        return self._add(AttendancePunch(**values))

    def punches_for_day(self, employee_id: int, work_date: date) -> Sequence[AttendancePunch]:
        start = datetime.combine(work_date, datetime.min.time())
        end = datetime.combine(work_date, datetime.max.time())
        return list(
            self.session.scalars(
                self._scope(
                    select(AttendancePunch).where(
                        AttendancePunch.employee_id == int(employee_id),
                        AttendancePunch.punched_at >= start,
                        AttendancePunch.punched_at <= end,
                    ),
                    AttendancePunch,
                ).order_by(AttendancePunch.punched_at, AttendancePunch.id)
            ).all()
        )

    def get_summary(
        self, employee_id: int, work_date: date, *, for_update: bool = False
    ) -> AttendanceDailySummary | None:
        stmt = self._scope(
            select(AttendanceDailySummary).where(
                AttendanceDailySummary.employee_id == int(employee_id),
                AttendanceDailySummary.work_date == work_date,
            ),
            AttendanceDailySummary,
        )
        return self.session.scalar(self._lock(stmt, for_update))

    def get_summary_by_id(
        self, summary_id: int, *, for_update: bool = False
    ) -> AttendanceDailySummary | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(AttendanceDailySummary).where(
                        AttendanceDailySummary.id == int(summary_id)
                    ),
                    AttendanceDailySummary,
                ),
                for_update,
            )
        )

    def create_summary(self, **values: Any) -> AttendanceDailySummary:
        return self._add(AttendanceDailySummary(**values))

    def list_summaries(
        self, *, employee_id: int | None, date_from: date, date_to: date, status: str | None
    ) -> Sequence[AttendanceDailySummary]:
        stmt = self._scope(
            select(AttendanceDailySummary).where(
                AttendanceDailySummary.work_date >= date_from,
                AttendanceDailySummary.work_date <= date_to,
            ),
            AttendanceDailySummary,
        )
        if employee_id is not None:
            stmt = stmt.where(AttendanceDailySummary.employee_id == int(employee_id))
        if status:
            stmt = stmt.where(AttendanceDailySummary.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(
                    AttendanceDailySummary.work_date.desc(), AttendanceDailySummary.employee_id
                )
            ).all()
        )

    # Leave
    def leave_by_key(self, key: str) -> WorkforceLeaveRequest | None:
        return self.session.scalar(
            select(WorkforceLeaveRequest).where(
                WorkforceLeaveRequest.tenant_id == self.tenant_id,
                WorkforceLeaveRequest.request_key == key,
            )
        )

    def create_leave(self, **values: Any) -> WorkforceLeaveRequest:
        return self._add(WorkforceLeaveRequest(**values))

    def get_leave(self, leave_id: int, *, for_update: bool = False) -> WorkforceLeaveRequest | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(WorkforceLeaveRequest).where(WorkforceLeaveRequest.id == int(leave_id)),
                    WorkforceLeaveRequest,
                ),
                for_update,
            )
        )

    def list_leaves(self, status: str | None = None) -> Sequence[WorkforceLeaveRequest]:
        stmt = self._scope(select(WorkforceLeaveRequest), WorkforceLeaveRequest)
        if status:
            stmt = stmt.where(WorkforceLeaveRequest.status == status)
        return list(
            self.session.scalars(stmt.order_by(WorkforceLeaveRequest.start_at.desc())).all()
        )

    def approved_leave_on(self, employee_id: int, work_date: date) -> WorkforceLeaveRequest | None:
        start = datetime.combine(work_date, datetime.min.time())
        end = datetime.combine(work_date, datetime.max.time())
        return self.session.scalar(
            self._scope(
                select(WorkforceLeaveRequest).where(
                    WorkforceLeaveRequest.employee_id == int(employee_id),
                    WorkforceLeaveRequest.status == "APPROVED",
                    WorkforceLeaveRequest.start_at <= end,
                    WorkforceLeaveRequest.end_at >= start,
                ),
                WorkforceLeaveRequest,
            ).limit(1)
        )

    def approval(self, approval_id: int | None) -> ApprovalRequest | None:
        if approval_id is None:
            return None
        return self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.tenant_id == self.tenant_id, ApprovalRequest.id == int(approval_id)
            )
        )

    # Performance
    def list_cycles(self, park_id: int | None = None) -> Sequence[PerformanceCycle]:
        stmt = self._scope(select(PerformanceCycle), PerformanceCycle)
        if park_id is not None:
            stmt = stmt.where(PerformanceCycle.park_id == int(park_id))
        return list(self.session.scalars(stmt.order_by(PerformanceCycle.start_date.desc())).all())

    def get_cycle(self, cycle_id: int, *, for_update: bool = False) -> PerformanceCycle | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(PerformanceCycle).where(PerformanceCycle.id == int(cycle_id)),
                    PerformanceCycle,
                ),
                for_update,
            )
        )

    def create_cycle(self, **values: Any) -> PerformanceCycle:
        return self._add(PerformanceCycle(**values))

    def goal_weight(self, cycle_id: int, employee_id: int) -> int:
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(PerformanceGoal.weight), 0)).where(
                    PerformanceGoal.tenant_id == self.tenant_id,
                    PerformanceGoal.cycle_id == int(cycle_id),
                    PerformanceGoal.employee_id == int(employee_id),
                )
            )
            or 0
        )

    def create_goal(self, **values: Any) -> PerformanceGoal:
        return self._add(PerformanceGoal(**values))

    def list_goals(
        self, cycle_id: int, employee_id: int | None = None
    ) -> Sequence[PerformanceGoal]:
        stmt = self._scope(
            select(PerformanceGoal).where(PerformanceGoal.cycle_id == int(cycle_id)),
            PerformanceGoal,
        )
        if employee_id is not None:
            stmt = stmt.where(PerformanceGoal.employee_id == int(employee_id))
        return list(
            self.session.scalars(
                stmt.order_by(PerformanceGoal.employee_id, PerformanceGoal.code)
            ).all()
        )

    def get_review(self, review_id: int, *, for_update: bool = False) -> PerformanceReview | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(PerformanceReview).where(PerformanceReview.id == int(review_id)),
                    PerformanceReview,
                ),
                for_update,
            )
        )

    def create_review(self, **values: Any) -> PerformanceReview:
        return self._add(PerformanceReview(**values))

    def list_reviews(self, cycle_id: int | None = None) -> Sequence[PerformanceReview]:
        stmt = self._scope(select(PerformanceReview), PerformanceReview)
        if cycle_id is not None:
            stmt = stmt.where(PerformanceReview.cycle_id == int(cycle_id))
        return list(self.session.scalars(stmt.order_by(PerformanceReview.created_at.desc())).all())

    # Qualifications
    def list_qualification_types(
        self, include_retired: bool = False
    ) -> Sequence[QualificationType]:
        stmt = select(QualificationType).where(QualificationType.tenant_id == self.tenant_id)
        if not include_retired:
            stmt = stmt.where(QualificationType.status == "ACTIVE")
        return list(self.session.scalars(stmt.order_by(QualificationType.code)).all())

    def get_qualification_type(self, type_id: int) -> QualificationType | None:
        return self.session.scalar(
            select(QualificationType).where(
                QualificationType.tenant_id == self.tenant_id, QualificationType.id == int(type_id)
            )
        )

    def create_qualification_type(self, **values: Any) -> QualificationType:
        return self._add(QualificationType(**values))

    def get_attachment(self, attachment_id: int, park_id: int) -> Attachment | None:
        return self.session.scalar(
            select(Attachment).where(
                Attachment.tenant_id == self.tenant_id,
                Attachment.id == int(attachment_id),
                Attachment.park_id == int(park_id),
                Attachment.status == "ACTIVE",
            )
        )

    def create_qualification(self, **values: Any) -> EmployeeQualification:
        return self._add(EmployeeQualification(**values))

    def get_qualification(
        self, qualification_id: int, *, for_update: bool = False
    ) -> EmployeeQualification | None:
        return self.session.scalar(
            self._lock(
                self._scope(
                    select(EmployeeQualification).where(
                        EmployeeQualification.id == int(qualification_id)
                    ),
                    EmployeeQualification,
                ),
                for_update,
            )
        )

    def list_qualifications(
        self, employee_id: int | None = None, status: str | None = None
    ) -> Sequence[EmployeeQualification]:
        stmt = self._scope(select(EmployeeQualification), EmployeeQualification)
        if employee_id is not None:
            stmt = stmt.where(EmployeeQualification.employee_id == int(employee_id))
        if status:
            stmt = stmt.where(EmployeeQualification.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(EmployeeQualification.expires_on, EmployeeQualification.id)
            ).all()
        )

    def due_qualifications(self, due_on: date) -> Sequence[EmployeeQualification]:
        return list(
            self.session.scalars(
                self._scope(
                    select(EmployeeQualification).where(
                        EmployeeQualification.status == "VERIFIED",
                        EmployeeQualification.expires_on.is_not(None),
                        EmployeeQualification.expires_on <= due_on,
                    ),
                    EmployeeQualification,
                ).order_by(EmployeeQualification.id)
            ).all()
        )

    def create_qualification_event(self, **values: Any) -> QualificationEvent:
        return self._add(QualificationEvent(**values))

    def qualification_events(self, qualification_id: int) -> Sequence[QualificationEvent]:
        return list(
            self.session.scalars(
                self._scope(
                    select(QualificationEvent).where(
                        QualificationEvent.qualification_id == int(qualification_id)
                    ),
                    QualificationEvent,
                ).order_by(QualificationEvent.occurred_at.desc())
            ).all()
        )
