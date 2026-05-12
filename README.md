# Intérprete de Figuras Geométricas

Intérprete interactivo de comandos para crear, manipular y visualizar figuras geométricas en un canvas. Implementado con Python + tkinter, siguiendo el pipeline clásico de compiladores: **Lexer → Parser → Análisis Semántico → Executor → Vista**.

---

## Tabla de contenidos

- [Arquitectura General](#arquitectura-general)
- [Pipeline de ejecución](#pipeline-de-ejecución)
- [Módulos](#módulos)
  - [lexer.py](#lexerpy--analizador-léxico)
  - [ast_nodes.py](#ast_nodespy--nodos-del-ast)
  - [parser.py](#parserpy--analizador-sintáctico)
  - [semantico.py](#semanticopy--analizador-semántico)
  - [tabla_simbolos.py](#tabla_simbolospy--tabla-de-símbolos)
  - [canvas_view.py](#canvas_viewpy--vista-y-gui)
  - [main.py](#mainpy--punto-de-entrada)
- [Flujo de un comando completo](#flujo-de-un-comando-completo)
- [Comandos del lenguaje](#comandos-del-lenguaje)
- [Errores y códigos](#errores-y-códigos)

---

## Arquitectura General

El proyecto está organizado en módulos completamente **desacoplados**. Cada fase del pipeline es independiente y se comunica con la siguiente únicamente a través de estructuras de datos bien definidas.

```
Texto de entrada
    ↓
lexer.py        → Lista de Tokens
    ↓
parser.py       → AST (Árbol de Sintaxis Abstracta)
    ↓
semantico.py    → TablaSimbolos actualizada + errores semánticos
    ↓
main.py         → Executor (salida en consola)
    ↓
canvas_view.py  → Visualización en tiempo real (tkinter)
```

---

## Pipeline de ejecución

| Fase                | Módulo               | Entrada                          | Salida                                   |
| ------------------- | -------------------- | -------------------------------- | ---------------------------------------- |
| Análisis léxico     | `lexer.py`           | `str` (línea de texto)           | `List[Token]`                            |
| Análisis sintáctico | `parser.py`          | `List[Token]`                    | `ProgramaNode` (AST)                     |
| Análisis semántico  | `semantico.py`       | `ProgramaNode` + `TablaSimbolos` | `TablaSimbolos` + `List[ErrorSemantico]` |
| Ejecución           | `main.py (Executor)` | `ProgramaNode` + `TablaSimbolos` | Mensajes en consola                      |
| Visualización       | `canvas_view.py`     | `TablaSimbolos`                  | Figuras en canvas                        |

---

## Módulos

---

### `lexer.py` — Analizador Léxico

Implementa un **AFD (Autómata Finito Determinista) explícito** con tabla de transiciones carácter a carácter.

#### `class TipoToken` (Enum)

Define los 13 tipos de tokens que reconoce el lenguaje:

| Token                   | Descripción                               | Ejemplo                                            |
| ----------------------- | ----------------------------------------- | -------------------------------------------------- |
| `PALABRA_RESERVADA`     | Comandos del lenguaje                     | `create`, `update`, `delete`                       |
| `TIPO_FIGURA`           | Nombres de figuras válidas                | `circle`, `square`, `triangle`, `line`, `pentagon` |
| `IDENTIFICADOR`         | Nombre de instancia (prefijo + 4 dígitos) | `circle0001`, `square0042`                         |
| `NUM_DEC`               | Número entero decimal                     | `2`, `10`, `100`                                   |
| `NUM_HEX`               | Color hexadecimal                         | `#FF0000`, `#abc`                                  |
| `STRING`                | Cadena entre comillas dobles              | `"red"`, `"azul"`                                  |
| `LPAREN` / `RPAREN`     | Paréntesis                                | `(`, `)`                                           |
| `LBRACKET` / `RBRACKET` | Corchetes                                 | `[`, `]`                                           |
| `COMMA`                 | Separador                                 | `,`                                                |
| `UNDERSCORE`            | Wildcard en update                        | `_`                                                |
| `EOF`                   | Fin de entrada                            | —                                                  |

#### `@dataclass Token`

Estructura **inmutable** que representa un token reconocido.

```python
Token(tipo: TipoToken, lexema: str, linea: int, columna: int)
```

La `columna` permite señalar errores con puntero visual `^^^` en la consola.

#### `class Estado` (Enum)

Estados del AFD:

| Estado       | Rol                                                          |
| ------------ | ------------------------------------------------------------ |
| `Q0`         | Estado inicial / sumidero de espacios                        |
| `QL`         | Leyendo letras (potencial palabra reservada o prefijo de ID) |
| `QID1..QID4` | Leyendo los 4 dígitos del sufijo de un identificador         |
| `QD`         | Leyendo número decimal                                       |
| `QH` / `QH1` | Después de `#` / leyendo dígitos hexadecimales               |
| `QS`         | Dentro de un string literal (manejo especial fuera de tabla) |
| `QSYM`       | Símbolo delimitador de un solo carácter                      |
| `QE`         | Estado de error implícito                                    |

#### `class CC` (Enum)

Clases de carácter (columnas de la tabla de transiciones):
`HEX_ALPHA`, `LETTER`, `DIGIT`, `HASH`, `QUOTE`, `LPAREN`, `RPAREN`, `LBRACKET`, `RBRACKET`, `COMMA`, `UNDER`, `SPACE`, `NEWLINE`, `EOF_CC`, `OTHER`.

#### `_TABLA` (dict)

Tabla de transiciones `(Estado, CC) → Estado`. Corazón del AFD. Cualquier par no definido resulta implícitamente en `QE` (error).

#### `_RESERVADAS` y `_TIPOS_FIGURA` (frozenset)

Solo se consultan al **emitir** un token de estado `QL`, para clasificarlo como `PALABRA_RESERVADA`, `TIPO_FIGURA`, o error léxico `L001`. No participan en el recorrido carácter a carácter.

#### `class Lexer`

Implementa el AFD. Variables de instancia principales:

| Variable               | Descripción                             |
| ---------------------- | --------------------------------------- |
| `_texto`, `_pos`       | Cadena de entrada e índice actual       |
| `_linea`, `_col`       | Posición actual para reporte de errores |
| `_estado`              | Estado actual del AFD                   |
| `_buf`                 | Acumulador del lexema en construcción   |
| `_tok_lin`, `_tok_col` | Posición de inicio del token actual     |
| `errores`              | Lista de `ErrorLexico` encontrados      |

#### `Lexer.tokenizar() → List[Token]`

Loop principal del AFD. Ejecuta 4 casos en orden de prioridad:

1. **Estado `QS` (string):** acepta todo hasta encontrar `"`.
2. **Delimitador en estado acumulador:** emite el token sin consumir el delimitador y reinicia.
3. **EOF:** flush del buffer pendiente, emite `Token(EOF)`.
4. **Transición normal:** consulta `_TABLA`; si resultado es `QSYM` emite símbolo; si `Q0` descarta espacio; si otro estado, acumula carácter.

#### `Lexer._emitir_acumulado() → Optional[Token]`

Selecciona el tipo de token según el estado acumulador:

- `QL` → llama a `_mk_palabra` (clasifica como reservada, tipo figura o error)
- `QID4` → llama a `_mk_identificador` (valida prefijo)
- `QD` → `NUM_DEC`
- `QH1` → `NUM_HEX`

#### `Lexer._mk_identificador(lexema, lin, col)`

Valida que el prefijo del identificador sea un tipo de figura válido. Si no, emite error **L004**.

#### `def tokenizar(texto) → Tuple[List[Token], List[ErrorLexico]]`

Función de conveniencia (API pública del módulo). Instancia `Lexer` y devuelve `(tokens, errores)`.

#### `class ErrorLexico`

| Campo                         | Descripción                                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `codigo`                      | `L001` símbolo inválido · `L002` string sin cerrar · `L003` hexadecimal inválido · `L004` identificador inválido |
| `mensaje`                     | Descripción del error                                                                                            |
| `linea`, `columna`, `col_fin` | Posición en el texto fuente                                                                                      |
| `sugerencia`                  | Texto de ayuda para el usuario                                                                                   |

---

### `ast_nodes.py` — Nodos del AST

Todos los nodos son **dataclasses** sin lógica. El AST representa solo la esencia semántica del programa, sin paréntesis ni comas.

#### Nodos de valor

| Clase             | Campos             | Descripción                                                                   |
| ----------------- | ------------------ | ----------------------------------------------------------------------------- |
| `PosicionNode`    | `x: int, y: int`   | Coordenadas `[x, y]`                                                          |
| `ValorUpdateNode` | `tipo: str, valor` | Un slot de `update`: `"color"`, `"escala"`, `"posicion"` o `"wildcard"` (`_`) |

#### Nodos de parámetros

| Clase                       | Campos                       | Descripción                                  |
| --------------------------- | ---------------------------- | -------------------------------------------- |
| `ParametrosNode`            | `color, escala, posicion`    | Parámetros de `create` para figuras normales |
| `ParametrosLineaNode`       | `color, grosor, inicio, fin` | Parámetros de `create line`                  |
| `ParametrosUpdateNode`      | `color, escala, posicion`    | 3 slots para `update` de figuras normales    |
| `ParametrosUpdateLineaNode` | `color, grosor, inicio, fin` | 4 slots para `update line`                   |

#### Nodos de comandos

| Clase        | Campos                    | Producido por            |
| ------------ | ------------------------- | ------------------------ |
| `CreateNode` | `tipo_figura, parametros` | `create circle(...)`     |
| `UpdateNode` | `id, parametros`          | `update circle0001(...)` |
| `DeleteNode` | `id`                      | `delete circle0001`      |
| `ShowNode`   | `id`                      | `show circle0001`        |
| `HideNode`   | `id`                      | `hide circle0001`        |
| `ListNode`   | —                         | `list`                   |
| `ClearNode`  | `scope`                   | `clear screen`           |
| `HelpNode`   | —                         | `help`                   |
| `RotateNode` | `id, grados`              | `rotate circle0001 (90)` |

#### `ProgramaNode`

Nodo raíz. Contiene `comandos: List[ComandoNode]` — todos los comandos parseados.

#### `ComandoNode` (Union type)

Alias de tipo que agrupa todos los nodos de comandos. Utilizado por el Parser y el Semántico para tipado estático.

---

### `parser.py` — Analizador Sintáctico

Parser **LL(1) descendente recursivo**. Una función por no-terminal de la gramática.

#### Gramática implementada (simplificada)

```
<programa>    ::= { <comando> }
<comando>     ::= <create> | <update> | <delete> | <show> | <hide>
                | <list>   | <clear>  | <help>   | <rotate>

<create>      ::= "create" <tipo_figura>
                | "create" <tipo_figura> "(" <parametros> ")"
<update>      ::= "update" <id> "(" <parametros_update> ")"
<delete>      ::= "delete" <id>
<show>        ::= "show"   <id>
<hide>        ::= "hide"   <id>
<rotate>      ::= "rotate" <id> "(" NUM_DEC ")"
<list>        ::= "list"
<clear>       ::= "clear" "screen"
<help>        ::= "help"

<parametros>  ::= <color> "," <escala> "," <posicion>
<parametros_update> ::= <valor_u> "," <valor_u> "," <valor_u>
<valor_u>     ::= <color> | <escala> | <posicion> | "_"
<posicion>    ::= "[" NUM_DEC "," NUM_DEC "]"
```

#### `class ErrorSintactico`

| Código | Significado                                      |
| ------ | ------------------------------------------------ |
| `S001` | Comando inválido (se esperaba palabra reservada) |
| `S002` | Estructura inválida                              |
| `S003` | Token inesperado                                 |

#### `class Parser`

| Variable    | Descripción                            |
| ----------- | -------------------------------------- |
| `_tokens`   | Lista de tokens del lexer              |
| `_pos`      | Índice del token actual (lookahead)    |
| `errores`   | Lista de `ErrorSintactico` acumulados  |
| `_DISPATCH` | Tabla LL(1): `{lexema → método_parse}` |

#### `Parser.parse() → ProgramaNode`

Punto de entrada. Implementa `<programa> ::= { <comando> }` con **recuperación de errores por modo pánico** (`_sincronizar`): si un comando falla, avanza tokens hasta encontrar la próxima palabra reservada conocida y sigue parseando.

#### `Parser.match(tipo) → Token`

Consume el token actual si su tipo coincide; lanza `S003` si no. Es el método fundamental que avanza `_pos`.

#### `Parser._DISPATCH`

Tabla lookahead LL(1). Mapea cada palabra reservada al método `_parse_*` correspondiente, permitiendo añadir nuevos comandos sin modificar `_parse_comando`.

---

### `semantico.py` — Analizador Semántico

Recorre el AST validando reglas de negocio y **mutando** la `TablaSimbolos`.

#### `class ErrorSemantico`

| Código | Significado                                       |
| ------ | ------------------------------------------------- |
| `M001` | Figura inexistente                                |
| `M002` | Identificador duplicado (figura activa ya existe) |
| `M003` | Tipo de valor inválido en slot de `update`        |
| `M004` | Escala inválida (≤ 0)                             |
| `M005` | Figura eliminada                                  |
| `M006` | `create line` sin los parámetros requeridos       |

#### Variables de módulo

```python
_DEFAULT_COLOR    = "white"
_DEFAULT_ESCALA   = 1
_DEFAULT_POSICION = (0, 0)
```

Valores que se aplican cuando se ejecuta `create <figura>` sin parámetros.

#### `class AnalizadorSemantico`

| Variable    | Descripción                                |
| ----------- | ------------------------------------------ |
| `_tabla`    | Referencia a la `TablaSimbolos` compartida |
| `errores`   | Lista de `ErrorSemantico` acumulados       |
| `_dispatch` | `{tipo_nodo → método_check}`               |

#### `AnalizadorSemantico.analizar(programa) → (TablaSimbolos, List[ErrorSemantico])`

Loop principal. Usa `_dispatch` para seleccionar el método validador por tipo de nodo. Acumula errores en lugar de detenerse (modo tolerante).

#### `_check_create(nodo)`

1. Genera el próximo ID con `siguiente_id(tipo)`.
2. Valida que no exista un ID activo igual (M002).
3. Valida escala > 0 (M004).
4. Inserta `EntradaFigura` en la tabla.

#### `_check_update(nodo)`

1. Obtiene la figura activa (M001/M005).
2. Valida que cada slot sea del tipo correcto con `_validar_slot` (M003).
3. Resuelve wildcards (`_`) conservando el valor anterior.
4. Muta los campos de la `EntradaFigura` directamente.

#### `_check_delete / _check_show / _check_hide (nodo)`

Obtienen la figura activa y mutan `eliminada`, `visible` respectivamente.

#### `_check_rotate(nodo)`

Acumula los grados: `rotacion = (rotacion + grados) % 360`.

#### `_check_clear(nodo)`

Llama a `tabla.vaciar()`, eliminando todas las figuras y reseteando contadores.

#### `_obtener_activa(id) → EntradaFigura`

Centraliza las validaciones **M001** (figura no existe) y **M005** (figura ya eliminada). Usado por `update`, `delete`, `show`, `hide` y `rotate`.

#### `_validar_slot(valor, esperado, slot)`

Verifica que el `ValorUpdateNode` en la posición posicional sea del tipo esperado. Un wildcard (`_`) siempre es válido en cualquier slot.

#### Resolvers de wildcard

| Método                          | Comportamiento                                                             |
| ------------------------------- | -------------------------------------------------------------------------- |
| `_resolver_color(v, actual)`    | Si `wildcard` → retorna `actual`; si no → retorna `str(v.valor)`           |
| `_resolver_escala(v, actual)`   | Si `wildcard` → retorna `actual`; si no → retorna `int(v.valor)`           |
| `_resolver_posicion(v, actual)` | Si `wildcard` → retorna `actual`; si no → retorna `(v.valor.x, v.valor.y)` |

---

### `tabla_simbolos.py` — Tabla de Símbolos

Almacena el estado en memoria de todas las figuras del programa.

#### `@dataclass EntradaFigura`

| Campo       | Tipo              | Descripción                                               |
| ----------- | ----------------- | --------------------------------------------------------- |
| `id`        | `str`             | Identificador único, ej. `circle0001`                     |
| `tipo`      | `str`             | `circle`, `square`, `triangle`, `line`, `pentagon`        |
| `color`     | `str`             | Lexema del color (`"red"`, `#FF0000`, `white`)            |
| `escala`    | `int`             | Tamaño relativo (debe ser > 0)                            |
| `posicion`  | `Tuple[int,int]`  | Coordenada lógica del origen                              |
| `visible`   | `bool`            | `True` = visible en canvas                                |
| `eliminada` | `bool`            | `True` = borrada lógicamente, ignorada en `list` y canvas |
| `pos_fin`   | `Optional[Tuple]` | Punto final, solo para `line`                             |
| `rotacion`  | `int`             | Grados acumulados (0–359)                                 |

#### `class TablaSimbolos`

Diccionario central `id → EntradaFigura`.

| Método                                  | Descripción                                                                                         |
| --------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `siguiente_id(tipo) → str`              | Genera el próximo ID disponible para el tipo: `circle0001`, `circle0002`... Salta IDs ya existentes |
| `insertar(entrada)`                     | Agrega o reemplaza una entrada; actualiza el contador del tipo                                      |
| `obtener(id) → Optional[EntradaFigura]` | Retorna la entrada o `None` si no existe                                                            |
| `existe(id) → bool`                     | Verifica si el ID existe en la tabla                                                                |
| `listar() → List[EntradaFigura]`        | Retorna todas las entradas (incluye eliminadas)                                                     |
| `vaciar()`                              | Limpia la tabla y resetea todos los contadores                                                      |

---

### `canvas_view.py` — Vista y GUI

Ventana tkinter con 3 pestañas + consola integrada. Es la **única clase que conoce tkinter**; el resto del sistema es completamente independiente de la UI.

#### Constantes globales

| Constante                | Valor     | Descripción                                     |
| ------------------------ | --------- | ----------------------------------------------- |
| `GRID`                   | `20`      | Píxeles por unidad lógica de posición           |
| `UNIT`                   | `15`      | Píxeles base para escala = 1                    |
| `BG`, `GRID_MINOR`, etc. | `#xxxxxx` | Paleta de colores **Catppuccin Mocha**          |
| `_TIPO_COLOR`            | dict      | Color de relleno por defecto por tipo de figura |

#### Sistema de coordenadas

- Origen `(0,0)` en la **esquina inferior-izquierda** del área útil.
- `X` crece hacia la derecha, `Y` crece hacia arriba (inverso al canvas nativo de tkinter).
- `_OX`, `_OY` — offsets en píxeles del origen lógico.
- Conversión: `px = OX + x * GRID`, `py = OY - y * GRID`.

#### `def _parse_color(raw, tipo) → str`

Convierte el lexema de color almacenado en la tabla a un color válido para tkinter:

| Entrada   | Salida                                    |
| --------- | ----------------------------------------- |
| `"red"`   | `red`                                     |
| `#F00`    | `#FF0000` (expande RGB corto a 6 dígitos) |
| `#RRGGBB` | pasa directo                              |
| Inválido  | `_TIPO_COLOR[tipo]` (fallback por tipo)   |

#### `class CanvasView`

##### Pestañas

| Pestaña       | Widgets principales       | Contenido                                                |
| ------------- | ------------------------- | -------------------------------------------------------- |
| **Canvas**    | `tk.Canvas`               | Figuras geométricas dibujadas en tiempo real             |
| **Historial** | `_lex_text` + `_sym_text` | Log léxico de tokens + evolución de la tabla de símbolos |
| **AST**       | `_ast_text`               | Árbol sintáctico del último comando parseado             |

##### Métodos públicos principales

| Método                                   | Descripción                                                |
| ---------------------------------------- | ---------------------------------------------------------- |
| `actualizar(tabla)`                      | Borra el canvas y redibuja todas las figuras no eliminadas |
| `write_console(text, tag)`               | Escribe una línea en la consola con el color del tag       |
| `set_command_callback(fn)`               | Registra la función que se llama al presionar Enter        |
| `log_comando(linea, tokens, tabla, ...)` | Registra en el Historial los tokens y snapshot de la tabla |
| `mostrar_ast(linea, ast)`                | Agrega el árbol AST del comando al panel AST               |
| `set_status(msg, level)`                 | Actualiza la barra de estado inferior                      |

##### `_dibujar(e: EntradaFigura)`

Dibuja la figura en el canvas según `e.tipo`:

| Tipo       | Método tkinter   | Notas                                                           |
| ---------- | ---------------- | --------------------------------------------------------------- |
| `circle`   | `create_oval`    | Radio = `escala * UNIT` px                                      |
| `square`   | `create_polygon` | 4 vértices rotados alrededor del centro                         |
| `triangle` | `create_polygon` | 3 vértices rotados alrededor del centro                         |
| `line`     | `create_line`    | Grosor = `escala * 2` px; 2 puntos rotados sobre el punto medio |
| `pentagon` | `create_polygon` | 5 vértices con trigonometría (`cos/sin`), separados 72°         |

Figuras **ocultas** se dibujan sin relleno, con contorno punteado tenue en gris.

##### `_rotate_pts(pts, cx, cy, deg) → List[float]`

Aplica rotación 2D a una lista plana `[x0,y0,x1,y1,...]` alrededor del centroide `(cx,cy)` usando la matriz de rotación estándar:

$$x' = cx + (x - cx)\cos\theta - (y - cy)\sin\theta$$
$$y' = cy + (x - cx)\sin\theta + (y - cy)\cos\theta$$

##### `_draw_grid()`

Dibuja la cuadrícula con líneas menores (cada `GRID` = 20 px) y ejes en `(_OX, _OY)`. Las etiquetas numéricas aparecen cada 5 unidades lógicas sobre los ejes.

##### `_ast_render(nodo, depth, prefix, is_last)`

Renderiza recursivamente el árbol AST con líneas Unicode (`├──`, `└──`) y coloreado semántico:

- Nombres de nodo: azul
- Campos: morado
- Valores: verde
- Wildcards: amarillo
- Ramas: gris

##### Historial de comandos

`_on_history_up/down` permiten navegar comandos anteriores con las teclas **↑↓** en el `Entry` de la consola. Los últimos 10 comandos se guardan en `_history`.

---

### `main.py` — Punto de Entrada

#### `class Executor`

Ejecuta acciones de **salida** después de que el semántico ya validó y actualizó la tabla. Su única responsabilidad es escribir mensajes de confirmación en la consola; **no modifica la tabla**.

| Variable    | Descripción                                    |
| ----------- | ---------------------------------------------- |
| `_tabla`    | Referencia a la `TablaSimbolos` (solo lectura) |
| `_write`    | Función `write_console(text, tag)` de la vista |
| `_dispatch` | `{tipo_nodo → método_exec}`                    |

##### Métodos `_exec_*`

Todos siguen el mismo patrón: leen datos de la tabla (ya actualizada por el semántico) y formatean un mensaje con `_write`.

| Método                    | Acción                                                          |
| ------------------------- | --------------------------------------------------------------- |
| `_exec_create`            | Muestra ID, color, escala y posición de la figura recién creada |
| `_exec_update`            | Muestra el estado actualizado de la figura                      |
| `_exec_delete`            | Muestra confirmación de eliminación                             |
| `_exec_show / _exec_hide` | Muestra confirmación de visibilidad                             |
| `_exec_list`              | Imprime tabla formateada con todas las figuras activas          |
| `_exec_rotate`            | Muestra el ID y la rotación acumulada                           |
| `_exec_clear`             | Muestra confirmación de limpieza                                |
| `_exec_help`              | Imprime la lista completa de comandos disponibles               |

#### `def _write_error(canvas_v, fuente, e)`

Formatea un error con puntero visual (`^^^`) señalando exactamente la columna del error en el texto fuente. Luego escribe el mensaje de error y la sugerencia en la consola.

```
  create circl("red", 2, [0,0])
         ^^^^^
  [L001] Línea 1, Col 8: palabra desconocida: 'circl'
  Sugerencia: Tipos de figura válidos: circle  square  triangle  line  pentagon
```

#### `def _proceso_comando(linea, tabla, executor, canvas_v)`

**Función central del REPL.** Orquesta todo el pipeline para cada línea de entrada:

1. Verifica si es comando de salida (`exit`, `quit`).
2. Llama `tokenizar(linea)` → `Parser(tokens).parse()` → `AnalizadorSemantico(tabla).analizar(ast)`.
3. Si hay errores (léxicos, sintácticos o semánticos): los muestra con `_write_error` y actualiza el canvas.
4. Si no hay errores: `executor.ejecutar(ast)` → `canvas_v.actualizar(tabla)` → `canvas_v.log_comando()` → `canvas_v.mostrar_ast()`.

#### Bloque `if __name__ == "__main__"`

Crea e interconecta todas las instancias:

```python
tabla    = TablaSimbolos()          # estado compartido
root     = tk.Tk()                  # ventana principal
canvas_v = CanvasView(root)         # toda la UI
executor = Executor(tabla, write_fn=canvas_v.write_console)

canvas_v.set_command_callback(
    lambda linea: _proceso_comando(linea, tabla, executor, canvas_v)
)
root.mainloop()
```

---

## Flujo de un comando completo

**Ejemplo:** `create circle("red", 2, [10, 20])`

| Paso              | Módulo           | Resultado                                                                                                                                                                   |
| ----------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Léxico**        | `lexer.py`       | `[PALABRA_RESERVADA:"create", TIPO_FIGURA:"circle", LPAREN, STRING:'"red"', COMMA, NUM_DEC:"2", COMMA, LBRACKET, NUM_DEC:"10", COMMA, NUM_DEC:"20", RBRACKET, RPAREN, EOF]` |
| **Sintáctico**    | `parser.py`      | `CreateNode(tipo_figura="circle", parametros=ParametrosNode(color='"red"', escala=2, posicion=PosicionNode(10, 20)))`                                                       |
| **Semántico**     | `semantico.py`   | Genera ID `circle0001`, valida escala > 0, inserta `EntradaFigura` en la tabla                                                                                              |
| **Ejecución**     | `main.py`        | Escribe `OK: circle0001 (color="red", escala=2, pos=[10, 20])` en consola                                                                                                   |
| **Visualización** | `canvas_view.py` | Dibuja un círculo relleno en posición lógica `(10, 20)` con radio `2 * 15 = 30` píxeles                                                                                     |

---

## Comandos del lenguaje

| Comando         | Sintaxis                                           | Descripción                                              |
| --------------- | -------------------------------------------------- | -------------------------------------------------------- |
| `create`        | `create <tipo>`                                    | Crea figura con valores por defecto                      |
| `create`        | `create <tipo>(color, escala, [x,y])`              | Crea con parámetros explícitos                           |
| `create line`   | `create line(color, grosor, [x1,y1], [x2,y2])`     | Crea línea entre dos puntos                              |
| `update`        | `update <id>(color \| _, escala \| _, [x,y] \| _)` | Modifica uno o más campos (`_` conserva el valor actual) |
| `rotate`        | `rotate <id> (grados)`                             | Rota la figura los grados indicados (acumulativo)        |
| `delete`        | `delete <id>`                                      | Elimina la figura                                        |
| `show`          | `show <id>`                                        | Hace visible la figura                                   |
| `hide`          | `hide <id>`                                        | Oculta la figura (permanece en tabla)                    |
| `list`          | `list`                                             | Lista todas las figuras activas                          |
| `clear screen`  | `clear screen`                                     | Elimina todas las figuras y limpia el canvas             |
| `help`          | `help`                                             | Muestra todos los comandos disponibles                   |
| `exit` / `quit` | `exit`                                             | Cierra el intérprete                                     |

**Tipos de figura válidos:** `circle`, `square`, `triangle`, `line`, `pentagon`

**Reglas del lenguaje:**

- Case-sensitive: `create` es válido, `Create` o `CREATE` no lo son.
- Una instrucción por línea.
- Los espacios son ignorados excepto dentro de strings.
- No soporta comentarios.

---

## Errores y códigos

### Errores Léxicos (`lexer.py`)

| Código | Descripción                                              |
| ------ | -------------------------------------------------------- |
| `L001` | Símbolo o carácter inválido / palabra desconocida        |
| `L002` | String sin cerrar (falta `"` de cierre)                  |
| `L003` | Hexadecimal inválido (carácter no hex después de `#`)    |
| `L004` | Identificador inválido (prefijo no es un tipo de figura) |

### Errores Sintácticos (`parser.py`)

| Código | Descripción                                    |
| ------ | ---------------------------------------------- |
| `S001` | Comando inválido (no es una palabra reservada) |
| `S002` | Estructura inválida                            |
| `S003` | Token inesperado (se esperaba otro tipo)       |

### Errores Semánticos (`semantico.py`)

| Código | Descripción                                                      |
| ------ | ---------------------------------------------------------------- |
| `M001` | Figura inexistente (ID no encontrado en la tabla)                |
| `M002` | Identificador duplicado (ya existe una figura activa con ese ID) |
| `M003` | Tipo de valor inválido en slot de `update`                       |
| `M004` | Escala inválida (valor ≤ 0)                                      |
| `M005` | Figura eliminada (ya no es operable)                             |
| `M006` | `create line` sin los 4 parámetros requeridos                    |
