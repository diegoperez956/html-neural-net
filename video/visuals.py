"""Manim drawing objects. All model arithmetic lives in model.py."""

import textwrap
from manim import (
    AnimationGroup,
    Arrow,
    Circle,
    DOWN,
    LEFT,
    Line,
    Rectangle,
    RIGHT,
    RoundedRectangle,
    Square,
    Text,
    Transform,
    UP,
    VGroup,
    VMobject,
)

BG = "#282828"
PANEL = "#1d2021"
INK = "#ebdbb2"
MUTED = "#a89984"
OFF = "#3c3836"
EDGE = "#665c54"
BLUE = "#83a598"
ORANGE = "#fe8019"
GREEN = "#b8bb26"
RED = "#fb4934"
YELLOW = "#fabd2f"
PURPLE = "#d3869b"


def text(value, size=28, color=INK, mono=False, width=None):
    obj = Text(
        str(value),
        font="JetBrains Mono" if mono else "Noto Sans",
        font_size=size,
        color=color,
        disable_ligatures=False,
    )
    if width and obj.width > width:
        obj.scale_to_fit_width(width)
    return obj


def equation(value, center=(0, 0, 0), size=35, color=INK, width=14):
    return text(value, size=size, color=color, width=width).move_to(center)


class Bit(VGroup):
    def __init__(self, value=0, label=None, side=0.72, color=BLUE):
        super().__init__()
        self.on_color = color
        self.side = side
        self.box = RoundedRectangle(
            width=side,
            height=side,
            corner_radius=0.07,
            stroke_color=EDGE,
            stroke_width=2,
            fill_color=color if value else PANEL,
            fill_opacity=1,
        )
        self.number = text(
            value, size=30 * side / 0.72, color=BG if value else MUTED, mono=True
        ).move_to(self.box)
        self.add(self.box, self.number)
        if label is not None:
            self.add(
                text(label, size=17, color=MUTED).next_to(self.box, DOWN, buff=0.12)
            )

    def change(self, value):
        number = text(
            value, size=30 * self.side / 0.72, color=BG if value else MUTED, mono=True
        ).move_to(self.box)
        return AnimationGroup(
            self.box.animate.set_fill(self.on_color if value else PANEL),
            Transform(self.number, number),
        )


def bit_word(values, signed=False, side=0.72, color=BLUE):
    result = VGroup(
        *[
            Bit(
                v,
                -(1 << (len(values) - 1))
                if signed and i == 0
                else 1 << (len(values) - i - 1),
                side,
                color,
            )
            for i, v in enumerate(values)
        ]
    )
    result.arrange(RIGHT, buff=0.18, aligned_edge=UP)
    return result


class Signal(VGroup):
    def __init__(self, name, value="?", color=BLUE, radius=0.44):
        super().__init__()
        self.ring = Circle(
            radius=radius,
            stroke_color=color,
            stroke_width=2.5,
            fill_color=PANEL,
            fill_opacity=1,
        )
        self.number = text(value, size=29, color=color, mono=True).move_to(self.ring)
        self.name = text(name, size=18, color=INK, width=2.4).next_to(
            self.ring, UP, buff=0.17
        )
        self.add(self.ring, self.number, self.name)

    def change(self, value, color=None):
        return Transform(
            self.number,
            text(value, size=29, color=color or BLUE, mono=True).move_to(self.ring),
        )


def wire(a, b, label=None, color=EDGE):
    start = a.ring.get_center() if isinstance(a, Signal) else a.get_center()
    end = b.ring.get_center() if isinstance(b, Signal) else b.get_center()
    arrow = Arrow(
        start,
        end,
        buff=0.48,
        stroke_width=2.4,
        color=color,
        max_tip_length_to_length_ratio=0.1,
    )
    if label is None:
        return arrow
    tag = text(label, size=19, color=color).move_to(arrow.get_center() + UP * 0.18)
    return VGroup(arrow, tag)


class PixelGrid(VGroup):
    def __init__(self, side=14, size=4.3, values=None, color=ORANGE, numbers=False):
        super().__init__()
        self.side = side
        self.pitch = size / side
        self.on_color = color
        values = values or [0] * (side * side)
        self.cells = VGroup()
        for i, value in enumerate(values):
            cell = Square(
                side_length=self.pitch * 0.95,
                stroke_width=0.8,
                stroke_color=EDGE,
                fill_color=color if value else PANEL,
                fill_opacity=1,
            )
            cell.move_to(
                [
                    (i % side - (side - 1) / 2) * self.pitch,
                    ((side - 1) / 2 - i // side) * self.pitch,
                    0,
                ]
            )
            self.cells.add(cell)
        self.add(self.cells)
        if numbers:
            self.add(
                VGroup(
                    *[
                        text(v, size=11, color=INK).move_to(cell)
                        for cell, v in zip(self.cells, values)
                    ]
                )
            )

    def change(self, values, color=None):
        return AnimationGroup(
            *[
                cell.animate.set_fill((color or self.on_color) if value else PANEL)
                for cell, value in zip(self.cells, values)
            ]
        )

    def block(self, row, col):
        return VGroup(
            *[
                self.cells[(row + dr) * self.side + col + dc]
                for dr in (0, 1)
                for dc in (0, 1)
            ]
        )


def code_panel(code, source, center=(3.8, 0.35, 0), width=6.5):
    lines = []
    for line in code.splitlines():
        if not line.strip():
            lines.append("")
            continue
        indent = len(line) - len(line.lstrip())
        lines.extend(
            textwrap.wrap(
                line,
                width=46,
                subsequent_indent=" " * (indent + 2),
                replace_whitespace=False,
                drop_whitespace=True,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    objects = VGroup()
    for i, line in enumerate(lines):
        content = line.lstrip() or " "
        obj = text(content, size=21, color=INK, mono=True)
        obj.move_to([0, -i * 0.39, 0], aligned_edge=LEFT)
        obj.shift(RIGHT * (len(line) - len(line.lstrip())) * 0.105)
        objects.add(obj)
    if objects.width > width - 0.45:
        objects.scale_to_fit_width(width - 0.45)
    if objects.height > 4.45:
        objects.scale_to_fit_height(4.45)
    backdrop = RoundedRectangle(
        width=width,
        height=max(objects.height + 0.6, 1.1),
        corner_radius=0.12,
        stroke_width=1,
        stroke_color=EDGE,
        fill_color=PANEL,
        fill_opacity=1,
    ).move_to(objects)
    objects.align_to(backdrop, LEFT).shift(RIGHT * 0.22)
    title = text(source, size=15, color=MUTED, width=width).next_to(
        backdrop, UP, buff=0.17
    )
    panel = VGroup(backdrop, objects, title).move_to(center)
    panel.lines = objects
    return panel


def matrix(values, color=INK, cell_width=0.85, cell_height=0.65, size=29):
    rows = len(values)
    cols = len(values[0])
    entries = VGroup()
    for r, row in enumerate(values):
        for c, value in enumerate(row):
            entry = text(value, size=size, color=color, mono=True)
            entry.move_to(
                [
                    (c - (cols - 1) / 2) * cell_width,
                    ((rows - 1) / 2 - r) * cell_height,
                    0,
                ]
            )
            entries.add(entry)
    w, h = cols * cell_width / 2 + 0.1, rows * cell_height / 2 + 0.08
    left = VMobject(stroke_color=MUTED, stroke_width=2).set_points_as_corners(
        [[-w + 0.12, h, 0], [-w, h, 0], [-w, -h, 0], [-w + 0.12, -h, 0]]
    )
    right = VMobject(stroke_color=MUTED, stroke_width=2).set_points_as_corners(
        [[w - 0.12, h, 0], [w, h, 0], [w, -h, 0], [w - 0.12, -h, 0]]
    )
    result = VGroup(entries, left, right)
    result.entries = entries
    return result


def score_chart(values, width=8.2, height=4.5):
    result = VGroup()
    rows = VGroup()
    limit = max(30, max(abs(v) for v in values) + 3)
    unit = (width - 1.7) / (2 * limit)
    zero_x = 0.2
    for i, value in enumerate(values):
        y = height / 2 - i * height / 9
        label = text(str(i), size=22, color=MUTED).move_to([-width / 2, y, 0])
        bar = Rectangle(
            width=max(0.025, abs(value) * unit),
            height=0.27,
            fill_opacity=1,
            fill_color=GREEN if value >= 0 else RED,
            stroke_width=0,
        ).move_to([zero_x + value * unit / 2, y, 0])
        number = text(value, size=21, color=INK, mono=True).move_to([width / 2, y, 0])
        row = VGroup(label, bar, number)
        rows.add(row)
    axis = Line(
        [zero_x, -height / 2 - 0.24, 0], [zero_x, height / 2 + 0.24, 0], color=EDGE
    )
    result.add(axis, rows)
    result.rows = rows
    return result


class SevenSegment(VGroup):
    def __init__(self, digit=None, size=2.3):
        super().__init__()
        from video.model import SEGMENTS

        specs = {
            "a": (0, 1, 0.9, 0.12),
            "b": (0.5, 0.5, 0.12, 0.85),
            "c": (0.5, -0.5, 0.12, 0.85),
            "d": (0, -1, 0.9, 0.12),
            "e": (-0.5, -0.5, 0.12, 0.85),
            "f": (-0.5, 0.5, 0.12, 0.85),
            "g": (0, 0, 0.9, 0.12),
        }
        self.segments = {}
        for name, (x, y, w, h) in specs.items():
            segment = RoundedRectangle(
                width=w,
                height=h,
                corner_radius=0.035,
                stroke_width=0,
                fill_opacity=1,
                fill_color=YELLOW
                if digit is not None and name in SEGMENTS[digit]
                else OFF,
            )
            segment.move_to([x, y, 0])
            self.segments[name] = segment
            self.add(segment)
        self.scale_to_fit_height(size)

    def change(self, digit):
        from video.model import SEGMENTS

        return AnimationGroup(
            *[
                part.animate.set_fill(YELLOW if name in SEGMENTS[digit] else OFF)
                for name, part in self.segments.items()
            ]
        )
