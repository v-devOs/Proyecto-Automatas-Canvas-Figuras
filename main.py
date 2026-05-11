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
    ShowNode, HideNode, ClearNode,
)


# ══════════════════════════════════════════════════════════════════════════════
# EXECUTOR  —  toda la salida va a canvas_v.write_console()
# ══════════════════════════════════════════════════════════════════════════════

class Executor:
    def __init__(self, tabla: TablaSimbolos, write_fn=None) -> None:
        self._tabla = tabla
        self._write = write_fn or (lambda text, tag="": None)
        self._dispatch = {
            CreateNode: self._exec_create,
            UpdateNode: self._exec_update,
            DeleteNode: self._exec_delete,
            ShowNode:   self._exec_show,
            HideNode:   self._exec_hide,
            ListNode:   self._exec_list,
            ClearNode:  self._exec_clear,
            HelpNode:   self._exec_help,
        }

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
            self._write(f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})", "ok")

    def _exec_update(self, nodo: UpdateNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e:
            self._write(f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})", "ok")

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
        self._write(f"  {'ID':<16} {'TIPO':<10} {'COLOR':<10} {'ESC':<4} {'POS':<12} VIS", "info")
        for e in figs:
            self._write(
                f"  {e.id:<16} {e.tipo:<10} {e.color:<10} {e.escala:<4} "
                f"{str(list(e.posicion)):<12} {'si' if e.visible else 'no'}",
                "ok" if e.visible else "warn",
            )

    def _exec_clear(self, _) -> None:
        self._write("  OK: tabla vaciada", "ok")

    def _exec_help(self, _) -> None:
        for ln in [
            "  Comandos disponibles:",
            "    create <tipo>                      crea figura con valores por defecto",
            "    create <tipo>(color,escala,[x,y])  crea con parámetros",
            "    update <id>(_|color,_|esc,_|pos)   modifica uno o más campos",
            "    delete <id>    elimina figura",
            "    show   <id>    hace visible         hide <id>    oculta",
            "    list           lista figuras         clear screen  vacía",
            "    help           esta ayuda            exit / quit   salir",
            "  Tipos: circle  square  triangle  line  pentagon",
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
        p   = Parser(tokens)
        ast = p.parse()
        _, sem_errs = AnalizadorSemantico(tabla).analizar(ast)

        todos = lex_errs + p.errores + sem_errs

        if todos:
            for err in todos:
                _write_error(canvas_v, linea, err)
            primer = todos[0]
            nivel  = "warn" if isinstance(primer, ErrorSemantico) else "error"
            canvas_v.actualizar(tabla)
            canvas_v.set_status(str(primer), nivel)
            canvas_v.log_comando(linea, [], tabla, error=str(primer), nivel=nivel)
        else:
            executor.ejecutar(ast)
            toks_log = [t for t in tokens if t.tipo.value != "EOF"]
            canvas_v.actualizar(tabla)
            canvas_v.set_status(f"OK  {linea}", "ok")
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
