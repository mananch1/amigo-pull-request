from tree_sitter import Language, Parser
import os

# Build language library (run once)
Language.build_library(
    'build/my-languages.so',
    ['tree-sitter-python']
)

PY_LANGUAGE = Language('build/my-languages.so', 'python')

parser = Parser()
parser.set_language(PY_LANGUAGE)


def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    chunks = []

    def extract_functions(node):
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            start = node.start_point[0]
            end = node.end_point[0]

            chunk = {
                "type": "function",
                "name": code[name_node.start_byte:name_node.end_byte],
                "code": code[node.start_byte:node.end_byte],
                "start_line": start,
                "end_line": end,
            }
            chunks.append(chunk)

        for child in node.children:
            extract_functions(child)

    extract_functions(root)
    return chunks