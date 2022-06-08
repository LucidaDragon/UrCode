from multiprocessing import Process, Queue
from typing import Any, Union
import os
from plugins.urcl.emulator import IDebugger, IPort, RandomPort, URCLEmulator
from plugins.urcl.parser import parse_source
from editor.base import ui, get_icon_font, load_icon

STREAM_COMMANDS = "commands"
STREAM_REPORTS = "reports"
IO = "io"
DEBUG_OPEN = "open"
DEBUG_CONTINUE = "continue"
DEBUG_BREAKPOINT_SET = "break"
DEBUG_BREAKPOINT_REMOVE = "unbreak"
DEBUG_STEP_INTO = "step"
DEBUG_STEP_OVER = "over"
DEBUG_STEP_OUT = "out"
DEBUG_QUERY_MEMORY = "memory"
DEBUG_CLOSE = "close"
FIELD_LINE = "line"
FIELD_REGISTERS = "registers"
FIELD_STACK = "stack"
FIELD_CALLS = "call_stack"
FIELD_HOTPATH = "hotpaths"

def _on_run(machine: URCLEmulator, on_start: Queue) -> None:
	on_start.put(None)
	try: machine.execute()
	except: ui.console.write("\nAn internal error occurred in the debugger.\n")

def _on_break(debug: IDebugger, data: dict) -> None:
	commands: Queue = data[STREAM_COMMANDS]
	reports: Queue = data[STREAM_REPORTS]
	reports.put(DEBUG_OPEN)
	reports.put({ FIELD_LINE: debug.get_line(), FIELD_REGISTERS: debug.get_registers(), FIELD_STACK: debug.get_stack(), FIELD_CALLS: debug.get_call_stack(), FIELD_HOTPATH: debug.get_hotpaths() })
	command = commands.get()
	while command == DEBUG_QUERY_MEMORY or command == DEBUG_BREAKPOINT_SET or command == DEBUG_BREAKPOINT_REMOVE:
		if command == DEBUG_QUERY_MEMORY:
			reports.put(debug.read_memory(commands.get()))
			command = commands.get()
		elif command == DEBUG_BREAKPOINT_SET:
			debug.set_breakpoint(commands.get())
		elif command == DEBUG_BREAKPOINT_REMOVE:
			debug.remove_breakpoint(commands.get())
	if command == DEBUG_STEP_INTO: debug.step_into()
	elif command == DEBUG_STEP_OVER: debug.step_over()
	elif command == DEBUG_STEP_OUT: debug.step_out()
	elif command == DEBUG_CONTINUE: debug.resume()
	reports.put(DEBUG_CLOSE)

class Debugger:
	def __init__(self, machine: URCLEmulator) -> None:
		self.machine = machine
		self.pending_additions: list[int] = []
		self.pending_deletions: list[int] = []
		self.commands = Queue()
		self.reports = Queue()
		self.on_start = Queue()
		self.process = Process(target=_on_run, daemon=True, args=[machine, self.on_start])
		streams = { STREAM_COMMANDS: self.commands, STREAM_REPORTS: self.reports }
		self.machine.set_break_callback(_on_break, streams)
		self.machine.set_port_data(streams)
		self.checker = ui.bind_busy_wait(lambda: True, self.check)
		self.checking = False
		self.debugging = False
		self.hotpaths: dict[str, dict[int, float]] = {}
		self.last_line: int = 0
	
	def add_breakpoint(self, line: int) -> None:
		if line in self.pending_deletions: self.pending_deletions.remove(line)
		else: self.pending_additions.append(line)
	
	def remove_breakpoint(self, line: int) -> None:
		if line in self.pending_additions: self.pending_additions.remove(line)
		else: self.pending_deletions.append(line)
	
	def read_memory(self, address: int) -> int:
		result: int = 0
		if self.debugging:
			self.commands.put(DEBUG_QUERY_MEMORY)
			self.commands.put(address)
			try: result = self.reports.get(timeout=1)
			except: pass
		return result
	
	def send_console(self, text: str) -> None:
		self.commands.put(IO)
		self.commands.put(text)
	
	def resume(self) -> None:
		if self.debugging: self.commands.put(DEBUG_CONTINUE)

	def step(self) -> None:
		if self.debugging: self.commands.put(DEBUG_STEP_INTO)
	
	def step_over(self) -> None:
		if self.debugging: self.commands.put(DEBUG_STEP_OVER)
	
	def step_out(self) -> None:
		if self.debugging: self.commands.put(DEBUG_STEP_OUT)

	def start(self) -> None:
		self.process.start()
		try: self.on_start.get(timeout=10)
		except: pass

	def terminate(self) -> None:
		self.process.terminate()
		ui.unbind_busy_wait(self.checker)
		self.checker = -1

	def check(self) -> None:
		if self.checking: return
		self.checking = True
		if not self.process.is_alive():
			stop()
			return
		try:
			while True:
				if self.debugging:
					while (len(self.pending_additions) + len(self.pending_deletions)) > 0:
						if len(self.pending_additions) > 0:
							line = self.pending_additions[0]
							self.commands.put(DEBUG_BREAKPOINT_SET)
							self.commands.put(line)
							self.pending_additions.pop(0)
						if len(self.pending_deletions) > 0:
							line = self.pending_deletions[0]
							self.commands.put(DEBUG_BREAKPOINT_REMOVE)
							self.commands.put(line)
							self.pending_deletions.pop(0)
				report = self.reports.get(block=False)
				if report == DEBUG_OPEN:
					status: dict[str, Any] = self.reports.get(timeout=1)
					self.last_line = int(status.get(FIELD_LINE, 0))
					self.hotpaths = status.get(FIELD_HOTPATH, {})
					variables = status.get(FIELD_REGISTERS, {})
					stack = status.get(FIELD_STACK, [])
					calls = status.get(FIELD_CALLS, [])
					format_hex = lambda value: f"0x{hex(value).lstrip('0x').upper().rjust(int(self.machine.integer_bits / 4), '0')}"
					self.debugging = True
					set_state_debug()
					ui.text_editor.set_location(self.last_line)
					ui.variables_tab.set_variables(variables, int_format=lambda value: (format_hex(value), "number"))
					ui.stack_tab.set_stack(stack, address_format=format_hex, value_format=format_hex)
					ui.calls_tab.set_calls(calls, address_format=format_hex)
					ui.memory_tab.set_address_format(format_hex)
					ui.memory_tab.set_value_format(format_hex)
					ui.memory_tab.refresh_memory()
					ui.performance_tab.set_show_callback(lambda name: ui.text_editor.set_hotpath(self.hotpaths[name]))
					ui.performance_tab.set_functions(self.hotpaths.keys())
				elif report == DEBUG_CLOSE:
					self.debugging = False
					ui.text_editor.clear_location()
					ui.variables_tab.clear_variables()
					ui.stack_tab.clear_stack()
					ui.calls_tab.clear_calls()
					set_state_running()
				elif report == IO:
					ui.console.write(self.reports.get(timeout=1))
		except: pass
		self.checking = False

class DebuggerTextPort(IPort):
	def __init__(self) -> None:
		self.buffer = []

	def read(self, machine: URCLEmulator) -> int:
		data = machine.get_port_data()
		commands: Queue = data[STREAM_COMMANDS]

		while len(self.buffer) == 0:
			op: str = ""
			while op != IO:
				op = commands.get()
				if op == IO:
					for c in commands.get():
						try: self.buffer.append(ord(c))
						except: self.buffer.append(0)
		
		return self.buffer.pop(0)
	
	def write(self, machine: URCLEmulator, value: int) -> None:
		data = machine.get_port_data()
		reports: Queue = data[STREAM_REPORTS]
		reports.put(IO)
		reports.put(chr(value))

breakpoints: "list[int]" = []
debugger: Union[Debugger, None] = None
run_action: int = -1
stop_action: int = -1
continue_action: int = -1
step_action: int = -1
step_over_action: int = -1
step_out_action: int = -1

def compile_emulator(source: str) -> Union[URCLEmulator, None]:
	ui.console.clear()

	parsed = parse_source(source)
	for line, warning in parsed.warnings:
		ui.text_editor.warning(line)
		ui.console.write(f"Warning (ln {line}): {warning}\n")
	if len(parsed.errors) > 0:
		for line, error in parsed.errors:
			ui.text_editor.error(line)
			ui.console.write(f"Error (ln {line}): {error}\n")
		return None

	result = URCLEmulator()
	result.add_port("TEXT", DebuggerTextPort())
	result.add_port("RAND", RandomPort())
	result.load_program_rom(parsed.program)
	for name in parsed.labels: result.add_label(parsed.labels[name], name)
	return result

def on_console_send() -> None:
	if debugger != None: debugger.send_console(ui.console.read())

def on_breakpoint_added(line: int) -> None:
	if not line in breakpoints: breakpoints.append(line)
	if debugger != None: debugger.add_breakpoint(line)

def on_breakpoint_removed(line: int) -> None:
	while line in breakpoints: breakpoints.remove(line)
	if debugger != None: debugger.remove_breakpoint(line)

def run() -> None:
	global debugger
	machine = compile_emulator(ui.text_editor.get_text())
	if machine == None: return
	for breakpoint in breakpoints: machine.set_breakpoint(breakpoint)
	if debugger != None: debugger.terminate()
	debugger = Debugger(machine)
	set_state_running()
	debugger.start()

def stop() -> None:
	global debugger
	if debugger != None: debugger.terminate()
	debugger = None
	set_state_editing()

def lint() -> None:
	compile_emulator(ui.text_editor.get_text())

def set_state_editing() -> None:
	ui.action_bar.enable_action(run_action)
	ui.action_bar.disable_action(stop_action)
	ui.action_bar.disable_action(continue_action)
	ui.action_bar.disable_action(step_action)
	ui.action_bar.disable_action(step_over_action)
	ui.action_bar.disable_action(step_out_action)
	ui.memory_tab.clear_memory()
	ui.text_editor.highlight()

def set_state_running() -> None:
	ui.action_bar.disable_action(run_action)
	ui.action_bar.enable_action(stop_action)
	ui.action_bar.disable_action(continue_action)
	ui.action_bar.disable_action(step_action)
	ui.action_bar.disable_action(step_over_action)
	ui.action_bar.disable_action(step_out_action)
	ui.text_editor.highlight()

def set_state_debug() -> None:
	ui.action_bar.disable_action(run_action)
	ui.action_bar.enable_action(stop_action)
	ui.action_bar.enable_action(continue_action)
	ui.action_bar.enable_action(step_action)
	ui.action_bar.enable_action(step_over_action)
	ui.action_bar.enable_action(step_out_action)

if os.name == "nt":
	ui.window.iconbitmap(os.path.abspath(os.path.join(os.path.dirname(__file__), "./urcl.ico")))
ui.text_editor.add_object_type("keyword", r"[A-Za-z]+")
ui.text_editor.add_object_type("function", r"\.[\w\d]+")
ui.text_editor.add_object_type("number", r"\-?\d+")
ui.text_editor.add_object_type("number", r"0x[\dA-Fa-f]+")
ui.text_editor.add_object_type("number", r"0o[0-7]+")
ui.text_editor.add_object_type("number", r"0b[01]+")
ui.text_editor.add_object_type("string", r"'([^']|(\\'))+'")
ui.text_editor.add_object_type("variable", r"R\d+")
ui.text_editor.add_object_type("variable", r"$\d+")
ui.text_editor.add_object_type("type", r"%[\w\d]+")
ui.text_editor.add_object_type("macro", r"@[\w\d]+")
ui.text_editor.highlight_event.bind(lint)
ui.breakpoint_added_bind.bind(on_breakpoint_added)
ui.breakpoint_removed_bind.bind(on_breakpoint_removed)
ui.memory_tab.set_request_callback(lambda address: 0 if debugger == None else debugger.read_memory(address))
run_action = ui.action_bar.add_action(load_icon("\uEB91", "Debug"), run, color="#89D185", font=get_icon_font())
stop_action = ui.action_bar.add_action(load_icon("\uEAD7", "Stop"), stop, color="#F48771", font=get_icon_font())
continue_action = ui.action_bar.add_action(load_icon("\uEACF", "Resume"), lambda: debugger.resume() if debugger != None else None, color="#75BEFF", font=get_icon_font())
step_over_action = ui.action_bar.add_action(load_icon("\uEAD6", "Step Over"), lambda: debugger.step_over() if debugger != None else None, color="#75BEFF", font=get_icon_font())
step_action = ui.action_bar.add_action(load_icon("\uEAD4", "Step Into"), lambda: debugger.step() if debugger != None else None, color="#75BEFF", font=get_icon_font())
step_out_action = ui.action_bar.add_action(load_icon("\uEAD5", "Step Out"), lambda: debugger.step_out() if debugger != None else None, color="#75BEFF", font=get_icon_font())
set_state_editing()