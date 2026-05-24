#!/usr/bin/env python3
"""Capture a single frame from /dev/video0 and save as tmp.jpg."""

import cv2
import sys

CAMERA_DEVICE = "/dev/video0"
OUTPUT_PATH = "tmp.jpg"

cap = cv2.VideoCapture(CAMERA_DEVICE)
if not cap.isOpened():
    print(f"ERROR: cannot open camera {CAMERA_DEVICE}")
    sys.exit(1)

ret, frame = cap.read()
cap.release()

if not ret:
    print("ERROR: failed to read frame")
    sys.exit(1)

cv2.imwrite(OUTPUT_PATH, frame)
print(f"Saved {OUTPUT_PATH} ({frame.shape[1]}x{frame.shape[0]})")
