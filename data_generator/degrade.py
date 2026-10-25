"""Turns a clean PDF page into a 'scanned' or 'photographed' image.

Real SME invoices often arrive as scans or phone photos, so the dataset needs
them too. Effects: slight rotation, blur, noise, uneven lighting, JPEG
compression and (for photos) a perspective tilt on a table-like background.
"""
from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
from pdf2image import convert_from_path


def _page(pdf: Path, dpi: int) -> np.ndarray:
    img = convert_from_path(str(pdf), dpi=dpi, first_page=1, last_page=1)[0]
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def scan(pdf: Path, out: Path, rng: random.Random) -> dict:
    img = _page(pdf, rng.choice([150, 200]))
    h, w = img.shape[:2]
    angle = rng.uniform(-2.0, 2.0)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    img = cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))
    gray = rng.random() < 0.6
    if gray:
        img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    blur = rng.choice([0, 1, 1, 2])
    if blur:
        k = blur * 2 + 1
        img = cv2.GaussianBlur(img, (k, k), 0)
    noise = rng.uniform(4, 14)
    img = np.clip(img.astype(np.float32) + np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, noise, img.shape), 0, 255)
    contrast, brightness = rng.uniform(0.8, 1.05), rng.uniform(-15, 20)
    img = np.clip(img * contrast + brightness, 0, 255).astype(np.uint8)
    q = rng.randint(35, 75)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return {"rotation_deg": round(angle, 2), "grayscale": gray, "blur": blur, "noise": round(noise, 1), "jpeg_quality": q}


def photo(pdf: Path, out: Path, rng: random.Random) -> dict:
    img = _page(pdf, 150)
    h, w = img.shape[:2]
    pad = int(0.08 * w)
    bg_col = rng.choice([(70, 90, 120), (60, 60, 60), (120, 140, 160), (40, 70, 90)])
    canvas = np.full((h + 2 * pad, w + 2 * pad, 3), bg_col, np.uint8)
    j = lambda: rng.uniform(-0.04, 0.04) * w
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[pad + j(), pad + j()], [pad + w + j(), pad + j()], [pad + w + j(), pad + h + j()], [pad + j(), pad + h + j()]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (canvas.shape[1], canvas.shape[0]), borderMode=cv2.BORDER_TRANSPARENT, dst=canvas)
    # uneven lighting: a soft gradient shadow
    gx = np.linspace(rng.uniform(0.65, 0.9), 1.0, warped.shape[1])[None, :, None]
    gy = np.linspace(1.0, rng.uniform(0.75, 0.95), warped.shape[0])[:, None, None]
    img = np.clip(warped * gx * gy, 0, 255).astype(np.uint8)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    q = rng.randint(55, 85)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return {"perspective": True, "jpeg_quality": q}
