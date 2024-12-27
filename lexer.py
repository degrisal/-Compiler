import re

class Lexer:
    def __init__(self, keywords, delimiters):
        self.keywords = keywords
        self.delimiters = delimiters
        self.token_specification = [
            ('NUMBER',   r'\d+(\.\d*)?([eE][+-]?\d+)?'),
            ('BINARY',   r'[bB][01]+'),
            ('OCTAL',    r'[oO][0-7]+'),
            ('HEX',      r'[dDhH][0-9A-Fa-f]+'),
            ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z_0-9]*'),
            ('DELIMITER', r'[' + re.escape(''.join(delimiters)) + r']'),
            ('SKIP',     r'[ \t]+'),
            ('NEWLINE',  r'\n'),
            ('MISMATCH', r'.'),
        ]
        self.tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in self.token_specification)

    def tokenize(self, code):
        line_num = 1
        line_start = 0
        tokens = []
        for mo in re.finditer(self.tok_regex, code):
            kind = mo.lastgroup
            value = mo.group(kind)
            column = mo.start() - line_start
            if kind == 'NUMBER':
                value = float(value) if '.' in value or 'e' in value.lower() else int(value)
            elif kind == 'BINARY':
                value = int(value[1:], 2)
                kind = 'NUMBER'
            elif kind == 'OCTAL':
                value = int(value[1:], 8)
                kind = 'NUMBER'
            elif kind == 'HEX':
                value = int(value[1:], 16)
                kind = 'NUMBER'
            elif kind == 'IDENTIFIER':
                if value in self.keywords:
                    kind = value.upper()  # Convert to token for specific keywords
            elif kind == 'DELIMITER':
                kind = 'DELIMITER'
            elif kind == 'SKIP':
                continue
            elif kind == 'NEWLINE':
                line_num += 1
                line_start = mo.end()
                continue
            elif kind == 'MISMATCH':
                raise RuntimeError(f'{value!r} unexpected on line {line_num}')
            tokens.append((kind, value))
        return tokens

keywords = {
            'assign', 'end', 'begin', 'var', 'enter', 'displ', 'add', 'umn', 'disa', 'del',
            'if', 'then', 'else', 'while', 'do', 'next', 'for', 'val', 'GRT', 'LOWE', 'GRE'
        }
delimiters = {',', ';', '#', '@', '&', ':','*', '(', ')'}

lexer = Lexer(keywords, delimiters)

file_path = "te.txt"
try:
    with open(file_path, 'r') as file:
        code = file.read()
except FileNotFoundError:
    print(f"Error: The file '{file_path}' was not found.")
    exit(1)

tokens = lexer.tokenize(code)
for token in tokens:
    print(token)
