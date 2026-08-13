from __future__ import annotations


def _data(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_spatial_tree_rules_and_scope_safe_lifecycle(client):
    park = _data(client.post("/api/v1/parks", json={"name": "空间测试园"}))
    area = _data(
        client.post(
            "/api/v1/spaces",
            json={
                "park_id": park["id"],
                "code": "a-1",
                "name": "一期",
                "node_type": "AREA",
            },
        )
    )
    building = _data(
        client.post(
            "/api/v1/spaces",
            json={
                "park_id": park["id"],
                "parent_id": area["id"],
                "code": "b-1",
                "name": "一号楼",
                "node_type": "BUILDING",
            },
        )
    )
    floor = _data(
        client.post(
            "/api/v1/spaces",
            json={
                "park_id": park["id"],
                "parent_id": building["id"],
                "code": "f-1",
                "name": "一层",
                "node_type": "FLOOR",
            },
        )
    )
    invalid = client.post(
        "/api/v1/spaces",
        json={
            "park_id": park["id"],
            "parent_id": area["id"],
            "code": "f-bad",
            "name": "错误楼层",
            "node_type": "FLOOR",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "SPACE_PARENT_TYPE_INVALID"

    duplicate = client.post(
        "/api/v1/spaces",
        json={
            "park_id": park["id"],
            "parent_id": building["id"],
            "code": "F-1",
            "name": "重复",
            "node_type": "FLOOR",
        },
    )
    assert duplicate.status_code == 409
    tree = _data(client.get(f"/api/v1/spaces/tree?park_id={park['id']}"))
    assert tree[0]["children"][0]["children"][0]["id"] == floor["id"]

    active_children = client.delete(f"/api/v1/spaces/{area['id']}")
    assert active_children.status_code == 409
    assert active_children.json()["code"] == "SPACE_ACTIVE_DESCENDANTS"

    empty_summary = _data(
        client.get(f"/api/v1/rent-control/summary?park_id={park['id']}")
    )
    assert empty_summary["inventory_count"] == 0
    assert empty_summary["rentable_area"] == 0
    assert empty_summary["occupancy_rate"] == 0

    unit = _data(
        client.post(
            "/api/v1/units",
            json={
                "park_id": park["id"],
                "building_id": floor["id"],
                "code": "U-1",
                "name": "101",
                "rentable_area": 100,
                "used_area": 99,
            },
        )
    )
    assert unit["used_area"] == 0
    blocked = client.delete(f"/api/v1/spaces/{building['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "SPACE_IN_USE"


def test_unit_version_split_merge_and_lineage(client):
    park = _data(client.post("/api/v1/parks", json={"name": "拆并测试园"}))
    building = _data(
        client.post(
            "/api/v1/spaces",
            json={
                "park_id": park["id"],
                "code": "B-1",
                "name": "一号楼",
                "node_type": "BUILDING",
            },
        )
    )
    source = _data(
        client.post(
            "/api/v1/units",
            json={
                "park_id": park["id"],
                "building_id": building["id"],
                "code": "101",
                "name": "101",
                "rentable_area": 100,
            },
        )
    )
    version = _data(
        client.post(
            f"/api/v1/units/{source['id']}/versions",
            json={"expected_lock_version": 1, "rentable_area": 120},
        )
    )
    assert version["version_no"] == 2
    assert version["supersedes_id"] == source["id"]
    history = _data(client.get(f"/api/v1/units/{version['id']}/history"))
    assert [row["version_no"] for row in history] == [2, 1]

    stale = client.post(
        f"/api/v1/units/{version['id']}/versions",
        json={"expected_lock_version": 9, "rentable_area": 130},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "UNIT_VERSION_CONFLICT"

    split = _data(
        client.post(
            "/api/v1/units/split",
            json={
                "unit_id": version["id"],
                "expected_lock_version": 1,
                "targets": [
                    {"code": "101-A", "name": "101A", "rentable_area": 50},
                    {"code": "101-B", "name": "101B", "rentable_area": 70},
                ],
            },
        )
    )
    assert sum(row["rentable_area"] for row in split["targets"]) == 120
    lineage = _data(client.get(f"/api/v1/units/{version['id']}/lineage"))
    assert len(lineage) == 2
    assert {row["operation_type"] for row in lineage} == {"SPLIT"}

    targets = split["targets"]
    merged = _data(
        client.post(
            "/api/v1/units/merge",
            json={
                "sources": [
                    {"unit_id": targets[0]["id"], "expected_lock_version": 1},
                    {"unit_id": targets[1]["id"], "expected_lock_version": 1},
                ],
                "code": "101-M",
                "name": "101合并",
            },
        )
    )
    assert merged["target"]["rentable_area"] == 120
    current = _data(client.get(f"/api/v1/units?park_id={park['id']}"))
    assert current["total"] == 1
    assert current["items"][0]["id"] == merged["target"]["id"]

    summary = _data(client.get(f"/api/v1/rent-control/summary?park_id={park['id']}"))
    assert summary == {
        "inventory_count": 1,
        "rentable_area": 120.0,
        "used_area": 0.0,
        "available_area": 120.0,
        "occupancy_rate": 0,
        "status_counts": {
            "DRAFT": 0,
            "VACANT": 1,
            "RESERVED": 0,
            "OCCUPIED": 0,
            "MAINTENANCE": 0,
            "RETIRED": 0,
        },
    }
    rent_units = _data(
        client.get(
            f"/api/v1/rent-control/units?park_id={park['id']}&space_id={building['id']}&keyword=101-M"
        )
    )
    assert rent_units["total"] == 1
    assert rent_units["items"][0]["space_code"] == "B-1"
    matrix = _data(client.get(f"/api/v1/rent-control/matrix?park_id={park['id']}"))
    assert len(matrix) == 1
    assert matrix[0]["units"][0]["id"] == merged["target"]["id"]
    detail = _data(client.get(f"/api/v1/rent-control/units/{merged['target']['id']}"))
    assert detail["can_split_merge"] is True
    assert detail["blocking_reason"] is None
    assert len(detail["lineage"]) == 2
    assert detail["effective_leases"] == []
    assert detail["work_orders"] == []
