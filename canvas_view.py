"""
canvas_view.py — Visualización en tiempo real de figuras geométricas.
Usa tkinter (incluido en Python estándar, sin dependencias externas).

Pestañas:
  1. Canvas  — figuras dibujadas en tiempo real.
  2. Historial — log de tokens léxicos y evolución de la tabla de símbolos.

Sistema de coordenadas del canvas:
  · Origen (0,0) en la esquina inferior-izquierda del área útil.
  · X crece hacia la derecha, Y hacia arriba.
  · Cada unidad de posición = GRID píxeles.
  · Tamaño de figura = escala * UNIT píxeles.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from tabla_simbolos import EntradaFigura, TablaSimbolos


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════════

# W, H, OX, OY se calculan en CanvasView.__init__ según la resolución de pantalla
GRID   = 20                # píxeles por unidad de posición
UNIT   = 15                # píxeles base para escala = 1

# ── Paleta (Catppuccin Latte — tema claro) ───────────────────────────────────────
BG          = "#eff1f5"
GRID_MINOR  = "#dce0e8"
GRID_AXIS   = "#9ca0b0"
LABEL_FG    = "#4c4f69"
STATUS_BG   = "#e6e9ef"
STATUS_OK   = "#40a02b"
STATUS_WARN = "#df8e1d"
STATUS_ERR  = "#d20f39"
OUTLINE_DEF = "#4c4f69"

# Mapeo tipo → color de relleno por defecto (si el color es "white" o no parseable)
_TIPO_COLOR: Dict[str, str] = {
    "circle":    "#1e66f5",
    "square":    "#40a02b",
    "triangle":  "#df8e1d",
    "line":      "#d20f39",
    "pentagon":  "#8839ef",
    "rectangle": "#fe640b",
    "ellipse":   "#179299",
    "text":      "#dc8a78",
}


# ═══════════════════════════════════════════════════════════════════════════════
# UTILIDADES DE COLOR
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_color(raw: str, tipo: str) -> str:
    """Convierte el lexema de color almacenado en la tabla a un color tkinter."""
    # String entre comillas: "red" → red
    if raw.startswith('"') and raw.endswith('"'):
        inner = raw[1:-1].strip()
        return inner if inner else _TIPO_COLOR.get(tipo, "white")

    # Hexadecimal de nuestra gramática: #[0-9A-Fa-f]+
    if raw.startswith('#'):
        h = raw[1:]
        try:
            if len(h) == 6:                         # #RRGGBB
                return raw
            if len(h) == 3:                         # #RGB → #RRGGBB
                r, g, b = h
                return f"#{r}{r}{g}{g}{b}{b}"
            if 1 <= len(h) <= 2:                    # escala de grises
                v = int(h, 16) * 255 // (16 ** len(h) - 1)
                return f"#{v:02x}{v:02x}{v:02x}"
            if len(h) > 6:                          # recortar a los primeros 6
                return f"#{h[:6]}"
        except ValueError:
            pass
        return _TIPO_COLOR.get(tipo, "white")

    # Nombre de color de texto plano (sin comillas, ej. generado internamente)
    return raw if raw else _TIPO_COLOR.get(tipo, "white")


# ═══════════════════════════════════════════════════════════════════════════════
# CANVAS VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class CanvasView:
    """
    Ventana tk con tres pestañas + consola integrada:
      · "Canvas"    — figuras geométricas en tiempo real.
      · "Historial" — log léxico y evolución de la tabla de símbolos.
      · "AST"       — árbol del último comando parseado.
      Consola de salida + barra de input en la parte inferior.
    """

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        root.title("Figuras Geométricas — intérprete")
        root.configure(bg=STATUS_BG)
        root.resizable(True, True)

        # ── Dimensiones iniciales basadas en la resolución de pantalla ────────
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self._W  = int(sw * 0.65)
        self._H  = int(sh * 0.75)
        self._OX = 70
        self._OY = int(self._H * 0.88)
        self._current_tabla: Optional[TablaSimbolos] = None

        # ── Zoom, pan y selección (deben estar antes de _draw_grid) ──────────
        self._scale:        float            = 1.0
        self._ox:           int              = 70
        self._oy:           int              = int(self._H * 0.6)
        self._first_resize: bool             = True
        self._pan_start_pt: Optional[tuple]  = None

        # Ventana: casi pantalla completa
        root.geometry(f"{sw - 60}x{sh - 80}")
        root.minsize(800, 480)

        # ── Estilo del Notebook ───────────────────────────────────────────────
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TNotebook",
                         background=STATUS_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                         background="#ccd0da", foreground=LABEL_FG,
                         padding=[14, 4], font=("Consolas", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", "#bcc0cc")],
                  foreground=[("selected", "#4c4f69")])
        style.configure("TPane.TFrame", background=STATUS_BG)

        # ── Layout principal: PanedWindow horizontal (9 col canvas | 3 col consola) ─
        main = tk.PanedWindow(
            root,
            orient=tk.HORIZONTAL,
            bg="#ccd0da",
            sashwidth=4,
            sashrelief=tk.FLAT,
            opaqueresize=True,
        )
        main.pack(fill=tk.BOTH, expand=True)

        # Panel izquierdo: Notebook (9/12 = 75 %)
        left = tk.Frame(main, bg=STATUS_BG)
        main.add(left, stretch="always", minsize=400)

        self._nb = ttk.Notebook(left)
        self._nb.pack(fill=tk.BOTH, expand=True)

        # Panel derecho: consola (3/12 = 25 %)
        con_frame = tk.Frame(main, bg="#e6e9ef")
        main.add(con_frame, stretch="never", minsize=200)
        self._build_console(con_frame)

        # Aplicar proporción 9:3 cuando la ventana ya tiene tamaño real
        def _set_sash(event=None):
            total = main.winfo_width()
            if total > 10:
                main.sash_place(0, int(total * 7 / 12), 0)
                root.unbind("<Map>")
        root.bind("<Map>", _set_sash)

        # ── Pestaña 1: Canvas ─────────────────────────────────────────────────
        tab_canvas = tk.Frame(self._nb, bg=BG)
        self._nb.add(tab_canvas, text="  Canvas  ")

        # Toolbar (arriba)
        toolbar = tk.Frame(tab_canvas, bg=STATUS_BG, pady=2)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        _btn_kw = dict(bg="#ccd0da", fg=LABEL_FG, relief=tk.FLAT,
                       padx=8, pady=2, font=("Consolas", 9),
                       activebackground="#bcc0cc", activeforeground=LABEL_FG,
                       cursor="hand2")
        tk.Button(toolbar, text="SVG",      command=self._export_svg,  **_btn_kw).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="PNG",      command=self._export_png,  **_btn_kw).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="⊛ Reset", command=self._reset_view,  **_btn_kw).pack(side=tk.LEFT, padx=8)
        tk.Label(toolbar, text="  Rueda: zoom | Click izquierdo: pan",
                 bg=STATUS_BG, fg=GRID_AXIS, font=("Consolas", 8)).pack(side=tk.LEFT, padx=6)

        self._canvas = tk.Canvas(
            tab_canvas,
            bg=BG, highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.bind("<Configure>",    self._on_canvas_resize)
        self._canvas.bind("<MouseWheel>",   self._on_zoom)          # Windows
        self._canvas.bind("<Button-4>",     self._on_zoom)          # Linux scroll ↑
        self._canvas.bind("<Button-5>",     self._on_zoom)          # Linux scroll ↓
        self._canvas.bind("<ButtonPress-2>",self._on_pan_start)     # botón medio
        self._canvas.bind("<B2-Motion>",    self._on_pan_move)
        self._canvas.bind("<ButtonPress-1>",self._on_pan_start)     # botón izquierdo
        self._canvas.bind("<B1-Motion>",    self._on_pan_move)
        self._draw_grid()

        # ── Pestaña 2: Historial ──────────────────────────────────────────────
        tab_hist = tk.Frame(self._nb, bg=STATUS_BG)
        self._nb.add(tab_hist, text="  Historial  ")
        self._build_historial(tab_hist)

        # ── Pestaña 3: AST ────────────────────────────────────────────────────
        tab_ast = tk.Frame(self._nb, bg=STATUS_BG)
        self._nb.add(tab_ast, text="  AST  ")
        self._build_ast_tab(tab_ast)

        # ── Pestaña 4: Referencia ─────────────────────────────────────────────
        tab_ref = tk.Frame(self._nb, bg=STATUS_BG)
        self._nb.add(tab_ref, text="  Referencia  ")
        self._build_ref_tab(tab_ref)

        # ── Pestaña 5: About ──────────────────────────────────────────────────
        tab_about = tk.Frame(self._nb, bg=STATUS_BG)
        self._nb.add(tab_about, text="  About  ")
        self._build_about_tab(tab_about)

        # ── Pestaña 6: Docs ───────────────────────────────────────────────────
        tab_docs = tk.Frame(self._nb, bg=STATUS_BG)
        self._nb.add(tab_docs, text="  Docs  ")
        self._build_docs_tab(tab_docs)

        # ── Callback de comandos + registro de figuras ────────────────────────
        self._cmd_callback = None
        self._items: Dict[str, List[int]] = {}
        self._cmd_count = 0
        self._history:  List[str] = []   # últimos 10 comandos ejecutados
        self._hist_idx: int = -1         # -1 = no estamos navegando

    # ═══════════════════════════════════════════════════════════════════════════
    # PESTAÑA HISTORIAL — construcción
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_historial(self, parent: tk.Frame) -> None:
        """Construye el panel de historial con dos secciones scrollables."""

        # ── Sección superior: log léxico ──────────────────────────────────────
        tk.Label(parent, text=" LOG LÉXICO / PIPELINE",
                 bg=STATUS_BG, fg="#8c8fa1",
                 font=("Consolas", 9, "bold"),
                 anchor="w").pack(fill=tk.X, padx=6, pady=(6, 0))

        lex_frame = tk.Frame(parent, bg=STATUS_BG)
        lex_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        lex_scroll = tk.Scrollbar(lex_frame, orient=tk.VERTICAL)
        lex_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._lex_text = tk.Text(
            lex_frame,
            bg="#ffffff", fg=LABEL_FG,
            font=("Consolas", 9),
            height=14,
            state=tk.DISABLED,
            yscrollcommand=lex_scroll.set,
            wrap=tk.NONE,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#dce0e8",
        )
        self._lex_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lex_scroll.config(command=self._lex_text.yview)

        # Tags de colores para el log léxico
        self._lex_text.tag_config("cmd",     foreground="#209fb5", font=("Consolas", 9, "bold"))
        self._lex_text.tag_config("header",  foreground="#8c8fa1", font=("Consolas", 9, "italic"))
        self._lex_text.tag_config("token",   foreground="#8839ef")
        self._lex_text.tag_config("ok",      foreground=STATUS_OK)
        self._lex_text.tag_config("err",     foreground=STATUS_ERR)
        self._lex_text.tag_config("warn",    foreground=STATUS_WARN)
        self._lex_text.tag_config("sep",     foreground="#dce0e8")

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(parent, bg="#dce0e8", height=2).pack(fill=tk.X, padx=6)

        # ── Sección inferior: tabla de símbolos ───────────────────────────────
        tk.Label(parent, text=" TABLA DE SÍMBOLOS — evolución",
                 bg=STATUS_BG, fg="#8c8fa1",
                 font=("Consolas", 9, "bold"),
                 anchor="w").pack(fill=tk.X, padx=6, pady=(4, 0))

        sym_frame = tk.Frame(parent, bg=STATUS_BG)
        sym_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))

        sym_scroll_y = tk.Scrollbar(sym_frame, orient=tk.VERTICAL)
        sym_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        sym_scroll_x = tk.Scrollbar(sym_frame, orient=tk.HORIZONTAL)
        sym_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self._sym_text = tk.Text(
            sym_frame,
            bg="#ffffff", fg=LABEL_FG,
            font=("Consolas", 9),
            height=10,
            state=tk.DISABLED,
            yscrollcommand=sym_scroll_y.set,
            xscrollcommand=sym_scroll_x.set,
            wrap=tk.NONE,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#dce0e8",
        )
        self._sym_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sym_scroll_y.config(command=self._sym_text.yview)
        sym_scroll_x.config(command=self._sym_text.xview)

        # Tags de colores tabla de símbolos
        self._sym_text.tag_config("th",      foreground="#8c8fa1", font=("Consolas", 9, "italic"))
        self._sym_text.tag_config("id_col",  foreground="#1e66f5")
        self._sym_text.tag_config("tipo",    foreground="#8839ef")
        self._sym_text.tag_config("active",  foreground=STATUS_OK)
        self._sym_text.tag_config("hidden",  foreground=STATUS_WARN)
        self._sym_text.tag_config("deleted", foreground=STATUS_ERR)
        self._sym_text.tag_config("sep",     foreground="#dce0e8")
        self._sym_text.tag_config("cmd_ref", foreground="#209fb5", font=("Consolas", 9, "bold"))

    # ═══════════════════════════════════════════════════════════════════════════
    # API PÚBLICA
    # ═══════════════════════════════════════════════════════════════════════════

    def actualizar(self, tabla: TablaSimbolos) -> None:
        """Re-dibuja el canvas con el estado actual de la tabla."""
        self._current_tabla = tabla
        for item_ids in self._items.values():
            for iid in item_ids:
                self._canvas.delete(iid)
        self._items.clear()

        for entrada in tabla.listar():
            if not entrada.eliminada:
                self._dibujar(entrada)

    def set_status(self, msg: str, level: str = "ok") -> None:
        """Actualiza la barra de estado compartida."""
        color = {"ok": STATUS_OK, "warn": STATUS_WARN, "error": STATUS_ERR}.get(level, STATUS_OK)
        self._status_var.set(f"  {msg}")
        self._status_lbl.configure(fg=color)

    def log_comando(
        self,
        linea:   str,
        tokens:  list,
        tabla:   TablaSimbolos,
        error:   Optional[str] = None,
        nivel:   str = "ok",
    ) -> None:
        """
        Registra en el historial:
          · Número y texto del comando.
          · Tokens producidos por el lexer.
          · Estado actual de la tabla de símbolos.
          · Error si lo hubo.
        """
        self._cmd_count += 1
        n = self._cmd_count
        self._log_lexico(n, linea, tokens, error, nivel)
        self._log_tabla(n, tabla)

    # ═══════════════════════════════════════════════════════════════════════════
    # HISTORIAL — escritura
    # ═══════════════════════════════════════════════════════════════════════════

    def _txt_append(self, widget: tk.Text, text: str, tag: str = "") -> None:
        widget.configure(state=tk.NORMAL)
        if tag:
            widget.insert(tk.END, text, tag)
        else:
            widget.insert(tk.END, text)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    def _log_lexico(
        self,
        n:      int,
        linea:  str,
        tokens: list,
        error:  Optional[str],
        nivel:  str,
    ) -> None:
        w = self._lex_text
        sep = "─" * 72 + "\n"
        self._txt_append(w, sep, "sep")
        self._txt_append(w, f"  #{n:03d}  ", "header")
        self._txt_append(w, f"{linea}\n", "cmd")

        if error:
            tag = "err" if nivel == "error" else "warn"
            self._txt_append(w, f"  ✗  {error}\n", tag)
        else:
            self._txt_append(w, "  tokens:\n", "header")
            for tok in tokens:
                tipo_str   = f"{tok.tipo.value:<22}"
                lexema_str = f"lexema={tok.lexema!r:<16}"
                pos_str    = f"L{tok.linea}:C{tok.columna}"
                self._txt_append(w, f"    {tipo_str} {lexema_str} {pos_str}\n", "token")
            self._txt_append(w, "  ✓  ok\n", "ok")

    def _log_tabla(self, n: int, tabla: TablaSimbolos) -> None:
        w    = self._sym_text
        sep  = "─" * 80 + "\n"
        cols = f"  {'ID':<16} {'TIPO':<10} {'COLOR':<10} {'ESC':<5} {'POSICION':<12} ESTADO\n"

        self._txt_append(w, sep, "sep")
        self._txt_append(w, f"  tras #{n:03d}  ", "th")
        self._txt_append(w, f"({len([e for e in tabla.listar() if not e.eliminada])} activas)\n", "th")
        self._txt_append(w, cols, "th")
        self._txt_append(w,
            f"  {'─'*16} {'─'*10} {'─'*10} {'─'*5} {'─'*12} {'─'*8}\n", "sep")

        figuras = tabla.listar()
        if not figuras:
            self._txt_append(w, "  (tabla vacía)\n", "th")
            return

        for e in figuras:
            if e.eliminada:
                estado_tag, estado_txt = "deleted", "ELIMINADA"
            elif not e.visible:
                estado_tag, estado_txt = "hidden",  "oculta"
            else:
                estado_tag, estado_txt = "active",  "visible"

            self._txt_append(w, f"  {e.id:<16} ", "id_col")
            self._txt_append(w, f"{e.tipo:<10} ", "tipo")
            self._txt_append(w,
                f"{e.color:<10} {e.escala:<5} {str(list(e.posicion)):<12} ")
            self._txt_append(w, f"{estado_txt}\n", estado_tag)

    # ═══════════════════════════════════════════════════════════════════════════
    # PESTAÑA REFERENCIA — referencia rápida de comandos con ejemplos
    # ═══════════════════════════════════════════════════════════════════════════

    # Referencia dinámica: { etiqueta_listbox: [(tag, texto), ...] }
    _REF_SECTIONS: "Dict[str, List[tuple]]" = {
        "📋  Todos": [],   # se rellena en _build_ref_tab
        "⬡  circle": [
            ("syn",  "  create circle"),
            ("desc", "  Crea un círculo con valores por defecto."),
            ("ex",   '  create circle'),
            ("",     ""),
            ("syn",  '  create circle(color, escala, [x, y])'),
            ("desc", "  color: string o hex   escala: radio en unidades   [x,y]: posición"),
            ("ex",   '  create circle("red", 3, [0, 0])'),
            ("ex",   '  create circle(#89b4fa, 5, [-4, 2])'),
            ("",     ""),
            ("syn",  '  update circle0001(color, escala, [x, y])'),
            ("desc", "  Modifica uno o más campos. Usa _ para conservar el valor actual."),
            ("ex",   '  update circle0001("blue", _, _)'),
            ("ex",   '  update circle0001(_, 4, [1, -3])'),
        ],
        "■  square": [
            ("syn",  "  create square"),
            ("syn",  "  create square(color, escala, [x, y])"),
            ("desc", "  escala: lado del cuadrado en unidades"),
            ("ex",   '  create square("green", 3, [2, 2])'),
            ("ex",   '  create square(#a6e3a1, 5, [0, 0])'),
            ("",     ""),
            ("syn",  "  update square0001(color, escala, [x, y])"),
            ("ex",   '  update square0001(_, 6, _)'),
        ],
        "▲  triangle": [
            ("syn",  "  create triangle"),
            ("syn",  "  create triangle(color, escala, [x, y])"),
            ("desc", "  escala: altura del triángulo equilátero"),
            ("ex",   '  create triangle("blue", 4, [0, 0])'),
            ("ex",   '  create triangle(#f9e2af, 3, [-5, -5])'),
            ("",     ""),
            ("syn",  "  rotate triangle0001 (grados)"),
            ("desc", "  Rota en sentido antihorario."),
            ("ex",   "  rotate triangle0001 (45)"),
            ("ex",   "  rotate triangle0001 (90)"),
        ],
        "—  line": [
            ("syn",  "  create line"),
            ("syn",  "  create line(color, grosor, [x1, y1], [x2, y2])"),
            ("desc", "  Segmento de línea entre dos puntos."),
            ("ex",   '  create line("white", 1, [-5, 0], [5, 0])'),
            ("ex",   '  create line(#f38ba8, 2, [0, -4], [0, 4])'),
            ("",     ""),
            ("syn",  "  update line0001(color, grosor, [x1,y1], [x2,y2])"),
            ("ex",   '  update line0001(_, 3, _, _)'),
        ],
        "⬠  pentagon": [
            ("syn",  "  create pentagon"),
            ("syn",  "  create pentagon(color, escala, [x, y])"),
            ("desc", "  escala: radio circunscrito del pentágono"),
            ("ex",   '  create pentagon("purple", 3, [0, 0])'),
            ("ex",   '  create pentagon(#cba6f7, 4, [3, -2])'),
            ("",     ""),
            ("syn",  "  rotate pentagon0001 (grados)"),
            ("ex",   "  rotate pentagon0001 (36)"),
        ],
        "▭  rectangle": [
            ("syn",  "  create rectangle"),
            ("syn",  "  create rectangle(color, ancho, alto, [x, y])"),
            ("desc", "  ancho y alto son independientes."),
            ("ex",   '  create rectangle("red", 8, 3, [0, 0])'),
            ("ex",   '  create rectangle(#fab387, 6, 4, [-2, 1])'),
            ("",     ""),
            ("syn",  "  update rectangle0001(color, ancho, alto, [x, y])"),
            ("ex",   '  update rectangle0001(_, 10, 2, _)'),
        ],
        "⬭  ellipse": [
            ("syn",  "  create ellipse"),
            ("syn",  "  create ellipse(color, rx, ry, [x, y])"),
            ("desc", "  rx: radio horizontal   ry: radio vertical"),
            ("ex",   '  create ellipse(#94e2d5, 5, 2, [0, 0])'),
            ("ex",   '  create ellipse("salmon", 3, 6, [4, -1])'),
            ("",     ""),
            ("syn",  "  update ellipse0001(color, rx, ry, [x, y])"),
            ("ex",   '  update ellipse0001(_, 7, 3, _)'),
        ],
        "T  text": [
            ("syn",  "  create text"),
            ("syn",  '  create text(color, tamaño, [x, y], "contenido")'),
            ("desc", "  tamaño: escala de la fuente   contenido: texto entre comillas"),
            ("ex",   '  create text("white", 3, [0, 0], "Hola Mundo")'),
            ("ex",   '  create text(#cdd6f4, 2, [-3, 4], "Canvas")'),
            ("",     ""),
            ("syn",  '  update text0001(color, tamaño, [x, y], "nuevo texto")'),
            ("ex",   '  update text0001(_, _, _, "Otro texto")'),
        ],
        "✎  create": [
            ("syn",  "  create <tipo>"),
            ("desc", "  Crea una figura con valores por defecto."),
            ("ex",   "  create circle"),
            ("ex",   "  create square   /   create triangle   /   create line"),
            ("",     ""),
            ("syn",  "  create <tipo>(color, escala, [x, y])"),
            ("desc", "  Forma general para circle, square, triangle, pentagon."),
            ("ex",   '  create circle("red", 3, [0, 0])'),
            ("",     ""),
            ("syn",  "  create line(color, grosor, [x1,y1], [x2,y2])"),
            ("ex",   '  create line("white", 1, [-5,0], [5,0])'),
            ("",     ""),
            ("syn",  "  create rectangle(color, ancho, alto, [x, y])"),
            ("ex",   '  create rectangle("blue", 6, 3, [0, 0])'),
            ("",     ""),
            ("syn",  "  create ellipse(color, rx, ry, [x, y])"),
            ("ex",   '  create ellipse(#89b4fa, 4, 2, [0, 0])'),
            ("",     ""),
            ("syn",  '  create text(color, sz, [x, y], "texto")'),
            ("ex",   '  create text("white", 2, [0, 0], "Hola")'),
        ],
        "✏  update": [
            ("desc", "  Modifica uno o más campos de una figura existente."),
            ("desc", "  Usa _ en cualquier posición para conservar el valor actual."),
            ("",     ""),
            ("syn",  "  update <id>(color, escala, [x, y])"),
            ("desc", "  Para: circle, square, triangle, pentagon"),
            ("ex",   '  update circle0001("blue", _, _)'),
            ("ex",   '  update square0001(_, 5, [3, 3])'),
            ("",     ""),
            ("syn",  "  update <rect_id>(color, ancho, alto, [x, y])"),
            ("ex",   '  update rectangle0001(_, 8, 4, _)'),
            ("",     ""),
            ("syn",  "  update <ellipse_id>(color, rx, ry, [x, y])"),
            ("ex",   '  update ellipse0001(_, 6, 2, _)'),
            ("",     ""),
            ("syn",  '  update <text_id>(color, sz, [x, y], "txt")'),
            ("ex",   '  update text0001(_, _, _, "Nuevo texto")'),
            ("",     ""),
            ("syn",  "  update <line_id>(color, grosor, [x1,y1], [x2,y2])"),
            ("ex",   '  update line0001(#ff0000, _, _, _)'),
        ],
        "↔  move": [
            ("syn",  "  move <id> (dx, dy)"),
            ("desc", "  Desplaza la figura por un offset relativo (dx, dy)."),
            ("desc", "  dx y dy pueden ser negativos. También funciona sobre grupos."),
            ("ex",   "  move circle0001 (3, -2)"),
            ("ex",   "  move rectangle0001 (-5, 0)"),
            ("ex",   "  move group0001 (1, 1)"),
        ],
        "↻  rotate": [
            ("syn",  "  rotate <id> (grados)"),
            ("desc", "  Rota la figura en sentido antihorario."),
            ("desc", "  El ángulo total se acumula. También funciona sobre grupos."),
            ("ex",   "  rotate triangle0001 (45)"),
            ("ex",   "  rotate square0001 (90)"),
            ("ex",   "  rotate group0001 (30)"),
        ],
        "⤢  scale": [
            ("syn",  "  scale <id> (factor)"),
            ("desc", "  Multiplica la escala actual por factor (entero > 0)."),
            ("desc", "  También funciona sobre grupos."),
            ("ex",   "  scale circle0001 (2)"),
            ("ex",   "  scale group0001 (3)"),
        ],
        "⧉  copy": [
            ("syn",  "  copy <id>"),
            ("desc", "  Duplica la figura con un ID nuevo."),
            ("desc", "  La copia aparece con un ligero desplazamiento."),
            ("ex",   "  copy circle0001"),
            ("ex",   "  copy rectangle0001"),
        ],
        "👁  show / hide": [
            ("syn",  "  show <id>   /   hide <id>"),
            ("desc", "  Muestra u oculta una figura o grupo completo."),
            ("desc", "  Las figuras ocultas no se dibujan pero siguen en la tabla."),
            ("ex",   "  hide circle0001"),
            ("ex",   "  show circle0001"),
            ("ex",   "  hide group0001"),
        ],
        "✕  delete": [
            ("syn",  "  delete <id>"),
            ("desc", "  Elimina la figura o grupo permanentemente."),
            ("ex",   "  delete circle0001"),
            ("ex",   "  delete group0001"),
        ],
        "⊞  group": [
            ("syn",  "  group <id1> <id2> ..."),
            ("desc", "  Agrupa dos o más figuras bajo un nuevo ID de grupo."),
            ("desc", "  move, rotate, scale, show, hide y delete operan sobre el grupo completo."),
            ("ex",   "  group circle0001 square0001"),
            ("ex",   "  group circle0001 triangle0001 pentagon0001"),
            ("",     ""),
            ("syn",  "  ungroup <gid>"),
            ("desc", "  Disuelve el grupo. Las figuras miembro se conservan."),
            ("ex",   "  ungroup group0001"),
        ],
        "𝑥  set (variables)": [
            ("desc", "  Las variables se pueden usar en lugar de literales en cualquier comando."),
            ("",     ""),
            ("syn",  "  set <nombre> <entero>"),
            ("desc", "  Variable entera (positiva o negativa)."),
            ("ex",   "  set x 5"),
            ("ex",   "  set y -3"),
            ("ex",   "  set radio 4"),
            ("",     ""),
            ("syn",  '  set <nombre> "color"'),
            ("desc", "  Variable de color como nombre CSS."),
            ("ex",   '  set primario "red"'),
            ("ex",   '  set fondo "darkblue"'),
            ("",     ""),
            ("syn",  "  set <nombre> #hexadecimal"),
            ("desc", "  Variable de color como valor hexadecimal."),
            ("ex",   "  set acento #ff6600"),
            ("ex",   "  set rosa #ff69b4"),
            ("",     ""),
            ("desc", "  Usar variables en comandos:"),
            ("ex",   "  create circle(primario, radio, [x, y])"),
            ("ex",   "  create ellipse(acento, radio, 2, [0, 0])"),
            ("ex",   "  move circle0001 (x, y)"),
            ("ex",   "  scale square0001 (radio)"),
        ],
        "🗒  list / clear": [
            ("syn",  "  list"),
            ("desc", "  Muestra todas las figuras activas en la consola."),
            ("ex",   "  list"),
            ("",     ""),
            ("syn",  "  clear screen"),
            ("desc", "  Elimina todas las figuras y vacía el canvas."),
            ("ex",   "  clear screen"),
        ],
        "🖥  canvas (controles)": [
            ("desc", "  Rueda del ratón         →  zoom acercar / alejar"),
            ("desc", "  Botón medio + arrastrar →  desplazar vista (pan)"),
            ("desc", "  Botón ⊛ Reset           →  restaurar zoom y posición"),
            ("desc", "  Botón SVG               →  exportar a archivo .svg"),
            ("desc", "  Botón PNG               →  exportar a imagen .png (requiere Pillow)"),
        ],
        "🎨  colores": [
            ("desc", "  Se aceptan tres formatos:"),
            ("",     ""),
            ("syn",  '  "nombre CSS"'),
            ("ex",   '  "red"   "blue"   "green"   "salmon"   "gold"   "white"'),
            ("ex",   '  "darkblue"   "tomato"   "orchid"   "teal"   "lime"'),
            ("",     ""),
            ("syn",  "  #RRGGBB"),
            ("ex",   "  #ff0000   #00bfff   #123456   #89b4fa   #a6e3a1"),
            ("",     ""),
            ("syn",  "  variable de color"),
            ("ex",   '  set c "red"   →  create circle(c, 3, [0,0])'),
            ("ex",   "  set h #ff6600  →  create square(h, 2, [0,0])"),
        ],
    }

    def _build_ref_tab(self, parent: tk.Frame) -> None:
        """Construye el panel de referencia dinámica con listbox de categorías."""
        # Rellenar la sección "Todos" concatenando todas las demás
        all_items: "List[tuple]" = []
        for key, rows in self._REF_SECTIONS.items():
            if key == "📋  Todos":
                continue
            label = key.split("  ", 1)[-1]   # quitar icono
            all_items += [("sec", f"══  {label.upper()}  " + "═" * max(0, 50 - len(label)))]
            all_items += rows
            all_items += [("", "")]
        self._REF_SECTIONS["📋  Todos"] = all_items

        # ── Layout: listbox izquierda | detalle derecha ──────────────────────
        pane = tk.PanedWindow(parent, orient=tk.HORIZONTAL,
                              bg="#ccd0da", sashwidth=3, relief=tk.FLAT)
        pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Panel izquierdo — lista de categorías
        left = tk.Frame(pane, bg=STATUS_BG)
        pane.add(left, width=170, minsize=130, stretch="never")

        tk.Label(left, text=" Categoría",
                 bg=STATUS_BG, fg="#8c8fa1",
                 font=("Consolas", 9, "bold"), anchor="w",
                 ).pack(fill=tk.X, padx=4, pady=(4, 2))

        lb_frame = tk.Frame(left, bg=STATUS_BG)
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        lb_scroll = tk.Scrollbar(lb_frame, orient=tk.VERTICAL, bg="#ccd0da")
        lb_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._ref_lb = tk.Listbox(
            lb_frame,
            bg="#ffffff", fg=LABEL_FG,
            selectbackground="#bcc0cc", selectforeground="#4c4f69",
            font=("Consolas", 9),
            relief=tk.FLAT, highlightthickness=0,
            activestyle="none",
            yscrollcommand=lb_scroll.set,
            exportselection=False,
        )
        self._ref_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scroll.config(command=self._ref_lb.yview)

        for key in self._REF_SECTIONS:
            self._ref_lb.insert(tk.END, f"  {key}")

        # Panel derecho — detalle
        right = tk.Frame(pane, bg=STATUS_BG)
        pane.add(right, stretch="always", minsize=200)

        tk.Label(right, text=" Detalle",
                 bg=STATUS_BG, fg="#8c8fa1",
                 font=("Consolas", 9, "bold"), anchor="w",
                 ).pack(fill=tk.X, padx=4, pady=(4, 2))

        detail_frame = tk.Frame(right, bg=STATUS_BG)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        det_scroll_y = tk.Scrollbar(detail_frame, orient=tk.VERTICAL)
        det_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self._ref_txt = tk.Text(
            detail_frame,
            bg="#ffffff", fg=LABEL_FG,
            font=("Consolas", 10),
            state=tk.DISABLED,
            yscrollcommand=det_scroll_y.set,
            wrap=tk.WORD,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#dce0e8",
            cursor="arrow",
            padx=8, pady=6,
        )
        self._ref_txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        det_scroll_y.config(command=self._ref_txt.yview)

        # Tags de color en el detalle
        self._ref_txt.tag_config("sec",  foreground="#6c6f85", font=("Consolas", 9, "bold"))
        self._ref_txt.tag_config("syn",  foreground="#1e66f5", font=("Consolas", 10, "bold"))
        self._ref_txt.tag_config("desc", foreground="#6c6f85", font=("Consolas", 9))
        self._ref_txt.tag_config("ex",   foreground="#40a02b", font=("Consolas", 9))

        def _on_select(event=None) -> None:
            sel = self._ref_lb.curselection()
            if not sel:
                return
            key = list(self._REF_SECTIONS.keys())[sel[0]]
            rows = self._REF_SECTIONS[key]
            self._ref_txt.configure(state=tk.NORMAL)
            self._ref_txt.delete("1.0", tk.END)
            for tag, line in rows:
                self._ref_txt.insert(tk.END, line + "\n", tag or "desc")
            self._ref_txt.configure(state=tk.DISABLED)

        self._ref_lb.bind("<<ListboxSelect>>", _on_select)

        # Seleccionar la primera entrada por defecto
        self._ref_lb.selection_set(0)
        _on_select()

    # ═══════════════════════════════════════════════════════════════════════════
    # PESTAÑA AST — construcción y actualización
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_ast_tab(self, parent: tk.Frame) -> None:
        """Construye el panel del AST con un widget de texto scrollable."""
        header_frame = tk.Frame(parent, bg=STATUS_BG)
        header_frame.pack(fill=tk.X, padx=6, pady=(6, 0))

        tk.Label(
            header_frame, text=" HISTORIAL — ÁRBOL DE SINTAXIS ABSTRACTA",
            bg=STATUS_BG, fg="#8c8fa1",
            font=("Consolas", 9, "bold"), anchor="w",
        ).pack(side=tk.LEFT)

        tk.Button(
            header_frame, text="Limpiar",
            bg="#ccd0da", fg="#6c6f85",
            font=("Consolas", 8), relief=tk.FLAT, cursor="hand2",
            activebackground="#bcc0cc", activeforeground="#4c4f69",
            command=lambda: (
                self._ast_text.configure(state=tk.NORMAL),
                self._ast_text.delete("1.0", tk.END),
                self._ast_text.configure(state=tk.DISABLED),
            ),
        ).pack(side=tk.RIGHT, padx=(0, 2))

        frame = tk.Frame(parent, bg=STATUS_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))

        scroll_y = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self._ast_text = tk.Text(
            frame,
            bg="#ffffff", fg=LABEL_FG,
            font=("Consolas", 10),
            state=tk.DISABLED,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            wrap=tk.NONE,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#dce0e8",
        )
        self._ast_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.config(command=self._ast_text.yview)
        scroll_x.config(command=self._ast_text.xview)

        # Tags de colores
        self._ast_text.tag_config("node",    foreground="#1e66f5",  font=("Consolas", 10, "bold"))
        self._ast_text.tag_config("field",   foreground="#8839ef")
        self._ast_text.tag_config("value",   foreground="#40a02b")
        self._ast_text.tag_config("branch",  foreground="#9ca0b0")
        self._ast_text.tag_config("wildcard",foreground="#df8e1d")
        self._ast_text.tag_config("hint",    foreground="#9ca0b0",  font=("Consolas", 9, "italic"))
        self._ast_text.tag_config("cmd",     foreground="#209fb5",  font=("Consolas", 10, "bold"))
        self._ast_text.tag_config("sep",     foreground="#dce0e8")

    def mostrar_ast(self, linea: str, ast: object) -> None:
        """Agrega al historial del panel AST el árbol del comando recibido."""
        w = self._ast_text
        # Separador entre entradas (omitir si el widget está vacío)
        if w.get("1.0", "end-1c") != "":
            self._txt_append(w, "─" * 52 + "\n", "sep")
        self._txt_append(w, f"→  {linea}\n", "cmd")
        self._ast_render(ast, depth=0, prefix="", is_last=True)

    def _ast_render(self, nodo: object, depth: int, prefix: str, is_last: bool) -> None:
        """Renderiza recursivamente el nodo AST con líneas de árbol Unicode."""
        from ast_nodes import (
            ProgramaNode, CreateNode, UpdateNode, DeleteNode,
            ShowNode, HideNode, ListNode, ClearNode, HelpNode,
            RotateNode, MoveNode, CopyNode, GroupNode, UngroupNode, ScaleNode,
            ParametrosNode, ParametrosUpdateNode, ValorUpdateNode, PosicionNode,
            ParametrosRectanguloNode, ParametrosElipseNode, ParametrosTextoNode,
            ParametrosUpdateRectanguloNode, ParametrosUpdateElipseNode, ParametrosUpdateTextoNode,
        )

        w          = self._ast_text
        connector  = "└── " if is_last else "├── "
        child_pre  = prefix + ("    " if is_last else "│   ")

        def line(text: str, tag: str = "") -> None:
            self._txt_append(w, prefix + connector, "branch")
            self._txt_append(w, text + "\n", tag)

        def field_val(key: str, val: str, vtag: str = "value") -> None:
            self._txt_append(w, child_pre + "    ", "branch")
            self._txt_append(w, f"{key}: ", "field")
            self._txt_append(w, val + "\n", vtag)

        if isinstance(nodo, ProgramaNode):
            self._txt_append(w, "ProgramaNode\n", "node")
            for i, cmd in enumerate(nodo.comandos):
                last = (i == len(nodo.comandos) - 1)
                self._ast_render(cmd, depth + 1, "", last)
            return

        if isinstance(nodo, CreateNode):
            line("CreateNode", "node")
            field_val("tipo_figura", nodo.tipo_figura)
            if nodo.parametros:
                self._ast_render(nodo.parametros, depth + 1, child_pre, is_last=True)
            else:
                self._txt_append(w, child_pre + "    └── ", "branch")
                self._txt_append(w, "parametros: (por defecto)\n", "hint")

        elif isinstance(nodo, UpdateNode):
            line("UpdateNode", "node")
            field_val("id", nodo.id)
            self._ast_render(nodo.parametros, depth + 1, child_pre, is_last=True)

        elif isinstance(nodo, DeleteNode):
            line("DeleteNode", "node")
            field_val("id", nodo.id)

        elif isinstance(nodo, ShowNode):
            line("ShowNode", "node")
            field_val("id", nodo.id)

        elif isinstance(nodo, HideNode):
            line("HideNode", "node")
            field_val("id", nodo.id)

        elif isinstance(nodo, ListNode):
            line("ListNode", "node")

        elif isinstance(nodo, ClearNode):
            line("ClearNode", "node")
            field_val("scope", nodo.scope)

        elif isinstance(nodo, HelpNode):
            line("HelpNode", "node")

        elif isinstance(nodo, RotateNode):
            line("RotateNode", "node")
            field_val("id",     nodo.id)
            field_val("grados", str(nodo.grados))

        elif isinstance(nodo, MoveNode):
            line("MoveNode", "node")
            field_val("id", nodo.id)
            field_val("dx", f"{nodo.dx:+d}")
            field_val("dy", f"{nodo.dy:+d}")

        elif isinstance(nodo, CopyNode):
            line("CopyNode", "node")
            field_val("id", nodo.id)

        elif isinstance(nodo, GroupNode):
            line("GroupNode", "node")
            for i, mid in enumerate(nodo.ids):
                last_m = (i == len(nodo.ids) - 1)
                conn2  = "└── " if last_m else "├── "
                self._txt_append(self._ast_text, child_pre + "    " + conn2, "branch")
                self._txt_append(self._ast_text, f"id[{i}]: ", "field")
                self._txt_append(self._ast_text, mid + "\n", "value")

        elif isinstance(nodo, UngroupNode):
            line("UngroupNode", "node")
            field_val("id", nodo.id)

        elif isinstance(nodo, ScaleNode):
            line("ScaleNode", "node")
            field_val("id",     nodo.id)
            field_val("factor", f"×{nodo.factor}")

        elif isinstance(nodo, ParametrosNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosNode\n", "node")
            pp = child_pre + "    "
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "color: ",   "field")
            self._txt_append(w, nodo.color + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "escala: ",  "field")
            self._txt_append(w, str(nodo.escala) + "\n", "value")
            self._txt_append(w, pp + "└── ", "branch")
            self._txt_append(w, "posicion: ", "field")
            self._txt_append(w, f"[{nodo.posicion.x}, {nodo.posicion.y}]\n", "value")

        elif isinstance(nodo, ParametrosRectanguloNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosRectanguloNode\n", "node")
            pp = child_pre + "    "
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "color: ", "field")
            self._txt_append(w, nodo.color + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "ancho: ", "field")
            self._txt_append(w, str(nodo.ancho) + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "alto: ", "field")
            self._txt_append(w, str(nodo.alto) + "\n", "value")
            self._txt_append(w, pp + "└── ", "branch")
            self._txt_append(w, "posicion: ", "field")
            self._txt_append(w, f"[{nodo.posicion.x}, {nodo.posicion.y}]\n", "value")

        elif isinstance(nodo, ParametrosElipseNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosElipseNode\n", "node")
            pp = child_pre + "    "
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "color: ", "field")
            self._txt_append(w, nodo.color + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "rx: ", "field")
            self._txt_append(w, str(nodo.rx) + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "ry: ", "field")
            self._txt_append(w, str(nodo.ry) + "\n", "value")
            self._txt_append(w, pp + "└── ", "branch")
            self._txt_append(w, "posicion: ", "field")
            self._txt_append(w, f"[{nodo.posicion.x}, {nodo.posicion.y}]\n", "value")

        elif isinstance(nodo, ParametrosTextoNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosTextoNode\n", "node")
            pp = child_pre + "    "
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "color: ", "field")
            self._txt_append(w, nodo.color + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "tamaño: ", "field")
            self._txt_append(w, str(nodo.tamanio) + "\n", "value")
            self._txt_append(w, pp + "├── ", "branch")
            self._txt_append(w, "posicion: ", "field")
            self._txt_append(w, f"[{nodo.posicion.x}, {nodo.posicion.y}]\n", "value")
            self._txt_append(w, pp + "└── ", "branch")
            self._txt_append(w, "contenido: ", "field")
            self._txt_append(w, nodo.contenido + "\n", "value")

        elif isinstance(nodo, ParametrosUpdateRectanguloNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosUpdateRectanguloNode\n", "node")
            pp = child_pre + "    "
            for label, slot in (("color", nodo.color), ("ancho", nodo.ancho),
                                 ("alto", nodo.alto), ("posicion", nodo.posicion)):
                connector2 = "└── " if label == "posicion" else "├── "
                self._txt_append(w, pp + connector2, "branch")
                self._txt_append(w, f"{label}: ", "field")
                if slot.tipo == "wildcard":
                    self._txt_append(w, "_ (conservar)\n", "wildcard")
                else:
                    self._txt_append(w, f"{slot.valor!r}\n", "value")

        elif isinstance(nodo, ParametrosUpdateElipseNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosUpdateElipseNode\n", "node")
            pp = child_pre + "    "
            for label, slot in (("color", nodo.color), ("rx", nodo.rx),
                                 ("ry", nodo.ry), ("posicion", nodo.posicion)):
                connector2 = "└── " if label == "posicion" else "├── "
                self._txt_append(w, pp + connector2, "branch")
                self._txt_append(w, f"{label}: ", "field")
                if slot.tipo == "wildcard":
                    self._txt_append(w, "_ (conservar)\n", "wildcard")
                else:
                    self._txt_append(w, f"{slot.valor!r}\n", "value")

        elif isinstance(nodo, ParametrosUpdateTextoNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosUpdateTextoNode\n", "node")
            pp = child_pre + "    "
            for label, slot in (("color", nodo.color), ("tamaño", nodo.tamanio),
                                 ("posicion", nodo.posicion), ("contenido", nodo.contenido)):
                connector2 = "└── " if label == "contenido" else "├── "
                self._txt_append(w, pp + connector2, "branch")
                self._txt_append(w, f"{label}: ", "field")
                if slot.tipo == "wildcard":
                    self._txt_append(w, "_ (conservar)\n", "wildcard")
                else:
                    self._txt_append(w, f"{slot.valor!r}\n", "value")

        elif isinstance(nodo, ParametrosUpdateNode):
            self._txt_append(w, child_pre + "└── ", "branch")
            self._txt_append(w, "ParametrosUpdateNode\n", "node")
            pp = child_pre + "    "
            for label, slot in (("color", nodo.color), ("escala", nodo.escala), ("posicion", nodo.posicion)):
                connector2 = "└── " if label == "posicion" else "├── "
                self._txt_append(w, pp + connector2, "branch")
                self._txt_append(w, f"{label}: ", "field")
                if slot.tipo == "wildcard":
                    self._txt_append(w, "_ (conservar)\n", "wildcard")
                else:
                    self._txt_append(w, f"{slot.valor!r}\n", "value")

    # ═══════════════════════════════════════════════════════════════════════════
    # CANVAS — grid y dibujo
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_canvas_resize(self, event: tk.Event) -> None:
        """Actualiza dimensiones y redibuja cuando el canvas cambia de tamaño."""
        self._W = event.width
        self._H = event.height
        if self._first_resize:
            self._ox = 70
            self._oy = int(event.height * 0.6)   # 60% desde arriba → cuadrante −Y visible
            self._first_resize = False
        self._canvas.delete("grid")
        self._draw_grid()
        if self._current_tabla is not None:
            self.actualizar(self._current_tabla)

    def _draw_grid(self) -> None:
        W, H  = self._W, self._H
        ox, oy = self._ox, self._oy
        eff   = GRID * self._scale
        if eff <= 0:
            return

        # Intervalo adaptativo de etiquetas según densidad de píxeles
        if eff >= 60:
            interval = 1
        elif eff >= 25:
            interval = 5
        elif eff >= 10:
            interval = 10
        else:
            interval = 20

        fnt = ("Consolas", max(7, min(10, int(8 * min(self._scale, 1.5)))))

        # Líneas verticales (X constante)
        n_min = int((-ox) / eff) - 1
        n_max = int((W - ox) / eff) + 1
        for n in range(n_min, n_max + 1):
            px = ox + n * eff
            color = GRID_AXIS if n == 0 else GRID_MINOR
            width = 2 if n == 0 else 1
            self._canvas.create_line(px, 0, px, H, fill=color, width=width, tags="grid")
            if n != 0 and n % interval == 0 and 0 <= px <= W:
                lbl_y = min(H - 10, max(10, oy + 12))
                self._canvas.create_text(
                    px, lbl_y, text=str(n), fill=GRID_AXIS, font=fnt, tags="grid")

        # Líneas horizontales (Y constante)
        m_min = int((oy - H) / eff) - 1
        m_max = int(oy / eff) + 1
        for m in range(m_min, m_max + 1):
            py = oy - m * eff
            color = GRID_AXIS if m == 0 else GRID_MINOR
            width = 2 if m == 0 else 1
            self._canvas.create_line(0, py, W, py, fill=color, width=width, tags="grid")
            if m != 0 and m % interval == 0 and 0 <= py <= H:
                lbl_x = min(W - 20, max(4, ox - 22))
                self._canvas.create_text(
                    lbl_x, py, text=str(m), fill=GRID_AXIS, font=fnt, tags="grid")

        # Etiqueta del origen y rótulos de ejes
        if 0 <= ox <= W and 0 <= oy <= H:
            self._canvas.create_text(ox - 12, oy + 12, text="0",
                                     fill=GRID_AXIS, font=fnt, tags="grid")
        # X⁺ / X⁻
        self._canvas.create_text(W - 6, max(oy, 10) - 8, text="X+",
                                 fill=LABEL_FG, font=fnt, tags="grid", anchor="e")
        self._canvas.create_text(max(ox - 2, 4), max(oy, 10) - 8, text="X−",
                                 fill=GRID_AXIS, font=fnt, tags="grid", anchor="e")
        # Y⁺ / Y⁻
        self._canvas.create_text(min(ox + 4, W - 6), 10, text="Y+",
                                 fill=LABEL_FG, font=fnt, tags="grid", anchor="w")
        self._canvas.create_text(min(ox + 4, W - 6), H - 8, text="Y−",
                                 fill=GRID_AXIS, font=fnt, tags="grid", anchor="w")

    # ── Dibujo de figuras ─────────────────────────────────────────────────────

    def _to_canvas(self, x: int, y: int) -> tuple:
        """Convierte coordenadas lógicas a píxeles del canvas (con zoom y pan)."""
        eff = GRID * self._scale
        return self._ox + x * eff, self._oy - y * eff

    @staticmethod
    def _rotate_pts(pts: List[float], cx: float, cy: float, deg: float) -> List[float]:
        """Rota una lista plana [x0,y0,x1,y1,...] alrededor de (cx,cy)."""
        if deg == 0:
            return pts
        rad = math.radians(deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        out: List[float] = []
        for i in range(0, len(pts), 2):
            dx, dy = pts[i] - cx, pts[i + 1] - cy
            out.append(cx + dx * cos_a - dy * sin_a)
            out.append(cy + dx * sin_a + dy * cos_a)
        return out

    def _dibujar(self, e: EntradaFigura) -> None:
        # Los grupos son entidades lógicas; no tienen representación visual propia
        if e.tipo == "group":
            return
        cx, cy  = self._to_canvas(*e.posicion)
        sz      = max(e.escala * UNIT * self._scale, 4)
        outline = OUTLINE_DEF
        items: List[int] = []

        if e.visible:
            # Figura visible: relleno sólido
            fill = _parse_color(e.color, e.tipo)
            kw   = dict(fill=fill, outline=outline, width=2)
            dash = None
        else:
            # Figura oculta: sin relleno, contorno punteado tenue
            fill = ""
            kw   = dict(fill="", outline="#acb0be", width=1)
            dash = (4, 4)

        if e.tipo == "circle":
            iid = self._canvas.create_oval(
                cx - sz, cy - sz, cx + sz, cy + sz, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "square":
            pts = self._rotate_pts(
                [cx - sz, cy - sz, cx + sz, cy - sz,
                 cx + sz, cy + sz, cx - sz, cy + sz],
                cx, cy, e.rotacion,
            )
            iid = self._canvas.create_polygon(pts, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "triangle":
            pts = self._rotate_pts(
                [cx, cy - sz, cx - sz, cy + sz, cx + sz, cy + sz],
                cx, cy, e.rotacion,
            )
            iid = self._canvas.create_polygon(pts, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "line":
            color_linea = _parse_color(e.color, e.tipo) if e.visible else "#acb0be"
            kw_line = dict(fill=color_linea, width=max(1, e.escala * 2 * self._scale))
            if dash:
                kw_line["dash"] = dash
            cx2, cy2 = self._to_canvas(*e.pos_fin)
            mx, my   = (cx + cx2) / 2, (cy + cy2) / 2
            x1r, y1r, x2r, y2r = self._rotate_pts(
                [cx, cy, cx2, cy2], mx, my, e.rotacion)
            items.append(self._canvas.create_line(x1r, y1r, x2r, y2r, **kw_line))

        elif e.tipo == "pentagon":
            raw: List[float] = []
            for i in range(5):
                a = math.radians(-90 + i * 72)
                raw += [cx + sz * math.cos(a), cy + sz * math.sin(a)]
            pts = self._rotate_pts(raw, cx, cy, e.rotacion)
            iid = self._canvas.create_polygon(pts, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "rectangle":
            # sz usa escala (ancho); param_extra guarda el alto
            w_px = max(e.escala * UNIT * self._scale, 4)
            h_px = max((e.param_extra or e.escala) * UNIT * self._scale, 4)
            pts = self._rotate_pts(
                [cx - w_px, cy - h_px, cx + w_px, cy - h_px,
                 cx + w_px, cy + h_px, cx - w_px, cy + h_px],
                cx, cy, e.rotacion,
            )
            iid = self._canvas.create_polygon(pts, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "ellipse":
            # escala = rx (radio horizontal), param_extra = ry (radio vertical)
            rx_px = max(e.escala * UNIT * self._scale, 4)
            ry_px = max((e.param_extra or e.escala) * UNIT * self._scale, 4)
            # Aproximar la elipse con un polígono de 36 puntos para soportar rotación
            raw_ellipse: List[float] = []
            for i in range(36):
                a = math.radians(i * 10)
                raw_ellipse += [cx + rx_px * math.cos(a), cy + ry_px * math.sin(a)]
            pts = self._rotate_pts(raw_ellipse, cx, cy, e.rotacion)
            iid = self._canvas.create_polygon(pts, smooth=True, **kw)
            if dash:
                self._canvas.itemconfig(iid, dash=dash)
            items.append(iid)

        elif e.tipo == "text":
            font_size = max(8, int(e.escala * 2 * self._scale))
            text_color = _parse_color(e.color, e.tipo) if e.visible else "#acb0be"
            contenido = (e.contenido or '"texto"').strip('"')
            iid = self._canvas.create_text(
                cx, cy,
                text=contenido,
                fill=text_color,
                font=("Consolas", font_size, "bold"),
                anchor="center",
            )
            items.append(iid)

        # Etiqueta con el id de la figura
        if e.tipo == "line":
            cx2, cy2 = self._to_canvas(*e.pos_fin)
            lbl_x = (cx + cx2) // 2
            lbl_y = (cy + cy2) // 2 - 10
        else:
            lbl_x = cx
            lbl_y = cy + sz + 14
        items.append(self._canvas.create_text(
            lbl_x, lbl_y,
            text=e.id,
            fill=LABEL_FG,
            font=("Consolas", 8, "bold"),
        ))

        # Pequeño punto en el origen de la figura
        items.append(self._canvas.create_oval(
            cx - 2, cy - 2, cx + 2, cy + 2,
            fill=OUTLINE_DEF, outline="",
        ))

        self._items[e.id] = items

    # ═══════════════════════════════════════════════════════════════════════════
    # CONSOLA INTEGRADA
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_console(self, parent: tk.Frame) -> None:
        """Construye la consola de salida (ScrolledText) + Entry de entrada."""
        from tkinter.scrolledtext import ScrolledText

        # Título del panel
        tk.Label(
            parent, text=" CONSOLA",
            bg="#e6e9ef", fg="#9ca0b0",
            font=("Consolas", 9, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=4, pady=(4, 0))
        tk.Frame(parent, bg="#dce0e8", height=1).pack(fill=tk.X)

        # ── Área de salida (crece verticalmente) ──────────────────────────────
        self._console = ScrolledText(
            parent,
            wrap=tk.WORD,
            bg="#ffffff",
            fg="#4c4f69",
            insertbackground="#4c4f69",
            font=("Consolas", 10),
            state="disabled",
            relief=tk.FLAT,
            highlightthickness=0,
            selectbackground="#ccd0da",
        )
        self._console.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Tags de colores para la consola
        self._console.tag_config("cmd",   foreground="#1e66f5",  font=("Consolas", 10, "bold"))
        self._console.tag_config("ok",    foreground="#40a02b")
        self._console.tag_config("error", foreground="#d20f39")
        self._console.tag_config("warn",  foreground="#df8e1d")
        self._console.tag_config("sug",   foreground="#209fb5")
        self._console.tag_config("ptr",   foreground="#df8e1d",  font=("Consolas", 10, "bold"))
        self._console.tag_config("info",  foreground="#9ca0b0")

        # ── Fila de entrada ───────────────────────────────────────────────────
        entry_row = tk.Frame(parent, bg="#e6e9ef")
        entry_row.pack(fill=tk.X, padx=0, pady=(1, 0))

        tk.Label(
            entry_row, text=">>>",
            bg="#e6e9ef", fg="#9ca0b0",
            font=("Consolas", 11, "bold"),
            padx=8,
        ).pack(side=tk.LEFT)

        self._entry = tk.Entry(
            entry_row,
            bg="#ffffff", fg="#4c4f69",
            insertbackground="#4c4f69",
            font=("Consolas", 11),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#dce0e8",
            highlightcolor="#1e66f5",
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=4)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>",     self._on_history_up)
        self._entry.bind("<Down>",   self._on_history_down)
        self._entry.focus_force()

    def write_console(self, text: str, tag: str = "") -> None:
        """Escribe una línea en la consola de salida."""
        self._console.configure(state=tk.NORMAL)
        if tag:
            self._console.insert(tk.END, text + "\n", tag)
        else:
            self._console.insert(tk.END, text + "\n")
        self._console.see(tk.END)
        self._console.configure(state=tk.DISABLED)

    def set_command_callback(self, fn) -> None:
        """Registra la función que se llama al presionar Enter en la consola."""
        self._cmd_callback = fn

    def _on_history_up(self, event=None) -> str:
        """Sube en el historial (comando más reciente primero)."""
        if not self._history:
            return "break"
        if self._hist_idx < len(self._history) - 1:
            self._hist_idx += 1
        self._set_entry(self._history[self._hist_idx])
        return "break"

    def _on_history_down(self, event=None) -> str:
        """Baja en el historial; llega a vacío al pasar del más reciente."""
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self._set_entry("")
        else:
            self._hist_idx -= 1
            self._set_entry(self._history[self._hist_idx])
        return "break"

    def _set_entry(self, text: str) -> None:
        """Reemplaza el contenido del Entry y mueve el cursor al final."""
        self._entry.delete(0, tk.END)
        self._entry.insert(0, text)
        self._entry.icursor(tk.END)

    def _on_enter(self, event=None) -> None:
        """Procesa la línea al presionar Enter; devuelve el foco al Entry."""
        try:
            cmd = self._entry.get().strip()
            if not cmd:
                return
            self._entry.delete(0, tk.END)
            # Guardar en historial (máx 5, sin duplicados consecutivos)
            if not self._history or self._history[0] != cmd:
                self._history.insert(0, cmd)
                if len(self._history) > 10:
                    self._history.pop()
            self._hist_idx = -1
            if self._cmd_callback:
                self._cmd_callback(cmd)
        except Exception as e:
            self.write_console(f"ERROR INTERNO: {e}", "error")
        finally:
            self._entry.focus_force()

    # ═══════════════════════════════════════════════════════════════════════════
    # ZOOM Y PAN
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_zoom(self, event: tk.Event) -> None:
        """Zoom centrado en el punto del ratón (rueda del ratón)."""
        if event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.9
        else:
            factor = 1.1
        mx, my = event.x, event.y
        eff = GRID * self._scale
        if eff == 0:
            return
        # Punto lógico bajo el cursor (antes de escalar)
        lx = (mx - self._ox) / eff
        ly = -(my - self._oy) / eff
        # Actualizar escala con límites
        self._scale = max(0.15, min(8.0, self._scale * factor))
        new_eff = GRID * self._scale
        # Reajustar origen para que lx,ly permanezca bajo el cursor
        self._ox = int(mx - lx * new_eff)
        self._oy = int(my + ly * new_eff)
        self._canvas.delete("grid")
        self._draw_grid()
        if self._current_tabla:
            self.actualizar(self._current_tabla)

    def _on_pan_start(self, event: tk.Event) -> None:
        """Inicia el pan al presionar el botón central."""
        self._pan_start_pt = (event.x, event.y)

    def _on_pan_move(self, event: tk.Event) -> None:
        """Desplaza el origen mientras se arrastra con el botón central."""
        if self._pan_start_pt is None:
            return
        dx = event.x - self._pan_start_pt[0]
        dy = event.y - self._pan_start_pt[1]
        self._ox += dx
        self._oy += dy
        self._pan_start_pt = (event.x, event.y)
        self._canvas.delete("grid")
        self._draw_grid()
        if self._current_tabla:
            self.actualizar(self._current_tabla)

    def _reset_view(self) -> None:
        """Restaura zoom y pan a los valores por defecto."""
        self._scale = 1.0
        self._ox = 70
        self._oy = int(self._H * 0.6)
        self._canvas.delete("grid")
        self._draw_grid()
        if self._current_tabla:
            self.actualizar(self._current_tabla)

    # ═══════════════════════════════════════════════════════════════════════════
    # EXPORTAR SVG / PNG
    # ═══════════════════════════════════════════════════════════════════════════

    def _export_svg(self) -> None:
        """Exporta el canvas como archivo SVG."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG", "*.svg"), ("Todos los archivos", "*.*")],
            title="Exportar como SVG",
        )
        if not path:
            return
        try:
            svg = self._generate_svg()
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg)
            self.write_console(f"  OK: SVG exportado → {path}", "ok")
        except Exception as ex:
            self.write_console(f"  Error al exportar SVG: {ex}", "error")

    def _generate_svg(self) -> str:
        """Genera el contenido SVG a partir de la tabla de figuras actual."""
        W, H = max(400, self._W), max(300, self._H)
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
            f'  <rect width="{W}" height="{H}" fill="{BG}"/>',
        ]
        figuras = []
        if self._current_tabla:
            figuras = [e for e in self._current_tabla.listar()
                       if not e.eliminada and e.tipo != "group"]
        for e in figuras:
            cx, cy = self._to_canvas(*e.posicion)
            fill   = _parse_color(e.color, e.tipo) if e.visible else "none"
            stroke = OUTLINE_DEF
            sz     = max(e.escala * UNIT * self._scale, 4)
            if e.tipo == "circle":
                lines.append(
                    f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{sz:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "square":
                lines.append(
                    f'  <rect x="{cx-sz:.1f}" y="{cy-sz:.1f}" '
                    f'width="{sz*2:.1f}" height="{sz*2:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "triangle":
                pts = (f"{cx:.1f},{cy-sz:.1f} "
                       f"{cx-sz:.1f},{cy+sz:.1f} "
                       f"{cx+sz:.1f},{cy+sz:.1f}")
                lines.append(
                    f'  <polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "pentagon":
                raw = []
                for i in range(5):
                    a = math.radians(-90 + i * 72)
                    raw.append(f"{cx + sz*math.cos(a):.1f},{cy + sz*math.sin(a):.1f}")
                lines.append(
                    f'  <polygon points="{" ".join(raw)}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "rectangle":
                w_px = max(e.escala * UNIT * self._scale, 4)
                h_px = max((e.param_extra or e.escala) * UNIT * self._scale, 4)
                lines.append(
                    f'  <rect x="{cx-w_px:.1f}" y="{cy-h_px:.1f}" '
                    f'width="{w_px*2:.1f}" height="{h_px*2:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "ellipse":
                rx = max(e.escala * UNIT * self._scale, 4)
                ry = max((e.param_extra or e.escala) * UNIT * self._scale, 4)
                lines.append(
                    f'  <ellipse cx="{cx:.1f}" cy="{cy:.1f}" '
                    f'rx="{rx:.1f}" ry="{ry:.1f}" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
            elif e.tipo == "text":
                fs   = max(8, int(e.escala * 2 * self._scale))
                tc   = _parse_color(e.color, e.tipo) if e.visible else "#acb0be"
                cont = (e.contenido or '"texto"').strip('"')
                cont = cont.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                lines.append(
                    f'  <text x="{cx:.1f}" y="{cy:.1f}" fill="{tc}" '
                    f'font-size="{fs}" font-family="monospace" '
                    f'text-anchor="middle" dominant-baseline="middle">{cont}</text>')
            elif e.tipo == "line" and e.pos_fin:
                cx2, cy2 = self._to_canvas(*e.pos_fin)
                sc = _parse_color(e.color, e.tipo) if e.visible else "#acb0be"
                sw = max(1, e.escala * 2 * self._scale)
                lines.append(
                    f'  <line x1="{cx:.1f}" y1="{cy:.1f}" '
                    f'x2="{cx2:.1f}" y2="{cy2:.1f}" '
                    f'stroke="{sc}" stroke-width="{sw:.1f}"/>')
            # Etiqueta de ID
            if e.tipo != "line":
                lines.append(
                    f'  <text x="{cx:.1f}" y="{cy+sz+16:.1f}" fill="{LABEL_FG}" '
                    f'font-size="9" font-family="monospace" text-anchor="middle">{e.id}</text>')
        lines.append("</svg>")
        return "\n".join(lines)

    def _export_png(self) -> None:
        """Exporta el canvas como PNG (requiere Pillow: pip install Pillow)."""
        from tkinter import filedialog
        try:
            from PIL import ImageGrab
        except ImportError:
            self.write_console("  Para exportar PNG instala Pillow:  pip install Pillow", "warn")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("Todos los archivos", "*.*")],
            title="Exportar como PNG",
        )
        if not path:
            return
        try:
            self._root.update_idletasks()
            x = self._canvas.winfo_rootx()
            y = self._canvas.winfo_rooty()
            w = self._canvas.winfo_width()
            h = self._canvas.winfo_height()
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
            img.save(path)
            self.write_console(f"  OK: PNG exportado → {path}", "ok")
        except Exception as ex:
            self.write_console(f"  Error al exportar PNG: {ex}", "error")

    # ═══════════════════════════════════════════════════════════════════════════
    # PESTAÑA ABOUT — información del proyecto y el equipo
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_about_tab(self, parent: tk.Frame) -> None:
        """Construye la pestaña About con logos, créditos y descripción."""
        import os
        from tkinter import font as tkfont

        BG_ABOUT  = STATUS_BG
        FG_TITLE  = "#1e66f5"
        FG_HEAD   = "#4c4f69"
        FG_SUB    = "#6c6f85"
        FG_DESC   = "#4c4f69"

        # ── Canvas con scrollbar vertical ────────────────────────────────────
        outer = tk.Frame(parent, bg=BG_ABOUT)
        outer.pack(fill=tk.BOTH, expand=True)

        vscroll = tk.Scrollbar(outer, orient=tk.VERTICAL)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        cv = tk.Canvas(outer, bg=BG_ABOUT, highlightthickness=0,
                       yscrollcommand=vscroll.set)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.config(command=cv.yview)

        inner = tk.Frame(cv, bg=BG_ABOUT)
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(event):
            cv.configure(scrollregion=cv.bbox("all"))

        def _on_canvas_configure(event):
            cv.itemconfig(win_id, width=event.width)

        inner.bind("<Configure>", _on_frame_configure)
        cv.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event):
            cv.yview_scroll(int(-1 * (event.delta / 120)), "units")

        cv.bind_all("<MouseWheel>", _on_mousewheel)

        # ── Fila de logos ─────────────────────────────────────────────────────
        logos_row = tk.Frame(inner, bg=BG_ABOUT)
        logos_row.pack(pady=(30, 10))

        base_dir = os.path.join(os.path.dirname(__file__), "img")

        self._about_imgs: list = []   # keep references alive

        for filename, label_text in [
            ("logo_itc.png", "Tecnológico Nacional de México\nCampus Celaya"),
            ("yo.jpeg",      "Galindo López Uriel Emiliano"),
        ]:
            img_path = os.path.join(base_dir, filename)
            col_frame = tk.Frame(logos_row, bg=BG_ABOUT)
            col_frame.pack(side=tk.LEFT, padx=40)

            try:
                from PIL import Image, ImageTk
                pil_img = Image.open(img_path)
                pil_img.thumbnail((140, 140), Image.LANCZOS)
                tk_img  = ImageTk.PhotoImage(pil_img)
                self._about_imgs.append(tk_img)
                img_label = tk.Label(col_frame, image=tk_img, bg=BG_ABOUT,
                                     relief=tk.FLAT, bd=0)
                img_label.pack()
            except Exception:
                # Fallback sin Pillow: usar PhotoImage nativo (solo PNG)
                try:
                    tk_img = tk.PhotoImage(file=img_path)
                    # Reducir si es demasiado grande (subsample)
                    w_px, h_px = tk_img.width(), tk_img.height()
                    factor = max(1, max(w_px, h_px) // 140)
                    if factor > 1:
                        tk_img = tk_img.subsample(factor, factor)
                    self._about_imgs.append(tk_img)
                    img_label = tk.Label(col_frame, image=tk_img, bg=BG_ABOUT,
                                         relief=tk.FLAT, bd=0)
                    img_label.pack()
                except Exception:
                    tk.Label(col_frame, text="[ imagen no disponible ]",
                             bg=BG_ABOUT, fg=FG_SUB,
                             font=("Consolas", 9, "italic")).pack()

            tk.Label(col_frame, text=label_text,
                     bg=BG_ABOUT, fg=FG_SUB,
                     font=("Consolas", 9), justify=tk.CENTER).pack(pady=(6, 0))

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(inner, bg="#dce0e8", height=2).pack(fill=tk.X, padx=40, pady=(16, 0))

        # ── Títulos de materia e información académica ────────────────────────
        info_frame = tk.Frame(inner, bg=BG_ABOUT)
        info_frame.pack(pady=(14, 0))

        tk.Label(info_frame,
                 text="Lenguajes y Autómatas II",
                 bg=BG_ABOUT, fg=FG_TITLE,
                 font=("Consolas", 17, "bold")).pack()

        tk.Label(info_frame,
                 text="Tecnológico Nacional de México  ·  Campus Celaya",
                 bg=BG_ABOUT, fg=FG_SUB,
                 font=("Consolas", 10)).pack(pady=(2, 10))

        for lbl, val in [
            ("Profesor :", "ISC. Ricardo González González"),
            ("Alumno   :", "21030060  ·  Galindo López Uriel Emiliano"),
        ]:
            row = tk.Frame(info_frame, bg=BG_ABOUT)
            row.pack(anchor="w", padx=20, pady=2)
            tk.Label(row, text=lbl,
                     bg=BG_ABOUT, fg=FG_SUB,
                     font=("Consolas", 11, "bold"), width=12,
                     anchor="e").pack(side=tk.LEFT)
            tk.Label(row, text=f"  {val}",
                     bg=BG_ABOUT, fg=FG_HEAD,
                     font=("Consolas", 11)).pack(side=tk.LEFT)

        # ── Separador ─────────────────────────────────────────────────────────
        tk.Frame(inner, bg="#dce0e8", height=2).pack(fill=tk.X, padx=40, pady=(18, 0))

        # ── Descripción del proyecto ──────────────────────────────────────────
        desc_frame = tk.Frame(inner, bg=BG_ABOUT)
        desc_frame.pack(fill=tk.X, padx=50, pady=(16, 30))

        tk.Label(desc_frame,
                 text="Acerca del Proyecto",
                 bg=BG_ABOUT, fg=FG_TITLE,
                 font=("Consolas", 13, "bold"),
                 anchor="w").pack(fill=tk.X, pady=(0, 8))

        descripcion = (
            "Este proyecto consiste en el desarrollo de un intérprete interactivo para\n"
            "un lenguaje de dominio específico (DSL) orientado a la creación y manipulación\n"
            "de figuras geométricas sobre un canvas virtual.\n\n"
            "El intérprete implementa las fases clásicas de un compilador:\n"
            "  · Análisis léxico    — tokenización del texto de entrada.\n"
            "  · Análisis sintáctico — validación de la gramática mediante un parser\n"
            "                          descendente recursivo.\n"
            "  · Análisis semántico  — verificación de tipos, existencia de identificadores\n"
            "                          y coherencia de parámetros.\n"
            "  · Ejecución           — aplicación de los cambios sobre la tabla de símbolos\n"
            "                          y re-renderizado inmediato en el canvas.\n\n"
            "Propósito: aplicar los conceptos de autómatas finitos, expresiones regulares,\n"
            "gramáticas formales y análisis semántico en un sistema funcional que permite\n"
            "explorar visualmente el resultado de cada instrucción en tiempo real."
        )

        tk.Label(desc_frame,
                 text=descripcion,
                 bg=BG_ABOUT, fg=FG_DESC,
                 font=("Consolas", 10),
                 justify=tk.LEFT,
                 anchor="nw",
                 wraplength=0).pack(fill=tk.X)

    # ═══════════════════════════════════════════════════════════════════════════
    # PESTAÑA DOCS — documentación completa del proyecto (README)
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_docs_tab(self, parent: tk.Frame) -> None:
        """Renderiza el contenido del README.md con formato visual en un Text widget."""
        import os

        # ── Contenedor con scrollbars ────────────────────────────────────────
        outer = tk.Frame(parent, bg=STATUS_BG)
        outer.pack(fill=tk.BOTH, expand=True)

        vscroll = tk.Scrollbar(outer, orient=tk.VERTICAL)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        hscroll = tk.Scrollbar(outer, orient=tk.HORIZONTAL)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)

        txt = tk.Text(
            outer,
            bg="#ffffff",
            fg=LABEL_FG,
            font=("Consolas", 10),
            wrap=tk.NONE,
            state=tk.DISABLED,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=18,
            pady=12,
            yscrollcommand=vscroll.set,
            xscrollcommand=hscroll.set,
            cursor="arrow",
        )
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.config(command=txt.yview)
        hscroll.config(command=txt.xview)

        # ── Scroll con rueda del ratón ────────────────────────────────────────
        def _mw(e):
            txt.yview_scroll(int(-1 * (e.delta / 120)), "units")
        txt.bind("<MouseWheel>", _mw)

        # ── Tags de formato ───────────────────────────────────────────────────
        txt.tag_config("h1",      foreground="#1e66f5", font=("Consolas", 16, "bold"))
        txt.tag_config("h2",      foreground="#1e66f5", font=("Consolas", 13, "bold"))
        txt.tag_config("h3",      foreground="#8839ef", font=("Consolas", 11, "bold"))
        txt.tag_config("h4",      foreground="#8839ef", font=("Consolas", 10, "bold"))
        txt.tag_config("code",    foreground="#d20f39", background="#f0f0f0",
                       font=("Consolas", 10))
        txt.tag_config("block",   foreground="#4c4f69", background="#f5f5f5",
                       font=("Consolas", 9), lmargin1=32, lmargin2=32)
        txt.tag_config("sep",     foreground="#dce0e8")
        txt.tag_config("th",      foreground="#6c6f85", font=("Consolas", 10, "italic"))
        txt.tag_config("td",      foreground=LABEL_FG, font=("Consolas", 10))
        txt.tag_config("bullet",  foreground="#209fb5", font=("Consolas", 10))
        txt.tag_config("normal",  foreground=LABEL_FG, font=("Consolas", 10))
        txt.tag_config("bold",    foreground=LABEL_FG, font=("Consolas", 10, "bold"))
        txt.tag_config("toclink", foreground="#1e66f5", font=("Consolas", 10))

        # ── Leer README.md ───────────────────────────────────────────────────
        readme_path = os.path.join(os.path.dirname(__file__), "README.md")
        try:
            with open(readme_path, encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            txt.configure(state=tk.NORMAL)
            txt.insert(tk.END, "  No se encontró README.md\n", "h3")
            txt.configure(state=tk.DISABLED)
            return

        # ── Renderizador ─────────────────────────────────────────────────────
        def _strip_inline(text: str) -> str:
            """Elimina los backticks de inline code para inserción simple."""
            return text.replace("`", "")

        def _ins(text, tag="normal"):
            txt.configure(state=tk.NORMAL)
            txt.insert(tk.END, text, tag)
            txt.configure(state=tk.DISABLED)

        in_code_block = False
        i = 0
        while i < len(lines):
            raw = lines[i].rstrip("\n")

            # Bloques de código (```)
            if raw.strip().startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    _ins("\n", "normal")
                else:
                    _ins("\n", "normal")
                i += 1
                continue

            if in_code_block:
                _ins(raw + "\n", "block")
                i += 1
                continue

            # Líneas horizontales
            if raw.strip().startswith("---"):
                _ins("─" * 90 + "\n", "sep")
                i += 1
                continue

            # Encabezados
            if raw.startswith("#### "):
                _ins(raw[5:] + "\n", "h4")
                i += 1
                continue
            if raw.startswith("### "):
                _ins("\n" + raw[4:] + "\n", "h3")
                i += 1
                continue
            if raw.startswith("## "):
                _ins("\n" + raw[3:] + "\n", "h2")
                i += 1
                continue
            if raw.startswith("# "):
                _ins(raw[2:] + "\n\n", "h1")
                i += 1
                continue

            # Tabla Markdown (línea que empieza con |)
            if raw.strip().startswith("|"):
                cells = [c.strip() for c in raw.strip().strip("|").split("|")]
                # Detectar si es línea separadora de tabla (|---|---|)
                if all(set(c.replace("-","").replace(":","").replace(" ","")) == set()
                       for c in cells if c):
                    i += 1
                    continue
                # Encabezado o fila de datos
                is_header = (i == 0 or not lines[i-1].strip().startswith("|"))
                row_tag = "th" if is_header else "td"
                line_out = "  " + "  │  ".join(f"{c:<28}" for c in cells) + "\n"
                _ins(line_out, row_tag)
                i += 1
                continue

            # Viñetas  -  /  *
            if raw.strip().startswith(("- ", "* ", "+ ")):
                indent = len(raw) - len(raw.lstrip())
                pad = " " * indent
                content = raw.strip()[2:]
                _ins(f"{pad}  · ", "bullet")
                _ins(_strip_inline(content) + "\n", "normal")
                i += 1
                continue

            # Línea vacía
            if raw.strip() == "":
                _ins("\n", "normal")
                i += 1
                continue

            # Texto normal (con inline code `...` resaltado)
            _ins(_strip_inline(raw) + "\n", "normal")
            i += 1

        # Scroll al inicio
        txt.configure(state=tk.NORMAL)
        txt.see("1.0")
        txt.configure(state=tk.DISABLED)
