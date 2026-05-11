"""
main.py - Interprete interactivo, Lenguaje de Figuras Geometricas
Consola nativa Python (threading) + canvas tkinter (hilo principal).
"""
from __future__ import annotations
import sys
import threading
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


class Executor:
    def __init__(self, tabla: TablaSimbolos) -> None:
        self._tabla = tabla
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
            print(f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})")

    def _exec_update(self, nodo: UpdateNode) -> None:
        e = self._tabla.obtener(nodo.id)
        if e:
            print(f"  OK: {e.id}  (color={e.color}, escala={e.escala}, pos={list(e.posicion)})")

    def _exec_delete(self, nodo: DeleteNode) -> None:
        print(f"  OK: {nodo.id} eliminado")

    def _exec_show(self, nodo: ShowNode) -> None:
        print(f"  OK: {nodo.id} visible")

    def _exec_hide(self, nodo: HideNode) -> None:
        print(f"  OK: {nodo.id} oculto")

    def _exec_list(self, _) -> None:
        figs = [e for e in self._tabla.listar() if not e.eliminada]
        if not figs:
            print("  (no hay figuras activas)")
            return
        print(f"  {'ID':<16} {'TIPO':<10} {'COLOR':<10} {'ESC':<4} {'POS':<12} VIS")
        for e in figs:
            print(f"  {e.id:<16} {e.tipo:<10} {e.color:<10} {e.escala:<4} {str(list(e.posicion)):<12} {'si' if e.visible else 'no'}")

    def _exec_clear(self, _) -> None:
        print("  OK: tabla vaciada")

    def _exec_help(self, _) -> None:
        print("""
  Comandos:
    create <tipo>                     crea figura
    create <tipo>(color,escala,[x,y]) crea con parametros
    update <id>(_|color,_|esc,_|pos)  actualiza campos
    delete <id>    elimina       show <id>  visible
    hide   <id>    oculta        list       listar todas
    clear screen   vaciar        help       esta ayuda
    exit / quit    salir
  Tipos: circle  square  triangle  line  pentagon
""")


_SALIR = {"exit", "quit"}

def _repl(tabla, executor, canvas, root):
    print("\n  Interprete de Figuras Geometricas")
    print("  Escribe  help  para ver los comandos.  exit  para salir.\n")
    while True:
        try:
            linea = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            root.after(0, root.destroy)
            break
        if not linea:
            continue
        if linea.lower() in _SALIR:
            print("  hasta luego.")
            root.after(0, root.destroy)
            break
        try:
            tokens = tokenizar(linea)
            ast    = Parser(tokens).parse()
            AnalizadorSemantico(tabla).analizar(ast)
            executor.ejecutar(ast)
            toks_log = [t for t in tokens if t.tipo.value != "EOF"]
            root.after(0, lambda l=linea, tl=toks_log, a=ast: (
                canvas.actualizar(tabla),
                canvas.set_status(f"OK  {l}", "ok"),
                canvas.log_comando(l, tl, tabla),
                canvas.mostrar_ast(l, a),
            ))
        except ErrorLexico as e:
            print(f"  ERROR LEXICO:     {e}")
            root.after(0, lambda m=str(e), l=linea: (
                canvas.set_status(m, "error"),
                canvas.log_comando(l, [], tabla, error=m, nivel="error"),
            ))
        except ErrorSintactico as e:
            print(f"  ERROR SINTACTICO: {e}")
            root.after(0, lambda m=str(e), l=linea: (
                canvas.set_status(m, "error"),
                canvas.log_comando(l, [], tabla, error=m, nivel="error"),
            ))
        except ErrorSemantico as e:
            print(f"  ERROR SEMANTICO:  {e}")
            root.after(0, lambda m=str(e), l=linea: (
                canvas.set_status(m, "warn"),
                canvas.log_comando(l, [], tabla, error=m, nivel="warn"),
            ))


if __name__ == "__main__":
    tabla    = TablaSimbolos()
    root     = tk.Tk()
    canvas_v = CanvasView(root)
    executor = Executor(tabla)
    threading.Thread(target=_repl, args=(tabla, executor, canvas_v, root), daemon=True).start()
    root.mainloop()
