import inspect, sys
from typing import Union

class IMachine:
	def read_register(self, index: int) -> int: ...
	def write_register(self, index: int, value: int) -> None: ...
	def get_special_register_id(self, name: str) -> int: ...
	def read_special_register(self, id: int) -> int: ...
	def write_special_register(self, id: int, value: int) -> None: ...
	def read_memory(self, address: int) -> int: ...
	def write_memory(self, address: int, value: int) -> None: ...
	def get_port_id(self, name: str) -> int: ...
	def read_port(self, id: int) -> int: ...
	def write_port(self, id: int, value: int) -> None: ...
	def get_sign_bit_mask(self) -> int: ...
	def get_bit_mask(self) -> int: ...
	def set_bit_mask(self, value: int) -> None: ...
	def halt(self) -> None: ...
	def debug(self) -> None: ...
	def indicate_call(self, return_address: int) -> None: ...
	def indicate_return(self) -> None: ...

class IOperand:
	def __init__(self, source) -> None: self.source = source
	def add_offset(self, offset: int) -> None: return
	def compile(self, machine: IMachine) -> None: return
	def load(self, machine: IMachine) -> int: ...
	def store(self, machine: IMachine, value: int) -> None: raise Exception("Operand type does not allow for a store operation.")

class IRegister(IOperand):
	def __init__(self, source) -> None: super().__init__(source)

class Register(IRegister):
	def __init__(self, index: int, source = None) -> None:
		super().__init__(source)
		self.index = index
	def load(self, machine: IMachine) -> int: return machine.read_register(self.index)
	def store(self, machine: IMachine, value: int) -> None: return machine.write_register(self.index, value)
	def __str__(self) -> str: return f"R{self.index}"

class SpecialRegister(IRegister):
	def __init__(self, name: str, source = None) -> None:
		super().__init__(source)
		self.name = name
	def compile(self, machine: IMachine) -> None: self.id = machine.get_special_register_id(self.name)
	def load(self, machine: IMachine) -> int: return machine.read_special_register(self.id)
	def store(self, machine: IMachine, value: int) -> None: machine.write_special_register(self.id, value)
	def __str__(self) -> str: return self.name

class Immediate(IOperand):
	def __init__(self, value: int, source = None) -> None:
		super().__init__(source)
		self.value = value
	def compile(self, machine: IMachine) -> None: self.value &= machine.get_bit_mask()
	def load(self, machine: IMachine) -> int: return self.value
	def __str__(self) -> str: return hex(self.value)

class Label(IOperand):
	def __init__(self, name: str = "", address: int = -1, source = None) -> None:
		super().__init__(source)
		self.name = name
		self.address = address
	def add_offset(self, offset: int) -> None: self.address += offset
	def load(self, machine: IMachine) -> int: return self.address
	def __str__(self) -> str: return self.name if self.name != "" else hex(self.address)

class Port(IOperand):
	def __init__(self, name: str, source = None) -> None:
		super().__init__(source)
		self.name = name
	def compile(self, machine: IMachine) -> None: self.id = machine.get_port_id(self.name)
	def load(self, machine: IMachine) -> int: return machine.read_port(self.id)
	def store(self, machine: IMachine, value: int) -> None: return machine.write_port(self.id, value)
	def __str__(self) -> str: return f"%{self.name}"

class IInstruction:
	def __init__(self, a: Union[IOperand, None] = None, b: Union[IOperand, None] = None, c: Union[IOperand, None] = None, source = None) -> None:
		self.a = a
		self.b = b
		self.c = c
		self.source = source
	def add_offset(self, offset: int) -> None:
		if self.a != None: self.a.add_offset(offset)
		if self.b != None: self.b.add_offset(offset)
		if self.c != None: self.c.add_offset(offset)
	def compile(self, machine: IMachine) -> None:
		if self.a != None: self.a.compile(machine)
		if self.b != None: self.b.compile(machine)
		if self.c != None: self.c.compile(machine)
	def execute(self, machine: IMachine) -> None: ...
	def __str__(self) -> str:
		return f"{self.__class__.__name__} {self.a if self.a != None else ''} {self.b if self.b != None else ''} {self.c if self.c != None else ''}"

class IStackInstruction(IInstruction):
	def __init__(self, a: Union[IOperand, None] = None, b: Union[IOperand, None] = None, c: Union[IOperand, None] = None, source = None) -> None:
		super().__init__(a, b, c, source=source)
		self.sp = -1
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.sp = machine.get_special_register_id("SP")

class IBranchInstruction(IInstruction):
	def __init__(self, a: Union[IOperand, None] = None, b: Union[IOperand, None] = None, c: Union[IOperand, None] = None, source = None) -> None:
		super().__init__(a, b, c, source=source)
		self.pc = -1
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.pc = machine.get_special_register_id("PC")

class LOD(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, machine.read_memory(self.b.load(machine)))

class STR(IInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: machine.write_memory(self.a.load(machine), self.b.load(machine))

class CPY(IInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: machine.write_memory(self.a.load(machine), machine.read_memory(self.b.load(machine)))

class ADD(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) + self.c.load(machine))

class SUB(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) - self.c.load(machine))

class MLT(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) * self.c.load(machine))

class DIV(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) / self.c.load(machine))

class MOD(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) % self.c.load(machine))

class RSH(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) >> 1)

class BSR(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) >> self.c.load(machine))

class LSH(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) << 1)

class BSL(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) << self.c.load(machine))

class OR(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) | self.c.load(machine))

class AND(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) & self.c.load(machine))

class XOR(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) ^ self.c.load(machine))

class NOR(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, ~(self.b.load(machine) | self.c.load(machine)))

class NAND(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, ~(self.b.load(machine) & self.c.load(machine)))

class XNOR(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, ~(self.b.load(machine) ^ self.c.load(machine)))

class NOT(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, ~self.b.load(machine))

class NEG(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, -self.b.load(machine))

class INC(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) + 1)

class DEC(IInstruction):
	def __init__(self, a: IRegister, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine) - 1)

class MOV(IInstruction):
	def __init__(self, a: IRegister, b: IRegister, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine))

class IMM(IInstruction):
	def __init__(self, a: IRegister, b: Immediate, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine))

class NOP(IInstruction):
	def __init__(self, source = None) -> None: super().__init__(source=source)
	def execute(self, machine: IMachine) -> None: return

class JMP(IBranchInstruction):
	def __init__(self, a: IOperand, source = None) -> None: super().__init__(a, source=source)
	def execute(self, machine: IMachine) -> None: machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRZ(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) == 0:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BNZ(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) != 0:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BEV(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) % 2 == 0:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BOD(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) % 2 == 1:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRP(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.bit_mask = machine.get_sign_bit_mask()
	def execute(self, machine: IMachine) -> None:
		if (self.b.load(machine) & self.bit_mask) == 0:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRN(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.bit_mask = machine.get_sign_bit_mask()
	def execute(self, machine: IMachine) -> None:
		if (self.b.load(machine) & self.bit_mask) != 0:
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRC(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.int_max = machine.get_bit_mask()
	def execute(self, machine: IMachine) -> None:
		if (self.b.load(machine) > (self.int_max - self.c.load(machine))):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BNC(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.int_max = machine.get_bit_mask()
	def execute(self, machine: IMachine) -> None:
		if (self.b.load(machine) <= (self.int_max - self.c.load(machine))):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRE(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) == self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BNE(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) != self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRL(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) < self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BRG(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) > self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BLE(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) <= self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class BGE(IBranchInstruction):
	def __init__(self, a: IOperand, b: IOperand, c: IOperand, source = None) -> None: super().__init__(a, b, c, source=source)
	def execute(self, machine: IMachine) -> None:
		if self.b.load(machine) >= self.c.load(machine):
			machine.write_special_register(self.pc, self.a.load(machine) - 1)

class PSH(IStackInstruction):
	def __init__(self, a: IOperand, source = None) -> None: super().__init__(a, source=source)
	def execute(self, machine: IMachine) -> None:
		sp = machine.read_special_register(self.sp) - 1
		machine.write_special_register(self.sp, sp)
		machine.write_memory(sp, self.a.load(machine))

class POP(IStackInstruction):
	def __init__(self, a: IRegister, source = None) -> None: super().__init__(a, source=source)
	def execute(self, machine: IMachine) -> None:
		sp = machine.read_special_register(self.sp)
		self.a.store(machine, machine.read_memory(sp))
		machine.write_special_register(self.sp, sp + 1)

class CAL(IInstruction):
	def __init__(self, a: IOperand, source = None) -> None: super().__init__(a, source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.sp = machine.get_special_register_id("SP")
		self.pc = machine.get_special_register_id("PC")
	def execute(self, machine: IMachine) -> None:
		sp = machine.read_special_register(self.sp) - 1
		return_address = machine.read_special_register(self.pc)
		machine.write_special_register(self.sp, sp)
		machine.write_memory(sp, return_address)
		machine.write_special_register(self.pc, self.a.load(machine) - 1)
		machine.indicate_call(return_address)

class RET(IInstruction):
	def __init__(self, source = None) -> None: super().__init__(source=source)
	def compile(self, machine: IMachine) -> None:
		super().compile(machine)
		self.sp = machine.get_special_register_id("SP")
		self.pc = machine.get_special_register_id("PC")
	def execute(self, machine: IMachine) -> None:
		sp = machine.read_special_register(self.sp)
		machine.write_special_register(self.pc, machine.read_memory(sp))
		machine.write_special_register(self.sp, sp + 1)
		machine.indicate_return()

class IN(IInstruction):
	def __init__(self, a: IRegister, b: Port, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine))

class OUT(IInstruction):
	def __init__(self, a: Port, b: IOperand, source = None) -> None: super().__init__(a, b, source=source)
	def execute(self, machine: IMachine) -> None: self.a.store(machine, self.b.load(machine))

class BREAK(IBranchInstruction):
	def __init__(self, source = None) -> None: super().__init__(source=source)
	def execute(self, machine: IMachine) -> None:
		machine.debug()

class HLT(IInstruction):
	def __init__(self, source = None) -> None: super().__init__(source=source)
	def execute(self, machine: IMachine) -> None: machine.halt()

class BITS(IInstruction):
	def __init__(self, a: Immediate, source = None) -> None: super().__init__(a, source=source)
	def compile(self, machine: IMachine) -> None:
		mask: int = 0
		for i in range(self.a.load(machine)): mask = (mask << 1) | 1
		machine.set_bit_mask(mask)

def get_instructions() -> list:
	result = []
	for name, member in inspect.getmembers(sys.modules[__name__], inspect.isclass):
		if issubclass(member, IInstruction) and name == name.upper():
			result.append(member)
	return result