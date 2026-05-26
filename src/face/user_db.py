"""
face/user_db.py
JSON-based user database with face embedding storage and cosine matching.
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np

from src.logger import info, error
from src.utils import ROOT_DIR

USERS_FILE: Path = ROOT_DIR / "src" / "face" / "users.json"


def _load_users() -> list[dict]:
    """Load users from JSON file. Returns empty list if file does not exist."""
    if not USERS_FILE.exists():
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("users", [])
    except (json.JSONDecodeError, KeyError) as e:
        error(f"[FaceDB] Failed to parse users.json: {e}")
        return []


def _save_users(users: list[dict]) -> None:
    """Save users to JSON file."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two embedding vectors."""
    a_np = np.array(a)
    b_np = np.array(b)
    dot = np.dot(a_np, b_np)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return float(1.0 - dot / (norm_a * norm_b))


def find_user_by_embedding(
    target: list[float],
    threshold: float = 0.5,
) -> Optional[dict]:
    """
    Find a user by comparing face embedding with all stored users.

    Args:
        target: Face embedding vector (128-d).
        threshold: Cosine distance threshold. Lower = stricter match.

    Returns:
        dict with name, last_clinic_id, distance if matched, or None.
    """
    users = _load_users()
    if not users:
        return None

    best_dist = float("inf")
    best_user: Optional[dict] = None

    for user in users:
        stored_embedding = user.get("face_embedding")
        if not stored_embedding:
            continue

        dist = _cosine_distance(target, stored_embedding)
        if dist < best_dist:
            best_dist = dist
            best_user = user

    if best_user is not None and best_dist < threshold:
        info(f"[FaceDB] Match: {best_user['name']} (distance={best_dist:.4f})")
        return {
            "name": best_user["name"],
            "last_clinic_id": best_user.get("last_clinic_id"),
            "distance": round(best_dist, 4),
        }

    info(f"[FaceDB] No match (best_distance={best_dist:.4f}, threshold={threshold})")
    return None


def add_user(name: str, embedding: list[float]) -> None:
    """Register a new user with face embedding."""
    users = _load_users()

    for u in users:
        if u["name"] == name:
            u["face_embedding"] = embedding
            info(f"[FaceDB] Updated embedding for user '{name}'")
            _save_users(users)
            return

    users.append({
        "name": name,
        "last_clinic_id": None,
        "face_embedding": embedding,
    })
    _save_users(users)
    info(f"[FaceDB] Registered user '{name}'")


def get_users() -> list[dict]:
    """Return all users without face embeddings (for debugging)."""
    return [
        {"name": u["name"], "last_clinic_id": u.get("last_clinic_id")}
        for u in _load_users()
    ]
