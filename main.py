import customtkinter as ctk
from customtkinter import filedialog
from PIL import Image
import json
import os
import logging
import tkinter as tk
import sys
from screeninfo import get_monitors
import sounddevice as sd
import XInput
import winreg
import subprocess
import pystray
from PIL import Image
from tkinter import messagebox

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- LOGGER CONFIGURATION ---
logging.basicConfig(
    filename='app_debug.log', 
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("--- Application Started ---")

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(1000, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                       background="#2b2b2b", foreground="#ffffff", relief='solid', borderwidth=1,
                       font=("Arial", "9", "normal"), padx=5, pady=3)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

# --- MAIN APPLICATION ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PC-Console Switcher")
        self.iconbitmap(resource_path("icon.ico"))
        self.geometry("620x680")
        self.resizable(False, False)
        
        self.config_file = "config.json"
        self.config_data = self.load_config()
        
        self.mapping_target = None 
        self.mapping_combo_set = set()
        self.pc_display_combos = []
        
        self.current_state = "PC"
        self.is_switching = False 
        self.action_cooldown = False

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.tabview = ctk.CTkTabview(self, width=580, height=610)
        self.tabview.pack(padx=20, pady=10)

        self.tabview.add("1. Profiles & Audio")
        self.tabview.add("2. Controller & Power")
        self.tabview.add("3. Steam")

        self.btn_save_global = ctk.CTkButton(self, text="Save Settings", width=120, command=self.save_config_manual)
        self.btn_save_global.place(relx=0.95, rely=0.97, anchor="se")

        # --- TAB 1: PROFILES & AUDIO ---
        tab_1 = self.tabview.tab("1. Profiles & Audio")
        
        self.top_actions_frame = ctk.CTkFrame(tab_1, fg_color="transparent")
        self.top_actions_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        self.btn_refresh_hw = ctk.CTkButton(self.top_actions_frame, text="↻ Refresh", width=90, command=self.detect_hardware)
        self.btn_refresh_hw.pack(side="right", padx=(10, 0))
        
        self.btn_identify = ctk.CTkButton(self.top_actions_frame, text="Identify Screens", width=110, command=self.identify_monitors)
        self.btn_identify.pack(side="right")

        self.frame_console = ctk.CTkFrame(tab_1)
        self.frame_console.pack(fill="x", padx=10, pady=5)
        
        self.lbl_console_title = ctk.CTkLabel(self.frame_console, text="Console Mode Input", font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_console_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w", columnspan=2)

        self.lbl_tv_monitor = ctk.CTkLabel(self.frame_console, text="TV Display:")
        self.lbl_tv_monitor.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.combo_tv_monitor = ctk.CTkComboBox(self.frame_console, values=["Select..."], width=180)
        self.combo_tv_monitor.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self.combo_tv_monitor.set("Select...")

        self.lbl_tv_audio = ctk.CTkLabel(self.frame_console, text="TV Audio:")
        self.lbl_tv_audio.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="w")
        self.combo_tv_audio = ctk.CTkComboBox(self.frame_console, values=["Select..."], width=200)
        self.combo_tv_audio.grid(row=2, column=1, padx=10, pady=(5, 15), sticky="w")
        self.combo_tv_audio.set("Select...")

        self.frame_pc = ctk.CTkFrame(tab_1)
        self.frame_pc.pack(fill="x", padx=10, pady=10)
        
        self.lbl_pc_title = ctk.CTkLabel(self.frame_pc, text="PC Mode Input", font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_pc_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w", columnspan=2)

        self.lbl_pc_audio = ctk.CTkLabel(self.frame_pc, text="PC Audio:")
        self.lbl_pc_audio.grid(row=1, column=0, padx=20, pady=5, sticky="w")
        self.combo_pc_audio = ctk.CTkComboBox(self.frame_pc, values=["Select..."], width=200)
        self.combo_pc_audio.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        self.combo_pc_audio.set("Select...")

        self.displays_container = ctk.CTkFrame(self.frame_pc, fg_color="transparent")
        self.displays_container.grid(row=2, column=0, columnspan=3, sticky="ew")
        
        self.btn_add_display = ctk.CTkButton(self.frame_pc, text="(+) Add Display", width=100, fg_color="#2b2b2b", hover_color="#404040", command=self.add_pc_display)
        self.btn_add_display.grid(row=3, column=1, padx=10, pady=(5, 15), sticky="w")

        self.frame_hp = ctk.CTkFrame(tab_1)
        self.frame_hp.pack(fill="x", padx=10, pady=5)
        
        self.lbl_hp_title = ctk.CTkLabel(self.frame_hp, text="Headphones Input (For Console Mode Switch)", font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_hp_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w", columnspan=2)

        self.lbl_hp_audio = ctk.CTkLabel(self.frame_hp, text="Audio:")
        self.lbl_hp_audio.grid(row=1, column=0, padx=20, pady=(5, 15), sticky="w")
        self.combo_hp_audio = ctk.CTkComboBox(self.frame_hp, values=["Select..."], width=200)
        self.combo_hp_audio.grid(row=1, column=1, padx=10, pady=(5, 15), sticky="w")
        self.combo_hp_audio.set("Select...")

        # --- TAB 2: CONTROLLER & POWER ---
        tab_2 = self.tabview.tab("2. Controller & Power")
        
        self.controller_select_frame = ctk.CTkFrame(tab_2, fg_color="transparent")
        self.controller_select_frame.pack(fill="x", padx=20, pady=(10, 0))
        
        self.lbl_controller_select = ctk.CTkLabel(self.controller_select_frame, text="Select Controller:")
        self.lbl_controller_select.pack(side="left", padx=(0, 10))
        
        self.combo_controller = ctk.CTkComboBox(self.controller_select_frame, values=["Select..."], command=self.on_controller_change, width=150)
        self.combo_controller.pack(side="left", fill="x", expand=True)
        self.combo_controller.set("Select...")
        
        self.btn_refresh_ctrl = ctk.CTkButton(self.controller_select_frame, text="↻ Refresh", width=70, command=self.refresh_controllers)
        self.btn_refresh_ctrl.pack(side="left", padx=(10, 0))

        self.chk_power = ctk.CTkSwitch(tab_2, text="Enable USB adapter to wake up PC")
        self.chk_power.pack(pady=(15, 10), anchor="w", padx=20)

        self.btn_shortcut_console = ctk.CTkButton(tab_2, text="Switch Console/PC Mode: [ UNMAPPED ]", fg_color="#333333", border_width=1, command=lambda: self.start_mapping("console"))
        self.btn_shortcut_console.pack(pady=5, fill="x", padx=20)
        
        self.btn_shortcut_audio = ctk.CTkButton(tab_2, text="Switch to Headphones: [ UNMAPPED ]", fg_color="#333333", border_width=1, command=lambda: self.start_mapping("audio"))
        self.btn_shortcut_audio.pack(pady=5, fill="x", padx=20)

        self.lbl_active_controller_name = ctk.CTkLabel(tab_2, text="Active: None", font=ctk.CTkFont(weight="bold", size=12), text_color="gray")
        self.lbl_active_controller_name.pack(pady=(15, 0))

        self.controller_frame = ctk.CTkFrame(tab_2, fg_color="transparent")
        self.controller_frame.pack(pady=5, fill="both", expand=True)

        try:
            img_path = resource_path("controller.png")
            ctrl_image = ctk.CTkImage(light_image=Image.open(img_path), size=(200, 200))
            self.lbl_controller_img = ctk.CTkLabel(self.controller_frame, text="", image=ctrl_image)
        except Exception:
            self.lbl_controller_img = ctk.CTkLabel(self.controller_frame, text="[No image]", width=200, height=200, fg_color="#222222")
            
        self.lbl_controller_img.pack(side="left", padx=(40, 20))

        self.lbl_tech_value = ctk.CTkLabel(self.controller_frame, text="Last Input: None", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00ffcc")
        self.lbl_tech_value.pack(side="left", padx=10)

        # --- TAB 3: STEAM ---
        tab_3 = self.tabview.tab("3. Steam")
        
        self.lbl_steam_path = ctk.CTkLabel(tab_3, text="steam.exe Path:")
        self.lbl_steam_path.pack(pady=(20,5), anchor="w", padx=20)
        
        self.steam_path_frame = ctk.CTkFrame(tab_3, fg_color="transparent")
        self.steam_path_frame.pack(pady=5, padx=20, anchor="w", fill="x")
        
        self.entry_steam_path = ctk.CTkEntry(self.steam_path_frame)
        self.entry_steam_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.btn_browse = ctk.CTkButton(self.steam_path_frame, text="Browse...", width=80, command=self.browse_steam_path)
        self.btn_browse.pack(side="left")

        self.chk_offline_mode = ctk.CTkCheckBox(tab_3, text="Start Steam in Offline Mode (Prevents family library conflicts)")
        self.chk_offline_mode.pack(pady=20, anchor="w", padx=20)
        
        self.chk_startup = ctk.CTkCheckBox(tab_3, text="Run PC-Console Mode Switcher program at Windows startup (Background)")
        self.chk_startup.pack(pady=(10, 20), anchor="w", padx=20)

        # --- INITIALIZATION ---
        self.detect_hardware()
        self.apply_config_to_ui()
        self.poll_controller()

        if not self.pc_display_combos:
            self.add_pc_display()

    # --- NIRCMD HELPERS ---
    def set_default_audio(self, device_name):
        if not device_name or device_name == "Select...": return
        
        clean_name = device_name.split(" (")[0].strip()
        
        nircmd_path = resource_path("nircmd.exe")
        
        if os.path.exists(nircmd_path):
            logging.info(f"Probando NirCmd con nombre exacto: {clean_name}")
            
            cmd = [nircmd_path, "setdefaultsounddevice", clean_name, "1"]
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.run(f'"{nircmd_path}" setdefaultsounddevice "{clean_name}" 1', shell=True)
            subprocess.run(f'"{nircmd_path}" setdefaultsounddevice "{clean_name}" 2', shell=True)
            logging.info("Comandos de audio enviados.")
        else:
            logging.error(f"nircmd.exe no encontrado en {nircmd_path}")

    def set_primary_display(self, display_name):
        if not display_name or display_name == "Select...": return
        
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        nircmd_path = resource_path("nircmd.exe") 
        
        if os.path.exists(nircmd_path):
            logging.info(f"Setting primary display to: {display_name}")
            subprocess.run([nircmd_path, "setprimarydisplay", display_name], creationflags=subprocess.CREATE_NO_WINDOW)

    def set_cursor_visibility(self, visible):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        nircmd_path = os.path.join(base_path, "nircmd.exe")
        
        if os.path.exists(nircmd_path):
            if visible:
                subprocess.run([nircmd_path, "setcursor", "0", "0"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.run([nircmd_path, "setcursor", "5000", "5000"], creationflags=subprocess.CREATE_NO_WINDOW)
    
    def show_status_overlay(self, message):
        overlay = tk.Toplevel(self)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="#1e1e1e")
        
        w, h = 600, 150
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        overlay.geometry(f"{w}x{h}+{x}+{y}")
        
        lbl = tk.Label(overlay, text=message, font=("Arial", 30, "bold"), bg="#1e1e1e", fg="#00ffcc")
        lbl.pack(expand=True)
        
        overlay.update() 
        overlay.after(2000, overlay.destroy)

    def trigger_mode_switch(self):
        if self.is_switching: return
        self.is_switching = True
        
        if self.current_state == "PC":
            logging.info(">>> SWITCHING TO CONSOLE MODE <<<")
            self.show_status_overlay("Switching to Console Mode...")
            self.update() # Asegura que la UI dibuje el cartel YA
            subprocess.run(["displayswitch.exe", "/external"], creationflags=subprocess.CREATE_NO_WINDOW)
            self.after(5000, self.finish_console_switch)
        else:
            logging.info(">>> SWITCHING TO PC MODE <<<")
            self.show_status_overlay("Switching to PC Mode...")
            self.update()
            subprocess.run(["displayswitch.exe", "/extend"], creationflags=subprocess.CREATE_NO_WINDOW)
            self.after(5000, self.finish_pc_switch)

    def finish_console_switch(self):
        tv_monitor = self.config_data.get("tv_monitor", "")
        self.set_primary_display(tv_monitor)

        tv_audio = self.config_data.get("tv_audio", "")
        self.set_default_audio(tv_audio)
        
        self.set_cursor_visibility(False)
        
        steam_path = self.config_data.get("steam_path", "")
        offline = self.config_data.get("steam_offline", False)
        
        try:
            if offline and os.path.exists(steam_path):
                subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], creationflags=subprocess.CREATE_NO_WINDOW)
                self.after(2000, lambda: subprocess.Popen([steam_path, "-offline", "-tenfoot"]))
            else:
                os.startfile("steam://open/bigpicture")
        except Exception as e:
            logging.error(f"Error launching Steam: {e}")
            
        self.current_state = "CONSOLE"
        self.is_switching = False

    def finish_pc_switch(self):
        pc_displays = self.config_data.get("pc_displays", [])
        if pc_displays:
            self.set_primary_display(pc_displays[0])

        pc_audio = self.config_data.get("pc_audio", "")
        self.set_default_audio(pc_audio)
        
        self.set_cursor_visibility(True)
        
        try:
            os.startfile("steam://close/bigpicture")
        except Exception as e:
            logging.error(f"Error cerrando Steam Big Picture: {e}")
        
        self.current_state = "PC"
        self.is_switching = False

    def trigger_headphones_switch(self):
        if not hasattr(self, 'audio_state'):
            self.audio_state = 'TV' 
        
        tv_audio = self.config_data.get("tv_audio", "")
        hp_audio = self.config_data.get("hp_audio", "")
        
        self.show_status_overlay("Switching TV/Headphones Audio...")
        if self.audio_state == 'TV':
            logging.info(">>> SWITCHING TO HEADPHONES <<<")
            self.set_default_audio(hp_audio)
            self.audio_state = 'HEADPHONES'
        else:
            logging.info(">>> SWITCHING TO TV AUDIO <<<")
            self.set_default_audio(tv_audio)
            self.audio_state = 'TV'

    def add_pc_display(self):
        if len(self.pc_display_combos) >= 4: return
        row_frame = ctk.CTkFrame(self.displays_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        lbl = ctk.CTkLabel(row_frame, text="Display:", width=110, anchor="w")
        lbl.pack(side="left", padx=(20, 10))
        combo = ctk.CTkComboBox(row_frame, values=["Select..."], width=180)
        combo.pack(side="left", padx=10)
        combo.set("Select...")
        self.pc_display_combos.append(combo)
        btn_remove = ctk.CTkButton(row_frame, text="X", width=30, fg_color="#8b0000", hover_color="#5a0000",
                                   command=lambda f=row_frame, c=combo: self.remove_pc_display(f, c))
        btn_remove.pack(side="left", padx=5)
        if hasattr(self, 'last_scanned_monitors') and self.last_scanned_monitors:
            combo.configure(values=self.last_scanned_monitors)
        self.relabel_pc_displays()

    def remove_pc_display(self, frame_to_destroy, combo_to_remove):
        frame_to_destroy.destroy()
        if combo_to_remove in self.pc_display_combos:
            self.pc_display_combos.remove(combo_to_remove)
        self.relabel_pc_displays()

    def relabel_pc_displays(self):
        for i, frame in enumerate(self.displays_container.winfo_children()):
            for widget in frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    if i == 0:
                        widget.configure(text="Display 1 (Main):")
                    else:
                        widget.configure(text=f"Display {i + 1}:")
                    break

    def browse_steam_path(self):
        file_path = filedialog.askopenfilename(title="Select steam.exe", filetypes=[("Executable Files", "*.exe")])
        if file_path:
            self.entry_steam_path.delete(0, "end")
            self.entry_steam_path.insert(0, os.path.normpath(file_path))

    def refresh_controllers(self):
        try:
            connected = XInput.get_connected()
            controllers = [f"Controller {i + 1}" for i in range(4) if connected[i]]
            if controllers:
                self.combo_controller.configure(values=controllers)
                if self.combo_controller.get() not in controllers:
                    self.combo_controller.set(controllers[0])
                    self.on_controller_change(controllers[0])
            else:
                self.combo_controller.configure(values=["No controller detected"])
                self.combo_controller.set("No controller detected")
                self.on_controller_change("No controller detected")
        except Exception as e:
            logging.error(f"Error refreshing controllers: {e}")

    def start_mapping(self, target):
        self.mapping_target = target
        self.mapping_combo_set.clear()
        if target == "console":
            self.btn_shortcut_console.configure(text="Switch Console/PC Mode: [ HOLD BUTTONS ]", fg_color="#1f538d")
        elif target == "audio":
            self.btn_shortcut_audio.configure(text="Switch to Headphones: [ HOLD BUTTONS ]", fg_color="#1f538d")

    def detect_hardware(self):
        try:
            monitors = [m.name for m in get_monitors() if m.name]
            if monitors:
                self.last_scanned_monitors = monitors
                self.combo_tv_monitor.configure(values=monitors)
                for combo in self.pc_display_combos:
                    combo.configure(values=monitors)
        except Exception as e:
            logging.error(f"Error detecting monitors: {e}")

        try:
            audio_devices = []
            for d in sd.query_devices():
                if d['max_output_channels'] > 0:
                    clean_name = d['name'].strip()
                    if "Microsoft Sound Mapper" not in clean_name and "Primary Sound Capture Driver" not in clean_name:
                        if clean_name not in audio_devices:
                            audio_devices.append(clean_name)
            if audio_devices:
                self.combo_tv_audio.configure(values=audio_devices)
                self.combo_pc_audio.configure(values=audio_devices)
                self.combo_hp_audio.configure(values=audio_devices)
        except Exception as e:
            logging.error(f"Error detecting audio: {e}")
            
        self.refresh_controllers()

    def on_controller_change(self, choice):
        if choice != "No controller detected" and choice != "Select...":
            self.lbl_active_controller_name.configure(text=f"Active: {choice}", text_color="white")
        else:
            self.lbl_active_controller_name.configure(text="Active: None", text_color="gray")

    def reset_cooldown(self):
        self.action_cooldown = False

    def poll_controller(self):
        try:
            selected = self.combo_controller.get()

            if selected == "No controller detected" or selected == "Select...":
                connected = XInput.get_connected()
                for i in range(4):
                    if connected[i]:
                        new_ctrl = f"Controller {i + 1}"
                        self.combo_controller.set(new_ctrl)
                        self.on_controller_change(new_ctrl)
                        selected = new_ctrl
                        break

            if selected.startswith("Controller"):
                idx = int(selected.split(" ")[1]) - 1
                if XInput.get_connected()[idx]:
                    
                    state = XInput.get_state(idx)
                    buttons = XInput.get_button_values(state)
                    pressed_buttons = [btn for btn, val in buttons.items() if val]
                    
                    triggers = XInput.get_trigger_values(state)
                    if triggers[0] > 0.5: pressed_buttons.append("LT")
                    if triggers[1] > 0.5: pressed_buttons.append("RT")

                    if pressed_buttons:
                        live_str = " + ".join(pressed_buttons)
                        self.lbl_tech_value.configure(text=f"Last Input: {live_str}")
                    else:
                        self.lbl_tech_value.configure(text="Last Input: None")

                    if self.mapping_target:
                        if pressed_buttons:
                            for p in pressed_buttons:
                                self.mapping_combo_set.add(p)
                            
                            current_build = " + ".join(sorted(list(self.mapping_combo_set)))
                            if self.mapping_target == "console":
                                self.btn_shortcut_console.configure(text=f"Switch Console/PC Mode: [ {current_build} ]")
                            elif self.mapping_target == "audio":
                                self.btn_shortcut_audio.configure(text=f"Switch to Headphones: [ {current_build} ]")
                        else:
                            if len(self.mapping_combo_set) > 0:
                                final_combo = " + ".join(sorted(list(self.mapping_combo_set)))
                                self.config_data[f"shortcut_{self.mapping_target}"] = final_combo
                                
                                if self.mapping_target == "console":
                                    self.btn_shortcut_console.configure(text=f"Switch Console/PC Mode: [ {final_combo} ]", fg_color="#333333")
                                elif self.mapping_target == "audio":
                                    self.btn_shortcut_audio.configure(text=f"Switch to Headphones: [ {final_combo} ]", fg_color="#333333")
                                
                                self.mapping_target = None
                                self.mapping_combo_set.clear()
                    
                    elif pressed_buttons and not self.mapping_target:
                        current_combo = " + ".join(sorted(pressed_buttons))
                        
                        saved_console = self.config_data.get("shortcut_console", "")
                        saved_audio = self.config_data.get("shortcut_audio", "")
                        
                        if current_combo == saved_console and current_combo != "":
                            if not self.action_cooldown:
                                self.action_cooldown = True
                                self.trigger_mode_switch()
                                self.after(5000, self.reset_cooldown)
                        
                        elif current_combo == saved_audio and current_combo != "":
                            if not self.action_cooldown:
                                self.action_cooldown = True
                                self.trigger_headphones_switch()
                                self.after(1000, self.reset_cooldown)

        except Exception:
            pass
        self.after(50, self.poll_controller)

    def identify_monitors(self):
        try:
            for index, m in enumerate(get_monitors()):
                overlay = tk.Toplevel(self)
                overlay.overrideredirect(True)
                overlay.attributes("-topmost", True)
                overlay.configure(bg="#1e1e1e")
                
                box_size = 400
                pos_x = m.x + (m.width // 2) - (box_size // 2)
                pos_y = m.y + (m.height // 2) - (box_size // 2)
                overlay.geometry(f"{box_size}x{box_size}+{pos_x}+{pos_y}")
                
                tk.Label(overlay, text=str(index + 1), font=("Arial", 150, "bold"), bg="#1e1e1e", fg="#00ffcc").pack(expand=True)
                tk.Label(overlay, text=m.name or f"Display {index + 1}", font=("Arial", 20, "bold"), bg="#1e1e1e", fg="white").pack(pady=20)
                
                overlay.after(3000, overlay.destroy)
        except Exception as e:
            logging.error(f"Error Identify Monitors: {e}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error reading config.json: {e}")
        return {}

    def apply_config_to_ui(self):
        if self.config_data.get("wake_pc", True): self.chk_power.select()
        else: self.chk_power.deselect()
        if self.config_data.get("steam_offline", False): self.chk_offline_mode.select()
        if self.config_data.get("run_startup", False): self.chk_startup.select()

        saved_pc_displays = self.config_data.get("pc_displays", [])
        if saved_pc_displays:
            for combo in self.pc_display_combos[:]:
                self.remove_pc_display(combo.master, combo)
            for val in saved_pc_displays:
                self.add_pc_display()
                self.pc_display_combos[-1].set(val)

        # 3. Carga de Combos estándar
        for combo, key in [
            (self.combo_tv_monitor, "tv_monitor"),
            (self.combo_tv_audio, "tv_audio"),
            (self.combo_pc_audio, "pc_audio"),
            (self.combo_hp_audio, "hp_audio"),
            (self.combo_controller, "master_controller")
        ]:
            val = self.config_data.get(key, "Select...")
            combo.set(val)
            if key == "master_controller": self.on_controller_change(val)

        # 4. Steam path y Mapeos
        self.entry_steam_path.insert(0, self.config_data.get("steam_path", "C:\\Program Files (x86)\\Steam\\steam.exe"))
        
        console_map = self.config_data.get("shortcut_console", "UNMAPPED")
        self.btn_shortcut_console.configure(text=f"Switch Console/PC Mode: [ {console_map} ]")
        
        audio_map = self.config_data.get("shortcut_audio", "UNMAPPED")
        self.btn_shortcut_audio.configure(text=f"Switch to Headphones: [ {audio_map} ]")
        
    def set_windows_startup(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PCConsoleSwitcher"
        
        executable_path = os.path.abspath(sys.executable) 
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{executable_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            logging.error(f"Failed to modify Windows registry for startup: {e}")

    def set_usb_wake(self, enable):
        keywords = ["Xbox", "Bluetooth", "Wireless", "Controller", "XINPUT", "Receiver"]
        try:
            result = subprocess.run(['powercfg', '-devicequery', 'wake_programmable'], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            devices = result.stdout.splitlines()
            for dev in devices:
                if any(kw.lower() in dev.lower() for kw in keywords):
                    if enable:
                        subprocess.run(['powercfg', '-deviceenablewake', f"{dev}"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    else:
                        subprocess.run(['powercfg', '-devicedisablewake', f"{dev}"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            logging.error(f"Error configuring powercfg for USB Wake: {e}")

    def save_config_manual(self):
        self.btn_save_global.configure(text="Saved!", fg_color="#2b8a3e")
        self.save_all_data()
        self.after(2000, lambda: self.btn_save_global.configure(text="Save Settings", fg_color=["#3a7ebf", "#1f538d"]))

    def save_all_data(self):
        try:
            self.config_data["wake_pc"] = bool(self.chk_power.get())
            self.set_usb_wake(bool(self.chk_power.get()))
            
            self.config_data["steam_offline"] = bool(self.chk_offline_mode.get())
            run_at_startup = bool(self.chk_startup.get())
            self.config_data["run_startup"] = run_at_startup
            self.set_windows_startup(run_at_startup)

            self.config_data["steam_path"] = self.entry_steam_path.get()
            self.config_data["tv_monitor"] = self.combo_tv_monitor.get()
            self.config_data["tv_audio"] = self.combo_tv_audio.get()
            self.config_data["pc_audio"] = self.combo_pc_audio.get()
            self.config_data["hp_audio"] = self.combo_hp_audio.get()
            self.config_data["master_controller"] = self.combo_controller.get()
            
            pc_displays = [combo.get() for combo in self.pc_display_combos if combo.get() != "Select..."]
            self.config_data["pc_displays"] = pc_displays
            
            with open(self.config_file, "w") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving data: {e}")
            
    def on_closing(self):
        if not hasattr(self, 'already_warned'):
            messagebox.showinfo("PC-Console Switcher", 
                                "The program will continue running in the system tray to keep your shortcuts active.")
            self.already_warned = True
        
        self.withdraw()
        self.create_tray_icon()

    def create_tray_icon(self):
        try:
            image = Image.open(resource_path("icon.ico"))
        except Exception:
            image = Image.new('RGB', (64, 64), color = (73, 109, 137))
        menu = pystray.Menu(
            pystray.MenuItem("Show Interface", self.show_window),
            pystray.MenuItem("Exit", self.force_exit)
        )
        self.tray_icon = pystray.Icon("PCConsoleSwitcher", image, "PC-Console Switcher", menu)
        
        import threading
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon, item):
        self.tray_icon.stop()
        self.deiconify() 

    def force_exit(self, icon, item):
        self.tray_icon.stop()
        self.save_all_data()
        self.destroy()
        sys.exit()
        
    

if __name__ == "__main__":
    import ctypes
    mutex_name = "Global\\PCConsoleSwitcherMutex"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    
    if last_error == 183: # 183 significa ERROR_ALREADY_EXISTS en Windows
        logging.warning("Application already running.")
        sys.exit(0)

    try:
        app = App()
        app.mainloop()
    except Exception as e:
        logging.critical(f"Fatal application crash: {e}", exc_info=True)