from __future__ import annotations

from app.core.security import create_access_token


def _data(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _headers(*permissions: str) -> dict[str, str]:
    token = create_access_token(
        subject="admin",
        claims={
            "uid": 1,
            "tenant_id": 1,
            "permissions": list(permissions) or ["*"],
            "park_ids": [],
            "park_scope_mode": "ALL",
        },
    )
    return {"Authorization": f"Bearer {token}"}


def test_builtin_templates_custom_lifecycle_and_stale_conflict(client):
    headers = _headers()
    templates = _data(client.get("/api/v1/asset-templates", headers=headers))
    assert {row["code"] for row in templates} == {
        "FACTORY",
        "WAREHOUSE",
        "SHOP",
        "OFFICE",
        "DORMITORY",
        "PARKING",
        "PUBLIC_SPACE",
    }
    assert all(row["published"]["status"] == "PUBLISHED" for row in templates)
    repeated = _data(client.get("/api/v1/asset-templates", headers=headers))
    assert [row["id"] for row in repeated] == [row["id"] for row in templates]

    created = _data(
        client.post(
            "/api/v1/asset-templates",
            headers=headers,
            json={
                "code": "COLD_WAREHOUSE",
                "name": "冷链仓",
                "category": "WAREHOUSE",
                "fields": [
                    {
                        "key": "temperature",
                        "label": "目标温度",
                        "type": "NUMBER",
                        "required": True,
                        "min": -80,
                        "max": 30,
                        "unit": "℃",
                    }
                ],
            },
        )
    )
    assert created["current_version"] == 0
    assert created["draft"]["version"] == 1
    published = _data(
        client.post(
            f"/api/v1/asset-templates/{created['id']}/publish",
            headers=headers,
            json={"expected_version": created["lock_version"]},
        )
    )
    assert published["current_version"] == 1
    assert published["published"]["schema_checksum"]
    stale = client.post(
        f"/api/v1/asset-templates/{created['id']}/drafts",
        headers=headers,
        json={"expected_version": created["lock_version"]},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "ASSET_TEMPLATE_VERSION_CONFLICT"

    invalid = client.post(
        "/api/v1/asset-templates",
        headers=headers,
        json={
            "code": "UNSAFE",
            "name": "不安全模板",
            "category": "OFFICE",
            "fields": [{"key": "script", "label": "https://unsafe.example", "type": "TEXT"}],
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "ASSET_TEMPLATE_INVALID"


def test_geometry_template_binding_map_vacancy_analysis_and_version_history(client):
    headers = _headers()
    park = _data(client.post("/api/v1/parks", headers=headers, json={"name": "多业态园"}))
    templates = _data(client.get("/api/v1/asset-templates", headers=headers))
    office = next(row for row in templates if row["code"] == "OFFICE")
    office_version_id = office["published"]["id"]
    building = _data(
        client.post(
            "/api/v1/spaces",
            headers=headers,
            json={
                "park_id": park["id"],
                "code": "OFFICE-1",
                "name": "研发办公楼",
                "node_type": "BUILDING",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [120, 0], [120, 80], [0, 80], [0, 0]]],
                },
                "coordinate_reference": "LOCAL",
            },
        )
    )
    assert building["geometry_version"] == 1
    unit = _data(
        client.post(
            "/api/v1/units",
            headers=headers,
            json={
                "park_id": park["id"],
                "building_id": building["id"],
                "code": "O-101",
                "name": "研发办公室 101",
                "rentable_area": 120,
                "base_rent_price": 3.5,
                "usage_type": "OFFICE",
                "asset_template_version_id": office_version_id,
                "attributes": {"workstation_capacity": 18, "fitout_grade": "PREMIUM"},
            },
        )
    )
    assert unit["usage_type"] == "OFFICE"
    assert unit["asset_template_version_id"] == office_version_id

    detail = _data(client.get(f"/api/v1/rent-control/units/{unit['id']}", headers=headers))
    assert detail["asset_template"]["template_code"] == "OFFICE"
    assert detail["asset_template"]["version_id"] == office_version_id

    map_data = _data(client.get(f"/api/v1/rent-control/map?park_id={park['id']}", headers=headers))
    assert map_data["provider_status"] == "NOT_CONNECTED_LOCAL_SCHEMATIC"
    assert map_data["unmapped_inventory_count"] == 0
    assert map_data["features"][0]["geometry"]["type"] == "Polygon"
    assert map_data["features"][0]["properties"]["rentable_area"] == 120

    vacancies = _data(
        client.get(f"/api/v1/rent-control/vacancies?park_id={park['id']}", headers=headers)
    )
    assert vacancies["total"] == 1
    assert vacancies["items"][0]["available_area"] == 120
    analysis = _data(
        client.get(f"/api/v1/rent-control/analysis?park_id={park['id']}", headers=headers)
    )
    assert analysis["summary"]["rentable_area"] == 120
    assert analysis["categories"][0]["key"] == "OFFICE"
    assert analysis["asking_rent_potential"] == 420
    assert "非会计收入" in analysis["asking_rent_potential_label"]

    changed = _data(
        client.post(
            f"/api/v1/units/{unit['id']}/versions",
            headers=headers,
            json={
                "expected_lock_version": 1,
                "rentable_area": 100,
                "asset_template_version_id": office_version_id,
                "attributes": {"workstation_capacity": 16, "fitout_grade": "STANDARD"},
            },
        )
    )
    assert changed["version_no"] == 2
    history = _data(client.get(f"/api/v1/units/{changed['id']}/history", headers=headers))
    assert [row["asset_template_version_id"] for row in history] == [
        office_version_id,
        office_version_id,
    ]

    maintained = _data(
        client.patch(
            f"/api/v1/units/{changed['id']}/status",
            headers=headers,
            json={"status": "MAINTENANCE"},
        )
    )
    assert maintained["status"] == "MAINTENANCE"
    unavailable = _data(
        client.get(f"/api/v1/rent-control/vacancies?park_id={park['id']}", headers=headers)
    )
    assert unavailable["total"] == 0
    unavailable_analysis = _data(
        client.get(f"/api/v1/rent-control/analysis?park_id={park['id']}", headers=headers)
    )
    assert unavailable_analysis["asking_rent_potential"] == 0

    stale_geometry = client.patch(
        f"/api/v1/spaces/{building['id']}",
        headers=headers,
        json={
            "expected_geometry_version": 9,
            "geometry": {"type": "Point", "coordinates": [10, 20]},
            "coordinate_reference": "LOCAL",
        },
    )
    assert stale_geometry.status_code == 409
    assert stale_geometry.json()["code"] == "SPACE_GEOMETRY_VERSION_CONFLICT"


def test_required_template_attribute_and_template_write_permission(client):
    headers = _headers()
    custom = _data(
        client.post(
            "/api/v1/asset-templates",
            headers=headers,
            json={
                "code": "REQUIRED_OFFICE",
                "name": "强校验办公室",
                "category": "OFFICE",
                "fields": [
                    {"key": "capacity", "label": "容量", "type": "NUMBER", "required": True}
                ],
            },
        )
    )
    custom = _data(
        client.post(
            f"/api/v1/asset-templates/{custom['id']}/publish",
            headers=headers,
            json={"expected_version": custom["lock_version"]},
        )
    )
    park = _data(client.post("/api/v1/parks", headers=headers, json={"name": "校验园"}))
    building = _data(
        client.post(
            "/api/v1/spaces",
            headers=headers,
            json={"park_id": park["id"], "code": "B1", "name": "一号楼", "node_type": "BUILDING"},
        )
    )
    rejected = client.post(
        "/api/v1/units",
        headers=headers,
        json={
            "park_id": park["id"],
            "building_id": building["id"],
            "code": "MISS",
            "name": "缺字段",
            "rentable_area": 10,
            "usage_type": "OFFICE",
            "asset_template_version_id": custom["published"]["id"],
            "attributes": {},
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "ASSET_ATTRIBUTES_INVALID"

    read_only = _headers("asset.template.read")
    visible = client.get("/api/v1/asset-templates", headers=read_only)
    assert visible.status_code == 200
    forbidden = client.post(
        "/api/v1/asset-templates",
        headers=read_only,
        json={"code": "NOPE", "name": "无权", "category": "OFFICE", "fields": []},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "PERMISSION_DENIED"


def test_template_category_blank_name_and_simple_polygon_guards(client):
    headers = _headers()
    templates = _data(client.get("/api/v1/asset-templates", headers=headers))
    office = next(row for row in templates if row["code"] == "OFFICE")

    draft = _data(
        client.post(
            "/api/v1/asset-templates",
            headers=headers,
            json={
                "code": "BLANK_NAME_GUARD",
                "name": "待校验模板",
                "category": "OFFICE",
                "fields": [],
            },
        )
    )
    blank_name = client.put(
        f"/api/v1/asset-templates/{draft['id']}/draft",
        headers=headers,
        json={"expected_version": draft["lock_version"], "name": "   "},
    )
    assert blank_name.status_code == 400
    assert blank_name.json()["code"] == "ASSET_TEMPLATE_INVALID"

    park = _data(client.post("/api/v1/parks", headers=headers, json={"name": "边界校验园"}))
    building = _data(
        client.post(
            "/api/v1/spaces",
            headers=headers,
            json={
                "park_id": park["id"],
                "code": "VALID-BUILDING",
                "name": "有效楼栋",
                "node_type": "BUILDING",
            },
        )
    )
    mismatch = client.post(
        "/api/v1/units",
        headers=headers,
        json={
            "park_id": park["id"],
            "building_id": building["id"],
            "code": "WRONG-TEMPLATE",
            "name": "错误模板单元",
            "rentable_area": 10,
            "usage_type": "FACTORY",
            "asset_template_version_id": office["published"]["id"],
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["code"] == "ASSET_TEMPLATE_CATEGORY_MISMATCH"

    self_intersection = client.post(
        "/api/v1/spaces",
        headers=headers,
        json={
            "park_id": park["id"],
            "code": "BOW-TIE",
            "name": "自交楼栋",
            "node_type": "BUILDING",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [4, 4], [0, 4], [4, 0], [0, 0]]],
            },
            "coordinate_reference": "LOCAL",
        },
    )
    assert self_intersection.status_code == 400
    assert self_intersection.json()["code"] == "SPACE_GEOMETRY_INVALID"
