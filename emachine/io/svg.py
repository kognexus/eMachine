"""
Small SVG chart writer: lines and coloured cells on linear axes. It exists so that results can
be looked at without installing a plotting library.
"""

import math

FONT = "font-family='Helvetica, Arial, sans-serif'"
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#7f7f7f", "#8c564b"]


def nice_ticks(low, high, target=6):
    """Round tick values covering [low, high]."""
    if not math.isfinite(low) or not math.isfinite(high) or high <= low:
        return [low]
    raw = (high - low) / max(target, 1)
    power = 10 ** math.floor(math.log10(raw))
    step = min((1, 2, 2.5, 5, 10), key=lambda m: abs(m * power - raw)) * power
    first = math.ceil(low / step - 1e-9) * step
    ticks, value = [], first
    while value <= high + 1e-9 * step:
        ticks.append(0.0 if abs(value) < 1e-12 * step else value)
        value += step
    return ticks


def _label(value):
    return f"{value:.6g}"


class Chart:
    """One set of axes. Coordinates of all drawing calls are data values."""

    def __init__(self, x_range, y_range, x_label="", y_label="", title="", width=640, height=400,
                 margin=(64, 150, 44, 52)):
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        if self.x1 <= self.x0:
            self.x1 = self.x0 + 1.0
        if self.y1 <= self.y0:
            self.y1 = self.y0 + 1.0
        self.width, self.height = width, height
        self.left, self.right, self.top, self.bottom = margin
        self.x_label, self.y_label, self.title = x_label, y_label, title
        self.body, self.legend = [], []

    def px(self, x):
        return self.left + (x - self.x0) / (self.x1 - self.x0) * (self.width - self.left - self.right)

    def py(self, y):
        return self.height - self.bottom - (y - self.y0) / (self.y1 - self.y0) * (self.height - self.top - self.bottom)

    def cell(self, x0, x1, y0, y1, color):
        x, y = self.px(x0), self.py(y1)
        self.body.append(f"<rect x='{x:.2f}' y='{y:.2f}' width='{self.px(x1) - x + 0.4:.2f}' "
                         f"height='{self.py(y0) - y + 0.4:.2f}' fill='{color}'/>")

    def line(self, xs, ys, color=None, label=None, dash=None, width=1.8):
        color = color or COLORS[len([e for e in self.legend if e[0] == "line"]) % len(COLORS)]
        points = " ".join(f"{self.px(x):.2f},{self.py(y):.2f}" for x, y in zip(xs, ys)
                          if math.isfinite(x) and math.isfinite(y))
        if points:
            self.body.append(f"<polyline points='{points}' fill='none' stroke='{color}' stroke-width='{width}'"
                             + (f" stroke-dasharray='{dash}'" if dash else "") + "/>")
        if label:
            self.legend.append(("line", color, label, dash))

    def marker(self, x, y, color="#000000", label=None):
        edge = "#000000" if color.lower() == "#ffffff" else "#ffffff"
        self.body.append(f"<circle cx='{self.px(x):.2f}' cy='{self.py(y):.2f}' r='4' fill='{color}' "
                         f"stroke='{edge}' stroke-width='1.2'/>")
        if label:
            self.legend.append(("marker", color, label, None))

    def band(self, color, label):
        self.legend.append(("band", color, label, None))

    def render(self, x_offset=0, y_offset=0):
        w, h = self.width, self.height
        right, bottom = w - self.right, h - self.bottom
        out = [f"<g transform='translate({x_offset},{y_offset})'>",
               f"<rect x='0' y='0' width='{w}' height='{h}' fill='#ffffff'/>",
               f"<clipPath id='clip{id(self)}'><rect x='{self.left}' y='{self.top}' width='{right - self.left}' "
               f"height='{bottom - self.top}'/></clipPath>"]
        grid = []
        for value in nice_ticks(self.x0, self.x1):
            x = self.px(value)
            grid.append(f"<line x1='{x:.2f}' y1='{self.top}' x2='{x:.2f}' y2='{bottom}' stroke='#e3e3e3' stroke-width='0.6'/>")
            out.append(f"<text x='{x:.2f}' y='{bottom + 16}' text-anchor='middle' font-size='11' {FONT}>{_label(value)}</text>")
        for value in nice_ticks(self.y0, self.y1):
            y = self.py(value)
            grid.append(f"<line x1='{self.left}' y1='{y:.2f}' x2='{right}' y2='{y:.2f}' stroke='#e3e3e3' stroke-width='0.6'/>")
            out.append(f"<text x='{self.left - 7}' y='{y + 4:.2f}' text-anchor='end' font-size='11' {FONT}>{_label(value)}</text>")
        out.append(f"<g clip-path='url(#clip{id(self)})'>" + "".join(grid) + "".join(self.body) + "</g>")
        out.append(f"<rect x='{self.left}' y='{self.top}' width='{right - self.left}' height='{bottom - self.top}' "
                   f"fill='none' stroke='#333333' stroke-width='1'/>")
        out.append(f"<text x='{(self.left + right) / 2:.1f}' y='{h - 12}' text-anchor='middle' font-size='12' {FONT}>{self.x_label}</text>")
        out.append(f"<text x='16' y='{(self.top + bottom) / 2:.1f}' text-anchor='middle' font-size='12' {FONT} "
                   f"transform='rotate(-90 16 {(self.top + bottom) / 2:.1f})'>{self.y_label}</text>")
        out.append(f"<text x='{self.left}' y='{self.top - 14}' font-size='13' font-weight='bold' {FONT}>{self.title}</text>")
        y = self.top + 8
        for kind, color, label, dash in self.legend:
            x = right + 12
            if kind == "band":
                out.append(f"<rect x='{x}' y='{y - 8}' width='16' height='11' fill='{color}' stroke='#888888' stroke-width='0.4'/>")
            elif kind == "marker":
                out.append(f"<circle cx='{x + 8}' cy='{y - 3}' r='4' fill='{color}' stroke='#000000' stroke-width='1'/>")
            else:
                out.append(f"<line x1='{x}' y1='{y - 3}' x2='{x + 16}' y2='{y - 3}' stroke='{color}' stroke-width='2'"
                           + (f" stroke-dasharray='{dash}'" if dash else "") + "/>")
            out.append(f"<text x='{x + 22}' y='{y + 1}' font-size='10.5' {FONT}>{label}</text>")
            y += 16
        out.append("</g>")
        return "\n".join(out)


def save(path, charts, columns=1):
    """Writes charts in a grid of `columns` columns to an SVG file."""
    rows = math.ceil(len(charts) / columns)
    cell_w = max(c.width for c in charts)
    cell_h = max(c.height for c in charts)
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{cell_w * columns}' height='{cell_h * rows}' "
             f"viewBox='0 0 {cell_w * columns} {cell_h * rows}'>",
             f"<rect width='{cell_w * columns}' height='{cell_h * rows}' fill='#ffffff'/>"]
    for i, chart in enumerate(charts):
        parts.append(chart.render((i % columns) * cell_w, (i // columns) * cell_h))
    parts.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(parts))
