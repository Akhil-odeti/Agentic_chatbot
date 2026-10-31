"""Pydantic spec per chart type. These are what the LLM fills in."""
import re
from typing import Annotated, Literal, Optional, Union

from css_colors import CSS_COLORS
from pydantic import BaseModel, Field, field_validator, model_validator

import config

_NAMED = CSS_COLORS
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class _Base(BaseModel):
    title: str
    colors: Optional[list[str]] = Field(
        default=None, description="Optional colors by CSS name (e.g. 'red') or hex ('#ff0000')."
    )
    x_title: Optional[str] = None
    y_title: Optional[str] = None
    computed: bool = Field(
        default=False,
        description="True ONLY if the values were calculated from numbers in the conversation "
        "(sums, averages, percentages). Never set it for estimates or numbers from memory.",
    )

    @field_validator("colors")
    @classmethod
    def _check_colors(cls, v):
        for c in v or []:
            if not (_HEX.match(c) or c.lower() in _NAMED):
                raise ValueError(f"Unknown color '{c}'. Use a CSS color name or hex like #1f77b4.")
        return v


class Series(BaseModel):
    name: str
    values: list[float]


class Group(BaseModel):
    name: str
    values: list[float] = Field(min_length=1)


class _XSeries(_Base):
    x: list[str]
    series: list[Series] = Field(min_length=1)

    @model_validator(mode="after")
    def _lengths(self):
        for s in self.series:
            if len(s.values) != len(self.x):
                raise ValueError(
                    f"Series '{s.name}' has {len(s.values)} values but x has {len(self.x)} labels."
                )
        return self


class BarSpec(_Base):
    type: Literal["bar"]
    x: list[str]
    y: list[float]

    @model_validator(mode="after")
    def _lengths(self):
        if len(self.x) != len(self.y) or not self.x:
            raise ValueError(f"x has {len(self.x)} items but y has {len(self.y)}.")
        return self


class GroupedBarSpec(_XSeries):
    type: Literal["grouped_bar"]


class StackedBarSpec(_XSeries):
    type: Literal["stacked_bar"]


class LineSpec(_XSeries):
    type: Literal["line"]


class AreaSpec(_XSeries):
    type: Literal["area"]


class PieSpec(_Base):
    type: Literal["pie"]
    labels: list[str]
    values: list[float]
    donut: bool = False

    @model_validator(mode="after")
    def _check(self):
        if len(self.labels) != len(self.values) or not self.labels:
            raise ValueError(f"labels has {len(self.labels)} items but values has {len(self.values)}.")
        if any(v < 0 for v in self.values):
            raise ValueError("Pie values must be non-negative.")
        return self


class ScatterSpec(_Base):
    type: Literal["scatter"]
    x: list[float]
    y: list[float]

    @model_validator(mode="after")
    def _lengths(self):
        if len(self.x) != len(self.y) or not self.x:
            raise ValueError(f"x has {len(self.x)} items but y has {len(self.y)}.")
        return self


class HistogramSpec(_Base):
    type: Literal["histogram"]
    values: list[float] = Field(min_length=1)
    bins: Optional[int] = Field(default=None, ge=1, le=200)


class BoxSpec(_Base):
    type: Literal["box"]
    groups: list[Group] = Field(min_length=1)


class HeatmapSpec(_Base):
    type: Literal["heatmap"]
    x: list[str]
    y: list[str]
    z: list[list[float]]

    @model_validator(mode="after")
    def _shape(self):
        if len(self.z) != len(self.y) or any(len(r) != len(self.x) for r in self.z):
            raise ValueError(
                f"z must be {len(self.y)} rows (len(y)) by {len(self.x)} columns (len(x))."
            )
        return self


ChartSpec = Annotated[
    Union[
        BarSpec, GroupedBarSpec, StackedBarSpec, LineSpec, AreaSpec,
        PieSpec, ScatterSpec, HistogramSpec, BoxSpec, HeatmapSpec,
    ],
    Field(discriminator="type"),
]


class ChartRequest(BaseModel):
    charts: list[ChartSpec] = Field(min_length=1, max_length=config.MAX_CHARTS)
