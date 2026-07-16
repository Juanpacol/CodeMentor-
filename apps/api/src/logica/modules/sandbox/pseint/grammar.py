"""Lark grammar for the PSeInt subset actually taught in class (RF-26): the
core control structures, arithmetic/logical expressions, and I/O — enough to
validate syntax and drive the tracer, without trying to be a full PSeInt
reimplementation.

Every control structure wraps its statement list in a named `block` (or
`then_block`/`else_block`) rule rather than splicing `stmt*` directly into
the parent — Lark drops the anonymous keyword tokens ("Entonces", "SiNo"...)
from the tree, so without a named boundary there'd be no way to tell where
the "then" statements end and the "else" statements begin."""

PSEINT_GRAMMAR = r"""
start: "Proceso"i NAME block "FinProceso"i

block: stmt*
then_block: stmt*
else_block: stmt*

stmt: definir_stmt
    | asignacion_stmt
    | escribir_stmt
    | leer_stmt
    | si_stmt
    | mientras_stmt
    | para_stmt
    | repetir_stmt

definir_stmt: "Definir"i NAME ("," NAME)* "Como"i TIPO ";"?
TIPO: "Entero"i | "Real"i | "Caracter"i | "Cadena"i | "Logico"i

asignacion_stmt: NAME "<-" expr ";"?

escribir_stmt: "Escribir"i expr ("," expr)* ";"?

leer_stmt: "Leer"i NAME ("," NAME)* ";"?

si_stmt: "Si"i expr "Entonces"i then_block ("SiNo"i else_block)? "FinSi"i

mientras_stmt: "Mientras"i expr "Hacer"i block "FinMientras"i

para_stmt: "Para"i NAME "<-" expr "Hasta"i expr ("Con"i "Paso"i expr)? "Hacer"i block "FinPara"i

repetir_stmt: "Repetir"i block "Hasta"i "Que"i expr ";"?

?expr: or_expr

?or_expr: and_expr
    | or_expr OR_OP and_expr -> binop
OR_OP: "O"i

?and_expr: not_expr
    | and_expr AND_OP not_expr -> binop
AND_OP: "Y"i

?not_expr: comparison
    | NOT_OP not_expr -> not_op
NOT_OP: "No"i

?comparison: sum
    | sum COMPOP sum -> binop
COMPOP: "<>" | "<=" | ">=" | "=" | "<" | ">"

?sum: product
    | sum SUM_OP product -> binop
SUM_OP: "+" | "-"

?product: unary
    | product PROD_OP unary -> binop
PROD_OP: "*" | "/" | "%"

?unary: power
    | "-" unary -> neg

?power: atom
    | atom "^" unary -> binop_pow

?atom: NUMBER -> number
    | STRING -> string
    | "Verdadero"i -> true_lit
    | "Falso"i -> false_lit
    | NAME -> var
    | "(" expr ")"

NAME: /[a-zA-Z_][a-zA-Z0-9_]*/
NUMBER: /\d+(\.\d+)?/
STRING: /"[^"]*"/

COMMENT: /\/\/[^\n]*/
%ignore COMMENT
%ignore /[ \t\r\n]+/
"""
