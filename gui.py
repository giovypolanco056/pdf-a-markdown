#!/usr/bin/env python3
"""Interfaz gráfica para el conversor PDF -> Markdown (Fase 1).

Ejecutar con:  python gui.py     (o doble clic en  interfaz.bat)

Dos modos (pestañas):
  * "Convertir archivos": eliges PDFs o carpetas y los conviertes.
  * "Vigilar carpeta": eliges una carpeta de ENTRADA y otra de SALIDA; cada PDF
    que llegue a la entrada se convierte solo y su original pasa a "procesados".

No requiere dependencias extra: Tkinter viene incluido con Python. El trabajo
pesado corre en hilos aparte para que la ventana no se congele.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))          # para importar watch.py
sys.path.insert(0, str(PROJECT_DIR / "src"))  # para importar el paquete pdf2md

import watch as watch_mod                                   # noqa: E402
from pdf2md.config import Config                            # noqa: E402
from pdf2md.errors import get_logger                        # noqa: E402
from pdf2md.pipeline import SUPPORTED_EXTS, convert_path, find_documents  # noqa: E402


def _abs(p) -> Path:
    """Convierte una ruta a absoluta respecto a la carpeta del proyecto."""
    p = Path(p)
    return p if p.is_absolute() else (PROJECT_DIR / p)


def build_config(output_dir: str, *, overwrite: bool, detect_tables: bool,
                 remove_headers_footers: bool, include_page_markers: bool,
                 ocr_lang: str, ocr_dpi: int) -> Config:
    """Construye la Config a partir de config.yaml + opciones de la interfaz.

    Es una función pura (sin Tkinter) para poder probarla sin abrir ventana.
    """
    cfg = Config.load(str(PROJECT_DIR / "config.yaml"))
    cfg.output_dir = str(_abs(output_dir))
    cfg.errors_dir = str(_abs(cfg.errors_dir))
    if cfg.tessdata_dir:                       # que funcione sea cual sea el CWD
        cfg.tessdata_dir = str(_abs(cfg.tessdata_dir))
    cfg.overwrite = overwrite
    cfg.detect_tables = detect_tables
    cfg.remove_headers_footers = remove_headers_footers
    cfg.include_page_markers = include_page_markers
    cfg.ocr_lang = ocr_lang or cfg.ocr_lang
    cfg.ocr_dpi = ocr_dpi or cfg.ocr_dpi
    return cfg


class ConverterGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.files: list[Path] = []
        self.queue: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.watch_stop = threading.Event()
        self.watch_thread: threading.Thread | None = None

        self._defaults = Config.load(str(PROJECT_DIR / "config.yaml"))

        root.title("Documentos → Markdown")
        root.geometry("800x740")
        root.minsize(680, 660)

        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll_queue)

    # ================================================================== UI ==
    def _build_ui(self) -> None:
        ttk.Label(self.root, text="Documentos → Markdown",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=10, pady=(10, 2))

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10, pady=4)
        tab_convert = ttk.Frame(nb)
        tab_watch = ttk.Frame(nb)
        nb.add(tab_convert, text="   Convertir archivos   ")
        nb.add(tab_watch, text="   Vigilar carpeta   ")

        self._build_convert_tab(tab_convert)
        self._build_watch_tab(tab_watch)
        self._build_options(self.root)

        # Progreso + estado (del modo "Convertir") + registro compartido
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(4, 0))
        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(self.root, textvariable=self.status_var).pack(anchor="w", padx=10, pady=(2, 4))
        self._build_log(self.root)

    def _build_convert_tab(self, parent: ttk.Frame) -> None:
        frm_in = ttk.LabelFrame(parent, text="Archivos a convertir  (PDF · Word · Excel)")
        frm_in.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        lst_wrap = ttk.Frame(frm_in)
        lst_wrap.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.listbox = tk.Listbox(lst_wrap, selectmode="extended", height=7, activestyle="none")
        sb = ttk.Scrollbar(lst_wrap, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btns = ttk.Frame(frm_in)
        btns.pack(side="right", fill="y", padx=8, pady=8)
        ttk.Button(btns, text="Agregar archivos…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Agregar carpeta…", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(btns, text="Quitar selección", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Vaciar lista", command=self.clear_files).pack(fill="x", pady=2)
        self.recursive_var = tk.BooleanVar(value=self._defaults.recursive)
        ttk.Checkbutton(btns, text="Incluir subcarpetas",
                        variable=self.recursive_var).pack(anchor="w", pady=(10, 0))

        frm_out = ttk.LabelFrame(parent, text="Carpeta de salida (.md)")
        frm_out.pack(fill="x", padx=8, pady=4)
        self.output_var = tk.StringVar(value=str(_abs(self._defaults.output_dir)))
        ttk.Entry(frm_out, textvariable=self.output_var).pack(
            side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(frm_out, text="Elegir…", command=self.choose_output).pack(
            side="right", padx=8, pady=8)

        frm_go = ttk.Frame(parent)
        frm_go.pack(fill="x", padx=8, pady=(4, 8))
        self.convert_btn = ttk.Button(frm_go, text="▶  Convertir", command=self.start)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ttk.Button(frm_go, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=6)
        ttk.Button(frm_go, text="Abrir carpeta Markdown",
                   command=self.open_output).pack(side="right")
        ttk.Button(frm_go, text="Abrir errores", command=self.open_errors).pack(side="right", padx=6)

    def _build_watch_tab(self, parent: ttk.Frame) -> None:
        info = ("Elige la carpeta de ENTRADA (donde dejarás los archivos nuevos) y la de "
                "SALIDA (.md). Con la vigilancia activa, cada PDF, Word o Excel que llegue "
                "se convierte solo y su original pasa a 'procesados'.")
        ttk.Label(parent, text=info, wraplength=740, justify="left").pack(
            anchor="w", padx=10, pady=(10, 6))

        self.w_in_var = tk.StringVar(value=str(_abs(self._defaults.watch_dir)))
        self.w_out_var = tk.StringVar(value=str(_abs(self._defaults.output_dir)))
        self.w_proc_var = tk.StringVar(value=str(_abs(self._defaults.processed_dir)))
        self.w_vault_var = tk.StringVar(value=str(self._defaults.vault_dir or ""))
        self.obsidian_var = tk.BooleanVar(value=bool(self._defaults.vault_dir))

        grid = ttk.Frame(parent)
        grid.pack(fill="x", padx=10, pady=4)
        grid.columnconfigure(1, weight=1)
        self._folder_row(grid, 0, "Carpeta de ENTRADA:", self.w_in_var, self.choose_watch_in)
        self._folder_row(grid, 1, "Carpeta de SALIDA (.md):", self.w_out_var, self.choose_watch_out)
        self._folder_row(grid, 2, "Carpeta de PROCESADOS:", self.w_proc_var, self.choose_watch_proc)
        self._folder_row(grid, 3, "Bóveda Obsidian:", self.w_vault_var, self.choose_watch_vault)

        ttk.Checkbutton(
            parent, variable=self.obsidian_var,
            text="Al convertir, enviar a Obsidian y organizar por formato (PDF · Word · Excel)"
        ).pack(anchor="w", padx=12, pady=(2, 0))

        row_i = ttk.Frame(parent)
        row_i.pack(fill="x", padx=10, pady=(4, 8))
        ttk.Label(row_i, text="Revisar cada (segundos):").pack(side="left")
        self.w_interval_var = tk.IntVar(value=3)
        ttk.Spinbox(row_i, from_=1, to=60, width=6,
                    textvariable=self.w_interval_var).pack(side="left", padx=6)

        frm_go = ttk.Frame(parent)
        frm_go.pack(fill="x", padx=10, pady=4)
        self.watch_start_btn = ttk.Button(frm_go, text="▶  Iniciar vigilancia",
                                           command=self.start_watch)
        self.watch_start_btn.pack(side="left")
        self.watch_stop_btn = ttk.Button(frm_go, text="■  Detener", command=self.stop_watch,
                                         state="disabled")
        self.watch_stop_btn.pack(side="left", padx=6)
        ttk.Button(frm_go, text="Abrir carpeta Markdown",
                   command=self.open_watch_output).pack(side="right")

        self.watch_activity = ttk.Progressbar(parent, mode="indeterminate")
        self.watch_activity.pack(fill="x", padx=10, pady=(6, 0))
        self.watch_status_var = tk.StringVar(value="Vigilancia detenida.")
        ttk.Label(parent, textvariable=self.watch_status_var).pack(anchor="w", padx=10, pady=(2, 6))

    def _folder_row(self, parent, r, label, var, command) -> None:
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=r, column=1, sticky="ew", padx=6, pady=3)
        ttk.Button(parent, text="Elegir…", command=command).grid(row=r, column=2, pady=3)

    def _build_options(self, parent) -> None:
        frm = ttk.LabelFrame(parent, text="Opciones (para ambos modos)")
        frm.pack(fill="x", padx=10, pady=4)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.tables_var = tk.BooleanVar(value=self._defaults.detect_tables)
        self.headers_var = tk.BooleanVar(value=self._defaults.remove_headers_footers)
        self.markers_var = tk.BooleanVar(value=self._defaults.include_page_markers)
        row1 = ttk.Frame(frm); row1.pack(fill="x", padx=8, pady=(6, 0))
        ttk.Checkbutton(row1, text="Sobrescribir existentes", variable=self.overwrite_var).pack(side="left", padx=6)
        ttk.Checkbutton(row1, text="Detectar tablas", variable=self.tables_var).pack(side="left", padx=6)
        ttk.Checkbutton(row1, text="Quitar cabeceras/pies", variable=self.headers_var).pack(side="left", padx=6)
        ttk.Checkbutton(row1, text="Marcas de página", variable=self.markers_var).pack(side="left", padx=6)
        row2 = ttk.Frame(frm); row2.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Label(row2, text="Idioma OCR:").pack(side="left", padx=(6, 2))
        self.lang_var = tk.StringVar(value=self._defaults.ocr_lang)
        ttk.Entry(row2, textvariable=self.lang_var, width=10).pack(side="left")
        ttk.Label(row2, text="DPI OCR:").pack(side="left", padx=(16, 2))
        self.dpi_var = tk.IntVar(value=self._defaults.ocr_dpi)
        ttk.Spinbox(row2, from_=150, to=600, increment=50, width=6,
                    textvariable=self.dpi_var).pack(side="left")

    def _build_log(self, parent) -> None:
        frm_log = ttk.LabelFrame(parent, text="Actividad")
        frm_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log = tk.Text(frm_log, height=8, wrap="word", state="disabled")
        logsb = ttk.Scrollbar(frm_log, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=logsb.set)
        self.log.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        logsb.pack(side="right", fill="y", pady=8)
        self.log.tag_configure("ok", foreground="#1a7f37")
        self.log.tag_configure("skip", foreground="#9a6700")
        self.log.tag_configure("error", foreground="#cf222e")
        self.log.tag_configure("info", foreground="#57606a")

    # ============================================================ archivos ==
    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecciona documentos (PDF, Word o Excel)",
            filetypes=[("Documentos", "*.pdf *.docx *.xlsx"),
                       ("PDF", "*.pdf"), ("Word", "*.docx"),
                       ("Excel", "*.xlsx"), ("Todos", "*.*")])
        self._add([Path(p) for p in paths])

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta con documentos")
        if folder:
            self._add(find_documents(Path(folder), self.recursive_var.get()))

    def _add(self, paths: list[Path]) -> None:
        existing = set(self.files)
        added = 0
        for p in paths:
            if p.suffix.lower() in SUPPORTED_EXTS and p not in existing:
                self.files.append(p)
                existing.add(p)
                added += 1
        self._refresh_list()
        if added:
            self._log(f"Añadidos {added} archivo(s). Total: {len(self.files)}.\n", "info")

    def remove_selected(self) -> None:
        for idx in sorted(self.listbox.curselection(), reverse=True):
            del self.files[idx]
        self._refresh_list()

    def clear_files(self) -> None:
        self.files.clear()
        self._refresh_list()

    def _refresh_list(self) -> None:
        self.listbox.delete(0, "end")
        for p in self.files:
            self.listbox.insert("end", f"  {p.name}      ({p.parent})")

    # ============================================================= carpetas ==
    def choose_output(self) -> None:
        self._pick_into(self.output_var)

    def choose_watch_in(self) -> None:
        self._pick_into(self.w_in_var)

    def choose_watch_out(self) -> None:
        self._pick_into(self.w_out_var)

    def choose_watch_proc(self) -> None:
        self._pick_into(self.w_proc_var)

    def choose_watch_vault(self) -> None:
        self._pick_into(self.w_vault_var)

    def _pick_into(self, var: tk.StringVar) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta",
                                         initialdir=var.get() or str(PROJECT_DIR))
        if folder:
            var.set(folder)

    def open_output(self) -> None:
        self._open_folder(self.output_var.get())

    def open_watch_output(self) -> None:
        self._open_folder(self.w_out_var.get())

    def open_errors(self) -> None:
        self._open_folder(str(_abs(self._defaults.errors_dir)))

    @staticmethod
    def _open_folder(path: str) -> None:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(p))            # Windows
        except AttributeError:              # otros SO
            messagebox.showinfo("Carpeta", str(p))

    # =========================================================== conversión ==
    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showwarning("Sin archivos", "Agrega al menos un documento.")
            return

        cfg = self._config_from_options(self.output_var.get())
        self.cancel_event.clear()
        self._set_running(True)
        self.progress.configure(mode="determinate", value=0, maximum=len(self.files))
        self._clear_log()
        self._log(f"Convirtiendo {len(self.files)} documento(s)…\n\n", "info")

        files = list(self.files)

        def work():
            def on_progress(done, total, name, status, detail):
                self.queue.put(("progress", done, total, name, status, detail))
            try:
                summary = convert_path(cfg, output_override=self.output_var.get(),
                                       files=files, on_progress=on_progress,
                                       should_cancel=self.cancel_event.is_set)
                self.queue.put(("done", summary))
            except Exception as exc:  # fallo inesperado del propio proceso
                self.queue.put(("fatal", f"{exc.__class__.__name__}: {exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.status_var.set("Cancelando… (terminará el archivo en curso)")

    # ============================================================ vigilancia ==
    def start_watch(self) -> None:
        if self.watch_thread and self.watch_thread.is_alive():
            return
        entrada = self.w_in_var.get().strip()
        salida = self.w_out_var.get().strip()
        proc = self.w_proc_var.get().strip() or str(_abs(self._defaults.processed_dir))
        if not entrada or not salida:
            messagebox.showwarning("Faltan carpetas",
                                   "Elige la carpeta de entrada y la de salida.")
            return
        try:
            interval = max(1.0, float(self.w_interval_var.get()))
        except (tk.TclError, ValueError):
            interval = 3.0

        cfg = self._config_from_options(salida)
        if self.obsidian_var.get() and self.w_vault_var.get().strip():
            cfg.vault_dir = self.w_vault_var.get().strip()   # ciclo completo hacia Obsidian
        else:
            cfg.vault_dir = None
        overwrite = self.overwrite_var.get()
        entrada_p, salida_p = _abs(entrada), _abs(salida)
        proc_p, errors_p = _abs(proc), _abs(cfg.errors_dir)

        self.watch_stop.clear()
        self._set_watching(True)
        self._clear_log()

        def on_event(kind, a, b):
            self.queue.put(("watch", kind, a, b))

        def work():
            try:
                watch_mod.watch(cfg, entrada_p, salida_p, proc_p, errors_p, interval,
                                get_logger(), overwrite,
                                stop_event=self.watch_stop, on_event=on_event)
            except Exception as exc:
                self.queue.put(("watch", "fatal", f"{exc.__class__.__name__}: {exc}", ""))

        self.watch_thread = threading.Thread(target=work, daemon=True)
        self.watch_thread.start()

    def stop_watch(self) -> None:
        self.watch_stop.set()
        self.watch_status_var.set("Deteniendo vigilancia…")

    def _config_from_options(self, output_dir: str) -> Config:
        return build_config(
            output_dir,
            overwrite=self.overwrite_var.get(),
            detect_tables=self.tables_var.get(),
            remove_headers_footers=self.headers_var.get(),
            include_page_markers=self.markers_var.get(),
            ocr_lang=self.lang_var.get().strip(),
            ocr_dpi=int(self.dpi_var.get()),
        )

    # ============================================= puente hilo -> interfaz ==
    def _poll_queue(self) -> None:
        try:
            while True:
                self._handle(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _handle(self, msg: tuple) -> None:
        kind = msg[0]
        if kind == "progress":
            _, done, total, name, status, detail = msg
            if status == "start":
                self.status_var.set(f"[{done + 1}/{total}]  {name}")
            else:
                self.progress.configure(value=done)
                marker = {"ok": "[OK]     ", "skip": "[omitido]", "error": "[ERROR]  "}.get(status, " • ")
                tag = status if status in ("ok", "skip", "error") else "info"
                extra = f"  ({detail})" if detail else ""
                self._log(f"{marker}  {name}{extra}\n", tag)
        elif kind == "done":
            self._finish(msg[1])
        elif kind == "fatal":
            self._log(f"\n⚠ Error inesperado: {msg[1]}\n", "error")
            self.status_var.set("Error inesperado.")
            self._set_running(False)
        elif kind == "watch":
            self._handle_watch(msg[1], msg[2], msg[3])

    def _handle_watch(self, sub: str, a: str, b: str) -> None:
        if sub == "started":
            self.watch_status_var.set("Vigilando… (esperando PDFs)")
            self._log(f"Vigilando: {a}\n   -> salida: {b}\n\n", "info")
        elif sub == "ok":
            self._log(f"[OK]     {a}   ->   {b}\n", "ok")
            self.watch_status_var.set(f"Último convertido: {a}")
        elif sub == "error":
            self._log(f"[ERROR]  {a}   ({b})\n", "error")
            self.watch_status_var.set(f"Error con: {a}")
        elif sub == "stopped":
            self._log("\nVigilancia detenida.\n", "info")
            self.watch_status_var.set("Vigilancia detenida.")
            self._set_watching(False)
        elif sub == "fatal":
            self._log(f"\n⚠ Error en la vigilancia: {a}\n", "error")
            self.watch_status_var.set("Error en la vigilancia.")
            self._set_watching(False)

    def _finish(self, summary: dict) -> None:
        self._set_running(False)
        s = summary
        self.status_var.set(
            f"Terminado: {s['ok']} OK · {s['skipped']} omitidos · {s['failed']} con error "
            f"(de {s['total']}).")
        self._log(f"\n{self.status_var.get()}\n", "info")

        produced = s["ok"] + s["skipped"]   # cuántos .md hay en la carpeta de salida
        if s["failed"]:
            self._log("Revisa la carpeta de errores para el detalle.\n", "error")
            if produced and messagebox.askyesno(
                    "Terminado con errores",
                    f"{s['failed']} archivo(s) fallaron; {produced} quedaron listos.\n\n"
                    "¿Abrir la carpeta con los Markdown?"):
                self.open_output()
            elif not produced:
                messagebox.showwarning(
                    "Con errores", f"{s['failed']} archivo(s) fallaron. Revisa 'Abrir errores'.")
        elif produced and messagebox.askyesno(
                "Listo", f"{s['ok']} archivo(s) convertidos correctamente.\n\n"
                         "¿Abrir la carpeta con los Markdown?"):
            self.open_output()

    # ================================================================ helpers ==
    def _set_running(self, running: bool) -> None:
        self.convert_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def _set_watching(self, watching: bool) -> None:
        self.watch_start_btn.configure(state="disabled" if watching else "normal")
        self.watch_stop_btn.configure(state="normal" if watching else "disabled")
        if watching:
            self.watch_activity.start(12)
        else:
            self.watch_activity.stop()

    def _log(self, text: str, tag: str = "info") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        self.cancel_event.set()
        self.watch_stop.set()
        self.root.destroy()


def main() -> None:
    try:   # nitidez en pantallas de alta resolución (Windows)
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")   # tema nativo de Windows si está disponible
    except tk.TclError:
        pass
    ConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
