import sys

import utils
from url import URL


def show(body):
    in_tag = False
    entity_buffer = ""
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif c == "&" and not in_tag:
            entity_buffer = "&"
        elif entity_buffer:
            entity_buffer += c
            if c == ";":
                entity = "".join(entity_buffer)
                print(utils.html_unescape(entity), end="")
                entity_buffer = ""
        elif not in_tag:
            print(c, end="")

def load(url):
    body = url.request()
    if url.is_view_source:
        print(body)
    else:
        show(body)

def get_url_arg():
    if len(sys.argv) > 1:
        return sys.argv[1]
    else:
        # return URL.DEFAULT_FILE_PATH
        # return 'data:text/html;base64,PGgxPkhlbGxvIFdvcmxkPC9oMT4='
        return 'https://browser.engineering/http.html'

if __name__ == "__main__":
    
    url_arg = get_url_arg()
    url = URL(url_arg)
    load(url)
