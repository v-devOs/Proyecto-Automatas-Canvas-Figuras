from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


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
    NOMBRE_VAR        = "NOMBRE_VAR"
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
#     Los estados de trie se nombran  "kw_<prefijo>"  y son strings,
#     no miembros del enum Estado, para permitir generación dinámica.
#     El resto de estados especiales sí son miembros del enum.
# ═══════════════════════════════════════════════════════════════════════════════

class Estado(Enum):
    Q0     = "q0"      # inicial / sumidero de espacios
    QL_VAR = "qL_var"  # acumulando letras que no siguen ninguna rama del trie
    QID1   = "qID1"    # 1er dígito del identificador
    QID2   = "qID2"    # 2do dígito
    QID3   = "qID3"    # 3er dígito
    QID4   = "qID4"    # 4to dígito → listo para emitir en delimitador
    QD     = "qD"      # leyendo dígitos decimales
    QNEG   = "qNEG"    # después de '-'
    QH     = "qH"      # después de '#'
    QH1    = "qH1"     # leyendo dígitos hexadecimales
    QS     = "qS"      # dentro de string literal
    QE     = "qE"      # sumidero de error
    QSYM   = "qSYM"    # símbolo de un carácter (accept inmediato)

# Tipo unión: estado puede ser Estado (enum) o str (nodo de trie)
_Estado = object   # Estado | str — solo para anotaciones


# ═══════════════════════════════════════════════════════════════════════════════
# 3 · CLASES DE CARÁCTER  (columnas de la tabla de transiciones)
# ═══════════════════════════════════════════════════════════════════════════════

class CC(Enum):
    HEX_ALPHA = "hex_alpha"
    LETTER    = "letter"
    DIGIT     = "digit"
    HASH      = "hash"
    QUOTE     = "quote"
    MINUS     = "minus"
    LPAREN    = "lparen"
    RPAREN    = "rparen"
    LBRACKET  = "lbracket"
    RBRACKET  = "rbracket"
    COMMA     = "comma"
    UNDER     = "under"
    SPACE     = "space"
    NEWLINE   = "newline"
    EOF_CC    = "eof"
    OTHER     = "other"


_HEX_CHARS: FrozenSet[str] = frozenset("ABCDEFabcdef")

_DELIM: FrozenSet[CC] = frozenset({
    CC.SPACE, CC.NEWLINE, CC.EOF_CC,
    CC.LPAREN, CC.RPAREN,
    CC.LBRACKET, CC.RBRACKET,
    CC.COMMA, CC.UNDER,
})

_SYM_TOKEN: Dict[str, TipoToken] = {
    '(': TipoToken.LPAREN,
    ')': TipoToken.RPAREN,
    '[': TipoToken.LBRACKET,
    ']': TipoToken.RBRACKET,
    ',': TipoToken.COMMA,
    '_': TipoToken.UNDERSCORE,
}


def _cc(c: Optional[str]) -> CC:
    if c is None:        return CC.EOF_CC
    if c in _HEX_CHARS:  return CC.HEX_ALPHA
    if c.isalpha():      return CC.LETTER
    if c.isdigit():      return CC.DIGIT
    _MAP: Dict[str, CC] = {
        '#': CC.HASH,     '"': CC.QUOTE,    '-': CC.MINUS,
        '(': CC.LPAREN,   ')': CC.RPAREN,
        '[': CC.LBRACKET, ']': CC.RBRACKET,
        ',': CC.COMMA,    '_': CC.UNDER,
    }
    if c in _MAP:        return _MAP[c]
    if c in ' \t':       return CC.SPACE
    if c in '\n\r':      return CC.NEWLINE
    return CC.OTHER


# ═══════════════════════════════════════════════════════════════════════════════
# 4 · GENERADOR DE TRIE  —  construye la tabla de transiciones para keywords
#
#   Para cada keyword "abcde" de tipo T se crea la cadena de estados:
#       Q0 ─a─→ kw_a ─b─→ kw_ab ─c─→ kw_abc ─d─→ kw_abcd ─e─→ kw_abcde
#   El estado final  kw_abcde  queda registrado en _ESTADO_TOKEN[kw_abcde] = T.
#
#   Si desde un nodo del trie llega una letra que NO tiene rama definida,
#   la transición apunta a  QL_VAR  (sigue acumulando para NOMBRE_VAR).
#
#   Si desde un nodo final de TIPO_FIGURA llega un dígito → QID1 (identificador).
#   Si desde un nodo final de PREFIJO_ID (tipos + "group") llega un dígito → QID1.
# ═══════════════════════════════════════════════════════════════════════════════

# Diccionario:  nombre_de_estado_trie → TipoToken  (solo estados finales)
_ESTADO_TOKEN: Dict[str, TipoToken] = {}

# Conjunto de todos los estados del trie (nodos intermedios + finales)
_ESTADOS_TRIE: Set[str] = set()

# Conjunto de estados trie que son finales de TIPO_FIGURA o "group"
# (desde ellos un dígito arranca el sufijo del identificador)
_TRIE_PREFIJO_ID: Set[str] = set()

# Tabla de transiciones principal.
# Clave: (estado: Estado | str, carácter: str)  → estado destino: Estado | str
# Se usa carácter literal, no CC, para los nodos del trie (máxima precisión).
_TABLA_TRIE: Dict[Tuple[object, str], object] = {}


def _nombre_nodo(prefijo: str) -> str:
    return f"kw_{prefijo}"


def _registrar_keyword(palabra: str, tipo: TipoToken) -> None:
    """Inserta una keyword en el trie de estados."""
    estado_ant: object = Estado.Q0
    for i, ch in enumerate(palabra):
        nodo = _nombre_nodo(palabra[: i + 1])
        _ESTADOS_TRIE.add(nodo)
        clave = (estado_ant, ch)
        if clave not in _TABLA_TRIE:          # no sobreescribir rama ya definida
            _TABLA_TRIE[clave] = nodo
        estado_ant = nodo
    # El último nodo es el estado final para esta keyword
    estado_final = _nombre_nodo(palabra)
    _ESTADO_TOKEN[estado_final] = tipo


# ── Registro de todas las keywords ──────────────────────────────────────────

_RESERVADAS_LIST = [
    "create", "update", "delete", "show",    "hide",
    "list",   "clear",  "screen", "help",    "rotate",
    "move",   "copy",   "group",  "ungroup", "scale",
    "set",
]

_TIPOS_FIGURA_LIST = [
    "circle", "square", "triangle", "line", "pentagon",
    "rectangle", "ellipse", "text",
]

for _kw in _RESERVADAS_LIST:
    _registrar_keyword(_kw, TipoToken.PALABRA_RESERVADA)

for _tf in _TIPOS_FIGURA_LIST:
    _registrar_keyword(_tf, TipoToken.TIPO_FIGURA)

# Marcar los nodos finales de prefijos válidos de identificador
_PREFIJOS_ID_LIST = _TIPOS_FIGURA_LIST + ["group"]
for _pf in _PREFIJOS_ID_LIST:
    _TRIE_PREFIJO_ID.add(_nombre_nodo(_pf))


# ── Completar el trie: para cualquier letra/hex no cubierta en un nodo
#    del trie, la transición cae a QL_VAR.
#    También: desde QL_VAR, cualquier letra/hex sigue en QL_VAR.

def _es_letra_o_hex(c: str) -> bool:
    return c.isalpha() or c in _HEX_CHARS


_LETRAS_POSIBLES = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)

# Desde Q0: letras no cubiertas por el trie → QL_VAR
for _ch in _LETRAS_POSIBLES:
    if (Estado.Q0, _ch) not in _TABLA_TRIE:
        _TABLA_TRIE[(Estado.Q0, _ch)] = Estado.QL_VAR

# Desde cada nodo del trie: letras no cubiertas → QL_VAR
for _nodo in list(_ESTADOS_TRIE):
    for _ch in _LETRAS_POSIBLES:
        if (_nodo, _ch) not in _TABLA_TRIE:
            _TABLA_TRIE[(_nodo, _ch)] = Estado.QL_VAR

# Desde QL_VAR: cualquier letra → QL_VAR
for _ch in _LETRAS_POSIBLES:
    _TABLA_TRIE[(Estado.QL_VAR, _ch)] = Estado.QL_VAR


# ═══════════════════════════════════════════════════════════════════════════════
# 5 · TABLA DE TRANSICIONES PRINCIPAL
#     Cubre estados numéricos, hexadecimales y los estados de base.
#     Se fusiona con _TABLA_TRIE en el bucle del lexer.
# ═══════════════════════════════════════════════════════════════════════════════

# Esta tabla usa CC (clase de carácter) para los estados no-trie,
# igual que la versión anterior.
_TABLA_CC: Dict[Tuple[object, CC], object] = {

    # ── Q0: estado inicial ────────────────────────────────────────────────────
    (Estado.Q0, CC.DIGIT):    Estado.QD,
    (Estado.Q0, CC.HASH):     Estado.QH,
    (Estado.Q0, CC.QUOTE):    Estado.QS,
    (Estado.Q0, CC.MINUS):    Estado.QNEG,
    (Estado.Q0, CC.LPAREN):   Estado.QSYM,
    (Estado.Q0, CC.RPAREN):   Estado.QSYM,
    (Estado.Q0, CC.LBRACKET): Estado.QSYM,
    (Estado.Q0, CC.RBRACKET): Estado.QSYM,
    (Estado.Q0, CC.COMMA):    Estado.QSYM,
    (Estado.Q0, CC.UNDER):    Estado.QSYM,
    (Estado.Q0, CC.SPACE):    Estado.Q0,
    (Estado.Q0, CC.NEWLINE):  Estado.Q0,

    # ── QNEG ─────────────────────────────────────────────────────────────────
    (Estado.QNEG, CC.DIGIT): Estado.QD,

    # ── QD: dígitos decimales ─────────────────────────────────────────────────
    (Estado.QD, CC.DIGIT): Estado.QD,

    # ── QH / QH1: hexadecimal ─────────────────────────────────────────────────
    (Estado.QH,  CC.DIGIT):     Estado.QH1,
    (Estado.QH,  CC.HEX_ALPHA): Estado.QH1,
    (Estado.QH1, CC.DIGIT):     Estado.QH1,
    (Estado.QH1, CC.HEX_ALPHA): Estado.QH1,

    # ── QID1 – QID4: sufijo numérico ──────────────────────────────────────────
    (Estado.QID1, CC.DIGIT): Estado.QID2,
    (Estado.QID2, CC.DIGIT): Estado.QID3,
    (Estado.QID3, CC.DIGIT): Estado.QID4,

    # ── QL_VAR + dígito: el prefijo es inválido pero el sufijo puede completarse
    #    para emitir un error L004 más preciso en vez de L001
    (Estado.QL_VAR, CC.DIGIT): Estado.QID1,
}

# Estados cuyos delimitadores disparan la emisión del token acumulado
_ESTADOS_EMIT_ENUM = frozenset({
    Estado.QL_VAR, Estado.QID4, Estado.QD, Estado.QH1,
})


# ═══════════════════════════════════════════════════════════════════════════════
# 6 · ERROR LÉXICO
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorLexico(Exception):
    """
    Códigos:
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
    Analizador léxico basado en AFD 100% por transiciones.

    Estrategia de lookup en dos pasos:
        1. Buscar (estado_actual, carácter_literal) en _TABLA_TRIE.
           Esto cubre todos los nodos del trie de keywords.
        2. Si no está, buscar (estado_actual, clase_CC) en _TABLA_CC.
           Esto cubre estados numéricos, hex y los demás.
        3. Si tampoco está → QE (error).

    Estados de emisión:
        · Nodo trie final + delimitador  → emite PALABRA_RESERVADA / TIPO_FIGURA
        · Nodo trie final de prefijo_id + dígito → QID1 (identificador)
        · QL_VAR + delimitador           → emite NOMBRE_VAR
        · QID4 + delimitador             → emite IDENTIFICADOR
        · QD   + delimitador             → emite NUM_DEC
        · QH1  + delimitador             → emite NUM_HEX
    """

    def __init__(self, texto: str) -> None:
        self._texto   = texto
        self._pos     = 0
        self._linea   = 1
        self._col     = 1
        self._estado: object = Estado.Q0
        self._buf:    List[str] = []
        self._tok_lin = 1
        self._tok_col = 1
        self.errores: List[ErrorLexico] = []

    # ── API pública ───────────────────────────────────────────────────────────

    def tokenizar(self) -> List[Token]:
        tokens: List[Token] = []

        while True:
            c  = self._peek()
            cc = _cc(c)

            # ── 1. String literal ─────────────────────────────────────────────
            if self._estado == Estado.QS:
                if cc == CC.EOF_CC:
                    self.errores.append(ErrorLexico(
                        "L002", "string sin cerrar",
                        self._tok_lin, self._tok_col,
                        sugerencia='Cierra el string con comillas dobles. Ej: "rojo"',
                    ))
                    tokens.append(Token(TipoToken.EOF, "", self._linea, self._col))
                    break
                self._buf.append(c)       # type: ignore[arg-type]
                self._avanzar()
                if cc == CC.QUOTE:
                    tokens.append(self._mk_string())
                    self._reset()
                continue

            # ── 2. Delimitador en nodo trie final → emitir keyword/tipo ───────
            if cc in _DELIM and isinstance(self._estado, str) and self._estado in _ESTADO_TOKEN:
                tokens.append(Token(
                    _ESTADO_TOKEN[self._estado],
                    "".join(self._buf),
                    self._tok_lin, self._tok_col,
                ))
                self._reset()
                continue

            # ── 3. Delimitador en estado acumulador enum ──────────────────────
            if cc in _DELIM and self._estado in _ESTADOS_EMIT_ENUM:
                tok = self._emitir_acumulado_enum()
                if tok is not None:
                    tokens.append(tok)
                self._reset()
                continue

            # ── 4. EOF ────────────────────────────────────────────────────────
            if cc == CC.EOF_CC:
                # Flush de trie final
                if isinstance(self._estado, str) and self._estado in _ESTADO_TOKEN:
                    tokens.append(Token(
                        _ESTADO_TOKEN[self._estado],
                        "".join(self._buf),
                        self._tok_lin, self._tok_col,
                    ))
                elif self._estado in _ESTADOS_EMIT_ENUM:
                    tok = self._emitir_acumulado_enum()
                    if tok is not None:
                        tokens.append(tok)
                elif self._estado not in (Estado.Q0,):
                    self._error_eof()
                tokens.append(Token(TipoToken.EOF, "", self._linea, self._col))
                break

            # ── 5. Dígito desde nodo trie final de prefijo de id → QID1 ──────
            if (cc == CC.DIGIT
                    and isinstance(self._estado, str)
                    and self._estado in _TRIE_PREFIJO_ID):
                if not self._buf:
                    self._tok_lin = self._linea
                    self._tok_col = self._col
                self._buf.append(c)       # type: ignore[arg-type]
                self._estado = Estado.QID1
                self._avanzar()
                continue

            # ── 6. Dígito desde nodo trie final que NO es prefijo de id ──────
            if (cc == CC.DIGIT
                    and isinstance(self._estado, str)
                    and self._estado in _ESTADO_TOKEN
                    and self._estado not in _TRIE_PREFIJO_ID):
                # Tratar la keyword como NOMBRE_VAR y continuar con dígito
                # (caso raro pero correcto: "set123" → QL_VAR + dígitos)
                self._estado = Estado.QL_VAR
                self._buf.append(c)       # type: ignore[arg-type]
                self._avanzar()
                continue

            # ── 7. Transición normal: buscar en _TABLA_TRIE primero ──────────
            sig = _TABLA_TRIE.get((self._estado, c))

            # Si no hay rama literal, buscar por clase CC
            if sig is None:
                sig = _TABLA_CC.get((self._estado, cc), Estado.QE)

            if sig == Estado.QE:
                self._error_transicion(c, cc)
                continue

            if sig == Estado.QSYM:
                tokens.append(Token(
                    _SYM_TOKEN[c],           # type: ignore[index]
                    c,                       # type: ignore[arg-type]
                    self._linea, self._col,
                ))
                self._avanzar()
                continue

            if sig == Estado.Q0:
                self._avanzar()
                continue

            # Acumular
            if not self._buf:
                self._tok_lin = self._linea
                self._tok_col = self._col
            self._buf.append(c)           # type: ignore[arg-type]
            self._estado = sig
            self._avanzar()

        return tokens

    # ── Emisión de tokens acumulados (estados enum) ───────────────────────────

    def _emitir_acumulado_enum(self) -> Optional[Token]:
        lexema   = "".join(self._buf)
        lin, col = self._tok_lin, self._tok_col

        if self._estado == Estado.QL_VAR:
            return Token(TipoToken.NOMBRE_VAR, lexema, lin, col)
        if self._estado == Estado.QID4:
            return self._mk_identificador(lexema, lin, col)
        if self._estado == Estado.QD:
            return Token(TipoToken.NUM_DEC, lexema, lin, col)
        if self._estado == Estado.QH1:
            return Token(TipoToken.NUM_HEX, lexema, lin, col)

        raise AssertionError(f"_emitir_acumulado_enum: estado inesperado {self._estado}")

    def _mk_identificador(self, lexema: str, lin: int, col: int) -> Optional[Token]:
        """Valida que el prefijo de letras sea un prefijo de id válido (L004)."""
        split   = next(i for i, ch in enumerate(lexema) if ch.isdigit())
        prefijo = lexema[:split]
        if prefijo not in set(_PREFIJOS_ID_LIST):
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

