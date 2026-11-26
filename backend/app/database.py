import sqlite3
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from .config import SQLITE_PATH

def get_connection():
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            active_variant TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 1,
            manifest_json TEXT NOT NULL DEFAULT '{}'
        )
    """)
    
    # 2. Presets table (marketplace templates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            marketplace TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            aspect_ratio TEXT NOT NULL,
            bg_color TEXT NOT NULL,
            subject_scale REAL NOT NULL,
            format TEXT NOT NULL,
            description TEXT
        )
    """)
    
    # 3. Proofing links table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proofing_sessions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            client_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            allow_comments INTEGER DEFAULT 1,
            feedback_json TEXT DEFAULT '[]'
        )
    """)
    
    # Pre-populate default Marketplace presets if empty
    cursor.execute("SELECT COUNT(*) as count FROM presets")
    if cursor.fetchone()["count"] == 0:
        default_presets = [
            ("shopee_square", "Shopee Standard 1:1", "Shopee", 1024, 1024, "1:1", "#FFFFFF", 0.90, "JPEG", "Chuẩn vuông hiển thị danh mục sản phẩm Shopee"),
            ("tiktok_shop_feed", "TikTok Shop Feed 3:4", "TikTok Shop", 1200, 1600, "3:4", "#FFFFFF", 0.85, "JPEG", "Chuẩn khung dọc 3:4 tối ưu trên di động TikTok"),
            ("tiktok_shop_square", "TikTok Shop Square 1:1", "TikTok Shop", 1080, 1080, "1:1", "#FFFFFF", 0.88, "JPEG", "Chuẩn khung vuông 1:1 cho tab sản phẩm"),
            ("amazon_hero", "Amazon Hero Pure White", "Amazon", 2000, 2000, "1:1", "#FFFFFF", 0.85, "JPEG", "Nền trắng tuyệt đối RGB (255,255,255), chủ thể chiếm đúng 85% diện tích"),
            ("lazada_square", "Lazada Square Product", "Lazada", 1200, 1200, "1:1", "#FFFFFF", 0.88, "JPEG", "Chuẩn ảnh sản phẩm thương mại điện tử Lazada"),
            ("transparent_png", "Web PNG Transparent", "Universal", 1200, 1200, "1:1", "transparent", 0.90, "PNG", "Ảnh tách nền không phông phục vụ ghép banner")
        ]
        cursor.executemany("""
            INSERT INTO presets (id, name, marketplace, width, height, aspect_ratio, bg_color, subject_scale, format, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_presets)
        
    conn.commit()
    conn.close()
