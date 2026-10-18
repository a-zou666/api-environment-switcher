#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tray_win — Windows 通知区域（托盘）图标，纯 ctypes，不依赖任何第三方库。

用法：
    tray = Tray(icon_path, "API 环境切换器")
    tray.start()
    ...
    while True:
        ev = tray.events.get()      # "show" / "exit"
"""
import ctypes
import ctypes.wintypes as wt
import os
import queue
import sys
import threading
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_TRAYICON = 0x8000 + 1
WM_SHOW = 0x8000 + 2          # 第二个实例发来的"把窗口叫出来"

WINDOW_CLASS = "ApictlTrayWnd"
WINDOW_TITLE = "apictl-tray"
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_NULL = 0x0000

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO = 0x1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
SM_CXSMICON = 49
MF_STRING = 0x0
MF_SEPARATOR = 0x800
TPM_RIGHTBUTTON = 0x2
TPM_RETURNCMD = 0x100
ID_SHOW, ID_EXIT = 1, 2

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wt.HICON),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
    ]


# 显式声明类型，64 位下才不会把句柄截断
kernel32.GetModuleHandleW.restype = wt.HMODULE
user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.RegisterWindowMessageW.restype = wt.UINT
user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
user32.TrackPopupMenu.restype = wt.BOOL
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.CreatePopupMenu.restype = wt.HMENU
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL
shell32.ExtractIconW.restype = wt.HICON
shell32.ExtractIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT]


class Tray:
    """托盘图标。事件通过 .events 队列交给主线程处理（"show" / "exit"）"""

    def __init__(self, icon_path=None, tip="API 环境切换器"):
        self.icon_path = icon_path
        self.tip = (tip or "")[:127]
        self.events = queue.Queue()
        self._hwnd = None
        self._hicon = None
        self._nid = None
        self._thread = None
        self._ready = threading.Event()
        self._taskbar_msg = 0
        self._wndproc = WNDPROC(self._on_message)  # 必须常驻，否则回调被回收
        self.ok = False

    # ---------------------------------------------------------- 生命周期
    def start(self, timeout=4.0):
        self._thread = threading.Thread(target=self._run, daemon=True, name="apictl-tray")
        self._thread.start()
        self._ready.wait(timeout)
        return self.ok

    def stop(self):
        if self._nid is not None and self._hwnd:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)

    def notify(self, title, text):
        """弹一个气泡提示"""
        if not self._nid:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = (title or "")[:63]
        nid.szInfo = (text or "")[:255]
        nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    # ---------------------------------------------------------- 内部
    def _run(self):
        try:
            hinst = kernel32.GetModuleHandleW(None)
            cls = WINDOW_CLASS
            wc = WNDCLASSW()
            wc.style = 0
            wc.lpfnWndProc = self._wndproc
            wc.hInstance = hinst
            wc.lpszClassName = cls
            user32.RegisterClassW(ctypes.byref(wc))  # 重复注册也无妨
            self._hwnd = user32.CreateWindowExW(
                0, cls, WINDOW_TITLE, 0, 0, 0, 0, 0, None, None, hinst, None
            )
            if not self._hwnd:
                return
            self._taskbar_msg = user32.RegisterWindowMessageW("TaskbarCreated")
            self.ok = self._add()
            self._ready.set()

            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            self.ok = False
        finally:
            self._ready.set()

    def _load_icon(self):
        size = user32.GetSystemMetrics(SM_CXSMICON) or 16
        if self.icon_path and os.path.exists(self.icon_path):
            h = user32.LoadImageW(None, self.icon_path, IMAGE_ICON, size, size, LR_LOADFROMFILE)
            if h:
                return h
        try:
            return shell32.ExtractIconW(kernel32.GetModuleHandleW(None), sys.executable, 0)
        except Exception:
            return None

    def _add(self):
        if not self._hwnd:
            return False
        self._hicon = self._load_icon()
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = self.tip
        self._nid = nid
        return bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))

    def _popup(self):
        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, MF_STRING, ID_SHOW, "打开主界面")
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "退出")
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self._hwnd)
        cmd = user32.TrackPopupMenu(
            hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self._hwnd, None
        )
        user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(hmenu)
        if cmd == ID_SHOW:
            self.events.put("show")
        elif cmd == ID_EXIT:
            self.events.put("exit")

    def _on_message(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_SHOW:
                self.events.put("show")
                return 0
            if msg == WM_TRAYICON:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.events.put("show")
                elif lparam == WM_RBUTTONUP:
                    self._popup()
                return 0
            if msg == WM_CLOSE:
                return self._destroy(hwnd)
            if msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            if self._taskbar_msg and msg == self._taskbar_msg:
                # 资源管理器重启后图标会丢，这里补回来
                self._add()
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _destroy(self, hwnd):
        if self._nid is not None:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        user32.DestroyWindow(hwnd)
        return 0


def notify_existing(timeout=2.0):
    """找到已经在跑的实例，让它把窗口弹出来；找到返回 True"""
    try:
        user32.FindWindowW.restype = wt.HWND
        user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
        end = time.time() + timeout
        while time.time() < end:
            hwnd = user32.FindWindowW(WINDOW_CLASS, WINDOW_TITLE)
            if hwnd:
                user32.PostMessageW(hwnd, WM_SHOW, 0, 0)
                return True
            time.sleep(0.15)
    except Exception:
        pass
    return False
