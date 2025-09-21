## Python Whiteboard

A simple whiteboard app using Tkinter.

### Features
- Freehand drawing with smooth rounded strokes
- Color picker and brush size control
- Eraser (paints with background color)
- Undo/Redo
- Save canvas to PNG
- Optional: AI analysis of your drawing (label, confidence, critique)

### Requirements
- Python 3.10+
- Pillow

### Setup
```bash
python -m venv .venv
.venv\\Scripts\\python -m pip install -U pip
.venv\\Scripts\\pip install -r requirements.txt
```

### One-click run (Windows)
- Double-click `run.ps1` or run:
```powershell
./run.ps1
```
- To force a clean reinstall:
```powershell
./run.ps1 -Reinstall
```

### Run
```bash
.venv\\Scripts\\python whiteboard.py
```

### Notes
- Saving uses a screen capture of the canvas area; ensure the window is visible and not covered.

### Optional: Enable AI analysis (Hugging Face)
- Install dependency (already included):
```bash
.venv\\Scripts\\pip install requests
```
- Set your token and (optionally) a model:
```powershell
$env:HF_API_TOKEN = "hf_..."
# Optional, default: google/vit-base-patch16-224 (image classifier)
$env:HF_MODEL = "google/vit-base-patch16-224"
```
- Click "Analyze (AI)". If the model is cold-starting, try again after a short delay.

### Optional: Enable AI analysis (Google Gemini)
- Install dependency (already included):
```bash
.venv\\Scripts\\pip install google-generativeai
```
- Set your API key and (optionally) a model:
```powershell
$env:GEMINI_API_KEY = "AIza..."  # do not commit keys to code
# Optional model (default: gemini-1.5-flash). Examples: gemini-1.5-flash, gemini-1.5-pro
$env:GEMINI_MODEL = "gemini-1.5-flash"
```
- Click "Analyze (AI)".

### Environment variables via .env
- Copy `.env.example` to `.env` and set your keys. The app automatically loads `.env`.

### Build a standalone EXE (Windows)
- Run:
```powershell
./build_exe.ps1
```
- Output will be in `dist/Whiteboard.exe`.

