from __future__ import annotations

from pathlib import Path

import cv2
from PIL import Image

from .utils import ensure_dir, list_images, parse_size


def images_to_video(folder: Path, output_path: Path, fps: float = 30.0, pattern: str = "*") -> Path:
    images = list_images(folder, pattern=pattern)
    if not images:
        raise ValueError(f"No images found in {folder}")

    first = cv2.imread(str(images[0]))
    if first is None:
        raise ValueError(f"Cannot read image: {images[0]}")
    height, width = first.shape[:2]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create video writer: {output_path}")

    try:
        for image_path in images:
            frame = cv2.imread(str(image_path))
            if frame is None:
                continue
            if frame.shape[:2] != (height, width):
                frame = cv2.resize(frame, (width, height))
            writer.write(frame)
    finally:
        writer.release()
    return output_path


def video_to_images(
    video_path: Path,
    output_folder: Path,
    every: int = 1,
    prefix: str = "frame",
    digits: int = 6,
    fmt: str = "jpg",
) -> list[Path]:
    ensure_dir(output_folder)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    outputs: list[Path] = []
    frame_index = 0
    saved_index = 1
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % every == 0:
                output = output_folder / f"{prefix}_{saved_index:0{digits}d}.{fmt}"
                cv2.imwrite(str(output), frame)
                outputs.append(output)
                saved_index += 1
            frame_index += 1
    finally:
        cap.release()
    return outputs


def images_to_gif(folder: Path, output_path: Path, fps: float = 10.0, pattern: str = "*") -> Path:
    images = list_images(folder, pattern=pattern)
    if not images:
        raise ValueError(f"No images found in {folder}")
    frames = [Image.open(path).convert("RGB") for path in images]
    duration = int(1000 / fps)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=duration, loop=0)
    for frame in frames:
        frame.close()
    return output_path


def video_to_gif(
    video_path: Path,
    output_path: Path,
    fps: float = 10.0,
    start: float | None = None,
    end: float | None = None,
    size: str | None = None,
) -> Path:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_frame = int(start * source_fps) if start is not None else 0
    end_frame = int(end * source_fps) if end is not None else None
    sample_every = max(1, int(round(source_fps / fps)))
    target_size = parse_size(size) if size else None
    frames: list[Image.Image] = []

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_index = start_frame
    try:
        while True:
            if end_frame is not None and frame_index > end_frame:
                break
            ok, frame = cap.read()
            if not ok:
                break
            if (frame_index - start_frame) % sample_every == 0:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if target_size:
                    frame = cv2.resize(frame, target_size)
                frames.append(Image.fromarray(frame))
            frame_index += 1
    finally:
        cap.release()

    if not frames:
        raise ValueError("No frames were extracted for GIF")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    for frame in frames:
        frame.close()
    return output_path


def clip_video(
    video_path: Path,
    output_path: Path,
    start: float | None = None,
    end: float | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> Path:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    s_frame = start_frame if start_frame is not None else int((start or 0) * fps)
    e_frame = end_frame if end_frame is not None else (int(end * fps) if end is not None else None)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create video writer: {output_path}")

    cap.set(cv2.CAP_PROP_POS_FRAMES, s_frame)
    frame_index = s_frame
    try:
        while True:
            if e_frame is not None and frame_index > e_frame:
                break
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(frame)
            frame_index += 1
    finally:
        cap.release()
        writer.release()
    return output_path


def resize_video(video_path: Path, output_path: Path, size: str) -> Path:
    target_size = parse_size(size)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, target_size)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(cv2.resize(frame, target_size))
    finally:
        cap.release()
        writer.release()
    return output_path
