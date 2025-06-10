import sys
import os
import tkinter

import utils
from url import URL
from socket_manager import socket_manager
from layout import Layout, Text, Tag
from config import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP

def lex(body):
    out = []
    buffer = ""
    in_tag = False
    entity_buffer = ""
    for c in body:
        if c == "<":
            in_tag = True
            if buffer:
                out.append(Text(buffer))
                buffer = ""
        elif c == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        elif not in_tag:
            if c == "&":
                entity_buffer = "&"
            elif entity_buffer:
                entity_buffer += c
                if c == ";":
                    buffer += utils.html_unescape(entity_buffer)
                    entity_buffer = ""
            else:
                buffer += c
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out

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
        self.display_list = []

    def update_display_list(self):
        tokens = lex(self.text)
        layout = Layout(tokens, width=self.width, hstep=HSTEP, vstep=VSTEP)
        self.display_list = layout.display_list
        if self.display_list:
            max_y = max(y for _, y, _, _ in self.display_list)
            self.max_scroll = max(0, max_y - self.height + VSTEP)
        else:
            self.max_scroll = 0

    def load(self, url):
        self.text = url.request()
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
        for x, y, word, font in self.display_list:
            if y > self.scroll + self.height: continue
            if y + font.metrics("linespace") < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=word, font=font, anchor="nw")
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

def get_url_arg():
    if len(sys.argv) > 1:
        return sys.argv[1]
    else:
        # return 'https://browser.engineering/text.html'
        return 'file:///Users/li016390/Desktop/challenges/browser-engineering/test/test_centered_title.html'

if __name__ == "__main__":
    url_arg = get_url_arg()
    url = URL(url_arg)
    Browser().load(url)
    tkinter.mainloop()
    socket_manager.close()