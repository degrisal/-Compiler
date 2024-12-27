import re
import logging


# Настройка логирования с указанием кодировки
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # Указываем кодировку utf-8
)
class Lexer:
    def __init__(self, keywords, delimiters):
        self.keywords = keywords
        self.delimiters = delimiters
        self.token_specification = [
            ('NUMBER',   r'\d+(\.\d*)?([eE][+-]?\d+)?'),  # Добавлена поддержка экспоненциальной записи
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
                logging.error(f'{value!r} unexpected on line {line_num}')
                raise RuntimeError(f'{value!r} unexpected on line {line_num}')
            tokens.append((kind, value))
        return tokens

keywords = {
            'assign', 'end', 'begin', 'var', 'enter', 'displ', 'add', 'umn', 'disa', 'del',
            'if', 'then', 'else', 'while', 'do', 'next', 'for', 'val', 'GRT', 'LOWE', 'GRE'
        }
delimiters = {',', ';', '#', '@', '&', ':','*', '(', ')'}

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

    def execute(self, lines):
        if not lines or lines[0].strip().lower() != "begin":
            logging.error("Программа должна начинаться с 'begin'.")
            raise SyntaxError("Программа должна начинаться с 'begin'.")

        index = 1  # Начинаем с первой строки после 'begin'
        in_comment_block = False
        while index < len(lines):
            line = lines[index].strip()

            if "(*" in line:
                in_comment_block = True
            if "*)" in line:
                in_comment_block = False
                index += 1
                continue
            if in_comment_block:
                index += 1
                continue

            if line.startswith("var"):  # Описание переменных
                self.handle_declaration(line)
            elif "assign" in line and not line.startswith("for"):  # Присваивание значений
                self.handle_assignment(line)
            elif line.lower().startswith("enter"):  # Оператор ввода
                self.handle_input(line)
            elif line.lower().startswith("displ"):  # Оператор вывода
                self.handle_display(line)
            elif line.lower().startswith("if"):  # Условный оператор
                index = self.handle_if(lines, index)  # Обрабатываем if
            elif line.lower().startswith("while"):
                index = self.handle_while(line, lines, index)
            elif line.lower().startswith("for"):  # Фиксированный цикл
                index = self.handle_for(line, lines, index)  # Обрабатываем for
            elif line.lower() == "next":
                index += 1  # Пропускаем команду next
                continue
            elif line.lower() == "end":
                return
            else:
                logging.error(f"Неизвестная команда: {line}")
                raise SyntaxError(f"Неизвестная команда: {line}")
            index += 1

    def handle_declaration(self, line):
        parts = line[4:].split(";")  # Убираем "var " и разбиваем по ';'
        for declaration in parts:
            declaration = declaration.strip()
            if not declaration:
                continue
            type_and_vars = declaration.split(" ", 1)
            if len(type_and_vars) != 2:
                logging.error("Некорректное описание переменных.")
                raise SyntaxError("Некорректное описание переменных.")

            var_type = type_and_vars[0].strip()  # Тип (#, @, &)
            identifiers = [var.strip() for var in type_and_vars[1].split(",")]

            for identifier in identifiers:
                if identifier in self.variables:
                    logging.error(f"Переменная '{identifier}' уже объявлена.")
                    raise SyntaxError(f"Переменная '{identifier}' уже объявлена.")
                if var_type not in ["#", "@", "&"]:
                    logging.error(f"Некорректный тип '{var_type}'.")
                    raise SyntaxError(f"Некорректный тип '{var_type}'.")
                # Инициализируем переменную значением по умолчанию
                if var_type == "#":
                    self.variables[identifier] = 0
                elif var_type == "@":
                    self.variables[identifier] = 0.0
                elif var_type == "&":
                    self.variables[identifier] = False
                self.described_variables.add(identifier)

    def handle_assignment(self, line):
        parts = line.split("assign")
        if len(parts) != 2:
            logging.error("Некорректное выражение.")
            raise SyntaxError("Некорректное выражение.")

        var_name = parts[0].strip()
        expression = parts[1].strip().rstrip(";")

        if var_name not in self.variables:
            logging.error(f"Переменная '{var_name}' не объявлена.")
            raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

        var_type = type(self.variables[var_name])
        value = self.get_value(expression)

        if var_type == int and not isinstance(value, int):
            logging.error(f"Переменная '{var_name}' типа int, но присваиваемое значение типа {type(value).__name__}.")
            raise TypeError(f"Переменная '{var_name}' типа int, но присваиваемое значение типа {type(value).__name__}.")
        elif var_type == float and not isinstance(value, float):
            logging.error(f"Переменная '{var_name}' типа float, но присваиваемое значение типа {type(value).__name__}.")
            raise TypeError(f"Переменная '{var_name}' типа float, но присваиваемое значение типа {type(value).__name__}.")
        elif var_type == bool and not isinstance(value, bool):
            logging.error(f"Переменная '{var_name}' типа bool, но присваиваемое значение типа {type(value).__name__}.")
            raise TypeError(f"Переменная '{var_name}' типа bool, но присваиваемое значение типа {type(value).__name__}.")

        self.variables[var_name] = value

    def handle_input(self, line):
        parts = line[5:].split()  # Убираем "enter " и делим по пробелам
        for var_name in parts:
            var_name = var_name.strip()
            if var_name not in self.variables:
                logging.error(f"Переменная '{var_name}' не объявлена.")
                raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

            # Запрашиваем ввод от пользователя
            value = input(f"Введите значение для {var_name}: ").strip()

            # В зависимости от типа переменной, преобразуем введенное значение
            if isinstance(self.variables[var_name], int):
                if value.startswith("B") or value.startswith("b"):  # Двоичное число
                    try:
                        self.variables[var_name] = int(value[1:], 2)
                    except ValueError:
                        logging.error(f"Неверный тип данных для переменной {var_name}, ожидается двоичное число.")
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается двоичное число.")
                elif value.startswith("O") or value.startswith("o"):  # Восьмеричное число
                    try:
                        self.variables[var_name] = int(value[1:], 8)
                    except ValueError:
                        logging.error(f"Неверный тип данных для переменной {var_name}, ожидается восьмеричное число.")
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается восьмеричное число.")
                elif value.startswith("H") or value.startswith("h"):  # Шестнадцатеричное число
                    try:
                        self.variables[var_name] = int(value[1:], 16)
                    except ValueError:
                        logging.error(f"Неверный тип данных для переменной {var_name}, ожидается шестнадцатеричное число.")
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается шестнадцатеричное число.")
                else:
                    try:
                        self.variables[var_name] = int(value)
                    except ValueError:
                        logging.error(f"Неверный тип данных для переменной {var_name}, ожидается целое число.")
                        raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается целое число.")
            elif isinstance(self.variables[var_name], float):
                try:
                    self.variables[var_name] = float(value)
                except ValueError:
                    logging.error(f"Неверный тип данных для переменной {var_name}, ожидается число с плавающей точкой.")
                    raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается число с плавающей точкой.")
            elif isinstance(self.variables[var_name], bool):
                if value.lower() == "true":
                    self.variables[var_name] = True
                elif value.lower() == "false":
                    self.variables[var_name] = False
                else:
                    logging.error(f"Неверный тип данных для переменной {var_name}, ожидается логическое значение (true/false).")
                    raise ValueError(f"Неверный тип данных для переменной {var_name}, ожидается логическое значение (true/false).")

    def handle_display(self, line):
        expressions = line[5:].strip()  # Удаляем лишние символы
        if not expressions:
            logging.error("Не указаны выражения для вывода.")
            raise SyntaxError("Не указаны выражения для вывода.")

        expr_list = expressions.split(",")
        for expr in expr_list:
            expr = expr.strip()
            value = self.get_value(expr)
            print(value, end=" ")
        print()

    def handle_if(self, lines, index):
        line = lines[index].strip()
        if "then" not in line or "end" not in line:
            logging.error("Ожидается синтаксис 'if <условие> then <оператор> [else <оператор>] end'.")
            raise SyntaxError("Ожидается синтаксис 'if <условие> then <оператор> [else <оператор>] end'.")

        condition = line[line.index("if") + 2:line.index("then")].strip()
        body = line[line.index("then") + 4:line.rindex("end")].strip()

        if "else" in body:
            then_expression = body[:body.index("else")].strip()
            else_expression = body[body.index("else") + 4:].strip()
        else:
            then_expression = body
            else_expression = None

        # Вычисляем условие
        condition_result = self.evaluate_expression(condition)

        if condition_result:
            self.execute_block(then_expression.split(";"))
        elif else_expression:
            self.execute_block(else_expression.split(";"))
        return index

    def handle_while(self, line, lines, index):
        if not line.lower().startswith("while"):
            logging.error("Некорректный вызов while.")
            raise SyntaxError("Некорректный вызов while.")

        condition = line[5:].strip().rstrip("do")
        condition_value = self.evaluate_expression(condition)
        self.while_stack.append((condition, index))

        while condition_value:
            j = index + 1
            while j < len(lines):
                line = lines[j].strip()
                if line.lower() == "next":  # Завершение блока
                    break
                elif "var" in line:  # Описание переменных
                    self.handle_declaration(line)
                elif "assign" in line:  # Присваивание значений
                    self.handle_assignment(line)
                elif line.lower().startswith("enter"):
                    self.handle_input(line)
                elif line.lower().startswith("displ"):
                    self.handle_display(line)
                elif line.lower().startswith("if"):
                    j = self.handle_if(lines, j)
                elif line.lower().startswith("while"):
                    j = self.handle_while(line, lines, j)
                elif line.lower().startswith("for"):
                    j = self.handle_for(line, lines, j)
                else:
                    logging.error(f"Неизвестная команда: {line}")
                    raise SyntaxError(f"Неизвестная команда: {line}")
                j += 1

            condition_value = self.evaluate_expression(condition)
            self.while_stack[-1] = (condition, index)

        self.while_stack.pop()
        return index

    def handle_for(self, line, lines, index):
        if not line.lower().startswith("for"):
            logging.error("Некорректный вызов for.")
            raise SyntaxError("Некорректный вызов for.")

        parts = line[3:].strip().rstrip("do").split(" val ")
        if len(parts) != 2:
            logging.error("Некорректный синтаксис for.")
            raise SyntaxError("Некорректный синтаксис for.")

        assignment = parts[0].strip()
        end_expression = parts[1].strip()

        # Разбиваем присваивание на переменную и начальное значение
        var_name, start_value = assignment.split(" assign ")
        var_name = var_name.strip()
        start_value = start_value.strip()

        # Выполняем присваивание начального значения
        self.handle_assignment(f"{var_name} assign {start_value}")

        # Обрабатываем end_expression как значение
        if end_expression.startswith("#"):
            end = int(end_expression[1:])
        elif end_expression.startswith("@"):
            end = float(end_expression[1:])
        else:
            logging.error(f"Некорректное выражение: {end_expression}")
            raise SyntaxError(f"Некорректное выражение: {end_expression}")

        if var_name not in self.described_variables:
            logging.error(f"Переменная '{var_name}' не описана.")
            raise ValueError(f"Переменная '{var_name}' не описана.")

        self.for_stack.append((var_name, end, index))

        while self.variables[var_name] <= end:
            j = index + 1
            while j < len(lines):
                line = lines[j].strip()
                if "var" in line:  # Описание переменных
                    self.handle_declaration(line)
                elif "assign" in line:  # Присваивание значений
                    self.handle_assignment(line)
                elif line.lower().startswith("enter"):
                    self.handle_input(line)
                elif line.lower().startswith("displ"):
                    self.handle_display(line)
                elif line.lower().startswith("if"):
                    j = self.handle_if(lines, j)
                elif line.lower().startswith("while"):
                    j = self.handle_while(line, lines, j)
                elif line.lower().startswith("for"):
                    j = self.handle_for(line, lines, j)
                else:
                    logging.error(f"Неизвестная команда: {line}")
                    raise SyntaxError(f"Неизвестная команда: {line}")
                j += 1

            self.variables[var_name] += 1
            self.for_stack[-1] = (var_name, end, index)

        self.for_stack.pop()
        return index

    def execute_block(self, lines):
        for line in lines:
            if not line.strip():
                continue
            if "var" in line:  # Описание переменных
                self.handle_declaration(line)
            elif "assign" in line:  # Присваивание значений
                self.handle_assignment(line)
            elif line.lower().startswith("enter"):
                self.handle_input(line)
            elif line.lower().startswith("displ"):
                self.handle_display(line)
            elif line.lower().startswith("if"):
                self.handle_if(lines, lines.index(line))
            elif line.lower().startswith("while"):
                self.handle_while(line, lines, lines.index(line))
            elif line.lower().startswith("for"):
                self.handle_for(line, lines, lines.index(line))
            else:
                logging.error(f"Неизвестная команда: {line}")
                raise SyntaxError(f"Неизвестная команда: {line}")

    def evaluate_expression(self, expression):
        tokens = expression.split()
        if len(tokens) != 3:
            logging.error(f"Некорректное выражение: {expression}")
            raise SyntaxError(f"Некорректное выражение: {expression}")

        operand1 = self.get_value(tokens[0])
        operator = tokens[1]
        operand2 = self.get_value(tokens[2])

        # Проверка типов операндов для операций сравнения
        if operator in ["NEQ", "EQV", "GRT", "LOWT", "LOWE", "GRE"]:
            if (isinstance(operand1, int) and isinstance(operand2, int)) or (isinstance(operand1, float) and isinstance(operand2, float)):
                pass
            else:
                logging.error("Операнды для операций сравнения должны быть либо целыми числами (#), либо числами с плавающей точкой (@).")
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
                logging.error(f"Неизвестная операция: {operator}")
                raise ValueError(f"Неизвестная операция: {operator}")
        except Exception as e:
            logging.error(f"Ошибка при вычислении выражения: {e}")
            raise ValueError(f"Ошибка при вычислении выражения: {e}")

    def get_value(self, token):
            token = token.strip()
            if token.startswith("#"):  # Целое число
                return int(float(token[1:]))  # Преобразуем в float, затем в int
            elif token.startswith("@"):  # Плавающая точка
                return float(token[1:])
            elif token.startswith("&"):  # Булевое значение
                return token[1:] == "true"
            elif token.startswith("B"):  # Двоичное число
                if len(token) > 1:
                    return int(token[1:], 2)
                else:
                    logging.error("Некорректное двоичное число.")
                    raise ValueError("Некорректное двоичное число.")
            elif token.startswith("O") or token.startswith("o"):  # Восьмеричное число
                if len(token) > 1:
                    return int(token[1:], 8)
                else:
                    logging.error("Некорректное восьмеричное число.")
                    raise ValueError("Некорректное восьмеричное число.")
            elif token.startswith("H"):  # Шестнадцатеричное число
                if len(token) > 1:
                    return int(token[1:], 16)
                else:
                    logging.error("Некорректное шестнадцатеричное число.")
                    raise ValueError("Некорректное шестнадцатеричное число.")
            elif token.startswith("D"):  # Десятичное число
                if len(token) > 1:
                    return int(token[1:], 10)
                else:
                    logging.error("Некорректное десятичное число.")
                    raise ValueError("Некорректное десятичное число.")
            elif token in self.variables:  # Переменная
                return self.variables[token]
            elif token == "true":
                return True
            elif token == "false":
                return False
            else:
                # Если токен представляет собой выражение, вычисляем его значение
                return self.evaluate_expression(token)

    def add(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 + operand2
        logging.error("Операция сложения возможна только с числовыми типами.")
        raise ValueError("Операция сложения возможна только с числовыми типами.")

    def subtract(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 - operand2
        logging.error("Операция вычитания возможна только с числовыми типами.")
        raise ValueError("Операция вычитания возможна только с числовыми типами.")

    def multiply(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            return operand1 * operand2
        logging.error("Операция умножения возможна только с числовыми типами.")
        raise ValueError("Операция умножения возможна только с числовыми типами.")

    def divide(self, operand1, operand2):
        if isinstance(operand1, (int, float)) and isinstance(operand2, (int, float)):
            if operand2 == 0:
                logging.error("Деление на ноль.")
                raise ValueError("Деление на ноль.")
            return float(operand1) / float(operand2)
        else:
            logging.error("Операция деления возможна только с числовыми типами.")
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
            logging.error(f"Неподдерживаемая система счисления: {from_base}")
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
            logging.error(f"Неподдерживаемая система счисления: {to_base}")
            raise ValueError(f"Неподдерживаемая система счисления: {to_base}")

    def handle_base_conversion(self, line):
        parts = line.split("convert")
        if len(parts) != 2:
            logging.error("Некорректное выражение.")
            raise SyntaxError("Некорректное выражение.")

        var_name = parts[0].strip()
        expression = parts[1].strip().rstrip(";")

        if var_name not in self.variables:
            logging.error(f"Переменная '{var_name}' не объявлена.")
            raise SyntaxError(f"Переменная '{var_name}' не объявлена.")

        var_type = type(self.variables[var_name])
        if var_type != int:
            logging.error(f"Переменная '{var_name}' должна быть типа int для преобразования системы счисления.")
            raise TypeError(f"Переменная '{var_name}' должна быть типа int для преобразования системы счисления.")

        from_base, to_base, value = expression.split()
        from_base = int(from_base)
        to_base = int(to_base)

        converted_value = self.convert_base(value, from_base, to_base)
        self.variables[var_name] = int(converted_value, to_base)

def read_file_by_char(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content.splitlines()

if __name__ == "__main__":
    file_path = input("Введите путь к файлу: ")

    # Чтение файла для лексера
    try:
        with open(file_path, 'r') as file:
            code = file.read()
    except FileNotFoundError:
        logging.error(f"The file '{file_path}' was not found.")
        print(f"Error: The file '{file_path}' was not found.")
        exit(1)

    lexer = Lexer(keywords, delimiters)
    tokens = lexer.tokenize(code)
    for token in tokens:
        print(token)

    # Чтение файла для интерпретатора
    lines = read_file_by_char(file_path)

    interpreter = Interpreter()
    interpreter.execute(lines)
