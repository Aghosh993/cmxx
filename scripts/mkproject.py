#!/usr/bin/python

# This is a script to auto-generate C++ templated device support header-only libraries
# utilizing the ARM CMSIS SVD format files from chip vendors as the sole input.
# In theory, this file, coupled with the device datasheet should be all that are required
# in order to develop drivers for a given processor by poking at relevant registers.

# Currently this script also generates the C++ startup code and interrupt base class 
# template from the specification in the SVD file provided. This feature is still potentially 
# a little buggy and a WIP...

# (c) 2017-2018, Abhimanyu Ghosh
# License: BSD

import os
import shutil
import argparse
import collections

from cmsis_svd.parser import SVDParser

class FieldNamespace:
	def __init__(self, fieldObj, addr, reg_access=None):
		self.field_comment = "            /*\r\n                %s\r\n             */\r\n" % (fieldObj.description)
		if reg_access == None:
			self.typedef_decl = "            typedef reg_t<0x%08x, 0x%08x, %d, %s> %s;\r\n" % (addr, pow(2,fieldObj.bit_width) - 1, fieldObj.bit_offset, self.get_policy(fieldObj.access), fieldObj.name)
		else:
			self.typedef_decl = "            typedef reg_t<0x%08x, 0x%08x, %d, %s> %s;\r\n" % (addr, pow(2,fieldObj.bit_width) - 1, fieldObj.bit_offset, self.get_policy(reg_access), fieldObj.name)			

	def get_policy(self, access):
		return {
			"read-write" : "rw_t",
			"read-only" : "ro_t",
			"write-only" : "wo_t",
			None : "noacc_t"
		}.get(access,'err')

	def dump(self, fh):
		fh.write(self.field_comment)
		fh.write(self.typedef_decl)

class RegisterNamespace:
	def __init__(self, regObj, periphBase):
		self.reg_comment = "        /*\r\n            %s\r\n         */\r\n" % (regObj.description)
		self.reset_const = "\r\n            static constexpr uint32_t RESETVALUE = 0x%08x;\r\n" % regObj.reset_value
		if len(regObj.fields) > 0:
			self.ns_opening = "        namespace "+regObj.name+" {\r\n"
			self.ns_close = "        };\r\n"
			self.fields = []
			self.periphBase = periphBase
			if regObj.access != None:
				self.typedef_decl = "            typedef reg_t<0x%08x, 0x%08x, %d, %s> %s;\r\n" % (periphBase+regObj.address_offset, pow(2,regObj.size) - 1, 0, self.get_policy(regObj.access), regObj.name+"_REG")
			else:
				self.typedef_decl = None
			for field in regObj.fields:
				self.fields.append(FieldNamespace(field, self.periphBase+regObj.address_offset, regObj.access))
		else:
			self.fields = None
			self.typedef_decl = "        typedef reg_t<0x%08x, 0x%08x, %d, %s> %s;\r\n" % (periphBase+regObj.address_offset, pow(2,regObj.size) - 1, 0, self.get_policy(regObj.access), regObj.name)
	
	def get_policy(self, access):
		return {
			"read-write" : "rw_t",
			"read-only" : "ro_t",
			"write-only" : "wo_t",
			None : "noacc_t"
		}.get(access,'err')

	def dump(self, fh):
		if self.fields != None:
			fh.write(self.reg_comment)
			fh.write(self.ns_opening)
			fh.write(self.reset_const)
			if self.typedef_decl != None:
				fh.write(self.typedef_decl)
			for field in self.fields:
				field.dump(fh)
			fh.write(self.ns_close)
		else:
			fh.write(self.typedef_decl)


class PeripheralNamespace:
	def __init__(self, periphObj):
		self.periph_comment = "    /*\r\n        %s\r\n     */\r\n" % (periphObj.description)
		self.ns_opening = "    namespace "+periphObj.name+" {\r\n"
		self.ns_close = "    };\r\n"
		self.regs = []
		for register in periphObj.registers:
			self.regs.append(RegisterNamespace(register, periphObj.base_address))

	def dump(self, fh):
		fh.write(self.periph_comment)
		fh.write(self.ns_opening)
		for reg in self.regs:
			reg.dump(fh)
		fh.write(self.ns_close)

class DeviceStartup:
	def __init__(self, devObj, path):
		vects = {}
		templ = open("startup.cpp.template", "r")
		templ_hdr = open("startup.h.template", "r")
		intvects_file = open(os.path.join(os.path.join(path,"src"),devObj.name+"_startup.cpp"), "w+")
		intvects_hdr_file = open(os.path.join(os.path.join(path,"inc"), devObj.name+"_startup.h"), "w+")
		outbuf = templ.readlines()
		hdr_outbuf = templ_hdr.readlines()
		
		for peripheral in devObj.peripherals:
			for interrupt in peripheral.interrupts:
				vects[interrupt.value] = interrupt.name

		vects_sorted=collections.OrderedDict(sorted(vects.items()))
		vectorTable=[]
		lastItem = -1		
		for item in vects_sorted:
			if lastItem != item-1:
				while lastItem < item-1:
					vectorTable.append('NULL')
					lastItem += 1
			vectorTable.append(vects_sorted[item])
			lastItem = item

		for hdr_line in hdr_outbuf:
			if "#define PERIPHERAL_IRQS nExceptions" in hdr_line:
				intvects_hdr_file.write(hdr_line.replace("nExceptions", str(len(vectorTable))))
			else:
				if "// DEVICE Exceptions: //" in hdr_line:
					intvects_hdr_file.write("\r\n	// %s Exceptions: //\r\n" % devObj.name)
					for i in range(len(vectorTable)):
						if vectorTable[i] != 'NULL':
							intvects_hdr_file.write("    static void "+vectorTable[i]+"_handler(void);\r\n")							
				else:
					intvects_hdr_file.write(hdr_line)


		for line in outbuf:
			if "#include <DEVICE_startup.h>" in line:
				intvects_file.write(line.replace("DEVICE", devObj.name, 1))
			else:
				if "IRQ* IRQ::irqRegistrationTable[PERIPHERAL_IRQS] = {" in line:
					intvects_file.write(line)
					for j in range(len(vectorTable)):
						intvects_file.write("	&defaultRegistration")
						if j < len(vectorTable)-1:
							intvects_file.write(",\r\n")
						else:
							intvects_file.write("\r\n")
				else:
					if "// DEVICE Exceptions: //" in line:
						intvects_file.write(line.replace("DEVICE", devObj.name))
						for vector in range(len(vectorTable)):
							if vectorTable[vector] != 'NULL':
								intvects_file.write("void IRQ::%s_handler(void)\r\n{\r\n    irqRegistrationTable[%d]->ISR();\r\n}\r\n\r\n" % (vectorTable[vector], vector))
					else:
						if "// Jump addresses for DEVICE interrupts: //" in line:
							intvects_file.write(line.replace("DEVICE", devObj.name))
							for vector in range(len(vectorTable)):
								if vectorTable[vector] != 'NULL':
									intvects_file.write("    IRQ::"+vectorTable[vector]+"_handler")
								else:
									intvects_file.write("    0")
								if vector < len(vectorTable)-1:
									intvects_file.write(",\r\n")
								else:
									intvects_file.write("\r\n")
						else:
							intvects_file.write(line)

		intvects_hdr_file.close()
		intvects_file.close()
		templ.close()

def getProjName(path):
	pathSplit = os.path.split(path)
	return pathSplit[len(pathSplit)-1]

def subst_target(srcfile, dstfile, nameToSub):
	f = open(srcfile, "r")
	f2 = open(dstfile, "w+")
	data = f.read()
	f2.write(data.replace("proj_target", nameToSub))
	f.close()
	f2.close()

def main():
	parser = argparse.ArgumentParser(description = 'Generate C++ project from CMSIS SVD XML file')
	parser.add_argument('input', metavar='inputsvd', nargs=1, help='Input SVD file to generate BSP from')
	parser.add_argument('project', metavar='project', nargs=1, help='Path to output project')
	args = parser.parse_args()

	if args.input:
		file = args.input[0]

	if args.project:
		if os.path.exists(args.project[0]):
			print("Path exists, exiting!")
			exit(-1)
		else:
			os.mkdir(args.project[0])
			os.mkdir(os.path.join(args.project[0], "inc"))
			os.mkdir(os.path.join(args.project[0], "src"))

	name = getProjName(args.project[0])

	parser = SVDParser.for_xml_file(file)
	dev = parser.get_device()
	outfile = dev.name+".h"

	f=open(os.path.join(args.project[0], "inc", outfile), "w+")
	f.write("#pragma once\r\n")
	f.write("#include <stdint.h>\r\n")
	f.write("#include <reg.h>\r\n")
	f.write("\r\nnamespace %s {\r\n" % dev.name)

	DeviceStartup(dev, args.project[0])

	for peripheral in dev.peripherals:
		p = PeripheralNamespace(peripheral)
		p.dump(f)
	f.write("};\r\n")
	f.close()
	shutil.copyfile("reg.h.template", os.path.join(os.path.join(args.project[0], "inc"),'reg.h'))
	shutil.copyfile("load_target.sh.template", os.path.join(args.project[0],'load_target.sh'))
	shutil.copyfile("target.cfg.template", os.path.join(args.project[0],'target.cfg'))
	shutil.copyfile("linker.template", os.path.join(args.project[0],'linker.ld'))
	# shutil.copyfile("runme.gdb.template", os.path.join(args.project[0],'runme.gdb'))
	# shutil.copyfile("Makefile.template", os.path.join(args.project[0],'Makefile'))
	subst_target('runme.gdb.template', os.path.join(args.project[0],'runme.gdb'), getProjName(args.project[0]))
	subst_target('Makefile.template', os.path.join(args.project[0],'Makefile'), getProjName(args.project[0]))

	targetMain = open(os.path.join(args.project[0],getProjName(args.project[0])+".cpp"), "w+")
	targetMain.write("int main(void)\r\n{\r\n    while(1);\r\n}\r\n");
	targetMain.close()
	
if __name__ == '__main__':
	main()