from __future__ import annotations

import hashlib
import io
import json
import threading
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.services.batch_worker import render_recipe_image


def _make_png(width: int = 300, height: int = 200, color: tuple[int, int, int, int] = (79, 70, 229, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_exif_rotated_jpeg(width: int = 120, height: int = 240) -> bytes:
    # Stored pixel dimensions are 120x240, EXIF Orientation=6 (90 CW -> 240x120 upright)
    im = Image.new("RGB", (width, height), (20, 140, 210))
    exif = im.getexif()
    exif[274] = 6
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif.tobytes(), quality=95)
    return buf.getvalue()


def _poll_batch_until_done(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/v1/batches/{job_id}")
        assert res.status_code == 200
        data = res.json()
        if data["status"] in ("completed", "partial_failed", "failed", "cancelled"):
            return data
        time.sleep(0.05)
    raise AssertionError(f"Batch job {job_id} did not finish within {timeout}s")


def test_batch_worker_renders_real_images_manifest_and_zip(
    client: TestClient, test_settings: Settings
) -> None:
    proj = client.post("/v1/projects", json={"name": "Batch Footwear"}).json()
    project_id = proj["id"]

    orig = client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("sneaker.png", _make_png(400, 200, (180, 40, 40, 255)), "image/png")},
    ).json()

    # Upload an AI_OUTPUT derived asset for shopee_1_1 (green) to verify prefer_ai_output
    client.post(
        f"/v1/projects/{project_id}/assets",
        files={"file": ("cutout_shopee.png", _make_png(200, 200, (20, 190, 60, 255)), "image/png")},
        data={
            "kind": "ai_output",
            "parent_asset_id": orig["id"],
            "variant": "shopee_1_1",
        },
    )

    submit_res = client.post(
        "/v1/batches",
        json={
            "project_id": project_id,
            "asset_ids": [orig["id"]],
            "recipes": [
                {"preset_id": "shopee_1_1", "format": "webp", "quality": 88},
                {"preset_id": "amazon_white_85", "format": "jpeg", "quality": 92},
                {"preset_id": "tiktok_3_4", "format": "png", "quality": 90},
            ],
            "include_shadow": True,
            "watermark_text": "KROMA Việt Nam",
            "adjustments": {"brightness": 1.05, "contrast": 1.05, "saturation": 1.0, "sharpness": 1.1},
            "prefer_ai_output": True,
        },
    )
    assert submit_res.status_code == 202
    created = submit_res.json()
    job_id = created["job_id"]
    assert created["total_items"] == 3

    finished = _poll_batch_until_done(client, job_id)
    assert finished["status"] == "completed"
    assert finished["completed_items"] == 3
    assert finished["failed_items"] == 0
    assert finished["progress"] == 100.0
    assert finished["download_url"] == f"/v1/batches/{job_id}/download"

    list_res = client.get(f"/v1/projects/{project_id}/batches")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1
    assert list_res.json()["jobs"][0]["job_id"] == job_id

    dl_res = client.get(finished["download_url"])
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(dl_res.content), "r") as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["job_id"] == job_id
        assert manifest["completed_items"] == 3
        assert len(manifest["items"]) == 3
        assert len(names) == len(manifest["items"]) + 1
        for item in manifest["items"]:
            assert item["sha256"] == hashlib.sha256(zf.read(item["output_filename"])).hexdigest()

        by_preset = {item["preset_id"]: item for item in manifest["items"]}
        with Image.open(io.BytesIO(zf.read(by_preset["shopee_1_1"]["output_filename"]))) as im:
            assert im.size == (1024, 1024)
            assert im.format == "WEBP"
            assert im.mode == "RGBA"
            # Corner pixel stays transparent (0 alpha) because shopee_1_1 has background_rgb=None
            assert im.getpixel((0, 0))[3] == 0
            # Center pixel came from green ai_output
            cx, cy = im.size[0] // 2, im.size[1] // 2
            r, g, b, a = im.getpixel((cx, cy))
            assert g > r and g > b and a == 255

        with Image.open(io.BytesIO(zf.read(by_preset["amazon_white_85"]["output_filename"]))) as im:
            assert im.size == (2000, 2000)
            assert im.format == "JPEG"
            assert im.mode == "RGB"
            # Pure white Amazon background at top-left corner
            assert im.getpixel((0, 0)) == (255, 255, 255)

        with Image.open(io.BytesIO(zf.read(by_preset["tiktok_3_4"]["output_filename"]))) as im:
            assert im.size == (1200, 1600)
            assert im.format == "PNG"
            assert im.mode == "RGBA"

    # Project delete cascades batch_jobs and unlinks ZIP from exports_dir
    zip_file = test_settings.exports_dir / f"{job_id}.zip"
    assert zip_file.is_file()
    del_res = client.delete(f"/v1/projects/{project_id}")
    assert del_res.status_code == 200
    assert not zip_file.exists()
    assert client.get(f"/v1/batches/{job_id}").status_code == 404


def test_render_recipe_image_exif_transpose_upright() -> None:
    rotated_jpg = _make_exif_rotated_jpeg(100, 200)
    snapshot = {
        "width": 400,
        "height": 400,
        "format": "png",
        "quality": 90,
        "background_rgb": None,
        "subject_area_ratio": None,
        "safe_zone": None,
        "include_shadow": False,
        "watermark_text": None,
        "adjustments": {},
    }
    out_bytes, w, h = render_recipe_image(rotated_jpg, snapshot)
    assert (w, h) == (400, 400)
    with Image.open(io.BytesIO(out_bytes)) as im:
        # Transposed 100x200 with Orientation=6 becomes 200x100 (wide landscape),
        # so middle-top (200, 50) must be transparent while middle-left (50, 200) is opaque!
        assert im.getpixel((200, 50))[3] == 0
        assert im.getpixel((50, 200))[3] == 255


def test_batch_recipe_snapshot_immutability_br10_br17(
    client: TestClient, monkeypatch
) -> None:
    proj = client.post("/v1/projects", json={"name": "Snapshot Immutability"}).json()
    asset = client.post(
        f"/v1/projects/{proj['id']}/assets",
        files={"file": ("item.png", _make_png(120, 120), "image/png")},
    ).json()

    custom = client.post(
        "/v1/presets",
        json={
            "id": "snap_custom_800",
            "name_en": "Snap 800",
            "width": 800,
            "height": 600,
            "formats": ["png"],
        },
    ).json()

    worker = client.app.state.container.batch_worker
    gate = threading.Event()
    orig_render = worker._render_item

    def _paused_render(item):
        gate.wait(timeout=5.0)
        return orig_render(item)

    monkeypatch.setattr(worker, "_render_item", _paused_render)

    submit_res = client.post(
        "/v1/batches",
        json={
            "project_id": proj["id"],
            "asset_ids": [asset["id"]],
            "recipes": [{"preset_id": custom["id"]}],
        },
    )
    assert submit_res.status_code == 202
    job_id = submit_res.json()["job_id"]

    # Mutate and then delete the custom preset while job is paused
    assert client.patch(
        f"/v1/presets/{custom['id']}",
        json={"width": 1600, "height": 1600},
    ).status_code == 200
    assert client.delete(f"/v1/presets/{custom['id']}").status_code == 200

    gate.set()
    finished = _poll_batch_until_done(client, job_id)
    assert finished["status"] == "completed"
    dl = client.get(finished["download_url"])
    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        fname = manifest["items"][0]["output_filename"]
        with Image.open(io.BytesIO(zf.read(fname))) as im:
            assert im.size == (800, 600)


def test_batch_partial_failure_isolation_and_retry(
    client: TestClient, test_settings: Settings
) -> None:
    proj = client.post("/v1/projects", json={"name": "Failure & Retry"}).json()
    pid = proj["id"]
    a1 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("good.png", _make_png(100, 100), "image/png")},
    ).json()
    a2 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("missing_later.png", _make_png(110, 110, (10, 20, 30, 255)), "image/png")},
    ).json()

    # Remove a2's physical blob so item 2 fails while item 1 succeeds
    repo = client.app.state.container.repo
    a2_domain = repo.get_asset(a2["id"])
    assert a2_domain is not None
    blob_path = test_settings.local_storage_dir / a2_domain.storage_key
    raw_a2_backup = blob_path.read_bytes()
    blob_path.chmod(0o644)
    blob_path.unlink()

    res = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"], a2["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    partial = _poll_batch_until_done(client, job_id)
    assert partial["status"] == "partial_failed"
    assert partial["completed_items"] == 1
    assert partial["failed_items"] == 1
    assert partial["download_url"] == f"/v1/batches/{job_id}/download"

    # Partial ZIP contains the 1 completed item + manifest detailing the failed item
    dl_partial = client.get(partial["download_url"])
    assert dl_partial.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl_partial.content), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        statuses = {it["asset_id"]: it["status"] for it in manifest["items"]}
        assert statuses == {a1["id"]: "completed", a2["id"]: "failed"}

    # Restore missing blob and retry failed item
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(raw_a2_backup)

    retry_res = client.post(f"/v1/batches/{job_id}/retry")
    assert retry_res.status_code == 202
    retried = _poll_batch_until_done(client, job_id)
    assert retried["status"] == "completed"
    assert retried["completed_items"] == 2
    assert retried["failed_items"] == 0


def test_batch_cancel_and_security_validation_guards(
    client: TestClient, monkeypatch
) -> None:
    proj = client.post("/v1/projects", json={"name": "Cancel & Validation"}).json()
    pid = proj["id"]
    a1 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("c1.png", _make_png(80, 80), "image/png")},
    ).json()
    a2 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("c2.png", _make_png(90, 90), "image/png")},
    ).json()

    # Bool coercion & invalid path traversal guards -> 422
    bad_bool = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "quality": True}],
        },
    )
    assert bad_bool.status_code == 422
    assert bad_bool.json()["code"] == "VALIDATION_ERROR"

    trav = client.get("/v1/batches/..%2F..%2Fetc/download")
    assert trav.status_code == 422
    assert trav.json()["code"] == "PATH_TRAVERSAL_DETECTED"

    trav_bs = client.get("/v1/batches/..%5C..%5Cetc/download")
    assert trav_bs.status_code == 422
    assert trav_bs.json()["code"] == "PATH_TRAVERSAL_DETECTED"

    bad_adj_bool = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"]],
            "recipes": [{"preset_id": "shopee_1_1"}],
            "adjustments": {"brightness": False},
        },
    )
    assert bad_adj_bool.status_code == 422
    assert bad_adj_bool.json()["code"] == "VALIDATION_ERROR"

    # Cancel a running job deterministically
    worker = client.app.state.container.batch_worker
    item_started = threading.Event()
    allow_finish = threading.Event()
    orig_render = worker._render_item

    def _slow_render(item):
        item_started.set()
        allow_finish.wait(timeout=5.0)
        return orig_render(item)

    monkeypatch.setattr(worker, "_render_item", _slow_render)

    sub = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"], a2["id"]],
            "recipes": [{"preset_id": "shopee_1_1"}],
        },
    )
    assert sub.status_code == 202
    job_id = sub.json()["job_id"]
    assert item_started.wait(timeout=5.0)

    cancel_res = client.post(f"/v1/batches/{job_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] in ("cancel_requested", "cancelled")

    allow_finish.set()
    final = _poll_batch_until_done(client, job_id)
    assert final["status"] == "cancelled"
    assert final["download_url"] is None
    assert client.get(f"/v1/batches/{job_id}/download").status_code == 409


def test_batch_all_failed_and_startup_recovery(
    test_settings: Settings,
) -> None:
    from app.domain.enums import BatchStatus
    from app.domain.models import BatchRecipeInput
    from app.main import create_app

    # 1) All items fail -> status == failed, no download
    app1 = create_app(settings=test_settings)
    with TestClient(app1) as c1:
        proj = c1.post("/v1/projects", json={"name": "All Fail & Recovery"}).json()
        pid = proj["id"]
        bad_asset = c1.post(
            f"/v1/projects/{pid}/assets",
            files={"file": ("broken.png", _make_png(64, 64), "image/png")},
        ).json()
        good_asset = c1.post(
            f"/v1/projects/{pid}/assets",
            files={"file": ("good.png", _make_png(64, 64, (10, 200, 100, 255)), "image/png")},
        ).json()

        repo1 = app1.state.container.repo
        bad_domain = repo1.get_asset(bad_asset["id"])
        assert bad_domain is not None
        bad_path = test_settings.local_storage_dir / bad_domain.storage_key
        bad_path.chmod(0o644)
        bad_path.unlink()

        fail_res = c1.post(
            "/v1/batches",
            json={
                "project_id": pid,
                "asset_ids": [bad_asset["id"]],
                "recipes": [{"preset_id": "shopee_1_1"}],
            },
        )
        assert fail_res.status_code == 202
        failed_job = _poll_batch_until_done(c1, fail_res.json()["job_id"])
        assert failed_job["status"] == "failed"
        assert failed_job["download_url"] is None
        assert c1.get(f"/v1/batches/{failed_job['job_id']}/download").status_code == 409

        # Seed a simulated interrupted 'running' job and a 'cancel_requested' job directly in repo
        # by shutting down worker before submitting, or writing via repo
        app1.state.container.batch_worker.shutdown(wait=True)
        interrupted_job, _ = app1.state.container.batch_worker.submit_batch_job(
            project_id=pid,
            asset_ids=[good_asset["id"]],
            recipes=[BatchRecipeInput(preset_id="shopee_1_1", format="png")],
        )
        # Wait for it or simulate crash by creating a queued/running job after shutdown:
        app1.state.container.batch_worker.shutdown(wait=True)

        # Force a second job in DB directly with status='running' and a third with 'cancel_requested'
        from app.core.ids import new_id, utc_now_iso
        from app.domain.enums import BatchItemStatus
        from app.domain.models import BatchJob, BatchJobItem

        now = utc_now_iso()
        preset = repo1.get_preset("shopee_1_1")
        assert preset is not None
        snap = {
            "width": 256,
            "height": 256,
            "format": "png",
            "quality": 90,
            "background_rgb": None,
            "subject_area_ratio": None,
            "safe_zone": None,
            "include_shadow": False,
            "watermark_text": None,
            "adjustments": {},
        }
        rec_job_id = "batch_recover_run"
        repo1.create_batch_job(
            BatchJob(
                id=rec_job_id,
                project_id=pid,
                status=BatchStatus.RUNNING,
                total_items=1,
                completed_items=0,
                failed_items=0,
                progress=0.0,
                created_at=now,
                started_at=now,
                updated_at=now,
            ),
            [
                BatchJobItem(
                    id=new_id(),
                    job_id=rec_job_id,
                    seq=1,
                    asset_id=good_asset["id"],
                    source_asset_id=good_asset["id"],
                    preset_id="shopee_1_1",
                    preset_version="1.0.0",
                    format="png",
                    quality=90,
                    recipe_snapshot=snap,
                    status=BatchItemStatus.RUNNING,
                    output_filename="001_recover.png",
                    created_at=now,
                    started_at=now,
                )
            ],
        )
        canc_job_id = "batch_recover_canc"
        repo1.create_batch_job(
            BatchJob(
                id=canc_job_id,
                project_id=pid,
                status=BatchStatus.CANCEL_REQUESTED,
                total_items=1,
                completed_items=0,
                failed_items=0,
                progress=0.0,
                created_at=now,
                started_at=now,
                updated_at=now,
            ),
            [
                BatchJobItem(
                    id=new_id(),
                    job_id=canc_job_id,
                    seq=1,
                    asset_id=good_asset["id"],
                    source_asset_id=good_asset["id"],
                    preset_id="shopee_1_1",
                    preset_version="1.0.0",
                    format="png",
                    quality=90,
                    recipe_snapshot=snap,
                    status=BatchItemStatus.PENDING,
                    output_filename="001_canc.png",
                    created_at=now,
                )
            ],
        )

    # 2) New app instance startup recovers both jobs cleanly
    app2 = create_app(settings=test_settings)
    with TestClient(app2) as c2:
        recovered = _poll_batch_until_done(c2, rec_job_id)
        assert recovered["status"] == "completed"
        assert recovered["completed_items"] == 1

        cancelled = _poll_batch_until_done(c2, canc_job_id)
        assert cancelled["status"] == "cancelled"
        assert interrupted_job.id


def test_batch_cancel_after_partial_completion_and_lost_staging_retry(
    client: TestClient, test_settings: Settings, monkeypatch
) -> None:
    proj = client.post("/v1/projects", json={"name": "Cancel & Lost Staging Retry"}).json()
    pid = proj["id"]
    a1 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("p1.png", _make_png(90, 90, (200, 40, 40, 255)), "image/png")},
    ).json()
    a2 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("p2.png", _make_png(90, 90, (40, 200, 40, 255)), "image/png")},
    ).json()
    a3 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("p3.png", _make_png(90, 90, (40, 40, 200, 255)), "image/png")},
    ).json()

    worker = client.app.state.container.batch_worker
    item2_started = threading.Event()
    allow_item2_finish = threading.Event()
    orig_render = worker._render_item

    def _gate_item2(item):
        if item.seq == 2 and not allow_item2_finish.is_set():
            item2_started.set()
            allow_item2_finish.wait(timeout=5.0)
        return orig_render(item)

    monkeypatch.setattr(worker, "_render_item", _gate_item2)

    sub = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"], a2["id"], a3["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert sub.status_code == 202
    job_id = sub.json()["job_id"]
    assert item2_started.wait(timeout=5.0)

    cancel_res = client.post(f"/v1/batches/{job_id}/cancel")
    assert cancel_res.status_code == 200
    allow_item2_finish.set()

    cancelled = _poll_batch_until_done(client, job_id)
    assert cancelled["status"] == "cancelled"
    assert cancelled["completed_items"] == 1
    assert not (test_settings.exports_dir / ".staging" / job_id).exists()

    # Retry after cancel -> must re-render item 1 (staging was deleted) and items 2 & 3
    retry_res = client.post(f"/v1/batches/{job_id}/retry")
    assert retry_res.status_code == 202
    retried = _poll_batch_until_done(client, job_id)
    assert retried["status"] == "completed"
    assert retried["completed_items"] == 3

    dl = client.get(retried["download_url"])
    assert dl.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert len(manifest["items"]) == 3
        assert len(zf.namelist()) == len(manifest["items"]) + 1
        for entry in manifest["items"]:
            fn = entry["output_filename"]
            assert fn in zf.namelist()
            assert entry["sha256"] == hashlib.sha256(zf.read(fn)).hexdigest()

    # Staging & in-memory dicts are cleaned up after COMPLETED
    assert not (test_settings.exports_dir / ".staging" / job_id).exists()
    assert job_id not in worker._cancel_events
    assert job_id not in worker._futures

    # Lost-staging retry on PARTIAL_FAILED
    repo = client.app.state.container.repo
    a2_domain = repo.get_asset(a2["id"])
    assert a2_domain is not None
    blob_path = test_settings.local_storage_dir / a2_domain.storage_key
    raw_a2 = blob_path.read_bytes()
    blob_path.chmod(0o644)
    blob_path.unlink()

    partial_sub = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"], a2["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert partial_sub.status_code == 202
    partial_id = partial_sub.json()["job_id"]
    partial_done = _poll_batch_until_done(client, partial_id)
    assert partial_done["status"] == "partial_failed"

    # Simulate external loss of .staging/{partial_id} before retrying
    import shutil
    shutil.rmtree(test_settings.exports_dir / ".staging" / partial_id, ignore_errors=True)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(raw_a2)

    retry_lost = client.post(f"/v1/batches/{partial_id}/retry")
    assert retry_lost.status_code == 202
    lost_done = _poll_batch_until_done(client, partial_id)
    assert lost_done["status"] == "completed"
    assert lost_done["completed_items"] == 2

    dl_lost = client.get(lost_done["download_url"])
    assert dl_lost.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl_lost.content), "r") as zf:
        manifest2 = json.loads(zf.read("manifest.json"))
        assert len(manifest2["items"]) == 2
        assert len(zf.namelist()) == len(manifest2["items"]) + 1
        for entry in manifest2["items"]:
            fn = entry["output_filename"]
            assert fn in zf.namelist()
            assert entry["sha256"] == hashlib.sha256(zf.read(fn)).hexdigest()


def test_batch_last_item_cancel_never_wedges_job(
    client: TestClient, test_settings: Settings, monkeypatch
) -> None:
    proj = client.post("/v1/projects", json={"name": "Last Item Cancel"}).json()
    pid = proj["id"]
    a1 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("l1.png", _make_png(80, 80), "image/png")},
    ).json()
    a2 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("l2.png", _make_png(80, 80, (10, 180, 90, 255)), "image/png")},
    ).json()

    worker = client.app.state.container.batch_worker
    item2_started = threading.Event()
    allow_item2_finish = threading.Event()
    orig_render = worker._render_item

    def _gate_last_item(item):
        if item.seq == 2 and not allow_item2_finish.is_set():
            item2_started.set()
            allow_item2_finish.wait(timeout=5.0)
        return orig_render(item)

    monkeypatch.setattr(worker, "_render_item", _gate_last_item)

    sub = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"], a2["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert sub.status_code == 202
    job_id = sub.json()["job_id"]
    assert item2_started.wait(timeout=5.0)

    cancel_res = client.post(f"/v1/batches/{job_id}/cancel")
    assert cancel_res.status_code == 200
    allow_item2_finish.set()

    done = _poll_batch_until_done(client, job_id)
    # Item 2 was cancelled mid-render -> retryable -> must never wedge (409 on both download & retry)
    assert done["status"] == "cancelled"
    assert done["items"][1]["status"] == "cancelled"

    retry_res = client.post(f"/v1/batches/{job_id}/retry")
    assert retry_res.status_code == 202
    completed = _poll_batch_until_done(client, job_id)
    assert completed["status"] == "completed"
    assert completed["completed_items"] == 2
    dl = client.get(completed["download_url"])
    assert dl.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dl.content), "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        assert len(zf.namelist()) == len(manifest["items"]) + 1

    # Also verify post-commit cancel race (all items already COMPLETED when cancel arrives)
    sub2 = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert sub2.status_code == 202
    job2_id = sub2.json()["job_id"]
    done2 = _poll_batch_until_done(client, job2_id)
    assert done2["status"] == "completed"

    # Simulate _is_cancelled returning True only at post-item check after last item committed
    orig_is_cancelled = worker._is_cancelled
    calls = {"n": 0}

    def _late_cancel(jid: str) -> bool:
        if jid not in (job_id, job2_id):
            calls["n"] += 1
            # 1: pre-claim, 2: pre-item-1, 3: post-render (before commit),
            # 4: post-item-1 (after item 1 committed COMPLETED)
            return calls["n"] >= 4
        return orig_is_cancelled(jid)

    monkeypatch.setattr(worker, "_is_cancelled", _late_cancel)
    sub3 = client.post(
        "/v1/batches",
        json={
            "project_id": pid,
            "asset_ids": [a1["id"]],
            "recipes": [{"preset_id": "shopee_1_1", "format": "png"}],
        },
    )
    assert sub3.status_code == 202
    job3_id = sub3.json()["job_id"]
    done3 = _poll_batch_until_done(client, job3_id)
    assert done3["status"] == "completed"
    assert client.get(done3["download_url"]).status_code == 200


def test_batch_missing_staged_file_during_zip_fails_loudly_and_claim_race(
    client: TestClient, test_settings: Settings, monkeypatch
) -> None:
    import pytest

    proj = client.post("/v1/projects", json={"name": "Missing Staging Fail"}).json()
    pid = proj["id"]
    a1 = client.post(
        f"/v1/projects/{pid}/assets",
        files={"file": ("m1.png", _make_png(64, 64), "image/png")},
    ).json()

    worker = client.app.state.container.batch_worker
    monkeypatch.setattr(worker, "_enqueue_job", lambda _jid: None)
    from app.core.ids import utc_now_iso
    from app.domain.models import BatchRecipeInput

    job, _items = worker.submit_batch_job(
        project_id=pid,
        asset_ids=[a1["id"]],
        recipes=[BatchRecipeInput(preset_id="shopee_1_1", format="png")],
    )
    # Remove staged file immediately after update_batch_job_item commits COMPLETED
    repo = client.app.state.container.repo
    orig_update = repo.update_batch_job_item

    def _delete_staged_after_complete(item):
        out = orig_update(item)
        if item.job_id == job.id and item.status.value == "completed" and item.output_filename:
            staged = test_settings.exports_dir / ".staging" / job.id / item.output_filename
            if staged.exists():
                staged.unlink()
        return out

    monkeypatch.setattr(repo, "update_batch_job_item", _delete_staged_after_complete)

    with pytest.raises(RuntimeError, match="missing staged"):
        worker._run_job(job.id)

    after = client.get(f"/v1/batches/{job.id}").json()
    assert after["status"] == "failed"
    assert after["download_url"] is None
    assert after["items"][0]["status"] == "failed"
    assert after["items"][0]["error_code"] == "STAGING_MISSING"
    assert not (test_settings.exports_dir / f"{job.id}.zip").exists()
    assert not (test_settings.exports_dir / ".staging" / job.id).exists()
    assert job.id not in worker._cancel_events
    assert job.id not in worker._futures

    # Also verify claim_batch_job_running returns None if job already cancelled while queued
    job_canc, _ = worker.submit_batch_job(
        project_id=pid,
        asset_ids=[a1["id"]],
        recipes=[BatchRecipeInput(preset_id="shopee_1_1", format="png")],
    )
    worker.cancel_batch_job(job_canc.id)
    assert repo.claim_batch_job_running(job_canc.id, utc_now_iso()) is None
    assert client.get(f"/v1/batches/{job_canc.id}").json()["status"] == "cancelled"



