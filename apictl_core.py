#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apictl_core — API 环境档案的核心逻辑（CLI 与 GUI 共用）

只负责"读、改、切、测"，不做任何界面输出。
"""
import copy
import ctypes
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path

VERSION = "1.7.2"
APP_NAME = "API 环境切换器"

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
DATA = Path(os.environ.get("APICTL_HOME") or (Path.home() / ".apictl"))
CONFIG = CODEX_HOME / "config.toml"
AUTH = CODEX_HOME / "auth.json"
STORE = DATA / "profiles.json"
BACKUPS = DATA / "backups"
ENV_SH = DATA / "env.sh"
ENV_DOT = DATA / ".env"

ENV_KEY = "OPENAI_API_KEY"
ENV_BASE = "OPENAI_BASE_URL"
ENV_MODEL = "OPENAI_MODEL"
ENV_ALIASES = ("CODEX_API_KEY",)


class CoreError(Exception):
    pass


# 打包成无控制台窗口的 exe 后，任何子进程都不许弹黑框
_NO_WIN = 0x08000000 if os.name == "nt" else 0


def _run(cmd, **kw):
    kw.setdefault("creationflags", _NO_WIN)
    kw.setdefault("stdout", subprocess.PIPE)
    kw.setdefault("stderr", subprocess.DEVNULL)
    return subprocess.run(cmd, **kw)


def _popen(cmd, **kw):
    kw.setdefault("creationflags", _NO_WIN)
    return subprocess.Popen(cmd, **kw)


# ---------------------------------------------------------------- 小工具
def mask(key):
    if not key:
        return "-"
    if len(key) <= 12:
        return key[:3] + "…" + key[-2:]
    return key[:6] + "…" + key[-4:]


def slug(text, fallback="profile"):
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "-", text or "").strip("-._").lower()
    return s or fallback


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else (url or "-")


# ---------------------------------------------------------------- 进程枚举
class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def _snapshot():
    """一次系统快照拿全部进程，约 2~4ms（tasklist 要 600ms，没法每秒刷新）
    返回 [(pid, ppid, 进程名小写), ...]"""
    if os.name != "nt":
        return []
    try:
        k32 = ctypes.windll.kernel32
        snap = k32.CreateToolhelp32Snapshot(0x2, 0)   # TH32CS_SNAPPROCESS
        if snap in (0, -1):
            return []
        rows, e = [], _PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        try:
            if k32.Process32FirstW(snap, ctypes.byref(e)):
                while True:
                    rows.append((int(e.th32ProcessID), int(e.th32ParentProcessID),
                                 (e.szExeFile or "").lower()))
                    if not k32.Process32NextW(snap, ctypes.byref(e)):
                        break
        finally:
            k32.CloseHandle(snap)
        return rows
    except Exception:
        return []


def _pid_path(pid):
    """取进程完整路径（权限不足返回空串，不算错误）"""
    if os.name != "nt":
        return ""
    try:
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, int(pid))   # QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value or ""
            return ""
        finally:
            k32.CloseHandle(h)
    except Exception:
        return ""


def list_processes():
    """返回 {进程名小写: [pid, ...]}"""
    procs = {}
    for pid, _ppid, name in _snapshot():
        procs.setdefault(name, []).append(pid)
    return procs


def _tree_of(names, path_prefix=""):
    """按进程名（可选路径前缀）圈出整棵树，返回 (全部 pid, 根 pid)"""
    rows = _snapshot()
    pids = set()
    for pid, _ppid, name in rows:
        if name not in names:
            continue
        if path_prefix and not _pid_path(pid).lower().startswith(path_prefix):
            continue
        pids.add(pid)
    changed = True
    while changed:
        changed = False
        for pid, ppid, _n in rows:
            if ppid in pids and pid not in pids:
                pids.add(pid)
                changed = True
    roots = [pid for pid, ppid, _n in rows if pid in pids and ppid not in pids]
    return pids, roots


def codex_running():
    procs = list_processes()
    return bool(procs.get("chatgpt.exe") or procs.get("codex.exe"))


# ---------------------------------------------------------------- TOML 手术
def _norm_header(s):
    return re.sub(r'[\s"]', "", s.strip().strip("[]"))


def _find_section(lines, header):
    h = _norm_header(header)
    start = None
    for i, line in enumerate(lines):
        st = line.strip()
        if st.startswith("[["):
            if start is not None:
                return start, i
            continue
        if st.startswith("[") and st.endswith("]"):
            if start is not None:
                return start, i
            if _norm_header(st) == h:
                start = i
    return (start, len(lines)) if start is not None else None


def _top_end(lines):
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            return i
    return len(lines)


def _toml_val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _set_kv(lines, lo, hi, kv):
    offset = 0
    for k, v in kv.items():
        pat = re.compile(r"^\s*" + re.escape(k) + r"\s*=")
        found = None
        for i in range(lo, hi + offset):
            if pat.match(lines[i]):
                found = i
                break
        if found is None:
            lines.insert(lo, f"{k} = {_toml_val(v)}")
            offset += 1
        else:
            lines[found] = f"{k} = {_toml_val(v)}"


def apply_config(profile):
    text = CONFIG.read_text(encoding="utf-8", errors="replace") if CONFIG.exists() else ""
    lines = text.splitlines()

    provider = profile.get("provider") or "custom"
    top = {"model_provider": provider}
    if profile.get("model"):
        top["model"] = profile["model"]
    for k, v in (profile.get("toml") or {}).items():
        top[k] = v
    _set_kv(lines, 0, _top_end(lines), top)

    header = f"model_providers.{provider}"
    # 新版 Codex 已经不吃 api_key 字段了（会报“无法识别的配置项”并导致 401），
    # 官方做法是 env_key 指向环境变量；我们本来就强制写全局环境变量，正好对上。
    block = {
        "name": provider,
        "wire_api": profile.get("wire_api") or "responses",
        "base_url": (profile.get("base_url") or "").rstrip("/"),
        "env_key": ENV_KEY,
    }
    rng = _find_section(lines, header)
    if rng is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{header}]")
        _set_kv(lines, len(lines), len(lines), block)
    else:
        _set_kv(lines, rng[0] + 1, rng[1], block)
        # 顺手清掉旧的 api_key 行，避免每次启动都弹“无法识别的配置项”
        again = _find_section(lines, header)
        if again:
            s, e = again
            lines[s + 1:e] = [l for l in lines[s + 1:e] if not re.match(r"^\s*api_key\s*=", l)]

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")

    # 桌面版的模型下拉不读 config.toml，读的是 model-catalogs 里的目录文件
    sync_catalog(profile.get("model") or "")


DEFAULT_CATALOG = CODEX_HOME / "model-catalogs" / "default.json"


def catalog_path():
    """config.toml 里 model_catalog_json 指向的模型目录文件"""
    if CONFIG.exists():
        try:
            for line in CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
                mm = re.match(r'^\s*model_catalog_json\s*=\s*["\'](.+?)["\']\s*$', line)
                if mm:
                    p = Path(mm.group(1))
                    return p if p.is_absolute() else (CODEX_HOME / p)
        except Exception:
            pass
    return DEFAULT_CATALOG


def pretty_model(slug_text):
    """"gpt-6.1-sol" -> "GPT-6.1-Sol"（界面会去掉 GPT- 前缀显示成 6.1 Sol）"""
    body = re.sub(r"(?i)^gpt-?[_-]?", "", (slug_text or "").strip())
    if not body:
        return (slug_text or "").strip()
    parts = []
    for seg in body.replace("_", "-").split("-"):
        parts.append(seg[:1].upper() + seg[1:] if seg[:1].isalpha() else seg)
    return "GPT-" + "-".join(parts)


def _pool_path(path):
    return path.with_name(path.name + ".apictl-pool")


def load_pool(path):
    """记录见过的每个模型的完整规格，切换时直接取回，避免反复克隆丢失参数"""
    try:
        data = json.loads(_pool_path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_pool(path, pool):
    try:
        _pool_path(path).write_text(
            json.dumps(pool, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    except Exception:
        pass


def sync_catalog(model):
    """把桌面版模型目录收敛成"只含当前档案模型"的一份。

    桌面版的下拉列表完全来自这个文件（config.toml 的 model 不参与渲染），
    以前是往目录里"追加"，结果切一次就多一个模型，和档案里选的模型对不上。
    现在改成：保留当前模型的完整规格，其余条目移出列表（规格存进 pool 备用）。
    """
    model = (model or "").strip()
    path = catalog_path()
    if not model:
        return {"ok": False, "reason": "没有模型名"}
    if not path.exists():
        return {"ok": False, "reason": "没有模型目录文件"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        models = data.get("models") or []
    except Exception as e:
        return {"ok": False, "reason": f"目录文件读不了：{e}"}
    if not isinstance(models, list) or not models:
        return {"ok": False, "reason": "目录里没有模型规格"}

    # 目录里出现过的模型规格全部收进 pool（首次见到就记下来）
    pool = load_pool(path)
    for m in models:
        slug = (m.get("slug") or "").strip()
        if slug and slug not in pool:
            pool[slug] = m
    save_pool(path, pool)

    if len(models) == 1 and (models[0].get("slug") or "") == model and models[0].get("visibility") == "list":
        return {"ok": True, "action": "kept", "path": str(path)}

    bak = path.with_name(path.name + ".apictl-bak")
    if not bak.exists():
        try:
            shutil.copy2(path, bak)
        except Exception:
            pass

    if model in pool:
        keep = copy.deepcopy(pool[model])
    else:
        # 从没见过的模型：拿当前第一个的规格做模板，只换名字
        keep = copy.deepcopy(models[0])
    keep["slug"] = model
    keep["display_name"] = pretty_model(model)
    keep["description"] = pretty_model(model)
    keep["visibility"] = "list"

    data["models"] = [keep]
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return {"ok": False, "reason": f"目录文件写不了：{e}"}
    return {"ok": True, "action": "synced", "path": str(path), "model": model}


def apply_auth(profile):
    data = {}
    if AUTH.exists():
        try:
            data = json.loads(AUTH.read_text(encoding="utf-8") or "{}")
        except Exception:
            data = {}
    data[ENV_KEY] = profile.get("api_key") or ""
    AUTH.parent.mkdir(parents=True, exist_ok=True)
    AUTH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def detect_live():
    if not CONFIG.exists():
        return None
    lines = CONFIG.read_text(encoding="utf-8", errors="replace").splitlines()
    provider = model = base = key = None
    wire = "responses"
    for i in range(_top_end(lines)):
        mm = re.match(r'^\s*model_provider\s*=\s*["\']([^"\']+)["\']', lines[i])
        if mm:
            provider = mm.group(1)
            break
    for i in range(_top_end(lines)):
        mm = re.match(r'^\s*model\s*=\s*["\']([^"\']+)["\']', lines[i])
        if mm:
            model = mm.group(1)
            break
    provider = provider or "custom"
    rng = _find_section(lines, f"model_providers.{provider}")
    if rng:
        for i in range(rng[0] + 1, rng[1]):
            for name, pat in (
                ("base_url", r'^\s*base_url\s*=\s*["\'](.*)["\']\s*$'),
                ("api_key", r'^\s*api_key\s*=\s*["\'](.*)["\']\s*$'),
                ("wire_api", r'^\s*wire_api\s*=\s*["\'](.*)["\']\s*$'),
            ):
                mm = re.match(pat, lines[i])
                if mm:
                    if name == "base_url":
                        base = mm.group(1)
                    elif name == "api_key":
                        key = mm.group(1)
                    else:
                        wire = mm.group(1)
    return {"provider": provider, "base_url": base, "api_key": key, "model": model, "wire_api": wire}


# ---------------------------------------------------------------- 档案库
def empty_store():
    return {"version": 1, "current": None, "previous": None, "profiles": {}}


def save_store(store):
    DATA.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        os.chmod(STORE, 0o600)
    except Exception:
        pass
    return STORE


def load_store():
    """读取档案库；不存在时自动把当前 config.toml 收编进来"""
    if STORE.exists():
        try:
            data = json.loads(STORE.read_text(encoding="utf-8"))
            data.setdefault("profiles", {})
            data.setdefault("current", None)
            return data
        except Exception:
            shutil.copy2(STORE, STORE.with_suffix(".broken.json"))

    store = empty_store()
    live = detect_live()
    if live and live.get("api_key") and live.get("base_url"):
        name = slug(host_of(live["base_url"]).split(".")[0])
        store["profiles"][name] = {
            "provider": live["provider"],
            "base_url": live["base_url"],
            "api_key": live["api_key"],
            "model": live["model"],
            "wire_api": live["wire_api"],
            "note": "从当前 config.toml 自动导入",
        }
        store["current"] = name
        save_store(store)
    else:
        save_store(store)
    return store


def current_name(store):
    """优先按真实生效配置反查，其次用记录值"""
    live = detect_live()
    if live and live.get("api_key"):
        for name, p in store.get("profiles", {}).items():
            if p.get("api_key") == live.get("api_key") and (
                (p.get("base_url") or "").rstrip("/") == (live.get("base_url") or "").rstrip("/")
            ):
                return name
    return store.get("current")


# ---------------------------------------------------------------- 环境文件
def build_env_pairs(profile):
    pairs = [(ENV_KEY, profile.get("api_key") or "")]
    pairs += [(a, profile.get("api_key") or "") for a in ENV_ALIASES]
    if profile.get("base_url"):
        pairs.append((ENV_BASE, profile["base_url"]))
    if profile.get("model"):
        pairs.append((ENV_MODEL, profile["model"]))
    pairs += [(k, str(v)) for k, v in (profile.get("env") or {}).items()]
    return pairs


def write_env_files(profile):
    pairs = build_env_pairs(profile)
    DATA.mkdir(parents=True, exist_ok=True)
    sh = ["# 由 API 环境切换器自动生成，重新切换一次即可覆盖"]
    dotenv = ["# 由 API 环境切换器自动生成"]
    for k, v in pairs:
        v = str(v)
        esc = v.replace("'", "'\"'\"'")
        sh.append(f"export {k}='{esc}'")
        dotenv.append(f"{k}={v}")
    ENV_SH.write_text("\n".join(sh) + "\n", encoding="utf-8")
    ENV_DOT.write_text("\n".join(dotenv) + "\n", encoding="utf-8")
    return pairs


# ---------------------------------------------------------------- 全局环境变量
ENV_SUBKEY = r"Environment"


def _env_key(write=False):
    import winreg

    flags = winreg.KEY_READ | (winreg.KEY_SET_VALUE if write else 0)
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_SUBKEY, 0, flags)


def _broadcast_env():
    """告诉资源管理器环境变量变了，新开的进程才能立刻拿到"""
    if os.name != "nt":
        return
    try:
        import ctypes

        res = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 0x2, 3000, ctypes.byref(res)
        )
    except Exception:
        pass


def read_global_env(names):
    if os.name != "nt":
        return {}
    import winreg

    out = {}
    try:
        with _env_key() as k:
            for n in names:
                try:
                    out[n] = winreg.QueryValueEx(k, n)[0]
                except OSError:
                    pass
    except OSError:
        pass
    return out


def write_global_env(pairs, stale=()):
    """强制把变量写进用户级全局环境变量（HKCU\\Environment），对所有新进程生效"""
    if os.name != "nt":
        raise CoreError("只有 Windows 支持写入全局环境变量")
    import winreg

    written = 0
    with _env_key(write=True) as k:
        for name in stale:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass
        for name, value in pairs:
            value = str(value)
            kind = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ
            winreg.SetValueEx(k, name, 0, kind, value)
            written += 1
    for name, value in pairs:
        os.environ[name] = str(value)
    _broadcast_env()
    return written


def sync_global_env(profile, previous_keys=()):
    """写入当前档案的全部环境变量，并清掉上一个档案留下的多余变量"""
    pairs = build_env_pairs(profile)
    keys = [k for k, _ in pairs]
    stale = [
        k
        for k in (previous_keys or [])
        if k not in keys and k.split("_")[0].upper() in ("OPENAI", "CODEX", "ANTHROPIC")
    ]
    n = write_global_env(pairs, stale)
    return n, keys


def backup_current(tag, keep=30):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = BACKUPS / f"{stamp}-{slug(tag)}"
    n = 1
    while dest.exists():
        dest = BACKUPS / f"{stamp}-{slug(tag)}-{n}"
        n += 1
    dest.mkdir(parents=True, exist_ok=True)
    for f in (CONFIG, AUTH):
        if f.exists():
            shutil.copy2(f, dest / f.name)
    dirs = sorted([d for d in BACKUPS.iterdir() if d.is_dir()])
    for old in dirs[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return dest


def last_backup():
    if not BACKUPS.exists():
        return None
    dirs = sorted([d for d in BACKUPS.iterdir() if d.is_dir()])
    return dirs[-1] if dirs else None


# ---------------------------------------------------------------- 核心操作
def use_profile(store, name, persist=True):
    """切换档案：改配置 + 强制写全局环境变量，返回结果信息字典"""
    if name == "-":
        name = store.get("previous") or ""
        if not name:
            raise CoreError("没有上一个档案可以回退")
    prof = store.get("profiles", {}).get(name)
    if not prof:
        near = [n for n in store.get("profiles", {}) if name.lower() in n.lower()]
        tip = f"，你是想用 {'、'.join(near)} 吗？" if near else ""
        raise CoreError(f"没有名为“{name}”的档案{tip}")
    if not prof.get("api_key"):
        raise CoreError("该档案缺少 API Key")
    if not prof.get("base_url"):
        raise CoreError("该档案缺少网关地址")

    before = current_name(store)
    bak = backup_current(name)
    apply_config(prof)
    apply_auth(prof)
    write_env_files(prof)

    # 无条件写全局环境变量，不给选择
    env_count, env_keys = sync_global_env(prof, store.get("env_keys") or [])

    store["previous"] = before if before and before != name else store.get("previous")
    store["current"] = name
    store["env_keys"] = env_keys
    save_store(store)

    return {
        "name": name,
        "profile": prof,
        "backup": bak,
        "persisted": env_count,
        "previous": store.get("previous"),
        "running": codex_running(),
    }


def add_profile(store, name, base_url, api_key, model="", provider="custom",
                wire_api="responses", note="", env=None, use=False):
    if not name:
        raise CoreError("名称不能为空")
    if not base_url:
        raise CoreError("网关地址不能为空")
    if not api_key:
        raise CoreError("API Key 不能为空")
    name = slug(name)
    store["profiles"][name] = {
        "provider": provider or "custom",
        "base_url": base_url.strip(),
        "api_key": api_key.strip(),
        "model": (model or "").strip(),
        "wire_api": wire_api or "responses",
        "note": note or "",
        "env": env or {},
    }
    save_store(store)
    if use:
        use_profile(store, name)
    return name


def update_profile(store, name, **fields):
    prof = store.get("profiles", {}).get(name)
    if not prof:
        raise CoreError(f"没有名为“{name}”的档案")
    changed = False
    for k in ("base_url", "api_key", "model", "provider", "wire_api", "note", "env"):
        v = fields.get(k)
        if v not in (None, ""):
            prof[k] = v
            changed = True
    if not changed:
        raise CoreError("没有要修改的内容")
    active = store.get("current") == name or current_name(store) == name
    save_store(store)
    if active:
        use_profile(store, name)
    return prof


def rename_profile(store, old, new):
    if old not in store["profiles"]:
        raise CoreError(f"没有名为“{old}”的档案")
    new = slug(new)
    if not new:
        raise CoreError("名称不能为空")
    if new != old and new in store["profiles"]:
        raise CoreError(f"“{new}”已存在")
    items = list(store["profiles"].items())
    store["profiles"] = {new if k == old else k: v for k, v in items}
    if store.get("current") == old:
        store["current"] = new
    if store.get("previous") == old:
        store["previous"] = new
    save_store(store)
    return new


def delete_profile(store, name):
    if name not in store.get("profiles", {}):
        raise CoreError(f"没有名为“{name}”的档案")
    del store["profiles"][name]
    if store.get("current") == name:
        store["current"] = None
    if store.get("previous") == name:
        store["previous"] = None
    save_store(store)


_PROXY_CACHE = {"at": 0.0, "url": ""}
DEFAULT_PROXY_PORTS = (10808, 10809, 7890, 1080, 8080)


def _port_open(host, port, timeout=0.15):
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _system_proxy():
    """读 Windows 系统代理（IE 设置），拿不到就返回空串"""
    if os.name != "nt":
        return ""
    try:
        import winreg

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            try:
                with winreg.OpenKey(root, path) as k:
                    enable = winreg.QueryValueEx(k, "ProxyEnable")[0]
                    if not enable:
                        continue
                    server = winreg.QueryValueEx(k, "ProxyServer")[0]
            except OSError:
                continue
            if not server:
                continue
            if "=" in server:  # "http=127.0.0.1:10809;https=127.0.0.1:10808"
                parts = dict(
                    (p.split("=", 1)[0].strip().lower(), p.split("=", 1)[1].strip())
                    for p in server.split(";")
                    if "=" in p
                )
                server = parts.get("https") or parts.get("http") or ""
            if server:
                return server if "://" in server else "http://" + server
    except Exception:
        pass
    return ""


def detect_proxy(force=False):
    """找出这台机器上可用的本地代理（10808 优先），一分钟内复用结果"""
    now = time.time()
    if not force and now - _PROXY_CACHE["at"] < 60:
        return _PROXY_CACHE["url"]
    url = (os.environ.get("APICTL_PROXY") or "").strip()
    if not url:
        url = _system_proxy()
    if not url:
        for port in DEFAULT_PROXY_PORTS:
            if _port_open("127.0.0.1", port):
                url = f"http://127.0.0.1:{port}"
                break
    _PROXY_CACHE.update(at=now, url=url)
    return url


def _opener(proxy):
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _short_proxy(url):
    return url.replace("http://", "").replace("https://", "").rstrip("/")


API_UA = f"apictl/{VERSION}"
# 部分网关（new-api / one-api 系）按客户端指纹放行，只认官方 CLI 的 UA，
# 其余一律回 "unauthorized client detected" 这种误导性的 401
COMPAT_UA = "codex_cli_rs/0.20.0 (Windows 10.0; x86_64) WindowsTerminal"
BLOCK_MARKS = ("unauthorized client", "unauthorized_client", "非法客户端",
               "client detected", "forbidden client")


def _is_html(body, ctype=""):
    head = (body or "").lstrip()[:512].lower()
    return ("text/html" in (ctype or "").lower()
            or head.startswith("<!doctype") or head.startswith("<html"))


def _client_blocked(body):
    low = (body or "").lower()
    return any(k in low for k in BLOCK_MARKS)


def _api_bases(base):
    """候选 API 根：网关多数把接口挂在 /v1 下，先试 /v1，再试原样"""
    b = (base or "").rstrip("/")
    if not b:
        return []
    if b.endswith(("/v1", "/v1beta")):
        return [b]
    return [b + "/v1", b]


def _model_ids(body):
    try:
        data = json.loads(body)
    except Exception:
        return []
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]


def _hint_for(status, body):
    low = (body or "").lower()
    if _client_blocked(body):
        return "网关按客户端身份放行，拒的是 apictl 的 UA，不是 key 本身"
    if status == 402 or "quota" in low or "budget" in low or "额度" in low:
        return "上游额度池已耗尽；令牌面板显示「无限额度」不代表供应商侧还有额度"
    if status == 503 or "无可用渠道" in low or "no available channel" in low:
        return "该分组下这个模型没有可用渠道，换个模型或换个分组"
    if status in (401, 403):
        return "API Key 无效或没有权限"
    if status == 404:
        return "网关没有 /models 接口，但聊天接口可能是通的"
    if status == 429:
        return "请求太频繁，被上游限流"
    return ""


def _probe(url, key, proxy, timeout, ua=API_UA):
    """请求一次 /models，把 HTML 页面、HTTP 错误、网络异常分开报告"""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": ua,
        },
    )
    try:
        with _opener(proxy).open(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "") or ""
            body = r.read(8000).decode("utf-8", "replace")
            return {"kind": "html" if _is_html(body, ctype) else "body",
                    "status": r.status, "body": body}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read(600).decode("utf-8", "replace").strip()
        except Exception:
            pass
        return {"kind": "http", "status": e.code, "body": detail}
    except Exception as e:
        return {"kind": "exc", "error": e}


def test_endpoint(profile, timeout=15):
    """测试 key / 网关连通性（不抛网络异常）；直连失败会自动改用本地代理重试"""
    base = (profile.get("base_url") or "").rstrip("/")
    key = profile.get("api_key") or ""
    if not base or not key:
        return {"ok": False, "error": "缺少网关地址或 API Key", "hint": ""}

    host = host_of(base)
    is_local = host.startswith(("127.", "localhost", "0.0.0.0", "192.168.", "10.", "::1"))
    proxy = "" if is_local else detect_proxy()

    routes = [("direct", "", min(timeout, 6) if proxy else timeout)]
    if proxy:
        routes.append(("proxy", proxy, max(timeout, 12)))

    html_hit = None
    last_exc = None
    for api_base in _api_bases(base):
        url = api_base + "/models"
        for via, px, tmo in routes:
            t0 = time.time()
            r = _probe(url, key, px, tmo)
            ms = int((time.time() - t0) * 1000)
            compat = False

            # 网关按 UA 拦人时，换个官方 CLI 身份再试一次
            if r["kind"] == "http" and _client_blocked(r["body"]):
                again = _probe(url, key, px, tmo, COMPAT_UA)
                if again["kind"] in ("body", "html"):
                    r, compat = again, True
                elif again["kind"] == "http":
                    r = again

            if r["kind"] == "body":
                res = {"ok": True, "status": r["status"], "ms": ms,
                       "models": _model_ids(r["body"]), "url": url,
                       "api_base": api_base, "via": via}
                if compat:
                    res["compat_ua"] = True
                if via == "proxy":
                    res["proxy"] = _short_proxy(px)
                if api_base != base:
                    res["fix_base"] = api_base
                return res

            if r["kind"] == "html":
                # 打到网关的网页控制台了：这个 base 不对，换下一个候选
                html_hit = {"status": r["status"], "url": url, "ms": ms,
                            "via": via, "api_base": api_base}
                break

            if r["kind"] == "http":
                out = {"ok": False, "status": r["status"], "ms": ms,
                       "error": (r["body"] or f"HTTP {r['status']}")[:300],
                       "hint": _hint_for(r["status"], r["body"]), "url": url,
                       "api_base": api_base, "via": via}
                if compat:
                    out["compat_ua"] = True
                if via == "proxy":
                    out["proxy"] = _short_proxy(px)
                return out

            last_exc = r.get("error")
            continue

    if html_hit:
        return {"ok": False, "status": html_hit["status"], "ms": html_hit["ms"],
                "error": f"{html_hit['url']} 返回的是网页（HTML），不是接口 JSON",
                "hint": "网关地址少了 /v1，改成 "
                        + html_hit["url"].rsplit("/models", 1)[0] + " 再试",
                "url": html_hit["url"], "via": html_hit["via"]}

    msg = str(last_exc or "连接失败")
    low = msg.lower()
    hint = ""
    if "ssl" in low:
        hint = "TLS 握手失败，多为代理或网关拦截"
    elif "tunnel" in low or "proxy" in low or "502" in low:
        hint = "代理连接失败，确认代理端口是否可用"
    elif "timed out" in low:
        hint = "连接超时，域名不通或需要代理"
    elif "10061" in low or "refused" in low:
        hint = "目标没有服务在监听"
    if proxy:
        hint = (hint + " · " if hint else "") + f"已试过代理 {_short_proxy(proxy)}"
    return {"ok": False, "status": None, "error": msg, "hint": hint, "url": "/".join(_api_bases(base)) + "/models", "via": ""}


def fetch_models(base_url, api_key, timeout=15):
    """从网关拉取模型列表，只返回结果不抛异常"""
    if not base_url:
        return {"ok": False, "status": None, "error": "缺少网关地址", "hint": ""}
    if not api_key:
        return {"ok": False, "status": None, "error": "缺少 API Key", "hint": ""}
    r = test_endpoint({"base_url": base_url, "api_key": api_key}, timeout=timeout)
    if r.get("ok"):
        models = sorted({m for m in (r.get("models") or []) if m}, key=str.lower)
        out = {"ok": True, "models": models, "ms": r.get("ms", 0),
               "via": r.get("via"), "proxy": r.get("proxy", ""),
               "api_base": r.get("api_base")}
        for k in ("fix_base", "compat_ua"):
            if r.get(k):
                out[k] = r[k]
        return out
    return {"ok": False, "status": r.get("status"), "error": r.get("error"),
            "hint": r.get("hint"), "via": r.get("via"),
            "api_base": r.get("api_base")}


# ---------------------------------------------------------------- 客户端检测
SCAN_DIRS = (
    r"%LOCALAPPDATA%\Programs",
    r"%LOCALAPPDATA%\Programs\OpenAI",
    r"%LOCALAPPDATA%\CodexPatched",
    r"%LOCALAPPDATA%\OpenAI",
    r"%LOCALAPPDATA%\ChatGPT",
    r"%APPDATA%\npm",
    r"%USERPROFILE%\.local\bin",
    r"%USERPROFILE%\.codex\bin",
    r"%PROGRAMFILES%\Codex",
    r"%PROGRAMFILES%\ChatGPT",
    r"%PROGRAMFILES%\OpenAI",
    r"%PROGRAMFILES(X86)%\Codex",
    r"%PROGRAMFILES(X86)%\ChatGPT",
)

LNK_DIRS = (
    r"%USERPROFILE%\Desktop",
    r"%PUBLIC%\Desktop",
    r"%APPDATA%\Microsoft\Windows\Start Menu\Programs",
    r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs",
)

EXE_NAMES = ("chatgpt.exe", "codex.exe", "chatgpt.bat", "chatgpt.cmd", "codex.bat", "codex.cmd")

EDITOR_DIRS = (
    ("VSCode", r"%USERPROFILE%\.vscode\extensions"),
    ("VSCode 预览版", r"%USERPROFILE%\.vscode-insiders\extensions"),
    ("Cursor", r"%USERPROFILE%\.cursor\extensions"),
    ("VSCode 共享", r"%USERPROFILE%\.vscode-shared\extensions"),
)


def _expand(p):
    return os.path.expandvars(os.path.expanduser(str(p)))


def _ver_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "0"))[:4])


# ---------------------------------------------------------------- 商店版（MSIX）
APPX_REPO = (
    r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion"
    r"\AppModel\Repository\Packages"
)


def _manifest_launch(pkg_dir):
    """从 AppxManifest.xml 取 GUI 入口：(exe 相对路径, Application Id)"""
    exe_rel, appid = "app/ChatGPT.exe", "App"
    man = Path(pkg_dir) / "AppxManifest.xml"
    try:
        if not man.exists():
            return exe_rel, appid
        text = man.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return exe_rel, appid

    picks = []
    for m in re.finditer(r"<Application\b([^>]*)>", text):
        attrs = m.group(1)
        e = re.search(r'Executable="([^"]+)"', attrs)
        a = re.search(r'\bId="([^"]+)"', attrs)
        if e and a:
            picks.append((e.group(1).replace("\\", "/"), a.group(1)))
    for rel, aid in picks:
        if rel.lower().endswith("chatgpt.exe"):
            return rel, aid
    return picks[0] if picks else (exe_rel, appid)


def find_msix_apps():
    """从 AppModel 仓库找商店安装的 ChatGPT / Codex 桌面版（普通权限可读）"""
    if os.name != "nt":
        return []
    try:
        import winreg
    except Exception:
        return []

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPX_REPO)
    except Exception:
        return []

    best = {}
    try:
        total = winreg.QueryInfoKey(root)[0]
        for i in range(total):
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                continue
            low = name.lower()
            if not (low.startswith("openai.") or "chatgpt" in low):
                continue
            try:
                sub = winreg.OpenKey(root, name)
                folder, _ = winreg.QueryValueEx(sub, "PackageRootFolder")
                sub.Close()
            except Exception:
                continue
            m = re.match(r"^(?P<name>[^_]+)_(?P<ver>\d+(?:\.\d+){1,3})_", name)
            if not m:
                continue
            family = f"{m.group('name')}_{name.rsplit('_', 1)[-1]}"
            ver = m.group("ver")
            cur = best.get(family)
            if cur and _ver_key(cur["version"]) >= _ver_key(ver):
                continue
            best[family] = {"family": family, "version": ver, "dir": str(folder)}
    finally:
        try:
            root.Close()
        except Exception:
            pass

    out = []
    for item in best.values():
        rel, appid = _manifest_launch(item["dir"])
        exe = Path(item["dir"]) / rel
        try:
            exists = exe.exists()
        except Exception:
            exists = False
        if not exists:
            continue
        out.append({"path": str(exe), "appdir": item["dir"],
                    "aumid": f"{item['family']}!{appid}",
                    "version": item["version"], "source": "商店安装"})
    return out


def _walk_limited(root, depth=3):
    """有限深度遍历，避免扫盘拖慢启动"""
    root = Path(_expand(root))
    if not root.is_dir():
        return
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        if len(Path(dirpath).parts) - base >= depth:
            dirnames[:] = []
        yield Path(dirpath), filenames


def _lnk_targets(path):
    """从 .lnk 里抠出目标可执行文件（快捷方式常指向自定义安装目录）"""
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return []
    hits = re.findall(r"[A-Za-z]:\\[\x20-\x7e]{2,240}?\.(?:exe|bat|cmd)", raw.decode("latin-1", "ignore"))
    if not hits:
        hits = re.findall(
            r"[A-Za-z]:\\[\x20-\x7e]{2,240}?\.(?:exe|bat|cmd)", raw.decode("utf-16-le", "ignore")
        )
    out = []
    for h in hits:
        p = _expand(h)
        if os.path.basename(p).lower() in EXE_NAMES and os.path.exists(p):
            out.append(p)
    return out


def _is_cli_path(p):
    low = str(p).lower()
    return "\\bin\\" in low and "programs" not in low


def _pid_alive(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False
    try:
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return False


_DISC = {"t": 0.0, "apps": [], "editors": []}
DISC_TTL = 20.0


def discover_clients(ttl=DISC_TTL):
    """装了哪些客户端（不含运行状态）。扫盘开销大，缓存 20 秒，运行状态每次现查"""
    now = time.time()
    if _DISC["apps"] and now - _DISC["t"] < ttl:
        return _DISC["apps"], _DISC["editors"]

    apps, seen = [], set()

    def add(path, source, aumid="", appdir=""):
        try:
            p = os.path.normpath(str(path))
        except Exception:
            return
        key = os.path.normcase(p)
        if key in seen or not os.path.exists(p):
            return
        base = os.path.basename(p).lower()
        if base.startswith("chatgpt"):
            label, kind = "ChatGPT 桌面版", "chatgpt"
        elif base.startswith("codex"):
            if _is_cli_path(p) or base.endswith((".bat", ".cmd")):
                label, kind = "Codex CLI", "cli"
            else:
                label, kind = "Codex 桌面版", "codex"
        else:
            return
        seen.add(key)
        apps.append({"label": label, "kind": kind, "path": p, "source": source,
                     "aumid": aumid, "appdir": appdir})

    # 0) 商店安装的（MSIX 装在 WindowsApps 里，普通扫目录找不到）
    for it in find_msix_apps():
        add(it["path"], it["source"], it["aumid"], it["appdir"])

    # 1) 常见安装目录
    for d in SCAN_DIRS:
        for folder, files in _walk_limited(d):
            for f in files:
                if f.lower() in EXE_NAMES:
                    add(folder / f, "安装目录")

    # 2) PATH
    for name in ("codex", "codex.exe", "codex.cmd", "chatgpt"):
        w = shutil.which(name)
        if w:
            add(w, "PATH")

    # 3) 桌面与开始菜单的快捷方式
    for d in LNK_DIRS:
        root = Path(_expand(d))
        if not root.is_dir():
            continue
        try:
            lnks = list(root.rglob("*.lnk"))
        except Exception:
            lnks = []
        for lnk in lnks:
            if not re.search(r"codex|chatgpt|openai", lnk.stem, re.I):
                continue
            for t in _lnk_targets(lnk):
                add(t, "快捷方式")

    # 4) 编辑器里的 Codex / ChatGPT 插件
    editors = []
    for name, d in EDITOR_DIRS:
        root = Path(_expand(d))
        if not root.is_dir():
            continue
        try:
            subs = [x.name for x in root.iterdir() if x.is_dir()]
        except Exception:
            subs = []
        hits = [s for s in subs if re.search(r"openai[.\-]|codex|chatgpt", s, re.I)]
        for h in hits:
            editors.append({"editor": name, "ext": h})

    # 5) 缓存结果
    _DISC.update({"t": now, "apps": apps, "editors": editors})
    return apps, editors


def _proc_names(app):
    """这个客户端的主进程名（子进程靠父子关系自动兜进来）"""
    if app.get("kind") == "chatgpt":
        return {"chatgpt.exe"}
    return {"codex.exe"}


def _app_pids(app):
    """(整树 pid 集合, 根 pid 列表) —— 每秒刷新用，只读快照，成本几毫秒"""
    return _tree_of(_proc_names(app), (app.get("appdir") or "").lower())


def detect_clients(force=False):
    """找出这台机器上的 ChatGPT 桌面版 / Codex，并附上实时运行状态"""
    apps_meta, editors = discover_clients(0.0 if force else DISC_TTL)
    apps = []
    for meta in apps_meta:
        item = dict(meta)
        pids, roots = _app_pids(item)
        item["pids"] = sorted(pids)
        item["roots"] = roots
        apps.append(item)

    # 装了桌面版时，它自带的引擎（%LOCALAPPDATA%\OpenAI\Codex\bin\codex.exe）不算独立客户端
    engine_dir = os.path.normcase(_expand(r"%LOCALAPPDATA%\OpenAI\Codex"))
    if any(a.get("kind") == "chatgpt" for a in apps):
        apps = [a for a in apps
                if not (a.get("kind") in ("codex", "cli")
                        and os.path.normcase(a["path"]).startswith(engine_dir))]

    # ChatGPT 应用自己会拉起 codex.exe（内嵌引擎），别把它错认成"还开着 Codex CLI"
    app_tree = set()
    for a in apps:
        if a.get("kind") == "chatgpt":
            app_tree |= set(a["pids"])
    for a in apps:
        if a.get("kind") in ("codex", "cli") and not a.get("appdir"):
            a["pids"] = [p for p in a["pids"] if p not in app_tree]
            a["roots"] = [p for p in a.get("roots", []) if p not in app_tree]

    for a in apps:
        a["running"] = bool(a["pids"])

    return {"apps": apps, "editors": editors,
            "only_config": CONFIG.exists() and not apps,
            "procs": list_processes()}


def describe_clients(clients):
    """每个客户端都带状态：运行中 / 已关闭（关了就写关闭，别让人以为还在跑）"""
    bits = []
    for a in clients.get("apps", []):
        bits.append(a["label"] + (" 运行中" if a.get("running") else " 已关闭"))
    for e in clients.get("editors", []):
        bits.append(f"{e['editor']} 插件")
    if not bits:
        return "未检测到 Codex 或 ChatGPT" + ("（仅有旧配置）" if clients.get("only_config") else "")
    return " · ".join(bits)


def _kill(pids):
    for pid in pids:
        try:
            _run(["taskkill", "/F", "/PID", str(pid)], timeout=10)
        except Exception:
            pass


def _kill_tree(app, pids, roots):
    """整棵树一起结束：先按根 taskkill /T，再逐个补刀
    （只杀渲染进程的话，界面只是刷新一下，这就是“看起来没重启”的原因）"""
    for pid in roots or list(pids):
        try:
            _run(["taskkill", "/F", "/T", "/PID", str(pid)], timeout=12)
        except Exception:
            pass
    left = {p for p in pids if _pid_alive(p)}
    if left:
        _kill(sorted(left))
    return left


def _wait_gone(pids, timeout=6.0):
    end = time.time() + timeout
    while time.time() < end:
        if not any(_pid_alive(p) for p in pids):
            return True
        time.sleep(0.15)
    return False


def _wait_app_gone(app, timeout=12.0):
    """等到这个客户端一个进程都不剩（含渲染进程和它自己拉起的 codex）"""
    end = time.time() + timeout
    while time.time() < end:
        pids, _roots = _app_pids(app)
        if not pids:
            return True
        time.sleep(0.2)
    return False


def _wait_app_up(app, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        pids, _roots = _app_pids(app)
        if pids:
            return True
        time.sleep(0.25)
    return False


def _launch(path):
    p = str(path)
    d = os.path.dirname(p) or None
    if p.lower().endswith((".bat", ".cmd")):
        _popen(["cmd", "/c", "start", "", p], cwd=d)
    else:
        _popen([p], cwd=d)


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def activate_app(aumid, args=""):
    """用应用容器身份启动商店应用，可带命令行参数（启动普通 exe 时参数无效）"""
    if os.name != "nt":
        raise CoreError("仅支持 Windows")
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    def guid(text):
        g = _GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g))
        return g

    obj = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(guid("{45BA127D-10A8-46EA-8AB7-56EA9078943C}")),
                                None, 1,
                                ctypes.byref(guid("{2e941141-7f97-4756-ba1d-9decde894a3d}")),
                                ctypes.byref(obj))
    if hr != 0 or not obj:
        raise CoreError(f"启动失败（COM {hr:#x}）")
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    func = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.LPCWSTR,
                              wintypes.LPCWSTR, wintypes.DWORD,
                              ctypes.POINTER(wintypes.DWORD))(vtbl[3])
    pid = wintypes.DWORD()
    hr = func(obj, aumid, args or None, 0, ctypes.byref(pid))
    if hr != 0:
        raise CoreError(f"启动失败（{hr:#x}）")
    return pid.value


def _launch_app(app, args=""):
    """商店版只能靠 AUMID 拉起来（直接跑 WindowsApps 里的 exe 起不来）"""
    aumid = app.get("aumid")
    if aumid:
        try:
            activate_app(aumid, args)
            return "aumid"
        except Exception:
            if args:
                return _launch_app(app, "")
            os.startfile("shell:AppsFolder\\" + aumid)
            return "aumid"
    _launch(app["path"])
    return "exe"


def restart_clients(clients=None, args=""):
    """整棵树重启 Codex / ChatGPT（绝不碰本工具自身）；CLI 只结束，编辑器只给提示"""
    clients = clients or detect_clients(force=True)
    results, relaunched = [], set()
    me = os.getpid()  # 兜底：无论如何都不结束自己

    for a in clients.get("apps", []):
        label, kind = a["label"], a["kind"]
        pids, roots = _app_pids(a)
        pids = {p for p in pids if p != me}
        roots = [r for r in roots if r != me]
        if not pids:
            results.append({"label": label, "status": "idle", "detail": "未在运行"})
            continue

        if kind == "cli":
            _kill_tree(a, pids, roots)
            _wait_gone(sorted(pids), 5)
            results.append({"label": label, "status": "killed",
                            "detail": "已结束进程，重新运行 codex 即读到新配置"})
            continue

        _kill_tree(a, pids, roots)
        if not _wait_app_gone(a, 12):
            left, _r = _app_pids(a)
            results.append({"label": label, "status": "error",
                            "detail": f"还有 {len(left)} 个进程结束不掉（可能被系统保护），请手动关闭"})
            continue

        time.sleep(0.4)          # 等系统清理掉窗口和单实例锁
        try:
            _launch_app(a, args)
        except Exception as e:
            results.append({"label": label, "status": "error",
                            "detail": f"已完全退出，但重启失败：{e}"})
            continue

        if _wait_app_up(a, 15):
            relaunched.add(kind)
            results.append({"label": label, "status": "restarted",
                            "detail": "已完全退出并重新启动"})
        else:
            results.append({"label": label, "status": "error",
                            "detail": "已完全退出，但没能自动拉起来，请手动打开"})

    # 终端里残留的 codex 进程，顺手结束（不重启，避免凭空弹终端）
    # 现查一遍客户端进程：刚拉起来的新实例自带的 codex.exe 必须保护，不能当残留杀掉
    if "codex" not in relaunched:
        protected = set()
        for a in clients.get("apps", []):
            pids_a, _r = _app_pids(a)
            protected |= pids_a
        orphans = [p for p in list_processes().get("codex.exe", [])
                   if p not in protected and p != me]
        if orphans:
            _kill(orphans)
            results.append({"label": "残留 Codex 进程", "status": "killed",
                            "detail": f"已结束 {len(orphans)} 个，下次调用会用新配置"})

    for e in clients.get("editors", []):
        results.append({"label": f"{e['editor']} 的 Codex 插件", "status": "hint",
                        "detail": "在编辑器里执行“重新加载窗口”即可"})

    return results


def launch_clients(clients=None, args=""):
    """把已安装但没在运行的客户端打开（不结束任何进程）"""
    clients = clients or detect_clients(force=True)
    out = []
    for a in clients.get("apps", []):
        if a.get("kind") == "cli":
            continue
        pids, _r = _app_pids(a)
        if pids:
            out.append({"label": a["label"], "status": "running", "detail": "已在运行"})
            continue
        try:
            _launch_app(a, args)
            up = _wait_app_up(a, 12)
            out.append({"label": a["label"], "status": "restarted" if up else "error",
                        "detail": "已启动" if up else "没能自动启动，请手动打开"})
        except Exception as e:
            out.append({"label": a["label"], "status": "error", "detail": f"启动失败：{e}"})
    return out


# ---------------------------------------------------------------- 界面汉化
# 思路：不动应用文件，用调试端口在页面里注入一份中英对照表。
# 关掉开关时用普通方式重启应用，注入的脚本自然消失。
HAN_PORT = 9222


def han_enabled(store):
    return bool(store.get("han_cn"))


def set_han(store, on):
    store["han_cn"] = bool(on)
    save_store(store)
    return store["han_cn"]


def han_args(store):
    # 新版 Chromium 会拒绝没有白名单的 WebSocket Origin（403），必须一起带上 allow-origins
    if not han_enabled(store):
        return ""
    return f"--remote-debugging-port={HAN_PORT} --remote-allow-origins=*"


# ------------------------------------------------------------ 桌面版单独走代理
# 只给 ChatGPT 桌面版加 --proxy-server，不碰系统代理，别的程序照旧直连。
DEFAULT_PROXY = "http://127.0.0.1:10808"


def proxy_conf(store):
    """读代理设置；没有存过就默认开启 127.0.0.1:10808"""
    p = store.get("proxy")
    if not isinstance(p, dict):
        p = {}
    return {
        "on": bool(p.get("on", True)),
        "url": str(p.get("url") or DEFAULT_PROXY).strip(),
    }


def set_proxy(store, on=None, url=None):
    c = proxy_conf(store)
    if on is not None:
        c["on"] = bool(on)
    if url:
        c["url"] = str(url).strip() or DEFAULT_PROXY
    store["proxy"] = c
    save_store(store)
    return c


def proxy_addr(url=None):
    """从代理地址里拆出 (host, port)，认 http/https/socks5/socks4 前缀"""
    if not url:
        url = proxy_conf(load_store())["url"]
    m = re.match(r"^(?:(?:https?|socks5h?|socks4a?)://)?\[?([^\]/:]+)\]?:(\d+)", str(url).strip())
    if not m:
        return None
    return m.group(1), int(m.group(2))


def proxy_alive(url=None, timeout=0.6):
    a = proxy_addr(url)
    if not a:
        return False
    try:
        with socket.create_connection(a, timeout):
            return True
    except OSError:
        return False


def proxy_args(store, require_alive=True):
    """代理端口没在监听时不带参数，免得客户端直接断网"""
    c = proxy_conf(store)
    if not c["on"]:
        return ""
    if require_alive and not proxy_alive(c["url"]):
        return ""
    return f"--proxy-server={c['url']}"


def client_args(store, require_alive=True):
    """启动桌面版时统一拼参数：调试端口（汉化用）+ 代理"""
    parts = [han_args(store), proxy_args(store, require_alive)]
    return " ".join(p for p in parts if p)


def debug_ready(port=HAN_PORT, timeout=0.8):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout):
            return True
    except Exception:
        return False


def wait_debug(port=HAN_PORT, timeout=60, step=0.5):
    end = time.time() + timeout
    while time.time() < end:
        if debug_ready(port):
            return True
        time.sleep(step)
    return False


def _ws_send(sock, text):
    import struct as _struct

    payload = text.encode("utf-8")
    n = len(payload)
    head = bytearray([0x81])
    mask = os.urandom(4)
    if n < 126:
        head.append(0x80 | n)
    elif n < 65536:
        head.append(0x80 | 126)
        head += _struct.pack(">H", n)
    else:
        head.append(0x80 | 127)
        head += _struct.pack(">Q", n)
    head += mask
    sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def _ws_recv(sock, decode=True):
    import struct as _struct

    def read(n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("调试连接被关闭")
            buf += chunk
        return buf

    while True:
        b1, b2 = read(2)
        n = b2 & 0x7F
        if n == 126:
            n = _struct.unpack(">H", read(2))[0]
        elif n == 127:
            n = _struct.unpack(">Q", read(8))[0]
        mask = read(4) if b2 & 0x80 else None
        data = read(n)
        if mask:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        opcode = b1 & 0x0F
        if opcode == 0x8:
            raise ConnectionError("调试连接已断开")
        if opcode in (0x9, 0xA):      # ping / pong
            continue
        return data.decode("utf-8", "replace") if decode else data


def cdp_eval(port=HAN_PORT, expr="1+1", timeout=15):
    """在页面里执行一段 JS（极简 CDP 客户端，只用标准库）"""
    import base64
    import socket

    try:
        pages = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/list", timeout=3).read())
    except Exception as e:
        return {"ok": False, "error": f"调试端口没开：{e}"}
    pages = [t for t in pages if t.get("type") == "page"]
    if not pages:
        return {"ok": False, "error": "没有可注入的页面"}
    page = next((t for t in pages if not t.get("parentId") and "index.html" in t.get("url", "")), None) \
        or next((t for t in pages if not t.get("parentId")), pages[0])

    m = re.match(r"ws://([^/:]+):(\d+)(/.*)$", page.get("webSocketDebuggerUrl", ""))
    if not m:
        return {"ok": False, "error": "调试地址异常"}
    host, sport, path = m.group(1), int(m.group(2)), m.group(3)

    sock = socket.create_connection((host, sport), timeout=timeout)
    try:
        sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{sport}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                return {"ok": False, "error": "握手失败"}
            buf += chunk
        status = buf.split(b"\r\n", 1)[0]
        if b"101" not in status:
            if b"403" in status:
                return {"ok": False, "need_flag": True,
                        "error": "调试端口拒绝连接（缺 --remote-allow-origins）"}
            return {"ok": False, "error": "调试端口拒绝连接"}
        # 握手响应后面可能粘着第一个帧，先留起来
        pending = buf.split(b"\r\n\r\n", 1)[1]

        payload = {"id": 1, "method": "Runtime.evaluate",
                   "params": {"expression": expr, "returnByValue": True,
                              "awaitPromise": True, "userGesture": True}}
        _ws_send(sock, json.dumps(payload))
        end = time.time() + timeout
        while time.time() < end:
            if pending:
                msg = json.loads(pending.decode("utf-8", "replace"))
                pending = b""
            else:
                msg = json.loads(_ws_recv(sock))
            if msg.get("id") == 1:
                r = msg.get("result", {})
                if "exceptionDetails" in r:
                    return {"ok": False, "error": str(r["exceptionDetails"].get("text"))}
                return {"ok": True, "value": r.get("result", {}).get("value")}
        return {"ok": False, "error": "等响应超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            sock.close()
        except Exception:
            pass


def page_ready(port=HAN_PORT, min_len=200, timeout=10):
    """页面是否已经有内容（只用于诊断，注入本身不需要等它）"""
    end = time.time() + timeout
    while time.time() < end:
        r = cdp_eval(port, "document.body?document.body.textContent.length:0", timeout=6)
        if r.get("ok") and isinstance(r.get("value"), int) and r["value"] >= min_len:
            return True
        if r.get("need_flag"):
            return False
        time.sleep(0.6)
    return False


def inject_zh(port=HAN_PORT, tries=3):
    """把中文对照表注入页面，返回替换条数

    注入脚本自带 MutationObserver + 多次延时补扫，所以页面还没渲染完也能先装进去，
    等界面画出来会自动翻译，不需要等 boot。
    """
    try:
        import zh_cn
    except Exception as e:
        return {"ok": False, "error": f"缺少词表：{e}"}
    js = zh_cn.build_js()
    last = ""
    for _ in range(max(1, tries)):
        r = cdp_eval(port, js, timeout=20)
        if r.get("ok"):
            return {"ok": True, "count": r.get("value") or len(zh_cn.DICT)}
        last = r.get("error") or "注入失败"
        if r.get("need_flag"):
            return {"ok": False, "error": last, "need_flag": True}
        time.sleep(1.0)
    return {"ok": False, "error": last}


def han_refresh(port=HAN_PORT, timeout=45):
    """等界面真正画出来，再从外部补扫一次

    应用启动时窗口还在后台，Chromium 会把页面里的 setTimeout 节流成几十秒一次，
    脚本自带的定时补扫因此常常不执行 —— 只能由外面主动推一把。
    """
    end = time.time() + timeout
    while time.time() < end:
        r = cdp_eval(port, "document.body?document.body.textContent.length:0", timeout=6)
        if r.get("ok") and isinstance(r.get("value"), int) and r["value"] >= 200:
            break
        time.sleep(0.8)

    best = 0
    for _ in range(8):
        r = cdp_eval(
            port,
            "window.__apictlZh&&window.__apictlZh.scan?(window.__apictlZh.scan(document.body),1):0",
            timeout=25,
        )
        if not r.get("ok"):
            time.sleep(1.2)
            continue
        c = cdp_eval(
            port,
            r"document.body?(document.body.textContent.match(/[\u4e00-\u9fa5]/g)||[]).length:0",
            timeout=8,
        )
        n = c.get("value") or 0
        best = max(best, int(n) if isinstance(n, int) else 0)
        if best >= 20:
            return {"ok": True, "zh": best}
        time.sleep(1.5)
    return {"ok": best > 0, "zh": best}


def han_apply(store, port=HAN_PORT, wait=120, on_tick=None):
    """启动/重启后调用：等调试端口 → 立即注入（不等渲染）→ 返回结果

    端口不在时先自己补一次「带调试参数的重启」，避免用户点了开关却没生效。
    """
    if not han_enabled(store):
        return {"ok": False, "skipped": True}

    if on_tick:
        try:
            on_tick("检查调试端口…")
        except Exception:
            pass

    # 0) 端口没开：说明当前实例不是带调试参数启动的，自愈一次
    if not debug_ready(port, timeout=0.6):
        try:
            restart_clients(args=client_args(store))
        except Exception:
            pass

    # 1) 便宜地等端口（只探 /json/version，不发大脚本）
    end = time.time() + min(90, wait)
    while time.time() < end:
        if debug_ready(port, timeout=0.4):
            break
        time.sleep(0.4)
    else:
        return {"ok": False, "error": f"调试端口 {port} 一直没起来（可能被别的程序占用了）"}

    if on_tick:
        try:
            on_tick("调试端口已就绪，正在翻译界面…")
        except Exception:
            pass

    # 2) 有页面目标就注入，脚本会自己等 body 并持续观察后续渲染
    deadline = time.time() + wait
    last = "没有可注入的页面"
    while time.time() < deadline:
        r = inject_zh(port, tries=1)
        if r.get("ok"):
            if on_tick:
                try:
                    on_tick("界面正在渲染，正在补扫文案…")
                except Exception:
                    pass
            ref = han_refresh(port, timeout=min(60, wait))
            r["zh"] = ref.get("zh", 0)
            r["ok"] = bool(ref.get("ok", True))
            if not r["ok"]:
                r["error"] = "页面已注入，但没扫到中文（界面可能还在加载）"
            return r
        last = r.get("error") or last
        if r.get("need_flag"):
            return r
        if on_tick:
            try:
                on_tick(last)
            except Exception:
                pass
        time.sleep(1.2)
    return {"ok": False, "error": last}


def han_watch(store, seconds=240, step=4, port=HAN_PORT):
    """应用偶尔会重载页面 / 重渲染，注入的翻译会丢；前几分钟盯着，掉了就补"""
    if not han_enabled(store):
        return
    end = time.time() + seconds
    miss = 0
    tick = 0
    while time.time() < end:
        time.sleep(step)
        if not han_enabled(store):
            return
        if not debug_ready(port, timeout=0.4):
            miss = 0
            continue
        tick += 1
        # 每 30 秒兜底重扫一次（后台窗口定时器会被节流，JS 自己的补扫靠不住）
        if tick % 8 == 0:
            cdp_eval(port, "window.__apictlZh&&window.__apictlZh.scan&&window.__apictlZh.scan(document.body)", timeout=25)
        r = cdp_eval(port, "!!(window.__apictlZh && window.__apictlZh.v)", timeout=6)
        if not r.get("ok"):
            continue
        if r.get("value") is True:
            miss = 0
            continue
        miss += 1
        if miss >= 2:
            inject_zh(port, tries=1)
            miss = 0
