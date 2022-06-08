import re
from io import StringIO, TextIOBase
from typing import Tuple, Union
from plugins.urcl.urcl import IInstruction, IOperand, Immediate, Port, Register, SpecialRegister, get_instructions, Label

_whitespace_regex = re.compile(r",?\s+")
_instructions = get_instructions()

class ParsingSource:
	def __init__(self, source_name: str, line_index: int) -> None:
		self.source_name = source_name
		self.line_index = line_index

class ParsingResult:
	def __init__(self) -> None:
		self.program: "list[IInstruction]" = []
		self.errors: "list[Tuple[int, str]]" = []
		self.warnings: "list[Tuple[int, str]]" = []
		self.labels: "dict[str, int]" = {}

class ParsingException(Exception):
	def __init__(self, message: str) -> None: self.message = message

def parse_source(source_text: str, source_name: str = "") -> ParsingResult:
	return parse_stream(StringIO(source_text), source_name)

def parse_stream(stream: TextIOBase, source_name: str = "") -> ParsingResult:
	result = ParsingResult()
	unmarked: dict[str, list[Label]] = {}
	line_index = 0
	while True:
		line = stream.readline()
		if line == "": break
		warnings = []
		for error in parse_line(line, result.program, result.labels, unmarked, warnings, line_index, source_name):
			result.errors.append((line_index + 1, error))
		for warning in warnings: result.warnings.append((line_index + 1, warning))
		line_index += 1
	for name in unmarked:
		for label in unmarked[name]:
			result.errors.append((label.source.line_index + 1, f"\"{name}\" is undefined."))
	return result

def parse_line(line: str, instructions: "list[IInstruction]", labels: "dict[str, int]", unmarked: "dict[str, list[Label]]", warnings: "list[str]", line_index: int = 0, source_name: str = "") -> "list[str]":
	errors: list[str] = []
	if "//" in line: line = line[:line.index("//")]
	line = re.sub(_whitespace_regex, " ", line.strip())
	if len(line) == 0: return errors
	if line.startswith("."):
		if " " in line:
			errors.append("Invalid syntax.")
			return errors
		address = len(instructions)
		labels[line] = address
		unmarked_labels = unmarked.get(line)
		if unmarked_labels != None:
			for label in unmarked_labels: label.address = address
			unmarked.pop(line)
	else:
		parts = line.split(" ")
		operation = parts[0].upper()
		a: Union[IOperand, None] = None
		b: Union[IOperand, None] = None
		c: Union[IOperand, None] = None
		try: a = None if len(parts) < 2 else parse_operand(parts[1], labels, unmarked, warnings, line_index, source_name)
		except ParsingException as ex: errors.append(ex.message)
		try: b = None if len(parts) < 3 else parse_operand(parts[2], labels, unmarked, warnings, line_index, source_name)
		except ParsingException as ex: errors.append(ex.message)
		try: c = None if len(parts) < 4 else parse_operand(parts[3], labels, unmarked, warnings, line_index, source_name)
		except ParsingException as ex: errors.append(ex.message)

		op_found: bool = False
		for instruction in _instructions:
			if instruction.__name__ == operation:
				op_found = True
				info = instruction.__init__.__annotations__
				if "a" in info and a == None: errors.append(f"Missing first operand of {operation}.")
				if "b" in info and b == None: errors.append(f"Missing second operand of {operation}.")
				if "c" in info and c == None: errors.append(f"Missing third operand of {operation}.")
				if a != None:
					if "a" in info:
						if not issubclass(a.__class__, info["a"]):
							errors.append(f"First operand of {operation} must match the type of {info['a'].__name__}.")
					else: errors.append(f"{operation} takes no operands but {len(parts) - 1} {'were' if len(parts) != 2 else 'was'} specified.")
				if b != None:
					if "b" in info:
						if not issubclass(b.__class__, info["b"]):
							errors.append(f"Second operand of {operation} must match the type of {info['b'].__name__}.")
					else: errors.append(f"{operation} takes 1 operand but {len(parts) - 1} {'were' if len(parts) != 2 else 'was'} specified.")
				if c != None:
					if "c" in info:
						if not issubclass(c.__class__, info["c"]):
							errors.append(f"Third operand of {operation} must match the type of {info['c'].__name__}.")
					else: errors.append(f"{operation} takes 2 operands but {len(parts) - 1} {'were' if len(parts) != 2 else 'was'} specified.")
		
				if len(errors) != 0: break
				if a == None: instructions.append(instruction(source=ParsingSource(source_name, line_index)))
				elif b == None: instructions.append(instruction(a, source=ParsingSource(source_name, line_index)))
				elif c == None: instructions.append(instruction(a, b, source=ParsingSource(source_name, line_index)))
				else: instructions.append(instruction(a, b, c, source=ParsingSource(source_name, line_index)))
				break
		if not op_found: errors.append(f"Unknown operation \"{operation}\".")
	
	return errors

def parse_operand(operand: str, labels: "dict[str, int]", unmarked: "dict[str, list[Label]]", warnings: "list[str]", line_index: int, source_name: str) -> IOperand:
	if len(operand) == 0: raise ParsingException("Empty operand.")
	prefix = operand.upper()[0]
	if prefix == "." and len(operand) > 1:
		label = Label(operand, source=ParsingSource(source_name, line_index))
		address = labels.get(operand)
		if address != None: label.address = address
		else:
			unmarked_labels = unmarked.get(operand)
			if unmarked_labels != None: unmarked_labels.append(label)
			else: unmarked[operand] = [label]
		return label
	elif prefix == "%" and len(operand) > 1: return Port(operand[1:], source=ParsingSource(source_name, line_index))
	elif prefix == "R" or prefix == "$" and len(operand) > 1:
		try:
			index = int(operand[1:])
			if index >= 0: return Register(index, source=ParsingSource(source_name, line_index))
		except: pass
	elif prefix.isdigit() or prefix == "-":
		try:
			value: int
			if len(operand) >= 3:
				if operand.upper().startswith("0X"): value = int(operand[2:], 16)
				elif operand.upper().startswith("0O"): value = int(operand[2:], 8)
				elif operand.upper().startswith("0B"): value = int(operand[2:], 2)
				else: value = int(operand)
			else: value = int(operand)
			return Immediate(value, source=ParsingSource(source_name, line_index))
		except: pass
	elif prefix.isalpha():
		operand = operand.upper()
		if not operand in ["PC", "SP"]: warnings.append(f"Use of non-standard register \"{operand}\".")
		return SpecialRegister(operand, source=ParsingSource(source_name, line_index))
	raise ParsingException(f"Invalid operand \"{operand}\".")