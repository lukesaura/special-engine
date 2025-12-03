# can_bike_gui_clean.py
# Clean, uncluttered CAN bike dashboard
# Edit ECU_PORT and ACT_PORT at top, then run.
import serial, threading, pygame, sys, time, math, re
from datetime import datetime

# === EDIT THESE ===
ECU_PORT = "COM20"
ACT_PORT = "COM21"
BAUD = 115200
# ==================

# open serial
try:
    ser_ecu = serial.Serial(ECU_PORT, BAUD, timeout=0.1)
except Exception as e:
    print("Failed to open ECU port:", e); sys.exit(1)
try:
    ser_act = serial.Serial(ACT_PORT, BAUD, timeout=0.1)
except Exception as e:
    print("Failed to open Actuator port:", e); ser_ecu.close(); sys.exit(1)

# logging (line-buffered)
log_filename = "can_bike_log_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
log_file = open(log_filename, "a", buffering=1)
print("Logging to", log_filename)

# state
state = {'spd':0.0,'rpm':0,'thr':0,'brk':0,'L':0,'R':0,'odo':0.0,'fuel':0.0,'fb':0,'hl':0}
running = True
last_raw_line = ""
show_raw = False

# tolerant parser
pattern = re.compile(r'([A-Za-z]+)\s*:\s*([-+]?\d+\.?\d*)')

def read_actuator():
    global running, last_raw_line
    while running:
        try:
            raw = ser_act.readline().decode(errors='ignore')
            if not raw:
                time.sleep(0.005); continue
            raw = raw.strip()
            if not raw: continue
            last_raw_line = raw
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            log_file.write(f"{ts} | {raw}\n")
            s = raw.replace(',', ';')
            matches = pattern.findall(s)
            for k,v in matches:
                key = k.strip().upper()
                try:
                    val = float(v) if '.' in v else int(v)
                except:
                    continue
                if key == 'SPD': state['spd'] = float(val)
                elif key == 'RPM': state['rpm'] = int(val)
                elif key == 'THR': state['thr'] = int(val)
                elif key == 'BRK': state['brk'] = int(val)
                elif key == 'L': state['L'] = int(val)
                elif key == 'R': state['R'] = int(val)
                elif key == 'ODO': state['odo'] = float(val)
                elif key == 'FUEL': state['fuel'] = float(val)
                elif key == 'FB': state['fb'] = int(val)
                elif key == 'HL': state['hl'] = int(val)
        except Exception:
            time.sleep(0.01)

t = threading.Thread(target=read_actuator, daemon=True)
t.start()

# Pygame setup
pygame.init()
W, H = 1000, 520
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("CAN Bike — Clean Dashboard")
# fonts
f_small = pygame.font.SysFont(None, 20)
f_med = pygame.font.SysFont(None, 34)
f_big = pygame.font.SysFont(None, 96)
clock = pygame.time.Clock()

key_state = {'UP':0, 'DOWN':0}
blink_state = True
last_blink = time.time()

def send_ecu(line):
    try:
        ser_ecu.write((line+"\n").encode())
    except:
        pass

def draw_text(s, x, y, fnt=f_small, color=(220,220,220)):
    surf = fnt.render(s, True, color)
    screen.blit(surf, (x,y))

# Simplified visuals
def draw_fuel_bars(x, y, bar_w, bar_h, bars):
    gap = 8
    for i in range(4):
        bx = x + i*(bar_w+gap)
        color = (40,200,80) if i < bars else (40,40,40)
        pygame.draw.rect(screen, color, (bx, y, bar_w, bar_h))
        pygame.draw.rect(screen, (14,14,14), (bx, y, bar_w, bar_h), 2)

def draw_rpm_gauge(cx, cy, radius, rpm):
    # outer
    pygame.draw.circle(screen, (30,30,30), (cx,cy), radius)
    pygame.draw.circle(screen, (10,10,10), (cx,cy), radius-8)
    # ticks 0..9k labeled 0..9
    for i in range(10):
        frac = i/9.0
        angle = math.radians(210) - frac*math.radians(240)
        x1 = cx + int((radius-12)*math.cos(angle))
        y1 = cy - int((radius-12)*math.sin(angle))
        x2 = cx + int((radius-36)*math.cos(angle))
        y2 = cy - int((radius-36)*math.sin(angle))
        pygame.draw.line(screen, (120,120,120), (x1,y1), (x2,y2), 3)
        # small label
        lx = cx + int((radius-60)*math.cos(angle))
        ly = cy - int((radius-60)*math.sin(angle))
        txt = f_small.render(str(i), True, (200,200,200))
        screen.blit(txt, (lx-8, ly-8))
    # needle
    rm = max(0, min(rpm, 9000))
    frac = rm/9000.0
    angle = math.radians(210) - frac*math.radians(240)
    nx = cx + int((radius-48)*math.cos(angle))
    ny = cy - int((radius-48)*math.sin(angle))
    pygame.draw.line(screen, (220,60,60), (cx,cy), (nx,ny), 6)
    pygame.draw.circle(screen, (220,220,220), (cx,cy), 6)

def draw_speed_gauge(cx, cy, radius, speed):
    pygame.draw.circle(screen, (28,28,28), (cx,cy), radius)
    pygame.draw.circle(screen, (8,8,8), (cx,cy), radius-8)
    # ticks 0,20..120
    for val in range(0,121,20):
        frac = val/120.0
        angle = math.radians(210) - frac*math.radians(240)
        x1 = cx + int((radius-12)*math.cos(angle))
        y1 = cy - int((radius-12)*math.sin(angle))
        x2 = cx + int((radius-36)*math.cos(angle))
        y2 = cy - int((radius-36)*math.sin(angle))
        pygame.draw.line(screen, (140,140,140), (x1,y1), (x2,y2), 3)
        lx = cx + int((radius-60)*math.cos(angle))
        ly = cy - int((radius-60)*math.sin(angle))
        lbl = f_small.render(str(val), True, (210,210,210))
        screen.blit(lbl, (lx-10, ly-10))
    s = max(0.0, min(speed, 120.0))
    frac = s/120.0
    angle = math.radians(210) - frac*math.radians(240)
    nx = cx + int((radius-48)*math.cos(angle))
    ny = cy - int((radius-48)*math.sin(angle))
    pygame.draw.line(screen, (30,190,220), (cx,cy), (nx,ny), 6)
    pygame.draw.circle(screen, (200,200,200), (cx,cy), 6)

# layout positions (spacious)
rpm_cx, rpm_cy, rpm_r = 250, 280, 200
spd_cx, spd_cy, spd_r = 630, 240, 200

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running=False; ser_ecu.close(); ser_act.close(); log_file.close(); pygame.quit(); sys.exit(0)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                if key_state['UP']==0: key_state['UP']=1; send_ecu("UP:1")
            elif event.key == pygame.K_DOWN:
                if key_state['DOWN']==0: key_state['DOWN']=1; send_ecu("DOWN:1")
            elif event.key == pygame.K_LEFT:
                send_ecu("LEFT_TOGGLE")
            elif event.key == pygame.K_RIGHT:
                send_ecu("RIGHT_TOGGLE")
            elif event.key == pygame.K_r:
                send_ecu("RESET_IND")
            elif event.key == pygame.K_SPACE:
                send_ecu("HEAD_TOGGLE")
            elif event.key == pygame.K_d:
                # toggle debug raw line on/off (d for debug)
                show_raw = not show_raw
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_UP:
                if key_state['UP']==1: key_state['UP']=0; send_ecu("UP:0")
            elif event.key == pygame.K_DOWN:
                if key_state['DOWN']==1: key_state['DOWN']=0; send_ecu("DOWN:0")

    # blink toggle
    if time.time() - last_blink > 0.5:
        blink_state = not blink_state; last_blink = time.time()

    # background
    screen.fill((12,12,18))

    # draw gauges
    draw_rpm_gauge(rpm_cx, rpm_cy, rpm_r, state['rpm'])
    draw_speed_gauge(spd_cx, spd_cy, spd_r, state['spd'])

    # big numbers (clean)
    spd_text = f"{state['spd']:.1f}"
    rpm_text = f"{state['rpm']}"
    # numeric speed
    surf_spd = f_big.render(spd_text, True, (240,240,240))
    screen.blit(surf_spd, (spd_cx-60, spd_cy+60))
    # rpm small text
    draw_text(rpm_text, rpm_cx-30, rpm_cy+90, f_med)

    # odometer (small, unobtrusive)
    draw_text(f"ODO: {state['odo']:.3f} km", spd_cx-40, spd_cy+140, f_small)

    # throttle percent
    thr_pct = int((state['thr']/255.0)*100)
    draw_text(f"THR: {thr_pct}%", spd_cx+120, spd_cy+60, f_small)

    # fuel bars and liters
    draw_text("FUEL", spd_cx+120, spd_cy+8, f_small)
    draw_text(f"{state['fuel']:.2f} L", spd_cx+180, spd_cy+8, f_small)
    draw_fuel_bars(spd_cx+120, spd_cy+36, 36, 60, state.get('fb',0))

    # headlight circle
    hl_color = (255,255,170) if state['hl'] else (60,60,60)
    pygame.draw.circle(screen, hl_color, (spd_cx+200, spd_cy+130), 14)
    draw_text("HL", spd_cx+193, spd_cy+150, f_small)

    # brake box
    br_col = (200,40,40) if state['brk'] else (40,40,40)
    pygame.draw.rect(screen, br_col, (spd_cx+80, spd_cy+130, 100, 36))
    draw_text("BRAKE", spd_cx+110, spd_cy+138, f_small)

    # indicators left/right (small)
    Lcol = (255,200,0) if state['L'] and blink_state else (70,70,70)
    Rcol = (255,200,0) if state['R'] and blink_state else (70,70,70)
    pygame.draw.polygon(screen, Lcol, [(rpm_cx-110, rpm_cy+20),(rpm_cx-132, rpm_cy+40),(rpm_cx-110, rpm_cy+60)])
    pygame.draw.polygon(screen, Rcol, [(rpm_cx+110, rpm_cy+20),(rpm_cx+132, rpm_cy+40),(rpm_cx+110, rpm_cy+60)])

    # help (compact)
    draw_text("Controls: Up (hold), Down, ←/→ (indicators), Space (headlight), R (reset), D (toggle raw)", 10, H-26, f_small)

    # optional raw line (toggle with 'd')
    if show_raw:
        draw_text("RAW: " + (last_raw_line[:160] + ("..." if len(last_raw_line)>160 else "")), 10, H-46, f_small,)

    pygame.display.flip()
    clock.tick(60)
