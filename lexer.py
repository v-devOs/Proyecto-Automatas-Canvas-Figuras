"""
lexer.py — Analizador Léxico · Lenguaje de Figuras Geométricas

Implementado como AFD explícito con tabla de transiciones carácter a carácter.
Ninguna decisión léxica se toma con "if lexema in lista"; las transiciones
gobiernan el flujo.  Los conjuntos PALABRAS_RESERVADAS / TIPOS_FIGURA se
consultan únicamente al EMITIR un token de letras, equivalente al mapeo
estado_final → TipoToken del AFD formal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# 1 · TIPOS DE TOKEN
# ═══════════════════════════════════════════════════════════════════════════════

class TipoToken(Enum):
    PALABRA_RESERVADA = "PALABRA_RESERVADA"
    TIPO_FIGURA       = "TIPO_FIGURA"
    IDENTIFICADOR     = "IDENTIFICADOR"
    NUM_DEC           = "NUM_DEC"
    NUM_HEX           = "NUM_HEX"
    STRING            = "STRING"
    LPAREN            = "LPAREN"
    RPAREN            = "RPAREN"
    LBRACKET          = "LBRACKET"
    RBRACKET          = "RBRACKET"
    COMMA             = "COMMA"
    UNDERSCORE        = "UNDERSCORE"
    EOF               = "EOF"


@dataclass(frozen=True)
class Token:
    tipo:    TipoToken
    lexema:  str
    linea:   int
    columna: int

    def __repr__(self) -> str:
        return (
            f"Token({self.tipo.value:<22} lexema={self.lexema!r:<16} "
            f"L{self.linea}:C{self.columna})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 2 · ESTADOS DEL AFD
# ═══════════════════════════════════════════════════════════════════════════════

class Estado(Enum):
    # ── Transitorios ──────────────────────────────────────────────────────────
    Q0   = "q0"     # inicial / sumidero de espacios
    QL   = "qL"     # leyendo letras (palabras / tipos / prefijo id)
    QID1 = "qID1"   # 1er dígito del identificador
    QID2 = "qID2"   # 2do dígito
    QID3 = "qID3"   # 3er dígito
    QID4 = "qID4"   # 4to dígito  →  listo para emitir en delimitador
    QD   = "qD"     # leyendo dígitos decimales
    QH   = "qH"     # después de '#'
    QH1  = "qH1"    # leyendo dígitos hexadecimales
    QS   = "qS"     # dentro de string literal
    QE   = "qE"     # sumidero de error
    # ── Aceptación inmediata (un solo carácter, sin acumulador) ───────────────
    QSYM = "qSYM"   # símbolo delimitador


# ═══════════════════════════════════════════════════════════════════════════════
# 3 · CLASES DE CARÁCTER  (columnas de la tabla de transiciones)
# ═══════════════════════════════════════════════════════════════════════════════

class CC(Enum):
    HEX_ALPHA = "hex_alpha"   # A-F  a-f   (también son letras; rol dual)
    LETTER    = "letter"      # resto de letras  g-z  G-Z
    DIGIT     = "digit"       # 0-9
    HASH      = "hash"        # #
    QUOTE     = "quote"       # "
    LPAREN    = "lparen"      # (
    RPAREN    = "rparen"      # )
    LBRACKET  = "lbracket"    # [
    RBRACKET  = "rbracket"    # ]
    COMMA     = "comma"       # ,
    UNDER     = "under"       # _
    SPACE     = "space"       # ' '  \t
    NEWLINE   = "newline"     # \n   \r
    EOF_CC    = "eof"
    OTHER     = "other"


_HEX_CHARS: FrozenSet[str] = frozenset("ABCDEFabcdef")

# Clases que actúan como «fin de lexema» para estados acumuladores.
# Al encontrar una de éstas en los estados _ESTADOS_EMIT, se emite el
# token acumulado SIN consumir el carácter delimitador.
_DELIM: FrozenSet[CC] = frozenset({
    CC.SPACE, CC.NEWLINE, CC.EOF_CC,
    CC.LPAREN, CC.RPAREN,
    CC.LBRACKET, CC.RBRACKET,
    CC.COMMA, CC.UNDER,
})

# Estados acumuladores que responden al delimitador emitiendo su token
_ESTADOS_EMIT: FrozenSet[Estado] = frozenset({
    Estado.QL, Estado.QID4, Estado.QD, Estado.QH1,
})


def _cc(c: Optional[str]) -> CC:
    """Clasifica un carácter en su clase CC."""
    if c is None:         return CC.EOF_CC
    if c in _HEX_CHARS:   return CC.HEX_ALPHA
    if c.isalpha():       return CC.LETTER
    if c.isdigit():       return CC.DIGIT
    _MAP: Dict[str, CC] = {
        '#': CC.HASH,     '"': CC.QUOTE,
        '(': CC.LPAREN,   ')': CC.RPAREN,
        '[': CC.LBRACKET, ']': CC.RBRACKET,
        ',': CC.COMMA,    '_': CC.UNDER,
    }
    if c in _MAP:         return _MAP[c]
    if c in ' \t':        return CC.SPACE
    if c in '\n\r':       return CC.NEWLINE
    return CC.OTHER


# ═══════════════════════════════════════════════════════════════════════════════
# 4 · TABLA DE TRANSICIONES
#     (Estado, CC) ──→ Estado
#     Pares no definidos equivalen a Estado.QE  (error implícito).
# ═══════════════════════════════════════════════════════════════════════════════

_TABLA: Dict[Tuple[Estado, CC], Estado] = {

    # ── q0: estado inicial ────────────────────────────────────────────────────
    (Estado.Q0, CC.HEX_ALPHA): Estado.QL,
    (Estado.Q0, CC.LETTER):    Estado.QL,
    (Estado.Q0, CC.DIGIT):     Estado.QD,
    (Estado.Q0, CC.HASH):      Estado.QH,
    (Estado.Q0, CC.QUOTE):     Estado.QS,
    (Estado.Q0, CC.LPAREN):    Estado.QSYM,
    (Estado.Q0, CC.RPAREN):    Estado.QSYM,
    (Estado.Q0, CC.LBRACKET):  Estado.QSYM,
    (Estado.Q0, CC.RBRACKET):  Estado.QSYM,
    (Estado.Q0, CC.COMMA):     Estado.QSYM,
    (Estado.Q0, CC.UNDER):     Estado.QSYM,
    (Estado.Q0, CC.SPACE):     Estado.Q0,    # espacio: permanecer en q0
    (Estado.Q0, CC.NEWLINE):   Estado.Q0,    # nueva línea: permanecer en q0
    # OTHER → QE (implícito)

    # ── qL: leyendo letras ────────────────────────────────────────────────────
    (Estado.QL, CC.HEX_ALPHA): Estado.QL,
    (Estado.QL, CC.LETTER):    Estado.QL,
    (Estado.QL, CC.DIGIT):     Estado.QID1,  # primer dígito del identificador
    # delimitador → emitir (manejado en el bucle principal, no en la tabla)
    # QUOTE / HASH / OTHER → QE  (implícito)

    # ── qID1 – qID4: sufijo numérico del identificador ────────────────────────
    (Estado.QID1, CC.DIGIT): Estado.QID2,
    (Estado.QID2, CC.DIGIT): Estado.QID3,
    (Estado.QID3, CC.DIGIT): Estado.QID4,
    # QID4 + delimitador → emitir (manejado en el bucle principal)
    # cualquier no-dígito en QID1-QID4 → QE  (implícito)

    # ── qD: número decimal ────────────────────────────────────────────────────
    (Estado.QD, CC.DIGIT): Estado.QD,
    # delimitador → emitir (manejado en el bucle principal)
    # otro → QE  (implícito)

    # ── qH: después de '#' ────────────────────────────────────────────────────
    (Estado.QH, CC.DIGIT):     Estado.QH1,
    (Estado.QH, CC.HEX_ALPHA): Estado.QH1,
    # otro → QE: L003  (implícito)

    # ── qH1: dígitos hexadecimales ────────────────────────────────────────────
    (Estado.QH1, CC.DIGIT):     Estado.QH1,
    (Estado.QH1, CC.HEX_ALPHA): Estado.QH1,
    # delimitador → emitir (manejado en el bucle principal)
    # letra no-hex / otro → QE: L003  (implícito)

    # qS: string literal
    # Manejo íntegramente en el bucle principal: acepta todo ≠ '"' sin tabla.
}

# ═══════════════════════════════════════════════════════════════════════════════
# 5 · CONJUNTOS DE CLASIFICACIÓN FINAL
#     Solo se consultan al EMITIR un token de letras (equivale al mapeo
#     qPR / qTF del AFD formal).  No participan en el recorrido caracter.
# ═══════════════════════════════════════════════════════════════════════════════

_RESERVADAS: FrozenSet[str] = frozenset({
    "create", "update", "delete", "show",    "hide",
    "list",   "clear",  "screen", "help",    "rotate",
    "move",   "copy",   "group",  "ungroup", "scale",
})

_TIPOS_FIGURA: FrozenSet[str] = frozenset({
    "circle", "square", "triangle", "line", "pentagon",
    "rectangle", "ellipse", "text",
})

# Prefijos válidos para identificadores: tipos de figura + "group" (para group0001)
_PREFIJOS_VALIDOS: FrozenSet[str] = _TIPOS_FIGURA | frozenset({"group"})

_SYM_TOKEN: Dict[str, TipoToken] = {
    '(': TipoToken.LPAREN,
    ')': TipoToken.RPAREN,
    '[': TipoToken.LBRACKET,
    ']': TipoToken.RBRACKET,
    ',': TipoToken.COMMA,
    '_': TipoToken.UNDERSCORE,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 6 · ERROR LÉXICO
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorLexico(Exception):
    """
    Códigos según especificación:
        L001  símbolo / carácter inválido
        L002  string sin cerrar
        L003  hexadecimal inválido
        L004  identificador inválido
    """
    def __init__(
        self, codigo: str, mensaje: str, linea: int, columna: int,
        sugerencia: str = "", col_fin: int = 0,
    ) -> None:
        super().__init__(f"[{codigo}] Línea {linea}, Col {columna}: {mensaje}")
        self.codigo     = codigo
        self.mensaje    = mensaje
        self.linea      = linea
        self.columna    = columna
        self.sugerencia = sugerencia
        self.col_fin    = col_fin or columna


# ═══════════════════════════════════════════════════════════════════════════════
# 7 · LEXER
# ═══════════════════════════════════════════════════════════════════════════════

class Lexer:
    """
    Analizador léxico basado en AFD explícito.

    Bucle principal:
        1. Estado QS (string): acepta todo ≠ '"' sin consultar tabla.
        2. Delimitador en estado acumulador: emite token sin consumir carácter.
        3. EOF: flush del acumulador pendiente.
        4. Transición normal: consulta _TABLA[(estado_actual, clase_char)].
           · QSYM  → emite símbolo de un solo carácter.
           · Q0    → espacio/newline en q0; solo avanza.
           · demás → acumula carácter en buf y cambia estado.
    """

    def __init__(self, texto: str) -> None:
        self._texto   = texto
        self._pos     = 0
        self._linea   = 1
        self._col     = 1
        self._estado  = Estado.Q0
        self._buf:    List[str] = []
        self._tok_lin = 1
        self._tok_col = 1
        self.errores: List[ErrorLexico] = []

    # ── API pública ───────────────────────────────────────────────────────────

    def tokenizar(self) -> List[Token]:
        """Ejecuta el AFD y devuelve la lista completa de tokens (incluye EOF)."""
        tokens: List[Token] = []

        while True:
            c  = self._peek()
            cc = _cc(c)

            # ── 1. String literal: manejo especial ────────────────────────────
            if self._estado == Estado.QS:
                if cc == CC.EOF_CC:
                    self.errores.append(ErrorLexico(
                        "L002", "string sin cerrar",
                        self._tok_lin, self._tok_col,
                        sugerencia='Cierra el string con comillas dobles. Ej: "rojo"',
                    ))
                    tokens.append(Token(TipoToken.EOF, "", self._linea, self._col))
                    break  # recuperación: salir del bucle
                self._buf.append(c)       # type: ignore[arg-type]
                self._avanzar()
                if cc == CC.QUOTE:        # comilla de cierre → emitir
                    tokens.append(self._mk_string())
                    self._reset()
                continue

            # ── 2. Delimitador en estado acumulador → emitir sin consumir ─────
            if cc in _DELIM and self._estado in _ESTADOS_EMIT:
                tok = self._emitir_acumulado()
                if tok is not None:
                    tokens.append(tok)
                self._reset()
                continue                  # reprocesar el delimitador desde Q0

            # ── 3. EOF ─────────────────────────────────────────────────────────
            if cc == CC.EOF_CC:
                if self._estado in _ESTADOS_EMIT:
                    tok = self._emitir_acumulado()
                    if tok is not None:
                        tokens.append(tok)
                elif self._estado not in (Estado.Q0,):
                    self._error_eof()
                tokens.append(Token(TipoToken.EOF, "", self._linea, self._col))
                break

            # ── 4. Transición normal vía tabla ────────────────────────────────
            sig = _TABLA.get((self._estado, cc), Estado.QE)

            if sig == Estado.QE:
                self._error_transicion(c, cc)

            elif sig == Estado.QSYM:
                tokens.append(Token(
                    _SYM_TOKEN[c],           # type: ignore[index]
                    c,                       # type: ignore[arg-type]
                    self._linea, self._col,
                ))
                self._avanzar()
                # buf sigue vacío; estado permanece Q0 (QSYM no acumula)

            elif sig == Estado.Q0:
                # Espacio / newline desde q0: descartar sin acumular
                self._avanzar()

            else:
                # Acumular carácter en el lexema actual
                if not self._buf:
                    self._tok_lin = self._linea
                    self._tok_col = self._col
                self._buf.append(c)          # type: ignore[arg-type]
                self._estado = sig
                self._avanzar()

        return tokens

    # ── Emisión de tokens ─────────────────────────────────────────────────────

    def _emitir_acumulado(self) -> Optional[Token]:
        """Selecciona tipo de token según el estado acumulador y emite."""
        lexema       = "".join(self._buf)
        lin, col     = self._tok_lin, self._tok_col

        if self._estado == Estado.QL:
            return self._mk_palabra(lexema, lin, col)
        if self._estado == Estado.QID4:
            return self._mk_identificador(lexema, lin, col)
        if self._estado == Estado.QD:
            return Token(TipoToken.NUM_DEC, lexema, lin, col)
        if self._estado == Estado.QH1:
            return Token(TipoToken.NUM_HEX, lexema, lin, col)

        raise AssertionError(f"_emitir_acumulado: estado inesperado {self._estado}")

    def _mk_palabra(self, lexema: str, lin: int, col: int) -> Optional[Token]:
        """
        Estado qPR / qTF del AFD formal.
        Consulta los conjuntos de clasificación final SOLO aquí.
        """
        if lexema in _RESERVADAS:
            return Token(TipoToken.PALABRA_RESERVADA, lexema, lin, col)
        if lexema in _TIPOS_FIGURA:
            return Token(TipoToken.TIPO_FIGURA, lexema, lin, col)
        self.errores.append(ErrorLexico(
            "L001", f"palabra desconocida: {lexema!r}", lin, col,
            sugerencia=(
                "Palabras reservadas: create update delete show hide list clear screen help "
                "rotate move copy group ungroup scale. "
                "Tipos de figura: circle  square  triangle  line  pentagon  "
                "rectangle  ellipse  text"
            ),
            col_fin=col + len(lexema) - 1,
        ))
        return None

    def _mk_identificador(self, lexema: str, lin: int, col: int) -> Optional[Token]:
        """
        Estado qIDF del AFD formal.
        Valida que el prefijo de letras sea un tipo de figura válido (L004).
        """
        split   = next(i for i, ch in enumerate(lexema) if ch.isdigit())
        prefijo = lexema[:split]
        if prefijo not in _PREFIJOS_VALIDOS:
            self.errores.append(ErrorLexico(
                "L004",
                f"prefijo de identificador inválido: {prefijo!r}",
                lin, col,
                sugerencia=(
                    "El prefijo debe ser un tipo de figura o 'group' seguido de 4 dígitos. "
                    "Ej: circle0001  square0042  triangle0003  line0010  pentagon0001  "
                    "rectangle0001  ellipse0001  text0001  group0001"
                ),
                col_fin=col + len(prefijo) - 1,
            ))
            return None
        return Token(TipoToken.IDENTIFICADOR, lexema, lin, col)

    def _mk_string(self) -> Token:
        """Estado qSTR del AFD formal.  El buf ya contiene comillas incluidas."""
        return Token(TipoToken.STRING, "".join(self._buf), self._tok_lin, self._tok_col)

    # ── Errores ───────────────────────────────────────────────────────────────

    def _error_transicion(self, c: Optional[str], cc: CC) -> None:
        lin, col = self._linea, self._col
        if self._estado in (Estado.QH, Estado.QH1):
            self.errores.append(ErrorLexico(
                "L003", f"carácter hexadecimal inválido: {c!r}", lin, col,
                sugerencia="El color hexadecimal solo acepta dígitos 0-9 y letras A-F. Ej: #FF00AB",
            ))
        elif self._estado in (Estado.QID1, Estado.QID2, Estado.QID3, Estado.QID4):
            self.errores.append(ErrorLexico(
                "L004", f"dígito esperado en identificador, se obtuvo {c!r}", lin, col,
                sugerencia="El identificador necesita exactamente 4 dígitos numéricos. Ej: circle0001",
            ))
        else:
            self.errores.append(ErrorLexico(
                "L001", f"símbolo inválido: {c!r}", lin, col,
                sugerencia='Caracteres válidos: letras, dígitos, #, ", (, ), [, ], coma, _',
            ))
        # Recuperación: descartar el carácter problemático y volver a Q0
        self._avanzar()
        self._reset()

    def _error_eof(self) -> None:
        lin, col = self._linea, self._col
        if self._estado in (Estado.QID1, Estado.QID2, Estado.QID3):
            self.errores.append(ErrorLexico(
                "L004", "identificador incompleto: faltan dígitos", lin, col,
                sugerencia="El identificador necesita exactamente 4 dígitos. Ej: circle0001",
            ))
        elif self._estado == Estado.QH:
            self.errores.append(ErrorLexico(
                "L003", "'#' sin dígitos hexadecimales", lin, col,
                sugerencia="Especifica al menos un dígito hexadecimal tras #. Ej: #FF o #1A2B3C",
            ))
        else:
            self.errores.append(ErrorLexico(
                "L001", "fin de entrada inesperado", lin, col,
            ))

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _peek(self) -> Optional[str]:
        return self._texto[self._pos] if self._pos < len(self._texto) else None

    def _avanzar(self) -> None:
        if self._pos < len(self._texto):
            if self._texto[self._pos] == '\n':
                self._linea += 1
                self._col    = 1
            else:
                self._col   += 1
            self._pos += 1

    def _reset(self) -> None:
        self._estado = Estado.Q0
        self._buf    = []


# ═══════════════════════════════════════════════════════════════════════════════
# 8 · FUNCIÓN DE CONVENIENCIA
# ═══════════════════════════════════════════════════════════════════════════════

def tokenizar(texto: str) -> Tuple[List[Token], List[ErrorLexico]]:
    """Ejecuta el AFD; devuelve (tokens, errores_léxicos)."""
    lx = Lexer(texto)
    tokens = lx.tokenizar()
    return tokens, lx.errores


# ═══════════════════════════════════════════════════════════════════════════════
# 9 · DEMO / PRUEBAS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    CASOS: List[Tuple[str, str]] = [
        # ── Válidos ──────────────────────────────────────────────────────────
        ("create circle",                       "create sin parámetros"),
        ("create square(\"red\",2,[10,20])",    "create con parámetros"),
        ("create circle(#1F,10,[0,0])",         "color hexadecimal"),
        ("update circle0001(_,3,_)",            "update con wildcard"),
        ("update triangle0045(\"blue\",_,[5,5])","update parcial"),
        ("delete pentagon9999",                 "delete"),
        ("hide circle0001",                     "hide"),
        ("show triangle0045",                   "show"),
        ("list",                                "list"),
        ("clear screen",                        "clear screen"),
        ("help",                                "help"),
        # ── Errores léxicos ──────────────────────────────────────────────────
        ("create @circle",                      "L001 símbolo inválido"),
        ("\"hello",                             "L002 string sin cerrar"),
        ("#ZZ",                                 "L003 hex inválido (G no es hex)"),
        ("#",                                   "L003 '#' sin dígitos"),
        ("circle001",                           "L004 identificador incompleto"),
        ("blah0001",                            "L004 prefijo inválido"),
        ("circle00001",                         "L004 identificador con 5 dígitos"),
    ]

    for texto, etiqueta in CASOS:
        sep = "─" * 62
        print(f"\n{sep}")
        print(f"  [{etiqueta}]  →  {texto!r}")
        print(sep)
        try:
            for tok in tokenizar(texto):
                print(f"  {tok}")
        except ErrorLexico as e:
            print(f"  ✗  {e}")
