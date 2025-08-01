"""
This file compiles the code in Web Browser Engineering,
up to and including Chapter 6 (Applying User Styles),
without exercises.
"""

import wbetools
import socket
import ssl
import tkinter
import tkinter.font
from lab1 import URL
from lab2 import WIDTH, HEIGHT, HSTEP, VSTEP, SCROLL_STEP
from lab3 import FONTS, get_font
from lab4 import Text, Element, print_tree, HTMLParser
from lab5 import DrawRect, DrawText, paint_tree
from lab5 import BlockLayout, DocumentLayout, Browser
import wbetools

@wbetools.patch(URL)
class URL:
    def resolve(self, url):
        if "://" in url: return URL(url)
        if not url.startswith("/"):
            dir, _ = self.path.rsplit("/", 1)
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
            url = dir + "/" + url
        if url.startswith("//"):
            return URL(self.scheme + ":" + url)
        else:
            return URL(self.scheme + "://" + self.host + \
                       ":" + str(self.port) + url)

@wbetools.patchable
def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def word(self):
        start = self.i
        if self.i < len(self.s) and self.s[self.i] == ':':
            self.i += 1
        
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.s[start:self.i]

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def selector(self):
        word = self.word()
        out = get_discrete_selector(word.casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            word = self.word()
            
            if word == ':has':
                out = self.get_has_selector(out)
                while self.s[self.i] != "{":
                    self.i +=1
                break
            descendant = get_discrete_selector(word.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def get_has_selector(self, ancestor_selector):
        left_parenthesis = self.s[self.i:].index('(')
        right_parenthesis = self.s[self.i:].index(')')
        descendant_selector = CSSParser(self.s[self.i + left_parenthesis + 1:self.i + right_parenthesis]).selector()
        return HasSelector(ancestor_selector, descendant_selector)

        

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules
    
class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

    @wbetools.js_hide
    def __repr__(self):
        return "TagSelector(tag={}, priority={})".format(
            self.tag, self.priority)

class ClassSelector:
    def __init__(self, class_name):
        self.class_name = class_name
        self.priority = 10  

    def matches(self, node):
        if not isinstance(node, Element): return False
        classes = node.attributes.get("class", "").split()
        return self.class_name in classes

    @wbetools.js_hide
    def __repr__(self):
        return "ClassSelector(class_name={}, priority={})".format(
            self.class_name, self.priority)

class HasSelector:
    def __init__(self, ancestor_selector, descendant_selector):
        self.ancestor_selector = ancestor_selector
        self.descendant_selector = descendant_selector
        self.priority = 15

    def ancestor_matches(self, node):
        if self.ancestor_selector.matches(node):
            if  not hasattr(node,'pending_css_rules'):
                node.pending_css_rules = {}
            
            return True

        return False


    @wbetools.js_hide
    def __repr__(self):
        return "HasSelector(selector_list={}, priority={})".format(
            self.selector_list, self.priority)

def get_discrete_selector(word):
    if word.startswith("."):
        return ClassSelector(word[1:])
    else:
        return TagSelector(word.casefold())

class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority
            
    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

    @wbetools.js_hide
    def __repr__(self):
        return ("DescendantSelector(ancestor={}, descendant={}, priority={})") \
            .format(self.ancestor, self.descendant, self.priority)

INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}

def style(node, rules, pending_rules={}):
    node.style = {}
    
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    node.style["display"] = "inline"
    
    for selector, body in rules:
        if isinstance(selector, HasSelector):
            if selector.ancestor_matches(node):
                pending_rule = {"selector": selector.descendant_selector,
                                "body": body,
                                "satisfied": False}
                node.pending_css_rules[str(id(pending_rule))] = pending_rule
        elif selector.matches(node): 
            for property, value in body.items():
                node.style[property] = value
    
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value
    
    if node.style["font-size"].endswith("%"):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            parent_font_size = INHERITED_PROPERTIES["font-size"]
        node_pct = float(node.style["font-size"][:-1]) / 100
        parent_px = float(parent_font_size[:-2])
        node.style["font-size"] = str(node_pct * parent_px) + "px"

    for rule_id in pending_rules:
        curr_rule = pending_rules[rule_id]
        if not curr_rule["satisfied"] and curr_rule["selector"].matches(node):
            curr_rule["satisfied"] = True
    
    if hasattr(node, "pending_css_rules"):
        pending_rules = node.pending_css_rules | pending_rules

    for child in node.children:
        pending_rules = pending_rules | style(child, rules, pending_rules)

    if hasattr(node, "pending_css_rules"):
        for rule_id in node.pending_css_rules:
            if pending_rules[rule_id]["satisfied"]:
                for property, value in pending_rules[rule_id]["body"].items():
                    node.style[property] = value

    return pending_rules

def cascade_priority(rule):
    selector, body = rule
    return selector.priority

@wbetools.patch(BlockLayout)
class BlockLayout:
    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br":
                self.flush()
            for child in node.children:
                self.recurse(child)

    def word(self, node, word):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(node.style["font-size"][:-2]) * .75)
        family = node.style.get("font-family")
        font = get_font(size, weight, style, family)

        w = font.measure(word)
        if self.cursor_x + w > self.width:
            self.flush()
        color = node.style["color"]
        self.line.append((self.cursor_x, word, font, color))
        self.cursor_x += w + font.measure(" ")

    def flush(self):
        if not self.line: return
        metrics = [font.metrics() for x, word, font, color in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for rel_x, word, font, color in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font, color))
        self.cursor_x = 0
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color",
                                      "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            cmds.append(rect)

        if self.layout_mode() == "inline":
            for x, y, word, font, color in self.display_list:
                cmds.append(DrawText(x, y, word, font, color))

        return cmds

    @wbetools.delete
    def open_tag(self, tag): pass

    @wbetools.delete
    def close_tag(self, tag): pass

@wbetools.patch(DrawText)
class DrawText:
    def __init__(self, x1, y1, text, font, color):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color

        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left, self.top - scroll,
            text=self.text,
            font=self.font,
            anchor='nw',
            fill=self.color)

DEFAULT_STYLE_SHEET = CSSParser(open("browser6.css").read()).parse()

@wbetools.patch(Browser)
class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT,
            bg="white",
        )
        self.canvas.pack()

        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.on_mousewheel)
        self.display_list = []

    def load(self, url):
        body = url.request()
        self.nodes = HTMLParser(body).parse()

        rules = DEFAULT_STYLE_SHEET.copy()
        
        links = [node.attributes["href"]
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "link"
                 and node.attributes.get("rel") == "stylesheet"
                 and "href" in node.attributes]
        for link in links:
            style_url = url.resolve(link)
            try:
                body = style_url.request()
            except:
                continue
            rules.extend(CSSParser(body).parse())
        
        inline_stlyes = [node
                 for node in tree_to_list(self.nodes, [])
                 if isinstance(node, Element)
                 and node.tag == "style"]
        for node in inline_stlyes:
            text = node.children[0].text
            rules.extend(CSSParser(text).parse())
        
        style(self.nodes, sorted(rules, key=cascade_priority))

        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        paint_tree(self.document, self.display_list)
        self.draw()

if __name__ == "__main__":
    import sys
    Browser().load(URL(sys.argv[1]))
    tkinter.mainloop()
