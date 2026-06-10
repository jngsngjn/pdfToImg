import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from worker import ExtractionWorker


class PdfImageExtractorApp:
    def __init__(self) -> None:
        root_class = TkinterDnD.Tk if TkinterDnD else tk.Tk
        self.root = root_class()
        self.root.title("PDF Image Extractor")
        self.root.geometry("760x620")
        self.root.minsize(680, 520)

        self.pdf_paths: list[Path] = []
        self.output_dir: Path | None = None
        self.events: queue.Queue[dict] = queue.Queue()
        self.worker: ExtractionWorker | None = None

        self.remove_duplicates_var = tk.BooleanVar(value=True)
        self.output_dir_var = tk.StringVar(value="기본값: 각 PDF 폴더\\extracted_images")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="0%")

        self._build_ui()
        self._setup_drag_and_drop()
        self.root.after(100, self._poll_events)

    def run(self) -> None:
        self.root.mainloop()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)
        self.root.rowconfigure(7, weight=2)

        title = ttk.Label(self.root, text="PDF Image Extractor", font=("Segoe UI", 16, "bold"))
        title.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        button_frame = ttk.Frame(self.root)
        button_frame.grid(row=1, column=0, padx=16, pady=6, sticky="ew")
        button_frame.columnconfigure(4, weight=1)

        self.add_button = ttk.Button(button_frame, text="PDF 파일 추가", command=self._select_pdfs)
        self.add_button.grid(row=0, column=0, padx=(0, 8))

        self.clear_button = ttk.Button(button_frame, text="목록 비우기", command=self._clear_pdfs)
        self.clear_button.grid(row=0, column=1, padx=(0, 8))

        self.output_button = ttk.Button(button_frame, text="출력 폴더 선택", command=self._select_output_dir)
        self.output_button.grid(row=0, column=2, padx=(0, 8))

        self.start_button = ttk.Button(button_frame, text="추출 시작", command=self._start_extraction)
        self.start_button.grid(row=0, column=3, padx=(0, 8))

        output_label = ttk.Label(self.root, textvariable=self.output_dir_var)
        output_label.grid(row=2, column=0, padx=16, pady=(2, 8), sticky="ew")

        drop_frame = ttk.LabelFrame(self.root, text="PDF를 여기로 드래그 앤 드롭하세요")
        drop_frame.grid(row=3, column=0, padx=16, pady=6, sticky="nsew")
        drop_frame.rowconfigure(0, weight=1)
        drop_frame.columnconfigure(0, weight=1)

        self.pdf_listbox = tk.Listbox(drop_frame, height=9, selectmode=tk.EXTENDED)
        self.pdf_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(drop_frame, orient=tk.VERTICAL, command=self.pdf_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.pdf_listbox.configure(yscrollcommand=scrollbar.set)

        options_frame = ttk.Frame(self.root)
        options_frame.grid(row=4, column=0, padx=16, pady=6, sticky="ew")
        duplicate_check = ttk.Checkbutton(
            options_frame,
            text="중복 이미지 제거",
            variable=self.remove_duplicates_var,
        )
        duplicate_check.grid(row=0, column=0, sticky="w")

        progress_frame = ttk.Frame(self.root)
        progress_frame.grid(row=5, column=0, padx=16, pady=6, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(progress_frame, textvariable=self.progress_text_var, width=6).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(self.root, text="로그").grid(row=6, column=0, padx=16, pady=(8, 0), sticky="w")

        log_frame = ttk.Frame(self.root)
        log_frame.grid(row=7, column=0, padx=16, pady=(4, 12), sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=10, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

    def _setup_drag_and_drop(self) -> None:
        if not TkinterDnD or not DND_FILES:
            self._append_log("tkinterdnd2가 설치되지 않아 드래그 앤 드롭은 비활성화됩니다.")
            return

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._handle_drop)
        self.pdf_listbox.drop_target_register(DND_FILES)
        self.pdf_listbox.dnd_bind("<<Drop>>", self._handle_drop)

    def _select_pdfs(self) -> None:
        paths = filedialog.askopenfilenames(
            title="PDF 파일 선택",
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")],
        )
        self._add_pdf_paths(paths)

    def _select_output_dir(self) -> None:
        selected = filedialog.askdirectory(title="출력 폴더 선택")
        if not selected:
            return

        self.output_dir = Path(selected)
        self.output_dir_var.set(str(self.output_dir))

    def _clear_pdfs(self) -> None:
        if self._is_running():
            return

        self.pdf_paths.clear()
        self.pdf_listbox.delete(0, tk.END)

    def _handle_drop(self, event) -> None:
        paths = self.root.tk.splitlist(event.data)
        self._add_pdf_paths(paths)

    def _add_pdf_paths(self, paths) -> None:
        existing = {path.resolve() for path in self.pdf_paths}
        added = 0

        for raw_path in paths:
            path = Path(raw_path)
            if path.suffix.lower() != ".pdf" or not path.is_file():
                continue

            resolved = path.resolve()
            if resolved in existing:
                continue

            self.pdf_paths.append(path)
            existing.add(resolved)
            self.pdf_listbox.insert(tk.END, str(path))
            added += 1

        if added:
            self._append_log(f"PDF {added}개를 목록에 추가했습니다.")

    def _start_extraction(self) -> None:
        if self._is_running():
            return

        if not self.pdf_paths:
            messagebox.showwarning("PDF 없음", "추출할 PDF 파일을 먼저 추가하세요.")
            return

        self.progress_var.set(0)
        self.progress_text_var.set("0%")
        self._set_controls_enabled(False)
        self._append_log("작업을 시작합니다.")

        self.worker = ExtractionWorker(
            pdf_paths=list(self.pdf_paths),
            output_dir=self.output_dir,
            remove_duplicates=self.remove_duplicates_var.get(),
            events=self.events,
        )
        self.worker.start()

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            event_type = event.get("type")
            if event_type == "log":
                self._append_log(event["message"])
            elif event_type == "progress":
                value = min(100, max(0, int(event["value"])))
                self.progress_var.set(value)
                self.progress_text_var.set(f"{value}%")
            elif event_type == "done":
                self.progress_var.set(100)
                self.progress_text_var.set("100%")
                self._set_controls_enabled(True)
                self._append_log(event["message"])
                self.worker = None

        self.root.after(100, self._poll_events)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for widget in (self.add_button, self.clear_button, self.output_button, self.start_button):
            widget.configure(state=state)

    def _is_running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()
