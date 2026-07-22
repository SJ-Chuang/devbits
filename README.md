# devbits

A lightweight CLI toolkit for daily development utilities — video/image processing, project file management, and more.

## Installation

```bash
pip install devbits
```

Requires Python ≥ 3.9.

## Usage

All commands are available in two ways:

```bash
# As subcommands of devbits
devbits <command> [options]

# As standalone commands
<command> [options]
```

Use `--help` on any command for detailed usage and parameter descriptions:

```bash
devbits clipvideo --help
clipvideo --help
```

## Commands

### Video

| Command | Description |
|---------|-------------|
| `clipvideo` | Trim a video by time (seconds) or frame range. Includes `--gui` for browser-based editing. |
| `video2images` | Extract frames from a video. |
| `video2gif` | Convert a video (or a portion) to animated GIF. |
| `images2video` | Assemble an image sequence into an MP4 video. |
| `images2gif` | Assemble an image sequence into an animated GIF. |
| `resizevideo` | Re-encode a video at a different resolution. |

### Image

| Command | Description |
|---------|-------------|
| `resizeimage` | Resize a single image (preserves aspect ratio by default). |
| `recolor` | Recolor a logo/icon foreground, leaving the background intact. |
| `image2ico` | Convert an image to a multi-size ICO file. |
| `batchimages` | Batch resize or convert all images in a folder. |
| `checkimages` | Scan for broken / corrupt image files. |
| `contactsheet` | Generate a thumbnail grid (contact sheet) from a folder of images. |

### Project / Files

| Command | Description |
|---------|-------------|
| `clearcache` | Remove `__pycache__` and other Python cache directories. |
| `tree` | Print a directory tree. |
| `size` | List the largest files / folders, sorted by size. |
| `renamefiles` | Batch rename files sequentially. |
| `samplefiles` | Copy or move the first N files to another folder. |

### Network

| Command | Description |
|---------|-------------|
| `netscan` | List devices connected to your local network (Wi-Fi / router) with their IP, MAC, and hostname. `--lookup` adds the manufacturer. |

## Examples

```bash
# Trim video from 5s to 20s
clipvideo movie.mp4 --start 5.0 --end 20.0

# Open interactive clip editor in the browser
clipvideo movie.mp4 --gui

# Convert video to GIF (3.5s–10s at 15 fps)
video2gif movie.mp4 --start 3.5 --end 10.0 --fps 15

# Extract every 5th frame as PNG
video2images movie.mp4 --every 5 --format png

# Recolor a logo's foreground to black (keeps the background)
recolor logo.png

# Recolor a logo's foreground to a custom color (hex or R,G,B)
recolor logo.png --color '#1a73e8'
recolor logo.png --color 0,178,179

# Batch resize images to 800×600
batchimages ./photos -o ./resized --size 800,600

# Clean Python caches
clearcache . --all

# List every device on your local network
netscan

# Also identify each device's manufacturer (online OUI lookup)
netscan --lookup

# Scan a specific subnet, faster, without hostname lookups
netscan --network 192.168.1.0/24 --timeout 0.5 --no-resolve
```

> `netscan` reports IP, MAC, hostname and (with `--lookup`) the hardware
> **manufacturer** — a network scan can't read a device's CPU/RAM/OS. Phones and
> laptops that use a randomized/private MAC show up as `(private)` and can't be
> attributed to a vendor.

## Output Defaults

When `-o` / `--output` is omitted, the output filename is derived from the input:

```
clipvideo movie.mp4          →  movie_clip.mp4
video2gif movie.mp4          →  movie.gif
resizeimage photo.jpg        →  photo_resized.jpg
recolor logo.png             →  logo_revised.png
contactsheet ./photos        →  photos_sheet.jpg
```

## License

MIT
