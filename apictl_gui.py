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
BG = "#f2f4f7"
CARD = "#ffffff"
BORDER = "#e3e6eb"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_SOFT = "#eaf1fe"
TEXT = "#1b1f24"
MUTED = "#6b7280"
FAINT = "#a3aab4"
GREEN = "#12a150"
GREEN_SOFT = "#e6f7ec"
RED = "#d92d20"
RED_SOFT = "#fdecea"
AMBER = "#b45309"
AMBER_SOFT = "#fdf3e2"
GHOST = "#edeff2"
GHOST_HOVER = "#e1e4e9"

S = 1.0  # DPI 缩放系数
WATCH_MS = 1500  # 客户端运行状态刷新间隔（毫秒）

_MUTEX = None  # 单实例锁，进程退出前必须一直被引用


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
    fams = set(tkfont.families(root))
    for f in ("Microsoft YaHei UI", "微软雅黑", "Microsoft YaHei", "PingFang SC", "Segoe UI"):
        if f in fams:
            return f
    return "TkDefaultFont"


def button(parent, text, cmd, kind="ghost", font=None, padx=14, pady=6):
    styles = {
        "primary": (ACCENT, "#ffffff", ACCENT_HOVER, "#ffffff"),
        "ghost": (GHOST, TEXT, GHOST_HOVER, TEXT),
        "soft": (ACCENT_SOFT, ACCENT, "#dde8fd", ACCENT),
        "danger": (RED_SOFT, RED, "#fbdcd8", RED),
        "del": (GHOST, RED, RED_SOFT, RED),
    }
    bg, fg, hov, hfg = styles.get(kind, styles["ghost"])
    b = tk.Button(
        parent, text=text, command=cmd, font=font,
        bg=bg, fg=fg, activebackground=hov, activeforeground=hfg,
        relief="flat", bd=0, highlightthickness=0,
        padx=px(padx), pady=px(pady), cursor="hand2",
    )
    b.bind("<Enter>", lambda e: b.config(bg=hov))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


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
        pad.pack(fill="both", expand=True, padx=px(26), pady=px(18))

        # 底部按钮先占位，保证任何情况下都不会被内容挤出去
        btns = tk.Frame(pad, bg=CARD)
        btns.pack(fill="x", side="bottom", pady=(px(12), 0))

        tk.Label(pad, text="编辑配置" if name else "新增配置", font=(self.f, 13, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(pad, text="保存后写入 Codex 配置；改动到当前配置会自动重启 Codex / ChatGPT",
                 font=(self.f, 9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(px(2), px(4)))

        self.vars = {}
        self.entries = {}

        def field(key, label, value="", hint="", show=None):
            tk.Label(pad, text=label, font=(self.f, 9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(px(7), px(2)))
            e = tk.Entry(
                pad, font=(self.f, 10), bg="#fbfcfd", fg=TEXT,
                relief="flat", highlightthickness=1, highlightbackground=BORDER,
                highlightcolor=ACCENT, insertbackground=TEXT,
            )
            if show:
                e.config(show=show)
            self.vars[key] = tk.StringVar(value=value or "")
            e.config(textvariable=self.vars[key])
            e.pack(fill="x", ipady=px(4))
            if hint:
                tk.Label(pad, text=hint, font=(self.f, 8), fg=FAINT, bg=CARD).pack(anchor="w", pady=(px(1), 0))
            self.entries[key] = e
            return e

        field("name", "名称", self.old_name or self.profile.get("name", ""), "英文或拼音，命令行也好用")
        field("base_url", "网关地址", self.profile.get("base_url", ""), "例如 https://api.openai.com/v1")
        key_entry = field("api_key", "API Key", self.profile.get("api_key", ""), "", show="•")

        self.show_key = tk.BooleanVar(value=False)
        tk.Checkbutton(pad, text="显示 Key", variable=self.show_key,
                       command=lambda: key_entry.config(show="" if self.show_key.get() else "•"),
                       font=(self.f, 8), fg=MUTED, bg=CARD, activebackground=CARD,
                       selectcolor=CARD, bd=0, highlightthickness=0, cursor="hand2").pack(anchor="e", pady=(px(2), 0))

        # 模型名称：手填，或拉取后在下拉列表里点选
        mrow = tk.Frame(pad, bg=CARD)
        mrow.pack(fill="x", pady=(px(7), px(2)))
        tk.Label(mrow, text="模型名称", font=(self.f, 9), fg=MUTED, bg=CARD).pack(side="left")
        self.pull_btn = button(mrow, "拉取模型", self.fetch_models, "soft",
                               font=(self.f, 8), padx=10, pady=2)
        self.pull_btn.pack(side="right")

        self.vars["model"] = tk.StringVar(value=self.profile.get("model", ""))
        self.model_entry = tk.Entry(
            pad, font=(self.f, 10), bg="#fbfcfd", fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
            insertbackground=TEXT, textvariable=self.vars["model"],
        )
        self.model_entry.pack(fill="x", ipady=px(4))
        self.entries["model"] = self.model_entry

        # 拉取到的模型用列表展示：点一下即选中（弹窗里的下拉框经常点不动）
        self.model_wrap = tk.Frame(pad, bg=CARD)
        self.model_list = tk.Listbox(
            self.model_wrap, font=(self.f, 9), bg="#fbfcfd", fg=TEXT, relief="flat",
            highlightthickness=1, highlightbackground=BORDER, activestyle="none",
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
            font=(self.f, 8), fg=(MUTED if cached else FAINT), bg=CARD, anchor="w",
        )
        self.model_hint.pack(anchor="w", pady=(px(1), 0))

        tk.Label(pad, text="接口类型", font=(self.f, 9), fg=MUTED, bg=CARD).pack(anchor="w", pady=(px(7), px(2)))
        self.wire = tk.StringVar(value=self.profile.get("wire_api") or "responses")
        ttk.Combobox(pad, textvariable=self.wire, values=["responses", "chat"],
                     state="readonly", font=(self.f, 10)).pack(fill="x", ipady=px(2))

        field("note", "备注", self.profile.get("note", ""), "可选，比如“官方直连”“备用”")

        self.err = tk.Label(pad, text="", font=(self.f, 9), fg=RED, bg=CARD,
                            wraplength=px(420), justify="left")
        self.err.pack(anchor="w", pady=(px(4), 0))

        if not name:
            self.use_now = tk.BooleanVar(value=True)
            tk.Checkbutton(pad, text="保存后立即切换", variable=self.use_now,
                           font=(self.f, 9), fg=TEXT, bg=CARD, activebackground=CARD,
                           selectcolor=CARD, bd=0, highlightthickness=0,
                           cursor="hand2").pack(anchor="w", pady=(px(6), 0))
        else:
            self.use_now = None

        is_cur = bool(name) and core.current_name(app.store) == name
        button(btns, "保存并生效" if is_cur else "保存", self.save, "primary",
               font=(self.f, 10), padx=22, pady=8).pack(side="right")
        button(btns, "取消", self.destroy, "ghost", font=(self.f, 10), padx=18, pady=8).pack(side="right", padx=(0, px(8)))
        if name:
            button(btns, "删除", self.remove, "danger", font=(self.f, 10), padx=16, pady=8).pack(side="left")

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

        # 按实际内容定高，再居中
        self.update_idletasks()
        h = min(self.winfo_reqheight(), int(self.winfo_screenheight() * 0.88))
        app.place(self, px(470), h)
        self.after(80, lambda: self.entries["name"].focus_set())

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
                self.model_wrap.pack(fill="x", after=self.model_entry, pady=(px(4), 0))
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
        if not models:
            self.model_hint.config(text="网关没返回模型列表，请手动输入", fg=AMBER)
            return

        self._fill_models(models)
        if getattr(self, "_last_base", ""):
            self.app.model_cache[self._last_base] = models
        via = "经代理 " + r["proxy"] if r.get("via") == "proxy" and r.get("proxy") else "直连"
        extra = f" · {r.get('ms', 0)}ms · {via}" if r.get("ms") else ""
        self.model_hint.config(
            text=f"已拉取 {len(models)} 个模型{extra} · 点下面任意一行选中", fg=GREEN
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
        root.minsize(px(820), px(540))
        try:
            if os.path.exists(ICON):
                root.iconbitmap(ICON)
        except Exception:
            pass
        self.center(root, 880, 620)

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
        colors = {"ok": GREEN, "err": RED, "warn": AMBER, "info": MUTED}
        self.status.config(text=text, fg=colors.get(kind, MUTED))
        if self._status_job:
            self.root.after_cancel(self._status_job)
        self._status_job = self.root.after(9000, lambda: self.status.config(text="", fg=MUTED))

    def reload(self):
        self.store = core.load_store()
        self.refresh()

    # ------------------------------------------------------------ 界面
    def _build(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=px(24), pady=(px(18), px(6)))
        left = tk.Frame(hdr, bg=BG)
        left.pack(side="left")
        tk.Label(left, text="API 环境切换器", font=(self.f, 15, "bold"), fg=TEXT, bg=BG).pack(anchor="w")
        self.sub = tk.Label(left, text="", font=(self.f, 9), fg=MUTED, bg=BG)
        self.sub.pack(anchor="w", pady=(px(3), 0))

        right = tk.Frame(hdr, bg=BG)
        right.pack(side="right")
        self.var_han = tk.BooleanVar(value=core.han_enabled(self.store))
        self.chk_han = tk.Checkbutton(
            right, text="汉化界面", variable=self.var_han, command=self.toggle_han,
            font=(self.f, 9), fg=MUTED, bg=BG, activebackground=BG,
            activeforeground=ACCENT, selectcolor=CARD, bd=0,
            highlightthickness=0, cursor="hand2",
        )
        self.chk_han.pack(side="left", padx=(0, px(12)))

        pconf = core.proxy_conf(self.store)
        pport = pconf["url"].rsplit(":", 1)[-1].strip("/")
        self.var_proxy = tk.BooleanVar(value=pconf["on"])
        self.chk_proxy = tk.Checkbutton(
            right, text=f"代理 {pport}", variable=self.var_proxy, command=self.toggle_proxy,
            font=(self.f, 9), fg=MUTED, bg=BG, activebackground=BG,
            activeforeground=ACCENT, selectcolor=CARD, bd=0,
            highlightthickness=0, cursor="hand2",
        )
        self.chk_proxy.pack(side="left", padx=(0, px(12)))
        self.btn_restart = button(right, "重启客户端", self.restart_now, "soft", font=(self.f, 9))
        self.btn_restart.pack(side="left", padx=(0, px(6)))
        button(right, "刷新", self.refresh, "ghost", font=(self.f, 9)).pack(side="left", padx=(0, px(6)))
        button(right, "打开配置文件", self.open_config, "ghost", font=(self.f, 9)).pack(side="left")

        # 底部（pack 顺序：先的在最底下）
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(side="bottom", fill="x", padx=px(26), pady=(0, px(12)))
        tk.Label(foot, text=f"配置文件  {core.CONFIG}", font=(self.f, 8), fg=FAINT, bg=BG,
                 anchor="w").pack(side="left")
        tk.Label(foot, text="每次切换：改配置 + 写全局环境变量 + 完整重启 Codex / ChatGPT",
                 font=(self.f, 8), fg=FAINT, bg=BG, anchor="e").pack(side="right")

        ftr = tk.Frame(self.root, bg=BG)
        ftr.pack(side="bottom", fill="x", padx=px(24), pady=(px(8), px(4)))
        button(ftr, "＋ 新增配置", self.add, "primary", font=(self.f, 10), padx=18, pady=8).pack(side="left")
        button(ftr, "切回上一个", self.use_prev, "ghost", font=(self.f, 9), pady=8).pack(side="left", padx=(px(8), 0))

        self.status = tk.Label(ftr, text="", font=(self.f, 9), fg=MUTED, bg=BG, anchor="e")
        self.status.pack(side="right")

        self.detect_lbl = tk.Label(ftr, text="正在检测 Codex / ChatGPT…", font=(self.f, 8),
                                   fg=FAINT, bg=BG, anchor="w")
        self.detect_lbl.pack(side="left", padx=(px(16), 0))

        # 列表
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=px(24), pady=(px(6), 0))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.root.bind_all("<MouseWheel>", self._on_wheel)

        # 顶部提示条：重启 / 保存等动作的结果放这里，比页脚小字显眼
        self.banner = tk.Frame(self.root, bg=ACCENT_SOFT)
        self.banner_lbl = tk.Label(self.banner, text="", font=(self.f, 9),
                                   fg=ACCENT, bg=ACCENT_SOFT, anchor="w")
        self.banner_lbl.pack(fill="x", padx=px(14), pady=px(7))

    def toast(self, text, kind="info", ms=9000):
        """窗口顶部的横条提示；ms=0 表示一直显示到下次调用"""
        colors = {"ok": (GREEN_SOFT, GREEN), "err": (RED_SOFT, RED),
                  "warn": ("#fff7e6", AMBER), "info": (ACCENT_SOFT, ACCENT)}
        bg, fg = colors.get(kind, colors["info"])
        try:
            self.banner.config(bg=bg)
            self.banner_lbl.config(text=text, fg=fg, bg=bg)
            if not self.banner.winfo_ismapped():
                self.banner.pack(fill="x", padx=px(24), pady=(0, px(6)), after=self.btn_restart.master.master)
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
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_wheel(self, e):
        if self.inner.winfo_height() > self.canvas.winfo_height():
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

    def _empty_state(self):
        box = tk.Frame(self.inner, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", pady=(px(8), 0))
        p = tk.Frame(box, bg=CARD)
        p.pack(padx=px(30), pady=px(36))
        tk.Label(p, text="还没有任何配置", font=(self.f, 13, "bold"), fg=TEXT, bg=CARD).pack()
        tk.Label(p, text="点击下面的「新增配置」，填入网关地址和 API Key\n以后就能在多个 Key 之间一键切换",
                 font=(self.f, 9), fg=MUTED, bg=CARD, justify="center").pack(pady=(px(8), px(16)))
        button(p, "＋ 新增第一套配置", self.add, "primary", font=(self.f, 10), padx=18, pady=8).pack()

    def _card(self, name, prof, is_cur, live_model=None):
        card = tk.Frame(
            self.inner, bg=CARD,
            highlightbackground=(ACCENT if is_cur else BORDER),
            highlightthickness=(2 if is_cur else 1),
        )
        card.pack(fill="x", pady=(0, px(9)))
        pad = tk.Frame(card, bg=CARD)
        pad.pack(fill="x", padx=px(16), pady=px(11))

        head = tk.Frame(pad, bg=CARD)
        head.pack(fill="x")

        meta = tk.Frame(pad, bg=CARD)
        meta.pack(fill="x", pady=(px(5), 0))

        res = tk.Label(meta, text="", font=(self.f, 9), fg=MUTED, bg=CARD, anchor="e")
        res.pack(side="right")

        btns = tk.Frame(head, bg=CARD)
        btns.pack(side="right")
        if not is_cur:
            button(btns, "切换", lambda n=name: self.use(n), "primary",
                   font=(self.f, 9), padx=17, pady=4).pack(side="right", padx=(px(6), 0))
        button(btns, "编辑", lambda n=name: self.edit(n), "ghost",
               font=(self.f, 9), padx=14, pady=4).pack(side="right", padx=(px(6), 0))
        button(btns, "测试", lambda n=name, lb=res: self.test(n, lb), "ghost",
               font=(self.f, 9), padx=14, pady=4).pack(side="right", padx=(px(6), 0))
        button(btns, "删除", lambda n=name: self.remove(n), "del",
               font=(self.f, 9), padx=14, pady=4).pack(side="right", padx=(px(6), 0))

        tk.Label(head, text="●", font=(self.f, 10), fg=(GREEN if is_cur else FAINT), bg=CARD).pack(side="left")
        tk.Label(head, text=name, font=(self.f, 11, "bold"), fg=TEXT, bg=CARD).pack(side="left", padx=(px(7), px(9)))
        if is_cur:
            tk.Label(head, text=" 使用中 ", font=(self.f, 8), fg=ACCENT, bg=ACCENT_SOFT).pack(side="left")
        tk.Label(head, text=prof.get("model") or "未设模型", font=(self.f, 9), fg=MUTED,
                 bg=CARD).pack(side="left", padx=(px(10), 0))
        if is_cur and live_model and prof.get("model") and live_model != prof.get("model"):
            tk.Label(head, text=f"config.toml 实际是 {live_model}", font=(self.f, 8),
                     fg=AMBER, bg=AMBER_SOFT).pack(side="left", padx=(px(8), 0))

        tk.Label(meta, text=f"网关 {core.host_of(prof.get('base_url'))}", font=(self.f, 9),
                 fg=MUTED, bg=CARD).pack(side="left")
        tk.Label(meta, text=f"Key {core.mask(prof.get('api_key'))}", font=(self.f, 9),
                 fg=MUTED, bg=CARD).pack(side="left", padx=(px(14), 0))
        if prof.get("note"):
            tk.Label(meta, text=str(prof.get("note"))[:30], font=(self.f, 9), fg=FAINT,
                     bg=CARD).pack(side="left", padx=(px(14), 0))

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
        self.say(text, "warn" if errors else "ok")
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
                self.detect_lbl.config(text="● " + text, fg=color)
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
