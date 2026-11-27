from __future__ import annotations

from fastapi.testclient import TestClient


def test_presets_returns_five_versioned_marketplace_presets(client: TestClient) -> None:
    res = client.get("/v1/presets")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 5
    presets = body["presets"]
    assert len(presets) == 5

    by_id = {item["id"]: item for item in presets}
    assert set(by_id.keys()) == {
        "shopee_1_1",
        "tiktok_3_4",
        "tiktok_1_1",
        "lazada_1_1",
        "amazon_white_85",
    }

    assert by_id["shopee_1_1"]["width"] == 1024
    assert by_id["shopee_1_1"]["height"] == 1024
    assert by_id["shopee_1_1"]["safe_zone"] == {"top": 0.04, "right": 0.04, "bottom": 0.04, "left": 0.04}
    assert by_id["shopee_1_1"]["is_system"] is True
    assert by_id["shopee_1_1"]["editable"] is True
    assert by_id["shopee_1_1"]["rule_description_en"]
    assert by_id["shopee_1_1"]["rule_description_vi"]
    assert by_id["shopee_1_1"]["created_at"]
    assert by_id["shopee_1_1"]["updated_at"]

    assert by_id["tiktok_3_4"]["width"] == 1200
    assert by_id["tiktok_3_4"]["height"] == 1600
    assert by_id["tiktok_3_4"]["safe_zone"] == {"top": 0.08, "right": 0.14, "bottom": 0.22, "left": 0.06}
    assert by_id["tiktok_1_1"]["width"] == 1024
    assert by_id["tiktok_1_1"]["height"] == 1024
    assert by_id["lazada_1_1"]["width"] == 1000
    assert by_id["lazada_1_1"]["height"] == 1000
    assert by_id["amazon_white_85"]["background_rgb"] == [255, 255, 255]
    assert by_id["amazon_white_85"]["subject_area_ratio"] == 0.85


def test_preset_crud_validation_and_system_reset(client: TestClient) -> None:
    # 1. GET single preset & 404 unified envelope
    single = client.get("/v1/presets/amazon_white_85")
    assert single.status_code == 200
    assert single.json()["id"] == "amazon_white_85"

    missing = client.get("/v1/presets/does_not_exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"

    # 2. POST custom preset (explicit ID + auto ID)
    create_res = client.post(
        "/v1/presets",
        json={
            "id": "custom_instagram_4_5",
            "marketplace": "custom",
            "name_en": "Instagram Portrait 4:5",
            "name_vi": "Instagram Dọc 4:5",
            "rule_description_en": "Portrait social feed card",
            "rule_description_vi": "Thẻ bài đăng dọc mạng xã hội",
            "width": 1080,
            "height": 1350,
            "formats": ["webp", "jpg"],
            "background_rgb": [248, 249, 250],
            "subject_area_ratio": 0.8,
            "safe_zone": {"top": 0.05, "right": 0.05, "bottom": 0.1, "left": 0.05},
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["id"] == "custom_instagram_4_5"
    assert created["aspect_ratio"] == "4:5"
    assert created["formats"] == ["webp", "jpeg"]
    assert created["is_system"] is False
    assert created["editable"] is True

    # Duplicate ID returns 409 CONFLICT
    dup_res = client.post(
        "/v1/presets",
        json={
            "id": "custom_instagram_4_5",
            "name_en": "Duplicate",
            "width": 1000,
            "height": 1000,
        },
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["code"] == "CONFLICT"

    # Auto-generated ID
    auto_res = client.post(
        "/v1/presets",
        json={
            "name_en": "Flash Sale Banner",
            "width": 1200,
            "height": 600,
        },
    )
    assert auto_res.status_code == 201
    auto_preset = auto_res.json()
    assert auto_preset["id"].startswith("custom_")
    assert auto_preset["aspect_ratio"] == "2:1"
    assert auto_preset["marketplace"] == "custom"

    # 3. Validation failures -> 422 VALIDATION_ERROR
    invalid_payloads = [
        {"name_en": "Bad Dim", "width": 10, "height": 1000},
        {"name_en": "Bad RGB", "width": 1000, "height": 1000, "background_rgb": [256, 0, 0]},
        {"name_en": "Bad Ratio", "width": 1000, "height": 1000, "subject_area_ratio": 1.2},
        {"name_en": "Bad Format", "width": 1000, "height": 1000, "formats": ["gif"]},
        {
            "name_en": "Bad SafeZone",
            "width": 1000,
            "height": 1000,
            "safe_zone": {"top": 0.5, "right": 0.6, "bottom": 0.1, "left": 0.5},
        },
    ]
    for bad in invalid_payloads:
        bad_res = client.post("/v1/presets", json=bad)
        assert bad_res.status_code == 422
        assert bad_res.json()["code"] == "VALIDATION_ERROR"

    # 4. PATCH & PUT update custom preset + clear nullable fields
    patch_res = client.patch(
        f"/v1/presets/{created['id']}",
        json={
            "width": 1600,
            "height": 1600,
            "background_rgb": None,
            "safe_zone": None,
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["width"] == 1600
    assert patched["height"] == 1600
    assert patched["aspect_ratio"] == "1:1"
    assert patched["background_rgb"] is None
    assert patched["safe_zone"] is None

    put_res = client.put(
        f"/v1/presets/{created['id']}",
        json={
            "name_en": "Instagram Square Updated",
            "width": 1080,
            "height": 1080,
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["name_en"] == "Instagram Square Updated"

    # 5. Customize system preset, cannot delete (403 FORBIDDEN), can reset (200)
    edit_sys = client.patch(
        "/v1/presets/shopee_1_1",
        json={"width": 1500, "height": 1500, "background_rgb": [255, 255, 255]},
    )
    assert edit_sys.status_code == 200
    assert edit_sys.json()["width"] == 1500
    assert edit_sys.json()["is_system"] is True

    del_sys = client.delete("/v1/presets/shopee_1_1")
    assert del_sys.status_code == 403
    assert del_sys.json()["code"] == "FORBIDDEN"

    reset_sys = client.post("/v1/presets/shopee_1_1/reset")
    assert reset_sys.status_code == 200
    restored = reset_sys.json()
    assert restored["width"] == 1024
    assert restored["height"] == 1024
    assert restored["background_rgb"] is None

    # Cannot reset custom preset -> 400
    reset_custom = client.post(f"/v1/presets/{created['id']}/reset")
    assert reset_custom.status_code == 400

    # 6. Delete custom preset -> 200, then 404
    del_custom = client.delete(f"/v1/presets/{created['id']}")
    assert del_custom.status_code == 200
    assert del_custom.json() == {"deleted": True, "preset_id": created["id"]}
    assert client.get(f"/v1/presets/{created['id']}").status_code == 404
    assert client.delete("/v1/presets/non_existent").status_code == 404


def _assert_unified_validation_422(res) -> None:
    assert res.status_code == 422
    body = res.json()
    assert "detail" not in body
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["correlation_id"], str) and body["correlation_id"]
    assert body["retryable"] is False
    assert res.headers.get("x-correlation-id") == body["correlation_id"]


def test_presets_reject_boolean_coercion_and_unify_validation_errors(client: TestClient) -> None:
    bool_post_payloads = [
        {"name_en": "Bool Ratio", "width": 1000, "height": 1000, "subject_area_ratio": True},
        {"name_en": "Bool RGB", "width": 1000, "height": 1000, "background_rgb": [True, 0, 0]},
        {
            "name_en": "Bool SafeZone",
            "width": 1000,
            "height": 1000,
            "safe_zone": {"top": False, "right": 0.1, "bottom": 0.0, "left": 0.1},
        },
        {"name_en": "Bool Width", "width": True, "height": 1000},
        {"name_en": "Bool Height", "width": 1000, "height": False},
    ]
    for payload in bool_post_payloads:
        _assert_unified_validation_422(client.post("/v1/presets", json=payload))

    bool_patch_payloads = [
        {"subject_area_ratio": True},
        {"background_rgb": [True, 0, 0]},
        {"background_rgb": [False, False, False]},
        {"safe_zone": {"top": False, "right": 0.1, "bottom": 0.0, "left": 0.1}},
        {"width": True},
    ]
    for payload in bool_patch_payloads:
        _assert_unified_validation_422(client.patch("/v1/presets/shopee_1_1", json=payload))

    malformed_payloads = [
        {"name_en": "Bad Width Type", "width": "not_int", "height": 1000},
        {"name_en": "Bad Formats Type", "width": 1000, "height": 1000, "formats": "webp"},
        {"width": 1000, "height": 1000},  # missing name_en
        {"name_en": "Partial SafeZone", "width": 1000, "height": 1000, "safe_zone": {"top": 0.1}},
    ]
    for payload in malformed_payloads:
        _assert_unified_validation_422(client.post("/v1/presets", json=payload))

    # Integer JSON values (1 / 0) for float fields remain accepted while booleans are rejected
    int_float_res = client.post(
        "/v1/presets",
        json={
            "id": "custom_int_float_ok",
            "name_en": "Int As Float",
            "width": 1000,
            "height": 1000,
            "subject_area_ratio": 1,
            "safe_zone": {"top": 0, "right": 0, "bottom": 0, "left": 0},
        },
    )
    assert int_float_res.status_code == 201
    created = int_float_res.json()
    assert created["subject_area_ratio"] == 1.0
    assert created["safe_zone"] == {"top": 0.0, "right": 0.0, "bottom": 0.0, "left": 0.0}
