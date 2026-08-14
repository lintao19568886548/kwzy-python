"""Pure-domain regression tests for facility management."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.modules.facility_ops.domain.facility_management import (
    normalize_severity,
    transition_alarm,
    transition_device,
    transition_task,
    validate_device_properties,
    validate_result,
    validate_template_items,
    weekly_window,
)


def test_device_properties_are_bounded_and_do_not_override_governance_fields() -> None:
    assert validate_device_properties({"voltage": 380, "networked": True}) == {
        "voltage": 380,
        "networked": True,
    }
    with pytest.raises(AppError, match="非法字段"):
        validate_device_properties({"tenant_id": 99})
    with pytest.raises(AppError, match="嵌套"):
        validate_device_properties({"unsafe": {"nested": True}})


def test_template_and_results_enforce_types_ranges_and_critical_failures() -> None:
    items = validate_template_items(
        [
            {
                "item_code": "temp",
                "label": "温度",
                "result_type": "NUMBER",
                "minimum": "10",
                "maximum": "30",
                "critical": True,
            },
            {
                "item_code": "mode",
                "label": "模式",
                "result_type": "SELECT",
                "options": ["自动", "手动"],
            },
        ]
    )
    assert items[0]["item_code"] == "TEMP"
    assert validate_result(items[0], "31") == (None, Decimal(31), False)
    assert validate_result(items[1], "自动") == ("自动", None, True)
    with pytest.raises(AppError, match="SELECT"):
        validate_result(items[1], "未知")


def test_weekly_window_is_timezone_aware_and_deterministic() -> None:
    start, due = weekly_window(
        reference=datetime(2026, 8, 12, 3, 0, tzinfo=timezone.utc).replace(tzinfo=None),
        weekday=5,
        local_due_time="18:30",
        timezone_name="Asia/Shanghai",
        completion_window_minutes=120,
    )
    assert due == datetime(2026, 8, 14, 10, 30, tzinfo=timezone.utc).replace(tzinfo=None)
    assert start == datetime(2026, 8, 14, 8, 30, tzinfo=timezone.utc).replace(tzinfo=None)


def test_state_machines_and_severity_mapping_reject_shortcuts() -> None:
    assert transition_device("ACTIVE", "MAINTENANCE") == "MAINTENANCE"
    assert transition_task("PENDING", "IN_PROGRESS") == "IN_PROGRESS"
    assert transition_alarm("OPEN", "ACKNOWLEDGED") == "ACKNOWLEDGED"
    assert normalize_severity("fatal", {"FATAL": "CRITICAL"}) == "CRITICAL"
    with pytest.raises(AppError, match="设备状态迁移"):
        transition_device("RETIRED", "ACTIVE")
    with pytest.raises(AppError, match="巡检任务状态迁移"):
        transition_task("PASSED", "IN_PROGRESS")
    with pytest.raises(AppError, match="告警状态迁移"):
        transition_alarm("CLOSED", "OPEN")
