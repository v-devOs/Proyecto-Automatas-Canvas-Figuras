"""
ast_nodes.py — Nodos del Árbol de Sintaxis Abstracta (AST)

Cada nodo representa un constructo del lenguaje de figuras geométricas.
El AST NO contiene paréntesis, comas ni detalles sintácticos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


# ═══════════════════════════════════════════════════════════════════════════════
# NODOS DE VALORES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PosicionNode:
    """[x, y] — coordenadas enteras."""
    x: int
    y: int

    def __repr__(self) -> str:
        return f"[{self.x}, {self.y}]"


@dataclass
class ValorUpdateNode:
    """
    Un valor en un slot de update.

    tipo  : "color" | "escala" | "posicion" | "wildcard"
    valor : str (color), int (escala), PosicionNode, o None (wildcard)
    """
    tipo:  str
    valor: Optional[Union[str, int, PosicionNode]]

    def __repr__(self) -> str:
        if self.tipo == "wildcard":
            return "_"
        return f"{self.tipo}({self.valor!r})"


# ═══════════════════════════════════════════════════════════════════════════════
# NODOS DE PARÁMETROS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ParametrosNode:
    """Parámetros completos de un create: color, escala y posición."""
    color:    str           # lexema STRING o NUM_HEX
    escala:   int
    posicion: PosicionNode


@dataclass
class ParametrosLineaNode:
    """Parámetros de create line: color, grosor, punto de inicio y punto de fin."""
    color:  str
    grosor: int
    inicio: PosicionNode
    fin:    PosicionNode


@dataclass
class ParametrosUpdateNode:
    """
    Tres slots posicionales de un update.
    El slot 1 corresponde a color, 2 a escala, 3 a posición.
    Cada uno puede ser su valor o wildcard (_).
    La validación de compatibilidad tipo-slot es responsabilidad del semántico.
    """
    color:    ValorUpdateNode
    escala:   ValorUpdateNode
    posicion: ValorUpdateNode


@dataclass
class ParametrosUpdateLineaNode:
    """
    Cuatro slots para update de line: color, grosor, inicio, fin.
    Cada uno puede ser su valor o wildcard (_).
    """
    color:  ValorUpdateNode
    grosor: ValorUpdateNode
    inicio: ValorUpdateNode
    fin:    ValorUpdateNode


@dataclass
class ParametrosRectanguloNode:
    """Parámetros de create rectangle: color, ancho, alto, posicion."""
    color:    str
    ancho:    int
    alto:     int
    posicion: PosicionNode


@dataclass
class ParametrosElipseNode:
    """Parámetros de create ellipse: color, rx (radio horizontal), ry (radio vertical), posicion."""
    color:    str
    rx:       int
    ry:       int
    posicion: PosicionNode


@dataclass
class ParametrosTextoNode:
    """Parámetros de create text: color, tamaño de fuente, posicion y contenido."""
    color:     str
    tamanio:   int
    posicion:  PosicionNode
    contenido: str


@dataclass
class ParametrosUpdateRectanguloNode:
    """Cuatro slots para update rectangle: color, ancho, alto, posicion."""
    color:    ValorUpdateNode
    ancho:    ValorUpdateNode
    alto:     ValorUpdateNode
    posicion: ValorUpdateNode


@dataclass
class ParametrosUpdateElipseNode:
    """Cuatro slots para update ellipse: color, rx, ry, posicion."""
    color:    ValorUpdateNode
    rx:       ValorUpdateNode
    ry:       ValorUpdateNode
    posicion: ValorUpdateNode


@dataclass
class ParametrosUpdateTextoNode:
    """Cuatro slots para update text: color, tamaño, posicion, contenido."""
    color:     ValorUpdateNode
    tamanio:   ValorUpdateNode
    posicion:  ValorUpdateNode
    contenido: ValorUpdateNode  # tipo="contenido" o "wildcard"


# ═══════════════════════════════════════════════════════════════════════════════
# NODOS DE COMANDOS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CreateNode:
    tipo_figura: str
    parametros:  Optional[Union[ParametrosNode, "ParametrosLineaNode"]] = None


@dataclass
class UpdateNode:
    id:         str
    parametros: Union[ParametrosUpdateNode, "ParametrosUpdateLineaNode"]


@dataclass
class DeleteNode:
    id: str


@dataclass
class ShowNode:
    id: str


@dataclass
class HideNode:
    id: str


@dataclass
class ListNode:
    pass


@dataclass
class ClearNode:
    scope: str   # siempre "screen"


@dataclass
class HelpNode:
    pass


@dataclass
class RotateNode:
    id:     str
    grados: int


@dataclass
class MoveNode:
    """Desplazamiento relativo: move <id> (dx, dy)"""
    id: str
    dx: int
    dy: int


@dataclass
class CopyNode:
    """Duplicar figura: copy <id>"""
    id: str   # ID de la figura fuente


@dataclass
class GroupNode:
    """Agrupar figuras: group <id1> <id2> ..."""
    ids: List[str]   # IDs de figuras a agrupar (mínimo 2)


@dataclass
class UngroupNode:
    """Disolver grupo: ungroup <gid>"""
    id: str   # ID del grupo


@dataclass
class ScaleNode:
    """Escalar de forma relativa: scale <id> (factor)"""
    id:     str
    factor: int   # multiplicador relativo (> 0); nueva_escala = escala_actual * factor


# ═══════════════════════════════════════════════════════════════════════════════
# NODO RAÍZ
# ═══════════════════════════════════════════════════════════════════════════════

ComandoNode = Union[
    CreateNode, UpdateNode, DeleteNode,
    ShowNode, HideNode, ListNode, ClearNode, HelpNode,
    RotateNode, MoveNode, CopyNode, GroupNode, UngroupNode, ScaleNode,
]


@dataclass
class ProgramaNode:
    comandos: List[ComandoNode] = field(default_factory=list)
