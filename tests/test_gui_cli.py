from __future__ import annotations
from unittest.mock import patch
import pytest
from devbits.cli import main

def test_clipvideo_no_gui_requires_video(capsys) -> None:
    # Running clipvideo without GUI should return exit code 1 if video is missing
    exit_code = main(["clipvideo"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "video path is required when --gui is not specified" in captured.err

def test_clipvideo_with_gui_no_video() -> None:
    # Running clipvideo with --gui and no video should launch GUI (which we mock)
    with patch("devbits.gui.launch_gui") as mock_launch:
        main(["clipvideo", "--gui"])
        mock_launch.assert_called_once_with(None)

def test_clipvideo_with_gui_and_video(tmp_path) -> None:
    # Running clipvideo with --gui and a video should launch GUI with that path
    video_file = tmp_path / "sample.mp4"
    video_file.touch()
    with patch("devbits.gui.launch_gui") as mock_launch:
        main(["clipvideo", "--gui", str(video_file)])
        mock_launch.assert_called_once()
        called_arg = mock_launch.call_args[0][0]
        assert called_arg.name == "sample.mp4"

def test_gui_upload(tmp_path) -> None:
    from devbits.gui import _Handler
    import http.server
    import threading
    import urllib.request
    import json
    
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    
    class TestHandler(_Handler):
        pass
    TestHandler.upload_dir = str(upload_dir)
    TestHandler.export_dir = str(export_dir)
    TestHandler.video_path = None
        
    server = http.server.HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    
    try:
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        filename = "test_sample.mp4"
        file_content = b"fake video bytes"
        
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body))
            }
        )
        
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            resp_body = response.read().decode("utf-8")
            data = json.loads(resp_body)
            assert "src" in data
            assert data["src"] == f"/uploads/{filename}"
            
        saved_file = upload_dir / filename
        assert saved_file.exists()
        assert saved_file.read_bytes() == file_content
    finally:
        server.shutdown()
        server.server_close()
