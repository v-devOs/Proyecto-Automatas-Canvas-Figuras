# Especificación Técnica Completa del Lenguaje de Figuras Geométricas

# 1. Objetivo del Sistema

El sistema es un intérprete de comandos especializado en manipulación de figuras geométricas.

El sistema NO es un compilador tradicional.
El sistema NO genera código objeto.
El sistema procesa instrucciones directamente y ejecuta operaciones en memoria.

El sistema implementa:

- análisis léxico
- análisis sintáctico
- análisis semántico
- generación de AST
- ejecución

El sistema debe ser modular.
Cada fase debe estar desacoplada de las demás.

---

# 2. Flujo General del Sistema

```plaintext id="pk03xp"
Texto de entrada
    ↓
Lexer
    ↓
Lista de Tokens
    ↓
Parser LL(1)
    ↓
AST
    ↓
Análisis Semántico
    ↓
Executor
    ↓
Actualización de Tabla de Símbolos
```

---

# 3. Reglas Generales del Lenguaje

# 3.1 Sensibilidad

El lenguaje es completamente case-sensitive.

## Correcto

```plaintext id="shfl0u"
create circle
```

## Incorrecto

```plaintext id="n1x0xv"
Create Circle
CREATE CIRCLE
```

---

# 3.2 Espacios

Los espacios en blanco son ignorados por el lexer excepto dentro de strings.

## Correcto

```plaintext id="9jx14m"
create     circle
```

```plaintext id="m6l8qy"
create circle ( "red" , 2 , [10,20] )
```

---

# 3.3 Fin de instrucción

Cada línea representa exactamente una instrucción.

NO se permite:

```plaintext id="2j07fx"
create circle create square
```

---

# 3.4 Comentarios

Actualmente el lenguaje NO soporta comentarios.

Cualquier símbolo fuera del alfabeto definido debe producir error léxico.

---

# 4. Alfabeto del Lenguaje

# 4.1 Letras válidas

```plaintext id="u6hx9x"
a-z
A-Z
```

NOTA:
Las palabras reservadas solo son válidas en minúsculas.

---

# 4.2 Dígitos válidos

```plaintext id="g6hl0q"
0-9
```

---

# 4.3 Caracteres hexadecimales válidos

```plaintext id="z5z4sn"
0-9
A-F
a-f
```

---

# 4.4 Símbolos válidos

```plaintext id="0r8e93"
(
)
[
]
,
_
"
#
```

---

# 5. Tokens del Sistema

# 5.1 PALABRA_RESERVADA

## Lexemas válidos

```plaintext id="qjlwm0"
create
update
delete
show
hide
list
clear
screen
help
```

---

# 5.2 TIPO_FIGURA

## Lexemas válidos

```plaintext id="f29ztm"
circle
square
triangle
line
pentagon
```

---

# 5.3 IDENTIFICADOR

# Estructura obligatoria

```plaintext id="b8te12"
TIPO_FIGURA + 4 dígitos
```

## Ejemplos válidos

```plaintext id="p05f1v"
circle0001
square9999
triangle0045
```

## Ejemplos inválidos

```plaintext id="pq4m4g"
circle1
circle001
circle00001
circulo0001
circleABCD
```

---

# 5.4 NUM_DEC

## Reglas

- únicamente enteros positivos
- sin signo negativo
- sin punto decimal

## Correctos

```plaintext id="n0bhmw"
1
25
999
```

## Incorrectos

```plaintext id="ktw7kg"
-1
3.14
```

---

# 5.5 NUM_HEX

# Formato obligatorio

```plaintext id="t5d2km"
# seguido de al menos un hexadecimal válido
```

## Correctos

```plaintext id="9mjlwm"
#A
#1F
#ABC
```

## Incorrectos

```plaintext id="s2n0jp"
#
#ZZ
#1G
```

---

# 5.6 STRING

# Formato obligatorio

```plaintext id="a4bqjw"
"contenido"
```

## Correctos

```plaintext id="4kkj8j"
"red"
"hello"
"circle"
```

## Incorrectos

```plaintext id="w1jpc2"
"red
red"
```

---

# 6. Gramática Formal

# 6.1 Programa

```plaintext id="oz0u1t"
<programa> ::= { <comando> }
```

El programa es una secuencia de comandos.

---

# 6.2 Comando

```plaintext id="xk7v7l"
<comando> ::= <create>
            | <update>
            | <delete>
            | <show>
            | <hide>
            | <list>
            | <clear>
            | <help>
```

---

# 6.3 Create

```plaintext id="2llhkm"
<create> ::= "create" <tipo_figura>
           | "create" <tipo_figura> "(" <parametros> ")"
```

---

# 6.4 Update

```plaintext id="w0n6xa"
<update> ::= "update" <identificador> "(" <parametros_update> ")"
```

---

# 6.5 Delete

```plaintext id="v96qtw"
<delete> ::= "delete" <identificador>
```

---

# 6.6 Show

```plaintext id="n9rf1u"
<show> ::= "show" <identificador>
```

---

# 6.7 Hide

```plaintext id="5n2r7x"
<hide> ::= "hide" <identificador>
```

---

# 6.8 List

```plaintext id="qjlwm1"
<list> ::= "list"
```

---

# 6.9 Clear

```plaintext id="r7b7qj"
<clear> ::= "clear" "screen"
```

---

# 6.10 Help

```plaintext id="7f4rcl"
<help> ::= "help"
```

---

# 6.11 Parámetros

```plaintext id="0v3rrz"
<parametros> ::= <color> "," <escala> "," <posicion>
```

---

# 6.12 Parámetros Update

```plaintext id="ik4xlg"
<parametros_update> ::= <valor_update>
                      "," <valor_update>
                      "," <valor_update>
```

---

# 6.13 Valor Update

```plaintext id="qk0y1f"
<valor_update> ::= <color>
                 | <escala>
                 | <posicion>
                 | "_"
```

---

# 7. Lexer

# 7.1 Responsabilidad

El lexer recibe texto plano.

El lexer produce una lista secuencial de tokens.

El lexer NO interpreta significado.
El lexer NO valida lógica semántica.

---

# 7.2 Formato de Token

## Estructura obligatoria

```plaintext id="djlwmr"
Token:
- type
- lexeme
- line
- column
```

---

# 7.3 Ejemplo real

## Entrada

```plaintext id="4kwt3u"
create circle("red",2,[10,20])
```

## Tokens

```plaintext id="6djq7m"
[
  CREATE,
  TIPO_FIGURA(circle),
  LPAREN,
  STRING("red"),
  COMMA,
  NUM_DEC(2),
  COMMA,
  LBRACKET,
  NUM_DEC(10),
  COMMA,
  NUM_DEC(20),
  RBRACKET,
  RPAREN
]
```

---

# 8. AFD Oficial

# 8.1 Restricciones obligatorias

El lexer:

- debe recorrer carácter por carácter
- debe mantener estado actual
- debe mantener lexema actual
- debe emitir token únicamente en estado final
- debe reiniciar el autómata tras emitir token

---

# 8.2 Estado q0

# Responsabilidad

Estado inicial.
Decide qué subproceso ejecutar.

---

# Entradas válidas

| Entrada | Acción |
| ------- | ------ |
| letra   | qL     |
| dígito  | qD     |
| #       | qH     |
| "       | qS     |
| símbolo | qSYM   |
| espacio | q0     |
| otro    | qE     |

---

# 8.3 Estado qL

# Responsabilidad

Reconocer:

- palabras reservadas
- tipos de figura
- prefijo de identificador

---

# Comportamiento

## letra

Permanece en qL.

## dígito

Transición a qID1.

## fin de palabra

Clasificación:

### si lexema ∈ reservadas

→ qPR

### si lexema ∈ tipos_figura

→ qTF

### cualquier otro caso

→ qE

---

# 8.4 Estados qID1-qID4

# Responsabilidad

Validar exactamente 4 dígitos.

---

# Restricciones

## qID1

Debe recibir dígito.

## qID2

Debe recibir dígito.

## qID3

Debe recibir dígito.

## qID4

Debe recibir:

- whitespace
- EOF
- símbolo delimitador

Cualquier otro valor es error.

---

# Regla final

Si se consumieron exactamente 4 dígitos:

→ qIDF

---

# 8.5 Estado qD

# Responsabilidad

Reconocer enteros decimales.

---

# Reglas

## dígito

Permanece en qD.

## whitespace o delimitador

→ qNUM

## cualquier otro

→ qE

---

# 8.6 Estado qH

# Responsabilidad

Validar inicio hexadecimal.

---

# Reglas

Después de # debe existir mínimo 1 hexadecimal válido.

---

# Correcto

```plaintext id="yjlwm8"
#A
#1F
```

---

# Incorrecto

```plaintext id="a87z3u"
#
#ZZ
```

---

# 8.7 Estado qH1

# Responsabilidad

Consumir hexadecimal completo.

---

# Reglas

## hexadecimal válido

Permanece en qH1.

## whitespace o delimitador

→ qHEX

## otro

→ qE

---

# 8.8 Estado qS

# Responsabilidad

Consumir string.

---

# Reglas

## cualquier caracter ≠ "

Permanece en qS.

## "

→ qSTR

## EOF

→ qE

---

# 9. Parser

# 9.1 Tipo

```plaintext id="xjlwm9"
LL(1)
Descendente recursivo
```

---

# 9.2 Restricciones

- una función por no terminal
- consumo secuencial
- un token lookahead

---

# 9.3 Función match

Debe:

- validar token esperado
- avanzar token actual
- lanzar error sintáctico si falla

---

# 10. AST

# 10.1 Responsabilidad

Representar estructura lógica del programa.

El AST NO debe contener:

- paréntesis
- comas
- detalles sintácticos innecesarios

---

# 10.2 Estructura obligatoria

# CreateNode

| Campo       | Tipo           |
| ----------- | -------------- |
| tipo_figura | string         |
| parametros  | ParametrosNode |

---

# UpdateNode

| Campo      | Tipo                 |
| ---------- | -------------------- |
| id         | string               |
| parametros | ParametrosUpdateNode |

---

# DeleteNode

| Campo | Tipo   |
| ----- | ------ |
| id    | string |

---

# ShowNode

| Campo | Tipo   |
| ----- | ------ |
| id    | string |

---

# HideNode

| Campo | Tipo   |
| ----- | ------ |
| id    | string |

---

# ListNode

Sin atributos.

---

# ClearNode

| Campo | Tipo   |
| ----- | ------ |
| scope | string |

Valor obligatorio:

```plaintext id="ev9jlwm"
screen
```

---

# 11. Tabla de Símbolos

# 11.1 Responsabilidad

Almacenar estado actual del sistema.

---

# 11.2 Estructura obligatoria

| Campo     | Tipo           |
| --------- | -------------- |
| id        | string         |
| tipo      | string         |
| color     | string         |
| escala    | int            |
| posicion  | tuple<int,int> |
| visible   | bool           |
| eliminada | bool           |

---

# 11.3 Reglas

## create

Inserta nueva figura.

## update

Modifica figura existente.

## delete

eliminada = true

## hide

visible = false

## show

visible = true

## clear screen

vacía completamente tabla.

---

# 12. Executor

# Restricción crítica

El executor NO debe consumir tokens.

El executor SOLO consume AST validado.

---

# Flujo obligatorio

```plaintext id="qjlwm2"
AST válido
    ↓
Executor
    ↓
Tabla de símbolos
```

---

# 13. Errores

# 13.1 Léxicos

| Código | Descripción            |
| ------ | ---------------------- |
| L001   | símbolo inválido       |
| L002   | string sin cerrar      |
| L003   | hexadecimal inválido   |
| L004   | identificador inválido |

---

# 13.2 Sintácticos

| Código | Descripción         |
| ------ | ------------------- |
| S001   | comando inválido    |
| S002   | estructura inválida |
| S003   | token inesperado    |

---

# 13.3 Semánticos

| Código | Descripción             |
| ------ | ----------------------- |
| M001   | figura inexistente      |
| M002   | identificador duplicado |
| M003   | tipo inválido           |
| M004   | escala inválida         |
| M005   | figura eliminada        |

---

# 14. Ejemplos Válidos

```plaintext id="jlwmr3"
create circle
```

```plaintext id="jlwmr4"
create square("red",2,[10,20])
```

```plaintext id="jlwmr5"
update circle0001(_,3,_)
```

```plaintext id="jlwmr6"
hide circle0001
```

```plaintext id="jlwmr7"
show circle0001
```

```plaintext id="jlwmr8"
list
```

```plaintext id="jlwmr9"
clear screen
```

---

# 15. Ejemplos Inválidos

## Error léxico

```plaintext id="jlwmr0"
create @circle
```

---

## Error sintáctico

```plaintext id="jlwmsa"
create circle("red" 2 [10,20])
```

---

## Error semántico

```plaintext id="jlwmsb"
show circle9999
```
