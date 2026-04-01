from tree_sitter import Language, Parser
import tree_sitter_python as tspython

PY_LANGUAGE = Language(tspython.language())

parser = Parser(PY_LANGUAGE)


def parse_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()

    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    chunks = []
    imports = []

    def extract_calls(node):
        calls = set()
        def traverse(n):
            if n.type == "call":
                func_node = n.child_by_field_name("function")
                if func_node:
                    calls.add(code[func_node.start_byte:func_node.end_byte])
            for child in n.children:
                traverse(child)
        traverse(node)
        return list(calls)

    def extract_nodes(node):
        if node.type in ("import_statement", "import_from_statement"):
            imports.append(code[node.start_byte:node.end_byte])
        
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            start = node.start_point[0]
            end = node.end_point[0]

            chunk = {
                "type": "function",
                "name": code[name_node.start_byte:name_node.end_byte] if name_node else "anonymous",
                "code": code[node.start_byte:node.end_byte],
                "start_line": start,
                "end_line": end,
                "calls": extract_calls(node)
            }
            chunks.append(chunk)

        for child in node.children:
            extract_nodes(child)

    extract_nodes(root)
    return {"imports": imports, "chunks": chunks}