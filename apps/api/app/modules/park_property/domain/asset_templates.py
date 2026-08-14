"""Pure domain validation for versioned asset templates and spatial geometry."""

from __future__ import annotations

import json
import math
import re
from hashlib import sha256
from typing import Any

ASSET_CATEGORIES = {
    "FACTORY",
    "WAREHOUSE",
    "SHOP",
    "OFFICE",
    "DORMITORY",
    "PARKING",
    "PUBLIC_SPACE",
}
FIELD_TYPES = {"TEXT", "NUMBER", "BOOLEAN", "ENUM"}
COORDINATE_REFERENCES = {"LOCAL", "WGS84", "GCJ02", "BD09"}
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_UNSAFE = re.compile(r"https?://|javascript:|\b(select|insert|update|delete|drop|exec)\b", re.I)

BUILTIN_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "code": "FACTORY",
        "name": "工业厂房",
        "category": "FACTORY",
        "fields": [
            {
                "key": "clear_height",
                "label": "层高",
                "type": "NUMBER",
                "unit": "m",
                "min": 0,
                "max": 100,
            },
            {
                "key": "floor_load",
                "label": "楼面荷载",
                "type": "NUMBER",
                "unit": "kN/㎡",
                "min": 0,
                "max": 500,
            },
            {
                "key": "power_capacity",
                "label": "供电容量",
                "type": "NUMBER",
                "unit": "kVA",
                "min": 0,
                "max": 100000,
            },
        ],
    },
    {
        "code": "WAREHOUSE",
        "name": "仓库物流",
        "category": "WAREHOUSE",
        "fields": [
            {
                "key": "clear_height",
                "label": "净高",
                "type": "NUMBER",
                "unit": "m",
                "min": 0,
                "max": 100,
            },
            {
                "key": "floor_load",
                "label": "楼面荷载",
                "type": "NUMBER",
                "unit": "kN/㎡",
                "min": 0,
                "max": 500,
            },
            {"key": "temperature_controlled", "label": "温控仓", "type": "BOOLEAN"},
        ],
    },
    {
        "code": "SHOP",
        "name": "商铺",
        "category": "SHOP",
        "fields": [
            {
                "key": "frontage",
                "label": "临街面宽",
                "type": "NUMBER",
                "unit": "m",
                "min": 0,
                "max": 1000,
            },
            {"key": "business_category", "label": "建议业态", "type": "TEXT"},
        ],
    },
    {
        "code": "OFFICE",
        "name": "写字楼办公室",
        "category": "OFFICE",
        "fields": [
            {
                "key": "workstation_capacity",
                "label": "建议工位",
                "type": "NUMBER",
                "unit": "seat",
                "min": 0,
                "max": 10000,
            },
            {
                "key": "fitout_grade",
                "label": "装修等级",
                "type": "ENUM",
                "options": ["BARE", "STANDARD", "PREMIUM"],
            },
        ],
    },
    {
        "code": "DORMITORY",
        "name": "宿舍人才公寓",
        "category": "DORMITORY",
        "fields": [
            {
                "key": "bed_count",
                "label": "床位数",
                "type": "NUMBER",
                "unit": "bed",
                "min": 0,
                "max": 1000,
            },
            {"key": "furnished", "label": "配套家具", "type": "BOOLEAN"},
        ],
    },
    {
        "code": "PARKING",
        "name": "停车位",
        "category": "PARKING",
        "fields": [
            {
                "key": "vehicle_type",
                "label": "车辆类型",
                "type": "ENUM",
                "options": ["CAR", "TRUCK", "MOTORCYCLE"],
            },
            {"key": "charging_ready", "label": "充电条件", "type": "BOOLEAN"},
        ],
    },
    {
        "code": "PUBLIC_SPACE",
        "name": "公共场地",
        "category": "PUBLIC_SPACE",
        "fields": [
            {"key": "venue_type", "label": "场地类型", "type": "TEXT"},
            {
                "key": "capacity",
                "label": "建议容量",
                "type": "NUMBER",
                "unit": "person",
                "min": 0,
                "max": 100000,
            },
        ],
    },
)


def normalize_category(value: object) -> str:
    category = str(value or "").strip().upper()
    aliases = {"APARTMENT": "DORMITORY", "RETAIL": "SHOP", "VENUE": "PUBLIC_SPACE"}
    category = aliases.get(category, category)
    if category not in ASSET_CATEGORIES:
        raise ValueError("资产模板类别不合法")
    return category


def validate_field_schema(
    fields: object, defaults: object | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    if not isinstance(fields, list) or len(fields) > 32:
        raise ValueError("模板字段必须为最多 32 项的数组")
    normalized: list[dict[str, Any]] = []
    keys: set[str] = set()
    for position, raw in enumerate(fields):
        if not isinstance(raw, dict):
            raise ValueError("模板字段必须为对象")
        key = str(raw.get("key") or "").strip()
        label = str(raw.get("label") or "").strip()
        field_type = str(raw.get("type") or "").upper()
        if not _KEY.fullmatch(key) or key in keys:
            raise ValueError("模板字段 key 不合法或重复")
        if not label or len(label) > 64 or _UNSAFE.search(label):
            raise ValueError("模板字段 label 不合法")
        if field_type not in FIELD_TYPES:
            raise ValueError("模板字段类型不合法")
        item: dict[str, Any] = {
            "key": key,
            "label": label,
            "type": field_type,
            "required": bool(raw.get("required", False)),
            "position": position,
        }
        unit = raw.get("unit")
        if unit is not None:
            unit = str(unit).strip()
            if len(unit) > 16 or _UNSAFE.search(unit):
                raise ValueError("模板字段单位不合法")
            item["unit"] = unit
        if field_type == "NUMBER":
            for bound in ("min", "max"):
                if raw.get(bound) is not None:
                    value = float(raw[bound])
                    if not math.isfinite(value):
                        raise ValueError("模板数值边界不合法")
                    item[bound] = value
            if (
                item.get("min") is not None
                and item.get("max") is not None
                and item["min"] > item["max"]
            ):
                raise ValueError("模板数值边界顺序不合法")
        if field_type == "ENUM":
            options = raw.get("options")
            if not isinstance(options, list) or not 1 <= len(options) <= 32:
                raise ValueError("枚举字段必须包含 1 到 32 个选项")
            clean = [str(option).strip() for option in options]
            if any(
                not option or len(option) > 64 or _UNSAFE.search(option) for option in clean
            ) or len(clean) != len(set(clean)):
                raise ValueError("枚举选项不合法或重复")
            item["options"] = clean
        keys.add(key)
        normalized.append(item)
    clean_defaults = validate_attributes(defaults or {}, normalized, require_all=False)
    payload = {"fields": normalized, "defaults": clean_defaults}
    checksum = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return normalized, clean_defaults, checksum


def validate_attributes(
    attributes: object, fields: list[dict[str, Any]], *, require_all: bool = True
) -> dict[str, Any]:
    if attributes is None:
        attributes = {}
    if not isinstance(attributes, dict) or len(attributes) > 32:
        raise ValueError("资产属性必须为最多 32 项的对象")
    definitions = {field["key"]: field for field in fields}
    unknown = sorted(set(str(key) for key in attributes) - set(definitions))
    if unknown:
        raise ValueError(f"资产属性包含模板未定义字段: {', '.join(unknown[:5])}")
    result: dict[str, Any] = {}
    for key, definition in definitions.items():
        if key not in attributes or attributes[key] is None or attributes[key] == "":
            if require_all and definition.get("required"):
                raise ValueError(f"资产属性 {key} 必填")
            continue
        value = attributes[key]
        field_type = definition["type"]
        if field_type == "TEXT":
            if not isinstance(value, str) or len(value) > 500 or _UNSAFE.search(value):
                raise ValueError(f"资产属性 {key} 文本不合法")
        elif field_type == "BOOLEAN":
            if not isinstance(value, bool):
                raise ValueError(f"资产属性 {key} 必须为布尔值")
        elif field_type == "NUMBER":
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise ValueError(f"资产属性 {key} 必须为数值")
            if definition.get("min") is not None and float(value) < float(definition["min"]):
                raise ValueError(f"资产属性 {key} 低于最小值")
            if definition.get("max") is not None and float(value) > float(definition["max"]):
                raise ValueError(f"资产属性 {key} 高于最大值")
        elif field_type == "ENUM" and value not in definition.get("options", []):
            raise ValueError(f"资产属性 {key} 不在允许选项中")
        result[key] = value
    return result


def validate_geometry(
    geometry: object, coordinate_reference: object
) -> tuple[dict[str, Any], str, str]:
    if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
        raise ValueError("几何必须是仅含 type/coordinates 的 GeoJSON 对象")
    geometry_type = str(geometry.get("type") or "")
    if geometry_type not in {"Point", "Polygon"}:
        raise ValueError("仅支持 Point 或 Polygon")
    crs = str(coordinate_reference or "").upper()
    if crs not in COORDINATE_REFERENCES:
        raise ValueError("坐标参考不合法")

    def point(raw: object) -> list[float]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError("坐标点必须包含两个数值")
        values = [float(raw[0]), float(raw[1])]
        if not all(math.isfinite(value) and -1_000_000 <= value <= 1_000_000 for value in values):
            raise ValueError("坐标超出允许范围")
        if crs != "LOCAL" and not (-180 <= values[0] <= 180 and -90 <= values[1] <= 90):
            raise ValueError("经纬度超出范围")
        return values

    if geometry_type == "Point":
        coordinates: Any = point(geometry["coordinates"])
    else:
        raw = geometry["coordinates"]
        if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], list):
            raise ValueError("仅支持无洞简单多边形")
        ring = [point(item) for item in raw[0]]
        if not 4 <= len(ring) <= 256 or ring[0] != ring[-1]:
            raise ValueError("多边形必须闭合且包含 4 到 256 个点")
        vertices = ring[:-1]
        if len({tuple(item) for item in vertices}) < 3:
            raise ValueError("多边形必须包含至少三个不同顶点")

        twice_area = sum(
            vertices[index][0] * vertices[(index + 1) % len(vertices)][1]
            - vertices[(index + 1) % len(vertices)][0] * vertices[index][1]
            for index in range(len(vertices))
        )
        if abs(twice_area) <= 1e-12:
            raise ValueError("多边形面积必须大于零")

        def orientation(a: list[float], b: list[float], c: list[float]) -> float:
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on_segment(a: list[float], b: list[float], c: list[float]) -> bool:
            return (
                min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
                and min(a[1], c[1]) <= b[1] <= max(a[1], c[1])
            )

        def intersects(
            a: list[float], b: list[float], c: list[float], d: list[float]
        ) -> bool:
            o1, o2 = orientation(a, b, c), orientation(a, b, d)
            o3, o4 = orientation(c, d, a), orientation(c, d, b)
            if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
                return True
            epsilon = 1e-12
            return any(
                abs(value) <= epsilon and on_segment(start, candidate, end)
                for value, start, candidate, end in (
                    (o1, a, c, b),
                    (o2, a, d, b),
                    (o3, c, a, d),
                    (o4, c, b, d),
                )
            )

        edge_count = len(vertices)
        for first in range(edge_count):
            for second in range(first + 1, edge_count):
                if second == first + 1 or (first == 0 and second == edge_count - 1):
                    continue
                if intersects(
                    vertices[first],
                    vertices[(first + 1) % edge_count],
                    vertices[second],
                    vertices[(second + 1) % edge_count],
                ):
                    raise ValueError("多边形边界不能自交或重叠")
        coordinates = [ring]
    canonical = {"type": geometry_type, "coordinates": coordinates}
    if len(json.dumps(canonical, separators=(",", ":")).encode()) > 16_384:
        raise ValueError("几何数据过大")
    return canonical, geometry_type.upper(), crs
