"""
face/routes.py
FastAPI router for face recognition endpoints.
"""

import numpy as np
import cv2
import face_recognition
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel

from src.logger import info, error, warning
from src.face.user_db import find_user_by_embedding, add_user

router = APIRouter(prefix="/face", tags=["face"])


class FaceRecogResponse(BaseModel):
    exist: bool
    name: str | None = None


class FaceRegisterResponse(BaseModel):
    success: bool
    message: str


@router.post("/face-recog", response_model=FaceRecogResponse)
def face_recog(image: UploadFile = File(...)) -> FaceRecogResponse:
    """
    Recognize a user by face image.

    Upload a face image (JPEG/PNG). Returns the matched user's name
    if found, or indicates the user does not exist.
    """
    try:
        contents = image.file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            error("[Face] Failed to decode uploaded image")
            return FaceRecogResponse(exist=False)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)
        if not encodings:
            info("[Face] No face detected in image")
            return FaceRecogResponse(exist=False)

        embedding = encodings[0].tolist()
        result = find_user_by_embedding(embedding)
        if result is None:
            return FaceRecogResponse(exist=False)

        return FaceRecogResponse(exist=True, name=result["name"])

    except Exception as exc:
        error(f"[Face] Recognition failed: {exc}", exc_info=True)
        return FaceRecogResponse(exist=False)


@router.post("/register", response_model=FaceRegisterResponse)
def face_register(
    name: str = Form(..., description="User name"),
    image: UploadFile = File(..., description="Face image (JPEG/PNG)"),
) -> FaceRegisterResponse:
    """
    Register a new user with name and face image.

    Extracts face embedding from the uploaded image and stores it
    in the user database. If the name already exists, the embedding
    is updated.
    """
    if not name.strip():
        return FaceRegisterResponse(success=False, message="Name is required")

    try:
        contents = image.file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            error("[Face] Register: failed to decode image")
            return FaceRegisterResponse(success=False, message="Failed to decode image")

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)
        if not encodings:
            warning(f"[Face] Register: no face detected in image for '{name}'")
            return FaceRegisterResponse(
                success=False,
                message="No face detected in image. Please upload a clear face photo.",
            )

        embedding = encodings[0].tolist()
        add_user(name.strip(), embedding)
        info(f"[Face] Registered: '{name.strip()}'")
        return FaceRegisterResponse(success=True, message=f"User '{name.strip()}' registered")

    except Exception as exc:
        error(f"[Face] Register failed: {exc}", exc_info=True)
        return FaceRegisterResponse(success=False, message="Registration failed")
