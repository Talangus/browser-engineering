"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 4 (Constructing a Document Tree),
Including exercises implemented by Tal Langus.
"""

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
import re
from lab1 import URL, html_unescape
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font, Layout, Browser

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        attrs = [" " + k + "=\"" + v + "\"" for k, v  in self.attributes.items()]
        attr_str = ""
        for attr in attrs:
            attr_str += attr
        return "<" + self.tag + attr_str + ">"

@wbetools.patchable
def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []
        self.unfinished_format_tags = []
        self.misnested_format_tags = []
        self.body_index = 0  

    def parse(self):
        text = ""
        in_tag = False
        in_script = False
        self.body_index = 0

        while self.body_index < len(self.body):
            if not in_script and self.body.startswith("<!--", self.body_index):
                self.skip_comment()
                in_tag = False
                text = ""
                continue
            if not in_script and self.body.startswith("<script", self.body_index):
                in_tag = True
                if text: self.add_text(text)
                text = ""
                self.handle_script_tag()
                in_script = True
                continue
            if in_script:
                in_script = not self.handle_script_content()
                text = ""
                continue
            c = self.body[self.body_index]
            if c == "<":
                in_tag = True
                if text: self.add_text(text)
                text = ""
                tag_content = self.read_tag()
                self.add_tag(tag_content)
                in_tag = False
                text = ""
                continue
            else:
                text += c
                self.body_index += 1
        if not in_tag and text:
            self.add_text(text)
        return self.finish()

    def read_tag(self):
        assert self.body[self.body_index] == "<"
        self.body_index += 1
        tag = ""
        in_quote = False
        quote_char = ""
        while self.body_index < len(self.body):
            c = self.body[self.body_index]
            if in_quote:
                tag += c
                if c == quote_char:
                    in_quote = False
                self.body_index += 1
            else:
                if c in ['"', "'"]:
                    in_quote = True
                    quote_char = c
                    tag += c
                    self.body_index += 1
                elif c == ">":
                    self.body_index += 1
                    break
                else:
                    tag += c
                    self.body_index += 1
        return tag.strip()

    def skip_comment(self):
        end_comment = self.body.find("-->", self.body_index)
        if end_comment == -1:
            self.body_index = len(self.body)
        else:
            self.body_index = end_comment + 3

    def handle_script_tag(self):
        script_tag_end = self.body.find(">", self.body_index)
        if script_tag_end == -1:
            self.body_index = len(self.body)
            return
        self.add_tag(self.body[self.body_index + 1:script_tag_end])
        self.body_index = script_tag_end + 1

    def handle_script_content(self):
        script_end = self.body.find("</script>", self.body_index)
        if script_end == -1:
            script_content = self.body[self.body_index:]
            self.body_index = len(self.body)
        else:
            script_content = self.body[self.body_index:script_end]
            self.body_index = script_end + len("</script>")
        if script_content:
            self.add_text(script_content)
        self.add_tag("/script")
        return script_end != -1

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
        return tag, attributes

    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    SELF_CLOSING_TAGS = [
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    ]

    FORMATTING_TAGS = ['i', 'b', 'small', 'big', 'pre']

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag)

        if tag.startswith("/") and tag[1:] in self.FORMATTING_TAGS:
            self.handle_misnested_formatting(tag[1:])
            return

        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
            if self.is_top_formatting_node(node):
                self.unfinished_format_tags.pop()
        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)
            if tag in self.FORMATTING_TAGS:
                self.unfinished_format_tags.append(node)

    def is_top_formatting_node(self, node):
        return (
            node.tag in self.FORMATTING_TAGS and
            self.unfinished_format_tags and
            self.unfinished_format_tags[-1] == node
        )

    def handle_misnested_formatting(self, tag):
        for i in range(len(self.unfinished_format_tags) - 1, -1, -1):
            node = self.unfinished_format_tags[i]
            if node.tag == tag:
                # Close all formatting tags above this one
                to_reopen = []
                while len(self.unfinished_format_tags) - 1 > i:
                    misnested_node = self.unfinished_format_tags.pop()
                    if misnested_node in self.unfinished:
                        self.unfinished.remove(misnested_node)
                        parent = misnested_node.parent
                        if parent:
                            parent.children.append(misnested_node)
                    to_reopen.append(misnested_node.tag)
                matching_node = self.unfinished_format_tags.pop()
                if matching_node in self.unfinished:
                    self.unfinished.remove(matching_node)
                    parent = matching_node.parent
                    if parent:
                        parent.children.append(matching_node)
                for reopen_tag in reversed(to_reopen):
                    self.add_tag(reopen_tag)
                return

    HEAD_TAGS = [
        "base", "basefont", "bgsound", "noscript",
        "link", "meta", "title", "style", "script",
    ]

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] \
                 and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and \
                 tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            elif tag == 'p' and 'p' in open_tags:
                self.add_tag('/p')
            elif  tag == 'li' and 'li' in open_tags:
                self.add_tag('/li')
            else:
                break

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        root = self.unfinished.pop()
        self.unescape_tree(root)
        return root
    
    def unescape_tree(self, node):
        if isinstance(node, Text):
            def replace_entity(match):
                return html_unescape(match.group(0))
            node.text = re.sub(r"&[a-zA-Z0-9#]+?;", replace_entity, node.text)
        for child in getattr(node, "children", []):
            self.unescape_tree(child)

@wbetools.patch(Layout)
class Layout:
    def __init__(self, tree):
        self.display_list = []

        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.in_pre = False

        self.line = []
        self.recurse(tree)
        self.flush()

    @wbetools.delete
    def token(self, tok): pass

    @wbetools.delete
    def word(self, word):
        if word == '\n' and self.in_pre:
            self.flush()
            return
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()
        self.line.append((self.cursor_x, word, font))
        self.cursor_x += w + font.measure(" ")

    @wbetools.delete
    def flush(self):
        if not self.line: return
        wbetools.record("initial_y", self.cursor_y, self.line);
        metrics = [font.metrics() for x, word, font in self.line]
        wbetools.record("metrics", metrics)
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        wbetools.record("max_ascent", max_ascent);
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
            wbetools.record("aligned", self.display_list);
        max_descent = max([metric["descent"] for metric in metrics])
        wbetools.record("max_descent", max_descent);
        self.cursor_y = baseline + 1.25 * max_descent
        self.cursor_x = HSTEP
        self.line = []
        wbetools.record("final_y", self.cursor_y);

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in self.split_text(tree.text):
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def split_text(self, text):
        if self.in_pre:
            return re.split(r'(\s)', text)
        
        return text.split()

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 4
        elif tag == "pre":
            self.in_pre = True
        elif tag == "br":
            self.flush()

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 4
        elif tag == "pre":
            self.in_pre = False
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP

@wbetools.patch(Browser)
class Browser:
    def load(self, url):
        body = url.request()
        if url.is_view_source:
            body = "<pre>" + body.replace("<", "&lt;").replace(">", "&gt;") + "</pre>"
        self.nodes = HTMLParser(body).parse()
        print_tree(self.nodes)
        self.display_list = Layout(self.nodes).display_list
        self.draw()

if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
