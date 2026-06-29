import sys
import time
import threading
import os
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import mido
import ctypes
import queue
import pydirectinput
import math

try:
    myappid = 'qlad.midilearner.led.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

CONFIG_FILE = "settings.ini"

pydirectinput.PAUSE = 0

class RobloxKeys:
    NUM0 = 'num0'
    NUM1 = 'numpad1'
    NUM2 = 'numpad2'
    NUM3 = 'numpad3'
    NUM4 = 'numpad4'
    NUM5 = 'numpad5'
    NUM6 = 'numpad6'
    NUM7 = 'numpad7'
    NUM8 = 'numpad8'
    NUM9 = 'numpad9'
    MULTIPLY = 'multiply'
    ADD = 'add'
    SUBTRACT = 'subtract'

pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM0] = 0x52
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM1] = 0x4F
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM2] = 0x50
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM3] = 0x51
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM4] = 0x4B
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM5] = 0x4C
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM6] = 0x4D
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM7] = 0x47
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM8] = 0x48
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.NUM9] = 0x49
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.MULTIPLY] = 0x37
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.ADD] = 0x4E
pydirectinput.KEYBOARD_MAPPING[RobloxKeys.SUBTRACT] = 0x4A

ROBLOX_KEY_ARRAY = [
    RobloxKeys.NUM0, RobloxKeys.NUM1, RobloxKeys.NUM2, RobloxKeys.NUM3, 
    RobloxKeys.NUM4, RobloxKeys.NUM5, RobloxKeys.NUM6, RobloxKeys.NUM7, 
    RobloxKeys.NUM8, RobloxKeys.NUM9, RobloxKeys.SUBTRACT, RobloxKeys.ADD
]

COLOR_PRESETS = {
    "Red": "#ff4757",
    "Lavender": "#e0b0ff",
    "Purple": "#9b59b6",
    "Blue": "#3498db",
    "Green": "#2ecc71",
    "Orange": "#e67e22",
    "Yellow": "#f1c40f",
    "Pink": "#ff69b4",
    "Cyan": "#1abc9c"
}

def get_windows_system_theme():
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except Exception:
        return "dark"

def set_window_title_bar_theme(root, theme):
    try:
        root.update()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if hwnd == 0:
            hwnd = root.winfo_id()
        rendering_mode = ctypes.c_int(1 if theme == "dark" else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_mode), ctypes.sizeof(rendering_mode)
        )
    except Exception:
        pass

def extract_notes_by_time(midi_file_path):
    mid = mido.MidiFile(midi_file_path)
    ticks_per_beat = mid.ticks_per_beat
    all_events = []
    
    for track in mid.tracks:
        current_tick = 0
        for msg in track:
            current_tick += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                all_events.append({'tick': current_tick, 'note': msg.note, 'type': 'on'})
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                all_events.append({'tick': current_tick, 'note': msg.note, 'type': 'off'})
               
    all_events.sort(key=lambda x: x['tick'])
   
    steps = []
    current_step = set()
    last_tick = -1
   
    for event in all_events:
        if event['type'] == 'on':
            if last_tick != -1 and event['tick'] > last_tick + (ticks_per_beat / 8):
                if current_step:
                    steps.append(list(current_step))
                    current_step = set()
            current_step.add(event['note'])
            last_tick = event['tick']
           
    if current_step:
        steps.append(list(current_step))
       
    return steps


class RobloxConnectWindow:
    def __init__(self, parent, gui_instance):
        self.parent = parent
        self.gui = gui_instance
        self.window = None

    def show(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.parent)
        self.window.title("Roblox MIDI Connect")
        self.window.geometry("340x240")
        self.window.resizable(False, False)
        
        self.window.attributes("-topmost", self.gui.roblox_always_on_top.get())
        set_window_title_bar_theme(self.window, self.gui.theme_mode)
        
        self.apply_colors()

        tk.Label(self.window, text="Roblox Engine Controller", font=("Arial", 11, "bold"), bg=self.bg, fg=self.fg).pack(pady=10)

        # Pin state checkbox
        self.top_chk = tk.Checkbutton(
            self.window, text="Keep Window Always on Top", variable=self.gui.roblox_always_on_top,
            command=self.update_pin, bg=self.bg, fg=self.fg, activebackground=self.bg, activeforeground=self.fg, selectcolor=self.select_bg
        )
        self.top_chk.pack(pady=5)

        # Main Activation Buttons
        self.status_lbl = tk.Label(self.window, text="Status: Disconnected", font=("Arial", 10, "italic"), bg=self.bg, fg="orange")
        self.status_lbl.pack(pady=8)

        self.connect_btn = tk.Button(self.window, text="Connect to Roblox", font=("Arial", 9, "bold"), bg="#2ecc71", fg="white", width=18, command=self.connect_engine)
        self.connect_btn.pack(pady=4)

        self.disconnect_btn = tk.Button(self.window, text="Disconnect Engine", font=("Arial", 9, "bold"), bg="#e74c3c", fg="white", width=18, command=self.disconnect_engine)
        self.disconnect_btn.pack(pady=4)
        
        self.refresh_ui_state()

    def update_pin(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.attributes("-topmost", self.gui.roblox_always_on_top.get())

    def connect_engine(self):
        self.gui.roblox_connected.set(True)
        self.refresh_ui_state()

    def disconnect_engine(self):
        self.gui.roblox_connected.set(False)
        self.refresh_ui_state()

    def refresh_ui_state(self):
        if self.gui.roblox_connected.get():
            self.status_lbl.config(text="Status: Connected & Streaming", fg="#2ecc71")
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
        else:
            self.status_lbl.config(text="Status: Disconnected", fg="orange")
            self.connect_btn.config(state="normal")
            self.disconnect_btn.config(state="disabled")

    def apply_colors(self):
        effective = self.gui.theme_mode if self.gui.theme_mode != "system" else get_windows_system_theme()
        if effective == "dark":
            self.bg = "#1e1e1e"
            self.fg = "#ffffff"
            self.select_bg = "#3d3d3d"
        else:
            self.bg = "#f9f9f9"
            self.fg = "#000000"
            self.select_bg = "#ffffff"
        self.window.config(bg=self.bg)


class MidiVisualizer:
    def __init__(self, parent, gui_instance):
        self.parent = parent
        self.gui = gui_instance
        self.window = None
        self.keys = {}
        
        self.active_growing_trails = {}
        self.floating_trails = []
        
        self.canvas_width = 1060
        self.canvas_height = 450
        self.key_y_top = 310    
        self.key_y_bottom = 450 

    def show(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.lift()
            return

        self.window = tk.Toplevel(self.parent)
        self.window.title("MIDI Piano Visualizer")
        self.window.geometry(f"{self.canvas_width}x{self.canvas_height}")
        self.window.resizable(False, False)
        self.window.configure(bg="#0f0f11")
        
        self.window.attributes("-topmost", self.gui.viz_always_on_top.get())
        set_window_title_bar_theme(self.window, self.gui.theme_mode)

        self.canvas = tk.Canvas(self.window, width=self.canvas_width, height=self.canvas_height, 
                                bg="#0f0f11", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.draw_keyboard()
        self.animate()

    def draw_keyboard(self):
        self.keys.clear()
        white_keys = []
        black_keys = []
        
        white_width = 20
        black_width = 12
        black_height = 85
        current_x = 10

        for i in range(88):
            note = i + 21
            is_black = (note % 12) in [1, 3, 6, 8, 10]
            if is_black:
                black_keys.append((note, current_x - (black_width // 2) - 4))
            else:
                white_keys.append((note, current_x))
                current_x += white_width + 1

        for note, x in white_keys:
            rect = self.canvas.create_rectangle(
                x, self.key_y_top, x + white_width, self.key_y_bottom, 
                fill="#fcfcfc", outline="#b5b5b5", width=1
            )
            self.keys[note] = {"rect": rect, "type": "white", "x1": x, "x2": x + white_width}

        for note, x in black_keys:
            rect = self.canvas.create_rectangle(
                x, self.key_y_top, x + black_width, self.key_y_top + black_height, 
                fill="#1e1e24", outline="#050505", width=1
            )
            self.keys[note] = {"rect": rect, "type": "black", "x1": x, "x2": x + black_width}

        self.canvas.create_rectangle(0, self.key_y_top - 4, self.canvas_width, self.key_y_top, 
                                     fill="#1a1a1a", outline="#0a0a0a")

    def animate(self):
        if not self.window or not tk.Toplevel.winfo_exists(self.window):
            return

        targets = getattr(self.gui, "active_targets", set())
        pressed = getattr(self.gui, "active_pressed", set())

        target_color = COLOR_PRESETS.get(self.gui.target_color_var.get(), "#ff4757")
        pressed_color = COLOR_PRESETS.get(self.gui.pressed_color_var.get(), "#9b59b6")
        trail_color = COLOR_PRESETS.get(self.gui.trail_color_var.get(), "#e0b0ff")

        for note in list(self.active_growing_trails.keys()):
            if note not in pressed:
                trail_id = self.active_growing_trails.pop(note)
                self.floating_trails.append({"id": trail_id, "life": 1.0})

        for note in pressed:
            if note in self.keys:
                kd = self.keys[note]
                if note not in self.active_growing_trails:
                    trail_id = self.canvas.create_rectangle(
                        kd["x1"] + 2, self.key_y_top - 12, kd["x2"] - 2, self.key_y_top - 4,
                        fill=trail_color, outline=""
                    )
                    self.active_growing_trails[note] = trail_id
                else:
                    trail_id = self.active_growing_trails[note]
                    coords = self.canvas.coords(trail_id)
                    if coords:
                        self.canvas.coords(trail_id, coords[0], coords[1] - 5, coords[2], coords[3])

        remaining_floating = []
        for trail in self.floating_trails:
            self.canvas.move(trail["id"], 0, -5)
            coords = self.canvas.coords(trail["id"])
            
            if coords and coords[3] > 0:
                trail["life"] -= 0.015
                if trail["life"] > 0:
                    remaining_floating.append(trail)
                else:
                    self.canvas.delete(trail["id"])
            else:
                self.canvas.delete(trail["id"])
        self.floating_trails = remaining_floating

        for note, data in self.keys.items():
            if note in targets:
                color = target_color
            elif note in pressed:
                color = pressed_color
            else:
                color = "#ffffff" if data["type"] == "white" else "#1e1e24"

            self.canvas.itemconfig(data["rect"], fill=color)

        for note, data in self.keys.items():
            if data["type"] == "black":
                self.canvas.tag_raise(data["rect"])

        self.window.after(16, self.animate)


class MidiLearnerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MIDI Key Light Learner")
        self.root.geometry("640x740")

        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
           
        icon_path = os.path.join(base_path, "app_icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.midi_path = ""
        self.steps = []
        self.current_step_idx = 0
        self.is_running = False
        self.stop_playback = threading.Event()
        self.skip_step = threading.Event()
        
        self.inport = None
        self.outport = None
        self.hMidiOut = None  
        self.current_in_name = None
        self.current_out_name = None
       
        self.active_targets = set()
        self.active_pressed = set()
        self.visualizer_window = None
        self.roblox_window_instance = None

        self.audio_queue = queue.Queue() 

        self.target_color_var = tk.StringVar(value="Red")
        self.pressed_color_var = tk.StringVar(value="Purple")
        self.trail_color_var = tk.StringVar(value="Lavender")

        self.theme_mode = "system"
        self.options_expanded = False
        self.always_on_top = tk.BooleanVar(value=False)
        self.viz_always_on_top = tk.BooleanVar(value=False)
        self.roblox_always_on_top = tk.BooleanVar(value=False)
        self.roblox_connected = tk.BooleanVar(value=False)
        
        self.enable_audio = tk.BooleanVar(value=True)
        self.enable_weight = tk.BooleanVar(value=True)
        self.enable_pedal = tk.BooleanVar(value=True)
        self.enable_hw_lights = tk.BooleanVar(value=True)

        self.volume_level = tk.IntVar(value=100) 
        self.weight_level = tk.IntVar(value=100) 
        self.delay_level = tk.IntVar(value=0) 

        self.top_bar = tk.Frame(root, bg="#2c3e50", height=40)
        self.top_bar.pack(fill="x", side="top")
        self.top_bar.pack_propagate(False)

        self.options_toggle_btn = tk.Button(self.top_bar, text="≡ Options Panel", bg="#34495e", fg="white",
                                            font=("Arial", 10, "bold"), bd=0, padx=12, command=self.toggle_options)
        self.options_toggle_btn.pack(side="left", fill="y")

        self.options_drawer = tk.Frame(root, bg="#ecf0f1", height=400)

        self.pins_frame = tk.Frame(self.options_drawer, bg="#ecf0f1")
        self.pins_frame.pack(fill="x", padx=15, pady=4)

        self.top_check = tk.Checkbutton(self.pins_frame, text="Always on Top", variable=self.always_on_top,
                                        command=self.update_always_on_top, bg="#ecf0f1", activebackground="#ecf0f1")
        self.top_check.pack(side="left", padx=5)

        self.viz_top_check = tk.Checkbutton(self.pins_frame, text="Visualizer Always on Top", variable=self.viz_always_on_top,
                                            command=self.update_visualizer_on_top, bg="#ecf0f1", activebackground="#ecf0f1")
        self.viz_top_check.pack(side="left", padx=10)

        self.theme_btn = tk.Button(self.pins_frame, text="Theme: System Sync", command=self.cycle_theme, bg="#7f8c8d", fg="white", font=("Arial", 9))
        self.theme_btn.pack(side="right", padx=5)

        self.toggles_frame = tk.Frame(self.options_drawer, bg="#ecf0f1")
        self.toggles_frame.pack(fill="x", padx=15, pady=4)

        self.audio_check = tk.Checkbutton(self.toggles_frame, text="🔊 Audio Engine", variable=self.enable_audio,
                                          command=self.toggle_audio_port, bg="#ecf0f1", activebackground="#ecf0f1")
        self.audio_check.pack(side="left", padx=5)

        self.weight_check = tk.Checkbutton(self.toggles_frame, text="⚖️ Weight Scaling", variable=self.enable_weight,
                                           bg="#ecf0f1", activebackground="#ecf0f1")
        self.weight_check.pack(side="left", padx=10)

        self.pedal_check = tk.Checkbutton(self.toggles_frame, text="🎛️ Pedal Support", variable=self.enable_pedal,
                                          bg="#ecf0f1", activebackground="#ecf0f1")
        self.pedal_check.pack(side="left", padx=10)

        self.hw_lights_check = tk.Checkbutton(self.toggles_frame, text="💡 HW Lights Support", variable=self.enable_hw_lights,
                                              bg="#ecf0f1", activebackground="#ecf0f1")
        self.hw_lights_check.pack(side="left", padx=10)

        self.sliders_row = tk.Frame(self.options_drawer, bg="#ecf0f1")
        self.sliders_row.pack(fill="x", padx=15, pady=6)

        self.vol_label = tk.Label(self.sliders_row, text="Vol:", bg="#ecf0f1")
        self.vol_label.pack(side="left", padx=2)
        self.vol_slider = tk.Scale(self.sliders_row, from_=0, to=200, orient="horizontal", variable=self.volume_level,
                                   length=90, showvalue=True, bg="#ecf0f1", bd=1, highlightthickness=0, command=lambda v: self.apply_hardware_volume())
        self.vol_slider.pack(side="left", padx=2)

        self.weight_label = tk.Label(self.sliders_row, text="Weight:", bg="#ecf0f1")
        self.weight_label.pack(side="left", padx=(10, 2))
        self.weight_slider = tk.Scale(self.sliders_row, from_=1, to=200, orient="horizontal", variable=self.weight_level,
                                      length=90, showvalue=True, bg="#ecf0f1", bd=1, highlightthickness=0)
        self.weight_slider.pack(side="left", padx=2)

        self.delay_label = tk.Label(self.sliders_row, text="Delay (ms):", bg="#ecf0f1")
        self.delay_label.pack(side="left", padx=(10, 2))
        self.delay_slider = tk.Scale(self.sliders_row, from_=0, to=500, orient="horizontal", variable=self.delay_level,
                                     length=85, showvalue=True, bg="#ecf0f1", bd=1, highlightthickness=0)
        self.delay_slider.pack(side="left", padx=2)

        self.save_btn = tk.Button(self.sliders_row, text="💾 Save", command=self.save_settings, bg="#2ecc71", fg="white", font=("Arial", 9, "bold"))
        self.save_btn.pack(side="right", padx=5)

        self.in_label = tk.Label(self.options_drawer, text="Input Port Name:", bg="#ecf0f1")
        self.in_label.pack()
        self.in_combo = ttk.Combobox(self.options_drawer, width=45, state="readonly")
        self.in_combo.pack(pady=2)
        self.in_combo.bind("<<ComboboxSelected>>", lambda e: self.update_midi_ports())

        self.out_label = tk.Label(self.options_drawer, text="Output Port Name (Required for Visualizer Loopback / MIDI Sync):", bg="#ecf0f1")
        self.out_label.pack()
        self.out_combo = ttk.Combobox(self.options_drawer, width=45, state="readonly")
        self.out_combo.pack(pady=2)
        self.out_combo.bind("<<ComboboxSelected>>", lambda e: self.update_midi_ports())

        self.colors_frame = tk.LabelFrame(self.options_drawer, text="🎨 Visualizer Custom Colors", bg="#ecf0f1", font=("Arial", 9, "bold"))
        self.colors_frame.pack(fill="x", padx=15, pady=5)

        color_options = list(COLOR_PRESETS.keys())

        tk.Label(self.colors_frame, text="Target Keys:", bg="#ecf0f1", width=12, anchor="w").grid(row=0, column=0, padx=5, pady=2)
        self.target_combo = ttk.Combobox(self.colors_frame, textvariable=self.target_color_var, values=color_options, state="readonly", width=15)
        self.target_combo.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(self.colors_frame, text="Pressed Keys:", bg="#ecf0f1", width=12, anchor="w").grid(row=1, column=0, padx=5, pady=2)
        self.pressed_combo = ttk.Combobox(self.colors_frame, textvariable=self.pressed_color_var, values=color_options, state="readonly", width=15)
        self.pressed_combo.grid(row=1, column=1, padx=5, pady=2)

        tk.Label(self.colors_frame, text="Note Trails:", bg="#ecf0f1", width=12, anchor="w").grid(row=0, column=2, padx=15, pady=2)
        self.trail_combo = ttk.Combobox(self.colors_frame, textvariable=self.trail_color_var, values=color_options, state="readonly", width=15)
        self.trail_combo.grid(row=0, column=3, padx=5, pady=2)

        self.main_canvas = tk.Frame(root)
        self.main_canvas.pack(fill="both", expand=True)

        self.file_btn = tk.Button(self.main_canvas, text="Browse MIDI File", command=self.browse_file)
        self.file_btn.pack(pady=10)
       
        self.file_label = tk.Label(self.main_canvas, text="No file selected", fg="gray", font=("Arial", 9, "italic"))
        self.file_label.pack(pady=2)

        self.status_label = tk.Label(self.main_canvas, text="Status: Ready", font=("Arial", 13, "bold"))
        self.status_label.pack(pady=10)

        self.progress_label = tk.Label(self.main_canvas, text="Step: 0 / 0", font=("Arial", 10))
        self.progress_label.pack()

        # Structural UI Window Toggles
        self.viz_btn = tk.Button(self.main_canvas, text="🎹 Open Visualizer", font=("Arial", 10, "bold"), bg="#9b59b6", fg="white", activebackground="#8e44ad", activeforeground="white", command=self.open_visualizer)
        self.viz_btn.pack(pady=8)

        self.roblox_btn = tk.Button(self.main_canvas, text="🎮 Roblox MIDI Connect", font=("Arial", 10, "bold"), bg="#e67e22", fg="white", activebackground="#d35400", activeforeground="white", command=self.open_roblox_connect)
        self.roblox_btn.pack(pady=8)

        self.btn_frame = tk.Frame(self.main_canvas)
        self.btn_frame.pack(side="bottom", pady=25)

        self.start_btn = tk.Button(self.btn_frame, text="START", bg="green", fg="white", width=10, font=("Arial", 9, "bold"), command=self.start_song)
        self.start_btn.pack(side="left", padx=15)

        self.skip_btn = tk.Button(self.btn_frame, text="SKIP STEP", bg="orange", fg="black", width=12, font=("Arial", 9, "bold"), command=self.trigger_skip)
        self.skip_btn.pack(side="left", padx=15)

        self.reset_btn = tk.Button(self.btn_frame, text="RESET", bg="red", fg="white", width=10, font=("Arial", 9, "bold"), command=self.reset_program)
        self.reset_btn.pack(side="left", padx=15)

        self.refresh_ports()
        self.load_settings()
        self.apply_theme_colors()

        self.global_listener_running = True
        self.midi_lock = threading.Lock()
        self.update_midi_ports()
        self.toggle_audio_port()
        
        self.listener_thread = threading.Thread(target=self.global_midi_listener, daemon=True)
        self.listener_thread.start()

        self.audio_thread = threading.Thread(target=self.delayed_audio_worker, daemon=True)
        self.audio_thread.start()

    def send_roblox_midi_keystroke(self, is_note_on, note_num, velocity):
        """Converts incoming physical piano key shifts into decoded numpad macro sequences."""
        if not self.roblox_connected.get():
            return
        try:
            pydirectinput.press(RobloxKeys.MULTIPLY)
            action_flag = 1 if is_note_on else 0
            to_send = [
                math.floor(note_num / 12),
                math.floor(note_num % 12),
                math.floor(velocity / 12),
                math.floor(velocity % 12),
                action_flag,
                0 
            ]
            for value in to_send:
                pydirectinput.press(ROBLOX_KEY_ARRAY[value])
        except Exception as e:
            print(f"Error casting keystroke injection: {e}")

    def send_roblox_cc_keystroke(self, control, value):
        """Converts MIDI Control Changes (like Sustain Pedal) into Roblox macro sequences."""
        if not self.roblox_connected.get() or not self.enable_pedal.get():
            return
        try:
            mapped_control = None
            if control == 64:  # Sustain Pedal
                mapped_control = 143
            
            if mapped_control is not None:
                pydirectinput.press(RobloxKeys.MULTIPLY)
                to_send = [
                    math.floor(mapped_control / 12),
                    math.floor(mapped_control % 12),
                    math.floor(value / 12),
                    math.floor(value % 12)
                ]
                for digit in to_send:
                    pydirectinput.press(ROBLOX_KEY_ARRAY[digit])
        except Exception as e:
            print(f"Error casting CC keystroke injection: {e}")

    def toggle_options(self):
        if self.options_expanded:
            self.options_drawer.pack_forget()
            self.options_toggle_btn.config(bg="#34495e", text="≡ Options Panel")
            self.options_expanded = False
        else:
            self.options_drawer.pack(fill="x", before=self.main_canvas)
            self.refresh_ports()
            self.options_toggle_btn.config(bg="#16a085", text="✕ Close Options")
            self.options_expanded = True

    def update_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top.get())

    def update_visualizer_on_top(self):
        if self.visualizer_window and tk.Toplevel.winfo_exists(self.visualizer_window.window):
            self.visualizer_window.window.attributes("-topmost", self.viz_always_on_top.get())

    def toggle_audio_port(self):
        with self.midi_lock:
            if self.enable_audio.get():
                if not self.hMidiOut:
                    try:
                        self.hMidiOut = ctypes.c_void_p()
                        ctypes.windll.winmm.midiOutOpen(ctypes.byref(self.hMidiOut), -1, 0, 0, 0)
                        ctypes.windll.winmm.midiOutShortMsg(self.hMidiOut, 0x0000C0)
                        self.apply_hardware_volume()
                    except Exception:
                        self.hMidiOut = None
            else:
                if self.hMidiOut:
                    try:
                        ctypes.windll.winmm.midiOutClose(self.hMidiOut)
                    except Exception: pass
                    self.hMidiOut = None

    def apply_hardware_volume(self):
        if not self.hMidiOut:
            return
        try:
            vol_factor = self.volume_level.get()
            if vol_factor > 100:
                hw_vol = 0xFFFF
            else:
                scaled = int((vol_factor / 100.0) * 0xFFFF)
                hw_vol = max(0, min(0xFFFF, scaled))
                
            packed_volume = hw_vol | (hw_vol << 16)
            ctypes.windll.winmm.midiOutSetVolume(self.hMidiOut, packed_volume)
        except Exception:
            pass

    def delayed_audio_worker(self):
        while self.global_listener_running:
            try:
                task = self.audio_queue.get(timeout=0.05)
                fire_time, msg_bytes = task
                
                wait_time = fire_time - time.time()
                if wait_time > 0:
                    time.sleep(wait_time)
                
                with self.midi_lock:
                    if self.hMidiOut:
                        ctypes.windll.winmm.midiOutShortMsg(self.hMidiOut, msg_bytes)
            except queue.Empty:
                pass
            except Exception:
                pass

    def cycle_theme(self):
        if self.theme_mode == "system":
            self.theme_mode = "dark"
        elif self.theme_mode == "dark":
            self.theme_mode = "light"
        else:
            self.theme_mode = "system"
        self.apply_theme_colors()

    def apply_theme_colors(self):
        effective_theme = self.theme_mode
        if effective_theme == "system":
            effective_theme = get_windows_system_theme()

        if effective_theme == "dark":
            bg_main = "#1e1e1e"
            fg_main = "#ffffff"
            fg_sub = "#aaaaaa"
            bg_drawer = "#2d2d2d"
            chk_select = "#3d3d3d"
        else:
            bg_main = "#f9f9f9"
            fg_main = "#000000"
            fg_sub = "gray"
            bg_drawer = "#ecf0f1"
            chk_select = "#ffffff"

        if self.theme_mode == "system":
            self.theme_btn.config(text="Theme: System Sync", bg="#3498db", fg="white")
        elif self.theme_mode == "dark":
            self.theme_btn.config(text="Theme: Forced Dark", bg="#f1c40f", fg="black")
        else:
            self.theme_btn.config(text="Theme: Forced Light", bg="#7f8c8d", fg="white")

        self.root.config(bg=bg_main)
        self.main_canvas.config(bg=bg_main)
        self.options_drawer.config(bg=bg_drawer)
        self.pins_frame.config(bg=bg_drawer)
        self.toggles_frame.config(bg=bg_drawer)
        self.sliders_row.config(bg=bg_drawer)
        self.btn_frame.config(bg=bg_main) 
        
        self.in_label.config(bg=bg_drawer, fg=fg_main)
        self.out_label.config(bg=bg_drawer, fg=fg_main)
        self.vol_label.config(bg=bg_drawer, fg=fg_main)
        self.weight_label.config(bg=bg_drawer, fg=fg_main)
        self.delay_label.config(bg=bg_drawer, fg=fg_main)
        self.colors_frame.config(bg=bg_drawer, fg=fg_main)
        
        self.top_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)
        self.viz_top_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)
        
        self.audio_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)
        self.weight_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)
        self.pedal_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)
        self.hw_lights_check.config(bg=bg_drawer, fg=fg_main, activebackground=bg_drawer, activeforeground=fg_main, selectcolor=chk_select)

        self.vol_slider.config(bg=bg_drawer, troughcolor=chk_select, fg=fg_main)
        self.weight_slider.config(bg=bg_drawer, troughcolor=chk_select, fg=fg_main)
        self.delay_slider.config(bg=bg_drawer, troughcolor=chk_select, fg=fg_main)
        
        self.file_label.config(bg=bg_main, fg=fg_sub)
        self.status_label.config(bg=bg_main, fg=fg_main)
        self.progress_label.config(bg=bg_main, fg=fg_main)

        set_window_title_bar_theme(self.root, effective_theme)

    def save_settings(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'theme_mode': self.theme_mode,
            'always_on_top': str(self.always_on_top.get()),
            'viz_always_on_top': str(self.viz_always_on_top.get()),
            'roblox_always_on_top': str(self.roblox_always_on_top.get()),
            'enable_audio': str(self.enable_audio.get()),
            'enable_weight': str(self.enable_weight.get()),
            'enable_pedal': str(self.enable_pedal.get()),
            'enable_hw_lights': str(self.enable_hw_lights.get()),
            'volume_level': str(self.volume_level.get()),
            'weight_level': str(self.weight_level.get()),
            'delay_level': str(self.delay_level.get()),
            'input_port': self.in_combo.get(),
            'output_port': self.out_combo.get(),
            'target_color': self.target_color_var.get(),
            'pressed_color': self.pressed_color_var.get(),
            'trail_color': self.trail_color_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")

    def load_settings(self):
        if not os.path.exists(CONFIG_FILE):
            return
        
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_FILE)
            if 'Settings' in config:
                self.theme_mode = config['Settings'].get('theme_mode', fallback="system")
                self.always_on_top.set(config['Settings'].getboolean('always_on_top', fallback=False))
                self.update_always_on_top()

                self.viz_always_on_top.set(config['Settings'].getboolean('viz_always_on_top', fallback=False))
                self.update_visualizer_on_top()

                self.roblox_always_on_top.set(config['Settings'].getboolean('roblox_always_on_top', fallback=False))

                self.enable_audio.set(config['Settings'].getboolean('enable_audio', fallback=True))
                self.enable_weight.set(config['Settings'].getboolean('enable_weight', fallback=True))
                self.enable_pedal.set(config['Settings'].getboolean('enable_pedal', fallback=True))
                self.enable_hw_lights.set(config['Settings'].getboolean('enable_hw_lights', fallback=True))

                self.volume_level.set(config['Settings'].getint('volume_level', fallback=100))
                self.weight_level.set(config['Settings'].getint('weight_level', fallback=100))
                self.delay_level.set(config['Settings'].getint('delay_level', fallback=0))
               
                saved_in = config['Settings'].get('input_port', fallback="")
                saved_out = config['Settings'].get('output_port', fallback="")
               
                if saved_in in self.in_combo['values']:
                    self.in_combo.set(saved_in)
                if saved_out in self.out_combo['values']:
                    self.out_combo.set(saved_out)
                    
                self.target_color_var.set(config['Settings'].get('target_color', fallback="Red"))
                self.pressed_color_var.set(config['Settings'].get('pressed_color', fallback="Purple"))
                self.trail_color_var.set(config['Settings'].get('trail_color', fallback="Lavender"))
        except Exception:
            pass 

    def browse_file(self):
        file_selected = filedialog.askopenfilename(filetypes=[("MIDI files", "*.mid;*.midi")])
        if file_selected:
            self.reset_program()
            self.midi_path = file_selected
            self.file_label.config(text=file_selected.split("/")[-1])
            try:
                self.steps = extract_notes_by_time(self.midi_path)
                self.progress_label.config(text=f"Step: 0 / {len(self.steps)}")
                self.status_label.config(text="Status: MIDI Loaded.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not parse MIDI:\n{e}")

    def refresh_ports(self):
        current_in = self.in_combo.get()
        current_out = self.out_combo.get()
        in_ports = mido.get_input_names()
        out_ports = mido.get_output_names()
       
        self.in_combo['values'] = in_ports if in_ports else ["No input device found"]
        self.out_combo['values'] = out_ports if out_ports else ["No output device found"]
       
        if current_in in self.in_combo['values']:
            self.in_combo.set(current_in)
        elif in_ports:
            self.in_combo.current(0)
           
        if current_out in self.out_combo['values']:
            self.out_combo.set(current_out)
        elif out_ports:
            self.out_combo.current(0)

    def update_midi_ports(self):
        with self.midi_lock:
            new_in = self.in_combo.get()
            new_out = self.out_combo.get()
            
            if new_in != self.current_in_name:
                if self.inport:
                    try: self.inport.close()
                    except Exception: pass
                    self.inport = None
                if new_in and "No input device" not in new_in:
                    try:
                        self.inport = mido.open_input(new_in)
                        self.current_in_name = new_in
                    except Exception:
                        self.current_in_name = None

            if new_out != self.current_out_name:
                if self.outport:
                    try: self.outport.close()
                    except Exception: pass
                    self.outport = None
                if new_out and "No output device" not in new_out:
                    try:
                        self.outport = mido.open_output(new_out)
                        self.current_out_name = new_out
                    except Exception:
                        self.current_out_name = None

    def global_midi_listener(self):
        pressed_notes = set()
        while self.global_listener_running:
            with self.midi_lock:
                if self.inport:
                    try:
                        for msg in self.inport.iter_pending():
                            if msg.type == 'note_on' and msg.velocity > 0:
                                pressed_notes.add(msg.note)
                                
                                self.send_roblox_midi_keystroke(True, msg.note, msg.velocity)
                                
                                if self.enable_weight.get():
                                    weight_scale = self.weight_level.get() / 100.0
                                    base_velocity = int(msg.velocity * weight_scale)
                                    base_velocity = max(1, min(127, base_velocity))
                                else:
                                    base_velocity = msg.velocity
                                    
                                if self.enable_audio.get() and self.hMidiOut:
                                    vol_percent = self.volume_level.get()
                                    vol_scale = vol_percent / 100.0
                                    final_vel = int(base_velocity * vol_scale)
                                    final_vel = max(1, min(127, final_vel))
                                    
                                    midi_msg = 0x90 | (msg.note << 8) | (final_vel << 16)
                                    fire_at = time.time() + (self.delay_level.get() / 1000.0)
                                    self.audio_queue.put((fire_at, midi_msg))
                                    
                            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                                if msg.note in pressed_notes:
                                    pressed_notes.remove(msg.note)
                                
                                self.send_roblox_midi_keystroke(False, msg.note, 0)
                                
                                if self.enable_audio.get() and self.hMidiOut:
                                    midi_msg = 0x80 | (msg.note << 8) | (0 << 16)
                                    fire_at = time.time() + (self.delay_level.get() / 1000.0)
                                    self.audio_queue.put((fire_at, midi_msg))

                            elif msg.type == 'control_change':
                                # Fire pedal parameters to Roblox when linked
                                self.send_roblox_cc_keystroke(msg.control, msg.value)

                                if self.enable_pedal.get() and self.enable_audio.get() and self.hMidiOut:
                                    midi_msg = 0xB0 | (msg.control << 8) | (msg.value << 16)
                                    fire_at = time.time() + (self.delay_level.get() / 1000.0)
                                    self.audio_queue.put((fire_at, midi_msg))
                                    
                    except Exception:
                        pass
            
            self.active_pressed = set(pressed_notes)
            time.sleep(0.005)

    def start_song(self):
        if not self.steps:
            messagebox.showwarning("Warning", "Please load a MIDI file first.")
            return
        if self.is_running:
            return
        
        self.is_running = True
        self.stop_playback.clear()
        self.skip_step.clear()
        self.status_label.config(text="Status: Playing...")
        
        self.playback_thread = threading.Thread(target=self.playback_worker, daemon=True)
        self.playback_thread.start()

    def playback_worker(self):
        for idx in range(self.current_step_idx, len(self.steps)):
            if self.stop_playback.is_set():
                break
                
            self.current_step_idx = idx
            notes_to_play = self.steps[idx]
            
            self.active_targets = set(notes_to_play)
            
            if self.enable_hw_lights.get():
                with self.midi_lock:
                    if self.outport:
                        for note in notes_to_play:
                            self.outport.send(mido.Message('note_on', note=note, velocity=1, channel=0))
                            
            self.root.after(0, lambda i=idx: self.progress_label.config(text=f"Step: {i+1} / {len(self.steps)}"))
            self.skip_step.clear()
            
            while not set(notes_to_play).issubset(self.active_pressed):
                if self.stop_playback.is_set() or self.skip_step.is_set():
                    break
                time.sleep(0.01)
                
            if self.enable_hw_lights.get():
                with self.midi_lock:
                    if self.outport:
                        for note in notes_to_play:
                            self.outport.send(mido.Message('note_off', note=note, velocity=0, channel=0))
                            
            time.sleep(0.15)
            
        self.active_targets.clear()
        self.is_running = False
        if not self.stop_playback.is_set():
            self.current_step_idx = 0
            self.root.after(0, lambda: self.status_label.config(text="Status: Finished! 🎉"))

    def trigger_skip(self):
        self.skip_step.set()

    def reset_program(self):
        self.stop_playback.set()
        self.skip_step.set()
        self.current_step_idx = 0
        self.active_targets.clear()
        self.status_label.config(text="Status: Ready")
        if self.steps:
            self.progress_label.config(text=f"Step: 0 / {len(self.steps)}")

    def open_visualizer(self):
        if not self.visualizer_window or not tk.Toplevel.winfo_exists(self.visualizer_window.window):
            self.visualizer_window = MidiVisualizer(self.root, self)
        self.visualizer_window.show()

    def open_roblox_connect(self):
        if not self.roblox_window_instance or not tk.Toplevel.winfo_exists(self.roblox_window_instance.window):
            self.roblox_window_instance = RobloxConnectWindow(self.root, self)
        self.roblox_window_instance.show()

if __name__ == "__main__":
    root = tk.Tk()
    app = MidiLearnerGUI(root)
    root.mainloop()