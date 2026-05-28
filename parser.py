from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, Union

from lexer import ErrorLexico, Lexer, Token, TipoToken, tokenizar
from ast_nodes import (
    ProgramaNode, ComandoNode,
    CreateNode, UpdateNode, DeleteNode,
    ShowNode, HideNode, ListNode, ClearNode, HelpNode, RotateNode,
    MoveNode, CopyNode, GroupNode, UngroupNode, ScaleNode, SetNode,
    ParametrosNode, ParametrosLineaNode, ParametrosUpdateNode, ParametrosUpdateLineaNode,
    ParametrosRectanguloNode, ParametrosElipseNode, ParametrosTextoNode,
    ParametrosUpdateRectanguloNode, ParametrosUpdateElipseNode, ParametrosUpdateTextoNode,
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
    def __init__(
        self, codigo: str, mensaje: str, linea: int, columna: int,
        sugerencia: str = "",
    ) -> None:
        super().__init__(f"[{codigo}] Línea {linea}, Col {columna}: {mensaje}")
        self.codigo     = codigo
        self.mensaje    = mensaje
        self.linea      = linea
        self.columna    = columna
        self.sugerencia = sugerencia
        self.col_fin    = columna  # posición del token (un solo token de ancho)


# ═══════════════════════════════════════════════════════════════════════════════
# SUGERENCIAS CONTEXTUALES
# ═══════════════════════════════════════════════════════════════════════════════

_SUGERENCIAS_TIPO: Dict[TipoToken, str] = {
    TipoToken.TIPO_FIGURA:   "Tipos de figura válidos: circle  square  triangle  line  pentagon  rectangle  ellipse  text",
    TipoToken.IDENTIFICADOR: "Los identificadores tienen la forma tipo+4dígitos. Ej: circle0001",
    TipoToken.LPAREN:        "Se esperaba '(' para abrir los parámetros. Ej: create circle(\"rojo\", 2, [0,0])",
    TipoToken.RPAREN:        "Se esperaba ')' para cerrar los parámetros",
    TipoToken.LBRACKET:      "Se esperaba '[' para abrir la posición. Ej: [10, 20]",
    TipoToken.RBRACKET:      "Se esperaba ']' para cerrar la posición",
    TipoToken.COMMA:         "Se esperaba ',' como separador. Ej: create circle(\"rojo\", 2, [0,0])",
    TipoToken.NUM_DEC:       "Se esperaba un número entero positivo para la escala. Ej: 2",
}

_SUGERENCIA_COMANDOS = (
    "Comandos válidos: create  update  delete  show  hide  list  clear screen  help  "
    "rotate  move  copy  group  ungroup  scale  set"
)


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

    def __init__(self, tokens: List[Token],
                 variables: Optional[Dict[str, int]] = None) -> None:
        self._tokens    = tokens
        self._pos       = 0
        self._variables: Dict[str, int] = variables if variables is not None else {}
        self.errores: List[ErrorSintactico] = []
        # ── Tabla de despacho de comandos (lookahead LL(1)) ───────────────────
        self._DISPATCH = {
            "create":  self._parse_create,
            "update":  self._parse_update,
            "delete":  self._parse_delete,
            "show":    self._parse_show,
            "hide":    self._parse_hide,
            "list":    self._parse_list,
            "clear":   self._parse_clear,
            "help":    self._parse_help,
            "rotate":  self._parse_rotate,
            "move":    self._parse_move,
            "copy":    self._parse_copy,
            "group":   self._parse_group,
            "ungroup": self._parse_ungroup,
            "scale":   self._parse_scale,
            "set":     self._parse_set,
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
                sugerencia=_SUGERENCIAS_TIPO.get(tipo, ""),
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
                sugerencia=_SUGERENCIAS_TIPO.get(tipo, ""),
            )
        self._pos += 1
        return tok

    # ── API pública ───────────────────────────────────────────────────────────

    def _sincronizar(self) -> None:
        """Avanza hasta el inicio del siguiente comando o EOF (recuperación de pánico)."""
        while self._lookahead() != TipoToken.EOF:
            tok = self._actual
            if tok.tipo == TipoToken.PALABRA_RESERVADA and tok.lexema in self._DISPATCH:
                break
            self._pos += 1

    def parse(self) -> ProgramaNode:
        """<programa> ::= { <comando> }  — con recuperación de errores."""
        nodo = ProgramaNode()
        while self._lookahead() != TipoToken.EOF:
            try:
                nodo.comandos.append(self._parse_comando())
            except ErrorSintactico as e:
                self.errores.append(e)
                self._sincronizar()
        if self._lookahead() == TipoToken.EOF:
            self._pos += 1
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
                sugerencia=_SUGERENCIA_COMANDOS,
            )
        fn = self._DISPATCH.get(tok.lexema)
        if fn is None:
            raise ErrorSintactico(
                "S001",
                f"comando desconocido: {tok.lexema!r}",
                tok.linea, tok.columna,
                sugerencia=_SUGERENCIA_COMANDOS,
            )
        return fn()

    # ── No-terminales: comandos ───────────────────────────────────────────────

    def _parse_create(self) -> CreateNode:
        """
        <create> ::= "create" <tipo_figura>
                   | "create" <tipo_figura>   "(" <parametros>           ")"
                   | "create" "line"          "(" <parametros_linea>      ")"
                   | "create" "rectangle"     "(" <parametros_rectangulo> ")"
                   | "create" "ellipse"       "(" <parametros_elipse>     ")"
                   | "create" "text"          "(" <parametros_texto>      ")"
        """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "create")
        tipo_tok    = self.match(TipoToken.TIPO_FIGURA)
        tipo_figura = tipo_tok.lexema

        if self._lookahead() == TipoToken.LPAREN:
            self.match(TipoToken.LPAREN)
            if tipo_figura == "line":
                params = self._parse_parametros_linea()
            elif tipo_figura == "rectangle":
                params = self._parse_parametros_rectangulo()
            elif tipo_figura == "ellipse":
                params = self._parse_parametros_elipse()
            elif tipo_figura == "text":
                params = self._parse_parametros_texto()
            else:
                params = self._parse_parametros()
            self.match(TipoToken.RPAREN)
            return CreateNode(tipo_figura=tipo_figura, parametros=params)

        return CreateNode(tipo_figura=tipo_figura)

    def _parse_update(self) -> UpdateNode:
        """
        <update> ::= "update" <identificador> "(" <parametros_update> ")"

        El tipo de parámetros se selecciona según el prefijo del identificador:
          line*       → ParametrosUpdateLineaNode     (color, grosor, inicio, fin)
          rectangle*  → ParametrosUpdateRectanguloNode (color, ancho, alto, posicion)
          ellipse*    → ParametrosUpdateElipseNode     (color, rx, ry, posicion)
          text*       → ParametrosUpdateTextoNode      (color, tamaño, posicion, contenido)
          otros       → ParametrosUpdateNode           (color, escala, posicion)
        """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "update")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        self.match(TipoToken.LPAREN)
        if id_tok.lexema.startswith("line"):
            params = self._parse_parametros_update_linea()
        elif id_tok.lexema.startswith("rectangle"):
            params = self._parse_parametros_update_rectangulo()
        elif id_tok.lexema.startswith("ellipse"):
            params = self._parse_parametros_update_elipse()
        elif id_tok.lexema.startswith("text"):
            params = self._parse_parametros_update_texto()
        else:
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

    def _parse_rotate(self) -> RotateNode:
        """<rotate> ::= "rotate" <identificador> "(" <entero> ")"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "rotate")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        self.match(TipoToken.LPAREN)
        grados = self._parse_entero("grados de rotación (puede ser negativo)")
        self.match(TipoToken.RPAREN)
        return RotateNode(id=id_tok.lexema, grados=grados)

    def _parse_move(self) -> MoveNode:
        """<move> ::= "move" <identificador> "(" <entero> "," <entero> ")" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "move")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        self.match(TipoToken.LPAREN)
        dx = self._parse_entero("desplazamiento dx (puede ser negativo)")
        self.match(TipoToken.COMMA)
        dy = self._parse_entero("desplazamiento dy (puede ser negativo)")
        self.match(TipoToken.RPAREN)
        return MoveNode(id=id_tok.lexema, dx=dx, dy=dy)

    def _parse_copy(self) -> CopyNode:
        """<copy> ::= "copy" <identificador>"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "copy")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        return CopyNode(id=id_tok.lexema)

    def _parse_group(self) -> GroupNode:
        """<group> ::= "group" <identificador> { <identificador> }"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "group")
        ids: List[str] = []
        while self._lookahead() == TipoToken.IDENTIFICADOR:
            ids.append(self._actual.lexema)
            self._pos += 1
        if len(ids) < 2:
            tok = self._actual
            raise ErrorSintactico(
                "S002",
                "group requiere al menos dos identificadores",
                tok.linea, tok.columna,
                sugerencia="Ej: group circle0001 square0001",
            )
        return GroupNode(ids=ids)

    def _parse_ungroup(self) -> UngroupNode:
        """<ungroup> ::= "ungroup" <identificador>"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "ungroup")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        return UngroupNode(id=id_tok.lexema)

    def _parse_scale(self) -> ScaleNode:
        """<scale> ::= "scale" <identificador> "(" <entero> ")" """
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "scale")
        id_tok = self.match(TipoToken.IDENTIFICADOR)
        self.match(TipoToken.LPAREN)
        factor = self._parse_entero("factor de escala (entero > 0)")
        self.match(TipoToken.RPAREN)
        return ScaleNode(id=id_tok.lexema, factor=factor)

    def _parse_set(self) -> SetNode:
        """<set> ::= "set" NOMBRE_VAR (<entero> | STRING | NUM_HEX)"""
        self._match_lexema(TipoToken.PALABRA_RESERVADA, "set")
        var_tok = self.match(TipoToken.NOMBRE_VAR)
        tok = self._actual
        if tok.tipo in (TipoToken.STRING, TipoToken.NUM_HEX):
            self._pos += 1
            valor: Union[int, str] = tok.lexema
        else:
            valor = self._parse_entero("valor de la variable: entero, \"color\" o #hex")
        return SetNode(nombre=var_tok.lexema, valor=valor)

    # ── No-terminales: parámetros ─────────────────────────────────────────────

    def _parse_parametros_linea(self) -> ParametrosLineaNode:
        """<parametros_linea> ::= <color> "," NUM_DEC "," <posicion> "," <posicion>"""
        color  = self._parse_color()
        self.match(TipoToken.COMMA)
        grosor = self._parse_escala()
        self.match(TipoToken.COMMA)
        inicio = self._parse_posicion()
        self.match(TipoToken.COMMA)
        fin    = self._parse_posicion()
        return ParametrosLineaNode(color=color, grosor=grosor, inicio=inicio, fin=fin)

    def _parse_parametros_update_linea(self) -> ParametrosUpdateLineaNode:
        """
        <parametros_update_linea> ::=
            <valor_update> "," <valor_update> "," <valor_update> "," <valor_update>

        Slots: color, grosor, inicio, fin.
        """
        v_color  = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_grosor = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_inicio = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_fin    = self._parse_valor_update()
        return ParametrosUpdateLineaNode(
            color=v_color, grosor=v_grosor, inicio=v_inicio, fin=v_fin,
        )

    def _parse_parametros_rectangulo(self) -> ParametrosRectanguloNode:
        """<parametros_rectangulo> ::= <color> "," NUM_DEC "," NUM_DEC "," <posicion>"""
        color    = self._parse_color()
        self.match(TipoToken.COMMA)
        ancho    = self._parse_escala()
        self.match(TipoToken.COMMA)
        alto     = self._parse_escala()
        self.match(TipoToken.COMMA)
        posicion = self._parse_posicion()
        return ParametrosRectanguloNode(color=color, ancho=ancho, alto=alto, posicion=posicion)

    def _parse_parametros_elipse(self) -> ParametrosElipseNode:
        """<parametros_elipse> ::= <color> "," NUM_DEC "," NUM_DEC "," <posicion>"""
        color    = self._parse_color()
        self.match(TipoToken.COMMA)
        rx       = self._parse_escala()
        self.match(TipoToken.COMMA)
        ry       = self._parse_escala()
        self.match(TipoToken.COMMA)
        posicion = self._parse_posicion()
        return ParametrosElipseNode(color=color, rx=rx, ry=ry, posicion=posicion)

    def _parse_parametros_texto(self) -> ParametrosTextoNode:
        """<parametros_texto> ::= <color> "," NUM_DEC "," <posicion> "," STRING"""
        color    = self._parse_color()
        self.match(TipoToken.COMMA)
        tamanio  = self._parse_escala()
        self.match(TipoToken.COMMA)
        posicion = self._parse_posicion()
        self.match(TipoToken.COMMA)
        tok = self._actual
        if tok.tipo != TipoToken.STRING:
            raise ErrorSintactico(
                "S002",
                f"se esperaba STRING para el contenido del texto, "
                f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
                tok.linea, tok.columna,
                sugerencia='El contenido debe ser un string entre comillas. Ej: "Hola mundo"',
            )
        self._pos += 1
        return ParametrosTextoNode(color=color, tamanio=tamanio, posicion=posicion, contenido=tok.lexema)

    def _parse_parametros_update_rectangulo(self) -> ParametrosUpdateRectanguloNode:
        """
        <parametros_update_rectangulo> ::=
            <valor_update> "," <valor_update> "," <valor_update> "," <valor_update>

        Slots: color, ancho, alto, posicion.
        """
        v_color    = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_ancho    = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_alto     = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_posicion = self._parse_valor_update()
        return ParametrosUpdateRectanguloNode(
            color=v_color, ancho=v_ancho, alto=v_alto, posicion=v_posicion,
        )

    def _parse_parametros_update_elipse(self) -> ParametrosUpdateElipseNode:
        """
        <parametros_update_elipse> ::=
            <valor_update> "," <valor_update> "," <valor_update> "," <valor_update>

        Slots: color, rx, ry, posicion.
        """
        v_color    = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_rx       = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_ry       = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_posicion = self._parse_valor_update()
        return ParametrosUpdateElipseNode(
            color=v_color, rx=v_rx, ry=v_ry, posicion=v_posicion,
        )

    def _parse_parametros_update_texto(self) -> ParametrosUpdateTextoNode:
        """
        <parametros_update_texto> ::=
            <valor_update> "," <valor_update> "," <valor_update> "," <valor_contenido>

        Slots: color, tamaño, posicion, contenido.
        """
        v_color    = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_tamanio  = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_posicion = self._parse_valor_update()
        self.match(TipoToken.COMMA)
        v_contenido = self._parse_valor_contenido()
        return ParametrosUpdateTextoNode(
            color=v_color, tamanio=v_tamanio, posicion=v_posicion, contenido=v_contenido,
        )

    def _parse_valor_contenido(self) -> ValorUpdateNode:
        """
        <valor_contenido> ::= STRING | "_"

        Usado exclusivamente para el slot de contenido en update text.
        FIRST = { STRING, UNDERSCORE }
        """
        tok = self._actual
        if tok.tipo == TipoToken.STRING:
            self._pos += 1
            return ValorUpdateNode(tipo="contenido", valor=tok.lexema)
        if tok.tipo == TipoToken.UNDERSCORE:
            self._pos += 1
            return ValorUpdateNode(tipo="wildcard", valor=None)
        raise ErrorSintactico(
            "S002",
            f"se esperaba STRING o '_' para el contenido del texto, "
            f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
            tok.linea, tok.columna,
            sugerencia='Usa un string "Hola" o _ para mantener el valor actual',
        )

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
        <color> ::= STRING | NUM_HEX | NOMBRE_VAR

        FIRST = { STRING, NUM_HEX, NOMBRE_VAR }
        """
        tok = self._actual
        if tok.tipo in (TipoToken.STRING, TipoToken.NUM_HEX):
            self._pos += 1
            return tok.lexema
        if tok.tipo == TipoToken.NOMBRE_VAR:
            self._pos += 1
            nombre = tok.lexema
            if nombre not in self._variables:
                raise ErrorSintactico(
                    "S004",
                    f"variable no definida: {nombre!r}",
                    tok.linea, tok.columna,
                    sugerencia=f"Usa 'set {nombre} \"color\"' para definir la variable",
                )
            val = self._variables[nombre]
            if not isinstance(val, str):
                raise ErrorSintactico(
                    "S005",
                    f"la variable {nombre!r} tiene valor entero ({val}), no es un color",
                    tok.linea, tok.columna,
                    sugerencia=f"Usa 'set {nombre} \"rojo\"' o 'set {nombre} #FF0088'",
                )
            return val
        raise ErrorSintactico(
            "S002",
            f"se esperaba color (STRING, NUM_HEX o variable de color), "
            f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
            tok.linea, tok.columna,
            sugerencia='El color puede ser un string "rojo", un hex #FF0088 o una variable: set c "red"',
        )

    def _parse_entero(self, contexto: str = "") -> int:
        """
        <entero> ::= NUM_DEC | NOMBRE_VAR

        Acepta literales enteros (incluyendo negativos) y nombres de variable.
        Las variables deben haber sido definidas previamente con 'set'.
        FIRST = { NUM_DEC, NOMBRE_VAR }
        """
        tok = self._actual
        if tok.tipo == TipoToken.NUM_DEC:
            self._pos += 1
            return int(tok.lexema)
        if tok.tipo == TipoToken.NOMBRE_VAR:
            self._pos += 1
            nombre = tok.lexema
            if nombre not in self._variables:
                raise ErrorSintactico(
                    "S004",
                    f"variable no definida: {nombre!r}",
                    tok.linea, tok.columna,
                    sugerencia=f"Usa 'set {nombre} <valor>' para definir la variable",
                )
            return self._variables[nombre]
        raise ErrorSintactico(
            "S003",
            f"se esperaba número o variable, "
            f"se obtuvo {tok.tipo.value} ({tok.lexema!r})",
            tok.linea, tok.columna,
            sugerencia=contexto or "Se esperaba un entero o nombre de variable. Ej: 5, -3, x",
        )

    def _parse_escala(self) -> int:
        """
        <escala> ::= <entero>   (positivo; relativo al tamaño de la figura)

        FIRST = { NUM_DEC, NOMBRE_VAR }
        """
        return self._parse_entero("escala (entero positivo > 0)")

    def _parse_posicion(self) -> PosicionNode:
        """
        <posicion> ::= "[" <entero> "," <entero> "]"

        FIRST = { LBRACKET }
        Las coordenadas admiten enteros negativos (cuadrantes negativos).
        """
        self.match(TipoToken.LBRACKET)
        x = self._parse_entero("coordenada X (puede ser negativa)")
        self.match(TipoToken.COMMA)
        y = self._parse_entero("coordenada Y (puede ser negativa)")
        self.match(TipoToken.RBRACKET)
        return PosicionNode(x=x, y=y)

    def _parse_valor_update(self) -> ValorUpdateNode:
        """
        <valor_update> ::= <color> | <escala> | <posicion> | "_"

        FIRST sets (disjuntos → LL(1)):
            color    →  { STRING, NUM_HEX }
            escala   →  { NUM_DEC, NOMBRE_VAR }
            posicion →  { LBRACKET }
            wildcard →  { UNDERSCORE }
        """
        tok = self._actual

        if tok.tipo in (TipoToken.STRING, TipoToken.NUM_HEX):
            return ValorUpdateNode(tipo="color",    valor=self._parse_color())
        if tok.tipo in (TipoToken.NUM_DEC, TipoToken.NOMBRE_VAR):
            return ValorUpdateNode(tipo="escala",   valor=self._parse_entero("escala"))
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
            sugerencia='Usa _ para mantener el valor actual. Ej: update circle0001("rojo", _, _)',
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN DE CONVENIENCIA
# ═══════════════════════════════════════════════════════════════════════════════

def parsear(texto: str) -> Tuple[ProgramaNode, List[ErrorLexico], List[ErrorSintactico]]:
    """Tokeniza y parsea el texto; devuelve (AST, errores_léxicos, errores_sintácticos)."""
    tokens, lex_errs = tokenizar(texto)
    p = Parser(tokens)
    ast = p.parse()
    return ast, lex_errs, p.errores


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


