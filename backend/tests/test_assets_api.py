from __future__ import annotations

import hashlib
import io
import json

from fastapi.testclient import TestClient
from PIL import Image


def _make_bytes(
    fmt: str,
    mode: str = "RGB",
    size: tuple[int, int] = (32, 24),
    color: tuple[int, ...] = (79, 70, 229),
) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color=color).save(buf, format=fmt)
    return buf.getvalue()


def test_asset_upload_sha256_and_immutable_download(client: TestClient) -> None:
    proj = client.post("/v1/projects", json={"name": "Asset Test"}).json()
    project_id = proj["id"]

    for ext, mime, fmt, mode in [
        ("jpg", "image/jpeg", "JPEG", "RGB"),
        ("png", "image/png", "PNG", "RGBA"),
        ("webp", "image/webp", "WEBP", "RGBA"),
    ]:
        raw = _make_bytes(fmt, mode=mode)
        expected_sha = hashlib.sha256(raw).hexdigest()

        upload_res = client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": (f"product.{ext}", raw, mime)},
        )
        assert upload_res.status_code == 201
        meta = upload_res.json()
        assert meta["id"] == meta["asset_id"]
        assert meta["project_id"] == project_id
        assert meta["kind"] == "original"
        assert meta["parent_asset_id"] is None
        assert meta["variant"] == "default"
        assert meta["metadata"] == {}
        assert meta["file_url"] == f"/v1/assets/{meta['id']}/file"
        assert meta["sha256"] == expected_sha
        assert meta["width"] == 32
        assert meta["height"] == 24
        assert meta["byte_size"] == len(raw)
        assert meta["mime_type"] == mime
        assert meta["is_readonly"] is True
        assert meta["updated_at"]

        file_res = client.get(f"/v1/assets/{meta['asset_id']}/file")
        assert file_res.status_code == 200
        assert file_res.content == raw
        assert file_res.headers["etag"] == f'"{expected_sha}"'
        assert file_res.headers["x-content-type-options"] == "nosniff"


def test_asset_upload_rejects_spoofed_mime_and_missing_project(client: TestClient) -> None:
    missing_proj_res = client.post(
        "/v1/projects/missing-id/assets",
        files={"file": ("a.png", _make_bytes("PNG"), "image/png")},
    )
    assert missing_proj_res.status_code == 404
    assert missing_proj_res.json()["code"] == "NOT_FOUND"

    proj = client.post("/v1/projects", json={"name": "Security Check"}).json()
    spoof_res = client.post(
        f"/v1/projects/{proj['id']}/assets",
        files={"file": ("fake.jpg", _make_bytes("PNG"), "image/jpeg")},
    )
    assert spoof_res.status_code == 422
    err = spoof_res.json()
    assert err["code"] == "MIME_SPOOF_DETECTED"
    assert err["retryable"] is False
    assert "correlation_id" in err

    missing_asset_res = client.get("/v1/assets/missing-asset/file")
    assert missing_asset_res.status_code == 404
    assert missing_asset_res.json()["code"] == "NOT_FOUND"


def test_derived_assets_filtering_patch_and_delete_set_null(client: TestClient) -> None:
    proj = client.post("/v1/projects", json={"name": "Derived Pipeline"}).json()
    project_id = proj["id"]
    other_proj = client.post("/v1/projects", json={"name": "Other Project"}).json()

    orig_bytes = _make_bytes("PNG", mode="RGBA", color=(10, 20, 30, 255))
    orig = client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("hero.png", orig_bytes, "image/png")},
    ).json()
    orig_id = orig["id"]

    # Derived mask & ai_output with parent_asset_id, variant, metadata_json
    mask_bytes = _make_bytes("PNG", mode="RGBA", color=(255, 255, 255, 255))
    mask_res = client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("hero_mask.png", mask_bytes, "image/png")},
        data={
            "kind": "mask",
            "parent_asset_id": orig_id,
            "variant": "shopee_1_1",
            "metadata_json": json.dumps({"model": "rmbg-1.4", "threshold": 0.5}),
        },
    )
    assert mask_res.status_code == 201
    mask = mask_res.json()
    assert mask["kind"] == "mask"
    assert mask["parent_asset_id"] == orig_id
    assert mask["variant"] == "shopee_1_1"
    assert mask["is_readonly"] is False
    assert mask["metadata"] == {"model": "rmbg-1.4", "threshold": 0.5}

    # Derived asset using exact same bytes as original must NOT collapse into the original row
    ai_res = client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("hero_ai.png", orig_bytes, "image/png")},
        data={
            "kind": "ai_output",
            "parent_asset_id": orig_id,
            "variant": "amazon_white_85",
            "metadata_json": '{"stage": "relight"}',
        },
    )
    assert ai_res.status_code == 201
    ai_out = ai_res.json()
    assert ai_out["id"] != orig_id
    assert ai_out["kind"] == "ai_output"
    assert ai_out["is_readonly"] is False

    # Validation checks
    assert (
        client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": ("bad_kind.png", mask_bytes, "image/png")},
            data={"kind": "vector"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": ("orig_parent.png", mask_bytes, "image/png")},
            data={"kind": "original", "parent_asset_id": orig_id},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": ("missing_parent.png", mask_bytes, "image/png")},
            data={"kind": "thumbnail", "parent_asset_id": "non-existent"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/v1/projects/{other_proj['id']}/assets",
            files={"file": ("cross_proj.png", mask_bytes, "image/png")},
            data={"kind": "thumbnail", "parent_asset_id": orig_id},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/projects/{project_id}/assets",
            files={"file": ("bad_meta.png", mask_bytes, "image/png")},
            data={"kind": "thumbnail", "metadata_json": "[1, 2, 3]"},
        ).status_code
        == 422
    )

    # Listing & filtering
    all_assets = client.get(f"/v1/projects/{project_id}/assets")
    assert all_assets.status_code == 200
    assert all_assets.json()["total"] == 3

    masks_only = client.get(f"/v1/projects/{project_id}/assets?kind=mask")
    assert masks_only.status_code == 200
    assert masks_only.json()["total"] == 1
    assert masks_only.json()["assets"][0]["id"] == mask["id"]

    by_parent = client.get(f"/v1/projects/{project_id}/assets?parent_asset_id={orig_id}")
    assert by_parent.status_code == 200
    assert by_parent.json()["total"] == 2

    # GET & PATCH asset
    get_res = client.get(f"/v1/assets/{mask['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == mask["id"]

    patch_res = client.patch(
        f"/v1/assets/{mask['id']}",
        json={
            "filename": "refined_mask.png",
            "variant": "tiktok_3_4",
            "metadata": {"model": "rmbg-2.0", "feather": 2},
        },
    )
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["filename"] == "refined_mask.png"
    assert patched["variant"] == "tiktok_3_4"
    assert patched["metadata"] == {"model": "rmbg-2.0", "feather": 2}

    assert client.patch(f"/v1/assets/{mask['id']}", json={"variant": "   "}).status_code == 422

    # Deleting original parent sets parent_asset_id = None on children (ON DELETE SET NULL)
    del_orig = client.delete(f"/v1/assets/{orig_id}")
    assert del_orig.status_code == 200
    assert del_orig.json() == {"deleted": True, "asset_id": orig_id}
    assert client.get(f"/v1/assets/{orig_id}").status_code == 404

    child_after = client.get(f"/v1/assets/{mask['id']}").json()
    assert child_after["parent_asset_id"] is None
    assert client.get(f"/v1/assets/{mask['id']}/file").status_code == 200


def test_ref_counted_blob_deletion_across_projects(client: TestClient) -> None:
    p1 = client.post("/v1/projects", json={"name": "Shared Blob 1"}).json()["id"]
    p2 = client.post("/v1/projects", json={"name": "Shared Blob 2"}).json()["id"]
    shared_bytes = _make_bytes("PNG", mode="RGBA", color=(12, 34, 56, 255))

    a1 = client.post(
        f"/v1/projects/{p1}/assets",
        files={"file": ("shared.png", shared_bytes, "image/png")},
    ).json()["id"]
    a2 = client.post(
        f"/v1/projects/{p2}/assets",
        files={"file": ("shared.png", shared_bytes, "image/png")},
    ).json()["id"]

    # Delete first project asset -> blob must still be readable via second project asset
    assert client.delete(f"/v1/assets/{a1}").status_code == 200
    file_res = client.get(f"/v1/assets/{a2}/file")
    assert file_res.status_code == 200
    assert file_res.content == shared_bytes


def test_patch_asset_enforces_filename_extension_matches_mime(client: TestClient) -> None:
    proj = client.post("/v1/projects", json={"name": "Patch Ext Check"}).json()
    png_bytes = _make_bytes("PNG", mode="RGBA", color=(30, 60, 90, 255))
    asset = client.post(
        f"/v1/projects/{proj['id']}/assets",
        files={"file": ("original_item.png", png_bytes, "image/png")},
    ).json()
    asset_id = asset["id"]

    for bad_name in ("evil.html", "photo.jpg", "no_extension"):
        bad_res = client.patch(f"/v1/assets/{asset_id}", json={"filename": bad_name})
        assert bad_res.status_code == 422
        err = bad_res.json()
        assert err["code"] == "VALIDATION_ERROR"
        assert "correlation_id" in err
        assert err["retryable"] is False

    ok_res = client.patch(f"/v1/assets/{asset_id}", json={"filename": "renamed_item.PNG"})
    assert ok_res.status_code == 200
    assert ok_res.json()["filename"] == "renamed_item.png"
