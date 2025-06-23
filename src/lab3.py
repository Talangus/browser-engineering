"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 3 (Formatting Text),
without exercises.
"""

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP, Browser

FONT_SIZE = 12

class Text:
    def __init__(self, text):
        self.text = text

    @wbetools.js_hide
    def __repr__(self):
        return "Text('{}')".format(self.text)

class Tag:
    def __init__(self, tag):
        self.tag = tag

    @wbetools.js_hide
    def __repr__(self):
        return "Tag('{}')".format(self.tag)

def lex(body):
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out

FONTS = {}

def get_font(size, weight, style, family=None):
    key = (size, weight, style, family)
    if key not in FONTS:
        if family:
            font = tkinter.font.Font(size=size, weight=weight, slant=style, family=family)
        else:
            font = tkinter.font.Font(size=size, weight=weight, slant=style)
        FONTS[key] = font
    return FONTS[key]

def find_soft_hyphen_break(word, font, start_x, max_width):
    SOFT_HYPHEN = "\u00AD"
    parts = []
    last = 0
    for i, c in enumerate(word):
        if c == SOFT_HYPHEN:
            parts.append(word[last:i])
            last = i + 1
    parts.append(word[last:])

    prefix = ""
    current_x = start_x
    for i, part in enumerate(parts[:-1]):
        test = prefix + part + "-"
        test_w = font.measure(test)
        if current_x + test_w > max_width:
            break
        prefix += part
        prefix += SOFT_HYPHEN

    clean_prefix = prefix.rstrip(SOFT_HYPHEN)
    if clean_prefix:
        suffix = word[len(prefix):]
        if suffix.startswith(SOFT_HYPHEN):
            suffix = suffix[1:]
        return clean_prefix, suffix
    else:
        return "", ""

class Layout:
    def __init__(self, tokens):
        self.tokens = tokens
        self.display_list = []

        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = FONT_SIZE
        self.in_title = False
        self.in_sup_tag = False
        self.in_abbr = False
        self.in_pre = False
        self.prev_size = None
        self.prev_weight = None

        self.line = []
        for tok in tokens:
            self.token(tok)
        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            if self.in_pre:
                self.pre_text(tok.text)
            else:
                for word in tok.text.split():
                    self.word(word)
        elif tok.tag == 'h1 class="title"':
            self.in_title = True
        elif tok.tag == "/h1":
            self.flush()
            self.in_title = False
            self.cursor_y += VSTEP
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
        elif tok.tag == "pre":
            self.in_pre = True
            self.flush()
        elif tok.tag == "/pre":
            self.in_pre = False
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag == "abbr":
            self.in_abbr = True
            self.prev_size = self.size
            self.prev_weight = self.weight
            self.size = int(self.size * 0.7)
            self.weight = "bold"
        elif tok.tag == "/abbr":
            self.in_abbr = False
            self.size = self.prev_size
            self.weight = self.prev_weight
            self.prev_size = None
            self.prev_weight = None
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        
    def word(self, word):
        SOFT_HYPHEN = "\u00AD"
        word = word.upper() if self.in_abbr else word
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > WIDTH - HSTEP and SOFT_HYPHEN in word:
            prefix, suffix = find_soft_hyphen_break(word, font, self.cursor_x, WIDTH - HSTEP)
            if prefix:
                self.line.append((self.cursor_x, prefix + "-", font, self.in_sup_tag))
                self.flush()
                if suffix:
                    self.word(suffix)
                return
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()
        display_word = word.replace(SOFT_HYPHEN, "")
        self.line.append((self.cursor_x, display_word, font, self.in_sup_tag))
        self.cursor_x += font.measure(display_word) + font.measure(" ")

    def pre_text(self, text):
        font = get_font(self.size, self.weight, self.style, family="Courier New")
        lines = text.split('\n')
        for i, line in enumerate(lines):
            x = self.cursor_x
            for c in line:
                self.line.append((x, c, font, self.in_sup_tag))
                x += font.measure(c)
            if i < len(lines) - 1:
                self.flush()
        self.cursor_x = x

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font, sup in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent

        if self.in_title:
            line_width = 0
            if self.line:
                last_x, last_word, last_font, *_ = self.line[-1]
                line_width = last_x + last_font.measure(last_word) - HSTEP
            offset = (WIDTH - line_width) // 2 if line_width < WIDTH else 0
        else:
            offset = 0

        for x, word, font, in_sup_tag in self.line:
            y = baseline - font.metrics("ascent")
            if in_sup_tag:
                y = baseline - max_ascent
            self.display_list.append((x + offset, y, word, font))
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = HSTEP
        self.line = []

@wbetools.patch(Browser)
class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()

        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.display_list = []

    def load(self, url):
        body = url.request()
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, word, font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + font.metrics("linespace") < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=word, font=font, anchor="nw")

if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
