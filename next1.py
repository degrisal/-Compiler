import re

class Lexer:
    def __init__(self, keywords, delimiters):
        self.keywords = keywords
        self.delimiters = delimiters
        self.token_specification = [
            ('NUMBER',   r'\d+(\.\d*)?'),       # Integer or decimal number
            ('BINARY',   r'[bB][01]+'),         # Binary number
            ('OCTAL',    r'[oO][0-7]+'),        # Octal number
            ('HEX',      r'[dDhH][0-9A-Fa-f]+'),# Hexadecimal number
            ('IDENTIFIER', r'[a-zA-Z_][a-zA-Z_0-9]*'), # Identifiers
            ('DELIMITER', r'[' + re.escape(''.join(delimiters)) + r']'), # Delimiters from table
            ('SKIP',     r'[ \t]+'),            # Skip spaces and tabs
            ('NEWLINE',  r'\n'),                # Newlines
            ('MISMATCH', r'.'),                 # Any other character
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
                value = float(value) if '.' in value else int(value)
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

class Interpreter:
    def __init__(self):
        self.variables = {}
        self.described_variables = set()
        self.condition_stack = []
        self.skip_block = False
        self.while_stack = []
        self.for_stack = []

        # Таблица №1 - Служебные слова
        self.keywords = {
            "begin", "var", "end", "#", "@", "&", "if", "then", "else",
            "for", "do", "while", "next", "enter", "displ"
        }

        # Таблица №2 - Ограничители
        self.delimiters = {
            "||", "&&", "^", "(", ")", "*", ",", ":", "NEQ", "EQV", "LOWT",
            "LOWE", "GRT", "GRE", "[", "]", "add", "del", "assign"
        }

    def execute(self, tokens):
        if not tokens or tokens[0][0] != "BEGIN":
            raise SyntaxError("Программа должна начинаться с 'begin'.")

        index = 1  # Начинаем с первой строки после 'begin'
        in_comment_block = False
        while index < len(tokens):
            token = tokens[index]

            if token[0] == 'DELIMITER' and token[1] == '(*':
                in_comment_block = True
            if token[0] == 'DELIMITER' and token[1] == '*)':
                in_comment_block = False
                index += 1
                continue
            if in_comment_block:
                index += 1
                continue

            if token[0] == 'VAR':  # Описание переменных
                index = self.handle_declaration(tokens, index)
            elif token[0] == 'IDENTIFIER' and tokens[index + 1][0] == 'ASSIGN':  # Присваивание значений
                index = self.handle_assignment(tokens, index)
            elif token[0] == 'ENTER':  # Оператор ввода
                index = self.handle_input(tokens, index)
            elif token[0] == 'DISPL':  # Оператор вывода
                index = self.handle_display(tokens, index)
            elif token[0] == 'IF':  # Условный оператор
                index = self.handle_if(tokens, index)  # Обрабатываем if
            elif token[0] == 'WHILE':
                index = self.handle_while(tokens, index)
            elif token[0] == 'FOR':  # Фиксированный цикл
                index = self.handle_for(tokens, index)  # Обрабатываем for
            elif token[0] == 'NEXT':
                index += 1  # Пропускаем команду next
                continue
            elif token[0] == 'END':
                return
            elif token[0] == 'DELIMITER':
                index += 1  # Пропускаем разделители
                continue
            else:
                raise SyntaxError(f"Неизвестная команда: {token}")

    def handle_declaration(self, tokens, index):
        index += 1
        while tokens[index][0] != 'DELIMITER' or tokens[index][1] != ';':
            var_type = tokens[index][1]
            index += 1
            identifiers = []
            while tokens[index][0] == 'IDENTIFIER':
                identifiers.append(tokens[index][1])
                index += 1
                if tokens[index][0] == 'DELIMITER' and tokens[index][1] == ',':
                    index += 1
            for identifier in identifiers:
                if identifier in self.variables:
                    raise SyntaxError(f"Переменная '{identifier}' уже объявлена.")
                if var_type not in ["#", "@", "&"]:
                    raise SyntaxError(f"Некорректный тип '{var_type}'.")
                # Инициализируем переменную значением по умолчанию
                if var_type == "#":
                    self.variables[identifier] = 0
                elif var_type == "@":
                    self.variables[identifier] = 0.0
                elif var_type == "&":
                    self.variables[identifier] = False
                self.described_variables.add(identifier)
            if tokens[index][0] == 'DELIMITER' and tokens[index][1] == ';':
                break
        return index

    def handle_assignment(self, tokens, index):
        var_name = tokens[index][1]
        index += 2  # Пропускаем 'assign'
        expression = []
        while tokens[index][0] != 'DELIMITER' or tokens[index][1] != ';':
            expression.append(tokens[index])
            index += 1

        if var_name not in self.variables:
            raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

        var_type = type(self.variables[var_name])
        value = self.get_value(expression)

        if var_type == int and not isinstance(value, int):
            raise TypeError(f"Переменная '{var_name}' типа int, но присваиваемое значение типа {type(value).__name__}.")
        elif var_type == float and not isinstance(value, float):
            raise TypeError(f"Переменная '{var_name}' типа float, но присваиваемое значение типа {type(value).__name__}.")
        elif var_type == bool and not isinstance(value, bool):
            raise TypeError(f"Переменная '{var_name}' типа bool, но присваиваемое значение типа {type(value).__name__}.")

        self.variables[var_name] = value
        return index

    def handle_input(self, tokens, index):
        index += 1
        while tokens[index][0] != 'DELIMITER' or tokens[index][1] != ';':
            var_name = tokens[index][1]
            index += 1
            if var_name not in self.variables:
                raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

            # Запрашиваем ввод от пользователя
            value = input(f"Введите значение для {var_name}: ").strip()

            # В зависимости от типа переменной, преобразуем введенное значение
            if isinstance(self.variables[var_name], int):
                if value.startswith("B") or value.startswith("b"):  # Двоичное число
                    try:
                        self.variables[var_name] = int(value[1:], 2)
                    except ValueError:
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается двоичное число.")
                elif value.startswith("O") or value.startswith("o"):  # Восьмеричное число
                    try:
                        self.variables[var_name] = int(value[1:], 8)
                    except ValueError:
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается восьмеричное число.")
                elif value.startswith("H") or value.startswith("h"):  # Шестнадцатеричное число
                    try:
                        self.variables[var_name] = int(value[1:], 16)
                    except ValueError:
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается шестнадцатеричное число.")
                else:
                    try:
                        self.variables[var_name] = int(value)
                    except ValueError:
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается целое число.")
            elif isinstance(self.variables[var_name], float):
                try:
                    self.variables[var_name] = float(value)
                except ValueError:
                    raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается число с плавающей точкой.")
            elif isinstance(self.variables[var_name], bool):
                if value.lower() == "true":
                    self.variables[var_name] = True
                elif value.lower() == "false":
                    self.variables[var_name] = False
                else:
                    raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается логическое значение (true/false).")
            if tokens[index][0] == 'DELIMITER' and tokens[index][1] == ',':
                index += 1
        return index

    def handle_display(self, tokens, index):
        expressions = []
        while tokens[index][0] != 'DELIMITER' or tokens[index][1] != ';':
            expressions.append(tokens[index][1])
            index += 1

        if not expressions:
            raise SyntaxError("Не указаны выражения для вывода.")

        for expr in expressions:
            value = self.get_value([('IDENTIFIER', expr)])
            print(value, end=" ")
        print()
        return index

    def handle_if(self, tokens, index):
        if tokens[index + 1][0] != 'DELIMITER' or tokens[index + 1][1] != '(':
            raise SyntaxError("Ожидается синтаксис 'if (<условие>) then <оператор> [else <оператор>] end'.")

        condition_start = index + 2
        condition_end = condition_start
        while tokens[condition_end][0] != 'DELIMITER' or tokens[condition_end][1] != ')':
            condition_end += 1

        condition = tokens[condition_start:condition_end]
        body_start = condition_end + 2
        body_end = body_start
        while tokens[body_end][0] != 'END':
            body_end += 1

        then_expression = tokens[body_start:body_end]
        else_expression = None
        if tokens[body_end + 1][0] == 'ELSE':
            else_start = body_end + 2
            else_end = else_start
            while tokens[else_end][0] != 'END':
                else_end += 1
            else_expression = tokens[else_start:else_end]

        # Вычисляем условие
        condition_result = self.evaluate_expression(condition)

        if condition_result:
            self.execute_block(then_expression)
        elif else_expression:
            self.execute_block(else_expression)
        return body_end + 1

    def handle_while(self, tokens, index):
        if tokens[index + 1][0] != 'DELIMITER' or tokens[index + 1][1] != '(':
            raise SyntaxError("Некорректный вызов while.")

        condition_start = index + 2
        condition_end = condition_start
        while tokens[condition_end][0] != 'DELIMITER' or tokens[condition_end][1] != ')':
            condition_end += 1

        condition = tokens[condition_start:condition_end]
        condition_value = self.evaluate_expression(condition)
        self.while_stack.append((condition, index))

        while condition_value:
            j = condition_end + 1
            while tokens[j][0] != 'NEXT':
                if tokens[j][0] == 'VAR':  # Описание переменных
                    j = self.handle_declaration(tokens, j)
                elif tokens[j][0] == 'IDENTIFIER' and tokens[j + 1][0] == 'ASSIGN':  # Присваивание значений
                    j = self.handle_assignment(tokens, j)
                elif tokens[j][0] == 'ENTER':
                    j = self.handle_input(tokens, j)
                elif tokens[j][0] == 'DISPL':
                    j = self.handle_display(tokens, j)
                elif tokens[j][0] == 'IF':
                    j = self.handle_if(tokens, j)
                elif tokens[j][0] == 'WHILE':
                    j = self.handle_while(tokens, j)
                elif tokens[j][0] == 'FOR':
                    j = self.handle_for(tokens, j)
                else:
                    raise SyntaxError(f"Неизвестная команда: {tokens[j]}")
                j += 1

            condition_value = self.evaluate_expression(condition)
            self.while_stack[-1] = (condition, index)

        self.while_stack.pop()
        return index

    def handle_for(self, tokens, index):
        if tokens[index + 1][0] != 'DELIMITER' or tokens[index + 1][1] != '(':
            raise SyntaxError("Некорректный вызов for.")

        condition_start = index + 2
        condition_end = condition_start
        while tokens[condition_end][0] != 'DELIMITER' or tokens[condition_end][1] != ')':
            condition_end += 1

        condition = tokens[condition_start:condition_end]
        condition_value = self.evaluate_expression(condition)
        self.for_stack.append((condition, index))

        while condition_value:
            j = condition_end + 1
            while tokens[j][0] != 'NEXT':
                if tokens[j][0] == 'VAR':  # Описание переменных
                    j = self.handle_declaration(tokens, j)
                elif tokens[j][0] == 'IDENTIFIER' and tokens[j + 1][0] == 'ASSIGN':  # Присваивание значений
                    j = self.handle_assignment(tokens, j)
                elif tokens[j][0] == 'ENTER':
                    j = self.handle_input(tokens, j)
                elif tokens[j][0] == 'DISPL':
                    j = self.handle_display(tokens, j)
                elif tokens[j][0] == 'IF':
                    j = self.handle_if(tokens, j)
                elif tokens[j][0] == 'WHILE':
                    j = self.handle_while(tokens, j)
                elif tokens[j][0] == 'FOR':
                    j = self.handle_for(tokens, j)
                else:
                    raise SyntaxError(f"Неизвестная команда: {tokens[j]}")
                j += 1

            condition_value = self.evaluate_expression(condition)
            self.for_stack[-1] = (condition, index)

        self.for_stack.pop()
        return index

    def execute_block(self, tokens):
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token[0] == 'VAR':  # Описание переменных
                index = self.handle_declaration(tokens, index)
            elif token[0] == 'IDENTIFIER' and tokens[index + 1][0] == 'ASSIGN':  # Присваивание значений
                index = self.handle_assignment(tokens, index)
            elif token[0] == 'ENTER':  # Оператор ввода
                index = self.handle_input(tokens, index)
            elif token[0] == 'DISPL':  # Оператор вывода
                index = self.handle_display(tokens, index)
            elif token[0] == 'IF':  # Условный оператор
                index = self.handle_if(tokens, index)  # Обрабатываем if
            elif token[0] == 'WHILE':
                index = self.handle_while(tokens, index)
            elif token[0] == 'FOR':  # Фиксированный цикл
                index = self.handle_for(tokens, index)  # Обрабатываем for
            elif token[0] == 'NEXT':
                index += 1  # Пропускаем команду next
                continue
            elif token[0] == 'END':
                return
            elif token[0] == 'DELIMITER':
                index += 1  # Пропускаем разделители
                continue
            else:
                raise SyntaxError(f"Неизвестная команда: {token}")

    def evaluate_expression(self, tokens):
        if len(tokens) != 3:
            raise SyntaxError(f"Некорректное выражение: {tokens}")

        operand1 = self.get_value([tokens[0]])
        operator = tokens[1][1]
        operand2 = self.get_value([tokens[2]])

        # Проверка типов операндов для операций сравнения
        if operator in ["NEQ", "EQV", "GRT", "LOWT", "LOWE", "GRE"]:
            if (isinstance(operand1, int) and isinstance(operand2, int)) or (isinstance(operand1, float) and isinstance(operand2, float)):
                pass
            else:
                raise ValueError("Операнды для операций сравнения должны быть либо целыми числами (#), либо числами с плавающей точкой (@).")

        try:
            if operator == "add":
                return self.add(operand1, operand2)
            elif operator == "disa":
                return self.subtract(operand1, operand2)
            elif operator == "||":  # Дизъюнкция
                return bool(operand1) or bool(operand2)
            elif operator == "umn":
                return self.multiply(operand1, operand2)
            elif operator == "del":
                return self.divide(operand1, operand2)
            elif operator == "&&":  # Конъюнкция
                return bool(operand1) and bool(operand2)
            elif operator == "EQV":
                return operand1 == operand2
            elif operator == "NEQ":
                return operand1 != operand2
            elif operator == "GRT":
                return operand1 > operand2
            elif operator == "LOWT":
                return operand1 < operand2
            elif operator == "LOWE":
                return operand1 <= operand2
            elif operator == "GRE":
                return operand1 >= operand2
            else:
                raise ValueError(f"Неизвестная операция: {operator}")
        except Exception as e:
            raise ValueError(f"Ошибка при вычислении выражения: {e}")

    def get_value(self, tokens):
        token = tokens[0]
        if token[0] == 'NUMBER':
            return token[1]
        elif token[0] == 'IDENTIFIER':
            if token[1] in self.variables:
                return self.variables[token[1]]
            else:
                raise SyntaxError(f"Переменная '{token[1]}' не объявлена.")
        else:
            raise SyntaxError(f"Неизвестный токен: {token}")

    def add(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 + operand2
        raise ValueError("Операция сложения возможна только с числовыми типами.")

    def subtract(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 - operand2
        raise ValueError("Операция вычитания возможна только с числовыми типами.")

    def multiply(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 * operand2
        raise ValueError("Операция умножения возможна только с числовыми типами.")

    def divide(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            if operand2 == 0:
                raise ValueError("Деление на ноль.")
            return float(operand1) / float(operand2)
        else:
            raise ValueError("Операция деления возможна только с числовыми типами.")

    def convert_base(self, value, from_base, to_base):
        if from_base == 2:
            value = int(value, 2)
        elif from_base == 8:
            value = int(value, 8)
        elif from_base == 10:
            value = int(value)
        elif from_base == 16:
            value = int(value, 16)
        else:
            raise ValueError(f"Неподдерживаемая система счисления: {from_base}")

        if to_base == 2:
            return bin(value)[2:]
        elif to_base == 8:
            return oct(value)[2:]
        elif to_base == 10:
            return str(value)
        elif to_base == 16:
            return hex(value)[2:]
        else:
            raise ValueError(f"Неподдерживаемая система счисления: {to_base}")

    def handle_base_conversion(self, tokens, index):
        parts = tokens[index][1].split("convert")
        if len(parts) != 2:
            raise SyntaxError("Некорректное выражение.")

        var_name = parts[0].strip()
        expression = parts[1].strip().rstrip(";")

        if var_name not in self.variables:
            raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

        var_type = type(self.variables[var_name])
        if var_type != int:
            raise TypeError(f"Переменная '{var_name}' должна быть типа int для преобразования системы счисления.")

        from_base, to_base, value = expression.split()
        from_base = int(from_base)
        to_base = int(to_base)

        converted_value = self.convert_base(value, from_base, to_base)
        self.variables[var_name] = int(converted_value, to_base)
        return index

def read_file_by_char(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content.splitlines()

def main():
    # Define keywords and delimiters
    keywords = {
        'assign', 'end', 'begin', 'var', 'enter', 'displ', 'add', 'umn', 'disa', 'del',
        'if', 'then', 'else', 'while', 'do', 'next', 'for', 'val', 'GRT', 'LOWE', 'GRE'
    }
    delimiters = {',', ';', '#', '@', '&', ':','*', '(', ')'}

    # Create lexer instance
    lexer = Lexer(keywords, delimiters)

    # Read input code from a file
    file_path = input("Введите путь к файлу: ")
    try:
        with open(file_path, 'r') as file:
            code = file.read()  # Read the entire file content
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return

    # Tokenize input
    tokens = lexer.tokenize(code)
    for token in tokens:
        print(token)

    # Create interpreter instance
    interpreter = Interpreter()

    # Execute the tokenized lines
    interpreter.execute(tokens)

if __name__ == "__main__":
    main()
