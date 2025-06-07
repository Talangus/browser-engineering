def read_file(path):
    with open(path, 'r') as file:
            content = file.read()
            return content
    
def html_unescape(entity):
    entity_map = {
        "&lt;": "<",
        "&gt;": ">",
        "&amp;": "&",
        "&quot;": "\"",
        "&apos;": "'",
        "&nbsp;": " ",
        "&copy;": "©",
        "&reg;": "®",
        "&trade;": "™",
        "&euro;": "€",
        "&ndash;": "–"
    }
    return entity_map.get(entity, entity)