"""
Audio/Video to Text Transcriber v2.3
Requires: pip install openai-whisper deep-translator
Also requires ffmpeg on your system PATH.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import multiprocessing
import os
import sys
import subprocess
import tempfile

# ── Dependency check ──────────────────────────────────────────────────────────
MISSING = []
try:
    import whisper
except ImportError:
    MISSING.append("openai-whisper")
try:
    from deep_translator import GoogleTranslator
except ImportError:
    MISSING.append("deep-translator")
try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    MISSING.append("Pillow")

if MISSING:
    print(f"Missing packages: {', '.join(MISSING)}")
    print(f"Install with:  pip install {' '.join(MISSING)}")
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
SUPPORTED_EXTS = (
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv",
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac",
)
MODELS = ["tiny", "base", "small", "medium", "large"]
TRANSCRIBE_LANGUAGES = [
    "Auto Detect", "English", "Hindi", "Spanish", "French",
    "German", "Chinese", "Japanese", "Korean", "Arabic",
    "Portuguese", "Russian", "Italian",
]
LANG_CODES = {
    "Auto Detect": None, "English": "en", "Hindi": "hi",
    "Spanish": "es", "French": "fr", "German": "de",
    "Chinese": "zh", "Japanese": "ja", "Korean": "ko",
    "Arabic": "ar", "Portuguese": "pt", "Russian": "ru",
    "Italian": "it",
}

# Translation targets — code : display name
TRANSLATE_OPTIONS = {
    "en":       "English",
    "hi":       "Hindi",
    "es":       "Spanish",
    "fr":       "French",
    "de":       "German",
    "zh-CN":    "Chinese (Simplified)",
    "ja":       "Japanese",
    "ko":       "Korean",
    "ar":       "Arabic",
    "pt":       "Portuguese",
    "ru":       "Russian",
    "it":       "Italian",
    "ta":       "Tamil",
    "te":       "Telugu",
    "mr":       "Marathi",
    "bn":       "Bengali",
    "ur":       "Urdu",
}

# ── Palette ───────────────────────────────────────────────────────────────────
BG          = "#1a1a1a"
PANEL_BG    = "#252525"
PANEL_HDR   = "#1e1e1e"
BORDER      = "#3a3a3a"
BORDER_DARK = "#111111"
ACCENT      = "#e8761a"
ACCENT_DIM  = "#c4611a"
TEXT        = "#d0d0d0"
TEXT_DIM    = "#787878"
TEXT_HDR    = "#a0a0a0"
INPUT_BG    = "#1e1e1e"
BTN_GREY    = "#363636"
BTN_HOVER   = "#424242"
SUCCESS     = "#4aaf5a"
DANGER      = "#c44040"


# ── Worker: Whisper ───────────────────────────────────────────────────────────
def _whisper_worker(audio_path, model_name, language, result_queue):
    try:
        import whisper as _w
        model = _w.load_model(model_name)
        kwargs = {}
        if language:
            kwargs["language"] = language
        result = model.transcribe(audio_path, **kwargs)
        result_queue.put(("ok", result["text"].strip()))
    except Exception as e:
        result_queue.put(("err", str(e)))


# ── Panel helper ──────────────────────────────────────────────────────────────
def make_panel(parent, title, **pack_kw):
    outer = tk.Frame(parent, bg=BORDER_DARK)
    outer.pack(**pack_kw)
    inner = tk.Frame(outer, bg=PANEL_BG)
    inner.pack(fill="both", expand=True, padx=1, pady=(0, 1))
    hdr = tk.Frame(inner, bg=PANEL_HDR, height=40)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text=title.upper(), font=("Courier", 11, "bold"),
             fg=TEXT_HDR, bg=PANEL_HDR, anchor="w", padx=16).pack(fill="y", side="left")
    body = tk.Frame(inner, bg=PANEL_BG)
    body.pack(fill="both", expand=True)
    return body


# ── Main App ──────────────────────────────────────────────────────────────────
class TranscriberApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Transcriber")
        self.geometry("1600x980")
        self.minsize(1100, 780)
        self.configure(bg=BG)

        self._transcription      = ""
        self._tmp_audio          = None
        self._worker_proc        = None
        self._ffmpeg_proc        = None
        self._stop_requested     = False
        self._transcript_editing = False
        self._translation_editing = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_topbar()
        self._build_media_panel()
        self._build_settings_panel()
        self._build_transport()
        self._build_output_row()

    def _build_topbar(self):
        bar = tk.Frame(self, bg="#111111", height=60)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="◆", font=("Courier", 20),
                 fg=ACCENT, bg="#111111").pack(side="left", padx=(14, 6), pady=10)
        tk.Label(bar, text="TRANSCRIBER", font=("Courier", 16, "bold"),
                 fg=TEXT, bg="#111111").pack(side="left")


    def _build_media_panel(self):
        body = make_panel(self, "Source Media",
                          fill="x", padx=18, pady=(14, 0))

        # Outer row: thumbnail (left) + right side (path field + details + import)
        outer = tk.Frame(body, bg=PANEL_BG)
        outer.pack(fill="x", padx=18, pady=14)

        # ── Thumbnail box ─────────────────────────────────────────────────────
        THUMB_W, THUMB_H = 220, 124
        thumb_frame = tk.Frame(outer, bg=BORDER_DARK, width=THUMB_W, height=THUMB_H)
        thumb_frame.pack(side="left", padx=(0, 18))
        thumb_frame.pack_propagate(False)
        self._thumb_lbl = tk.Label(thumb_frame, bg="#111111",
                                   text="NO\nMEDIA", font=("Courier", 12),
                                   fg=TEXT_DIM, justify="center")
        self._thumb_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self._thumb_image = None   # keep reference alive

        # ── Right side ────────────────────────────────────────────────────────
        right = tk.Frame(outer, bg=PANEL_BG)
        right.pack(side="left", fill="x", expand=True)

        # Path field + Import button
        path_row = tk.Frame(right, bg=PANEL_BG)
        path_row.pack(fill="x")

        field_outer = tk.Frame(path_row, bg=BORDER_DARK)
        field_outer.pack(side="left", fill="x", expand=True, ipady=1, ipadx=1)
        field_inner = tk.Frame(field_outer, bg=INPUT_BG)
        field_inner.pack(fill="both", padx=1, pady=1)
        self._file_var = tk.StringVar(value="No media selected")
        tk.Label(field_inner, textvariable=self._file_var,
                 font=("Courier", 13), fg=TEXT_DIM, bg=INPUT_BG,
                 anchor="w", padx=14, pady=10, wraplength=1100).pack(fill="x")

        self._browse_btn = self._mkbtn(path_row, "  IMPORT  ", self._browse, primary=True)
        self._browse_btn.pack(side="right", padx=(14, 0))

        # File name + size row (below path field)
        info_row = tk.Frame(right, bg=PANEL_BG)
        info_row.pack(fill="x", pady=(10, 0))

        self._file_name_var = tk.StringVar(value="")
        self._file_size_var = tk.StringVar(value="")

        tk.Label(info_row, textvariable=self._file_name_var,
                 font=("Courier", 12, "bold"), fg=TEXT, bg=PANEL_BG).pack(side="left")
        tk.Label(info_row, textvariable=self._file_size_var,
                 font=("Courier", 12), fg=TEXT_DIM, bg=PANEL_BG).pack(side="left", padx=(20, 0))

    def _build_settings_panel(self):
        body = make_panel(self, "Transcription Settings",
                          fill="x", padx=18, pady=(10, 0))

        # Row 1 — model + language + time estimate
        row = tk.Frame(body, bg=PANEL_BG)
        row.pack(fill="x", padx=18, pady=14)

        self._lbl(row, "MODEL").pack(side="left")
        self._model_var = tk.StringVar(value="base")
        self._combo(row, self._model_var, MODELS).pack(side="left", padx=(4, 10))

        self._model_var.trace_add("write", self._on_model_change)
        self._time_est_var = tk.StringVar(value="")
        tk.Label(row, textvariable=self._time_est_var,
                 font=("Courier", 11), fg=ACCENT, bg=PANEL_BG).pack(side="left", padx=(0, 24))

        self._lbl(row, "LANGUAGE").pack(side="left")
        self._lang_var = tk.StringVar(value="Auto Detect")
        self._combo(row, self._lang_var, TRANSCRIBE_LANGUAGES,
                    width=14).pack(side="left", padx=(4, 22))

        tk.Label(row, text="tiny=fast  ·  base=balanced  ·  medium/large=accurate",
                 font=("Courier", 11), fg=TEXT_DIM, bg=PANEL_BG).pack(side="left")

    def _build_transport(self):
        bar = tk.Frame(self, bg="#111111", height=72)
        bar.pack(fill="x", pady=(10, 0))
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_var,
                 font=("Courier", 12), fg=TEXT_DIM,
                 bg="#111111").place(x=24, rely=0.5, anchor="w")

        centre = tk.Frame(bar, bg="#111111")
        centre.place(relx=0.5, rely=0.5, anchor="center")

        self._run_btn = self._mkbtn(centre, "  ▶   TRANSCRIBE  ",
                                    self._start_transcription, primary=True,
                                    font=("Courier", 14, "bold"))
        self._run_btn.pack(side="left", padx=12)

        self._stop_btn = self._mkbtn(centre, "  ■   STOP  ",
                                     self._stop_transcription, primary=False,
                                     font=("Courier", 14, "bold"))
        self._stop_btn.pack(side="left", padx=12)
        self._stop_btn.config(state="disabled")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("R.Horizontal.TProgressbar",
                        troughcolor="#2a2a2a", background=ACCENT,
                        bordercolor="#111111", lightcolor=ACCENT, darkcolor=ACCENT)
        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=280,
                                         style="R.Horizontal.TProgressbar")
        self._progress.place(relx=1.0, x=-24, rely=0.5, anchor="e")

    def _build_output_row(self):
        """Side-by-side: Transcript (left) + Translation (right)."""
        row = tk.Frame(self, bg=BG)
        row.pack(fill="both", expand=True, padx=18, pady=(10, 16))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        row.rowconfigure(0, weight=1)

        # ── LEFT: Transcript ──────────────────────────────────────────────────
        left_outer = tk.Frame(row, bg=BORDER_DARK)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_inner = tk.Frame(left_outer, bg=PANEL_BG)
        left_inner.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        # panel header
        l_hdr = tk.Frame(left_inner, bg=PANEL_HDR, height=40)
        l_hdr.pack(fill="x")
        l_hdr.pack_propagate(False)
        tk.Label(l_hdr, text="TRANSCRIPT OUTPUT", font=("Courier", 11, "bold"),
                 fg=TEXT_HDR, bg=PANEL_HDR, anchor="w", padx=16).pack(side="left", fill="y")

        # toolbar
        l_tb = tk.Frame(left_inner, bg=PANEL_HDR, height=44)
        l_tb.pack(fill="x")
        l_tb.pack_propagate(False)
        self._copy_btn = self._mksmallbtn(l_tb, "COPY ALL", self._copy)
        self._copy_btn.pack(side="left", padx=(14, 6), pady=8)
        self._clear_btn = self._mksmallbtn(l_tb, "CLEAR", self._clear, danger=True)
        self._clear_btn.pack(side="left", pady=8)
        self._edit_transcript_btn = self._mksmallbtn(l_tb, "✎  EDIT", self._toggle_transcript_edit)
        self._edit_transcript_btn.pack(side="left", padx=(6, 0), pady=8)
        self._char_var = tk.StringVar(value="")
        tk.Label(l_tb, textvariable=self._char_var,
                 font=("Courier", 11), fg=TEXT_DIM, bg=PANEL_HDR).pack(side="right", padx=14)

        # text area — locked by default
        l_txt_wrap = tk.Frame(left_inner, bg=INPUT_BG)
        l_txt_wrap.pack(fill="both", expand=True, padx=1, pady=1)
        self._text = tk.Text(
            l_txt_wrap, font=("Courier", 14), fg=TEXT, bg=INPUT_BG,
            insertbackground=ACCENT, relief="flat", wrap="word",
            padx=20, pady=16, selectbackground=ACCENT,
            selectforeground="#fff", bd=0, state="disabled",
        )
        self._text.pack(fill="both", expand=True, side="left")
        l_sb = ttk.Scrollbar(l_txt_wrap, command=self._text.yview)
        l_sb.pack(side="right", fill="y")
        self._text.config(yscrollcommand=l_sb.set)

        # ── RIGHT: Translation ────────────────────────────────────────────────
        right_outer = tk.Frame(row, bg=BORDER_DARK)
        right_outer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_inner = tk.Frame(right_outer, bg=PANEL_BG)
        right_inner.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        # panel header
        r_hdr = tk.Frame(right_inner, bg=PANEL_HDR, height=40)
        r_hdr.pack(fill="x")
        r_hdr.pack_propagate(False)
        tk.Label(r_hdr, text="TRANSLATION", font=("Courier", 11, "bold"),
                 fg=TEXT_HDR, bg=PANEL_HDR, anchor="w", padx=16).pack(side="left", fill="y")

        # toolbar with language selector + translate button
        r_tb = tk.Frame(right_inner, bg=PANEL_HDR, height=44)
        r_tb.pack(fill="x")
        r_tb.pack_propagate(False)

        self._lbl(r_tb, "TO").pack(side="left", padx=(14, 6), pady=8)

        lang_names = list(TRANSLATE_OPTIONS.values())
        self._translate_lang_var = tk.StringVar(value="English")
        self._combo(r_tb, self._translate_lang_var, lang_names,
                    width=18).pack(side="left", pady=4)

        self._translate_btn = self._mksmallbtn(r_tb, "TRANSLATE", self._start_translation)
        self._translate_btn.pack(side="left", padx=(12, 6), pady=8)

        self._copy_trans_btn = self._mksmallbtn(r_tb, "COPY", self._copy_translation)
        self._copy_trans_btn.pack(side="left", pady=8)

        self._edit_translation_btn = self._mksmallbtn(r_tb, "✎  EDIT", self._toggle_translation_edit)
        self._edit_translation_btn.pack(side="left", padx=(6, 0), pady=8)

        self._trans_status_var = tk.StringVar(value="")
        tk.Label(r_tb, textvariable=self._trans_status_var,
                 font=("Courier", 11), fg=TEXT_DIM,
                 bg=PANEL_HDR).pack(side="right", padx=14)

        # text area — locked by default
        r_txt_wrap = tk.Frame(right_inner, bg=INPUT_BG)
        r_txt_wrap.pack(fill="both", expand=True, padx=1, pady=1)
        self._trans_text = tk.Text(
            r_txt_wrap, font=("Courier", 14), fg=TEXT, bg=INPUT_BG,
            insertbackground=ACCENT, relief="flat", wrap="word",
            padx=20, pady=16, selectbackground=ACCENT,
            selectforeground="#fff", bd=0, state="disabled",
        )
        self._trans_text.pack(fill="both", expand=True, side="left")
        r_sb = ttk.Scrollbar(r_txt_wrap, command=self._trans_text.yview)
        r_sb.pack(side="right", fill="y")
        self._trans_text.config(yscrollcommand=r_sb.set)

    # ── Widget factories ──────────────────────────────────────────────────────
    def _mkbtn(self, parent, text, cmd, primary=False,
               font=("Courier", 13, "bold")):
        bg = ACCENT if primary else BTN_GREY
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg="#fff",
                         activebackground=ACCENT_DIM if primary else BTN_HOVER,
                         activeforeground="#fff", relief="flat", cursor="hand2",
                         font=font, bd=0, pady=12, padx=8)

    def _mksmallbtn(self, parent, text, cmd, danger=False):
        bg = "#3a1a1a" if danger else BTN_GREY
        fg = "#cc5555" if danger else TEXT
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg,
                         activebackground="#501a1a" if danger else BTN_HOVER,
                         activeforeground=fg, relief="flat", cursor="hand2",
                         font=("Courier", 11, "bold"), bd=0, padx=14, pady=6)

    def _lbl(self, parent, text):
        return tk.Label(parent, text=text, font=("Courier", 11, "bold"),
                        fg=TEXT_DIM, bg=PANEL_HDR if parent.cget("bg") == PANEL_HDR else PANEL_BG)

    def _combo(self, parent, var, values, width=10):
        style = ttk.Style()
        style.configure("R.TCombobox",
                        fieldbackground=INPUT_BG, background=BTN_GREY,
                        foreground=TEXT, selectbackground=INPUT_BG,
                        selectforeground=TEXT,
                        arrowcolor=TEXT_DIM, bordercolor=BORDER_DARK)
        style.map("R.TCombobox",
                  fieldbackground=[("readonly", INPUT_BG)],
                  foreground=[("readonly", TEXT)],
                  selectbackground=[("readonly", INPUT_BG)],
                  selectforeground=[("readonly", TEXT)])
        cb = ttk.Combobox(parent, textvariable=var, values=values,
                          state="readonly", width=width,
                          font=("Courier", 12), style="R.TCombobox")
        cb.bind("<<ComboboxSelected>>", lambda e: e.widget.selection_clear())
        return cb

    # ── State helpers ─────────────────────────────────────────────────────────
    def _set_busy(self, busy):
        if busy:
            self._run_btn.config(state="disabled", bg="#555555")
            self._browse_btn.config(state="disabled")
            self._stop_btn.config(state="normal", bg=DANGER)
            self._progress.start(10)
        else:
            self._run_btn.config(state="normal", bg=ACCENT)
            self._browse_btn.config(state="normal")
            self._stop_btn.config(state="disabled", bg=BTN_GREY)
            self._progress.stop()

    def _set_status(self, msg):
        self.after(0, lambda: self._status_var.set(msg))

    def _toggle_transcript_edit(self):
        self._transcript_editing = not self._transcript_editing
        if self._transcript_editing:
            self._text.config(state="normal", bg="#252020",
                              highlightthickness=1, highlightbackground=ACCENT)
            self._edit_transcript_btn.config(text="✔  LOCK", bg="#2a3a1a", fg="#7acc55")
        else:
            self._text.config(state="disabled", bg=INPUT_BG,
                              highlightthickness=0)
            self._edit_transcript_btn.config(text="✎  EDIT", bg=BTN_GREY, fg=TEXT)

    def _toggle_translation_edit(self):
        self._translation_editing = not self._translation_editing
        if self._translation_editing:
            self._trans_text.config(state="normal", bg="#252020",
                                    highlightthickness=1, highlightbackground=ACCENT)
            self._edit_translation_btn.config(text="✔  LOCK", bg="#2a3a1a", fg="#7acc55")
        else:
            self._trans_text.config(state="disabled", bg=INPUT_BG,
                                    highlightthickness=0)
            self._edit_translation_btn.config(text="✎  EDIT", bg=BTN_GREY, fg=TEXT)

    # ── Transcription ─────────────────────────────────────────────────────────
    # ── File duration (set after browsing) ───────────────────────────────────
    _file_duration_sec: float = 0.0

    # CPU speed ratios: how many seconds of audio per second of processing
    _MODEL_SPEED = {
        "tiny":   15.0,
        "base":    7.0,
        "small":   3.0,
        "medium":  1.2,
        "large":   0.6,
    }

    def _get_duration(self, path: str) -> float:
        """Return file duration in seconds using ffprobe, or 0 on failure."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=10,
            )
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _fmt_size(self, nbytes: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}"
            nbytes /= 1024
        return f"{nbytes:.1f} GB"

    def _fmt_time(self, seconds: float) -> str:
        if seconds <= 0:
            return ""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        if mins == 0:
            return f"~{secs}s"
        return f"~{mins}m {secs}s" if secs else f"~{mins}m"

    def _on_model_change(self, *_):
        self._update_time_estimate()

    def _update_time_estimate(self):
        dur = self._file_duration_sec
        model = self._model_var.get()
        if dur <= 0 or model not in self._MODEL_SPEED:
            self._time_est_var.set("")
            return
        est = dur / self._MODEL_SPEED[model]
        self._time_est_var.set(f"est. {self._fmt_time(est)} on CPU")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Import Media",
            filetypes=[("Audio/Video", " ".join(f"*{e}" for e in SUPPORTED_EXTS)),
                       ("All files", "*.*")],
        )
        if not path:
            return

        self._file_var.set(path)

        # File name
        name = os.path.basename(path)
        self._file_name_var.set(name)

        # File size
        try:
            size = os.path.getsize(path)
            self._file_size_var.set(self._fmt_size(size))
        except Exception:
            self._file_size_var.set("")

        # Reset thumbnail placeholder
        self._thumb_lbl.config(image="", text="⏳", font=("Courier", 22), fg=TEXT_DIM)
        self._thumb_image = None

        # Duration + thumbnail in background
        self._file_duration_sec = 0.0
        self._time_est_var.set("calculating…")
        threading.Thread(target=self._load_file_meta, args=(path,), daemon=True).start()

        self._status_var.set("Media loaded — ready to transcribe")

    def _load_file_meta(self, path):
        """Background thread: get duration + extract thumbnail."""
        dur = self._get_duration(path)
        self._file_duration_sec = dur
        self.after(0, self._update_time_estimate)

        # Extract thumbnail
        ext = os.path.splitext(path)[1].lower()
        video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"}

        if ext in video_exts:
            thumb = self._extract_video_thumb(path)
        else:
            thumb = self._make_audio_thumb()

        if thumb:
            self.after(0, self._set_thumbnail, thumb)
        else:
            self.after(0, lambda: self._thumb_lbl.config(image="", text="?", fg=TEXT_DIM))

    def _extract_video_thumb(self, path):
        """Extract a frame from the video at 10% duration using ffmpeg."""
        try:
            dur = self._file_duration_sec
            seek = max(1.0, dur * 0.1) if dur > 0 else 1.0
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            tmp.close()
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(seek), "-i", path,
                 "-vframes", "1", "-vf", "scale=220:124:force_original_aspect_ratio=decrease,"
                 "pad=220:124:(ow-iw)/2:(oh-ih)/2:black",
                 tmp.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
            )
            img = Image.open(tmp.name).resize((220, 124), Image.LANCZOS)
            os.unlink(tmp.name)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _make_audio_thumb(self):
        """Create a simple audio waveform placeholder image."""
        try:
            img = Image.new("RGB", (220, 124), "#1a1a1a")
            draw = ImageDraw.Draw(img)
            import random, math
            random.seed(42)
            cx, cy = 110, 62
            for i in range(50):
                x = int(6 + i * 4)
                h = int(14 + random.random() * 42 * abs(math.sin(i * 0.6)))
                draw.rectangle([x, cy - h, x + 2, cy + h], fill="#e8761a")
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _set_thumbnail(self, photo):
        self._thumb_image = photo   # prevent GC
        self._thumb_lbl.config(image=photo, text="")

    def _load_duration(self, path):
        dur = self._get_duration(path)
        self._file_duration_sec = dur
        self.after(0, self._update_time_estimate)

    def _start_transcription(self):
        path = self._file_var.get()
        if path == "No media selected" or not os.path.exists(path):
            messagebox.showerror("No Media", "Please import a media file first.")
            return
        if os.path.splitext(path)[1].lower() not in SUPPORTED_EXTS:
            messagebox.showerror("Unsupported", "File type not supported.")
            return
        self._stop_requested = False
        self._set_busy(True)
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        if not self._transcript_editing:
            self._text.config(state="disabled")
        self._trans_text.config(state="normal")
        self._trans_text.delete("1.0", "end")
        if not self._translation_editing:
            self._trans_text.config(state="disabled")
        self._char_var.set("")
        self._trans_status_var.set("")
        self._set_status("Initialising…")
        threading.Thread(target=self._transcribe_thread, args=(path,), daemon=True).start()

    def _stop_transcription(self):
        self._stop_requested = True
        if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
            self._ffmpeg_proc.terminate()
            self._ffmpeg_proc = None
        if self._worker_proc and self._worker_proc.is_alive():
            self._worker_proc.terminate()
            self._worker_proc.join(timeout=3)
            self._worker_proc = None
        self._cleanup_tmp()
        self._set_busy(False)
        self._status_var.set("Stopped")

    def _transcribe_thread(self, path):
        try:
            model_name = self._model_var.get()
            language   = LANG_CODES.get(self._lang_var.get())

            audio_path = path
            if os.path.splitext(path)[1].lower() in {".mp4",".mkv",".mov",".avi",".webm",".flv"}:
                self._set_status("Extracting audio…")
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.close()
                audio_path = tmp.name
                self._tmp_audio = audio_path
                self._ffmpeg_proc = subprocess.Popen(
                    ["ffmpeg", "-y", "-i", path, "-vn",
                     "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._ffmpeg_proc.wait()
                if self._stop_requested: return
                if self._ffmpeg_proc.returncode != 0:
                    raise RuntimeError("ffmpeg failed to extract audio.")
                self._ffmpeg_proc = None

            if self._stop_requested: return

            self._set_status(f"Transcribing · {model_name} · {self._lang_var.get()}…")
            result_queue = multiprocessing.Queue()
            self._worker_proc = multiprocessing.Process(
                target=_whisper_worker,
                args=(audio_path, model_name, language, result_queue),
                daemon=True,
            )
            self._worker_proc.start()
            self._worker_proc.join()

            if self._stop_requested: return

            if not result_queue.empty():
                status, payload = result_queue.get_nowait()
                self._cleanup_tmp()
                self.after(0, self._show_result if status == "ok" else self._show_error, payload)
            else:
                self._cleanup_tmp()
                self.after(0, self._show_error, "Transcription produced no output.")

        except FileNotFoundError:
            self._cleanup_tmp()
            self.after(0, self._show_error,
                       "ffmpeg not found.\n\nInstall from https://ffmpeg.org/download.html\n"
                       "and add it to your system PATH.")
        except Exception as e:
            self._cleanup_tmp()
            self.after(0, self._show_error, str(e))

    def _cleanup_tmp(self):
        if self._tmp_audio:
            try: os.unlink(self._tmp_audio)
            except Exception: pass
            self._tmp_audio = None

    def _show_result(self, text):
        self._transcription = text
        self._text.config(state="normal")
        self._text.insert("1.0", text)
        if not self._transcript_editing:
            self._text.config(state="disabled")
        self._char_var.set(f"{len(text):,} chars  ·  {len(text.split()):,} words")
        self._status_var.set("Transcription complete ✓")
        self._set_busy(False)

    def _show_error(self, msg):
        self._set_busy(False)
        self._status_var.set("Error")
        messagebox.showerror("Transcription Error", msg)

    # ── Translation ───────────────────────────────────────────────────────────
    def _start_translation(self):
        self._text.config(state="normal")
        source = self._text.get("1.0", "end-1c").strip()
        if not self._transcript_editing:
            self._text.config(state="disabled")
        if not source:
            messagebox.showinfo("Nothing to Translate", "Transcribe a file first.")
            return

        lang_name = self._translate_lang_var.get()
        self._trans_text.delete("1.0", "end")
        self._trans_status_var.set("Translating…")
        self._translate_btn.config(state="disabled", bg="#555555")

        threading.Thread(target=self._translate_thread,
                         args=(source, lang_name), daemon=True).start()

    def _translate_thread(self, text, lang_name):
        try:
            target_code = None
            for code, name in TRANSLATE_OPTIONS.items():
                if name == lang_name:
                    target_code = code
                    break

            result = GoogleTranslator(source="auto", target=target_code).translate(text)
            self.after(0, self._show_translation, result, lang_name)

        except Exception as e:
            self.after(0, self._translation_error, str(e))

    def _show_translation(self, text, lang_name):
        self._trans_text.config(state="normal")
        self._trans_text.insert("1.0", text)
        if not self._translation_editing:
            self._trans_text.config(state="disabled")
        self._trans_status_var.set(f"→ {lang_name} ✓")
        self._translate_btn.config(state="normal", bg=BTN_GREY)

    def _translation_error(self, msg):
        self._trans_status_var.set("Error")
        self._translate_btn.config(state="normal", bg=BTN_GREY)
        messagebox.showerror("Translation Error",
                             f"{msg}\n\nMake sure you have an internet connection.")

    # ── Copy / Clear ──────────────────────────────────────────────────────────
    def _copy(self):
        self._text.config(state="normal")
        text = self._text.get("1.0", "end-1c").strip()
        if not self._transcript_editing:
            self._text.config(state="disabled")
        if not text:
            messagebox.showinfo("Nothing to Copy", "Transcribe a file first.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        orig = self._copy_btn.cget("text")
        self._copy_btn.config(text="COPIED ✓", bg=SUCCESS, fg="#fff")
        self.after(1800, lambda: self._copy_btn.config(text=orig, bg=BTN_GREY, fg=TEXT))

    def _copy_translation(self):
        self._trans_text.config(state="normal")
        text = self._trans_text.get("1.0", "end-1c").strip()
        if not self._translation_editing:
            self._trans_text.config(state="disabled")
        if not text:
            messagebox.showinfo("Nothing to Copy", "Translate something first.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        orig = self._copy_trans_btn.cget("text")
        self._copy_trans_btn.config(text="COPIED ✓", bg=SUCCESS, fg="#fff")
        self.after(1800, lambda: self._copy_trans_btn.config(text=orig, bg=BTN_GREY, fg=TEXT))

    def _clear(self):
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        if not self._transcript_editing:
            self._text.config(state="disabled")
        self._trans_text.config(state="normal")
        self._trans_text.delete("1.0", "end")
        if not self._translation_editing:
            self._trans_text.config(state="disabled")
        self._transcription = ""
        self._char_var.set("")
        self._trans_status_var.set("")
        self._file_var.set("No media selected")
        self._file_name_var.set("")
        self._file_size_var.set("")
        self._time_est_var.set("")
        self._file_duration_sec = 0.0
        self._thumb_lbl.config(image="", text="NO\nMEDIA", font=("Courier", 12), fg=TEXT_DIM)
        self._thumb_image = None
        self._status_var.set("Ready")

    def _on_close(self):
        self._stop_transcription()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = TranscriberApp()
    app.mainloop()