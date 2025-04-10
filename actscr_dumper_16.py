# HAL Action Script dumper for 16-bit (Super Famicon) games.

# This file depends on an extra data file that needs to have the attributes specified in `required_attributes` below.

# Basic Python code, nothing too fancy.



# ------------------------ Imports, constants and global variables ------------------------ #



import os
import sys
import argparse
import importlib.util
import time

# Constants.
BANK_C0_OFFSET = 0xC00000
ADDR_WRAPPER = ('/* ', ' */')
COMMENT_WRAPPER = ('// ', '')
DEF_LABEL_START = 'M_'
WAITED_OPCODES_APPEND = '_w'
EXTRA_SPACING = 3
STR_BYTE = 'byte'
STR_SHORT = 'short'
STR_ADR24 = 'adr24'
STR_ADR32 = 'adr32'

# Globals.
lines = []                    # List that gets populated with the lines that will be written to the output file.
labels = []                   # List that gets populated with addresses requiring labels.

# List of required attributes in the data module and their expected types.
required_attributes = {
	"rom_info": dict,
	"RANGES": (tuple, list),
	"MAX_VAR": int,
	"MAX_OPR": int,
	"operation_list": (tuple, list),
	"opcodes_list": (tuple, list),
	"waited_opcodes": (tuple, list),
	"asm_routine_list": (tuple, list),
	"label_list": (tuple, list)
}



# ---------------------------------- Auxiliar functions ----------------------------------- #



# Turns an unsigned byte into a signed byte.
def u_to_s_8(val):
	if val > 127:
		return val-256
	return val

# Turns an unsigned 16-bit word into a signed 16-bit word.
def u_to_s_16(val):
	if val > 32767:
		return val-65536
	return val

# Checks if a certain address is outside the specified ranges to read.
def out_of_range(addr):
	for start, end in RANGES:
		if start < addr < end:
			return False
	return True

# Error handler.
def raise_error(code, data_1=None, data_2=None):
	match code:
		case 0:
			msg = f"The data file is missing one of the required attributes ({data_1})."
		case 1:
			msg = f"One of the required attributes ({data_1}) in the data file is of the wrong type."
		case 2:
			msg = f"The ROM does not seem to be a valid {data_1} ROM."
		case 3:
			msg = f"Trying to read an invalid opcode {data_1} at {data_2}."
		case 4:
			msg = f"Trying to operate an object var higher than {MAX_VAR} at {data_1}."
		case 5:
			msg = f"Trying to use an invalid operation ({data_1} when max is {MAX_OPR}) at {data_2}."
		case 6:
			msg = f"Trying to use a multi-argument operation of size 0 at {data_1}."
		case 7:
			msg = f"Trying to read an invalid argument type ({data_1})."
		case _:
			msg = "An unknown exception ocurred."
	
	print(f"ERROR: " + msg)
	sys.exit()
	
	return   # Shouldn't be reached.



# ------------------------------------ Main functions ------------------------------------- #



# Reads the first byte in 'addr' to determine the opcode, and then the subsequent arguments, if any.
# Returns a dict with the data read.
def read_from_rom(addr):
	data = {}   # Dict that will be returned.
	returned_args = []
	
	rom.seek(addr)
	initial_cursor = rom.tell()
	
	opcode = rom.read(1)[0]
	
	# Check for waited opcodes.
	for waited_opcode in data_module.waited_opcodes:
		if waited_opcode["range"] < opcode < waited_opcode["range"] + 0x0F:
			data["wait"] = opcode - waited_opcode["range"]
			opcode = waited_opcode["opcode"]
			break
	
	# Raise an error if the opcode is invalid.
	if opcode >= len(data_module.opcodes_list):
		raise_error(3, f"0x{opcode:X}", f"{addr + BANK_C0_OFFSET:X}")
	
	data["opcode"] = opcode
	
	# If there are no arguments, return early with an effective read length of 1.
	if data_module.opcodes_list[opcode].get("args") == None:
		data["read"] = 1
		return data
	
	args = data_module.opcodes_list[opcode]["args"]
	
	# Check for 'asm_arg'.
	if 'asm_arg' in args:
		asmcall = {}
		asmcall["address"] = int.from_bytes(rom.read(3), "little")
		for routine in data_module.asm_routine_list:
			if routine["address"] == asmcall["address"]:
				if routine.get("name") != None:
					asmcall["name"] = routine["name"]
				if routine.get("comment") != None:
					asmcall["comment"] = routine["comment"]
				if routine.get("args"):
					asmcall["args"] = []
					if routine["args"][0] == 'multi':
						asmcall["args"].append(read_arg('u_8'))
						for value in range(0, int(asmcall["args"][0][1]), 1):
							asmcall["args"].append(read_arg(routine["args"][1]))
					else:
						for arg in routine["args"]:
							asmcall["args"].append(read_arg(arg))
				break
		data["asmcall"] = asmcall
	
	# Check for 'multi'.
	elif args[0] == 'multi':
		data["multi"] = read_arg('u_8')
		for value in range(0, int(data["multi"][1]), 1):
			returned_args.append(read_arg(args[1]))
	
	# Constant size opcode.
	else:
		for arg in args:
			returned_arg = read_arg(arg)
			if returned_arg[0] == 'var':
				data["var"] = returned_arg[1]
			elif returned_arg[0] == 'opr':
				data["opr"] = returned_arg[1]
			else:
				returned_args.append(returned_arg)
	
	# Get the effective length of the data read.
	data["read"] = rom.tell() - initial_cursor
	
	if returned_args:
		data["args"] = returned_args
	
	return data

# Reads an argument.
# Returns a tuple (type, value).
def read_arg(arg):
	match arg:
		case 'u_8' | 'var' | 'opr':
			value = f'{rom.read(1)[0]}'
		case 'u_16':
			value = f'{int.from_bytes(rom.read(2), "little")}'
		case 'hex_8':
			value = f'0x{rom.read(1)[0]:02X}'
		case 'hex_16':
			value = f'0x{int.from_bytes(rom.read(2), "little"):04X}'
		case 'hex_24':
			value = f'0x{int.from_bytes(rom.read(3), "little"):04X}'
		case 'hex_32':
			high_short = int.from_bytes(rom.read(2), "little")
			low_short = int.from_bytes(rom.read(2), "little")
			value = f'0x{0x10000 * high_short + low_short:X}'
		case 's_8':
			value = f'{u_to_s_8(rom.read(1)[0])}'
		case 's_16':
			value = f'{u_to_s_16(int.from_bytes(rom.read(2), "little"))}'
		case 'l_16':
			short_addr = int.from_bytes(rom.read(2), "little")
			long_addr = BANK_C0_OFFSET + ((addr - header) & 0xFF0000) + short_addr
			
			if out_of_range(long_addr - BANK_C0_OFFSET):
				value = f'0x{short_addr:04X}'
			else:
				for entry in data_module.label_list:
					if entry["address"] == long_addr:
						value = entry["label"][-1]
						break
				else:
					value = f'{DEF_LABEL_START}{long_addr:X}'
					labels.append(long_addr)
		case 'l_24':
			long_addr = int.from_bytes(rom.read(3), "little")
			
			if out_of_range(long_addr - BANK_C0_OFFSET):
				value = f'0x{long_addr:X}'
			else:
				for entry in data_module.label_list:
					if entry["address"] == long_addr:
						value = entry["label"][-1]
						break
				else:
					value = f'{DEF_LABEL_START}{long_addr:X}'
					labels.append(long_addr)
		case _:
			raise_error(7, arg)
	
	if arg.endswith('_8'):
		type = STR_BYTE
	elif arg.endswith('_16'):
		type = STR_SHORT
	elif arg.endswith('_24'):
		type = STR_ADR24
	elif arg.endswith('_32'):
		type = STR_ADR32
	elif arg == 'var' or arg == 'opr':
		type = arg
	else:
		raise_error(7, arg)   # This shouldn't be reached as it's already covered in the previous block.
	
	return (type, value)

# Writes a normal action script code line.
# Returns said line.
def write_line(addr, data):
	line_to_write = ""
	
	opcode = data["opcode"]
	name = data_module.opcodes_list[opcode]["name"]
	newline = ""
	
	if data_module.opcodes_list[opcode].get("newline") != None:
		newline = data_module.opcodes_list[opcode]["newline"]
	
	if newline == 'before' and not lines[-1].endswith('\n\n'):
		line_to_write += "\n"
	
	line_to_write += f"{ADDR_WRAPPER[0]}{addr:X}{ADDR_WRAPPER[1]}{EXTRA_SPACING * ' '}"
	
	if data.get("asmcall") != None:
		if data["asmcall"].get("name") != None:
			line_to_write += data["asmcall"]["name"]
			
			if data.get("wait") != None:
				line_to_write += f"{WAITED_OPCODES_APPEND}{data["wait"]}"
			
			if data["asmcall"].get("args"):
				line_to_write += "("
				
				for arg_index in range(0, len(data["asmcall"]["args"]), 1):
					line_to_write += data["asmcall"]["args"][arg_index][1]
					if arg_index < len(data["asmcall"]["args"]) - 1:
						line_to_write += ", "
				
				line_to_write += ")"
			
			if data["asmcall"].get("comment"):
				line_to_write += f"   {COMMENT_WRAPPER[0]}{data["asmcall"]["comment"]}{COMMENT_WRAPPER[1]}"
		else:
			line_to_write += f"{name}"
			
			if data.get("wait") != None:
				line_to_write += f"{WAITED_OPCODES_APPEND}{data["wait"]}"
				
			line_to_write += f"(0x{data["asmcall"]["address"]:X})"
			
			if data["asmcall"].get("comment"):
				line_to_write += f"   {COMMENT_WRAPPER[0]}{data["asmcall"]["comment"]}{COMMENT_WRAPPER[1]}"
			
			if data["asmcall"].get("args"):
				for arg_index in range(0, len(data["asmcall"]["args"]), 1):
					line_to_write += f"\n{(len(ADDR_WRAPPER[0]) + 6 + (len(ADDR_WRAPPER[1]) + EXTRA_SPACING)) * ' '}"
					line_to_write += f"{data["asmcall"]["args"][arg_index][0]} {data["asmcall"]["args"][arg_index][1]}"
	else:
		line_to_write += name
		
		if data.get("opr"):
			line_to_write += f"{operation_list[int(data["opr"])]}"
			
		if data_module.opcodes_list[opcode].get("terminator") != None:
			line_to_write += data_module.opcodes_list[opcode]["terminator"]
			
		if data.get("var"):
			line_to_write += f"{data["var"]}"
			
		if data.get("wait") != None:
			line_to_write += f"{WAITED_OPCODES_APPEND}{data["wait"]}"
		
		if data.get("args") != None:
			if data.get("multi") != None:
				line_to_write += f"({data["multi"][1]})"
				for arg in data["args"]:
					line_to_write += f"\n{(len(ADDR_WRAPPER[0]) + 6 + (len(ADDR_WRAPPER[1]) + EXTRA_SPACING)) * ' '}{arg[0]} {arg[1]}"
				line_to_write += "\n"
				return line_to_write
			
			line_to_write += "("
			
			for arg_index in range(0, len(data["args"]), 1):
				line_to_write += data["args"][arg_index][1]
				if arg_index < len(data["args"]) - 1:
					line_to_write += ", "
			
			line_to_write += ")"
			
	
	if newline == 'after':
		line_to_write += "\n"
	
	line_to_write += "\n"
	
	return line_to_write

# Adds requested labels from 'labels' to 'lines'.
# Returns nothing.
def add_labels():
	label_index = 0
	
	# Iterate the lines list excluding the first and last elements.
	for line_index, line in enumerate(lines[1:-1], 1):
		line_to_insert = ""
		address_from_line = 0
		
		# We assume that SNES addresses are 6 chars longs.
		if line.startswith(f"\n{ADDR_WRAPPER[0]}"):
			address_from_line = int(line[len(ADDR_WRAPPER[0]) + 1:len(ADDR_WRAPPER[0]) + 7], 16)
		elif line.startswith(f"{ADDR_WRAPPER[0]}"):
			address_from_line = int(line[len(ADDR_WRAPPER[0]):len(ADDR_WRAPPER[0]) + 6], 16)
		
		if labels[label_index] == address_from_line:
			if not lines[line_index - 1].endswith('\n\n'):
				line_to_insert += "\n"
			
			for label in data_module.label_list:
				if label["address"] == address_from_line:
					if label.get("comment") != None:
						for comment in label["comment"]:
							line_to_insert += f"{COMMENT_WRAPPER[0]}{comment}{COMMENT_WRAPPER[1]}\n"
					
					# We assume that there is at least one label.
					for named_label in label["label"]:
						line_to_insert += f"{named_label}:"
						if not line.startswith('\n'):
							line_to_insert += "\n"
					break
			
			# By this point, if 'line_to_insert' is empty, it means a named label wasn't inserted, insert a default one.
			if line_to_insert == "" or line_to_insert == "\n":
				line_to_insert += f"{DEF_LABEL_START}{address_from_line:X}:"
				if not line.startswith('\n'):
					line_to_insert += "\n"
			
			# Advance the sorted 'labels' list.
			if label_index < len(labels)-1:
				label_index += 1
		
		elif labels[label_index] < address_from_line:
			if label_index < len(labels)-1:
				while labels[label_index] < address_from_line:
					print(f"WARNING: The label at 0x{labels[label_index]:X} could not be inserted.")
					label_index += 1
		
		lines[line_index] = line_to_insert + line
	
	return



# ------------------------------------- Main program -------------------------------------- #



if __name__ == '__main__':
	# Parse three arguments: the ROM, the output file and the data file.
	parser = argparse.ArgumentParser()
	
	parser.add_argument('rom', help = "The input ROM file to extract data from")
	parser.add_argument('output', help = "The output file that will be created")
	parser.add_argument('data', help = "The Python file containing the ROM info and misc data")
	
	py_args = parser.parse_args()
	
	# Import the data file as a module.
	data_file_name = os.path.splitext(os.path.basename(py_args.data))[0]
	spec = importlib.util.spec_from_file_location(data_file_name, py_args.data)
	
	data_module = importlib.util.module_from_spec(spec)
	
	spec.loader.exec_module(data_module)
	
	# Check integrity of data file.
	for attribute, expected_type in required_attributes.items():
		if not hasattr(data_module, attribute):
			raise_error(0, attribute)
		attr_value = getattr(data_module, attribute)
		
		if not isinstance(attr_value, expected_type):
			raise_error(1, attribute)
	
	# Copy some variables from the data module.
	rom_info = data_module.rom_info
	RANGES = data_module.RANGES
	MAX_VAR = data_module.MAX_VAR
	MAX_OPR = data_module.MAX_OPR
	operation_list = data_module.operation_list
	
	# Open ROM.
	with open(py_args.rom, "rb") as rom:
		header = 0x0
		
		rom_offset = rom_info["offset"]
		
		rom.seek(rom_offset)
		
		# Validate ROM.
		for byte in rom_info["data"]:
			if rom.read(1)[0] != byte:
				header = 0x200
				rom.seek(rom_offset + header)
				for byte in rom_info["data"]:
					if rom.read(1)[0] != byte:
						raise_error(2, rom_info["name"])
		
		print(f"Extracting Action Script data from {rom_info["name"]}!\n")
		
		start_time = time.time()
		
		lines.append(f"// Action Script dump for {rom_info["name"]}\n")
		
		for start, end in RANGES:
			print(f"Extracting range (0x{start:06X}, 0x{end:06X})")
			
			lines.append(f"\n// RANGE (0x{start + BANK_C0_OFFSET:X}, 0x{end + BANK_C0_OFFSET:X})\n")
			
			labels.append(start + BANK_C0_OFFSET)
			
			addr = start + header
			while addr < end + header:
				data = read_from_rom(addr)
				lines.append(write_line(addr + BANK_C0_OFFSET - header, data))
				addr += data["read"]
				
				if data_module.opcodes_list[data["opcode"]].get("newline") != None:
					if data_module.opcodes_list[data["opcode"]]["newline"] == 'label':
						if not out_of_range(addr - header):
							labels.append(addr + BANK_C0_OFFSET - header)
	
	print("\nAdding labels...")
	
	# Append label addresses from our named label list.
	labels.extend(label["address"] for label in data_module.label_list)
	
	# Remove repeated elements and sort list.
	labels = list(set(labels))
	labels.sort()
	
	add_labels()
	
	print(f"\nWriting to output file...")
	
	with open(py_args.output, "w") as out:
		for line in lines:
			out.write(line)
	
	print(f"\nFinished extraction in {time.time()-start_time:.4f} seconds!")