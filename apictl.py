#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apictl — API 环境一键切换（命令行版，全中文）

    apictl              交互菜单
    apictl ls           列出全部档案
    apictl use 名称     一键切换
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apictl_core as core
from apictl_core import (
    APP_NAME,
    VERSION,
    CONFIG,
    AUTH,
    STORE,
    ENV_SH,
    BACKUPS,
    CoreError,
    host_of,
    mask,
)

USAGE = """
用法：apictl [命令] [参数]

  不带参数            打开交互菜单，按编号即可切换
  ls                  列出全部档案
  use <名称>          一键切换到某个档案
  use -               切回上一个档案
  cur                 查看当前生效的配置
  show [名称]         查看档案详情（--full 显示完整 Key）
  add                 新增档案（不带参数走向导）
  update <名称>       修改档案（--api-key / --base-url / --model / --note）
  rename <旧> <新>    重命名档案
  rm <名称>           删除档案（-y 免确认）
  models [名称]      拉取该网关的模型列表
  restart            检测并重启 Codex / ChatGPT
  test [名称]         测试 Key 与网关连通性
  env [名称]          输出 export 语句，可 eval $(apictl env 名称)
  path                显示所有配置路径
  doctor              环境自检
  gui                 打开图形界面

示例：
  apictl add work --base-url https://api.x.com/v1 --api-key sk-xxx --model gpt-4o
  apictl use work
  apictl test
"""


# ---------------------------------------------------------------- 终端输出
class C:
    on = False
    R = B = D = CY = GR = YE = RE = ""


def _init_color():
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return
    if os.name == "nt":
        try:
            import ctypes

            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            m = ctypes.c_uint32()
            k.GetConsoleMode(h, ctypes.byref(m))
            k.SetConsoleMode(h, m.value | 0x0004)
        except Exception:
            pass
    C.on = True
    C.R, C.B, C.D = "\033[0m", "\033[1m", "\033[2m"
    C.CY, C.GR, C.YE, C.RE = "\033[36m", "\033[32m", "\033[33m", "\033[31m"


def c(s, color):
    return f"{color}{s}{C.R}" if C.on else str(s)


def dwidth(s):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(s))


def pad(s, width, align="left"):
    s = str(s)
    n = width - dwidth(s)
    if n <= 0:
        return s
    if align == "right":
        return " " * n + s
    return s + " " * n


def _plain(s):
    import re

    return re.sub(r"\033\[[0-9;]*m", "", str(s))


def render_table(headers, rows):
    widths = [dwidth(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], dwidth(_plain(cell)))
    out = ["  " + "  ".join(c(pad(h, widths[i]), C.D) for i, h in enumerate(headers)).rstrip()]
    out.append("  " + c("─" * (sum(widths) + 2 * (len(widths) - 1)), C.D))
    for row in rows:
        cells = [str(cell) + " " * (widths[i] - dwidth(_plain(cell))) for i, cell in enumerate(row)]
        out.append(("  " + "  ".join(cells)).rstrip())
    return "\n".join(out)


def ask(prompt, default=""):
    d = f"（{default}）" if default else ""
    try:
        v = input(f"  {prompt}{d}：").strip()
    except EOFError:
        v = ""
    return v or default


# ---------------------------------------------------------------- 参数解析
def parse_flags(args, value_flags, bool_flags):
    """极简参数解析：中文报错，不依赖英文提示"""
    vals, pos, i = {}, [], 0
    while i < len(args):
        a = args[i]
        if a in value_flags:
            if i + 1 >= len(args):
                raise CoreError(f"参数 {a} 后面缺少内容")
            vals[value_flags[a]] = args[i + 1]
            i += 2
        elif a.startswith("--") and "=" in a and a.split("=", 1)[0] in value_flags:
            k, v = a.split("=", 1)
            vals[value_flags[k]] = v
            i += 1
        elif a in bool_flags:
            vals[bool_flags[a]] = True
            i += 1
        elif a in ("-h", "--help"):
            print(USAGE)
            raise SystemExit(0)
        else:
            pos.append(a)
            i += 1
    return pos, vals


# ---------------------------------------------------------------- 各命令
def print_list(store):
    if not store["profiles"]:
        print("  还没有任何档案，运行 " + c("apictl add", C.B) + " 添加一个，或直接 " + c("apictl gui", C.B))
        return
    cur = core.current_name(store)
    names = sorted(store["profiles"], key=str.lower)
    rows = []
    for i, name in enumerate(names, 1):
        p = store["profiles"][name]
        rows.append(
            [
                pad(str(i), 2, "right"),
                c("●", C.GR) if name == cur else c("○", C.D),
                c(name, C.B) if name == cur else name,
                p.get("model") or "-",
                host_of(p.get("base_url")),
                mask(p.get("api_key")),
                p.get("note") or "",
            ]
        )
    print()
    print(render_table(["#", "", "名称", "模型", "网关", "Key", "备注"], rows))
    print()
    print("  " + c(f"{len(names)} 个档案", C.D) + "   " + c("● 当前生效", C.D) + "   " + c("apictl use <名称> 切换", C.D))
    print()


def cmd_ls(store, args):
    print_list(store)
    return 0


def print_restart(res):
    if not res:
        print("  " + c("· 未检测到 Codex 或 ChatGPT，无需重启", C.D))
        return
    marks = {
        "restarted": c("✔", C.GR), "killed": c("✔", C.GR), "started": c("✔", C.GR),
        "idle": c("·", C.D), "hint": c("→", C.YE), "error": c("✘", C.RE),
    }
    for r in res:
        print("  " + marks.get(r["status"], "·") + " " + r["label"] + c("  " + r["detail"], C.D))


def do_use(store, name):
    try:
        r = core.use_profile(store, name)
    except CoreError as e:
        print("  " + c(f"✘ {e}", C.RE))
        return 1
    p = r["profile"]
    print()
    print("  " + c("✔ 已切换", C.GR) + "  " + c(r["name"], C.B))
    print("  " + c(f"网关  {p.get('base_url')}", C.D))
    print("  " + c(f"模型  {p.get('model') or '保持不变'}", C.D))
    print("  " + c(f"Key   {mask(p.get('api_key'))}", C.D))
    print()
    print("  " + c(f"配置文件  {CONFIG}", C.D))
    print("  " + c(f"鉴权文件  {AUTH}", C.D))
    print("  " + c(f"全局变量  {r['persisted']} 个已写入用户环境变量（新进程即生效）", C.D))
    print()
    print_restart(core.restart_clients(args=core.client_args(store)))
    print()
    return 0


def cmd_use(store, args):
    pos, _ = parse_flags(args, {}, {})
    if not pos:
        print("  " + c("用法：apictl use <名称>", C.RE))
        return 2
    return do_use(store, pos[0])


def cmd_restart(store, args):
    print()
    cl = core.detect_clients()
    print("  " + c(core.describe_clients(cl), C.D))
    print()
    print_restart(core.restart_clients(cl, args=core.client_args(store)))
    print()
    return 0


def cmd_cur(store, args):
    live = core.detect_live()
    name = core.current_name(store)
    print()
    print("  " + c("当前档案  ", C.D) + c(name or "未匹配到档案", C.B if name else C.YE))
    if live:
        print("  " + c("接口提供  ", C.D) + str(live.get("provider")))
        print("  " + c("网关地址  ", C.D) + str(live.get("base_url")))
        print("  " + c("模型      ", C.D) + str(live.get("model")))
        print("  " + c("Key       ", C.D) + mask(live.get("api_key")))
    print()
    return 0


def cmd_show(store, args):
    pos, f = parse_flags(args, {}, {"--full": "full"})
    name = pos[0] if pos else core.current_name(store)
    p = store["profiles"].get(name or "")
    if not p:
        print("  " + c(f"✘ 没有名为“{name}”的档案", C.RE))
        return 1
    print()
    print("  " + c(name, C.B) + ("   " + c("（当前）", C.GR) if name == core.current_name(store) else ""))
    print()
    for k, v in (
        ("接口提供", p.get("provider")),
        ("网关地址", p.get("base_url")),
        ("模型", p.get("model") or "-"),
        ("接口类型", p.get("wire_api") or "-"),
        ("Key", p.get("api_key") if f.get("full") else mask(p.get("api_key"))),
        ("备注", p.get("note") or "-"),
    ):
        print("  " + c(pad(k, 10), C.D) + str(v))
    print()
    return 0


def cmd_add(store, args):
    pos, f = parse_flags(
        args,
        {
            "--base-url": "base_url",
            "--api-key": "api_key",
            "--model": "model",
            "--provider": "provider",
            "--wire-api": "wire_api",
            "--note": "note",
            "--from": "from_profile",
        },
        {"-y": "quiet", "--quiet": "quiet", "--use": "use"},
    )
    if f.get("quiet") and pos and f.get("base_url"):
        try:
            name = core.add_profile(
                store, pos[0], f.get("base_url"), f.get("api_key"),
                model=f.get("model", ""), provider=f.get("provider", "custom"),
                wire_api=f.get("wire_api", "responses"), note=f.get("note", ""),
                use=f.get("use", False),
            )
        except CoreError as e:
            print("  " + c(f"✘ {e}", C.RE))
            return 1
        print("  " + c(f"✔ 已添加档案“{name}”", C.GR))
        return 0

    base = {}
    if f.get("from_profile"):
        base = dict(store["profiles"].get(f["from_profile"]) or {})

    print()
    print("  " + c("新增档案", C.B) + c("（回车使用默认值）", C.D))
    print()
    name = pos[0] if pos else ask("名称（英文/拼音，好打为准）", base.get("name") or "new")
    provider = f.get("provider") or ask("接口提供方（配置文件里的段名）", base.get("provider") or "custom")
    base_url = f.get("base_url") or ask("网关地址", base.get("base_url") or "")
    api_key = f.get("api_key") or ask("API Key")
    model = f.get("model") or ask("模型名称", base.get("model") or "")
    wire = f.get("wire_api") or ask("接口类型 responses / chat", base.get("wire_api") or "responses")
    note = f.get("note") or ask("备注（可留空）", base.get("note") or "")
    try:
        name = core.add_profile(store, name, base_url, api_key, model=model, provider=provider,
                                wire_api=wire, note=note, use=False)
    except CoreError as e:
        print("  " + c(f"✘ {e}", C.RE))
        return 1
    print()
    print("  " + c(f"✔ 已添加档案“{name}”", C.GR))
    if f.get("use") or ask("现在就切换过去？（Y/n）", "Y").lower().startswith("y"):
        return do_use(store, name)
    return 0


def cmd_update(store, args):
    pos, f = parse_flags(
        args,
        {
            "--api-key": "api_key",
            "--base-url": "base_url",
            "--model": "model",
            "--provider": "provider",
            "--wire-api": "wire_api",
            "--note": "note",
        },
        {},
    )
    if not pos:
        print("  " + c("用法：apictl update <名称> --api-key sk-xxx", C.RE))
        return 2
    before = core.detect_live()
    try:
        core.update_profile(store, pos[0], **{k: v for k, v in f.items() if v})
    except CoreError as e:
        print("  " + c(f"✘ {e}", C.RE))
        return 1
    print("  " + c(f"✔ 已更新“{pos[0]}”", C.GR))
    if core.detect_live() != before:
        print("  " + c("改到的是当前生效的配置，自动重启客户端", C.D))
        print_restart(core.restart_clients(args=core.client_args(store)))
    print()
    return 0


def cmd_rename(store, args):
    pos, _ = parse_flags(args, {}, {})
    if len(pos) != 2:
        print("  " + c("用法：apictl rename <旧名称> <新名称>", C.RE))
        return 2
    try:
        new = core.rename_profile(store, pos[0], pos[1])
    except CoreError as e:
        print("  " + c(f"✘ {e}", C.RE))
        return 1
    print("  " + c(f"✔ 已重命名为“{new}”", C.GR))
    return 0


def cmd_rm(store, args):
    pos, f = parse_flags(args, {}, {"-y": "yes", "--yes": "yes"})
    if not pos:
        print("  " + c("用法：apictl rm <名称>", C.RE))
        return 2
    name = pos[0]
    if name not in store["profiles"]:
        print("  " + c(f"✘ 没有名为“{name}”的档案", C.RE))
        return 1
    if not f.get("yes") and not ask(f"确认删除“{name}”？（y/N）", "N").lower().startswith("y"):
        print("  已取消")
        return 0
    try:
        core.delete_profile(store, name)
    except CoreError as e:
        print("  " + c(f"✘ {e}", C.RE))
        return 1
    print("  " + c(f"✔ 已删除“{name}”", C.GR))
    return 0


def cmd_test(store, args):
    pos, f = parse_flags(args, {"--timeout": "timeout"}, {})
    name = pos[0] if pos else core.current_name(store)
    p = store["profiles"].get(name or "")
    label = name
    if not p:
        p = core.detect_live()
        label = "当前配置文件"
    print()
    print("  " + c(f"测试 {label}", C.B))
    r = core.test_endpoint(p, timeout=float(f.get("timeout", 15)))
    if r.get("url"):
        print("  " + c(f"请求 {r['url']}", C.D))
    if r.get("ok"):
        print("  " + c("✔ 可用", C.GR) + c(f"  HTTP {r['status']}  {r['ms']}ms", C.D))
        if r.get("models"):
            print("  " + c(f"可用模型 {len(r['models'])} 个：", C.D) + "、".join(r["models"][:8]))
        print()
        return 0
    status = f"HTTP {r['status']}" if r.get("status") else "连接失败"
    print("  " + c(f"✘ {status}", C.RE) + (c(f"  {r['ms']}ms", C.D) if r.get("ms") else ""))
    if r.get("error"):
        print("  " + c(str(r["error"])[:200], C.D))
    if r.get("hint"):
        print("  " + c(r["hint"], C.YE))
    print()
    return 1


def cmd_env(store, args):
    pos, _ = parse_flags(args, {}, {})
    name = pos[0] if pos else core.current_name(store)
    p = store["profiles"].get(name or "")
    if not p:
        print("  " + c(f"✘ 没有名为“{name}”的档案", C.RE))
        return 1
    for k, v in core.build_env_pairs(p):
        print(f"export {k}='{v}'")
    return 0


def cmd_models(store, args):
    pos, f = parse_flags(args, {"--timeout": "timeout"}, {})
    name = pos[0] if pos else core.current_name(store)
    p = store["profiles"].get(name or "")
    if not p:
        print("  " + c(f"✘ 没有名为“{name}”的档案", C.RE))
        return 1
    print()
    print("  " + c(f"拉取 {name} 的模型列表", C.B) + c(f"  {host_of(p.get('base_url'))}", C.D))
    r = core.fetch_models(p.get("base_url"), p.get("api_key"), timeout=float(f.get("timeout", 15)))
    if not r.get("ok"):
        status = f"HTTP {r['status']}" if r.get("status") else "连接失败"
        print("  " + c(f"✘ {status}", C.RE))
        if r.get("hint"):
            print("  " + c(r["hint"], C.YE))
        print()
        return 1
    models = r.get("models") or []
    if not models:
        print("  " + c("网关没有返回模型列表（需要支持 /models 接口）", C.YE))
        print()
        return 1
    cols = 3
    width = max((dwidth(m) for m in models), default=12) + 4
    for i in range(0, len(models), cols):
        print("  " + "".join(pad(m, width) for m in models[i:i + cols]).rstrip())
    print()
    print("  " + c(f"共 {len(models)} 个 · 用 apictl update <名称> --model <模型名> 固定下来", C.D))
    print()
    return 0


def cmd_path(store, args):
    print(f"  配置文件   {CONFIG}")
    print(f"  鉴权文件   {AUTH}")
    print(f"  档案库     {STORE}")
    print(f"  环境文件   {ENV_SH}")
    print(f"  备份目录   {BACKUPS}")
    return 0


def cmd_doctor(store, args):
    live = core.detect_live()
    bak = core.last_backup()
    cl = core.detect_clients()
    print()
    print("  " + c("环境自检", C.B))
    print()
    rows = [
        ["Python", sys.version.split()[0], "正常"],
        ["程序版本", VERSION, "正常"],
        ["配置文件", str(CONFIG), "存在" if CONFIG.exists() else c("缺失", C.RE)],
        ["鉴权文件", str(AUTH), "存在" if AUTH.exists() else c("缺失", C.YE)],
        ["档案库", str(STORE), f"{len(store['profiles'])} 个档案"],
        ["环境文件", str(ENV_SH), "已生成" if ENV_SH.exists() else "未生成"],
        ["最近备份", str(bak.name) if bak else "无", "正常" if bak else c("无备份", C.YE)],
        ["全局变量", "OPENAI_API_KEY / CODEX_API_KEY / OPENAI_BASE_URL",
         f"{len(core.read_global_env(['OPENAI_API_KEY', 'CODEX_API_KEY']))} 个已写入"],
        ["客户端", core.describe_clients(cl), "正常"],
    ]
    print(render_table(["项目", "路径 / 数值", "状态"], rows))
    print()
    cur = core.current_name(store)
    if live and live.get("base_url"):
        print("  " + c("配置文件指向：", C.D) + f"{live.get('base_url')}  {mask(live.get('api_key'))}")
    if cur:
        print("  " + c("匹配到档案：  ", C.D) + c(cur, C.B))
    elif live:
        print("  " + c("当前配置没有对应档案，用 apictl add 把它收编进来", C.YE))
    print()
    return 0


def cmd_gui(store, args):
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    gui = os.path.join(here, "apictl_gui.py")
    if not os.path.exists(gui):
        print("  " + c("✘ 找不到图形界面文件 apictl_gui.py", C.RE))
        return 1
    subprocess.Popen([sys.executable, gui])
    return 0


def menu(store):
    while True:
        print()
        print("  " + c("API 环境切换器", C.B) + c(f"   命令行版 v{VERSION}", C.D))
        if not store["profiles"]:
            print()
            print("  " + c("还没有档案。", C.YE))
            if ask("现在添加一个？（Y/n）", "Y").lower().startswith("y"):
                cmd_add(store, [])
                continue
            return 0
        print_list(store)
        try:
            choice = input("  " + c("输入编号切换", C.B) + c("，a 新增，t 测试，g 图形界面，q 退出 > ", C.D)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not choice:
            continue
        low = choice.lower()
        if low in ("q", "quit", "exit", "退出"):
            return 0
        if low in ("a", "add"):
            cmd_add(store, [])
            continue
        if low in ("t", "test"):
            cmd_test(store, [])
            continue
        if low in ("g", "gui"):
            cmd_gui(store, [])
            continue
        names = sorted(store["profiles"], key=str.lower)
        target = None
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            target = names[int(choice) - 1]
        elif choice in store["profiles"]:
            target = choice
        else:
            near = [n for n in names if low in n.lower()]
            if len(near) == 1:
                target = near[0]
        if target:
            do_use(store, target)
        else:
            print("  " + c("没找到这个档案", C.RE))


COMMANDS = {
    "ls": cmd_ls,
    "list": cmd_ls,
    "use": cmd_use,
    "switch": cmd_use,
    "cur": cmd_cur,
    "current": cmd_cur,
    "show": cmd_show,
    "add": cmd_add,
    "update": cmd_update,
    "rename": cmd_rename,
    "rm": cmd_rm,
    "remove": cmd_rm,
    "models": cmd_models,
    "test": cmd_test,
    "restart": cmd_restart,
    "env": cmd_env,
    "path": cmd_path,
    "doctor": cmd_doctor,
    "gui": cmd_gui,
}


def main(argv=None):
    _init_color()
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    argv = sys.argv[1:] if argv is None else list(argv)

    if argv and argv[0] in ("-h", "--help", "help", "-?", "帮助"):
        print(USAGE)
        return 0
    if argv and argv[0] in ("-V", "--version", "-v", "version"):
        print(f"{APP_NAME} 命令行版 v{VERSION}")
        return 0

    if not argv:
        return menu(core.load_store())

    cmd = argv[0].lower()
    rest = argv[1:]
    store = core.load_store()

    if cmd in COMMANDS:
        try:
            return COMMANDS[cmd](store, rest)
        except CoreError as e:
            print("  " + c(f"✘ {e}", C.RE))
            return 1
        except SystemExit:
            raise
        except KeyboardInterrupt:
            print()
            return 130

    # 兼容：apictl 1 / apictl 档案名 直接切换
    names = sorted(store["profiles"], key=str.lower)
    target = None
    if cmd.isdigit() and 1 <= int(cmd) <= len(names):
        target = names[int(cmd) - 1]
    elif cmd in store["profiles"]:
        target = cmd
    else:
        near = [n for n in names if cmd in n.lower()]
        if len(near) == 1:
            target = near[0]
    if target:
        return do_use(store, target)
    print("  " + c(f"✘ 未知命令或档案：{argv[0]}", C.RE))
    print("  " + c("输入 apictl -h 查看全部用法", C.D))
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
