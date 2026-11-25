"""Parse a small analytical SQL grammar and compile an independent parameterized query."""

import re
from dataclasses import dataclass
from typing import Literal

MAX_SQL = 4096
MAX_ROWS = 50
MAX_COLUMNS = 12
MAX_CELL = 256
MAX_OUTPUT = 96 * 1024

TOKEN = re.compile(
    r"""(?P<space>[ \t\r\n]+)|(?P<string>'(?:[^']|'')*')|"""
    r"""(?P<name>"[A-Za-z_][A-Za-z_0-9]{0,62}"|[A-Za-z_][A-Za-z_0-9]{0,62})|"""
    r"""(?P<number>[0-9]{1,12}(?:\.[0-9]{1,8})?)|(?P<operator><=|>=|<>|!=|[(),.*;+/<>=-])"""
)
FUNCTIONS = {
    "COUNT": (1, 1),
    "SUM": (1, 1),
    "AVG": (1, 1),
    "MIN": (1, 1),
    "MAX": (1, 1),
    "LOWER": (1, 1),
    "UPPER": (1, 1),
    "LENGTH": (1, 1),
    "ABS": (1, 1),
    "ROUND": (1, 2),
    "COALESCE": (2, 4),
}
CASTS = {"BIGINT": "BIGINT", "DOUBLE": "DOUBLE", "DATE": "DATE", "MONEY": "DECIMAL(18,2)"}
PRECEDENCE = {
    "OR": 1,
    "AND": 2,
    "=": 3,
    "<>": 3,
    "!=": 3,
    "<": 3,
    ">": 3,
    "<=": 3,
    ">=": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
}
Scalar = str | int | float | bool


class PolicyDenied(ValueError):
    """A static message describes which part of the allowed grammar to use."""


@dataclass(frozen=True)
class Expression:
    kind: Literal["column", "literal", "call", "binary", "cast", "star", "null", "isnull"]
    value: Scalar
    children: tuple["Expression", ...] = ()

    def render(self, params: list[Scalar]) -> str:
        if self.kind == "literal":
            params.append(self.value)
            return "?"
        if self.kind == "column":
            return quote(str(self.value))
        if self.kind == "star":
            return "*"
        if self.kind == "null":
            return "NULL"
        args = [child.render(params) for child in self.children]
        if self.kind == "binary":
            return f"({args[0]} {self.value} {args[1]})"
        if self.kind == "isnull":
            return f"({args[0]} IS {'NOT ' if self.value else ''}NULL)"
        if self.kind == "cast":
            return f"TRY_CAST({args[0]} AS {CASTS[str(self.value)]})"
        return f"{self.value}({', '.join(args)})"


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@dataclass(frozen=True)
class Select:
    projections: tuple[tuple[Expression, str | None], ...]
    distinct: bool
    predicate: Expression | None
    groups: tuple[str, ...]
    order: tuple[tuple[str, bool], ...]
    limit: int | None

    def compile(self) -> tuple[str, list[Scalar]]:
        params: list[Scalar] = []
        columns = [
            expression.render(params) + (f" AS {quote(alias)}" if alias is not None else "")
            for expression, alias in self.projections
        ]
        distinct = "DISTINCT " if self.distinct else ""
        sql = f'SELECT {distinct}{", ".join(columns)} FROM "data"'
        if self.predicate is not None:
            sql += " WHERE " + self.predicate.render(params)
        if self.groups:
            sql += " GROUP BY " + ", ".join(map(quote, self.groups))
        if self.order:
            terms = [quote(name) + (" DESC" if desc else " ASC") for name, desc in self.order]
            sql += " ORDER BY " + ", ".join(terms)
        sql += f" LIMIT {self.limit if self.limit is not None else MAX_ROWS + 1}"
        return sql, params


def tokenize(sql: str) -> list[tuple[str, str]]:
    if not sql or len(sql) > MAX_SQL or "\0" in sql:
        raise PolicyDenied("Provide one SQL query of at most 4096 characters.")
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(sql):
        match = TOKEN.match(sql, position)
        if match is None or match.lastgroup is None:
            raise PolicyDenied("The query contains unsupported SQL syntax.")
        if match.lastgroup != "space":
            tokens.append((match.lastgroup, match.group()))
        if len(tokens) > 256:
            raise PolicyDenied("Simplify the query to at most 256 SQL tokens.")
        position = match.end()
    return [*tokens, ("end", "")]


class Parser:
    def __init__(self, sql: str, columns: set[str]) -> None:
        self.tokens = tokenize(sql)
        self.position = 0
        self.columns = {name.lower() for name in columns}

    @property
    def current(self) -> tuple[str, str]:
        return self.tokens[self.position]

    def take(self, value: str) -> bool:
        if self.current[1].upper() != value:
            return False
        self.position += 1
        return True

    def need(self, value: str, message: str = "Use one supported SELECT from data.") -> None:
        if not self.take(value):
            raise PolicyDenied(message)

    def name(self) -> str:
        kind, token = self.current
        if kind != "name":
            raise PolicyDenied("Use a column name or a simple alias.")
        self.position += 1
        return token.strip('"').lower()

    def column(self) -> str:
        value = self.name()
        if value not in self.columns:
            raise PolicyDenied("Reference a column listed in the dataset schema.")
        return value

    def atom(self, depth: int) -> Expression:
        if self.take("("):
            nested = self.expression(depth=depth + 1)
            self.need(")")
            return nested
        kind, token = self.current
        if kind == "string":
            self.position += 1
            value = token[1:-1].replace("''", "'")
            if len(value) > MAX_CELL:
                raise PolicyDenied("Use text literals of at most 256 characters.")
            return Expression("literal", value)
        if kind == "number":
            self.position += 1
            return Expression("literal", float(token) if "." in token else int(token))
        if self.take("NULL"):
            return Expression("null", "")
        if self.take("TRUE"):
            return Expression("literal", True)
        if self.take("FALSE"):
            return Expression("literal", False)
        name = self.name()
        if not self.take("("):
            if name not in self.columns:
                raise PolicyDenied("Reference a column listed in the dataset schema.")
            return Expression("column", name)
        function = name.upper()
        if function == "TRY_CAST":
            subject = self.expression(depth=depth + 1)
            self.need("AS")
            target = self.name().upper()
            if target == "DECIMAL":
                self.need("(")
                self.need("18")
                self.need(",")
                self.need("2")
                self.need(")")
                target = "MONEY"
            elif target not in {"BIGINT", "DOUBLE", "DATE"}:
                raise PolicyDenied("Cast to BIGINT, DOUBLE, DATE, or DECIMAL(18,2).")
            self.need(")")
            return Expression("cast", target, (subject,))
        if function not in FUNCTIONS:
            raise PolicyDenied("Use a supported aggregate or scalar function.")
        if function == "COUNT" and self.take("*"):
            args = [Expression("star", "")]
        else:
            args = [self.expression(depth=depth + 1)]
            while self.take(","):
                args.append(self.expression(depth=depth + 1))
        self.need(")")
        minimum, maximum = FUNCTIONS[function]
        if not minimum <= len(args) <= maximum:
            raise PolicyDenied("The function received an unsupported number of arguments.")
        return Expression("call", function, tuple(args))

    def expression(self, minimum: int = 1, depth: int = 0) -> Expression:
        if depth >= 16:
            raise PolicyDenied("Simplify the nesting in the query.")
        left = self.atom(depth)
        while True:
            if minimum <= 3 and self.take("IS"):
                negated = self.take("NOT")
                self.need("NULL", "Use IS NULL or IS NOT NULL for missing values.")
                left = Expression("isnull", negated, (left,))
                continue
            precedence = PRECEDENCE.get(self.current[1].upper(), 0)
            if precedence < minimum:
                break
            operator = self.current[1].upper()
            self.position += 1
            right = self.expression(precedence + 1, depth + 1)
            left = Expression("binary", operator, (left, right))
        return left

    def parse(self) -> Select:
        self.need("SELECT", "Only one SELECT from data is allowed.")
        distinct = self.take("DISTINCT")
        projections = []
        aliases = set()
        while True:
            expression = self.expression()
            alias = self.name() if self.take("AS") else None
            if alias is not None and alias in aliases:
                raise PolicyDenied("Use distinct aliases for result columns.")
            aliases.add(alias)
            projections.append((expression, alias))
            if len(projections) > MAX_COLUMNS:
                raise PolicyDenied("Select at most 12 result columns.")
            if not self.take(","):
                break
        self.need("FROM")
        self.need("DATA", "Query only the unqualified data table.")
        predicate = self.expression() if self.take("WHERE") else None
        groups = []
        if self.take("GROUP"):
            self.need("BY")
            groups.append(self.column())
            while self.take(","):
                groups.append(self.column())
        ordering = []
        if self.take("ORDER"):
            self.need("BY")
            while True:
                name = self.name()
                if name not in self.columns and name not in aliases:
                    raise PolicyDenied("Order by a dataset column or an explicit result alias.")
                descending = self.take("DESC")
                if not descending:
                    self.take("ASC")
                ordering.append((name, descending))
                if not self.take(","):
                    break
        limit = None
        if self.take("LIMIT"):
            kind, raw = self.current
            if kind != "number" or not raw.isascii() or not raw.isdigit():
                raise PolicyDenied("Use a literal LIMIT between 1 and 50.")
            self.position += 1
            limit = int(raw)
            if not 1 <= limit <= MAX_ROWS:
                raise PolicyDenied("Use a literal LIMIT between 1 and 50.")
        self.take(";")
        if self.current[0] != "end":
            raise PolicyDenied("Use one SELECT with supported clauses and no extra statements.")
        return Select(
            tuple(projections), distinct, predicate, tuple(groups), tuple(ordering), limit
        )


def parse_select(sql: str, columns: set[str]) -> Select:
    return Parser(sql, columns).parse()
