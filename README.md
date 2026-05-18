# devbits

## CLI style

`devbits` provides both a main command and standalone commands installed into your Python environment's PATH.

Main command style:

```bash
devbits clearcache .
devbits images2video frames/ -o output.mp4 --fps 30
```

Standalone command style:

```bash
clearcache .
images2video frames/ -o output.mp4 --fps 30
video2gif input.mp4 -o output.gif
clipvideo input.mp4 --start 3 --end 10 -o clip.mp4
```

After editable install, reopen the terminal or run `hash -r` if your shell does not immediately find the new commands.


`devbits` is a lightweight CLI toolkit for daily development utilities, including cache cleanup, media conversion, image helpers, dataset-like file operations, and project maintenance tools.

The project supports two CLI styles:

```bash
devbits <command> [options]
<command> [options]
```

## Features

### Project cleanup

```bash
devbits clearcache .
devbits clearcache . --all
devbits clearcache . --dry-run
```

Removes:

- `__pycache__/`
- `*.pyc`
- `*.pyo`
- optionally `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`

### Image and video conversion

```bash
devbits images2video ./frames -o output.mp4 --fps 30
devbits video2images input.mp4 -o ./frames --every 1
devbits images2gif ./frames -o output.gif --fps 10
devbits video2gif input.mp4 -o output.gif --fps 10 --start 2 --end 8
devbits clipvideo input.mp4 -o clip.mp4 --start 3 --end 10
devbits clipvideo input.mp4 -o clip.mp4 --start-frame 100 --end-frame 500
devbits resizevideo input.mp4 -o resized.mp4 --size 1280,720
```

### Image utilities

```bash
devbits image2ico logo.png -o logo.ico
devbits resizeimage input.jpg -o output.jpg --size 640,480
devbits batchimages ./images -o ./resized --size 640,480 --format jpg
devbits checkimages ./images --recursive
devbits contactsheet ./images -o sheet.jpg --cols 5 --labels
```

### Project utilities

```bash
devbits tree . --depth 3
devbits size . --top 20
devbits renamefiles ./images --prefix frame --digits 6
devbits renamefiles ./images --prefix frame --digits 6 --dry-run
devbits samplefiles ./images -o ./sample --num 100
```

## Installation for local development

```bash
git clone https://github.com/yourname/devbits.git
cd devbits
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Check the CLI:

```bash
devbits --help
devbits images2video --help
clearcache --help
images2video --help
```

## Build package

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

## Upload to TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
```

## Upload to PyPI

```bash
python -m twine upload dist/*
```

## Commands

| Command | Description |
|---|---|
| `clearcache` | Clear Python cache files. |
| `images2video` | Convert image sequence to MP4 video. |
| `video2images` | Extract frames from a video. |
| `images2gif` | Convert image sequence to GIF. |
| `video2gif` | Convert video to GIF. |
| `clipvideo` | Clip video by seconds or frame indices. |
| `resizevideo` | Resize a video. |
| `image2ico` | Convert image to `.ico`. |
| `resizeimage` | Resize an image. |
| `batchimages` | Batch resize or convert images. |
| `checkimages` | Check broken image files. |
| `contactsheet` | Create a contact sheet. |
| `tree` | Print a compact project tree. |
| `size` | Show top-level folder/file sizes. |
| `renamefiles` | Batch rename files. |
| `samplefiles` | Copy or move first N files. |

## Roadmap

- Interactive `clipvideo --gui`
- `mergevideos`
- `comparevideos`
- `concatframes`
- `annotatevideo`
- `watermark`
- `splitdataset`
- `countdataset`
- `dedupimages`
- Optional ROS helpers under `devbits[ros]`

## License

MIT
