"""
semantico.py — Analizador Semántico · Lenguaje de Figuras Geométricas

Recorre el AST validado por el parser y aplica las reglas semánticas.
NUNCA consume tokens directamente; opera exclusivamente sobre nodos AST.

Reglas implementadas:
  create  → M002 si el id ya existe (no eliminado)
             M004 si escala ≤ 0
  update  → M001 si la figura no existe
             M005 si la figura está eliminada
             M003 si el tipo del valor no corresponde al slot
             M004 si la nueva escala ≤ 0
  delete  → M001 si no existe / M005 si ya eliminada
  show    → M001 si no existe / M005 si eliminada
  hide    → M001 si no existe / M005 si eliminada
  list    → sin validación semántica
  clear   → vacía la tabla
  help    → sin validación semántica

Valores por defecto de create sin parámetros:
  color    = "white"
  escala   = 1
  posicion = (0, 0)
"""

from __future__ import annotations

from typing import List, Tuple

from ast_nodes import (
    ProgramaNode, ComandoNode,
    CreateNode, UpdateNode, DeleteNode,
    ShowNode, HideNode, ListNode, ClearNode, HelpNode,
    ParametrosUpdateNode, ValorUpdateNode,
)
from tabla_simbolos import EntradaFigura, TablaSimbolos


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR SEMÁNTICO
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorSemantico(Exception):
    """
    Códigos según especificación:
        M001  figura inexistente
        M002  identificador duplicado
        M003  tipo de valor inválido en slot de update
        M004  escala inválida  (≤ 0)
        M005  figura eliminada
    """
    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(f"[{codigo}] {mensaje}")
        self.codigo  = codigo
        self.mensaje = mensaje


# ═══════════════════════════════════════════════════════════════════════════════
# VALORES POR DEFECTO
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_COLOR:    str            = "white"
_DEFAULT_ESCALA:   int            = 1
_DEFAULT_POSICION: Tuple[int,int] = (0, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# ANALIZADOR SEMÁNTICO
# ═══════════════════════════════════════════════════════════════════════════════

class AnalizadorSemantico:
    """
    Recorre el ProgramaNode nodo a nodo.
    Cada método _check_* valida y actualiza la TablaSimbolos.
    Devuelve la tabla actualizada tras procesar el AST completo.
    """

    # Tabla de despacho: tipo de nodo → método validador
    # Se construye en __init__ para referenciar self.

    def __init__(self, tabla: TablaSimbolos) -> None:
        self._tabla = tabla
        self._dispatch = {
            CreateNode: self._check_create,
            UpdateNode: self._check_update,
            DeleteNode: self._check_delete,
            ShowNode:   self._check_show,
            HideNode:   self._check_hide,
            ListNode:   self._check_list,
            ClearNode:  self._check_clear,
            HelpNode:   self._check_help,
        }

    # ── API pública ───────────────────────────────────────────────────────────

    def analizar(self, programa: ProgramaNode) -> TablaSimbolos:
        """Procesa cada comando del AST; actualiza y devuelve la tabla."""
        for nodo in programa.comandos:
            fn = self._dispatch.get(type(nodo))
            if fn is None:
                raise AssertionError(f"Nodo no manejado: {type(nodo)}")
            fn(nodo)
        return self._tabla

    # ── create ────────────────────────────────────────────────────────────────

    def _check_create(self, nodo: CreateNode) -> None:
        # Generar ID automático
        nuevo_id = self._tabla.siguiente_id(nodo.tipo_figura)

        # M002: No debe existir ya una figura activa con ese id
        # (siguiente_id garantiza que el candidato no existe, pero si el usuario
        # fuerza un id concreto en el futuro, esta guarda aplica)
        entrada_previa = self._tabla.obtener(nuevo_id)
        if entrada_previa and not entrada_previa.eliminada:
            raise ErrorSemantico(
                "M002",
                f"identificador duplicado: {nuevo_id!r}",
            )

        # Resolver parámetros (con valores por defecto si no se proporcionaron)
        if nodo.parametros:
            color    = nodo.parametros.color
            escala   = nodo.parametros.escala
            posicion = (nodo.parametros.posicion.x, nodo.parametros.posicion.y)
        else:
            color    = _DEFAULT_COLOR
            escala   = _DEFAULT_ESCALA
            posicion = _DEFAULT_POSICION

        # M004: escala debe ser > 0
        self._validar_escala(escala)

        self._tabla.insertar(EntradaFigura(
            id       = nuevo_id,
            tipo     = nodo.tipo_figura,
            color    = color,
            escala   = escala,
            posicion = posicion,
        ))

    # ── update ────────────────────────────────────────────────────────────────

    def _check_update(self, nodo: UpdateNode) -> None:
        entrada = self._obtener_activa(nodo.id)  # M001 / M005

        params = nodo.parametros

        # M003: validar que cada slot tenga el tipo correcto o sea wildcard
        self._validar_slot(params.color,    esperado="color",    slot=1)
        self._validar_slot(params.escala,   esperado="escala",   slot=2)
        self._validar_slot(params.posicion, esperado="posicion", slot=3)

        # Resolver nuevos valores (wildcard → conservar existente)
        nuevo_color    = self._resolver_color(params.color,       entrada.color)
        nuevo_escala   = self._resolver_escala(params.escala,     entrada.escala)
        nuevo_posicion = self._resolver_posicion(params.posicion, entrada.posicion)

        # M004: escala resultante debe ser > 0
        self._validar_escala(nuevo_escala)

        entrada.color    = nuevo_color
        entrada.escala   = nuevo_escala
        entrada.posicion = nuevo_posicion

    # ── delete ────────────────────────────────────────────────────────────────

    def _check_delete(self, nodo: DeleteNode) -> None:
        entrada = self._obtener_activa(nodo.id)  # M001 / M005
        entrada.eliminada = True

    # ── show ──────────────────────────────────────────────────────────────────

    def _check_show(self, nodo: ShowNode) -> None:
        entrada = self._obtener_activa(nodo.id)  # M001 / M005
        entrada.visible = True

    # ── hide ──────────────────────────────────────────────────────────────────

    def _check_hide(self, nodo: HideNode) -> None:
        entrada = self._obtener_activa(nodo.id)  # M001 / M005
        entrada.visible = False

    # ── list / clear / help ───────────────────────────────────────────────────

    def _check_list(self, nodo: ListNode) -> None:
        pass  # sin validación semántica; la ejecución la maneja el executor

    def _check_clear(self, nodo: ClearNode) -> None:
        self._tabla.vaciar()

    def _check_help(self, nodo: HelpNode) -> None:
        pass

    # ── Utilidades de validación ──────────────────────────────────────────────

    def _obtener_activa(self, id: str) -> EntradaFigura:
        """M001 si no existe; M005 si está eliminada."""
        entrada = self._tabla.obtener(id)
        if entrada is None:
            raise ErrorSemantico("M001", f"figura inexistente: {id!r}")
        if entrada.eliminada:
            raise ErrorSemantico("M005", f"figura eliminada: {id!r}")
        return entrada

    def _validar_escala(self, escala: int) -> None:
        """M004 si escala ≤ 0."""
        if escala <= 0:
            raise ErrorSemantico("M004", f"escala inválida: {escala} (debe ser > 0)")

    def _validar_slot(self, valor: ValorUpdateNode, esperado: str, slot: int) -> None:
        """
        M003 si el tipo del valor no es compatible con el slot posicional.
        Un wildcard siempre es válido en cualquier slot.
        """
        if valor.tipo == "wildcard":
            return
        if valor.tipo != esperado:
            raise ErrorSemantico(
                "M003",
                f"slot {slot} espera {esperado!r}, "
                f"se obtuvo {valor.tipo!r} = {valor.valor!r}",
            )

    # ── Resolución de valores con wildcard ────────────────────────────────────

    def _resolver_color(self, v: ValorUpdateNode, actual: str) -> str:
        if v.tipo == "wildcard":
            return actual
        return str(v.valor)

    def _resolver_escala(self, v: ValorUpdateNode, actual: int) -> int:
        if v.tipo == "wildcard":
            return actual
        return int(v.valor)  # type: ignore[arg-type]

    def _resolver_posicion(
        self,
        v: ValorUpdateNode,
        actual: tuple,
    ) -> Tuple[int, int]:
        if v.tipo == "wildcard":
            return actual  # type: ignore[return-value]
        from ast_nodes import PosicionNode
        p = v.valor
        assert isinstance(p, PosicionNode)
        return (p.x, p.y)


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN DE CONVENIENCIA
# ═══════════════════════════════════════════════════════════════════════════════

def analizar(programa: ProgramaNode, tabla: TablaSimbolos) -> TablaSimbolos:
    """Analiza semánticamente el AST sobre la tabla dada y la devuelve."""
    return AnalizadorSemantico(tabla).analizar(programa)


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO / PRUEBAS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    from lexer  import ErrorLexico
    from parser import ErrorSintactico, parsear

    def ejecutar(texto: str, tabla: TablaSimbolos) -> None:
        ast = parsear(texto)
        analizar(ast, tabla)

    CASOS: List[Tuple[str, str]] = [
        # ── Válidos (flujo completo) ──────────────────────────────────────────
        ("create circle",                         "create sin parámetros   → circle0001"),
        ("create circle(\"red\",2,[10,20])",      "create con params       → circle0002"),
        ("create square(#FF,3,[5,5])",            "create hex color        → square0001"),
        ("update circle0001(_,5,_)",              "update escala           → circle0001 escala=5"),
        ("update circle0002(\"blue\",_,_)",       "update color            → circle0002 color=blue"),
        ("update square0001(_,_,[1,1])",          "update posicion         → square0001 pos=[1,1]"),
        ("hide circle0001",                       "hide circle0001"),
        ("show circle0001",                       "show circle0001"),
        ("delete circle0002",                     "delete circle0002"),
        ("list",                                  "list  (solo semántica)"),
        ("help",                                  "help  (solo semántica)"),
        ("clear screen",                          "clear screen            → tabla vacía"),
        # ── Errores semánticos ────────────────────────────────────────────────
        ("show circle0001",                       "M001 figura inexistente  (tabla vaciada)"),
    ]

    tabla = TablaSimbolos()
    for texto, etiqueta in CASOS:
        sep = "─" * 64
        print(f"\n{sep}")
        print(f"  [{etiqueta}]")
        print(f"  entrada: {texto!r}")
        print(sep)
        try:
            ejecutar(texto, tabla)
            print(f"  OK  →  {tabla}")
        except (ErrorLexico, ErrorSintactico, ErrorSemantico) as e:
            print(f"  ✗  {e}")

    # ── Casos adicionales sin estado previo ───────────────────────────────────
    CASOS_EXTRA: List[Tuple[str, str]] = [
        ("delete circle9999",                     "M001 figira inexistente"),
        ("update circle9999(\"red\",1,[0,0])",    "M001 figura inexistente"),
        ("create circle(\"red\",0,[0,0])",        "M004 escala = 0"),
        ("create circle(\"red\",-1,[0,0])",       "Léxico: NUM_DEC no admite negativo"),
    ]

    print("\n\n══ Casos extra (tabla fresca) ══")
    for texto, etiqueta in CASOS_EXTRA:
        tabla2 = TablaSimbolos()
        # Crear una figura para probar M005
        tabla2.insertar(EntradaFigura(
            id="circle0001", tipo="circle",
            color="red", escala=1, posicion=(0,0),
            eliminada=True,
        ))
        sep = "─" * 64
        print(f"\n{sep}")
        print(f"  [{etiqueta}]  →  {texto!r}")
        print(sep)
        try:
            ejecutar(texto, tabla2)
            print(f"  OK  →  {tabla2}")
        except (ErrorLexico, ErrorSintactico, ErrorSemantico) as e:
            print(f"  ✗  {e}")

    # M005 explícito
    print("\n\n══ M005 figura eliminada ══")
    tabla3 = TablaSimbolos()
    tabla3.insertar(EntradaFigura(
        id="circle0001", tipo="circle",
        color="red", escala=1, posicion=(0,0),
        eliminada=True,
    ))
    for cmd in ("show circle0001", "hide circle0001",
                "delete circle0001", "update circle0001(\"blue\",2,[0,0])"):
        sep = "─" * 64
        print(f"\n{sep}")
        print(f"  [M005]  →  {cmd!r}")
        print(sep)
        try:
            ejecutar(cmd, tabla3)
            print("  OK")
        except (ErrorLexico, ErrorSintactico, ErrorSemantico) as e:
            print(f"  ✗  {e}")

    # M003 tipo inválido en slot
    print("\n\n══ M003 tipo inválido en slot ══")
    tabla4 = TablaSimbolos()
    tabla4.insertar(EntradaFigura(
        id="circle0001", tipo="circle",
        color="red", escala=1, posicion=(0,0),
    ))
    for cmd, desc in [
        ("update circle0001(5,2,_)",          "slot 1 (color) recibe escala"),
        ("update circle0001(\"red\",[0,0],_)","slot 2 (escala) recibe posicion"),
    ]:
        sep = "─" * 64
        print(f"\n{sep}")
        print(f"  [{desc}]  →  {cmd!r}")
        print(sep)
        try:
            ejecutar(cmd, tabla4)
            print("  OK")
        except (ErrorLexico, ErrorSintactico, ErrorSemantico) as e:
            print(f"  ✗  {e}")
