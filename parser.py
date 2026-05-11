"""
parser.py — Analizador Sintáctico · Lenguaje de Figuras Geométricas

Parser LL(1) descendente recursivo.
  · Una función por no-terminal.
  · Un token de lookahead.
  · match() valida y avanza; error sintáctico si falla.

Gramática implementada:
  <programa>          ::= { <comando> }
  <comando>           ::= <create> | <update> | <delete> | <show>
                        | <hide>   | <list>   | <clear>  | <help>
  <create>            ::= "create" <tipo_figura>
                        | "create" <tipo_figura> "(" <parametros> ")"
  <update>            ::= "update" <identificador> "(" <parametros_update> ")"
  <delete>            ::= "delete" <identificador>
  <show>              ::= "show"   <identificador>
  <hide>              ::= "hide"   <identificador>
  <list>              ::= "list"
  <clear>             ::= "clear" "screen"
  <help>              ::= "help"
  <parametros>        ::= <color> "," <escala> "," <posicion>
  <parametros_update> ::= <valor_update> "," <valor_update> "," <valor_update>
  <valor_update>      ::= <color> | <escala> | <posicion> | "_"
  <color>             ::= STRING | NUM_HEX
  <escala>            ::= NUM_DEC
  <posicion>          ::= "[" NUM_DEC "," NUM_DEC "]"
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from lexer import Lexer, Token, TipoToken, tokenizar
from ast_nodes import (
    ProgramaNode, ComandoNode,
    CreateNode, UpdateNode, DeleteNode,
    ShowNode, HideNode, ListNode, ClearNode, HelpNode,
    ParametrosNode, ParametrosUpdateNode,
    ValorUpdateNode, PosicionNode,
)


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR SINTÁCTICO
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorSintactico(Exception):
    """
    Códigos según especificación:
        S001  comando inválido
        S002  estructura inválida
        S003  token inesperado
    """
    def __init__(self, codigo: str, mensaje: str, linea: int, columna: int) -> None:
        super().__init__(f"[{codigo}] Línea {linea}, Col {columna}: {mensaje}")
        self.codigo  = codigo
        self.mensaje = mensaje
        self.linea   = linea
        self.columna = columna


# ═══════════════════════════════════════════════════════════════════════════════
# PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class Parser:
    """
    Parser LL(1) descendente recursivo.

    La tabla de despacho _DISPATCH mapea cada lexema de palabra reservada
    a su función de parseo, implementando el lookahead LL(1) de <comando>.
    """

    # Tabla LL(1): lexema PALABRA_RESERVADA → método parseador
    # Se construye en __init__ para poder referenciar self.
    _DISPATCH: Dict[str, Callable[[], ComandoNode]]

    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos    = 0

        # ── Tabla de despacho de comandos (lookahead LL(1)) ───────────────────
        self._DISPATCH = {
            "create": self._parse_create,
            "update": self._parse_update,
            "delete": self._parse_delete,
            "show":   self._parse_show,
            "hide":   self._parse_hide,
            "list":   self._parse_list,
            "clear":  self._parse_clear,
            "help":   self._parse_help,
        }

    # ── Utilidades ────────────────────────────────────────────────────────────

    @property
    def _actual(self) -> Token:
        return self._tokens[self._pos]

    def _lookahead(self) -> TipoToken:
        return self._actual.tipo

    def match(self, tipo: TipoToken) -> Token:
        """Consume el token actual si su tipo coincide; lanza S003 si no."""
        tok = self._actual
        if tok.tipo != tipo:
            raise ErrorSintactico(
                "S003",
                f"se esperaba {tipo.value}, "
                f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
                tok.linea, tok.columna,
            )
        self._pos += 1
        return tok

    def _match_lexema(self, tipo: TipoToken, lexema: str) -> Token:
        """Consume token si tipo Y lexema coinciden; lanza S003 si no."""
        tok = self._actual
        if tok.tipo != tipo or tok.lexema != lexema:
            raise ErrorSintactico(
                "S003",
                f"se esperaba {lexema!r}, "
                f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
                tok.linea, tok.columna,
            )
        self._pos += 1
        return tok

    # ── API pública ───────────────────────────────────────────────────────────

    def parse(self) -> ProgramaNode:
        """<programa> ::= { <comando> }"""
        nodo = ProgramaNode()
        while self._lookahead() != TipoToken.EOF:
            nodo.comandos.append(self._parse_comando())
        self.match(TipoToken.EOF)
        return nodo

    # ── No-terminal: <comando> ────────────────────────────────────────────────

    def _parse_comando(self) -> ComandoNode:
        """
        <comando> ::= <create> | <update> | <delete> | <show>
                    | <hide>   | <list>   | <clear>  | <help>

        Lookahead LL(1): token actual debe ser PALABRA_RESERVADA.
        La tabla _DISPATCH selecciona la función correcta según el lexema.
        """
        tok = self._actual
        if tok.tipo != TipoToken.PALABRA_RESERVADA:
            raise ErrorSintactico(
                "S001",
                f"se esperaba un comando, "
                f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
                tok.linea, tok.columna,
            )
        fn = self._DISPATCH.get(tok.lexema)
        if fn is None:
            raise ErrorSintactico(
                "S001",
                f"comando desconocido: {tok.lexema!r}",
                tok.linea, tok.columna,
            )
        return fn()

    # ── No-terminales: comandos ───────────────────────────────────────────────

    def _parse_create(self) -> CreateNode:
        """
        <create> ::= "create" <tipo_figura>
                   | "create" <tipo_figura> "(" <parametros> ")"
        """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "create")
        tipo_tok    = self.match(TipoToken.TIPO_FIGURA)
        tipo_figura = tipo_tok.lexema

        if self._lookahead() == TipoToken.LPAREN:
            self.match(TipoToken.LPAREN)
            params = self._parse_parametros()
            self.match(TipoToken.RPAREN)
            return CreateNode(tipo_figura=tipo_figura, parametros=params)

        return CreateNode(tipo_figura=tipo_figura)

    def _parse_update(self) -> UpdateNode:
        """<update> ::= "update" <identificador> "(" <parametros_update> ")" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "update")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        self.match(TipoToken.LPAREN)
        params = self._parse_parametros_update()
        self.match(TipoToken.RPAREN)
        return UpdateNode(id=id_tok.lexema, parametros=params)

    def _parse_delete(self) -> DeleteNode:
        """<delete> ::= "delete" <identificador>"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "delete")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        return DeleteNode(id=id_tok.lexema)

    def _parse_show(self) -> ShowNode:
        """<show> ::= "show" <identificador>"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "show")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        return ShowNode(id=id_tok.lexema)

    def _parse_hide(self) -> HideNode:
        """<hide> ::= "hide" <identificador>"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "hide")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        return HideNode(id=id_tok.lexema)

    def _parse_list(self) -> ListNode:
        """<list> ::= "list" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "list")
        return ListNode()

    def _parse_clear(self) -> ClearNode:
        """<clear> ::= "clear" "screen" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "clear")
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "screen")
        return ClearNode(scope="screen")

    def _parse_help(self) -> HelpNode:
        """<help> ::= "help" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "help")
        return HelpNode()

    # ── No-terminales: parámetros ─────────────────────────────────────────────

    def _parse_parametros(self) -> ParametrosNode:
        """<parametros> ::= <color> "," <escala> "," <posicion>"""
        color    = self._parse_color()
        self.match(TipoToken.COMMA)
        escala   = self._parse_escala()
        self.match(TipoToken.COMMA)
        posicion = self._parse_posicion()
        return ParametrosNode(color=color, escala=escala, posicion=posicion)

    def _parse_parametros_update(self) -> ParametrosUpdateNode:
        """
        <parametros_update> ::= <valor_update> "," <valor_update> "," <valor_update>

        Los tres slots corresponden posicionalmente a color, escala y posición.
        La validación de compatibilidad tipo-slot es tarea del semántico.
        """
        v_color    = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_escala   = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_posicion = self._parse_valor_update()
        return ParametrosUpdateNode(
            color=v_color, escala=v_escala, posicion=v_posicion,
        )

    # ── No-terminales: valores ────────────────────────────────────────────────

    def _parse_color(self) -> str:
        """
        <color> ::= STRING | NUM_HEX

        FIRST = { STRING, NUM_HEX }
        """
        tok = self._actual
        if tok.tipo in (TipoToken.STRING, TipoToken.NUM_HEX):
            self._pos += 1
            return tok.lexema
        raise ErrorSintactico(
            "S002",
            f"se esperaba color (STRING o NUM_HEX), "
            f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
            tok.linea, tok.columna,
        )

    def _parse_escala(self) -> int:
        """
        <escala> ::= NUM_DEC

        FIRST = { NUM_DEC }
        """
        tok = self.match(TipoToken.NUM_DEC)
        return int(tok.lexema)

    def _parse_posicion(self) -> PosicionNode:
        """
        <posicion> ::= "[" NUM_DEC "," NUM_DEC "]"

        FIRST = { LBRACKET }
        """
        self.match(TipoToken.LBRACKET)
        x_tok = self.match(TipoToken.NUM_DEC)
        self.match(TipoToken.COMMA)
        y_tok = self.match(TipoToken.NUM_DEC)
        self.match(TipoToken.RBRACKET)
        return PosicionNode(x=int(x_tok.lexema), y=int(y_tok.lexema))

    def _parse_valor_update(self) -> ValorUpdateNode:
        """
        <valor_update> ::= <color> | <escala> | <posicion> | "_"

        FIRST sets (disjuntos → LL(1)):
            color    →  { STRING, NUM_HEX }
            escala   →  { NUM_DEC }
            posicion →  { LBRACKET }
            wildcard →  { UNDERSCORE }
        """
        tok = self._actual

        if tok.tipo in (TipoToken.STRING, TipoToken.NUM_HEX):
            return ValorUpdateNode(tipo="color",    valor=self._parse_color())
        if tok.tipo == TipoToken.NUM_DEC:
            return ValorUpdateNode(tipo="escala",   valor=self._parse_escala())
        if tok.tipo == TipoToken.LBRACKET:
            return ValorUpdateNode(tipo="posicion", valor=self._parse_posicion())
        if tok.tipo == TipoToken.UNDERSCORE:
            self._pos += 1
            return ValorUpdateNode(tipo="wildcard", valor=None)

        raise ErrorSintactico(
            "S002",
            f"se esperaba valor_update (color / escala / posicion / _), "
            f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
            tok.linea, tok.columna,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN DE CONVENIENCIA
# ═══════════════════════════════════════════════════════════════════════════════

def parsear(texto: str) -> ProgramaNode:
    """Tokeniza el texto y lo parsea, devolviendo el AST."""
    tokens = tokenizar(texto)
    return Parser(tokens).parse()


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO / PRUEBAS
# ═══════════════════════════════════════════════════════════════════════════════

def _imprimir_ast(nodo: object, indent: int = 0) -> None:
    """Impresión recursiva simple del AST."""
    pad = "  " * indent
    nombre = type(nodo).__name__

    from ast_nodes import (
        ProgramaNode, CreateNode, UpdateNode, DeleteNode,
        ShowNode, HideNode, ListNode, ClearNode, HelpNode,
        ParametrosNode, ParametrosUpdateNode, ValorUpdateNode, PosicionNode,
    )

    if isinstance(nodo, ProgramaNode):
        print(f"{pad}ProgramaNode ({len(nodo.comandos)} comandos)")
        for cmd in nodo.comandos:
            _imprimir_ast(cmd, indent + 1)

    elif isinstance(nodo, CreateNode):
        print(f"{pad}CreateNode  tipo={nodo.tipo_figura!r}")
        if nodo.parametros:
            _imprimir_ast(nodo.parametros, indent + 1)

    elif isinstance(nodo, UpdateNode):
        print(f"{pad}UpdateNode  id={nodo.id!r}")
        _imprimir_ast(nodo.parametros, indent + 1)

    elif isinstance(nodo, DeleteNode):
        print(f"{pad}DeleteNode  id={nodo.id!r}")

    elif isinstance(nodo, ShowNode):
        print(f"{pad}ShowNode    id={nodo.id!r}")

    elif isinstance(nodo, HideNode):
        print(f"{pad}HideNode    id={nodo.id!r}")

    elif isinstance(nodo, ListNode):
        print(f"{pad}ListNode")

    elif isinstance(nodo, ClearNode):
        print(f"{pad}ClearNode   scope={nodo.scope!r}")

    elif isinstance(nodo, HelpNode):
        print(f"{pad}HelpNode")

    elif isinstance(nodo, ParametrosNode):
        print(f"{pad}ParametrosNode")
        print(f"{pad}  color    = {nodo.color!r}")
        print(f"{pad}  escala   = {nodo.escala}")
        print(f"{pad}  posicion = {nodo.posicion}")

    elif isinstance(nodo, ParametrosUpdateNode):
        print(f"{pad}ParametrosUpdateNode")
        print(f"{pad}  color    = {nodo.color}")
        print(f"{pad}  escala   = {nodo.escala}")
        print(f"{pad}  posicion = {nodo.posicion}")

    else:
        print(f"{pad}{nodo!r}")


if __name__ == "__main__":

    from lexer import ErrorLexico

    CASOS: List[Tuple[str, str]] = [
        # ── Válidos ──────────────────────────────────────────────────────────
        ("create circle",                           "create sin parámetros"),
        ("create square(\"red\",2,[10,20])",        "create con STRING"),
        ("create circle(#1F,10,[0,0])",             "create con NUM_HEX"),
        ("update circle0001(_,3,_)",                "update wildcards"),
        ("update triangle0045(\"blue\",_,[5,5])",   "update parcial"),
        ("delete pentagon9999",                     "delete"),
        ("hide circle0001",                         "hide"),
        ("show triangle0045",                       "show"),
        ("list",                                    "list"),
        ("clear screen",                            "clear screen"),
        ("help",                                    "help"),
        # ── Errores sintácticos ───────────────────────────────────────────────
        ("create circle(\"red\" 2 [10,20])",        "S002 comas faltantes"),
        ("update circle0001()",                     "S002 update sin valores"),
        ("circle0001",                              "S001 sin comando"),
        ("delete",                                  "S003 delete sin id"),
        ("clear",                                   "S003 clear sin screen"),
    ]

    for texto, etiqueta in CASOS:
        sep = "─" * 64
        print(f"\n{sep}")
        print(f"  [{etiqueta}]  →  {texto!r}")
        print(sep)
        try:
            ast = parsear(texto)
            _imprimir_ast(ast)
        except (ErrorLexico, ErrorSintactico) as e:
            print(f"  ✗  {e}")
