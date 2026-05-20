import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from PIL import Image, ImageTk
from pathlib import Path
import threading

class VideoEditorGUI:
    def __init__(self, root, video_path):
        self.root = root
        self.root.title("ClipVideo Editor")
        self.root.geometry("1000x700")

        self.video_path = Path(video_path) if video_path else None
        
        # Clip data: list of dicts {'path': Path, 'start_f': int, 'end_f': int, 'speed': float}
        self.clips = []
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.width = 640
        self.height = 480
        
        if self.video_path:
            self._load_video_info(self.video_path)

        self.is_playing = False
        self.current_frame = 0
        self.selected_clip_index = -1

        self._build_ui()
        self._update_timeline()
        self._show_frame()

    def _load_video_info(self, path):
        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.clips = [{'path': path, 'start_f': 0, 'end_f': self.total_frames - 1, 'speed': 1.0}]
            cap.release()

    def _build_ui(self):
        # Top: Video display
        self.video_frame = ttk.Frame(self.root)
        self.video_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.lbl_video = tk.Label(self.video_frame, bg="black")
        self.lbl_video.pack(fill=tk.BOTH, expand=True)

        # Middle: Controls
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="Play/Pause", command=self.toggle_play).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Split", command=self.split_clip).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Delete Clip", command=self.delete_clip).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Move Left", command=lambda: self.move_clip(-1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Move Right", command=lambda: self.move_clip(1)).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = ttk.Scale(control_frame, from_=0.25, to=4.0, variable=self.speed_var, command=self.change_speed)
        self.speed_scale.pack(side=tk.LEFT, padx=5)

        # Export controls
        export_frame = ttk.Frame(control_frame)
        export_frame.pack(side=tk.RIGHT, padx=5)
        self.format_var = tk.StringVar(value="mp4")
        ttk.Combobox(export_frame, textvariable=self.format_var, values=["mp4", "avi", "gif"], width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="Export", command=self.export_video).pack(side=tk.LEFT, padx=5)

        # Bottom: Timeline
        self.timeline_canvas = tk.Canvas(self.root, height=100, bg="gray20")
        self.timeline_canvas.pack(fill=tk.X, padx=10, pady=10)
        self.timeline_canvas.bind("<Button-1>", self.on_timeline_click)
        self.timeline_canvas.bind("<B1-Motion>", self.on_timeline_drag)

    def toggle_play(self):
        self.is_playing = not self.is_playing
        if self.is_playing:
            self._play_loop()

    def _play_loop(self):
        if not self.is_playing:
            return
        
        self.current_frame += 1
        total_len = sum((c['end_f'] - c['start_f']) / c['speed'] for c in self.clips)
        if self.current_frame >= total_len:
            self.current_frame = 0
            self.is_playing = False
            self._update_timeline()
            self._show_frame()
            return

        self._show_frame()
        self._update_timeline()
        
        # Calculate delay based on current clip speed
        delay = int(1000 / self.fps)
        clip, _ = self._get_clip_at_frame(self.current_frame)
        if clip:
            delay = int(delay / clip['speed'])
            
        self.root.after(delay, self._play_loop)

    def _get_clip_at_frame(self, global_f):
        acc = 0
        for i, c in enumerate(self.clips):
            c_len = (c['end_f'] - c['start_f']) / c['speed']
            if acc <= global_f < acc + c_len:
                local_f = c['start_f'] + (global_f - acc) * c['speed']
                return c, int(local_f)
            acc += c_len
        return None, 0

    def _show_frame(self):
        if not self.clips:
            return
            
        clip, local_f = self._get_clip_at_frame(self.current_frame)
        if not clip:
            return

        if self.cap is None or self.cap_path != clip['path']:
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(str(clip['path']))
            self.cap_path = clip['path']

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, local_f)
        ok, frame = self.cap.read()
        if ok:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Resize for display
            h, w = frame.shape[:2]
            display_h = 400
            display_w = int(w * (display_h / h))
            frame = cv2.resize(frame, (display_w, display_h))
            
            img = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self.lbl_video.config(image=img)
            self.lbl_video.image = img

    def _update_timeline(self):
        self.timeline_canvas.delete("all")
        if not self.clips:
            return
            
        w = self.timeline_canvas.winfo_width()
        if w == 1: # Window not initialized fully
            w = 1000
            
        total_len = sum((c['end_f'] - c['start_f']) / c['speed'] for c in self.clips)
        if total_len == 0:
            return

        x = 0
        for i, c in enumerate(self.clips):
            c_len = (c['end_f'] - c['start_f']) / c['speed']
            c_w = (c_len / total_len) * w
            color = "royalblue" if i == self.selected_clip_index else "steelblue"
            self.timeline_canvas.create_rectangle(x, 10, x + c_w, 90, fill=color, outline="white", tags=f"clip_{i}")
            self.timeline_canvas.create_text(x + c_w/2, 50, text=f"Clip {i+1}\n{c['speed']}x", fill="white")
            x += c_w

        # Draw playhead
        playhead_x = (self.current_frame / total_len) * w
        self.timeline_canvas.create_line(playhead_x, 0, playhead_x, 100, fill="red", width=2, tags="playhead")

    def on_timeline_click(self, event):
        w = self.timeline_canvas.winfo_width()
        total_len = sum((c['end_f'] - c['start_f']) / c['speed'] for c in self.clips)
        
        click_f = (event.x / w) * total_len
        self.current_frame = max(0, min(click_f, total_len - 1))
        
        # Find selected clip
        acc = 0
        self.selected_clip_index = -1
        for i, c in enumerate(self.clips):
            c_len = (c['end_f'] - c['start_f']) / c['speed']
            if acc <= self.current_frame <= acc + c_len:
                self.selected_clip_index = i
                self.speed_var.set(c['speed'])
                break
            acc += c_len
            
        self._update_timeline()
        self._show_frame()

    def on_timeline_drag(self, event):
        self.on_timeline_click(event)

    def change_speed(self, val):
        if self.selected_clip_index != -1:
            self.clips[self.selected_clip_index]['speed'] = round(float(val), 2)
            self._update_timeline()

    def split_clip(self):
        if self.selected_clip_index == -1:
            return
            
        acc = 0
        for i, c in enumerate(self.clips):
            c_len = (c['end_f'] - c['start_f']) / c['speed']
            if i == self.selected_clip_index:
                global_offset = self.current_frame - acc
                local_f = c['start_f'] + global_offset * c['speed']
                
                # Create two clips
                c1 = c.copy()
                c1['end_f'] = int(local_f)
                
                c2 = c.copy()
                c2['start_f'] = int(local_f) + 1
                
                if c1['end_f'] > c1['start_f'] and c2['end_f'] > c2['start_f']:
                    self.clips[i] = c1
                    self.clips.insert(i + 1, c2)
                break
            acc += c_len
            
        self._update_timeline()

    def delete_clip(self):
        if self.selected_clip_index != -1 and len(self.clips) > 1:
            del self.clips[self.selected_clip_index]
            self.selected_clip_index = -1
            self.current_frame = 0
            self._update_timeline()
            self._show_frame()

    def move_clip(self, direction):
        i = self.selected_clip_index
        if i == -1: return
        new_i = i + direction
        if 0 <= new_i < len(self.clips):
            self.clips[i], self.clips[new_i] = self.clips[new_i], self.clips[i]
            self.selected_clip_index = new_i
            self._update_timeline()

    def export_video(self):
        if not self.clips:
            return
            
        fmt = self.format_var.get()
        out_path = filedialog.asksaveasfilename(defaultextension=f".{fmt}")
        if not out_path:
            return

        def process():
            from .media import images_to_gif
            import tempfile
            
            if fmt == "gif":
                temp_dir = tempfile.mkdtemp()
                temp_path = Path(temp_dir)
            else:
                fourcc = cv2.VideoWriter_fourcc(*"mp4v") if fmt == "mp4" else cv2.VideoWriter_fourcc(*"XVID")
                writer = cv2.VideoWriter(out_path, fourcc, self.fps, (self.width, self.height))

            frame_idx = 0
            for c in self.clips:
                cap = cv2.VideoCapture(str(c['path']))
                cap.set(cv2.CAP_PROP_POS_FRAMES, c['start_f'])
                f = c['start_f']
                while f <= c['end_f']:
                    ok, frame = cap.read()
                    if not ok: break
                    
                    if fmt == "gif":
                        cv2.imwrite(str(temp_path / f"{frame_idx:06d}.jpg"), frame)
                    else:
                        writer.write(frame)
                    
                    # Skip frames based on speed
                    f += c['speed']
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
                    frame_idx += 1
                cap.release()

            if fmt == "gif":
                images_to_gif(temp_path, Path(out_path), fps=self.fps)
                
            elif fmt in ["mp4", "avi"]:
                writer.release()
                
            messagebox.showinfo("Export", "Export complete!")

        threading.Thread(target=process, daemon=True).start()

def launch_gui(video_path: Path | None = None):
    root = tk.Tk()
    app = VideoEditorGUI(root, video_path)
    root.mainloop()
