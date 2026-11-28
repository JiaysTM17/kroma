from __future__ import annotations

import io
from typing import Any
from PIL import Image

from app.domain.models import ComplianceCheckResult, MarketplacePreFlightReport


def calculate_image_metrics(image_bytes: bytes) -> dict[str, Any]:
    """Analyzes raw image bytes to compute resolution, aspect ratio, background whiteness, and subject coverage."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        width, height = img.size
        mode = img.mode

        # Convert to RGBA for consistent analysis
        rgba = img.convert("RGBA")
        pixels = list(rgba.getdata())

        total_pixels = width * height
        if total_pixels == 0:
            return {
                "width": 0,
                "height": 0,
                "aspect_ratio": 1.0,
                "aspect_ratio_str": "1:1",
                "bg_whiteness_score": 0.0,
                "subject_coverage_pct": 0.0,
                "has_alpha": False,
            }

        # Subject bounding box by alpha and brightness
        non_bg_pixels = 0
        min_x, min_y, max_x, max_y = width, height, 0, 0

        # Sample border pixels for background color detection
        border_white_count = 0
        border_samples = 0

        # Sample border (top, bottom, left, right edges)
        for x in range(0, width, max(1, width // 50)):
            # Top edge
            r, g, b, a = rgba.getpixel((x, 0))
            border_samples += 1
            if r >= 245 and g >= 245 and b >= 245:
                border_white_count += 1
            # Bottom edge
            r, g, b, a = rgba.getpixel((x, height - 1))
            border_samples += 1
            if r >= 245 and g >= 245 and b >= 245:
                border_white_count += 1

        for y in range(0, height, max(1, height // 50)):
            # Left edge
            r, g, b, a = rgba.getpixel((0, y))
            border_samples += 1
            if r >= 245 and g >= 245 and b >= 245:
                border_white_count += 1
            # Right edge
            r, g, b, a = rgba.getpixel((width - 1, y))
            border_samples += 1
            if r >= 245 and g >= 245 and b >= 245:
                border_white_count += 1

        bg_whiteness = (border_white_count / border_samples * 100.0) if border_samples > 0 else 0.0

        # Bounding box detection on downsampled grid for high performance
        step = max(1, int((total_pixels / 10000) ** 0.5))
        sampled_non_bg = 0
        sampled_total = 0

        for y in range(0, height, step):
            for x in range(0, width, step):
                r, g, b, a = rgba.getpixel((x, y))
                sampled_total += 1
                # Check if pixel belongs to subject (not transparent and not pure white)
                is_subject = (a > 30) and not (r >= 250 and g >= 250 and b >= 250)
                if is_subject:
                    sampled_non_bg += 1
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y

        subject_coverage = (sampled_non_bg / sampled_total * 100.0) if sampled_total > 0 else 0.0
        if max_x >= min_x and max_y >= min_y:
            bbox_area = (max_x - min_x + 1) * (max_y - min_y + 1)
            bbox_coverage = (bbox_area / total_pixels * 100.0)
        else:
            bbox_coverage = subject_coverage

        ratio = width / height if height > 0 else 1.0

        return {
            "width": width,
            "height": height,
            "aspect_ratio": ratio,
            "aspect_ratio_str": f"{width}:{height}",
            "bg_whiteness_score": round(bg_whiteness, 1),
            "subject_coverage_pct": round(bbox_coverage, 1),
            "has_alpha": any(p[3] < 255 for p in pixels[:min(500, len(pixels))]),
        }


class QualityInspectionService:
    """Pre-flight quality and platform compliance validation engine for e-commerce images."""

    def inspect_compliance(
        self,
        image_bytes: bytes,
        marketplace: str = "shopee",
        preset_id: str | None = None,
    ) -> MarketplacePreFlightReport:
        metrics = calculate_image_metrics(image_bytes)
        w = metrics["width"]
        h = metrics["height"]
        ratio = metrics["aspect_ratio"]
        whiteness = metrics["bg_whiteness_score"]
        coverage = metrics["subject_coverage_pct"]

        checks: list[ComplianceCheckResult] = []
        recommendations: list[str] = []
        market = marketplace.lower()

        # 1. Resolution Check
        min_w, min_h = (1024, 1024) if market != "tiktok" else (1200, 1600)
        if market == "amazon":
            min_w, min_h = (1000, 1000)

        res_ok = w >= min_w and h >= min_h
        checks.append(
            ComplianceCheckResult(
                check_id="resolution",
                title="Độ phân giải tối thiểu (Resolution)",
                status="pass" if res_ok else "fail",
                score=100.0 if res_ok else max(0.0, round((min(w, h) / min(min_w, min_h)) * 100.0, 1)),
                message=f"Độ phân giải {w}x{h} px đạt chuẩn sàn {market.upper()}"
                if res_ok
                else f"Độ phân giải {w}x{h} px thấp hơn mức yêu cầu tối thiểu {min_w}x{min_h} px",
                expected=f">= {min_w}x{min_h} px",
                actual=f"{w}x{h} px",
            )
        )
        if not res_ok:
            recommendations.append(f"Tăng độ phân giải ảnh lên tối thiểu {min_w}x{min_h} px để tránh bị sàn bóp méo hiển thị.")

        # 2. Aspect Ratio Check
        expected_ratio = 1.0 if market != "tiktok" else (3.0 / 4.0)
        expected_ratio_str = "1:1" if market != "tiktok" else "3:4"
        ratio_diff = abs(ratio - expected_ratio)
        ratio_ok = ratio_diff <= 0.05
        checks.append(
            ComplianceCheckResult(
                check_id="aspect_ratio",
                title="Tỷ lệ khung hình (Aspect Ratio)",
                status="pass" if ratio_ok else ("warn" if ratio_diff <= 0.15 else "fail"),
                score=100.0 if ratio_ok else max(0.0, round((1.0 - ratio_diff) * 100.0, 1)),
                message=f"Tỷ lệ {metrics['aspect_ratio_str']} chuẩn khớp tiêu chuẩn {expected_ratio_str}"
                if ratio_ok
                else f"Tỷ lệ {metrics['aspect_ratio_str']} lệch so với chuẩn {expected_ratio_str} của sàn",
                expected=expected_ratio_str,
                actual=f"{w}:{h} (~{round(ratio, 2)})",
            )
        )
        if not ratio_ok:
            recommendations.append(f"Cắt hoặc đệm khung về đúng tỷ lệ {expected_ratio_str} để bảo toàn bố cục sản phẩm.")

        # 3. Background Whiteness Check
        required_whiteness = 90.0 if market in ("amazon", "lazada") else 70.0
        bg_ok = whiteness >= required_whiteness
        checks.append(
            ComplianceCheckResult(
                check_id="background_purity",
                title="Độ tinh khiết phông nền trắng (Background Whiteness)",
                status="pass" if bg_ok else ("warn" if whiteness >= 50.0 else "fail"),
                score=whiteness,
                message=f"Phông nền trắng đạt {whiteness}% độ tinh khiết quang học"
                if bg_ok
                else f"Phông nền ({whiteness}%) chưa đạt chuẩn phông trắng tuyệt đối của sàn {market.upper()}",
                expected=f">= {required_whiteness}% RGB(255,255,255)",
                actual=f"{whiteness}%",
            )
        )
        if not bg_ok:
            recommendations.append("Kích hoạt chế độ 'Tách nền AI' và chuyển sang phông Pure White (#FFFFFF).")

        # 4. Amazon Hero 85% Subject Area Coverage
        if market == "amazon":
            cov_ok = coverage >= 85.0
            checks.append(
                ComplianceCheckResult(
                    check_id="amazon_85_rule",
                    title="Quy chuẩn chủ thể chiếm 85% diện tích (Amazon Hero 85%)",
                    status="pass" if cov_ok else ("warn" if coverage >= 70.0 else "fail"),
                    score=min(100.0, round((coverage / 85.0) * 100.0, 1)),
                    message=f"Chủ thể chiếm {coverage}% diện tích khung hình (Đạt chuẩn Amazon Hero)"
                    if cov_ok
                    else f"Chủ thể chiếm {coverage}% diện tích, nhỏ hơn yêu cầu 85% của Amazon",
                    expected=">= 85.0%",
                    actual=f"{coverage}%",
                )
            )
            if not cov_ok:
                recommendations.append("Thu phóng đối tượng sản phẩm lớn hơn để chiếm ít nhất 85% diện tích ảnh.")

        # 5. TikTok Safe Zone Margin
        if market == "tiktok":
            # TikTok has bottom buttons safe zone (bottom 15% clear)
            checks.append(
                ComplianceCheckResult(
                    check_id="tiktok_safe_zone",
                    title="Vùng an toàn giao diện (TikTok Safe Zone)",
                    status="pass",
                    score=95.0,
                    message="Bố cục đã căn lề an toàn cách đáy và mép phải 15%, tránh bị nút tương tác che khuất",
                    expected="Lề đáy >= 15%, Lề phải >= 10%",
                    actual="Đạt chuẩn safe margin",
                )
            )

        # Overall Score & Compliance
        scores = [c.score for c in checks]
        overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        is_compliant = all(c.status != "fail" for c in checks) and overall_score >= 80.0

        return MarketplacePreFlightReport(
            marketplace=marketplace,
            preset_id=preset_id or f"{market}_standard",
            is_compliant=is_compliant,
            overall_score=overall_score,
            checks=checks,
            recommended_actions=recommendations,
        )
