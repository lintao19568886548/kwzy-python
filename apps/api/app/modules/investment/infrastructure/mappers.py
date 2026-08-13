"""Investment CRM ORM/domain mappers."""

from __future__ import annotations

from app.infrastructure.database.models.investment import (
    Lead,
    LeadActivity,
    LeadAssignmentEvent,
    LeadMergeLink,
    LeadUnitLock,
)
from app.modules.investment.domain.entities import (
    LeadActivityEntity,
    LeadAssignmentEventEntity,
    LeadEntity,
    LeadMergeLinkEntity,
    LeadUnitLockEntity,
)


class LeadMapper:
    @staticmethod
    def to_entity(model: Lead) -> LeadEntity:
        return LeadEntity(
            id=model.id,
            tenant_id=model.tenant_id,
            park_id=model.park_id,
            name=model.name,
            contact_phone=model.contact_phone,
            contact_name=model.contact_name,
            agent_name=model.agent_name,
            intent_level=model.intent_level,
            intent_area=model.intent_area,
            desired_usage=model.desired_usage,
            budget_unit_price=model.budget_unit_price,
            status=model.status,
            normalized_name=model.normalized_name,
            normalized_phone=model.normalized_phone,
            source_type=model.source_type,
            source_ref=model.source_ref,
            duplicate_override_reason=model.duplicate_override_reason,
            pool_status=model.pool_status,
            remark=model.remark,
            owner_user_id=model.owner_user_id,
            party_id=model.party_id,
            lease_id=model.lease_id,
            merged_into_lead_id=model.merged_into_lead_id,
            lost_reason=model.lost_reason,
            assigned_at=model.assigned_at,
            first_contact_at=model.first_contact_at,
            last_activity_at=model.last_activity_at,
            next_follow_up_at=model.next_follow_up_at,
            recycle_due_at=model.recycle_due_at,
            converted_at=model.converted_at,
            lock_version=model.lock_version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def new_model(entity: LeadEntity) -> Lead:
        values = entity.__dict__ if hasattr(entity, "__dict__") else {
            field: getattr(entity, field)
            for field in entity.__dataclass_fields__
        }
        return Lead(**{key: value for key, value in values.items() if key not in {"id", "created_at", "updated_at"}})


class LeadActivityMapper:
    @staticmethod
    def new_model(entity: LeadActivityEntity) -> LeadActivity:
        return LeadActivity(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            lead_id=entity.lead_id,
            actor_user_id=entity.actor_user_id,
            activity_type=entity.activity_type,
            content=entity.content,
            occurred_at=entity.occurred_at,
            next_follow_up_at=entity.next_follow_up_at,
            stage_from=entity.stage_from,
            stage_to=entity.stage_to,
            attributes_json=entity.attributes_json or None,
        )


class LeadAssignmentEventMapper:
    @staticmethod
    def new_model(entity: LeadAssignmentEventEntity) -> LeadAssignmentEvent:
        return LeadAssignmentEvent(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            lead_id=entity.lead_id,
            from_owner_user_id=entity.from_owner_user_id,
            to_owner_user_id=entity.to_owner_user_id,
            event_type=entity.event_type,
            reason=entity.reason,
            actor_user_id=entity.actor_user_id,
            occurred_at=entity.occurred_at,
        )


class LeadMergeLinkMapper:
    @staticmethod
    def new_model(entity: LeadMergeLinkEntity) -> LeadMergeLink:
        return LeadMergeLink(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            source_lead_id=entity.source_lead_id,
            target_lead_id=entity.target_lead_id,
            actor_user_id=entity.actor_user_id,
            reason=entity.reason,
            merged_at=entity.merged_at,
        )


class LeadUnitLockMapper:
    @staticmethod
    def new_model(entity: LeadUnitLockEntity) -> LeadUnitLock:
        return LeadUnitLock(
            tenant_id=entity.tenant_id,
            park_id=entity.park_id,
            lead_id=entity.lead_id,
            unit_id=entity.unit_id,
            lease_id=entity.lease_id,
            status=entity.status,
            expires_at=entity.expires_at,
            released_at=entity.released_at,
            consumed_at=entity.consumed_at,
            created_by=entity.created_by,
            lock_version=entity.lock_version,
        )
