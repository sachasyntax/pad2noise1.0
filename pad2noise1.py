import tkinter as tk
from tkinter import filedialog
import numpy as np
import sounddevice as sd
import os
import time

# globals
audio_data1 = None  # pool 1
audio_data2 = None  # pool 2
file_size1 = 0
file_size2 = 0
play_pos1 = 0.0
play_pos2 = 0.0
nav_x = 0.5
nav_y = 0.5
current_directory = None
file_list = []
current_index1 = -1
current_index2 = -1
WINDOW_SIZE = 4096

# feedback
feedback_buffer1 = np.zeros(WINDOW_SIZE, dtype=np.float32)
feedback_buffer2 = np.zeros(WINDOW_SIZE, dtype=np.float32)
feedback_pos1 = 0
feedback_pos2 = 0
feedback_amount1 = 0.005
feedback_amount2 = 0.02

# lowpass
cutoff = 0.4
last_val = 0.0

# pool flag
pool1_loaded = False
pool2_loaded = False

# step
step1 = 1
step2 = 1

# mouse next
prev_mouse_x = 0.5
prev_mouse_y = 0.5
prev_time = None
trigger_cooldown = 0.2
last_trigger_time1 = 0
last_trigger_time2 = 0

# functions
def log(msg):
    log_box.insert(tk.END, msg + "\n")
    log_box.see(tk.END)

def load_audio(pool_num, path=None):
    global audio_data1, audio_data2, file_size1, file_size2
    global pool1_loaded, pool2_loaded, current_directory, file_list

    if path is None:
        path = filedialog.askopenfilename()
    if not path:
        return

    current_directory = os.path.dirname(path)
    file_list = sorted([
        os.path.join(current_directory, f)
        for f in os.listdir(current_directory)
        if os.path.isfile(os.path.join(current_directory, f)) and os.path.getsize(os.path.join(current_directory, f)) > 0
    ])

    try:
        with open(path, "rb") as f:
            data = np.frombuffer(f.read(), dtype=np.uint8)
        data = (data.astype(np.float32) - 128) / 128.0
    except Exception as e:
        log(f"Error loading {path}: {e}")
        return

    if pool_num == 1:
        audio_data1 = data
        file_size1 = len(data)
        pool1_loaded = True
        log(f"Pool 1 loaded: {os.path.basename(path)} ({file_size1} bytes)")
    else:
        audio_data2 = data
        file_size2 = len(data)
        pool2_loaded = True
        log(f"Pool 2 loaded: {os.path.basename(path)} ({file_size2} bytes)")

    if pool1_loaded and pool2_loaded:
        start_audio()

def next_file(pool_num):
    global current_index1, current_index2
    if not file_list:
        return
    if pool_num == 1:
        current_index1 = (current_index1 + 1) % len(file_list)
        load_audio(1, file_list[current_index1])
    else:
        current_index2 = (current_index2 + 1) % len(file_list)
        load_audio(2, file_list[current_index2])

def mouse_move(event):
    global nav_x, nav_y, prev_mouse_x, prev_mouse_y, prev_time
    global last_trigger_time1, last_trigger_time2
    global step1, step2

    # non-linearità
    nx = np.sqrt(event.x / canvas.winfo_width())
    ny = np.sqrt(event.y / canvas.winfo_height())

    # accellerazione
    now = time.time()
    if prev_time is not None:
        dt = now - prev_time
        if dt > 0:
            vx = (nx - prev_mouse_x) / dt
            vy = (ny - prev_mouse_y) / dt

            threshold = 5.0
            if vy > threshold and now - last_trigger_time1 > trigger_cooldown:
                next_file(1)
                last_trigger_time1 = now
            if vx > threshold and now - last_trigger_time2 > trigger_cooldown:
                next_file(2)
                last_trigger_time2 = now

    prev_mouse_x = nx
    prev_mouse_y = ny
    prev_time = now

    nav_x = nx
    nav_y = ny

    # step update
    step1 = int(np.interp(nav_y, [0, 1], [1, 8]))
    step2 = int(np.interp(nav_x, [0, 1], [1, 12]))

def audio_callback(outdata, frames, time, status):
    global play_pos1, play_pos2, feedback_pos1, feedback_pos2, last_val
    out = np.zeros(frames, dtype=np.float32)

    if (audio_data1 is None or audio_data2 is None or file_size1 == 0 or file_size2 == 0):
        outdata[:] = 0
        return

    # params 
    speed1 = np.interp(nav_y, [0,1], [0.2, 2.0])
    speed2 = np.interp(nav_x, [0,1], [0.5, 3.0])
    distortion2 = 0.5  # fissa

    feedback_window1_local = int(np.interp(nav_y, [0,1], [256, WINDOW_SIZE]))
    feedback_window2_local = int(np.interp(nav_x, [0,1], [256, WINDOW_SIZE]))

    for i in range(frames):
        # pool1
        idx1 = int(nav_x * (file_size1 - 1)) + int(play_pos1)
        idx1 %= file_size1
        val1 = audio_data1[idx1]
        val1 += feedback_amount1 * feedback_buffer1[feedback_pos1]
        feedback_buffer1[feedback_pos1] = val1
        feedback_pos1 = (feedback_pos1 + 1) % feedback_window1_local
        play_pos1 += speed1 * step1
        if play_pos1 >= file_size1:
            play_pos1 = 0.0

        # pool2
        idx2 = int(nav_y * (file_size2 - 1)) + int(play_pos2)
        idx2 %= file_size2
        val2 = audio_data2[idx2]
        val2 += feedback_amount2 * feedback_buffer2[feedback_pos2]
        feedback_buffer2[feedback_pos2] = val2
        feedback_pos2 = (feedback_pos2 + 1) % feedback_window2_local
        val2 = np.tanh(val2 * (1.0 + distortion2))
        play_pos2 += speed2 * step2
        if play_pos2 >= file_size2:
            play_pos2 = 0.0

        # mix
        mixed = (val1 + val2) * 0.5
        last_val = cutoff * mixed + (1 - cutoff) * last_val
        out[i] = last_val

    # saturazione
    out = np.tanh(out*1.3) #eventuale sat

    outdata[:,0] = out
    outdata[:,1] = out

# audio stream
stream = sd.OutputStream(
    channels=2, samplerate=44100, blocksize=1024, callback=audio_callback
)

def start_audio():
    if not stream.active:
        stream.start()

# GUI
root = tk.Tk()
root.title("DATA NAVIGATOR 1.0")

controls = tk.Frame(root)
controls.pack(pady=5)
tk.Button(controls, text="LOAD1", command=lambda: load_audio(1)).pack(side="left", padx=5)
tk.Button(controls, text="LOAD2", command=lambda: load_audio(2)).pack(side="left", padx=5)
tk.Button(controls, text="NEXT1", command=lambda: next_file(1)).pack(side="left", padx=5)
tk.Button(controls, text="NEXT2", command=lambda: next_file(2)).pack(side="left", padx=5)

canvas = tk.Canvas(root, bg="black", height=400)
canvas.pack(fill="x")
canvas.bind("<Motion>", mouse_move)

log_box = tk.Text(root, height=8)
log_box.pack(fill="both", expand=True)

root.mainloop()
