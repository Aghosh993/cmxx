#!/bin/bash
openocd -f ./target.cfg &
sleep 2
arm-none-eabi-gdb --batch --command=runme.gdb 
echo "Killing OpenOCD..."
pkill openocd
echo "Done."