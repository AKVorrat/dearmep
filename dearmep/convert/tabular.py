from __future__ import annotations
import csv
from itertools import chain
import sys
from typing import Any, Iterable, List, Mapping, Optional

from rich.console import Console
from rich.table import Table


class Tabular:
    def __init__(
        self,
        *headers: str,
        rows: Optional[Iterable[Iterable]] = None,
    ):
        self._headers = tuple(headers)
        self._rows: List[tuple] = []
        if rows is not None:
            self.extend(rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, key: int) -> tuple:
        return self._rows[key]

    @classmethod
    def from_mappings(cls, values: Iterable[Mapping[str, Any]]) -> Tabular:
        iter_v = iter(values)
        first = next(iter_v)
        headers = tuple(first.keys())
        rows = chain((first,), iter_v)

        def converter() -> Iterable[tuple]:
            for mapping in rows:
                keys = tuple(mapping.keys())
                if keys != headers:
                    raise ValueError(
                        f"expected input keys to be {headers}, got {keys}")
                row = tuple(mapping.values())
                yield row

        return cls(*headers, rows=converter())

    def append(self, *row: Any):
        self.extend(row)

    def extend(self, *rows: Iterable):
        num_headers = len(self._headers)
        for row_num, row in enumerate(rows, 1):
            values = tuple(row)
            if len(values) != num_headers:
                raise ValueError(
                    f"input row {row_num} has {len(values)} value(s), "
                    f"expected {num_headers}"
                )
            self._rows.append(values)

    def print_to_console(self, console: Console):
        console.print(self.to_rich_table())

    def to_rich_table(self, **kwargs) -> Table:
        t = Table(*self._headers, **kwargs)
        for row in self._rows:
            t.add_row(*row)
        return t


class CSVStreamTabular(Tabular):
    def __init__(
        self,
        *headers: str,
        rows: Optional[Iterable[Iterable]] = None,
    ):
        super().__init__(*headers, rows=rows)
        self._csvw = csv.writer(sys.stdout)
        self._csvw.writerow(self._headers)

    def extend(self, *rows: Iterable):
        num_headers = len(self._headers)
        for row_num, row in enumerate(rows, 1):
            values = tuple(row)
            if len(values) != num_headers:
                raise ValueError(
                    f"input row {row_num} has {len(values)} value(s), "
                    f"expected {num_headers}"
                )
            self._csvw.writerow(row)

    def print_to_console(self, console: Console):
        # We have already printed our stuff, nothing to do here.
        pass