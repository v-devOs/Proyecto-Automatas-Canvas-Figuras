"""
main.py - Intérprete interactivo, Lenguaje de Figuras Geométricas.
Consola integrada en tkinter — hilo único, sin threading.
"""
from __future__ import annotations
import tkinter as tk

from lexer          import ErrorLexico,     tokenizar
from parser         import ErrorSintactico, Parser
from semantico      import ErrorSemantico,  AnalizadorSemantico
from tabla_simbolos import TablaSimbolos
from canvas_view    import CanvasView
from ast_nodes      import (
    ProgramaNode, ListNode, HelpNode,
    CreateNode, UpdateNode, DeleteNode,
    ShowNode, HideNode, ClearNode, RotateNode,
    MoveNode, CopyNode, GroupNode, UngroupNode, ScaleNode, SetNode,
)


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTOR  —  toda la salida va a canvas_v.write_console()
# ══════════════════════════════════════════════════════════════════════════════

class Executor:
    def __init__(self, tabla: TablaSimbolos, write_fn=None) -> None:
        self._tabla     = tabla
        self._write     = write_fn or (lambda text, tag="": None)
        self._variables: dict = {}   # nombre → int; compartido con el parser
        self._dispatch = {
            CreateNode:  self._exec_create,
            UpdateNode:  self._exec_update,
            DeleteNode:  self._exec_delete,
            ShowNode:    self._exec_show,
            HideNode:    self._exec_hide,
            ListNode:    self._exec_list,
            ClearNode:   self._exec_clear,
            HelpNode:    self._exec_help,
            RotateNode:  self._exec_rotate,
            MoveNode:    self._exec_move,
            CopyNode:    self._exec_copy,
            GroupNode:   self._exec_group,
            UngroupNode: self._exec_ungroup,
            ScaleNode:   self._exec_scale,
            SetNode:     self._exec_set,
        }

    @property
    def variables(self) -> dict:
        return self._variables

    def ejecutar(self, programa: ProgramaNode) -> None:
        for nodo in programa.comandos:
            fn = self._dispatch.get(type(nodo))
            if fn:
                fn(nodo)

    def _exec_create(self, nodo: CreateNode) -> None:
        tipo = nodo.tipo_figura
        figs = [e for e in self._tabla.listar() if e.tipo == tipo and not e.eliminada]
        if figs:
            e = figs[-1]
            if e.pos_fin is not None:
                self._write(
                    f"  OK: {e.id}  (color={e.color}, grosor={e.escala}, "
                    f"inicio={list(e.posicion)}, fin={list(e.pos_fin)})", "ok")
            elif e.tipo == "rectangle":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, ancho={e.escala}, "
                    f"alto={e.param_extra}, pos={list(e.posicion)})", "ok")
            elif e.tipo == "ellipse":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, rx={e.escala}, "
                    f"ry={e.param_extra}, pos={list(e.posicion)})", "ok")
            elif e.tipo == "text":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, tamaño={e.escala}, "
                    f"pos={list(e.posicion)}, texto={e.contenido})", "ok")
            else:
                self._write(
                    f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})", "ok")

    def _exec_update(self, nodo: UpdateNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e:
            if e.pos_fin is not None:
                self._write(
                    f"  OK: {e.id}  (color={e.color}, grosor={e.escala}, "
                    f"inicio={list(e.posicion)}, fin={list(e.pos_fin)})", "ok")
            elif e.tipo == "rectangle":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, ancho={e.escala}, "
                    f"alto={e.param_extra}, pos={list(e.posicion)})", "ok")
            elif e.tipo == "ellipse":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, rx={e.escala}, "
                    f"ry={e.param_extra}, pos={list(e.posicion)})", "ok")
            elif e.tipo == "text":
                self._write(
                    f"  OK: {e.id}  (color={e.color}, tamaño={e.escala}, "
                    f"pos={list(e.posicion)}, texto={e.contenido})", "ok")
            else:
                self._write(
                    f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})", "ok")

    def _exec_delete(self, nodo: DeleteNode) -> None:
        self._write(f"  OK: {nodo.id} eliminado", "ok")

    def _exec_show(self, nodo: ShowNode) -> None:
        self._write(f"  OK: {nodo.id} visible", "ok")

    def _exec_hide(self, nodo: HideNode) -> None:
        self._write(f"  OK: {nodo.id} oculto", "ok")

    def _exec_list(self, _) -> None:
        figs = [e for e in self._tabla.listar() if not e.eliminada]
        if not figs:
            self._write("  (no hay figuras activas)", "info")
            return
        # ─ Figuras individuales ──────────────────────────────────────────────
        indiv = [e for e in figs if e.tipo != "group"]
        if indiv:
            self._write(
                f"  {'ID':<16} {'TIPO':<12} {'COLOR':<10} {'DIM':<12} {'POS / INICIO':<14} {'FIN/TEXTO':<14} {'ROT':<5} VIS", "info")
            for e in indiv:
                rot = f"{e.rotacion}°"
                if e.tipo == "rectangle":
                    dim  = f"{e.escala}×{e.param_extra}"
                    fin_col = "—"
                elif e.tipo == "ellipse":
                    dim  = f"rx={e.escala} ry={e.param_extra}"
                    fin_col = "—"
                elif e.tipo == "text":
                    dim  = f"sz={e.escala}"
                    fin_col = (e.contenido or "").strip('"')[:12]
                elif e.pos_fin is not None:
                    dim  = str(e.escala)
                    fin_col = str(list(e.pos_fin))
                else:
                    dim  = str(e.escala)
                    fin_col = "—"
                self._write(
                    f"  {e.id:<16} {e.tipo:<12} {e.color:<10} {dim:<12} "
                    f"{str(list(e.posicion)):<14} {fin_col:<14} {rot:<5} {'si' if e.visible else 'no'}",
                    "ok" if e.visible else "warn",
                )
        # ─ Grupos ──────────────────────────────────────────────────────────
        grupos = [e for e in figs if e.tipo == "group"]
        if grupos:
            self._write(f"  {'ID':<16} MIEMBROS", "info")
            for g in grupos:
                miembros = ", ".join(g.grupo_ids or [])
                self._write(f"  {g.id:<16} {miembros}", "ok")

    def _exec_clear(self, _) -> None:
        self._write("  OK: tabla vaciada", "ok")

    def _exec_rotate(self, nodo: RotateNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e and e.tipo == "group":
            miembros = ", ".join(e.grupo_ids or [])
            self._write(f"  OK: {nodo.id} → [{miembros}]  rotación +{nodo.grados}°", "ok")
        elif e:
            self._write(
                f"  OK: {e.id}  rotación={e.rotacion}°", "ok")

    def _exec_move(self, nodo: MoveNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e and e.tipo == "group":
            miembros = ", ".join(e.grupo_ids or [])
            self._write(
                f"  OK: {nodo.id} → [{miembros}]  movidos ({nodo.dx:+d}, {nodo.dy:+d})", "ok")
        elif e:
            if e.pos_fin is not None:
                self._write(
                    f"  OK: {e.id}  inicio={list(e.posicion)}  fin={list(e.pos_fin)}", "ok")
            else:
                self._write(
                    f"  OK: {e.id}  pos={list(e.posicion)}", "ok")

    def _exec_copy(self, nodo: CopyNode) -> None:
        tipo = self._tabla.obtener(nodo.id)
        if tipo is None:
            return
        # El semántico ya insertó la copia; buscamos la entrada más reciente del mismo tipo
        t = tipo.tipo
        copias = [e for e in self._tabla.listar() if e.tipo == t and not e.eliminada]
        if copias:
            nueva = copias[-1]
            self._write(
                f"  OK: {nueva.id}  (copia de {nodo.id})  pos={list(nueva.posicion)}", "ok")

    def _exec_group(self, nodo: GroupNode) -> None:
        grupos = [e for e in self._tabla.listar() if e.tipo == "group" and not e.eliminada]
        if grupos:
            g = grupos[-1]
            miembros = ", ".join(g.grupo_ids or [])
            self._write(f"  OK: {g.id}  →  [{miembros}]", "ok")

    def _exec_ungroup(self, nodo: UngroupNode) -> None:
        self._write(f"  OK: {nodo.id} disuelto (miembros conservados)", "ok")

    def _exec_scale(self, nodo: ScaleNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e and e.tipo == "group":
            miembros = ", ".join(e.grupo_ids or [])
            self._write(
                f"  OK: {nodo.id} → [{miembros}]  escala ×{nodo.factor}", "ok")
        elif e:
            self._write(
                f"  OK: {e.id}  escala={e.escala}", "ok")

    def _exec_set(self, nodo: SetNode) -> None:
        self._variables[nodo.nombre] = nodo.valor
        self._write(f"  OK: {nodo.nombre} = {nodo.valor}", "ok")

    def _exec_help(self, _) -> None:
        for ln in [
            "  Comandos disponibles:",
            "    create <tipo>                                    crea figura con valores por defecto",
            "    create <tipo>(color, escala, [x,y])              crea con parámetros",
            "    create line(color, grosor, [x1,y1], [x2,y2])    línea entre dos puntos",
            "    create rectangle(color, ancho, alto, [x,y])     rectángulo con dimensiones independientes",
            "    create ellipse(color, rx, ry, [x,y])            elipse con radio horizontal y vertical",
            '    create text(color, tamaño, [x,y], \"contenido\")  texto en el canvas',
            "    update <id>(_|color, _|esc, _|pos)               modifica uno o más campos",
            "    update <rect_id>(_|color, _|ancho, _|alto, _|pos)  modifica rectángulo",
            "    update <ellipse_id>(_|color, _|rx, _|ry, _|pos)   modifica elipse",
            '    update <text_id>(_|color, _|sz, _|pos, _|\"txt\")   modifica texto',
            "    move   <id> (dx, dy)                             desplaza figura o grupo",
            "    rotate <id> (grados)                             rota figura o grupo",
            "    scale  <id> (factor)                             escala ×factor figura o grupo",
            "    copy   <id>                                      duplica figura con nuevo ID",
            "    group  <id1> <id2> ...                           agrupa figuras",
            "    ungroup <gid>                                    disuelve el grupo",
            "    delete <id>    elimina figura o grupo",
            "    show   <id>    hace visible            hide <id>    oculta (cascada en grupos)",
            "    list           lista figuras y grupos   clear screen  vacía",
            "    help           esta ayuda               exit / quit   salir",
            "  Tipos: circle  square  triangle  line  pentagon  rectangle  ellipse  text",
        ]:
            self._write(ln, "info")


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY DE ERRORES EN LA CONSOLA TKINTER
# ══════════════════════════════════════════════════════════════════════════════

def _write_error(canvas_v: CanvasView, fuente: str, e: object) -> None:
    """Escribe un error con puntero visual y sugerencia en la consola integrada."""
    col     = getattr(e, "columna",    1)
    col_fin = getattr(e, "col_fin",    col)
    sug     = getattr(e, "sugerencia", "")

    if col > 0 and fuente.strip():
        n   = max(1, (col_fin or col) - col + 1)
        ptr = " " * (col - 1) + "^" * n
        canvas_v.write_console(f"  {fuente}", "info")
        canvas_v.write_console(f"  {ptr}", "ptr")

    nivel = "warn" if isinstance(e, ErrorSemantico) else "error"
    canvas_v.write_console(f"  {e}", nivel)
    if sug:
        canvas_v.write_console(f"  Sugerencia: {sug}", "sug")


# ══════════════════════════════════════════════════════════════════════════════
# PROCESADOR DE COMANDOS  (reemplaza el antiguo REPL en hilo separado)
# ══════════════════════════════════════════════════════════════════════════════

_SALIR = {"exit", "quit"}


def _proceso_comando(
    linea: str,
    tabla: TablaSimbolos,
    executor: Executor,
    canvas_v: CanvasView,
) -> None:
    """Corre en el hilo principal de tkinter; llama a lexer→parser→semántico→executor."""
    if linea.lower() in _SALIR:
        canvas_v.write_console("  hasta luego.", "info")
        canvas_v._root.after(300, canvas_v._root.destroy)
        return

    canvas_v.write_console(f"> {linea}", "cmd")

    try:
        tokens, lex_errs = tokenizar(linea)
        p   = Parser(tokens, variables=executor.variables)
        ast = p.parse()
        _, sem_errs = AnalizadorSemantico(tabla).analizar(ast)

        todos = lex_errs + p.errores + sem_errs

        if todos:
            for err in todos:
                _write_error(canvas_v, linea, err)
            primer = todos[0]
            nivel  = "warn" if isinstance(primer, ErrorSemantico) else "error"
            canvas_v.actualizar(tabla)
            canvas_v.log_comando(linea, [], tabla, error=str(primer), nivel=nivel)
        else:
            executor.ejecutar(ast)
            toks_log = [t for t in tokens if t.tipo.value != "EOF"]
            canvas_v.actualizar(tabla)
            canvas_v.log_comando(linea, toks_log, tabla)
            canvas_v.mostrar_ast(linea, ast)

    except Exception as exc:
        canvas_v.write_console(f"  ERROR INTERNO: {exc}", "error")
        canvas_v.set_status(f"ERROR INTERNO: {exc}", "error")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRADA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tabla    = TablaSimbolos()
    root     = tk.Tk()
    canvas_v = CanvasView(root)
    executor = Executor(tabla, write_fn=canvas_v.write_console)

    canvas_v.set_command_callback(
        lambda linea: _proceso_comando(linea, tabla, executor, canvas_v)
    )

    canvas_v.write_console("  Intérprete de Figuras Geométricas", "info")
    canvas_v.write_console("  Escribe  help  para ver los comandos.   exit  para salir.", "info")
    canvas_v.write_console("", "")

    root.mainloop()
