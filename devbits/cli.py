from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cache import clear_cache
from .image import batch_images, check_images, contact_sheet, image_to_ico, resize_image
from .media import clip_video, images_to_gif, images_to_video, resize_video, video_to_gif, video_to_images
from .project import print_tree, rename_files, sample_files, top_sizes
from .utils import ensure_exists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devbits", description="Daily development utility CLI toolkit.")
    parser.add_argument("--version", action="version", version="devbits 0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("clearcache", help="Clear Python cache files under a folder.")
    p.add_argument("folder", type=Path)
    p.add_argument("--all", action="store_true", help="Also remove pytest, mypy, and ruff caches.")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_clearcache)

    p = sub.add_parser("images2video", help="Convert image sequence to MP4 video.")
    p.add_argument("folder", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("output.mp4"))
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--pattern", default="*")
    p.set_defaults(func=cmd_images2video)

    p = sub.add_parser("video2images", help="Extract frames from a video.")
    p.add_argument("video", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("frames"))
    p.add_argument("--every", type=int, default=1)
    p.add_argument("--prefix", default="frame")
    p.add_argument("--digits", type=int, default=6)
    p.add_argument("--format", default="jpg")
    p.set_defaults(func=cmd_video2images)

    p = sub.add_parser("images2gif", help="Convert image sequence to GIF.")
    p.add_argument("folder", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("output.gif"))
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--pattern", default="*")
    p.set_defaults(func=cmd_images2gif)

    p = sub.add_parser("video2gif", help="Convert video to GIF.")
    p.add_argument("video", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("output.gif"))
    p.add_argument("--fps", type=float, default=10.0)
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--size", help="Output size, e.g. 640,360")
    p.set_defaults(func=cmd_video2gif)

    p = sub.add_parser("clipvideo", help="Clip video by seconds or frame indices.")
    p.add_argument("video", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("clip.mp4"))
    p.add_argument("--start", type=float)
    p.add_argument("--end", type=float)
    p.add_argument("--start-frame", type=int)
    p.add_argument("--end-frame", type=int)
    p.add_argument("--gui", action="store_true", help="Reserved for future GUI clip selection.")
    p.set_defaults(func=cmd_clipvideo)

    p = sub.add_parser("resizevideo", help="Resize a video.")
    p.add_argument("video", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("resized.mp4"))
    p.add_argument("--size", required=True, help="Output size, e.g. 1280,720")
    p.set_defaults(func=cmd_resizevideo)

    p = sub.add_parser("image2ico", help="Convert an image to ICO.")
    p.add_argument("image", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("image.ico"))
    p.add_argument("--sizes", default="16,32,48,64,128,256")
    p.set_defaults(func=cmd_image2ico)

    p = sub.add_parser("resizeimage", help="Resize an image.")
    p.add_argument("image", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("resized.jpg"))
    p.add_argument("--size", required=True)
    p.add_argument("--no-keep-ratio", action="store_true")
    p.set_defaults(func=cmd_resizeimage)

    p = sub.add_parser("batchimages", help="Batch resize or convert images.")
    p.add_argument("folder", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--size")
    p.add_argument("--format")
    p.set_defaults(func=cmd_batchimages)

    p = sub.add_parser("checkimages", help="Check broken image files.")
    p.add_argument("folder", type=Path)
    p.add_argument("--recursive", action="store_true")
    p.add_argument("--remove-broken", action="store_true")
    p.set_defaults(func=cmd_checkimages)

    p = sub.add_parser("contactsheet", help="Create a contact sheet from images.")
    p.add_argument("folder", type=Path)
    p.add_argument("-o", "--output", type=Path, default=Path("sheet.jpg"))
    p.add_argument("--cols", type=int, default=5)
    p.add_argument("--thumb-size", default="256,256")
    p.add_argument("--labels", action="store_true")
    p.set_defaults(func=cmd_contactsheet)

    p = sub.add_parser("tree", help="Print project tree.")
    p.add_argument("folder", type=Path, nargs="?", default=Path("."))
    p.add_argument("--depth", type=int, default=3)
    p.set_defaults(func=cmd_tree)

    p = sub.add_parser("size", help="Show top-level folder sizes.")
    p.add_argument("folder", type=Path, nargs="?", default=Path("."))
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(func=cmd_size)

    p = sub.add_parser("renamefiles", help="Batch rename files in a folder.")
    p.add_argument("folder", type=Path)
    p.add_argument("--prefix", default="file")
    p.add_argument("--digits", type=int, default=6)
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_renamefiles)

    p = sub.add_parser("samplefiles", help="Copy first N files into another folder.")
    p.add_argument("folder", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--num", type=int, required=True)
    p.add_argument("--move", action="store_true")
    p.set_defaults(func=cmd_samplefiles)
    return parser


def cmd_clearcache(args: argparse.Namespace) -> None:
    targets = clear_cache(ensure_exists(args.folder), include_extra=args.all, dry_run=args.dry_run)
    for target in targets:
        print(target)
    print(f"{'Found' if args.dry_run else 'Removed'} {len(targets)} cache item(s).")


def cmd_images2video(args: argparse.Namespace) -> None:
    print(images_to_video(ensure_exists(args.folder), args.output, args.fps, args.pattern))


def cmd_video2images(args: argparse.Namespace) -> None:
    outputs = video_to_images(ensure_exists(args.video), args.output, args.every, args.prefix, args.digits, args.format)
    print(f"Saved {len(outputs)} frame(s) to {args.output}")


def cmd_images2gif(args: argparse.Namespace) -> None:
    print(images_to_gif(ensure_exists(args.folder), args.output, args.fps, args.pattern))


def cmd_video2gif(args: argparse.Namespace) -> None:
    print(video_to_gif(ensure_exists(args.video), args.output, args.fps, args.start, args.end, args.size))


def cmd_clipvideo(args: argparse.Namespace) -> None:
    if args.gui:
        print("Warning: --gui is reserved for a future interactive clip selector; using CLI options now.")
    print(clip_video(ensure_exists(args.video), args.output, args.start, args.end, args.start_frame, args.end_frame))


def cmd_resizevideo(args: argparse.Namespace) -> None:
    print(resize_video(ensure_exists(args.video), args.output, args.size))


def cmd_image2ico(args: argparse.Namespace) -> None:
    print(image_to_ico(ensure_exists(args.image), args.output, args.sizes))


def cmd_resizeimage(args: argparse.Namespace) -> None:
    print(resize_image(ensure_exists(args.image), args.output, args.size, not args.no_keep_ratio))


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
    print(contact_sheet(ensure_exists(args.folder), args.output, args.cols, args.thumb_size, labels=args.labels))


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
