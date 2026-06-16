from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cache import clear_cache
from .image import batch_images, check_images, contact_sheet, image_to_ico, recolor_image, resize_image
from .media import clip_video, images_to_gif, images_to_video, resize_video, video_to_gif, video_to_images
from .project import print_tree, rename_files, sample_files, top_sizes
from .utils import ensure_exists


# ---------------------------------------------------------------------------
# Helper: derive default output path from input path
# ---------------------------------------------------------------------------

def _derive_output(input_path: Path, suffix: str, tag: str = "") -> Path:
    """Build ``<stem>[_<tag>].<suffix>`` next to the input file."""
    stem = input_path.stem
    name = f"{stem}_{tag}{suffix}" if tag else f"{stem}{suffix}"
    return input_path.parent / name


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devbits",
        description="Daily development utility CLI toolkit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="devbits 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    # ── clearcache ─────────────────────────────────────────────
    p = sub.add_parser(
        "clearcache",
        help="Clear Python cache files under a folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Recursively remove __pycache__ directories under the given folder.\n"
            "With --all, also removes .pytest_cache, .mypy_cache, and .ruff_cache."
        ),
    )
    p.add_argument("folder", type=Path, help="Root folder to scan.")
    p.add_argument("--all", action="store_true", help="Also remove pytest / mypy / ruff caches.")
    p.add_argument("--dry-run", action="store_true", help="List targets without deleting.")
    p.set_defaults(func=cmd_clearcache)

    # ── images2video ───────────────────────────────────────────
    p = sub.add_parser(
        "images2video",
        help="Convert image sequence to MP4 video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Read images from a folder (sorted by name), encode them into an MP4\n"
            "video at the specified frame rate.\n\n"
            "Examples:\n"
            "  devbits images2video ./frames\n"
            "  devbits images2video ./frames --fps 60 --pattern '*.png'"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder containing source images.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output video path. Default: <folder_name>.mp4")
    p.add_argument("--fps", type=float, default=30.0,
                   help="Frame rate (frames per second). Default: 30.0")
    p.add_argument("--pattern", default="*",
                   help="Glob pattern to filter images, e.g. '*.png'. Default: '*'")
    p.set_defaults(func=cmd_images2video)

    # ── video2images ───────────────────────────────────────────
    p = sub.add_parser(
        "video2images",
        help="Extract frames from a video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Decode a video file and save individual frames as images.\n\n"
            "Examples:\n"
            "  devbits video2images movie.mp4\n"
            "  devbits video2images movie.mp4 --every 5 --format png"
        ),
    )
    p.add_argument("video", type=Path, help="Input video file.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output folder for frames. Default: <video_stem>_frames/")
    p.add_argument("--every", type=int, default=1,
                   help="Save every N-th frame (1 = all frames). Default: 1")
    p.add_argument("--prefix", default="frame",
                   help="Filename prefix for saved frames. Default: 'frame'")
    p.add_argument("--digits", type=int, default=6,
                   help="Number of zero-padded digits in filenames. Default: 6")
    p.add_argument("--format", default="jpg",
                   help="Image format for saved frames (jpg, png, bmp). Default: 'jpg'")
    p.set_defaults(func=cmd_video2images)

    # ── images2gif ─────────────────────────────────────────────
    p = sub.add_parser(
        "images2gif",
        help="Convert image sequence to GIF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Read images from a folder (sorted by name) and assemble them into\n"
            "an animated GIF.\n\n"
            "Examples:\n"
            "  devbits images2gif ./frames\n"
            "  devbits images2gif ./frames --fps 15 --pattern '*.png'"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder containing source images.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output GIF path. Default: <folder_name>.gif")
    p.add_argument("--fps", type=float, default=10.0,
                   help="Frame rate (frames per second). Default: 10.0")
    p.add_argument("--pattern", default="*",
                   help="Glob pattern to filter images. Default: '*'")
    p.set_defaults(func=cmd_images2gif)

    # ── video2gif ──────────────────────────────────────────────
    p = sub.add_parser(
        "video2gif",
        help="Convert video to GIF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Convert a video file (or a portion of it) into an animated GIF.\n\n"
            "Time arguments (--start, --end) are in seconds.\n\n"
            "Examples:\n"
            "  devbits video2gif movie.mp4\n"
            "  devbits video2gif movie.mp4 --start 3.5 --end 10.0 --fps 15\n"
            "  devbits video2gif movie.mp4 --size 640,360"
        ),
    )
    p.add_argument("video", type=Path, help="Input video file.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output GIF path. Default: <video_stem>.gif")
    p.add_argument("--fps", type=float, default=10.0,
                   help="GIF frame rate (frames per second). Default: 10.0")
    p.add_argument("--start", type=float, metavar="SEC",
                   help="Start time in seconds (from the beginning of the video).")
    p.add_argument("--end", type=float, metavar="SEC",
                   help="End time in seconds (from the beginning of the video).")
    p.add_argument("--size", metavar="W,H",
                   help="Output size as 'width,height' in pixels, e.g. 640,360.")
    p.set_defaults(func=cmd_video2gif)

    # ── clipvideo ──────────────────────────────────────────────
    p = sub.add_parser(
        "clipvideo",
        help="Clip (trim) a video by time range or frame range.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Trim a portion of a video. You can specify the range in seconds\n"
            "(--start / --end) or in frame indices (--start-frame / --end-frame).\n"
            "If both are omitted, the full video is copied.\n\n"
            "Use --gui to open the interactive browser-based clip editor.\n\n"
            "Examples:\n"
            "  devbits clipvideo movie.mp4 --start 5.0 --end 20.0\n"
            "  devbits clipvideo movie.mp4 --start-frame 150 --end-frame 600\n"
            "  devbits clipvideo movie.mp4 --gui"
        ),
    )
    p.add_argument("video", type=Path, nargs="?", default=None,
                   help="Input video file (optional when --gui is used).")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output video path. Default: <video_stem>_clip.mp4")
    p.add_argument("--start", type=float, metavar="SEC",
                   help="Start time in seconds.")
    p.add_argument("--end", type=float, metavar="SEC",
                   help="End time in seconds.")
    p.add_argument("--start-frame", type=int, metavar="IDX",
                   help="Start frame index (0-based).")
    p.add_argument("--end-frame", type=int, metavar="IDX",
                   help="End frame index (0-based, inclusive).")
    p.add_argument("--gui", action="store_true",
                   help="Open interactive browser-based clip editor.")
    p.set_defaults(func=cmd_clipvideo)

    # ── resizevideo ────────────────────────────────────────────
    p = sub.add_parser(
        "resizevideo",
        help="Resize a video to a specified resolution.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Re-encode a video at a different resolution.\n\n"
            "Examples:\n"
            "  devbits resizevideo movie.mp4 --size 1280,720\n"
            "  devbits resizevideo movie.mp4 --size 640,480 -o small.mp4"
        ),
    )
    p.add_argument("video", type=Path, help="Input video file.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output video path. Default: <video_stem>_resized.mp4")
    p.add_argument("--size", required=True, metavar="W,H",
                   help="Target resolution as 'width,height' in pixels, e.g. 1280,720.")
    p.set_defaults(func=cmd_resizevideo)

    # ── image2ico ──────────────────────────────────────────────
    p = sub.add_parser(
        "image2ico",
        help="Convert an image to a multi-size ICO file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Generate a Windows ICO icon file containing multiple sizes.\n\n"
            "Examples:\n"
            "  devbits image2ico logo.png\n"
            "  devbits image2ico logo.png --sizes 32,64,128"
        ),
    )
    p.add_argument("image", type=Path, help="Input image file.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output ICO path. Default: <image_stem>.ico")
    p.add_argument("--sizes", default="16,32,48,64,128,256",
                   help="Comma-separated icon sizes in pixels. Default: 16,32,48,64,128,256")
    p.set_defaults(func=cmd_image2ico)

    # ── resizeimage ────────────────────────────────────────────
    p = sub.add_parser(
        "resizeimage",
        help="Resize an image to a specified size.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Resize a single image. By default, aspect ratio is preserved.\n\n"
            "Examples:\n"
            "  devbits resizeimage photo.jpg --size 800,600\n"
            "  devbits resizeimage photo.png --size 256,256 --no-keep-ratio"
        ),
    )
    p.add_argument("image", type=Path, help="Input image file.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output image path. Default: <image_stem>_resized.<ext>")
    p.add_argument("--size", required=True, metavar="W,H",
                   help="Target size as 'width,height' in pixels, e.g. 800,600.")
    p.add_argument("--no-keep-ratio", action="store_true",
                   help="Do not preserve aspect ratio; stretch to exact size.")
    p.set_defaults(func=cmd_resizeimage)

    # ── recolor ────────────────────────────────────────────────
    p = sub.add_parser(
        "recolor",
        help="Recolor the foreground of a logo / icon image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Recolor a logo or icon. The background (transparent or a lighter\n"
            "surrounding color) is detected automatically and left untouched,\n"
            "while every foreground pixel is repainted with the target color.\n"
            "The result is always saved as an RGBA PNG.\n\n"
            "Examples:\n"
            "  devbits recolor logo.png\n"
            "  devbits recolor logo.png --color '#1a73e8'\n"
            "  devbits recolor logo.png --color 0,178,179\n"
            "  devbits recolor icon.jpg --color white --threshold 90"
        ),
    )
    p.add_argument("image", type=Path, help="Input logo / icon image.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output image path. Default: <image_stem>_revised.png")
    p.add_argument("--color", default="black",
                   help="Target foreground color: name, hex, or R,G,B (e.g. black, '#1a73e8', 0,178,179). Default: black")
    p.add_argument("--threshold", type=int, default=60,
                   help="Color distance from the background for opaque images. Default: 60")
    p.set_defaults(func=cmd_recolor)

    # ── batchimages ────────────────────────────────────────────
    p = sub.add_parser(
        "batchimages",
        help="Batch resize or convert images in a folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Process all images in a folder: resize, convert format, or both.\n\n"
            "Examples:\n"
            "  devbits batchimages ./photos -o ./resized --size 800,600\n"
            "  devbits batchimages ./raw -o ./converted --format png"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder containing source images.")
    p.add_argument("-o", "--output", type=Path, required=True,
                   help="Output folder for processed images (required).")
    p.add_argument("--size", metavar="W,H",
                   help="Target size as 'width,height' in pixels.")
    p.add_argument("--format",
                   help="Convert images to this format (jpg, png, bmp, etc.).")
    p.set_defaults(func=cmd_batchimages)

    # ── checkimages ────────────────────────────────────────────
    p = sub.add_parser(
        "checkimages",
        help="Scan for broken / corrupt image files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Scan a folder for image files that cannot be opened or decoded.\n\n"
            "Examples:\n"
            "  devbits checkimages ./photos\n"
            "  devbits checkimages ./photos --recursive --remove-broken"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder to scan.")
    p.add_argument("--recursive", action="store_true",
                   help="Scan sub-folders recursively.")
    p.add_argument("--remove-broken", action="store_true",
                   help="Delete broken image files after detection.")
    p.set_defaults(func=cmd_checkimages)

    # ── contactsheet ───────────────────────────────────────────
    p = sub.add_parser(
        "contactsheet",
        help="Create a contact sheet (thumbnail grid) from images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Generate a single image containing a grid of thumbnails from all\n"
            "images in a folder.\n\n"
            "Examples:\n"
            "  devbits contactsheet ./photos\n"
            "  devbits contactsheet ./photos --cols 8 --thumb-size 128,128 --labels"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder containing source images.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output image path. Default: <folder_name>_sheet.jpg")
    p.add_argument("--cols", type=int, default=5,
                   help="Number of columns in the grid. Default: 5")
    p.add_argument("--thumb-size", default="256,256", metavar="W,H",
                   help="Thumbnail size as 'width,height' in pixels. Default: 256,256")
    p.add_argument("--labels", action="store_true",
                   help="Print filenames below each thumbnail.")
    p.set_defaults(func=cmd_contactsheet)

    # ── tree ───────────────────────────────────────────────────
    p = sub.add_parser(
        "tree",
        help="Print a project directory tree.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Display the directory structure as an indented tree.\n\n"
            "Examples:\n"
            "  devbits tree\n"
            "  devbits tree ./src --depth 5"
        ),
    )
    p.add_argument("folder", type=Path, nargs="?", default=Path("."),
                   help="Root folder to display. Default: current directory")
    p.add_argument("--depth", type=int, default=3,
                   help="Maximum depth to traverse. Default: 3")
    p.set_defaults(func=cmd_tree)

    # ── size ───────────────────────────────────────────────────
    p = sub.add_parser(
        "size",
        help="Show top-level folder / file sizes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "List the largest items under a folder, sorted by size.\n\n"
            "Examples:\n"
            "  devbits size\n"
            "  devbits size /data --top 50"
        ),
    )
    p.add_argument("folder", type=Path, nargs="?", default=Path("."),
                   help="Folder to inspect. Default: current directory")
    p.add_argument("--top", type=int, default=20,
                   help="Number of items to show. Default: 20")
    p.set_defaults(func=cmd_size)

    # ── renamefiles ────────────────────────────────────────────
    p = sub.add_parser(
        "renamefiles",
        help="Batch rename files sequentially.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Rename all files in a folder to a sequential numbered pattern:\n"
            "  <prefix><number>.<ext>\n\n"
            "Examples:\n"
            "  devbits renamefiles ./photos --prefix img --digits 4\n"
            "  devbits renamefiles ./data --start 100 --dry-run"
        ),
    )
    p.add_argument("folder", type=Path, help="Folder containing files to rename.")
    p.add_argument("--prefix", default="file",
                   help="Filename prefix. Default: 'file'")
    p.add_argument("--digits", type=int, default=6,
                   help="Number of zero-padded digits. Default: 6")
    p.add_argument("--start", type=int, default=1,
                   help="Starting number. Default: 1")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview renames without applying.")
    p.set_defaults(func=cmd_renamefiles)

    # ── samplefiles ────────────────────────────────────────────
    p = sub.add_parser(
        "samplefiles",
        help="Copy (or move) the first N files to another folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Pick the first N files (sorted by name) from a folder and copy\n"
            "(or move) them to a destination folder.\n\n"
            "Examples:\n"
            "  devbits samplefiles ./photos -o ./sample --num 50\n"
            "  devbits samplefiles ./data -o ./subset --num 10 --move"
        ),
    )
    p.add_argument("folder", type=Path, help="Source folder.")
    p.add_argument("-o", "--output", type=Path, required=True,
                   help="Destination folder (required).")
    p.add_argument("--num", type=int, required=True,
                   help="Number of files to sample.")
    p.add_argument("--move", action="store_true",
                   help="Move files instead of copying.")
    p.set_defaults(func=cmd_samplefiles)

    return parser


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_clearcache(args: argparse.Namespace) -> None:
    targets = clear_cache(ensure_exists(args.folder), include_extra=args.all, dry_run=args.dry_run)
    for target in targets:
        print(target)
    print(f"{'Found' if args.dry_run else 'Removed'} {len(targets)} cache item(s).")


def cmd_images2video(args: argparse.Namespace) -> None:
    folder = ensure_exists(args.folder)
    output = args.output or _derive_output(folder, ".mp4")
    print(images_to_video(folder, output, args.fps, args.pattern))


def cmd_video2images(args: argparse.Namespace) -> None:
    video = ensure_exists(args.video)
    output = args.output or (video.parent / f"{video.stem}_frames")
    outputs = video_to_images(video, output, args.every, args.prefix, args.digits, args.format)
    print(f"Saved {len(outputs)} frame(s) to {output}")


def cmd_images2gif(args: argparse.Namespace) -> None:
    folder = ensure_exists(args.folder)
    output = args.output or _derive_output(folder, ".gif")
    print(images_to_gif(folder, output, args.fps, args.pattern))


def cmd_video2gif(args: argparse.Namespace) -> None:
    video = ensure_exists(args.video)
    output = args.output or _derive_output(video, ".gif")
    print(video_to_gif(video, output, args.fps, args.start, args.end, args.size))


def cmd_clipvideo(args: argparse.Namespace) -> None:
    if args.gui:
        from .gui import launch_gui
        launch_gui(args.video)
        return
    if args.video is None:
        raise ValueError("video path is required when --gui is not specified")
    video = ensure_exists(args.video)
    output = args.output or _derive_output(video, ".mp4", "clip")
    print(clip_video(video, output, args.start, args.end, args.start_frame, args.end_frame))


def cmd_resizevideo(args: argparse.Namespace) -> None:
    video = ensure_exists(args.video)
    output = args.output or _derive_output(video, ".mp4", "resized")
    print(resize_video(video, output, args.size))


def cmd_image2ico(args: argparse.Namespace) -> None:
    image = ensure_exists(args.image)
    output = args.output or _derive_output(image, ".ico")
    print(image_to_ico(image, output, args.sizes))


def cmd_resizeimage(args: argparse.Namespace) -> None:
    image = ensure_exists(args.image)
    output = args.output or _derive_output(image, image.suffix, "resized")
    print(resize_image(image, output, args.size, not args.no_keep_ratio))


def cmd_recolor(args: argparse.Namespace) -> None:
    image = ensure_exists(args.image)
    output = args.output or _derive_output(image, ".png", "revised")
    print(recolor_image(image, output, args.color, args.threshold))


def cmd_batchimages(args: argparse.Namespace) -> None:
    outputs = batch_images(ensure_exists(args.folder), args.output, args.size, args.format)
    print(f"Saved {len(outputs)} image(s) to {args.output}")


def cmd_checkimages(args: argparse.Namespace) -> None:
    broken = check_images(ensure_exists(args.folder), args.recursive, args.remove_broken)
    if broken:
        print("Broken images:")
        for path in broken:
            print(path)
    print(f"Found {len(broken)} broken image(s).")


def cmd_contactsheet(args: argparse.Namespace) -> None:
    folder = ensure_exists(args.folder)
    output = args.output or (folder.parent / f"{folder.name}_sheet.jpg")
    print(contact_sheet(folder, output, args.cols, args.thumb_size, labels=args.labels))


def cmd_tree(args: argparse.Namespace) -> None:
    for line in print_tree(ensure_exists(args.folder), args.depth):
        print(line)


def cmd_size(args: argparse.Namespace) -> None:
    for path, _, size_text in top_sizes(ensure_exists(args.folder), args.top):
        print(f"{size_text:>10}  {path}")


def cmd_renamefiles(args: argparse.Namespace) -> None:
    mappings = rename_files(ensure_exists(args.folder), args.prefix, args.digits, args.start, args.dry_run)
    for old, new in mappings:
        print(f"{old.name} -> {new.name}")
    print(f"{'Planned' if args.dry_run else 'Renamed'} {len(mappings)} file(s).")


def cmd_samplefiles(args: argparse.Namespace) -> None:
    outputs = sample_files(ensure_exists(args.folder), args.output, args.num, copy=not args.move)
    print(f"Saved {len(outputs)} file(s) to {args.output}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
