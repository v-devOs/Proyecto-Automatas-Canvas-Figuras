"""
tabla_simbolos.py — Tabla de Símbolos · Lenguaje de Figuras Geométricas

Almacena el estado actual de todas las figuras creadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRADA DE LA TABLA
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EntradaFigura:
    id:        str
    tipo:      str
    color:     str
    escala:    int
    posicion:  Tuple[int, int]
    visible:   bool = True
    eliminada: bool = False
    pos_fin:   Optional[Tuple[int, int]] = None   # solo para type=="line"
    rotacion:  int  = 0                           # grados acumulados

    def __repr__(self) -> str:
        estado = "ELIMINADA" if self.eliminada else ("oculta" if not self.visible else "visible")
        return (
            f"EntradaFigura(id={self.id!r}, tipo={self.tipo!r}, "
            f"color={self.color!r}, escala={self.escala}, "
            f"posicion={list(self.posicion)}, estado={estado})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TABLA DE SÍMBOLOS
# ═══════════════════════════════════════════════════════════════════════════════

class TablaSimbolos:
    """
    Diccionario id → EntradaFigura.
    Gestiona contadores por tipo para la generación automática de identificadores.
    """

    def __init__(self) -> None:
        self._tabla:     Dict[str, EntradaFigura] = {}
        self._contadores: Dict[str, int]          = {}

    # ── Lectura ───────────────────────────────────────────────────────────────

    def existe(self, id: str) -> bool:
        return id in self._tabla

    def obtener(self, id: str) -> Optional[EntradaFigura]:
        return self._tabla.get(id)

    def listar(self) -> List[EntradaFigura]:
        return list(self._tabla.values())

    # ── Generación de ID ──────────────────────────────────────────────────────

    def siguiente_id(self, tipo: str) -> str:
        """Genera el próximo identificador disponible para el tipo dado."""
        n = self._contadores.get(tipo, 0) + 1
        while True:
            candidato = f"{tipo}{n:04d}"
            if candidato not in self._tabla:
                return candidato
            n += 1

    # ── Escritura ─────────────────────────────────────────────────────────────

    def insertar(self, entrada: EntradaFigura) -> None:
        self._tabla[entrada.id] = entrada
        # Actualizar contador para mantener la secuencia correcta
        sufijo = int(entrada.id[len(entrada.tipo):])
        actual = self._contadores.get(entrada.tipo, 0)
        if sufijo >= actual:
            self._contadores[entrada.tipo] = sufijo

    def vaciar(self) -> None:
        self._tabla.clear()
        self._contadores.clear()

    # ── Representación ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        if not self._tabla:
            return "TablaSimbolos (vacía)"
        lineas = [f"TablaSimbolos ({len(self._tabla)} figura(s)):"]
        for e in self._tabla.values():
            lineas.append(f"  {e}")
        return "\n".join(lineas)
