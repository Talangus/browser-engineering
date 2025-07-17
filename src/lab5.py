"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 5 (Laying out Pages),
Including exercises implemented by Tal Langus.
"""

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font
from lab4 import Text, Element, print_tree, HTMLParser, Layout, Browser

BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

LIST_ELEMENTS= ["ul", "ol", "menu"]

INDENT_PX = 20  
BULLET_SIZE = 8
TOC_HEADER_HEIGHT = 24

@wbetools.patch(Layout)
class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        self.display_list = []

    def layout(self):
        wbetools.record("layout_pre", self)
        height_offset = 0
        self.x = self.parent.x
        self.width = self.parent.width

        if isinstance(self.node, Element) and self.node.tag == "li":
            self.x += INDENT_PX
            self.width -= INDENT_PX

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        if isinstance(self.node, Element) and self.node.tag in LIST_ELEMENTS and\
            is_toc_nav_element(self.node.parent):
            self.y += TOC_HEADER_HEIGHT
            height_offset = TOC_HEADER_HEIGHT

        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                if isinstance(child, Element) and child.tag == "head":
                    continue
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next
        else:
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 12
            self.in_pre = False

            self.line = []
            self.recurse(self.node)
            self.flush()

        for child in self.children:
            child.layout()

        if mode == "block":
            self.height = sum([
                child.height for child in self.children]) + height_offset
        else:
            self.height = self.cursor_y

        wbetools.record("layout_post", self)

    def layout_mode(self):
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for rel_x, word, font in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        self.cursor_x = 0
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

    def paint(self):
        cmds = []
        if isinstance(self.node, Element) and self.node.tag == "pre":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "gray")
            cmds.append(rect)

        elif is_toc_nav_element(self.node):
            header_color = "#cccccc"
            rect = DrawRect(self.x, self.y, self.x + self.width, self.y + TOC_HEADER_HEIGHT, header_color)
            cmds.append(rect)
            
            font = get_font(14, "bold", "roman")
            text_x = self.x + 8
            text_y = self.y + 4
            cmds.append(DrawText(text_x, text_y, "Table of Contents", font))

        elif isinstance(self.node, Element) and self.node.tag == "nav" and\
            has_attribute(self.node, "class", "links"):
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, "#e0e0e0")  # light gray
            cmds.append(rect)
        
        elif isinstance(self.node, Element) and self.node.tag == "li":
            bullet_x = self.x - INDENT_PX + 4  
            bullet_y = self.y + 4  
            rect = DrawRect(
                bullet_x,
                bullet_y,
                bullet_x + BULLET_SIZE,
                bullet_y + BULLET_SIZE,
                "black"
            )
            cmds.append(rect)

        if self.layout_mode() == "inline":
            for x, y, word, font in self.display_list:
                cmds.append(DrawText(x, y, word, font))
        return cmds

    @wbetools.js_hide
    def __repr__(self):
        return "BlockLayout[{}](x={}, y={}, width={}, height={}, node={})".format(
            self.layout_mode(), self.x, self.y, self.width, self.height, self.node)

class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.previous = None
        self.children = []

    def layout(self):
        wbetools.record("layout_pre", self)
        child = BlockLayout(self.node, self, None)
        self.children.append(child)

        self.width = WIDTH - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height
        wbetools.record("layout_post", self)

    def paint(self):
        return []

    @wbetools.js_hide
    def __repr__(self):
        return "DocumentLayout()"

class DrawText:
    def __init__(self, x1, y1, text, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font

        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw')

    @wbetools.js_hide
    def __repr__(self):
        return "DrawText(top={} left={} bottom={} text={} font={})".format(
            self.top, self.left, self.bottom, self.text, self.font)

class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left, self.top - scroll,
            self.right, self.bottom - scroll,
            width=0,
            fill=self.color)

    @wbetools.js_hide
    def __repr__(self):
        return "DrawRect(top={} left={} bottom={} right={} color={})".format(
            self.top, self.left, self.bottom, self.right, self.color)

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

def has_attribute(html_node, attr_name, attr_value):
    return attr_name in html_node.attributes and\
        html_node.attributes[attr_name] == attr_value

def is_toc_nav_element(node):
    return isinstance(node, Element) and node.tag == "nav" and has_attribute(node, "id", "toc")
    

@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)

    def scrolldown(self, e):
        max_y = max(self.document.height + 2*VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.draw()

if __name__ == "__main__":
    import sys 
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
