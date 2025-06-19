"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 2 (Drawing to the Screen),
without exercises.
"""

import wbetools
import socket
import ssl
import tkinter
import os
from lab1 import URL

def lex(body):
    text = ""
    in_tag = False
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            text += c
        wbetools.record("lex", text)
    return text

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18

SCROLL_STEP = 100
EMOJI_PATH = "openmoji"

def layout(text, width=WIDTH):
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        if c == "\n":
            cursor_x = HSTEP
            cursor_y += VSTEP * 2
        else: 
            display_list.append((cursor_x, cursor_y, c))
            cursor_x += HSTEP
            if cursor_x >= width - HSTEP:
                cursor_y += VSTEP
                cursor_x = HSTEP
            wbetools.record("layout", display_list)
    return display_list

class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )

        self.canvas.pack(fill=tkinter.BOTH, expand=True)

        self.scroll = 0
        self.max_scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.on_mousewheel)
        self.window.bind("<Configure>", self.on_resize)

        self.width = WIDTH
        self.height = HEIGHT
        self.text = ""
        self.emoji_cache = {}

    def get_emoji_image(self, char):
        codepoint = f"{ord(char):X}".upper()
        filename = os.path.join(EMOJI_PATH, f"{codepoint}.png")
        if not os.path.exists(filename):
            return None
        if filename not in self.emoji_cache:
            img = tkinter.PhotoImage(file=filename)
            if img.width() != 16 or img.height() != 16:
                x_factor = max(1, img.width() // 16)
                y_factor = max(1, img.height() // 16)
                img = img.subsample(x_factor, y_factor)
            self.emoji_cache[filename] = img
        return self.emoji_cache[filename]
    
    def update_display_list(self):
        self.display_list = layout(self.text, self.width)
        if self.display_list:
            max_y = max(y for _, y, _ in self.display_list)
            self.max_scroll = max(0, max_y - self.height + VSTEP)
        else:
            self.max_scroll = 0

    def load(self, url):
        body = url.request()
        self.text = lex(body)
        self.update_display_list()
        self.draw()

    def needs_scrollbar(self):
        return self.max_scroll > 0

    def draw_scrollbar(self):
        if not self.needs_scrollbar():
            return
        bar_width = 10
        bar_x0 = self.width - bar_width
        bar_x1 = self.width

        visible_ratio = self.height / (self.max_scroll + self.height)
        bar_height = max(30, self.height * visible_ratio)

        max_bar_y = self.height - bar_height
        bar_y0 = (self.scroll / self.max_scroll) * max_bar_y if self.max_scroll else 0
        bar_y1 = bar_y0 + bar_height

        self.canvas.create_rectangle(
            bar_x0, bar_y0, bar_x1, bar_y1,
            fill="blue", outline="blue"
        )

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            wbetools.record("draw")
            if y > self.scroll + self.height: continue
            if y + VSTEP < self.scroll: continue
            emoji_img = self.get_emoji_image(c)
            if emoji_img:
                self.canvas.create_image(x, y - self.scroll - 0.5*VSTEP, anchor="nw", image=emoji_img)
            else:
                self.canvas.create_text(x, y - self.scroll, text=c)
        self.draw_scrollbar()    

    def scrolldown(self, e=None):
        self.scroll += SCROLL_STEP
        if self.scroll > self.max_scroll:
            self.scroll = self.max_scroll
        self.draw()

    def scrollup(self, e=None):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()

    def on_mousewheel(self, event):
        if event.delta > 0:
            self.scrollup()
        else:
            self.scrolldown()

    def on_resize(self, event):
        self.width = event.width
        self.height = event.height
        self.update_display_list()
        if self.scroll > self.max_scroll:
            self.scroll = self.max_scroll
        self.draw()

if __name__ == "__main__":
    import sys

    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
