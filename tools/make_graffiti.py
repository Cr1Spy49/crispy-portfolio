"""Build the graffiti sprite, clean four-point stars, and outlined wordmark.
Optional build tooling: fontTools. Run: python3 tools/make_graffiti.py
The site serves the generated SVG directly and needs no build dependencies.
"""
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
ORANGE = '#ff7629'
CHALK = '#f1dfc6'
INK = '#101017'


def redraw(path, seed):
    rng = random.Random(seed)
    # Only coordinate paths are used here (no SVG arc flags).
    return re.sub(r'-?\d+(?:\.\d+)?', lambda match: f'{float(match[0]) + rng.uniform(-1.15, 1.15):.2f}', path)


def stroke(path, color=ORANGE, width=4, opacity=1, fill='none'):
    return f'<path d="{path}" fill="{fill}" stroke="{color}" stroke-width="{width}" opacity="{opacity}" stroke-linecap="round" stroke-linejoin="round"/>'


def four_point(cx, cy, rx, ry):
    """Four sharp tips with inward-curving sides, matching the shape of ✧."""
    return (f'M{cx} {cy-ry} '
            f'C{cx+rx*.13} {cy-ry*.27} {cx+rx*.27} {cy-ry*.13} {cx+rx} {cy} '
            f'C{cx+rx*.27} {cy+ry*.13} {cx+rx*.13} {cy+ry*.27} {cx} {cy+ry} '
            f'C{cx-rx*.13} {cy+ry*.27} {cx-rx*.27} {cy+ry*.13} {cx-rx} {cy} '
            f'C{cx-rx*.27} {cy-ry*.13} {cx-rx*.13} {cy-ry*.27} {cx} {cy-ry}Z')


def star_four():
    return stroke(four_point(155, 155, 135, 142), ORANGE, 4)


def comet_head():
    return stroke(four_point(82, 82, 53, 58), CHALK, 3.2)


def comet_trail():
    return (stroke('M113 109 C153 150 213 188 282 207', ORANGE, 3, .8)
            + stroke('M110 126 C150 180 189 214 240 246', CHALK, 1.6, .55)
            + stroke('M142 112 C184 139 226 154 275 161', ORANGE, 1.6, .4))


def wordmark():
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    # Renamed subset of Knewave; see media/fonts/knewave-OFL.txt.
    font = TTFont(ROOT / 'media' / 'fonts' / 'crispy-logo-source.woff')
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    outline, bounds = SVGPathPen(glyphs), BoundsPen(glyphs)
    offset = 0
    for character in 'CriSpy':
        name = cmap[ord(character)]
        matrix = (1, 0, 0, 1, offset, 0)
        glyphs[name].draw(TransformPen(outline, matrix))
        glyphs[name].draw(TransformPen(bounds, matrix))
        offset += font['hmtx'][name][0]
    xmin, ymin, xmax, ymax = bounds.bounds
    scale = min(285 / (xmax - xmin), 76 / (ymax - ymin))
    transform = f'translate({20-xmin*scale:.4f} {99+ymin*scale:.4f}) scale({scale:.6f} {-scale:.6f})'
    path = f'<path transform="{transform}" d="{outline.getCommands()}"/>'
    result = '<g transform="rotate(-5 170 65)">'
    result += f'<g fill="{ORANGE}" transform="translate(3 4)">{path}</g>'
    result += f'<g fill="{CHALK}">{path}</g>'
    result += stroke('M24 114 Q153 96 310 105', ORANGE, 4.5)
    result += '</g>'
    result += stroke(four_point(345, 42, 22, 31), ORANGE, 3.5)
    return result


def tag(frame):
    # Loose marker letters spell CRISPY; underline and overshoots are intentional.
    paths = [
        'M72 99 C17 59 5 164 66 130 M99 72 L74 144 M90 103 C142 47 146 104 95 111 L131 145',
        'M158 66 L137 139 M151 64 L170 59 M128 145 L149 140',
        'M217 59 C163 48 170 91 204 94 C247 97 205 145 172 132',
        'M244 66 L222 147 M240 83 C307 44 305 114 236 116',
        'M287 70 L303 103 L328 61 M303 103 L286 146',
        'M27 163 Q170 130 326 157 M68 184 Q171 161 284 168',
    ]
    return ''.join(stroke(redraw(path, 200 + frame * 8 + i), CHALK if i == 5 else ORANGE, 3 if i == 5 else 5) for i, path in enumerate(paths))


def swoop(frame):
    paths = [
        'M79 24 C183 10 185 59 89 97 C-10 137 52 190 121 162 C223 119 170 215 66 251',
        'M53 58 C1 76 74 111 126 119 C200 132 151 175 68 198',
        'M55 246 L64 269 L89 250',
    ]
    return ''.join(stroke(redraw(path, 300 + frame * 8 + i), CHALK if i == 1 else ORANGE, 3.5 if i == 1 else 5) for i, path in enumerate(paths))


def smile(frame):
    result = stroke(redraw('M49 43 C4 60 17 157 89 175 C150 195 196 150 185 83 C178 35 97 15 49 43Z', 400 + frame), CHALK, 4)
    result += stroke(redraw('M65 76 L59 96 M115 75 L108 96 M48 119 Q93 160 141 119', 410 + frame), ORANGE, 6)
    result += stroke(redraw('M181 30 L191 16 M202 59 L220 53 M38 183 L30 199 M156 177 L169 192', 420 + frame), ORANGE, 3)
    return result


def arrow(frame):
    paths = [
        'M29 138 Q115 24 231 79 L209 25 L298 91 L201 139 L221 91 C144 57 92 98 65 153',
        'M43 174 L39 196 M63 166 L67 182 M107 118 Q145 100 173 111',
    ]
    return ''.join(stroke(redraw(path, 500 + frame * 8 + i), ORANGE if i == 0 else CHALK, 4 if i == 0 else 2.5) for i, path in enumerate(paths))


def main():
    drawings = [('tag', tag, '0 0 350 210'), ('swoop', swoop, '0 0 230 290'),
                ('smile', smile, '0 0 240 220'), ('arrow', arrow, '0 0 330 220')]
    symbols = []
    for name, draw, viewbox in drawings:
        for frame in range(3):
            symbols.append(f'<symbol id="{name}-{frame}" viewBox="{viewbox}">{draw(frame)}</symbol>')
    for name, draw, viewbox in [('star-four', star_four, '0 0 310 310'),
                                ('comet-head', comet_head, '0 0 320 290'),
                                ('comet-trail', comet_trail, '0 0 320 290'),
                                ('wordmark', wordmark, '0 0 380 130')]:
        symbols.append(f'<symbol id="{name}" viewBox="{viewbox}">{draw()}</symbol>')
    output = ROOT / 'media' / 'graffiti' / 'marks.svg'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<svg xmlns="http://www.w3.org/2000/svg"><defs>\n' + '\n'.join(symbols) + '\n</defs></svg>\n')
    print(f'Generated {len(symbols)} vector marks: {output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
