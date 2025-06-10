import tkinter.font
import utils
from config import WIDTH, HEIGHT, HSTEP, VSTEP, FONT_SIZE

class Text:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return f"Text({self.text!r})"

class Tag:
    def __init__(self, tag):
        self.tag = tag

    def __repr__(self):
        return f"Tag({self.tag!r})"

FONTS = {}
def get_font(size, weight, style):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        FONTS[key] = font
    return FONTS[key]

class Layout:
    def __init__(self, tokens, width=WIDTH, hstep=HSTEP, vstep=VSTEP):
        self.tokens = tokens
        self.display_list = []

        self.cursor_x = hstep
        self.cursor_y = vstep
        self.weight = "normal"
        self.style = "roman"
        self.size = FONT_SIZE
        self.in_title = False
        self.in_sup_tag = False
        self.prev_size = None

        self.line = []
        self.width = width
        self.hstep = hstep
        self.vstep = vstep

        for tok in tokens:
            self.token(tok)
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == 'h1 class="title"':
            self.in_title = True
        elif tok.tag == "/h1":
            self.flush()
            self.in_title = False
            self.cursor_y += self.vstep
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "sup":
            self.in_sup_tag = True
            self.prev_size = self.size
            self.size = max(1, FONT_SIZE // 2)
        elif tok.tag == "/sup":
            self.in_sup_tag = False
            self.size = self.prev_size
            self.prev_size = None
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += self.vstep

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > self.width - self.hstep:
            self.flush()
        self.line.append((self.cursor_x, word, font, self.in_sup_tag))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font, sup in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        if self.in_title:
            line_width = 0
            if self.line:
                last_x, last_word, last_font, *_ = self.line[-1]
                line_width = last_x + last_font.measure(last_word) - self.hstep
            offset = (self.width - line_width) // 2 if line_width < self.width else 0
        else:
            offset = 0

        for x, word, font, in_sup_tag in self.line:
            y = baseline - font.metrics("ascent")
            if in_sup_tag:
                y = baseline - max_ascent
            self.display_list.append((x + offset, y, word, font))
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = self.hstep
        self.line = []