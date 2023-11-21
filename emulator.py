import pygame
import random
import threading

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

class Memory:
    def __init__(self) -> None:
        self.memory = bytearray(0x1000) # ram. Only 4096 bytes or 0x1000 in hex. 
                                        # Data should start on byte 0x200 since normally, the chip8 interpreter is loaded there

    def write_bytes_at(self, array, position, size = 0):
        if(size == 0):
            size = len(array)
        self.memory[position:position + size] = array

    def read_bytes_at(self, position, size = 1):
        return self.memory[position:position+size]

    def read_opcode_at(self, position) -> (int, int, int, int):
        # Read 2 bytes from memory at position of PC, as 4 half bit/nibble (4 bit)
        # Return the 4 nibble
        two_bytes = self.memory[position:position+2]

        # Bit operation shits to extract the nibble from the byte. I dont want to learn how to do it so i used chatgpt
        nibble1 = (two_bytes[0] & 0xF0) >> 4
        nibble2 = two_bytes[0] & 0x0F
        nibble3 = (two_bytes[1] & 0xF0) >> 4
        nibble4 = two_bytes[1] & 0x0F

        return (hex(nibble1), hex(nibble2), hex(nibble3), hex(nibble4))

class Emulator:
    def __init__(self, rom_name) -> None:
        self.rom = rom_name
        self.stack = [] # Represents the stack.
        self.memory = Memory() # Make a new memory

        self.delay_timer = 60 # Count down at 60 hertz (ie. 60 times per second) until it reach 0
        self.sound_timer = 0 # When value is not zero, bleep

        self.resolution = (64, 32) # Display is 64x32 running at 60hz ie. 60 fps.
        self.display_buffer = [[0 for _ in range(64)] for _ in range(32)] # Array of 0 and 1 representing pixels. self.display_buffer[y][x]
        # Registers
        self.V0 = self.V1 = self.V2 = self.V3 = self.V4 = \
        self.V5 = self.V6 = self.V7 = self.V8 = self.V9 = \
        self.VA = self.VB = self.VC = self.VD = self.VE = \
        self.VF = self.I = self.PC = 1 #registers V0 - VF, Index register, and program counter

        pygame.init()
        self.scale_factor = 10 # The factor by which to scale the window
        self.window_size = (self.resolution[0] * self.scale_factor, self.resolution[1] * self.scale_factor) # Scaled window size
        self.screen = pygame.display.set_mode(self.window_size) # Window size is now scaled
        self.virtual_screen = pygame.Surface(self.resolution) # Virtual screen at original resolution
        self.clock = pygame.time.Clock()

        self.setup()

    def setup(self):
        # Bytes representing font. Each bits of these represents a pixel that is on/off in the screen.
        # These are part of the interpreter so it is loaded on the first 0x200 bytes. Common convention is to put it in 050 - 09F
        fonts = [0xF0, 0x90, 0x90, 0x90, 0xF0, #0
                 0x20, 0x60, 0x20, 0x20, 0x70, #1
                 0xF0, 0x10, 0xF0, 0x80, 0xF0, #2
                 0xF0, 0x10, 0xF0, 0x10, 0xF0, #3
                 0x90, 0x90, 0xF0, 0x10, 0x10, #4
                 0xF0, 0x80, 0xF0, 0x10, 0xF0, #5
                 0xF0, 0x80, 0xF0, 0x90, 0xF0, #6
                 0xF0, 0x10, 0x20, 0x40, 0x40, #7
                 0xF0, 0x90, 0xF0, 0x90, 0xF0, #8
                 0xF0, 0x90, 0xF0, 0x10, 0xF0, #9
                 0xF0, 0x90, 0xF0, 0x90, 0x90, #A
                 0xE0, 0x90, 0xE0, 0x90, 0xE0, #B
                 0xF0, 0x80, 0x80, 0x80, 0xF0, #C
                 0xE0, 0x90, 0x90, 0x90, 0xE0, #D
                 0xF0, 0x80, 0xF0, 0x80, 0xF0, #E
                 0xF0, 0x80, 0xF0, 0x80, 0x80]  #F
        self.memory.write_bytes_at(fonts, 0x50)

        # Load the rom into memory at position 0x200
        with open(self.rom, 'rb') as file:
            file_bytes = file.read()
            self.memory.write_bytes_at(file_bytes, 0x200)

        self.PC = 0x200 # Set pc to the start of the program (ie. 0x200).

        pygame.display.set_caption(self.rom.split('.')[0])

        # Keyboard mapping 
        self.keyboard = {
                            0x1: pygame.K_1, 0x2: pygame.K_2, 0x3: pygame.K_3, 0xc: pygame.K_4,
                            0x4: pygame.K_q, 0x5: pygame.K_w, 0x6: pygame.K_e, 0xd: pygame.K_r,
                            0x7: pygame.K_a, 0x8: pygame.K_s, 0x9: pygame.K_d, 0xe: pygame.K_f,
                            0xa: pygame.K_z, 0x0: pygame.K_x, 0xb: pygame.K_c, 0xf: pygame.K_v
                        }

        self.run() # run the main loop

    def update_display(self):
        for y in range(self.resolution[1]):
            for x in range(self.resolution[0]):
                color = WHITE if self.display_buffer[y][x] == 1 else BLACK
                self.virtual_screen.set_at((x, y), color)
        scaled_screen = pygame.transform.scale(self.virtual_screen, self.window_size)
        self.screen.blit(scaled_screen, (0, 0))
        pygame.display.flip()

    def read_NN(self, nibble1, nibble2):
        int1 = int(nibble1, 16)
        int2 = int(nibble2, 16)

        return (int1 << 4) | int2

    def read_NNN(self, nibble1, nibble2, nibble3):
        # Turn the 3 nibbles into a 12 bit int 
        int1 = int(nibble1, 16)
        int2 = int(nibble2, 16)
        int3 = int(nibble3, 16)

        combined = (int1 << 8) | (int2 << 4) | int3

        return combined #& 0xFFF
    
    def read_register(self, nibble):
        reg_index = nibble[-1].upper()

        var_name = f'V{reg_index}'
        # Return the value of the register in V(nibble)
        return getattr(self, var_name, None)
    
    def write_register(self, nibble, value):
        reg_index = nibble[-1].upper()

        var_name = f'V{reg_index}'
        value = value & 255
        # Return the value of the register in V(nibble)
        setattr(self, var_name, value)

    def run_timers(self):
        # Reduce the timers
        while True:
            if self.delay_timer > 0:
                self.delay_timer -= 1

            if self.sound_timer > 0 :
                self.sound_timer -= 1


            self.clock.tick(60)


    def run(self):
        timer_thread = threading.Thread(target=self.run_timers)
        timer_thread.start() # Run the timers independently of the executing of opcodes, since some opcdoes can halt the execution.

        while True: # Represent a cycle
            #Read the opcode
            opcode = self.memory.read_opcode_at(self.PC)
            self.execute(opcode)
            print(opcode)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    break

            self.clock.tick(1000) # Slow it down artificially to represent a shitty hardware
            #self.update_display()

        timer_thread.join()


    def execute(self, opcode):
        # This is gonna be a big if else to match the opcodes
        # Remember, the opcode consists of 4 nibble

        # Either 0NNN or 00E0
        if opcode[0] == '0x0':

            # 00E0 Clears the screen.
            if opcode[1] == '0x0' and opcode[2] == '0xe' and opcode[3] == '0x0':
                for i in range(self.resolution[0]):
                    for j in range(self.resolution[1]):
                        self.display_buffer[j][i] = 0
                self.update_display()
                self.PC += 2
                #pass

            # 00EE return
            elif opcode[1] == '0x0' and opcode[2] == '0xe' and opcode[3] == '0xe':
                self.PC = self.stack.pop()
                self.PC += 2

        # Only 1NNN
        elif opcode[0] == '0x1':
            
            # 1NNN goto NNN
            self.PC = self.read_NNN(opcode[1], opcode[2], opcode[3])

        # Only 2NNN
        elif opcode[0] == '0x2':

            # 2NNN *(0xNNN)()
            self.stack.append(self.PC)
            self.PC = self.read_NNN(opcode[1], opcode[2], opcode[3])

        # Only 3XNN
        elif opcode[0] == '0x3':

            #3XNN if (Vx == NN) skip instruction
            if(self.read_register(opcode[1]) == self.read_NN(opcode[2], opcode[3])):
                self.PC += 2
            self.PC += 2

        # Only 4XNN
        elif opcode[0] == '0x4':

            #4XNN if (Vx != NN) skip instruction
            if(self.read_register(opcode[1]) != self.read_NN(opcode[2], opcode[3])):
                self.PC += 2
            self.PC += 2

        # Only 5XY0
        elif opcode[0] == '0x5':

            # 5XY0 if (Vx == Vy) skip instruction
            if(self.read_register(opcode[1]) == self.read_register(opcode[2])):
                self.PC += 2
            self.PC += 2

        # Only 6XNN 
        elif opcode[0] == '0x6':
            
            #6XNN Vx = NN
            self.write_register(opcode[1], self.read_NN(opcode[2], opcode[3]))
            self.PC += 2

        # Only 7XNN
        elif opcode[0] == '0x7':

            # 7XNN Vx += NN
            add_value = self.read_register(opcode[1]) + self.read_NN(opcode[2], opcode[3])
            add_value = add_value & 0xFF # The register is 1 byte. Represent an overflow by doing this.

            self.write_register(opcode[1], add_value)
            self.PC += 2

        # Either 8XY0, 8XY1, 8XY2, 8XY3, 8XY4, 8XY5, 8XY6, 8XY7, 8XYE
        elif opcode[0] == '0x8':

            # 8XY0 Vx = Vy
            if(opcode[3] == '0x0'):
                self.write_register(opcode[1], self.read_register(opcode[2]))
                self.PC += 2

            # 8XY1 Vx |= Vy
            elif(opcode[3] == '0x1'):
                value = self.read_register(opcode[1]) | self.read_register(opcode[2])
                self.write_register(opcode[1], value)
                self.PC += 2

            # 8XY2 Vx &= Vy
            elif(opcode[3] == '0x2'):
                Vx = self.read_register(opcode[1])
                Vy = self.read_register(opcode[2])
                #print(Vx, Vy)
                value = self.read_register(opcode[1]) & self.read_register(opcode[2])
                self.write_register(opcode[1], value)
                self.PC += 2

            # 8XY3 Vx ^= Vy
            elif(opcode[3] == '0x3'):
                value = self.read_register(opcode[1]) ^ self.read_register(opcode[2])
                self.write_register(opcode[1], value)
                self.PC += 2

            # 8XY4 Vx += Vy
            elif(opcode[3] == '0x4'):
                value = self.read_register(opcode[1]) + self.read_register(opcode[2])

                self.write_register(opcode[1], value)

                if value > 0xFF:
                    self.VF = 1
                    value &= 0xFF
                else:
                    self.VF = 0

                self.PC += 2

            # 8XY5 Vx -= Vy
            elif(opcode[3] == '0x5'):
                Vx = self.read_register(opcode[1])
                Vy = self.read_register(opcode[2])

                if Vx >= Vy:
                    self.VF = 1
                else:
                    self.VF = 0
                
                value = (Vx - Vy)

                self.write_register(opcode[1], value)
                self.PC += 2

            # 8XY6 Vx >>= 1
            elif opcode[3] == '0x6':
                Vx = self.read_register(opcode[1])
                value = Vx >> 1
                self.write_register(opcode[1], value)
                self.VF = Vx & 1
                self.PC += 2

            # 8XY7 Vx = Vy - Vx
            elif opcode[3] == '0x7':
                Vx = self.read_register(opcode[1])
                Vy = self.read_register(opcode[2])

                self.write_register(opcode[1], Vy - Vx)

                if Vx > Vy:
                    self.VF = 0
                else:
                    self.VF = 1

                self.PC += 2

            # 8XYE Vx <<= 1
            elif opcode[3] == '0xe':
                Vx = self.read_register(opcode[1])
            
                Vx <<= 1

                self.write_register(opcode[1], Vx)

                self.VF = (Vx >> 7) & 1
                self.PC += 2

        # Only 9XY0
        elif opcode[0] == '0x9':

            # 9XY0 if (Vx != Vy) skip instruction
            if(self.read_register(opcode[1]) != self.read_register(opcode[2])):
                self.PC += 2
            self.PC += 2

        # Only ANNN
        elif opcode[0] == '0xa':

            # ANNN I = NNN
            self.I = self.read_NNN(opcode[1], opcode[2], opcode[3])
            self.PC += 2

        # Only BNNN
        elif opcode[0] == '0xb':

            # BNNN PC = V0 + NNN
            self.PC = self.read_register('0x0') + self.read_NNN(opcode[1], opcode[2], opcode[3])

        # Only CXNN
        elif opcode[0] == '0xc':

            # CXNN Vx = rand() & NN
            value = random.randint(0, 255) & self.read_NN(opcode[2], opcode[3])
            self.write_register(opcode[1], value)
            self.PC += 2

        # Only DXYN
        elif opcode[0] == '0xd':

            #DXYN draw(Vx, Vy, N)
            x = self.read_register(opcode[1])
            x = x % 64 # The screen is only 64 pixels so modulo it
            y = self.read_register(opcode[2])
            y = y % 32

            height = int(opcode[3], 16)

            sprite_address = self.I

            for row in range(height):
                bits = [int(bit) for bit in '{:08b}'.format(self.memory.read_bytes_at(self.I + row)[0])]
                self.VF = 0
                for i in range(8):
                    if x + i < 64 and y + row < 32: # Dont go beyond the resolution
                        previous_val = self.display_buffer[y + row][x + i]
                        self.display_buffer[y + row][x + i] ^= bits[i]
                        if previous_val == 1 and self.display_buffer[y + row][x + i] == 0:# If set and changed to unset
                            self.VF = 1

            self.update_display()
            self.PC += 2

        # Either EX9E or EXA1
        elif opcode[0] == '0xe':

            #EX9E if (key() == Vx) skip instruction
            if opcode[2] == '0x9' and opcode[3] == '0xe':
                #print("called")
                Key = self.keyboard[self.read_register(opcode[1])]
                if pygame.key.get_pressed()[Key]:
                    self.PC += 2
                self.PC += 2

            # EXA1 if (key() != Vx) skip instruction
            elif opcode[2] == '0xa' and opcode[3] == '0x1':
                #print("called")
                Key = self.keyboard[self.read_register(opcode[1])]
                if not pygame.key.get_pressed()[Key]:
                    self.PC += 2
                self.PC += 2

        # Either FX07, FX0A, FX15, FX18, FX1E, FX29, FX33, FX55, FX65
        elif opcode[0] == '0xf':

            #FX07 Vx = get_delay()
            if opcode[2] == '0x0' and opcode[3] == '0x7':
                self.write_register(opcode[1], self.delay_timer)
                self.PC += 2

            # FX0A Vx = get_key()
            elif opcode[2] == '0x0' and opcode[3] == '0xa':
                waiting_for_input = True
                while waiting_for_input:
                    for event in pygame.event.get():
                        if event.type == pygame.KEYDOWN:
                            if event.key in self.keyboard.values():
                                for key, value in self.keyboard:
                                    if value == event.key:
                                        self.write_register(opcode[1], key)
                                        waiting_for_input = False
                self.PC += 2

            # FX15 delay_timer(Vx)
            elif opcode[2] == '0x1' and opcode[3] == '0x5':
                self.delay_timer = self.read_register(opcode[1])
                self.PC += 2

            # FX18 sound_timer(Vx)
            elif opcode[2] == '0x1' and opcode[3] == '0x8':
                self.sound_timer = self.read_register(opcode[1])
                self.PC += 2

            # FX1E I += Vx
            elif opcode[2] == '0x1' and opcode[3] == '0xe':
                self.I += self.read_register(opcode[1])
                self.I = self.I & 0xFFF # Overflow
                self.PC += 2

            # FX29 I = sprite_addr[Vx]
            elif opcode[2] == '0x2' and opcode[3] == '0x9':
                self.I = 0x50 + self.read_register(opcode[1]) # 0x50 is the locatoin of the font. Vx will be the character
                self.PC += 2

            # FX33 set_BCD(Vx) *(I+0) = BCD(3); *(I+1) = BCD(2); *(I+2) = BCD(1);
            elif opcode[2] == '0x3' and opcode[3] == '0x3':
                Vx = self.read_register(opcode[1])

                number = f"{Vx:03d}"
                digit1, digit2, digit3 = number

                self.memory.write_bytes_at([int(digit1), int(digit2), int(digit3)], self.I, 3)
                self.PC += 2

            # FX55 reg_dump(Vx, &I)
            elif opcode[2] == '0x5' and opcode[3] == '0x5':
                registers = [self.V0, self.V1, self.V2, self.V3, self.V4, self.V5, self.V6, self.V7,
                             self.V8, self.V9, self.VA, self.VB, self.VC, self.VD, self.VE, self.VF]
                #print(opcode[1])
                register_to_dump = registers[0: int(opcode[1], 16) + 1]
                self.memory.write_bytes_at(register_to_dump, self.I)
                #print(register_to_dump)

                self.PC += 2

            # FX65 reg_load(Vx, &I)
            elif opcode[2] == '0x6' and opcode[3] == '0x5':
                for i in range(int(opcode[1], 16) + 1):
                    self.write_register(hex(i), self.memory.read_bytes_at(self.I + i)[0])

                self.PC += 2
 
        

Emulator("games\Space Invaders [David Winter].ch8")