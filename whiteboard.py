from typing import List, Optional
import os
import io
import threading
import requests
import json
import re

import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox

try:
    from PIL import ImageGrab
except ImportError as exc:
    raise SystemExit(
        "Pillow is required. Install with: pip install Pillow"
    ) from exc

# Load .env if present (for GEMINI_API_KEY, HF_API_TOKEN, etc.)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass
try:
    import google.generativeai as genai  # type: ignore
    _GEMINI_AVAILABLE = True
except Exception:
    _GEMINI_AVAILABLE = False


class WhiteboardApp(tk.Tk):
    """A simple whiteboard application with drawing, eraser, undo/redo, and save-as-PNG."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Whiteboard")
        self.geometry("1200x800")
        self.minsize(800, 500)

        # Drawing state
        self.current_color: str = "#000000"
        self.background_color: str = "#FFFFFF"
        self.brush_size: int = 4
        self.is_eraser: bool = False
        self.draw_mode: str = "pen"  # "pen", "rectangle", "circle", "line"

        # Stroke management: tag each stroke so we can hide/show for undo/redo
        self.stroke_index: int = 0
        self.current_stroke_tag: Optional[str] = None
        self._current_stroke_has_items: bool = False
        self.undo_stack: List[str] = []  # list of stroke tags
        self.redo_stack: List[str] = []  # list of stroke tags

        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        self._preview_item = None

        self._build_ui()
        self._bind_shortcuts()

    def _build_ui(self) -> None:
        # Configure layout
        self.columnconfigure(0, weight=0)  # toolbar
        self.columnconfigure(1, weight=1)  # canvas
        self.rowconfigure(0, weight=1)

        toolbar = ttk.Frame(self, padding=(10, 10))
        toolbar.grid(row=0, column=0, sticky="ns")
        toolbar.columnconfigure(0, weight=1)

        # Buttons and controls
        color_btn = ttk.Button(toolbar, text="Color", command=self.choose_color)
        color_btn.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.eraser_var = tk.BooleanVar(value=self.is_eraser)
        eraser_btn = ttk.Checkbutton(
            toolbar, text="Eraser", variable=self.eraser_var, command=self.toggle_eraser
        )
        eraser_btn.grid(row=1, column=0, sticky="ew", pady=6)

        # Shape tools
        ttk.Label(toolbar, text="Tools").grid(row=2, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="pen")
        ttk.Radiobutton(toolbar, text="Pen", variable=self.mode_var, value="pen", command=self._set_mode).grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(toolbar, text="Line", variable=self.mode_var, value="line", command=self._set_mode).grid(row=4, column=0, sticky="w")
        ttk.Radiobutton(toolbar, text="Rectangle", variable=self.mode_var, value="rectangle", command=self._set_mode).grid(row=5, column=0, sticky="w")
        ttk.Radiobutton(toolbar, text="Circle", variable=self.mode_var, value="circle", command=self._set_mode).grid(row=6, column=0, sticky="w")

        ttk.Label(toolbar, text="Brush size").grid(row=7, column=0, sticky="w")
        self.size_scale = ttk.Scale(
            toolbar, from_=1, to=30, value=self.brush_size, orient=tk.HORIZONTAL, command=self._on_size_change
        )
        self.size_scale.grid(row=8, column=0, sticky="ew", pady=(0, 6))

        undo_btn = ttk.Button(toolbar, text="Undo (Ctrl+Z)", command=self.undo)
        undo_btn.grid(row=9, column=0, sticky="ew", pady=(6, 0))

        redo_btn = ttk.Button(toolbar, text="Redo (Ctrl+Y)", command=self.redo)
        redo_btn.grid(row=10, column=0, sticky="ew", pady=(6, 0))

        clear_btn = ttk.Button(toolbar, text="Clear", command=self.clear_canvas)
        clear_btn.grid(row=11, column=0, sticky="ew", pady=(12, 0))

        save_btn = ttk.Button(toolbar, text="Save PNG (Ctrl+S)", command=self.save_png)
        save_btn.grid(row=12, column=0, sticky="ew", pady=(6, 0))

        analyze_btn = ttk.Button(toolbar, text="Analyze (AI)", command=self.analyze_drawing)
        analyze_btn.grid(row=13, column=0, sticky="ew", pady=(12, 0))

        ttk.Label(toolbar, text="Tips: Hold left mouse to draw").grid(row=14, column=0, sticky="w", pady=(12, 0))

        # Canvas
        self.canvas = tk.Canvas(self, bg=self.background_color, highlightthickness=0)
        self.canvas.grid(row=0, column=1, sticky="nsew")

        # Mouse bindings
        self.canvas.bind("<ButtonPress-1>", self._start_draw)
        self.canvas.bind("<B1-Motion>", self._draw_motion)
        self.canvas.bind("<ButtonRelease-1>", self._end_draw)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-Z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.bind("<Control-Y>", lambda e: self.redo())
        self.bind("<Control-s>", lambda e: self.save_png())
        self.bind("<Control-S>", lambda e: self.save_png())
        self.bind("e", lambda e: self._toggle_eraser_shortcut())

    def _on_size_change(self, value: str) -> None:
        try:
            self.brush_size = int(float(value))
        except ValueError:
            pass

    def choose_color(self) -> None:
        color_tuple = colorchooser.askcolor(color=self.current_color, title="Choose draw color")
        if color_tuple and color_tuple[1]:
            self.current_color = color_tuple[1]
            if self.is_eraser:
                # Turn off eraser if a new color is picked
                self.is_eraser = False
                self.eraser_var.set(False)

    def toggle_eraser(self) -> None:
        self.is_eraser = bool(self.eraser_var.get())

    def _toggle_eraser_shortcut(self) -> None:
        self.is_eraser = not self.is_eraser
        self.eraser_var.set(self.is_eraser)

    def _set_mode(self) -> None:
        self.draw_mode = self.mode_var.get()

    # --- Drawing logic ---
    def _start_draw(self, event: tk.Event) -> None:
        self._current_stroke_has_items = False
        self.current_stroke_tag = f"stroke_{self.stroke_index}"
        self.stroke_index += 1
        self._last_x, self._last_y = event.x, event.y
        
        if self.draw_mode == "pen":
            color = self.background_color if self.is_eraser else self.current_color
            self.canvas.create_line(
                event.x, event.y, event.x + 1, event.y + 1,
                fill=color, width=self.brush_size, capstyle=tk.ROUND,
                smooth=True, tags=(self.current_stroke_tag,)
            )
            self._current_stroke_has_items = True

    def _draw_motion(self, event: tk.Event) -> None:
        if self._last_x is None or self._last_y is None:
            return

        if self.draw_mode == "pen":
            color = self.background_color if self.is_eraser else self.current_color
            self.canvas.create_line(
                self._last_x, self._last_y, event.x, event.y,
                fill=color, width=self.brush_size, capstyle=tk.ROUND,
                smooth=True, tags=(self.current_stroke_tag,)
            )
            self._last_x, self._last_y = event.x, event.y
        else:
            # Shape preview
            if self._preview_item:
                self.canvas.delete(self._preview_item)
            color = self.background_color if self.is_eraser else self.current_color
            if self.draw_mode == "line":
                self._preview_item = self.canvas.create_line(
                    self._last_x, self._last_y, event.x, event.y,
                    fill=color, width=self.brush_size
                )
            elif self.draw_mode == "rectangle":
                self._preview_item = self.canvas.create_rectangle(
                    self._last_x, self._last_y, event.x, event.y,
                    outline=color, width=self.brush_size
                )
            elif self.draw_mode == "circle":
                self._preview_item = self.canvas.create_oval(
                    self._last_x, self._last_y, event.x, event.y,
                    outline=color, width=self.brush_size
                )

    def _end_draw(self, event: tk.Event) -> None:
        if self.draw_mode != "pen" and self._last_x is not None and self._last_y is not None:
            if self._preview_item:
                self.canvas.delete(self._preview_item)
                self._preview_item = None
            
            color = self.background_color if self.is_eraser else self.current_color
            if self.draw_mode == "line":
                self.canvas.create_line(
                    self._last_x, self._last_y, event.x, event.y,
                    fill=color, width=self.brush_size, tags=(self.current_stroke_tag,)
                )
            elif self.draw_mode == "rectangle":
                self.canvas.create_rectangle(
                    self._last_x, self._last_y, event.x, event.y,
                    outline=color, width=self.brush_size, tags=(self.current_stroke_tag,)
                )
            elif self.draw_mode == "circle":
                self.canvas.create_oval(
                    self._last_x, self._last_y, event.x, event.y,
                    outline=color, width=self.brush_size, tags=(self.current_stroke_tag,)
                )
            self._current_stroke_has_items = True
        
        if self._current_stroke_has_items and self.current_stroke_tag:
            self.undo_stack.append(self.current_stroke_tag)
            self.redo_stack.clear()
        self._current_stroke_has_items = False
        self.current_stroke_tag = None
        self._last_x, self._last_y = None, None

    # --- Editing actions ---
    def undo(self) -> None:
        if not self.undo_stack:
            return
        stroke_tag = self.undo_stack.pop()
        self.canvas.itemconfigure(stroke_tag, state='hidden')
        self.redo_stack.append(stroke_tag)

    def redo(self) -> None:
        if not self.redo_stack:
            return
        stroke_tag = self.redo_stack.pop()
        self.canvas.itemconfigure(stroke_tag, state='normal')
        self.undo_stack.append(stroke_tag)

    def clear_canvas(self) -> None:
        self.canvas.delete("all")
        self.undo_stack.clear()
        self.redo_stack.clear()

    def save_png(self) -> None:
        # Ask for path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Save Whiteboard as PNG",
        )
        if not file_path:
            return

        # Ensure window is updated so geometry is correct
        self.update_idletasks()

        # Compute screen bbox of the canvas and screenshot it
        x = self.canvas.winfo_rootx()
        y = self.canvas.winfo_rooty()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        bbox = (x, y, x + w, y + h)
        try:
            img = ImageGrab.grab(bbox=bbox)
            img.save(file_path, "PNG")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save failed", f"Could not save image.\n{exc}")

    def _capture_canvas_image(self) -> 'ImageGrab.Image':  # type: ignore[name-defined]
        self.update_idletasks()
        x = self.canvas.winfo_rootx()
        y = self.canvas.winfo_rooty()
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        bbox = (x, y, x + w, y + h)
        return ImageGrab.grab(bbox=bbox)
    
    def analyze_drawing(self) -> None:
        """Captures the canvas and analyzes it with a configured AI service."""
        try:
            img = self._capture_canvas_image()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Capture failed", f"Could not capture canvas.\n{exc}")
            return
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key and _GEMINI_AVAILABLE:
            self._run_analysis_in_thread(self._analyze_with_gemini, img)
            return
        
        hf_token = os.environ.get("HF_API_TOKEN")
        if hf_token:
            self._run_analysis_in_thread(self._analyze_with_hf, img)
            return
        
        messagebox.showinfo(
            "AI not configured",
            "Set GEMINI_API_KEY (Google Gemini) or HF_API_TOKEN (Hugging Face) and install dependencies to enable AI analysis.",
        )

    def _run_analysis_in_thread(self, analysis_func, image) -> None:
        """Runs the provided analysis function in a background thread to avoid UI blocking."""
        self.config(cursor="watch")
        self.update_idletasks()

        def task_wrapper():
            try:
                message = analysis_func(image)
                self.after(0, lambda: messagebox.showinfo("AI Analysis", message))
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda: messagebox.showerror("AI Error", str(e)))
            finally:
                self.after(0, lambda: self.config(cursor=""))

        threading.Thread(target=task_wrapper, daemon=True).start()

    def _analyze_with_gemini(self, img: 'ImageGrab.Image') -> str:
        """Analyzes the image with Google Gemini and returns a message string."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        with io.BytesIO() as buf:
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

        genai.configure(api_key=gemini_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)
        prompt = (
            "You are a drawing judge. Look at the sketch and provide: "
            "1) a short label for what it depicts, 2) a confidence 0-100, "
            "3) a one-sentence critique or suggestion. Respond in JSON with keys: "
            "label, confidence, critique."
        )
        image_part = {"mime_type": "image/png", "data": image_bytes}
        resp = model.generate_content([prompt, image_part])
        content = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if getattr(resp, "candidates", None) else "")


        result = None
        if content:
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", content)
                if match:
                    try:
                        result = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        result = None
        if isinstance(result, dict):
            label = result.get("label", "Unknown")
            conf = result.get("confidence", "?")
            critique = result.get("critique", "")
            return f"Label: {label}\nConfidence: {conf}\n\n{critique}"
        else:
            return content or "No response"

    def _analyze_with_hf(self, img: 'ImageGrab.Image') -> str:
        """Analyzes the image with Hugging Face and returns a message string."""
        hf_token = os.environ.get("HF_API_TOKEN")
        if not hf_token:
            return "HF_API_TOKEN not configured"
        
        with io.BytesIO() as buf:
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

        model = os.environ.get("HF_MODEL", "google/vit-base-patch16-224")
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {hf_token}"}
        resp = requests.post(url, headers=headers, data=image_bytes, timeout=60)
        
        if resp.status_code == 503:
            return "Model is loading on Hugging Face. Please try again in a few seconds."
        
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list) and data:
            top = max(data, key=lambda x: x.get("score", 0))
            label = top.get("label", "Unknown")
            conf = round(float(top.get("score", 0)) * 100, 1)
            return f"Label: {label}\nConfidence: {conf}"
        else:
            return str(data)


def main() -> None:
    app = WhiteboardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
