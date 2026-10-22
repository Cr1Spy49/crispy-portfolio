"""Author the lightweight graffiti sprite: three gently redrawn vector frames per mark.
No image dependencies. Run: python3 tools/make_graffiti.py
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


def comet(frame):
    tail = [
        'M110 115 C151 130 165 172 220 203',
        'M117 100 C174 119 218 151 280 160',
        'M94 130 C115 178 161 208 184 258',
        'M140 133 C162 153 177 176 204 182',
    ]
    star = 'M84 29 Q94 67 130 79 Q98 85 83 128 Q75 92 35 85 Q70 73 84 29Z'
    result = ''.join(stroke(redraw(path, 100 * frame + i), CHALK if i == 1 else ORANGE, 3 if i == 1 else 5, .8) for i, path in enumerate(tail))
    star = redraw(star, 30 + frame)
    result += stroke(star, INK, 13, 1, INK)
    result += stroke(star, ORANGE, 7)
    result += stroke(redraw('M80 48 Q80 73 56 82 M91 83 Q83 88 81 107', frame + 44), CHALK, 2.5)
    result += stroke(redraw('M152 171 Q161 186 171 190 M227 187 L238 194 M192 235 L197 245', frame + 51), ORANGE, 2.5, .65)
    for x, y, radius in [(145, 108, 2), (124, 174, 2.2), (245, 179, 1.5), (54, 56, 1.8), (215, 224, 1.5)]:
        result += f'<circle cx="{x + frame * .4}" cy="{y - frame * .4}" r="{radius}" fill="{ORANGE}" opacity=".6"/>'
    return result


def burst(frame):
    path = redraw('M159 24 Q169 79 197 106 L281 85 L232 151 L279 226 L194 213 L154 289 L121 219 L29 238 L77 161 L24 102 L112 112Z', 80 + frame)
    result = stroke(path, INK, 13, 1, INK)
    result += stroke(path, ORANGE, 5, 1, '#a23c12')
    result += stroke(redraw('M151 47 L169 112 L198 125 L251 108 M70 214 L117 190 M176 232 L157 267', 90 + frame), CHALK, 3, .8)
    result += stroke(redraw('M54 58 L42 42 M24 170 L9 172 M255 254 L265 270 M235 48 L243 28', 96 + frame), ORANGE, 3, .7)
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
    drawings = [('comet', comet, '0 0 320 290'), ('burst', burst, '0 0 310 310'),
                ('tag', tag, '0 0 350 210'), ('swoop', swoop, '0 0 230 290'),
                ('smile', smile, '0 0 240 220'), ('arrow', arrow, '0 0 330 220')]
    symbols = []
    for name, draw, viewbox in drawings:
        for frame in range(3):
            symbols.append(f'<symbol id="{name}-{frame}" viewBox="{viewbox}">{draw(frame)}</symbol>')
    output = ROOT / 'media' / 'graffiti' / 'marks.svg'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<svg xmlns="http://www.w3.org/2000/svg"><defs>\n' + '\n'.join(symbols) + '\n</defs></svg>\n')
    print(f'Generated 18 original vector marks: {output.stat().st_size} bytes')


if __name__ == '__main__':
    main()
