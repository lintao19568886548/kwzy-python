from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.modules.lease.domain.changes import (
    assert_base_version,
    assert_change_status_transition,
    validate_change_proposal,
)
from app.modules.lease.domain.errors import LeaseDomainError
from app.modules.lease.domain.pricing import (
    generate_performance_schedule,
    schedule_checksum,
)
from app.modules.lease.domain.rules import (
    assert_direct_edit_allowed,
    assert_lease_status,
    assert_v2_status_transition,
    is_occupying_status,
)
from app.modules.lease.domain.settlement import (
    assert_financial_clearance,
    calculate_exit_totals,
    validate_meter_readings,
)
from app.modules.lease.domain.versioning import (
    assert_expected_version,
    canonical_json,
    scoped_idempotency_key,
    snapshot_checksum,
)


def _error_code(exc: pytest.ExceptionInfo[LeaseDomainError]) -> str:
    return exc.value.code


def _snapshot() -> dict:
    return {
        "contract": {
            "tenant_id": 1,
            "park_id": 10,
            "party_id": 20,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "currency": "CNY",
        },
        "units": [{"unit_id": 100, "occupied_area": "100"}],
        "charges": [{"charge_code": "RENT", "amount": "1000"}],
    }


def _monthly_charge(**overrides) -> dict:
    charge = {
        "charge_code": "RENT",
        "charge_type": "RENT",
        "calculation_method": "FIXED",
        "billing_cycle": "MONTHLY",
        "currency": "CNY",
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 3, 31),
        "due_day": 5,
        "amount": "100.005",
        "tax_rate": "0.06",
    }
    charge.update(overrides)
    return charge


def test_v2_lifecycle_and_legacy_renewed_read_only() -> None:
    assert assert_v2_status_transition("DRAFT", "PENDING_APPROVAL") == "PENDING_APPROVAL"
    assert assert_v2_status_transition("PENDING_APPROVAL", "PENDING_ACTIVE") == "PENDING_ACTIVE"
    assert assert_v2_status_transition("PENDING_ACTIVE", "ACTIVE") == "ACTIVE"
    assert assert_v2_status_transition("ACTIVE", "EXIT_PENDING") == "EXIT_PENDING"
    assert assert_v2_status_transition("EXIT_PENDING", "TERMINATED") == "TERMINATED"
    assert assert_v2_status_transition("EXIT_PENDING", "ACTIVE") == "ACTIVE"
    assert assert_v2_status_transition("EXIT_PENDING", "EXPIRING") == "EXPIRING"
    assert assert_lease_status("renewed") == "RENEWED"
    assert is_occupying_status("EXIT_PENDING")
    with pytest.raises(LeaseDomainError) as renewed:
        assert_lease_status("RENEWED", for_write=True)
    assert _error_code(renewed) == "LEASE_LEGACY_STATUS_READ_ONLY"
    with pytest.raises(LeaseDomainError) as illegal:
        assert_v2_status_transition("ACTIVE", "TERMINATED")
    assert _error_code(illegal) == "LEASE_STATUS_INVALID"


def test_only_draft_allows_direct_business_edit() -> None:
    assert_direct_edit_allowed("DRAFT")
    with pytest.raises(LeaseDomainError) as conflict:
        assert_direct_edit_allowed("ACTIVE")
    assert _error_code(conflict) == "LEASE_CHANGE_ORDER_REQUIRED"


def test_canonical_snapshot_and_checksum_are_stable() -> None:
    first = {
        "z": Decimal("1.2300"),
        "a": {"when": datetime(2026, 1, 1, tzinfo=timezone.utc), "day": date(2026, 2, 3)},
    }
    second = {"a": {"day": "2026-02-03", "when": "2026-01-01T00:00:00Z"}, "z": "1.23"}
    assert canonical_json(first) == canonical_json(second)
    assert snapshot_checksum(first) == snapshot_checksum(second)
    assert len(snapshot_checksum(first)) == 64
    with pytest.raises(LeaseDomainError) as unsupported:
        canonical_json(first, schema_version=2)
    assert _error_code(unsupported) == "LEASE_SNAPSHOT_SCHEMA_UNSUPPORTED"


def test_expected_version_and_scoped_idempotency_semantics() -> None:
    assert assert_expected_version(3, 3) == 3
    with pytest.raises(LeaseDomainError) as stale:
        assert_expected_version(3, 2)
    assert _error_code(stale) == "LEASE_VERSION_CONFLICT"
    assert scoped_idempotency_key(8, "apply-change", "client-1") == (
        "lease:t8:APPLY-CHANGE:client-1"
    )


def test_schedule_is_deterministic_half_up_and_rule_aware() -> None:
    args = {
        "tenant_id": 1,
        "contract_id": 9,
        "contract_version_no": 1,
        "contract_start": date(2026, 1, 1),
        "contract_end": date(2026, 3, 31),
        "charges": [_monthly_charge()],
        "units": [{"unit_id": 1, "occupied_area": "20"}],
        "rules": [
            {
                "rule_type": "RENT_FREE",
                "charge_code": "RENT",
                "effective_date": "2026-02-01",
                "end_date": "2026-02-28",
                "rule_ref": "FREE-FEB",
            },
            {
                "rule_type": "ESCALATION",
                "charge_code": "RENT",
                "effective_date": "2026-03-01",
                "rate": "0.10",
                "rule_ref": "UP-MAR",
            },
        ],
    }
    first = generate_performance_schedule(**args)
    second = generate_performance_schedule(**args)
    assert len(first) == 3
    assert [row.net_amount for row in first] == [
        Decimal("100.01"),
        Decimal("0.00"),
        Decimal("110.01"),
    ]
    assert first[0].tax_amount == Decimal("6.00")
    assert first[0].gross_amount == Decimal("106.01")
    assert first[1].rule_refs == ("FREE-FEB",)
    assert first[2].rule_refs == ("UP-MAR",)
    assert first == second
    assert schedule_checksum(first) == schedule_checksum(second)


def test_per_area_and_one_time_schedule() -> None:
    per_area = _monthly_charge(calculation_method="PER_AREA", amount=None, unit_price="2.345")
    rows = generate_performance_schedule(
        tenant_id=1,
        contract_id=2,
        contract_version_no=0,
        contract_start=date(2026, 1, 1),
        contract_end=date(2026, 3, 31),
        charges=[per_area],
        units=[{"occupied_area": "10"}, {"occupied_area": "5"}],
    )
    assert rows[0].area == Decimal("15")
    assert rows[0].net_amount == Decimal("35.18")

    one_time = _monthly_charge(
        charge_code="DEPOSIT",
        charge_type="DEPOSIT",
        billing_cycle="ONE_TIME",
        start_date=date(2026, 1, 8),
        end_date=date(2026, 1, 8),
        amount="500",
        tax_rate="0",
    )
    once = generate_performance_schedule(
        tenant_id=1,
        contract_id=2,
        contract_version_no=0,
        contract_start=date(2026, 1, 1),
        contract_end=date(2026, 3, 31),
        charges=[one_time],
        units=[],
    )
    assert len(once) == 1
    assert once[0].period_start == once[0].period_end == date(2026, 1, 8)


def test_schedule_rejects_empty_area_duplicate_charge_and_partial_rule() -> None:
    per_area = _monthly_charge(calculation_method="PER_AREA", amount=None, unit_price="2")
    with pytest.raises(LeaseDomainError) as empty:
        generate_performance_schedule(
            tenant_id=1,
            contract_id=2,
            contract_version_no=0,
            contract_start=date(2026, 1, 1),
            contract_end=date(2026, 3, 31),
            charges=[per_area],
            units=[],
        )
    assert _error_code(empty) == "LEASE_CHARGE_AREA_REQUIRED"

    with pytest.raises(LeaseDomainError) as duplicate:
        generate_performance_schedule(
            tenant_id=1,
            contract_id=2,
            contract_version_no=0,
            contract_start=date(2026, 1, 1),
            contract_end=date(2026, 3, 31),
            charges=[_monthly_charge(), _monthly_charge()],
            units=[],
        )
    assert _error_code(duplicate) == "LEASE_CHARGE_INVALID"

    with pytest.raises(LeaseDomainError) as partial:
        generate_performance_schedule(
            tenant_id=1,
            contract_id=2,
            contract_version_no=0,
            contract_start=date(2026, 1, 1),
            contract_end=date(2026, 3, 31),
            charges=[_monthly_charge()],
            units=[],
            rules=[
                {
                    "rule_type": "RENT_FREE",
                    "charge_code": "RENT",
                    "effective_date": "2026-01-15",
                    "end_date": "2026-01-31",
                }
            ],
        )
    assert _error_code(partial) == "LEASE_PRORATION_UNSUPPORTED"


def test_all_seven_change_invariants() -> None:
    before = _snapshot()
    renewal = deepcopy(before)
    renewal["contract"]["end_date"] = "2027-12-31"
    validate_change_proposal(
        "RENEWAL",
        current_snapshot=before,
        proposed_snapshot=renewal,
        effective_date=date(2027, 1, 1),
        reason="续租",
    )

    expansion = deepcopy(before)
    expansion["units"].append({"unit_id": 101, "occupied_area": "50"})
    validate_change_proposal(
        "EXPANSION",
        current_snapshot=before,
        proposed_snapshot=expansion,
        effective_date=date(2026, 4, 1),
        reason="扩租",
    )

    reduction = deepcopy(before)
    reduction["units"][0]["occupied_area"] = "60"
    validate_change_proposal(
        "REDUCTION",
        current_snapshot=before,
        proposed_snapshot=reduction,
        effective_date=date(2026, 4, 1),
        reason="减租",
    )

    transfer = deepcopy(before)
    transfer["units"] = [{"unit_id": 102, "occupied_area": "100"}]
    validate_change_proposal(
        "UNIT_TRANSFER",
        current_snapshot=before,
        proposed_snapshot=transfer,
        effective_date=date(2026, 4, 1),
        reason="换房",
    )

    price = deepcopy(before)
    price["charges"][0]["amount"] = "1200"
    validate_change_proposal(
        "PRICE_ADJUSTMENT",
        current_snapshot=before,
        proposed_snapshot=price,
        effective_date=date(2026, 4, 1),
        reason="调价",
        today=date(2026, 3, 1),
        cycle_boundaries={date(2026, 4, 1)},
    )

    party = deepcopy(before)
    party["contract"]["party_id"] = 21
    validate_change_proposal(
        "PARTY_TRANSFER",
        current_snapshot=before,
        proposed_snapshot=party,
        effective_date=date(2026, 4, 1),
        reason="主体变更",
        target_party_eligible=True,
    )

    validate_change_proposal(
        "EARLY_TERMINATION",
        current_snapshot=before,
        proposed_snapshot=deepcopy(before),
        effective_date=date(2026, 6, 1),
        reason="提前退租",
        today=date(2026, 3, 1),
    )


def test_change_lifecycle_and_conflicts() -> None:
    assert assert_change_status_transition("DRAFT", "SUBMITTED") == "SUBMITTED"
    assert assert_change_status_transition("SUBMITTED", "APPROVED") == "APPROVED"
    assert assert_change_status_transition("APPROVED", "APPLIED") == "APPLIED"
    assert assert_base_version(2, 2) == 2
    with pytest.raises(LeaseDomainError) as stale:
        assert_base_version(3, 2)
    assert _error_code(stale) == "LEASE_CHANGE_BASE_VERSION_CONFLICT"

    bad_party = deepcopy(_snapshot())
    bad_party["contract"]["party_id"] = 21
    with pytest.raises(LeaseDomainError) as ineligible:
        validate_change_proposal(
            "PARTY_TRANSFER",
            current_snapshot=_snapshot(),
            proposed_snapshot=bad_party,
            effective_date=date(2026, 4, 1),
            reason="主体变更",
            target_party_eligible=False,
        )
    assert _error_code(ineligible) == "LEASE_PARTY_INELIGIBLE"


def test_exit_totals_are_stable_and_unambiguous() -> None:
    covered = calculate_exit_totals(
        held_deposit_amount="1000",
        outstanding_amount="100",
        items=[
            {"item_type": "DEDUCTION", "amount": "50.005", "description": "维修"},
            {"item_type": "REFUND", "amount": "10", "description": "多收调整"},
        ],
        meter_readings=[
            {"meter_code": "POWER", "previous_reading": "10", "current_reading": "12"}
        ],
    )
    replay = calculate_exit_totals(
        held_deposit_amount=Decimal("1000.00"),
        outstanding_amount=Decimal("100"),
        items=[
            {"item_type": "DEDUCTION", "amount": "50.005", "description": "维修"},
            {"item_type": "REFUND", "amount": "10", "description": "多收调整"},
        ],
        meter_readings=[
            {"meter_code": "POWER", "previous_reading": "10", "current_reading": "12"}
        ],
    )
    assert covered["net_due_to_party"] == Decimal("859.99")
    assert covered["net_due_from_party"] == Decimal("0.00")
    assert covered["checksum"] == replay["checksum"]

    shortfall = calculate_exit_totals(
        held_deposit_amount="100",
        outstanding_amount="80",
        items=[{"item_type": "RECEIVABLE", "amount": "50", "description": "欠费"}],
    )
    assert shortfall["net_due_from_party"] == Decimal("30.00")
    assert shortfall["net_due_to_party"] == Decimal("0.00")


def test_meter_regression_and_clearance_fail_closed() -> None:
    with pytest.raises(LeaseDomainError) as meter:
        validate_meter_readings(
            [{"meter_code": "WATER", "previous_reading": "12", "current_reading": "10"}]
        )
    assert _error_code(meter) == "LEASE_EXIT_ITEM_INVALID"
    with pytest.raises(LeaseDomainError) as clearance:
        assert_financial_clearance(
            net_due_from_party="10",
            net_due_to_party="0",
            status="PENDING",
            evidence_ref=None,
            reason=None,
        )
    assert _error_code(clearance) == "LEASE_FINANCIAL_CLEARANCE_REQUIRED"
    assert_financial_clearance(
        net_due_from_party="10",
        net_due_to_party="0",
        status="CONFIRMED",
        evidence_ref="ATTACHMENT-7",
        reason="线下结清凭证已复核",
    )
