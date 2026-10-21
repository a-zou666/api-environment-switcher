#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 环境切换器 — 图形界面

双击即可管理多套 API Key / 网关，一键切换 Codex 的配置。
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apictl_core as core

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(BASE, "app.ico")

# ---------------------------------------------------------------- 配色
BG = "#f5f6f8"           # 页面底色
CARD = "#ffffff"
BORDER = "#e2e6ee"
BTN_BORDER = "#d7dde8"
BORDER_HOVER = "#c6d1e8"
FIELD = "#fbfcfe"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_SOFT = "#eef3ff"
TEXT = "#141a22"
MUTED = "#5d6a7d"
FAINT = "#9aa4b4"
GREEN = "#0f9d58"
GREEN_SOFT = "#e8f8ef"
RED = "#d92d20"
RED_SOFT = "#fdeeeb"
AMBER = "#b45309"
AMBER_SOFT = "#fdf5e6"
CHIP = "#f3f5f9"
CHIP_FG = "#4d5a70"
DOT_OFF = "#cbd3df"

S = 1.0  # DPI 缩放系数
WATCH_MS = 1500  # 客户端运行状态刷新间隔（毫秒）
FNT = "Microsoft YaHei UI"

_MUTEX = None  # 单实例锁，进程退出前必须一直被引用


def fnt(size, bold=False):
    return (FNT, size, "bold") if bold else (FNT, size)


def ensure_single_instance():
    """只允许跑一个实例；已有的会被叫到前台，当前进程直接退出"""
    global _MUTEX
    if os.name != "nt":
        return True
    try:
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        _MUTEX = k32.CreateMutexW(None, 0, "Local\\ApiEnvSwitcher.SingleInstance")
        if not _MUTEX:
            return True
        if ctypes.get_last_error() != 183:  # ERROR_ALREADY_EXISTS
            return True
        try:
            from tray_win import notify_existing

            notify_existing()
        except Exception:
            pass
        return False
    except Exception:
        return True


def px(n):
    return max(1, int(round(n * S)))


def enable_dpi():
    """在创建窗口前调用：声明 DPI 感知并按实际 DPI 计算缩放系数"""
    global S
    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except Exception:
            dpi = ctypes.windll.user32.GetDeviceCaps(ctypes.windll.gdi32.CreateDCW("DISPLAY", None, None, None), 90)
        if dpi and 72 <= dpi <= 400:
            S = dpi / 96.0
    except Exception:
        S = 1.0


def pick_font(root):
    global FNT
    fams = set(tkfont.families(root))
    for f in ("Microsoft YaHei UI", "微软雅黑", "Microsoft YaHei", "PingFang SC", "Segoe UI"):
        if f in fams:
            FNT = f
            return f
    return FNT


def init_ttk(root):
    """统一 ttk 控件（下拉框）的观感，靠近自绘按钮"""
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure(
        "Jz.TCombobox",
        fieldbackground=FIELD, background=CARD, foreground=TEXT,
        arrowcolor=MUTED, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD,
        selectbackground=FIELD, selectforeground=TEXT,
        padding=(px(8), px(5)),
    )
    st.map(
        "Jz.TCombobox",
        fieldbackground=[("readonly", FIELD), ("disabled", BG)],
        bordercolor=[("focus", ACCENT), ("hover", BORDER_HOVER)],
        arrowcolor=[("active", ACCENT)],
        selectbackground=[("readonly", FIELD)],
        selectforeground=[("readonly", TEXT)],
    )
    root.option_add("*TCombobox*Listbox.font", fnt(10))
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_SOFT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT)


# ---------------------------------------------------------------- 自绘控件
def round_poly(c, x1, y1, x2, y2, r, **kw):
    """在 canvas 上画圆角矩形（圆弧采样折线，避免 smooth 样条溢出）"""
    import math

    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    if r <= 0.5:
        return c.create_rectangle(x1, y1, x2, y2, **kw)
    n = 6
    pts = []
    for cx, cy, a0 in (
        (x2 - r, y1 + r, -90.0),   # 右上
        (x2 - r, y2 - r, 0.0),     # 右下
        (x1 + r, y2 - r, 90.0),    # 左下
        (x1 + r, y1 + r, 180.0),   # 左上
    ):
        for i in range(n + 1):
            a = math.radians(a0 + 90.0 * i / n)
            pts.extend((cx + r * math.cos(a), cy + r * math.sin(a)))
    return c.create_polygon(pts, **kw)


KINDS = {
    "primary": dict(fill=ACCENT, fg="#ffffff", hover=ACCENT_HOVER, border=""),
    "ghost": dict(fill=CARD, fg="#3f4a5a", hover="#f2f5fa", border=BTN_BORDER, hover_fg=TEXT),
    "soft": dict(fill=ACCENT_SOFT, fg=ACCENT, hover="#e2ebff", border="#d3e1ff"),
    "danger": dict(fill=RED_SOFT, fg=RED, hover="#fbdcd8", border=""),
    "del": dict(fill="", fg=FAINT, hover=RED_SOFT, border="", hover_fg=RED),
    "chip": dict(fill=CHIP, fg=CHIP_FG, hover=CHIP, border=""),
    "chip_out": dict(fill=CARD, fg=MUTED, hover="#f2f5fa", border=BTN_BORDER),
    "chip_warn": dict(fill=AMBER_SOFT, fg=AMBER, hover=AMBER_SOFT, border=""),
    "pill": dict(fill=ACCENT_SOFT, fg=ACCENT, hover=ACCENT_SOFT, border="#d3e1ff"),
}


class RoundButton(tk.Canvas):
    """圆角按钮 / 标签胶囊：比 tk.Button 干净，且高度可按字体算准"""

    def __init__(self, master, text="", command=None, kind="ghost", size=9, bold=False,
                 padx=14, pady=6, radius=8, bg=None):
        self._f = tkfont.Font(family=FNT, size=size, weight=("bold" if bold else "normal"))
        self._text = text
        self._kind = kind
        self._cmd = command
        self._radius = radius
        self._hover = False
        self._disabled = False
        self._padx = px(padx)
        self._bw = self._f.measure(text) + self._padx * 2
        self._bh = max(px(26), self._f.metrics("linespace") + px(pady) * 2 + px(2))
        try:
            pbg = bg or master.cget("bg")
        except Exception:
            pbg = BG
        super().__init__(master, width=self._bw, height=self._bh, bg=pbg,
                         highlightthickness=0, bd=0, takefocus=0)
        self._draw()
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._click)
        if command:
            try:
                self.config(cursor="hand2")
            except Exception:
                pass

    # -- 绘制
    def _draw(self):
        self.delete("all")
        w, h = self._bw, self._bh
        k = KINDS.get(self._kind, KINDS["ghost"])
        live = self._hover and not self._disabled and bool(self._cmd)
        base = self.cget("bg")
        fill = (k.get("hover") if live else k["fill"]) or base
        fg = (k.get("hover_fg", k["fg"]) if live else k["fg"])
        if self._disabled:
            fg = "#b7bfcc"
        r = h / 2 if self._radius >= 90 else min(px(self._radius), h / 2)
        round_poly(self, 1, 1, w - 1, h - 1, r,
                   fill=fill, outline=(k.get("border") or ""), width=1)
        self.create_text(w / 2, h / 2 + 0.5, text=self._text, font=self._f, fill=fg)

    def _enter(self, _=None):
        if self._cmd and not self._disabled:
            self._hover = True
            self._draw()

    def _leave(self, _=None):
        if self._hover:
            self._hover = False
            self._draw()

    def _click(self, _=None):
        if self._disabled or not self._cmd:
            return
        self._hover = False
        self._draw()
        self._cmd()

    # -- 兼容 tk.Button 的用法
    def _set_text(self, text):
        self._text = text
        self._bw = self._f.measure(text) + self._padx * 2
        self.configure(width=self._w)
        self._draw()

    def set_kind(self, kind):
        self._kind = kind
        self._draw()

    def config(self, cnf=None, **kw):
        if "text" in kw:
            self._set_text(kw.pop("text"))
        if "kind" in kw:
            self._kind = kw.pop("kind")
        if "command" in kw:
            self._cmd = kw.pop("command")
        if "state" in kw:
            st = kw.pop("state")
            self._disabled = st == "disabled"
            try:
                self.config(cursor="" if self._disabled else ("hand2" if self._cmd else ""))
            except Exception:
                pass
            self._hover = False
            self._draw()
        if kw or cnf:
            super().config(cnf, **kw)

    configure = config


def button(parent, text, cmd, kind="ghost", font=None, padx=14, pady=6):
    size, bold = 9, False
    if font:
        try:
            size = int(font[1])
            bold = len(font) > 2 and "bold" in str(font[2])
        except Exception:
            pass
    return RoundButton(parent, text, cmd, kind=kind, size=size, bold=bold, padx=padx, pady=pady)


def dot(parent, color, d=8):
    c = tk.Canvas(parent, width=px(d), height=px(d), bg=parent.cget("bg"),
                  highlightthickness=0, bd=0)
    c.create_oval(px(1), px(1), px(d) - px(1), px(d) - px(1), fill=color, outline="")
    return c


class Chip(tk.Frame):
    """开关式胶囊：开启时高亮，关闭时低调"""

    def __init__(self, parent, text, var, cmd=None, size=9):
        bg = parent.cget("bg")
        super().__init__(parent, bg=bg)
        self.var = var
        self._cmd = cmd
        self.btn = RoundButton(self, text, self._toggle,
                               kind="pill" if var.get() else "chip_out",
                               size=size, padx=11, pady=5, radius=99)
        self.btn.pack()

    def _toggle(self):
        self.var.set(not self.var.get())
        self.btn.set_kind("pill" if self.var.get() else "chip_out")
        if self._cmd:
            self._cmd()

    def sync(self):
        try:
            self.btn.set_kind("pill" if self.var.get() else "chip_out")
        except Exception:
            pass


class SlimScroll(tk.Canvas):
    """细长滚动条：内容不满时不出现，出现时也不抢视线"""

    def __init__(self, master, command, bg=BG):
        self._bar = px(6)
        super().__init__(master, width=self._bar + px(6), bg=bg, highlightthickness=0, bd=0)
        self._cmd = command
        self._first, self._last = 0.0, 1.0
        self._hover = False
        self._grab = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_grab", None))

    def _on_enter(self, _=None):
        self._hover = True
        self._draw()

    def _on_leave(self, _=None):
        if self._grab is None:
            self._hover = False
            self._draw()

    def set(self, first, last):
        self._first, self._last = float(first), float(last)
        self._draw()

    def _geom(self):
        h = max(1, self.winfo_height())
        span = max(0.0, min(1.0, self._last - self._first))
        th = max(px(26), h * span)
        th = min(th, h)
        rest = h - th
        f = 0.0 if span >= 1 else min(1.0, max(0.0, self._first / (1 - span)))
        return th, rest * f

    def _draw(self):
        self.delete("all")
        if self._last - self._first >= 0.999:
            return
        th, y = self._geom()
        x1, x2 = px(3), px(3) + self._bar
        color = "#b6c0d0" if self._hover else "#ccd4e2"
        round_poly(self, x1, y, x2, y + th, self._bar / 2, fill=color, outline="")

    def _press(self, e):
        th, y = self._geom()
        if y <= e.y <= y + th:
            self._grab = e.y - y
        else:
            self._grab = th / 2
            self._jump(e.y)

    def _drag(self, e):
        self._jump(e.y)

    def _jump(self, y):
        th, _ = self._geom()
        span = max(0.001, min(1.0, self._last - self._first))
        rest = max(1, self.winfo_height() - th)
        top = min(1.0, max(0.0, (y - (self._grab or 0)) / rest))
        self._cmd("moveto", top * (1 - span))


class Card(tk.Canvas):
    """圆角卡片：canvas 画形状，内部 Frame 承载内容"""

    def __init__(self, master, active=False, bg=None, radius=10, fill=CARD, line=None):
        super().__init__(master, bg=bg or master.cget("bg"), highlightthickness=0, bd=0)
        self._r = px(radius)
        self._inset = max(px(2), int(self._r * 0.42))
        self._active = active
        self._hover = False
        self._ch = 0
        self._fill = fill
        self._line = line
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(self._inset, self._inset, window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._sync)
        self.bind("<Configure>", self._sync)

    def _sync(self, _=None):
        w = self.winfo_width()
        if w < 2:
            return
        bh = max(self.body.winfo_reqheight(), 1)
        h = bh + self._inset * 2
        self.itemconfig(self._win, width=max(1, w - self._inset * 2))
        if h != self._ch:
            self._ch = h
            self.configure(height=h)
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), self._ch
        if w < 2 or h < 2:
            return
        self.delete("shape")
        if self._line is None:
            line = ACCENT if self._active else (BORDER_HOVER if self._hover else BORDER)
        else:
            line = self._line
        round_poly(self, 1, 1, w - 1, h - 1, self._r,
                   fill=self._fill, outline=line, width=1, tags="shape")
        self.tag_lower("shape")

    def set_fill(self, fill, line=""):
        self._fill = fill
        self._line = line
        self.body.config(bg=fill)
        self._draw()

    def hoverable(self):
        def walk(w):
            w.bind("<Enter>", self._enter, add="+")
            w.bind("<Leave>", self._leave, add="+")
            for c in w.winfo_children():
                walk(c)

        walk(self.body)
        return self

    def _enter(self, _=None):
        if not self._hover:
            self._hover = True
            self._draw()

    def _leave(self, _=None):
        if not self._hover:
            return
        x, y = self.winfo_pointerxy()
        rx, ry = self.winfo_rootx(), self.winfo_rooty()
        if rx <= x <= rx + self.winfo_width() and ry <= y <= ry + self._ch:
            return
        self._hover = False
        self._draw()


class ProfileDialog(tk.Toplevel):
    """新增 / 编辑档案"""

    def __init__(self, app, name=None):
        super().__init__(app.root)
        self.app = app
        self.f = app.f
        self.old_name = name
        self.profile = dict(app.store["profiles"].get(name, {})) if name else {}

        self.title("编辑配置" if name else "新增配置")
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.transient(app.root)
        self.grab_set()

        pad = tk.Frame(self, bg=CARD)
        pad.pack(fill="both", expand=True, padx=px(26), pady=px(20))

        # 底部按钮先占位，保证任何情况下都不会被内容挤出去
        btns = tk.Frame(pad, bg=CARD)
        btns.pack(fill="x", side="bottom", pady=(px(14), 0))

        tk.Label(pad, text="编辑配置" if name else "新增配置", font=fnt(13, True),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(pad, text="保存后写入 Codex 配置；改动到当前配置会自动重启 Codex / ChatGPT",
                 font=fnt(9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(px(3), px(6)))

        self.vars = {}
        self.entries = {}

        def field(key, label, value="", hint="", show=None, row_hook=None):
            row = tk.Frame(pad, bg=CARD)
            row.pack(fill="x", pady=(px(9), px(3)))
            tk.Label(row, text=label, font=fnt(9), fg=MUTED, bg=CARD).pack(side="left")
            if row_hook:
                row_hook(row)
            e = tk.Entry(
                pad, font=fnt(10), bg=FIELD, fg=TEXT, relief="flat",
                highlightthickness=1, highlightbackground=BTN_BORDER,
                highlightcolor=ACCENT, insertbackground=TEXT,
            )
            if show:
                e.config(show=show)
            self.vars[key] = tk.StringVar(value=value or "")
            e.config(textvariable=self.vars[key])
            e.pack(fill="x", ipady=px(5))
            if hint:
                tk.Label(pad, text=hint, font=fnt(8), fg=FAINT, bg=CARD).pack(anchor="w", pady=(px(2), 0))
            self.entries[key] = e
            return e

        field("name", "名称", self.old_name or self.profile.get("name", ""), "英文或拼音，命令行也好用")
        field("base_url", "网关地址", self.profile.get("base_url", ""), "例如 https://api.openai.com/v1")

        self.show_key = tk.BooleanVar(value=False)

        def key_hook(row):
            Chip(row, "显示 Key", self.show_key, self._toggle_key, size=8).pack(side="right")

        key_entry = field("api_key", "API Key", self.profile.get("api_key", ""), "", show="•",
                          row_hook=key_hook)

        # 模型名称：手填，或拉取后在下拉列表里点选
        mrow = tk.Frame(pad, bg=CARD)
        mrow.pack(fill="x", pady=(px(9), px(3)))
        tk.Label(mrow, text="模型名称", font=fnt(9), fg=MUTED, bg=CARD).pack(side="left")
        self.pull_btn = button(mrow, "拉取模型", self.fetch_models, "soft",
                               font=fnt(8), padx=11, pady=3)
        self.pull_btn.pack(side="right")

        self.vars["model"] = tk.StringVar(value=self.profile.get("model", ""))
        self.model_entry = tk.Entry(
            pad, font=fnt(10), bg=FIELD, fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BTN_BORDER, highlightcolor=ACCENT,
            insertbackground=TEXT, textvariable=self.vars["model"],
        )
        self.model_entry.pack(fill="x", ipady=px(5))
        self.entries["model"] = self.model_entry

        # 拉取到的模型用列表展示：点一下即选中（弹窗里的下拉框经常点不动）
        self.model_wrap = tk.Frame(pad, bg=CARD)
        self.model_list = tk.Listbox(
            self.model_wrap, font=fnt(9), bg=FIELD, fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER,
            activestyle="none", bd=0,
            selectbackground=ACCENT_SOFT, selectforeground=ACCENT,
            height=6, exportselection=False,
        )
        self.model_list.pack(fill="x")
        self.model_list.bind("<ButtonRelease-1>", self._pick_model)
        self.model_list.bind("<Return>", lambda e: self._pick_model())

        cached = list(app.model_cache.get(self.profile.get("base_url")) or [])
        if cached:
            self._fill_models(cached, show=False)
        self.model_hint = tk.Label(
            pad,
            text=(f"上次拉取过 {len(cached)} 个模型，点列表里的一行即可选中" if cached
                  else "可直接输入，或点「拉取模型」从网关获取真实列表"),
            font=fnt(8), fg=(MUTED if cached else FAINT), bg=CARD, anchor="w",
        )
        self.model_hint.pack(anchor="w", pady=(px(2), 0))

        wrow = tk.Frame(pad, bg=CARD)
        wrow.pack(fill="x", pady=(px(9), px(3)))
        tk.Label(wrow, text="接口类型", font=fnt(9), fg=MUTED, bg=CARD).pack(side="left")

        self.wire = tk.StringVar(value=self.profile.get("wire_api") or "responses")
        seg = tk.Frame(pad, bg=CARD)
        seg.pack(anchor="w")

        def pick_wire(v):
            self.wire.set(v)
            for val, b in wire_btns:
                b.set_kind("pill" if val == v else "chip_out")

        wire_btns = []
        for val in ("responses", "chat"):
            b = RoundButton(seg, val, None, size=9, padx=14, pady=5, radius=99)
            b._cmd = lambda v=val: pick_wire(v)
            b.config(cursor="hand2")
            b.pack(side="left", padx=(0, px(6)))
            wire_btns.append((val, b))
        pick_wire(self.wire.get() if self.wire.get() in ("responses", "chat") else "responses")

        field("note", "备注", self.profile.get("note", ""), "可选，比如“官方直连”“备用”")

        self.err = tk.Label(pad, text="", font=fnt(9), fg=RED, bg=CARD,
                            wraplength=px(360), justify="left")
        self.err.pack(anchor="w", pady=(px(6), 0))

        if not name:
            self.use_now = tk.BooleanVar(value=True)
            Chip(pad, "保存后立即切换", self.use_now, size=9).pack(anchor="w", pady=(px(8), 0))
        else:
            self.use_now = None

        is_cur = bool(name) and core.current_name(app.store) == name
        button(btns, "保存并生效" if is_cur else "保存", self.save, "primary",
               font=fnt(10), padx=22, pady=8).pack(side="right")
        button(btns, "取消", self.destroy, "ghost", font=fnt(10), padx=18, pady=8).pack(side="right", padx=(0, px(8)))
        if name:
            button(btns, "删除", self.remove, "danger", font=fnt(10), padx=16, pady=8).pack(side="left")

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

        # 按实际内容定高，再居中
        self.update_idletasks()
        h = min(self.winfo_reqheight(), int(self.winfo_screenheight() * 0.88))
        app.place(self, px(432), h)
        self.after(80, lambda: self.entries["name"].focus_set())

    def _toggle_key(self):
        e = self.entries.get("api_key")
        if e is not None:
            e.config(show="" if self.show_key.get() else "•")

    def fetch_models(self):
        base = self._val("base_url") or self.profile.get("base_url", "")
        key = self._val("api_key") or self.profile.get("api_key", "")
        if not base:
            return self.err.config(text="先填网关地址，再拉取模型")
        if not key:
            return self.err.config(text="先填 API Key，再拉取模型")
        self._last_base = base.strip()
        self.err.config(text="")
        self.pull_btn.config(text="拉取中…", state="disabled")
        px_url = core.detect_proxy()
        self.model_hint.config(
            text="正在请求 /models …" + (f"（直连不通会自动走代理 {core._short_proxy(px_url)}）" if px_url else ""),
            fg=MUTED)

        def work():
            r = core.fetch_models(base, key)
            self.app._ui(lambda: self._models_ready(r))

        threading.Thread(target=work, daemon=True).start()

    def _fill_models(self, models, show=True):
        """把模型塞进列表；默认展开显示"""
        self.model_list.delete(0, "end")
        for m in models:
            self.model_list.insert("end", m)
        if show and models:
            if not self.model_wrap.winfo_ismapped():
                self.model_wrap.pack(fill="x", after=self.model_entry, pady=(px(5), 0))
            self.model_list.config(height=min(6, max(3, len(models))))
            cur = self.vars["model"].get().strip()
            if cur in models:
                i = models.index(cur)
                self.model_list.selection_set(i)
                self.model_list.see(i)

    def _pick_model(self, _=None):
        sel = self.model_list.curselection()
        if not sel:
            return
        name = self.model_list.get(sel[0])
        self.vars["model"].set(name)
        is_cur = bool(self.old_name) and core.current_name(self.app.store) == self.old_name
        if not is_cur:
            self.model_hint.config(text=f"已选中 {name} · 点「保存」写入这套配置", fg=ACCENT)
            return
        # 当前档案：选中即落盘，避免"拉到了模型但 config.toml 没变"
        try:
            core.update_profile(self.app.store, self.old_name, model=name)
        except core.CoreError as e:
            self.model_hint.config(text=f"写入失败：{e}", fg=RED)
            return
        self.app.reload()
        live = (core.detect_live() or {}).get("model")
        if live == name:
            # 桌面版只在启动时读模型目录，写完必须重启才会真的换模型
            self.model_hint.config(
                text=f"已写入 model = {name} · 正在重启客户端让它生效…", fg=GREEN)
            self.app.say(f"模型已切换为 {name} · config.toml 与模型目录都已更新，正在重启客户端…", "ok")
            self.app._restart_async(prefix=f"模型改为 {name}")
        else:
            self.model_hint.config(
                text=f"写入后读回是「{live or '空'}」，对不上，请点「保存并生效」重试", fg=RED)

    def _models_ready(self, r):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.pull_btn.config(text="拉取模型", state="normal")

        if not r.get("ok"):
            head = f"HTTP {r['status']}" if r.get("status") else "连接失败"
            tip = r.get("hint") or str(r.get("error") or "")[:48]
            self.model_hint.config(text=f"拉取失败：{head}" + (f" · {tip}" if tip else ""), fg=RED)
            return

        models = r.get("models") or []
        fix = r.get("fix_base") or ""
        if not models:
            tip = f"网关地址建议改成 {fix}" if fix else "网关没返回模型列表，请手动输入"
            self.model_hint.config(text=tip, fg=AMBER)
            return

        self._fill_models(models)
        if getattr(self, "_last_base", ""):
            self.app.model_cache[self._last_base] = models
        via = "经代理 " + r["proxy"] if r.get("via") == "proxy" and r.get("proxy") else "直连"
        extra = f" · {r.get('ms', 0)}ms · {via}" if r.get("ms") else ""
        if fix:
            extra += f" · 网关地址建议改成 {fix}"
        self.model_hint.config(
            text=f"已拉取 {len(models)} 个模型{extra} · 点下面任意一行选中",
            fg=AMBER if fix else GREEN
        )

    def _val(self, k):
        return self.vars[k].get().strip()

    def save(self):
        name = core.slug(self._val("name"))
        base_url = self._val("base_url")
        api_key = self._val("api_key")
        if not name:
            return self.err.config(text="名称不能为空")
        if not base_url:
            return self.err.config(text="网关地址不能为空")
        if not api_key:
            return self.err.config(text="API Key 不能为空")
        if not base_url.startswith(("http://", "https://")):
            return self.err.config(text="网关地址要以 http:// 或 https:// 开头")
        if name in self.app.store["profiles"] and name != self.old_name:
            return self.err.config(text=f"名称“{name}”已存在，换一个")

        fields = dict(
            base_url=base_url, api_key=api_key, model=self._val("model"),
            wire_api=self.wire.get(), note=self._val("note"),
        )
        old = self.profile or {}
        changed = [
            label
            for key, label in (("model", "模型"), ("base_url", "网关"),
                               ("api_key", "Key"), ("wire_api", "接口类型"))
            if str(old.get(key) or "") != str(fields.get(key) or "")
        ]

        live_before = core.detect_live()
        try:
            if self.old_name:
                if name != self.old_name:
                    core.rename_profile(self.app.store, self.old_name, name)
                core.update_profile(self.app.store, name, **fields)
            else:
                core.add_profile(
                    self.app.store, name, base_url, api_key,
                    model=fields["model"], wire_api=fields["wire_api"],
                    note=fields["note"], use=bool(self.use_now and self.use_now.get()),
                )
            self.app.reload()
        except core.CoreError as e:
            return self.err.config(text=str(e))
        live_after = core.detect_live()
        is_cur = core.current_name(self.app.store) == name
        wrote = (live_after or {}).get("model") or "未设置"

        verb = "已保存" if self.old_name else "已添加"
        want = (fields.get("model") or "").strip()
        bad = bool(is_cur and want and wrote != want)
        self.destroy()

        what = f"（{'、'.join(changed)}）" if changed else ""
        if bad:
            # 写完读回来对不上：明确报出来，不要静默
            self.app.say(
                f"{verb}「{name}」{what} · 但 config.toml 里读到的是「{wrote}」，期望「{want}」",
                "warn")
            self.app.toast(f"模型没写进 config.toml（读回 {wrote}），请点「重启客户端」后再试", "err", 14000)
        elif not is_cur:
            self.app.say(f"{verb}「{name}」 · 不是当前生效的配置，切换过去时生效", "ok")
        elif live_after != live_before:
            # 真正改动到当前生效的配置 → 和"切换"一样，自动重启客户端
            self.app.say(f"{verb}「{name}」{what} · config.toml 已写入 model = {wrote}，正在重启客户端…", "ok")
            self.app._restart_async(prefix=f"{verb}「{name}」{what}")
        else:
            self.app.say(f"{verb}「{name}」{what} · config.toml 里 model = {wrote}，没有变化", "ok")

    def remove(self):
        name = self.old_name
        if not messagebox.askyesno("删除配置", f"确定删除「{name}」吗？\n\n只删掉这套档案，不会改动当前配置文件。",
                                   parent=self):
            return
        try:
            core.delete_profile(self.app.store, name)
        except core.CoreError as e:
            return messagebox.showerror("删除失败", str(e), parent=self)
        self.app.reload()
        self.app.say(f"已删除「{name}」", "ok")
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        self.f = pick_font(root)
        init_ttk(root)
        self.store = core.load_store()
        self._status_job = None
        self._tray_hint = False
        self._ui_q = queue.Queue()
        self.model_cache = {}          # 网关 -> 上次拉到的模型列表
        self.tray = None
        self.clients = {"apps": [], "editors": []}
        self._detecting = False        # 是否有一轮检测在跑（避免重复起线程）
        self._detect_text = None       # 上一次的检测文案（变了才刷，免得闪）
        self._closing = False

        root.title(core.APP_NAME)
        root.configure(bg=BG)
        root.minsize(px(820), px(420))
        try:
            if os.path.exists(ICON):
                root.iconbitmap(ICON)
        except Exception:
            pass
        self.center(root, 900, 640)

        self._build()
        self.refresh()
        self._init_tray()
        self._detect_async()

    # ------------------------------------------------------------ 工具
    def center(self, win, w, h):
        self.place(win, px(w), px(h))

    def place(self, win, w, h):
        """w/h 已经是像素值"""
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        h = min(h, int(sh * 0.92))
        if win is self.root:
            x, y = (sw - w) // 2, (sh - h) // 2 - px(24)
        else:
            x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def say(self, text, kind="info"):
        """动作结果统一走顶部提示条（9 秒后自动消失）"""
        self.toast(text, kind, 9000)

    def reload(self):
        self.store = core.load_store()
        self.refresh()

    # ------------------------------------------------------------ 界面
    def _build(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=px(24), pady=(px(20), px(4)))
        self._hdr = hdr
        left = tk.Frame(hdr, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="API 环境切换器", font=fnt(16, True), fg=TEXT, bg=BG).pack(anchor="w")
        self.sub = tk.Label(left, text="", font=fnt(9), fg=MUTED, bg=BG)
        self.sub.pack(anchor="w", pady=(px(4), 0))

        right = tk.Frame(hdr, bg=BG)
        right.pack(side="right")
        self.var_han = tk.BooleanVar(value=core.han_enabled(self.store))
        self.chip_han = Chip(right, "汉化界面", self.var_han, self.toggle_han)
        self.chip_han.pack(side="left", padx=(0, px(8)))

        pconf = core.proxy_conf(self.store)
        pport = pconf["url"].rsplit(":", 1)[-1].strip("/")
        self.var_proxy = tk.BooleanVar(value=pconf["on"])
        self.chip_proxy = Chip(right, f"代理 {pport}", self.var_proxy, self.toggle_proxy)
        self.chip_proxy.pack(side="left", padx=(0, px(14)))

        self.btn_restart = button(right, "重启客户端", self.restart_now, "soft", font=fnt(9), padx=14, pady=6)
        self.btn_restart.pack(side="left", padx=(0, px(8)))
        button(right, "刷新", self.refresh, "ghost", font=fnt(9), padx=14, pady=6).pack(side="left", padx=(0, px(8)))
        button(right, "打开配置文件", self.open_config, "ghost", font=fnt(9), padx=14, pady=6).pack(side="left")

        # 顶部提示条（重启 / 保存等动作的结果）
        self.banner_slot = tk.Frame(self.root, bg=BG)
        self.banner_slot.pack(fill="x")
        self.banner = Card(self.banner_slot, radius=9, fill=ACCENT_SOFT, line="")
        self.banner_lbl = tk.Label(self.banner.body, text="", font=fnt(9), fg=ACCENT,
                                   bg=ACCENT_SOFT, anchor="w", justify="left",
                                   wraplength=px(740))
        self.banner_lbl.pack(fill="x", padx=px(12), pady=px(8))

        # 底部（pack 顺序：先的在最底下）
        tiny = tk.Frame(self.root, bg=BG)
        tiny.pack(side="bottom", fill="x", padx=px(26), pady=(0, px(12)))
        self._tiny = tiny
        tk.Label(tiny, text=f"配置文件  {core.CONFIG}", font=fnt(8), fg=FAINT, bg=BG,
                 anchor="w").pack(side="left")
        tk.Label(tiny, text="每次切换：改配置 + 写全局环境变量 + 完整重启 Codex / ChatGPT",
                 font=fnt(8), fg=FAINT, bg=BG, anchor="e").pack(side="right")

        foot = tk.Frame(self.root, bg=BG)
        foot.pack(side="bottom", fill="x", padx=px(24), pady=(px(10), px(8)))
        self._foot = foot
        button(foot, "＋ 新增配置", self.add, "primary", font=fnt(10), padx=18, pady=8).pack(side="left")
        button(foot, "切回上一个", self.use_prev, "ghost", font=fnt(9), padx=15, pady=8).pack(side="left", padx=(px(8), 0))

        self.detect_box = tk.Frame(foot, bg=BG)
        self.detect_box.pack(side="right")
        self.detect_dot = dot(self.detect_box, FAINT, 7)
        self.detect_dot.pack(side="left", padx=(0, px(6)))
        self.detect_lbl = tk.Label(self.detect_box, text="正在检测 Codex / ChatGPT…",
                                   font=fnt(9), fg=FAINT, bg=BG, anchor="e")
        self.detect_lbl.pack(side="left")

        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(side="bottom", fill="x", padx=px(24))

        # 列表
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=px(24), pady=(px(10), 0))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb = SlimScroll(wrap, self.canvas.yview, bg=BG)
        self.vsb.pack(side="right", fill="y", padx=(px(4), 0), before=self.canvas)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack_forget()

        self.inner = tk.Frame(self.canvas, bg=BG)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", lambda e: self._on_resize(e))
        self.root.bind_all("<MouseWheel>", self._on_wheel)

    def _on_resize(self, e):
        self.canvas.itemconfig(self.win, width=e.width)
        self._on_inner()

    def toast(self, text, kind="info", ms=9000):
        """窗口顶部的横条提示；ms=0 表示一直显示到下次调用"""
        colors = {"ok": (GREEN_SOFT, GREEN), "err": (RED_SOFT, RED),
                  "warn": (AMBER_SOFT, AMBER), "info": (ACCENT_SOFT, ACCENT)}
        bg, fg = colors.get(kind, colors["info"])
        try:
            self.banner.set_fill(bg, "")
            self.banner_lbl.config(text=text, fg=fg, bg=bg)
            if not self.banner.winfo_ismapped():
                self.banner.pack(fill="x", padx=px(24), pady=(px(6), 0))
        except Exception:
            return
        if getattr(self, "_toast_job", None):
            try:
                self.root.after_cancel(self._toast_job)
            except Exception:
                pass
            self._toast_job = None
        if ms:
            self._toast_job = self.root.after(ms, self._hide_toast)

    def _hide_toast(self):
        self._toast_job = None
        try:
            self.banner.pack_forget()
        except Exception:
            pass

    def _on_inner(self, _=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            return
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1
        try:
            shown = bool(self.vsb.winfo_ismapped())
            if need and not shown:
                self.vsb.pack(side="right", fill="y", padx=(px(4), 0), before=self.canvas)
            elif not need and shown:
                self.vsb.pack_forget()
        except Exception:
            pass

    def _on_wheel(self, e):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120), "units")

    # ------------------------------------------------------------ 渲染
    def refresh(self):
        self.store = core.load_store()
        for w in self.inner.winfo_children():
            w.destroy()

        cur = core.current_name(self.store)
        names = sorted(self.store["profiles"], key=str.lower)
        live = core.detect_live() or {}
        if not names:
            self._empty_state()
        else:
            for name in names:
                self._card(name, self.store["profiles"][name], name == cur, live.get("model"))

        if cur:
            self.sub.config(text=f"共 {len(names)} 套配置    ·    当前使用 {cur}    ·    "
                                 f"{live.get('model') or '模型未设置'}")
        else:
            self.sub.config(text=f"共 {len(names)} 套配置    ·    当前配置未匹配到任何档案")
        self.root.update_idletasks()
        self._on_inner()
        if not getattr(self, "_fitted", False):
            self._fit_window()

    def _fit_window(self):
        """第一次渲染后把窗口高度收到内容高度，空列表也好看"""
        self._fitted = True
        try:
            self.root.update_idletasks()
            chrome = (self._hdr.winfo_reqheight() + px(24)
                      + self._foot.winfo_reqheight() + px(18)
                      + self._tiny.winfo_reqheight() + px(12) + px(11))
            need = self.inner.winfo_reqheight() + chrome
            h = int(max(px(440), min(need, px(720))))
            w = px(900)
            cx = self.root.winfo_rootx() + self.root.winfo_width() // 2
            cy = self.root.winfo_rooty() + self.root.winfo_height() // 2
            self.root.geometry(f"{w}x{h}+{max(0, cx - w // 2)}+{max(0, cy - h // 2)}")
        except Exception:
            pass

    def _empty_state(self):
        card = Card(self.inner)
        card.pack(fill="x", pady=(px(4), 0))
        p = tk.Frame(card.body, bg=CARD)
        p.pack(padx=px(28), pady=px(34))
        tk.Label(p, text="还没有任何配置", font=fnt(13, True), fg=TEXT, bg=CARD).pack()
        tk.Label(p, text="点击下面的「新增配置」，填入网关地址和 API Key\n以后就能在多个 Key 之间一键切换",
                 font=fnt(9), fg=MUTED, bg=CARD, justify="center").pack(pady=(px(8), px(16)))
        button(p, "＋ 新增第一套配置", self.add, "primary", font=fnt(10), padx=18, pady=8).pack()

    def _card(self, name, prof, is_cur, live_model=None):
        card = Card(self.inner, active=is_cur)
        card.pack(fill="x", pady=(0, px(10)))
        pad = tk.Frame(card.body, bg=CARD)
        pad.pack(fill="x", padx=px(15), pady=px(12))

        head = tk.Frame(pad, bg=CARD)
        head.pack(fill="x")
        meta = tk.Frame(pad, bg=CARD)
        meta.pack(fill="x", pady=(px(8), 0))

        res = tk.Label(meta, text="", font=fnt(9), fg=MUTED, bg=CARD, anchor="e")
        res.pack(side="right")

        btns = tk.Frame(head, bg=CARD)
        btns.pack(side="right")
        if not is_cur:
            button(btns, "切换", lambda n=name: self.use(n), "primary",
                   font=fnt(9), padx=18, pady=5).pack(side="right", padx=(px(6), 0))
        button(btns, "编辑", lambda n=name: self.edit(n), "ghost",
               font=fnt(9), padx=14, pady=5).pack(side="right", padx=(px(6), 0))
        button(btns, "测试", lambda n=name, lb=res: self.test(n, lb), "ghost",
               font=fnt(9), padx=14, pady=5).pack(side="right", padx=(px(6), 0))
        button(btns, "删除", lambda n=name: self.remove(n), "del",
               font=fnt(9), padx=10, pady=5).pack(side="right", padx=(px(2), 0))

        dot(head, GREEN if is_cur else DOT_OFF, 8).pack(side="left", padx=(px(1), px(10)))
        tk.Label(head, text=name, font=fnt(11, True), fg=TEXT, bg=CARD).pack(side="left")
        if is_cur:
            RoundButton(head, "使用中", None, kind="pill", size=8, padx=8, pady=3, radius=99).pack(
                side="left", padx=(px(9), 0))
        model = (prof.get("model") or "").strip()
        RoundButton(head, model or "未设模型", None,
                    kind="chip" if model else "chip_warn",
                    size=8, padx=9, pady=3, radius=99).pack(side="left", padx=(px(9), 0))
        if is_cur and live_model and model and live_model != model:
            tk.Label(head, text=f"config.toml 实际是 {live_model}", font=fnt(8),
                     fg=AMBER, bg=AMBER_SOFT, padx=px(6), pady=px(1)).pack(side="left", padx=(px(8), 0))

        tk.Label(meta, text="网关", font=fnt(9), fg=FAINT, bg=CARD).pack(side="left")
        tk.Label(meta, text=core.host_of(prof.get("base_url")), font=fnt(9), fg=MUTED,
                 bg=CARD).pack(side="left", padx=(px(5), px(16)))
        tk.Label(meta, text="Key", font=fnt(9), fg=FAINT, bg=CARD).pack(side="left")
        tk.Label(meta, text=core.mask(prof.get("api_key")), font=fnt(9), fg=MUTED,
                 bg=CARD).pack(side="left", padx=(px(5), 0))
        if prof.get("note"):
            tk.Label(meta, text="·", font=fnt(9), fg=FAINT, bg=CARD).pack(side="left", padx=px(10))
            tk.Label(meta, text=str(prof.get("note"))[:30], font=fnt(9), fg=FAINT,
                     bg=CARD).pack(side="left")

        card.hoverable()

    # ------------------------------------------------------------ 动作
    def use(self, name):
        try:
            r = core.use_profile(self.store, name)
        except core.CoreError as e:
            return messagebox.showerror("切换失败", str(e), parent=self.root)
        self.refresh()
        self.say(f"已切换到「{name}」 · 全局环境变量已写入，正在重启客户端…", "ok")
        self._restart_async(prefix=f"已切换到「{name}」")

    def remove(self, name):
        if not messagebox.askyesno(
            "删除配置", f"确定删除「{name}」吗？\n\n只删掉这套档案，不会改动当前配置文件。",
            parent=self.root,
        ):
            return
        try:
            core.delete_profile(self.store, name)
        except core.CoreError as e:
            return messagebox.showerror("删除失败", str(e), parent=self.root)
        self.refresh()
        self.say(f"已删除「{name}」", "ok")

    # ------------------------------------------------------------ 客户端重启
    def restart_now(self):
        self._restart_async()

    def toggle_han(self):
        on = bool(self.var_han.get())
        core.set_han(self.store, on)
        if on:
            self.toast("已开启汉化 · 正在带调试端口重启客户端，启动后自动翻译界面…", "info", 0)
            self._restart_async(prefix="开启汉化")
        else:
            self.toast("已关闭汉化 · 正在用原样方式重启客户端（界面回到英文）…", "info", 0)
            self._restart_async(prefix="关闭汉化")

    def toggle_proxy(self):
        on = bool(self.var_proxy.get())
        c = core.set_proxy(self.store, on=on)
        if not on:
            self.toast("已关闭 · ChatGPT 恢复直连（系统代理没动过），正在重启…", "info", 0)
            return self._restart_async(prefix="关闭代理")
        if core.proxy_alive(c["url"]):
            self.toast(f"已开启 · ChatGPT 将单独走 {c['url']}，正在重启…", "info", 0)
        else:
            self.toast(f"已开启，但 {c['url']} 现在没在监听，本次先直连（代理起来后重启即可）", "warn", 12000)
        self._restart_async(prefix="开启代理")

    def _han_bg(self):
        """重启完成后在后台把界面翻成中文（不阻塞窗口）"""
        if not core.han_enabled(self.store):
            return

        def tick(msg):
            self._ui(lambda: self.toast(msg, "info", 0))

        def work():
            try:
                r = core.han_apply(self.store, wait=120, on_tick=tick)
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            self._ui(lambda: self._show_han(r))
            if r.get("ok"):
                core.han_watch(self.store)   # 页面万一重载，自动补回来

        threading.Thread(target=work, daemon=True).start()

    def _show_han(self, r):
        if r.get("skipped"):
            return
        if r.get("ok"):
            zh = r.get("zh") or 0
            self.toast(f"界面已汉化 · 词库 {r.get('count', 0)} 条，界面上已生效 {zh} 处", "ok", 8000)
        else:
            self.toast(f"汉化没成功：{r.get('error')}", "err", 14000)

    def _restart_async(self, prefix=""):
        if getattr(self, "_restarting", False):
            return
        self._restarting = True
        try:
            self.btn_restart.config(text="重启中…", state="disabled")
        except Exception:
            pass
        head = (prefix + " · ") if prefix else ""
        self.toast(head + "正在完全退出并重新启动 Codex / ChatGPT，约 5–15 秒，请稍等…", "info", 0)

        def work():
            try:
                res = core.restart_clients(args=core.client_args(self.store))
            except Exception as e:
                res = [{"label": "重启", "status": "error", "detail": str(e)}]
            self._ui(lambda: self._show_restart(res, prefix))

        threading.Thread(target=work, daemon=True).start()

    def _launch_bg(self):
        try:
            res = core.launch_clients(args=core.client_args(self.store))
        except Exception as e:
            res = [{"label": "启动", "status": "error", "detail": str(e)}]
        self._ui(lambda: self._show_restart(res, "启动"))

    def _show_restart(self, res, prefix=""):
        self._restarting = False
        try:
            self.btn_restart.config(text="重启客户端", state="normal")
        except Exception:
            pass
        restarted = [r["label"] for r in res if r["status"] == "restarted"]
        killed = [r["label"] for r in res if r["status"] == "killed"]
        errors = [r for r in res if r["status"] == "error"]
        hints = [r for r in res if r["status"] == "hint"]
        idle = [r["label"] for r in res if r["status"] == "idle"]

        parts = []
        if restarted:
            parts.append("已完整重启 " + "、".join(restarted))
        if killed:
            parts.append("已结束 " + "、".join(killed))
        if idle:
            parts.append("、".join(idle) + " 当前未运行")
        if not parts:
            parts.append("未检测到正在运行的 Codex / ChatGPT")

        text = (prefix + " · " if prefix else "") + " · ".join(parts)
        if hints:
            text += f" · {hints[0]['label']}请重载窗口"
        if errors:
            text += " · " + errors[0]["detail"]
        self.toast(text, "err" if errors else ("ok" if restarted or killed else "warn"),
                   14000 if errors else 9000)

        # 一个都没在跑：直接问要不要现在打开，别让按钮看起来"没反应"
        if res and not restarted and not killed and not errors and not prefix:
            if messagebox.askyesno("客户端没在运行",
                                   "没有检测到正在运行的 Codex / ChatGPT。\n\n要现在帮你打开吗？",
                                   parent=self.root):
                self.toast("正在启动客户端…", "info", 0)
                threading.Thread(target=self._launch_bg, daemon=True).start()
                return
        if core.han_enabled(self.store) and (restarted or killed):
            self._han_bg()
        self._detect_async()

    def _detect_async(self):
        """秒级轮询：装了/在跑/关了，都要跟着实时变"""
        if getattr(self, "_detecting", False) or getattr(self, "_closing", False):
            return
        self._detecting = True

        def work():
            try:
                c = core.detect_clients()
            except Exception:
                c = {"apps": [], "editors": []}
            self._ui(lambda: self._apply_detect(c))

        threading.Thread(target=work, daemon=True).start()

    def _apply_detect(self, c):
        self._detecting = False
        self.clients = c
        text = core.describe_clients(c)
        running = any(a.get("running") for a in c.get("apps", []))
        installed = bool(c.get("apps") or c.get("editors"))
        color = GREEN if running else (MUTED if installed else FAINT)
        try:
            if text != self._detect_text:
                self._detect_text = text
                self.detect_lbl.config(text=text, fg=color)
                self.detect_dot.itemconfig(1, fill=color)
            else:
                self.detect_lbl.config(fg=color)
        except Exception:
            return
        if not self._closing:
            try:
                visible = True
                try:
                    visible = self.root.state() == "normal"
                except Exception:
                    pass
                self.root.after(WATCH_MS if visible else WATCH_MS * 3, self._detect_async)
            except Exception:
                pass

    # ------------------------------------------------------------ 托盘
    def _init_tray(self):
        try:
            from tray_win import Tray

            self.tray = Tray(ICON, core.APP_NAME)
            self.tray.start()
        except Exception:
            self.tray = None
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        except Exception:
            pass
        self.root.after(100, self._tick)

    def _ui(self, fn):
        """后台线程把要执行的动作丢到这里，主线程统一执行（Tk 不能跨线程调用）"""
        self._ui_q.put(fn)

    def _tick(self):
        while True:
            try:
                fn = self._ui_q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass

        if self.tray:
            while True:
                try:
                    ev = self.tray.events.get_nowait()
                except Exception:
                    break
                if ev == "show":
                    self.show_window()
                elif ev == "exit":
                    return self.quit()
        self.root.after(100, self._tick)

    def hide_to_tray(self):
        if not (self.tray and self.tray.ok):
            self.root.iconify()  # 托盘没起来就正常最小化，避免窗口找不回来
            return
        self.root.withdraw()
        if not self._tray_hint:
            self._tray_hint = True
            self.tray.notify(core.APP_NAME, "已缩到右下角通知区域，双击图标可重新打开")

    def show_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def quit(self):
        self._closing = True
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    def use_prev(self):
        prev = self.store.get("previous")
        if not prev or prev not in self.store["profiles"]:
            return self.say("还没有可回退的配置", "warn")
        self.use(prev)

    def add(self):
        ProfileDialog(self, None)

    def edit(self, name):
        ProfileDialog(self, name)

    def test(self, name, label):
        prof = self.store["profiles"].get(name)
        if not prof:
            return
        if label is not None:
            label.config(text="正在测试…", fg=MUTED)

        def work():
            r = core.test_endpoint(prof)

            def show():
                if label is None or not label.winfo_exists():
                    return
                if r.get("ok"):
                    extra = f" · {len(r['models'])} 个模型" if r.get("models") else ""
                    label.config(text=f"✓ 可用 {r.get('ms', 0)}ms{extra}", fg=GREEN)
                else:
                    head = f"✗ HTTP {r['status']}" if r.get("status") else "✗ 连接失败"
                    tip = r.get("hint") or ""
                    label.config(text=(head + (" · " + tip if tip else ""))[:64], fg=RED)

            self._ui(show)

        threading.Thread(target=work, daemon=True).start()

    def open_config(self):
        if core.CONFIG.exists():
            try:
                os.startfile(str(core.CONFIG))
            except Exception as e:
                messagebox.showerror("打不开文件", str(e), parent=self.root)
        else:
            messagebox.showwarning("文件不存在", f"还没有 {core.CONFIG}", parent=self.root)


def main():
    enable_dpi()
    if not ensure_single_instance():
        return
    root = tk.Tk()
    try:
        App(root)
    except Exception as e:
        messagebox.showerror("启动失败", f"{type(e).__name__}: {e}")
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
