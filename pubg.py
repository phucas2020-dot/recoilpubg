import tkinter as tk
import threading
import time
import win32api
import win32con
import ctypes
import winreg
import math

class RecoilControl:
    # === BÙ VIÊN ĐẦU ===
    FIRST_BULLET_TIME   = 0.06   # 60ms đầu
    FIRST_BULLET_FACTOR = 2.2    # Hệ số bù viên đầu
    # ====================

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PUBG Recoil Control")
        self.root.geometry("420x560")
        self.root.resizable(False, False)

        # Thông số tối ưu cho sen 25, dọc 1.0, DPI 1600
        self.strength   = self.load_setting("Strength",   3.5)
        self.multiplier = self.load_setting("Multiplier", 1.5)
        self.rate       = self.load_setting("Rate",       8.0)
        self.t_cap      = self.load_setting("TCap",       0.6)
        self.running    = True
        self.fire_start_time = 0.0

        self._last_ui_update     = 0.0
        self._ui_update_interval = 0.10
        self._last_status        = ""
        self._last_info          = ""

        self._build_ui()
        threading.Thread(target=self.recoil_loop, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.exit)

    def calc_pull(self, elapsed: float) -> int:
        if elapsed < self.FIRST_BULLET_TIME:
            pull = self.strength * self.multiplier * self.FIRST_BULLET_FACTOR
            return max(0, round(pull))

        t_after = elapsed - self.FIRST_BULLET_TIME
        raw = self.strength * self.multiplier * math.log1p(t_after * self.rate)
        cap = self.strength * self.multiplier * math.log1p(self.t_cap * self.rate)
        return max(0, round(min(raw, cap)))

    def _build_ui(self):
        tk.Label(self.root, text="PUBG Recoil Control",
                 font=("Arial", 14, "bold")).pack(pady=5)

        for label, attr, from_, to, res, save_key, lbl_fmt in [
            ("Lực bù gốc:",   "strength",   0.0,  10.0, 0.1, "Strength",   "{:.1f}"),
            ("Hệ số nhân:",   "multiplier", 1.0,  10.0, 0.1, "Multiplier", "{:.1f}x"),
            ("Tốc độ tăng:",  "rate",       1.0,  20.0, 0.5, "Rate",       "{:.1f}"),
            ("Ổn định tại:",  "t_cap",      0.2,   3.0, 0.1, "TCap",       "{:.1f}s"),
        ]:
            frame = tk.Frame(self.root)
            frame.pack(pady=2)
            tk.Label(frame, text=label, width=13, anchor="w").pack(side=tk.LEFT)
            lbl_var = tk.Label(frame, text=lbl_fmt.format(getattr(self, attr)), width=6)
            def make_cmd(a=attr, sk=save_key, lv=lbl_var, fmt=lbl_fmt):
                def cmd(val):
                    v = float(val)
                    setattr(self, a, v)
                    lv.config(text=fmt.format(v))
                    self.save_setting(sk, v)
                    self._draw_curve()
                return cmd
            sl = tk.Scale(frame, from_=from_, to=to, resolution=res,
                          orient=tk.HORIZONTAL, length=180, command=make_cmd())
            sl.set(getattr(self, attr))
            sl.pack(side=tk.LEFT, padx=5)
            lbl_var.pack(side=tk.LEFT)
            setattr(self, f"slider_{attr}", sl)
            setattr(self, f"lbl_{attr}",   lbl_var)

        self.status = tk.Label(self.root, text="⏹ ĐANG CHỜ",
                               font=("Arial", 12, "bold"), fg="orange")
        self.status.pack(pady=4)
        self.info = tk.Label(self.root, text="Lực kéo: 0 | Thời gian: 0.00s",
                             font=("Arial", 10), fg="blue")
        self.info.pack(pady=2)

        tk.Label(self.root, text="Đường cong lực bù:", font=("Arial", 9)).pack()
        self.canvas = tk.Canvas(self.root, width=380, height=80, bg="#111111")
        self.canvas.pack(pady=4)
        self._draw_curve()

        tk.Label(self.root, text="🖱 GIỮ nút FORWARD + chuột trái").pack()
        tk.Label(self.root,
                 text="⌨️  +/-  lực  |  * /  hệ số  |  ↑↓  tốc độ  |  PgUp/PgDn  ổn định",
                 font=("Arial", 8)).pack()
        tk.Button(self.root, text="Thoát", command=self.exit,
                  bg="#f44336", fg="white", width=12).pack(pady=6)

        self.root.bind('<Key-plus>',       lambda e: self._adj("strength",    0.1, "Strength"))
        self.root.bind('<Key-equal>',      lambda e: self._adj("strength",    0.1, "Strength"))
        self.root.bind('<Key-minus>',      lambda e: self._adj("strength",   -0.1, "Strength"))
        self.root.bind('<Key-asterisk>',   lambda e: self._adj("multiplier",  0.1, "Multiplier"))
        self.root.bind('<Key-slash>',      lambda e: self._adj("multiplier", -0.1, "Multiplier"))
        self.root.bind('<Up>',             lambda e: self._adj("rate",        0.5, "Rate"))
        self.root.bind('<Down>',           lambda e: self._adj("rate",       -0.5, "Rate"))
        self.root.bind('<Prior>',          lambda e: self._adj("t_cap",       0.1, "TCap"))
        self.root.bind('<Next>',           lambda e: self._adj("t_cap",      -0.1, "TCap"))

    def _draw_curve(self):
        c = self.canvas
        c.delete("all")
        W, H, pad = 380, 80, 8
        max_t = 3.0

        pulls   = [self.calc_pull(i / 100 * max_t) for i in range(101)]
        max_pull = max(pulls) if max(pulls) > 0 else 1

        pts = []
        for i, p in enumerate(pulls):
            x = pad + (W - 2*pad) * i / 100
            y = H - pad - (H - 2*pad) * p / max_pull
            pts.extend([x, y])
        if len(pts) >= 4:
            c.create_line(*pts, fill="#FF8C00", width=2, smooth=True)

        cap_x = pad + (W - 2*pad) * min(self.t_cap + self.FIRST_BULLET_TIME, max_t) / max_t
        c.create_line(cap_x, pad, cap_x, H - pad, fill="#4488ff", dash=(3, 3))
        c.create_text(cap_x + 2, pad + 2, text=f"ổn định {self.t_cap:.1f}s",
                      fill="#4488ff", anchor="nw", font=("Arial", 7))

        c.create_text(W - pad, pad, text=f"max {max_pull}px",
                      fill="#FF8C00", anchor="ne", font=("Arial", 7))
        c.create_text(pad,     H - pad, text="0s",  fill="#555", anchor="sw", font=("Arial", 7))
        c.create_text(W - pad, H - pad, text="3s",  fill="#555", anchor="se", font=("Arial", 7))

    def _adj(self, attr, delta, save_key):
        lo_map = {"strength": 0.0, "multiplier": 1.0, "rate": 1.0, "t_cap": 0.2}
        hi_map = {"strength": 10.0, "multiplier": 10.0, "rate": 20.0, "t_cap": 3.0}
        v = round(max(lo_map[attr], min(hi_map[attr], getattr(self, attr) + delta)), 1)
        setattr(self, attr, v)
        getattr(self, f"slider_{attr}").set(v)
        fmt_map = {"strength": "{:.1f}", "multiplier": "{:.1f}x",
                   "rate": "{:.1f}", "t_cap": "{:.1f}s"}
        getattr(self, f"lbl_{attr}").config(text=fmt_map[attr].format(v))
        self.save_setting(save_key, v)
        self._draw_curve()

    def save_setting(self, key, value):
        try:
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\PUBG_Recoil_Control")
            winreg.SetValueEx(k, key, 0, winreg.REG_SZ, str(value))
            winreg.CloseKey(k)
        except: pass

    def load_setting(self, key, default):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\PUBG_Recoil_Control")
            v, _ = winreg.QueryValueEx(k, key)
            winreg.CloseKey(k)
            return float(v)
        except: return default

    def recoil_loop(self):
        FORWARD = 0x06
        LEFT    = 0x01
        t = time.perf_counter

        while self.running:
            now  = t()
            fwd  = bool(win32api.GetAsyncKeyState(FORWARD) & 0x8000)
            left = bool(win32api.GetAsyncKeyState(LEFT)    & 0x8000)

            if fwd and left:
                if self.fire_start_time == 0.0:
                    self.fire_start_time = now

                elapsed = now - self.fire_start_time
                pull    = self.calc_pull(elapsed)

                if pull > 0:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, pull, 0, 0)

                if now - self._last_ui_update >= self._ui_update_interval:
                    self._last_ui_update = now
                    status_txt = "▶ ĐANG GHÌM"
                    info_txt   = f"Lực kéo: {pull} | Thời gian: {elapsed:.2f}s"
                    if status_txt != self._last_status:
                        self._last_status = status_txt
                        self.root.after(0, lambda t=status_txt: self.status.config(text=t, fg="green"))
                    if info_txt != self._last_info:
                        self._last_info = info_txt
                        self.root.after(0, lambda t=info_txt: self.info.config(text=t))
            else:
                self.fire_start_time = 0.0
                if now - self._last_ui_update >= self._ui_update_interval:
                    self._last_ui_update = now
                    s = "⏸ GIỮ FORWARD + CLICK TRÁI" if fwd else "⏹ ĐANG CHỜ"
                    if s != self._last_status:
                        self._last_status = s
                        self.root.after(0, lambda t=s: self.status.config(text=t, fg="orange"))
                    if self._last_info != "Lực kéo: 0 | Thời gian: 0.00s":
                        self._last_info = "Lực kéo: 0 | Thời gian: 0.00s"
                        self.root.after(0, lambda: self.info.config(
                            text="Lực kéo: 0 | Thời gian: 0.00s"))

            target = now + 0.001
            time.sleep(max(0, target - t() - 0.0002))
            while t() < target:
                pass

    def exit(self):
        self.running = False
        try: self.root.quit()
        except: pass
        try: self.root.destroy()
        except: pass


if __name__ == "__main__":
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print("⚠️ Cần chạy với quyền Administrator!")
            input("Nhấn Enter để thoát..."); exit()
    except:
        print("⚠️ Lỗi kiểm tra admin."); input(); exit()

    try:
        import win32api, win32con
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
        print("Đã cài pywin32, chạy lại."); input(); exit()

    app = RecoilControl()
    app.root.mainloop()