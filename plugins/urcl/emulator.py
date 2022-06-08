import random
import sys
from typing import Callable, Tuple, Union
from plugins.urcl.urcl import NOP, IInstruction, IMachine

class IDebugger:
	def set_break_callback(self, callback: "Callable[[IDebugger, dict], None]", data: dict = {}) -> None: ...
	def set_breakpoint(self, line: int) -> None: ...
	def remove_breakpoint(self, line: int) -> None: ...
	def get_line(self) -> Union[int, None]: ...
	def get_registers(self) -> "dict[str, int]": ...
	def get_stack(self) -> "list[Tuple[int, int]]": ...
	def get_call_stack(self) -> "list[Tuple[int, Union[str, None]]]": ...
	def get_hotpaths(self) -> "dict[str, dict[int, float]]": ...
	def read_memory(self, address: int) -> int: ...
	def resume(self) -> None: ...
	def step_into(self) -> None: ...
	def step_over(self) -> None: ...
	def step_out(self) -> None: ...

class URCLEmulator(IMachine, IDebugger):
	def __init__(self, integer_mask: int = 0xFFFFFFFFFFFFFFFF) -> None:
		self.general_registers: list[int] = []
		self.special_registers: list[int] = []
		self.special_register_map: dict[str, int] = {}
		self.set_bit_mask(integer_mask)
		self.memory_block_size: int = 0x10000
		self.memory_block_offset_mask: int = self.memory_block_size - 1
		self.memory_block_offset_bits: int = self._get_bit_count(self.memory_block_offset_mask)
		self.memory_blocks: dict[int, list[int]] = {}
		self.ports: list[IPort] = []
		self.port_map: dict[str, int] = {}
		self.port_data: dict = {}
		self.labels: dict[int, str] = {}
		self.rom: list[IInstruction] = []
		self.call_stack: list[int] = []
		self.call_source_stack: list[int] = []
		self.hotpaths: dict[str, dict[int, int]] = {}
		self.executing: bool = False
		self.debugging: bool = False
		self.break_callback: Union[Callable[[IDebugger, dict], None], None] = None
		self.break_data: dict = {}
		self.breakpoints: list[int] = []
		self.gopoints: list[int] = []
		self.pc = self.get_special_register_id("PC")
	
	def set_bit_mask(self, integer_mask: int) -> None:
		if integer_mask <= 0: raise Exception("Integer mask must be greater than zero.")
		self.integer_mask = integer_mask
		self.integer_bits = self._get_bit_count(self.integer_mask)

	def load_program_rom(self, program: "list[IInstruction]") -> None:
		self.rom = program
		for instruction in self.rom: instruction.compile(self)
	
	def set_port_data(self, data: dict = {}) -> None:
		self.port_data = data
	
	def get_port_data(self) -> dict:
		return self.port_data

	def set_break_callback(self, callback: "Callable[[IDebugger, dict], None]", data: dict = {}) -> None:
		self.break_callback = callback
		self.break_data = data
	
	def set_breakpoint(self, line: int) -> None:
		self.breakpoints.append(line)
	
	def remove_breakpoint(self, line: int) -> None:
		self.breakpoints.remove(line)

	def set_gopoint(self, address: int) -> None:
		self.gopoints.append(address)

	def add_label(self, address: int, name: str) -> None: self.labels[address] = name

	def add_port(self, name: str, port: "IPort") -> None:
		self.port_map[name] = len(self.ports)
		self.ports.append(port)

	def execute(self) -> None:
		self.executing = True
		while self.executing: self.step()

	def step(self) -> None:
		address = self.read_special_register(self.pc)
		if address >= 0 and address < len(self.rom):
			if address in self.gopoints:
				self.gopoints.remove(address)
				self.debug()
			elif len(self.breakpoints) > 0:
				source = self.get_current_instruction().source
				if source != None and (getattr(source, "line_index", -1) + 1) in self.breakpoints: self.debug()
			if self.debugging and self.break_callback != None:
				self.break_callback(self, self.break_data)
			else:
				self.step_into()
		else:
			self.executing = False
	
	def get_line(self) -> Union[int, None]:
		instruction = self.get_current_instruction()
		result = getattr(instruction.source, "line_index", None) if instruction.source != None else None
		return result + 1 if result != None else result

	def get_registers(self) -> "dict[str, int]":
		result: "dict[str, int]" = {}
		for i in range(1, len(self.general_registers), 1): result[f"R{i}"] = self.general_registers[i]
		for name in self.special_register_map: result[name] = self.special_registers[self.special_register_map[name]]
		return result
	
	def get_stack(self) -> "list[Tuple[int, int]]":
		result: list[Tuple[int, int]] = []
		sp = self.read_special_register(self.get_special_register_id("SP"))
		if sp != 0:
			min_sp = self.integer_mask if (self.integer_mask - sp) < 32 else sp + 32
			for i in range(sp, min_sp + 1, 1): result.append((i, self.read_memory(i)))
		return result

	def get_call_stack(self) -> "list[Tuple[int, Union[str, None]]]":
		result: "list[Tuple[int, Union[str, None]]]" = []
		for address in self.call_stack:
			result.append((address, self.labels.get(address, None)))
		return result
	
	def get_address_name(self, address: int) -> str:
		return self.labels.get(address, "0x" + hex(address).lstrip("0x").upper().rjust(int(self.integer_bits / 4), "0"))

	def get_hotpaths(self) -> "dict[str, dict[int, float]]":
		result: dict[str, dict[int, float]] = {}
		for func in self.hotpaths:
			total: float = 0.0
			func_result: dict[int, float] = {}
			for line in self.hotpaths[func]: total += self.hotpaths[func][line]
			for line in self.hotpaths[func]: func_result[line] = self.hotpaths[func][line] / total
			result[func] = func_result
		return result

	def get_current_instruction(self) -> IInstruction:
		return self.get_instruction(self.read_special_register(self.pc))
	
	def get_instruction(self, address: int) -> IInstruction:
		return NOP() if address < 0 or address >= len(self.rom) else self.rom[address]
	
	def get_bit_mask(self) -> int: return self.integer_mask
	
	def get_sign_bit_mask(self) -> int: return 1 << (self.integer_mask - 1)

	def read_register(self, index: int) -> int:
		return 0 if index >= len(self.general_registers) else self.general_registers[index]
	
	def write_register(self, index: int, value: int) -> None:
		if index == 0: return
		while len(self.general_registers) <= index: self.general_registers.append(0)
		self.general_registers[index] = value & self.integer_mask
	
	def get_special_register_id(self, name: str) -> int:
		result = self.special_register_map.get(name)
		if result == None:
			result = len(self.special_registers)
			self.special_register_map[name] = result
			self.special_registers.append(0)
		return result
	
	def read_special_register(self, id: int) -> int: return self.special_registers[id]
	def write_special_register(self, id: int, value: int) -> None: self.special_registers[id] = value & self.integer_mask

	def read_memory(self, address: int) -> int:
		if address < 0: address += self.integer_mask + 1
		offset = address & self.memory_block_offset_mask
		address = address >> self.memory_block_offset_bits
		block = self.memory_blocks.get(address)
		return 0 if block == None else block[offset]
	
	def write_memory(self, address: int, value: int) -> None:
		if address < 0: address += self.integer_mask + 1
		offset = address & self.memory_block_offset_mask
		address = address >> self.memory_block_offset_bits
		block = self.memory_blocks.get(address)
		if block == None:
			block = [0] * self.memory_block_size
			self.memory_blocks[address] = block
		block[offset] = value & self.integer_mask
	
	def get_port_id(self, name: str) -> int:
		result = self.port_map.get(name)
		if result == None: raise Exception(f"Port \"{name}\" does not exist.")
		return result
	
	def read_port(self, id: int) -> int: return self.ports[id].read(self)
	def write_port(self, id: int, value: int) -> None: self.ports[id].write(self, value)
	
	def halt(self) -> None: self.executing = False

	def resume(self) -> None: self.debugging = False

	def step_into(self) -> None:
		self.mark_hotpath(self.read_special_register(self.pc))
		self.get_current_instruction().execute(self)
		if self.executing: self.write_special_register(self.pc, self.read_special_register(self.pc) + 1)

	def step_over(self) -> None:
		self.set_gopoint(self.read_special_register(self.pc) + 1)
		self.step_into()
		self.debugging = False
	
	def step_out(self) -> None:
		if len(self.call_stack) > 0: self.set_gopoint(self.call_stack[len(self.call_stack) - 1])
		self.step_into()
		self.debugging = False

	def debug(self) -> None:
		self.debugging = True

	def indicate_call(self, return_address: int) -> None:
		address = self.read_special_register(self.pc) + 1
		self.call_stack.append(address)
		self.call_source_stack.append(return_address)
	
	def indicate_return(self) -> None:
		if len(self.call_stack) > 0: self.call_stack.pop()
		if len(self.call_source_stack) > 0: self.call_source_stack.pop()

	def mark_hotpath(self, address: int, source_index: int = -1) -> None:
		line = getattr(self.get_instruction(address).source, "line_index", -1) + 1
		if line == 0: return
		elif source_index < 0:
			func = self.get_address_name(self.call_stack[len(self.call_stack) - 1] if len(self.call_stack) > 0 else 0)
		else:
			func = self.get_address_name(self.call_stack[source_index - 1] if len(self.call_stack) > 1 else 0)
		func_hotpaths = self.hotpaths.get(func, None)
		if func_hotpaths == None:
			func_hotpaths = {}
			self.hotpaths[func] = func_hotpaths
		current = func_hotpaths.get(line, 0)
		func_hotpaths[line] = current + 1
		if source_index != 0 and len(self.call_source_stack) > 0:
			index = len(self.call_source_stack) - 1 if source_index < 0 else source_index - 1
			self.mark_hotpath(self.call_source_stack[index], index)

	def _get_bit_count(self, value: int) -> int:
		result = 0
		while value > 0:
			result += 1
			value >>= 1
		return result

class IPort:
	def read(self, machine: URCLEmulator) -> int: ...
	def write(self, machine: URCLEmulator, value: int) -> None: ...

class StdioPort(IPort):
	def read(self, machine: URCLEmulator) -> int:
		try: return ord(sys.stdin.read(1))
		except: return 0
	
	def write(self, machine: URCLEmulator, value: int) -> None:
		sys.stdout.write(chr(value & 0xFF))

class RandomPort(IPort):
	def read(self, machine: URCLEmulator) -> int:
		return random.randint(0, machine.get_bit_mask())
	
	def write(self, machine: URCLEmulator, value: int) -> None: return