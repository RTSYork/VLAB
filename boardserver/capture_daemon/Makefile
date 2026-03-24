# Makefile for capture_daemon — bare-metal Core 1 framebuffer capture
#
# Requires: arm-none-eabi-gcc (from Vivado/Vitis SDK or standalone toolchain)
#
# Build:   make
# Clean:   make clean

CROSS_COMPILE ?= arm-none-eabi-

CC      = $(CROSS_COMPILE)gcc
AS      = $(CROSS_COMPILE)gcc
LD      = $(CROSS_COMPILE)gcc
OBJCOPY = $(CROSS_COMPILE)objcopy
SIZE    = $(CROSS_COMPILE)size

TARGET  = capture_daemon

CFLAGS  = -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard \
          -O2 -Wall -Wextra \
          -ffreestanding -nostdlib \
          -ffunction-sections -fdata-sections \
          -mno-unaligned-access \
          -idirafter compat

ASFLAGS = -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard

LDFLAGS = -T link.ld -nostdlib -nostartfiles \
          -Wl,--gc-sections \
          -lgcc

OBJS    = startup.o main.o

.PHONY: all clean

all: $(TARGET).elf $(TARGET).bin
	@$(SIZE) $(TARGET).elf

$(TARGET).elf: $(OBJS) link.ld
	$(LD) $(CFLAGS) $(OBJS) -o $@ $(LDFLAGS)

$(TARGET).bin: $(TARGET).elf
	$(OBJCOPY) -O binary $< $@

startup.o: startup.s
	$(AS) $(ASFLAGS) -c $< -o $@

main.o: main.c stb_image_write.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET).elf $(TARGET).bin
