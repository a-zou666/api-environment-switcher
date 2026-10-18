#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zh_cn — ChatGPT 桌面版界面中文对照表

应用自带中文语言包，但这个版本的界面没有真正用上（英文界面 + 中文语言包未生效）。
这里用运行时注入的方式把界面文字换成中文：只改页面显示，不动应用自身的任何文件。
键是界面上出现的英文原文（精确匹配），值是中文。
路径、快捷键、模型名、对话标题等动态内容不翻译。
"""

DICT = {
    # ---------------- 主界面
    "Skip to content": "跳到主要内容",
    "File": "文件",
    "Edit": "编辑",
    "View": "视图",
    "Help": "帮助",
    "ChatGPT Work": "ChatGPT 工作",
    "New chat": "新对话",
    "Scheduled": "定时任务",
    "Plugins": "插件",
    "Projects": "项目",
    "No chats": "暂无对话",
    "Recents": "最近",
    "What should we work on?": "今天想做点什么？",
    "Select effort": "选择思考强度",
    "Custom": "自定义",
    "High": "高",
    "None": "无",
    "Minimal": "最少",
    "Light": "轻",
    "Medium": "中",
    "Extra High": "超高",
    "Max": "最高",
    "Ultra": "极致",
    "Persistent": "常驻",
    "Back": "后退",
    "Forward": "前进",
    "Hide sidebar": "隐藏侧边栏",
    "Application menu": "应用菜单",
    "Chat history": "对话历史",
    "Search": "搜索",
    "Project sidebar options": "项目侧栏选项",
    "Add new project": "新建项目",
    "Chat sidebar options": "对话侧栏选项",
    "Open profile menu": "打开账户菜单",
    "Toggle side panel": "切换右侧面板",
    "Work with ChatGPT": "交给 ChatGPT 处理…",
    "Add files and more": "添加文件等",
    "Send": "发送",
    "Composer utility bar": "输入框工具栏",
    "Don't work in a project": "不放在项目里",
    "Choose where to run this chat": "选择这次对话的运行位置",
    "Notifications alt+T": "通知 alt+T",
    "Back to app": "返回应用",
    "Search settings": "搜索设置",
    "Settings": "设置",

    # ---------------- 设置导航
    "Personal": "个人",
    "General": "通用",
    "Appearance": "外观",
    "Archived chats": "已归档对话",
    "Voice": "语音",
    "Storage": "存储",
    "Configuration": "配置",
    "Personalization": "个性化",
    "Mini & Pets": "迷你模式与宠物",
    "Keyboard shortcuts": "键盘快捷键",
    "Integrations": "集成",
    "Computer use": "计算机操作",
    "Browser": "浏览器",
    "Coding": "编程",
    "Hooks": "钩子",
    "Git": "Git",
    "Environments": "环境",
    "Worktrees": "工作树",

    # ---------------- 通用设置
    "Permissions": "权限",
    "Default permissions": "默认权限",
    "By default, ChatGPT can read and edit files in its workspace. It can ask for additional access when needed":
        "默认情况下，ChatGPT 可以读写它的工作目录里的文件；需要更多权限时它会主动询问。",
    "Full access": "完全访问",
    "Learn more": "了解更多",
    "about elevated risks.": "了解提权风险。",
    "Projectless chat folder": "无项目对话的存放目录",
    "The location where chats started outside of projects store their data by default.":
        "不在任何项目里开始的对话，默认把数据存在这里。",
    "Change": "更改",
    "Default file open destination": "默认打开文件的方式",
    "Where files and folders open by default": "文件和文件夹默认用什么打开",
    "Integrated terminal shell": "集成终端使用的 shell",
    "Choose which shell opens in the integrated terminal.": "选择集成终端里启动哪个 shell。",
    "Language": "语言",
    "Language for the app UI": "应用界面显示的语言",
    "Confirm before closing a window": "关闭窗口前确认",
    "Warn when a tab-close shortcut would close the window": "用关闭标签页的快捷键会关掉整个窗口时给出提醒",
    "Close shortcut only": "仅关闭快捷键时",
    "Launch at login": "开机自动启动",
    "On": "开启",
    "Open Startup Apps": "打开启动项设置",
    "Bottom panel": "底部面板",
    "Show the bottom panel control in the app header": "在应用顶部显示底部面板开关",
    "Automatically archive inactive chats": "自动归档不活跃的对话",
    "Archive local chats after a period of inactivity": "本地对话闲置一段时间后自动归档",
    "Never": "从不",
    "Compress local chat history": "压缩本地对话历史",
    "Save disk space by compressing older local chat history. Restart ChatGPT to apply changes.":
        "压缩较早的本地对话记录以节省磁盘空间，重启 ChatGPT 后生效。",
    "Import work from other AI apps": "从其他 AI 应用导入",
    "Bring over your setup, projects, and recent chats": "把配置、项目和最近的对话一起带过来",
    "No data detected": "没有检测到可导入的数据",
    "Open source licenses": "开源许可",
    "Third-party notices for bundled dependencies": "随附依赖的第三方声明",
    "Allow ChatGPT to use installed plugins": "允许 ChatGPT 使用已安装的插件",

    # ---------------- 输入框 / 通知
    "Composer": "输入框",
    "Plain text composer": "纯文本输入",
    "Keep code, Markdown, and links as literal text while writing messages":
        "撰写消息时，代码、Markdown 和链接都保持为纯文本",
    "Show context window usage": "显示上下文用量",
    "Send shortcut": "发送快捷键",
    "Choose when Enter sends a prompt or inserts a new line": "选择回车是发送消息还是换行",
    "Enter": "回车",
    "Follow-up behavior": "追问行为",
    "Queue follow-ups while ChatGPT runs or steer the current run. Press Ctrl+⏎ to do the opposite for one message":
        "ChatGPT 运行时，追问是排队等待还是直接改变当前这一轮；单条消息按 Ctrl+⏎ 可临时反过来。",
    "Queue": "排队",
    "Steer": "实时干预",
    "Notifications": "通知",
    "Turn completion notifications": "轮次完成通知",
    "Set when ChatGPT alerts you that it's finished": "设置 ChatGPT 完成时什么时候提醒你",
    "Only when unfocused": "仅窗口不在前台时",
    "Enable permission notifications": "开启权限请求通知",
    "Show alerts when notification permissions are required": "需要授权时弹出提醒",
    "Enable question notifications": "开启提问通知",
    "Show alerts when input is needed to continue": "需要你输入才能继续时弹出提醒",
    "Enable dot notifications": "开启小圆点通知",
    "Show alerts when your dot sends you a message": "小圆点给你发消息时提醒",
    "Notification sound": "通知声音",
    "Sound for task completion, permission requests, and questions": "任务完成、请求权限、提问时的提示音",
    "Default": "默认",
    "Default permissions are always shown": "始终显示默认权限",
    "Show Full access in the composer": "在输入框显示「完全访问」",
    "Toggle plugins": "切换插件",
    "Show context window usage in the composer": "在输入框显示上下文用量",

    # ---------------- 外观
    "Visual style": "视觉风格",
    "Mode": "模式",
    "Theme": "主题",
    "Accent": "强调色",
    "Background": "背景色",
    "Light background color": "浅色背景颜色",
    "Foreground": "前景色",
    "Light ink color": "浅色文字颜色",
    "Font": "字体",
    "System": "跟随系统",
    "Advanced": "高级",
    "Reset to default": "恢复默认",
    "Dark": "深色",
    "Import Light theme": "导入浅色主题",
    "Copy Light theme": "复制浅色主题",
    "Light code theme": "浅色代码主题",
    "Light accent color": "浅色强调色",
    "Light UI font": "浅色界面字体",

    # ---------------- 配置
    "Configure permissions, web access, and agent responses for new chats": "为新对话设置权限、联网方式和回答风格",
    "Agent defaults": "智能体默认设置",
    "Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.":
        "Codex 忽略了 1 个无法识别的配置项，可能是拼写错误或已废弃的配置。",
    "is ignored.": "已被忽略。",
    "User config": "用户配置",
    "Open config.toml": "打开 config.toml",
    "Approval policy": "审批策略",
    "Choose when ChatGPT asks for approval": "选择 ChatGPT 什么时候向你申请授权",
    "On request": "按需申请",
    "Sandbox settings": "沙盒设置",
    "Choose how much ChatGPT can do when running commands": "选择运行命令时 ChatGPT 能做的事",
    "Read only": "只读",
    "Web search": "联网搜索",
    "Choose how ChatGPT accesses the web": "选择 ChatGPT 怎么访问网络",
    "Cached": "使用缓存",
    "Output detail": "输出详细程度",
    "Choose how much detail ChatGPT includes in responses": "选择回答里包含多少细节",
    "Model default": "默认模型",
    "Reasoning summary": "推理摘要",
    "Choose how ChatGPT summarizes its reasoning": "选择 ChatGPT 如何总结推理过程",
    "Auto": "自动",
    "Codex memory": "Codex 记忆",
    "Configure how Codex manages memory for Local.": "设置 Codex 如何管理本地记忆。",
    "Local": "本地",
    "Enable Codex memories": "开启 Codex 记忆",
    "Create memories from chats on Local and use them to personalize future chats on Local":
        "从本地对话里生成记忆，并用于以后的本地对话",
    "Allow memories from tool-assisted chats": "允许从使用了工具的对话里生成记忆",
    "Generate memories from chats that used MCP tools or web search": "从用过 MCP 工具或联网搜索的对话里生成记忆",
    "Delete Codex memories": "删除 Codex 记忆",
    "Delete all Codex memories for Local": "删除本地全部 Codex 记忆",
    "Delete": "删除",
    "Custom instructions": "自定义指令",
    "Codex instructions": "Codex 指令",
    "Edit the AGENTS.md file on the selected machine. Repository instructions may also apply.":
        "编辑所选机器上的 AGENTS.md；仓库里的指令同样会生效。",
    "Edit Codex custom instructions": "编辑 Codex 自定义指令",

    # ---------------- 快捷键页
    "To change a shortcut, select the key combination, and then type the new keys":
        "要改快捷键，先选中原来的组合，再直接按新的按键",
    "Send message": "发送消息",
    "Send message in background": "后台发送消息",
    "Attach files and folders": "添加文件和文件夹",
    "Chat": "对话",
    "Archive chat": "归档对话",
    "Delete chat": "删除对话",
    "Rename chat": "重命名对话",
    "Toggle pin": "置顶 / 取消置顶",
    "Mark as unread": "标记为未读",
    "App": "应用",
    "Show keyboard shortcuts": "显示快捷键列表",
    "Send annotations": "发送标注",
    "Toggle annotation mode": "切换标注模式",
    "Switch chat…": "切换对话…",
    "Open command menu": "打开命令菜单",
    "Toggle sidebar": "切换侧边栏",
    "New Temporary Chat": "新建临时对话",
    "New Window": "新建窗口",
    "Close": "关闭",
    "Restore defaults": "恢复默认",
    "Dictation": "听写",
    "Dictation unavailable": "听写不可用",
    "Dictation is not available in your current configuration": "当前配置下无法使用听写",

    # ---------------- 存储 / 归档
    "This device": "本机",
    "Manage chats and worktrees stored on this computer": "管理这台电脑上保存的对话和工作树",
    "Refresh": "刷新",
    "Chats": "对话",
    "Subagents": "子代理",
    "Unclassified chats": "未分类的对话",
    "Other": "其他",
    "Clean up old chats": "清理旧对话",
    "Review chats and their subagents before permanently deleting them": "永久删除前，先检查对话及其子代理",
    "Review": "检查",
    "Manage worktrees": "管理工作树",
    "Review working copies and choose how many old worktrees to keep": "检查工作副本，并决定保留多少个旧工作树",
    "Manage": "管理",
    "Restore or delete individual archived chats": "恢复或删除单个已归档对话",
    "Delete all": "全部删除",
    "Search archived chats": "搜索已归档对话",
    "All chats": "全部对话",
    "All projects": "全部项目",
    "Unarchive": "取消归档",
    "Filter archived chats": "筛选已归档对话",
    "Filter archived chats by project": "按项目筛选已归档对话",
    "Project actions": "项目操作",
    "Delete archived chat": "删除已归档对话",

    # ---------------- 插件
    "Manage plugins, skills, and MCPs": "管理插件、技能和 MCP",
    "Browse directory": "浏览目录",
    "Add": "添加",
    "MCPs": "MCP",
    "Skills": "技能",
    "Search plugins": "搜索插件",
    "Unavailable in this context": "当前环境不可用",
    "Control the in-app browser": "控制应用内置浏览器",
    "Computer Use": "计算机操作",
    "Control Windows apps": "操作 Windows 应用",
    "Visualize": "可视化",
    "Create interactive visuals": "生成可交互的图表",
    "Servers": "服务",
    "MCP Apps": "MCP 应用",
    "App data": "应用数据",
    "Clear site data and cache from all MCP apps": "清除所有 MCP 应用的站点数据和缓存",
    "Clear all app data": "清除全部应用数据",
    "Manage extensions": "管理扩展",
    "Toggle plugin enabled state": "启用 / 停用插件",
    "Enable": "启用",

    # ---------------- 计算机操作 / 浏览器
    "Manage how ChatGPT uses other applications on your computer": "设置 ChatGPT 如何使用电脑上的其他应用",
    "Control": "控制",
    "Google Chrome": "Google Chrome",
    "Disabled by your organization or unavailable in your region": "已被组织禁用，或在当前地区不可用",
    "Manage your Browser Use preferences and site access.": "设置浏览器使用的偏好和站点权限。",
    "Web URL and link open destination": "网页链接的打开方式",
    "Local URL open destination": "本地地址的打开方式",
    "Where local development sites open by default": "本地开发站点默认在哪里打开",
    "Show full URL": "显示完整网址",
    "Include the path, query, and fragment in the address bar": "地址栏里包含路径、查询参数和锚点",
    "Browsing data": "浏览数据",
    "Clear browsing history, site data, cache, and download history from the in-app browser":
        "清除内置浏览器的历史记录、站点数据、缓存和下载记录",
    "Clear browsing data": "清除浏览数据",
    "Browsing history": "浏览历史",
    "View and manage pages visited in the built-in browser": "查看和管理在内置浏览器里访问过的页面",
    "Annotation screenshots": "标注截图",
    "Screenshots help ChatGPT better understand and address comments, but increase plan usage":
        "截图能让 ChatGPT 更好地理解并处理你的意见，但会占用更多额度",
    "Always include": "总是包含",
    "Autofill and passwords": "自动填充与密码",
    "Password manager": "密码管理器",
    "Add, delete, and edit saved passwords": "添加、删除、编辑已保存的密码",
    "Contact info": "联系信息",
    "Add, delete, and edit saved addresses, phone numbers, and email addresses":
        "添加、删除、编辑已保存的地址、电话和邮箱",
    "Downloads": "下载",
    "Location": "位置",
    "System Downloads folder": "系统下载文件夹",
    "Ask where to save downloads": "下载前询问保存位置",
    "Show a save dialog for downloads you start in the built-in browser": "在内置浏览器里下载时弹出保存对话框",
    "Download history": "下载记录",
    "View and manage files downloaded from the built-in browser": "查看和管理从内置浏览器下载的文件",
    "Browser permissions": "浏览器权限",
    "Site settings": "站点设置",
    "Control camera and microphone permissions in the built-in browser": "控制内置浏览器的摄像头和麦克风权限",
    "Manage download history": "管理下载记录",

    # ---------------- 钩子
    "Manage lifecycle hooks from config and enabled plugins.": "管理来自配置和已启用插件的生命周期钩子。",
    "No hooks found": "没有找到钩子",
    "Configured hooks will appear here": "配置好的钩子会显示在这里",
    "Reload hooks": "重新加载钩子",

    # ---------------- Git
    "Branch prefix": "分支前缀",
    "Prefix used when ChatGPT creates new branches": "ChatGPT 新建分支时使用的前缀",
    "Pull request merge method": "拉取请求的合并方式",
    "Choose how ChatGPT merges pull requests": "选择 ChatGPT 如何合并拉取请求",
    "Merge": "合并",
    "Squash": "压缩合并",
    "Always force push": "总是强制推送",
    "Use --force-with-lease when pushing from ChatGPT": "ChatGPT 推送时使用 --force-with-lease",
    "Create draft pull requests": "创建草稿拉取请求",
    "Use draft pull requests by default when creating PRs from ChatGPT": "ChatGPT 创建 PR 时默认用草稿",
    "Review delivery": "代码审查的方式",
    "Start /review in the current chat when possible or launch a separate review chat":
        "尽量在当前对话里执行 /review，否则另开一个审查对话",
    "Inline": "内联",
    "Detached": "独立对话",
    "Watch and fix pull requests": "持续关注并修复拉取请求",
    "Auto-merge when ready": "满足条件时自动合并",
    "Continue watching until the pull request is merged": "一直关注到拉取请求被合并为止",
    "Commit instructions": "提交信息要求",
    "Added to commit message generation prompts": "会附加到生成提交信息的提示里",
    "Pull request instructions": "拉取请求要求",
    "Added to PR title/description generation prompts": "会附加到生成 PR 标题/描述的提示里",
    "Pull request watch instructions": "PR 巡检要求",
    "Add commit message guidance…": "补充提交信息的要求…",
    "Add pull request guidance…": "补充拉取请求的要求…",
    "For example: Comment /merge after checks pass and approve unrelated Chromatic changes…":
        "例如：检查通过后评论 /merge，并批准无关的 Chromatic 变更…",

    # ---------------- 环境 / 工作树
    "Local environments tell ChatGPT how to set up worktrees for a project.":
        "本地环境用于告诉 ChatGPT 该怎么为项目准备工作树。",
    "Select a project": "选择项目",
    "Add project": "添加项目",
    "Available projects": "可用项目",
    "Worktree root": "工作树根目录",
    "Directory where ChatGPT creates managed worktrees. Leave blank to use the default location":
        "ChatGPT 创建受管工作树的目录，留空则使用默认位置",
    "Always fetch upstream before creating worktrees": "创建工作树前总是拉取上游",
    "Codex normally picks up branch updates during regular Git activity. This also fetches before each new worktree.":
        "Codex 平时会在 Git 操作中顺带更新分支；开启后每次新建工作树前也会拉取一次。",
    "Automatically delete old worktrees": "自动删除旧工作树",
    "Recommended for most users. Turn this off only if you want to manage old worktrees and disk usage yourself.":
        "建议保持开启。只有想自己管理旧工作树和磁盘占用时才关闭。",
    "Auto-delete limit": "自动删除上限",
    "No worktrees yet": "还没有工作树",
    "Worktrees created by ChatGPT will appear here": "ChatGPT 创建的工作树会出现在这里",
    # 新版本（26.1013）新增文案
    "What should we build?": "今天想做点什么？",
    "Do anything": "随便问点什么…",
    "What should we work on?": "今天想做点什么？",
    "Choose project": "选择项目",
    "Ask for approval": "需要批准",
    "Switch mode, current mode: ChatGPT Work": "切换模式，当前模式：ChatGPT 工作",
    "Start new chat": "开始新对话",
    "Open project": "打开项目",
    "Project actions": "项目操作",
    "Select model": "选择模型",
    "Locked, opens access options": "已锁定，点击查看可用的访问方式",
    "Loading model…": "正在加载模型…",
    "Loading model...": "正在加载模型…",
    "Persistent": "常驻",
    "Extended": "增强",
    "Skip to content": "跳到主要内容",
    "New": "新建",
    "Search": "搜索",
    "Close": "关闭",
    "Cancel": "取消",
    "Save": "保存",
    "Delete": "删除",
    "Rename": "重命名",
    "Copy": "复制",
    "Retry": "重试",
    "Send": "发送",
    "Stop": "停止",
    "Settings": "设置",
    "Help": "帮助",
}

# 这些是动态内容或专有名词，注入时直接跳过
ZH_JS_VER = 8

SKIP_PREFIX = ("Ctrl", "Alt", "Shift", "F1", "F2", "F3", "F4", "F5", "F6", "F7",
               "F8", "F9", "F10", "F11", "F12", "Mouse")

# 带项目名的动态句式：[前缀, 中文前缀, 中文后缀]
PATTERNS = [
    ("What should we work on in ", "在 ", " 里想做点什么？"),
    ("What should we build in ", "在 ", " 里想做点什么？"),
    ("Project actions for ", "", " 的项目操作"),
    ("Start new chat in ", "在 ", " 里新建对话"),
]


def build_js():
    """生成注入用的 JS（含影子 DOM，React 重渲染后自动补翻；只跑一次，不占 CPU）"""
    import json

    data = json.dumps(DICT, ensure_ascii=False)
    skip = json.dumps(list(SKIP_PREFIX), ensure_ascii=False)
    pats = json.dumps([list(p) for p in PATTERNS], ensure_ascii=False)
    return r"""(function(){
  var D = __DICT__;
  var SKIP = __SKIP__;
  var PFX = __PFX__;
  if(window.__apictlZh && window.__apictlZh.v === __VER__ && window.__apictlZh.scan){
    try { window.__apictlZh.scan(document.body); } catch(e){}
    return window.__apictlZh.count;
  }
  function skipKey(k){
    if(k.length < 2 || k.length > 400) return true;
    if(k.charCodeAt(0) < 58 && k.charCodeAt(0) > 47) return true;
    if(k.length > 24 && /[:\\\/]/.test(k)) return true;
    for(var i=0;i<SKIP.length;i++){ if(k.indexOf(SKIP[i])===0) return true; }
    return false;
  }
  function tr(v){
    if(!v || v.length > 420) return null;
    var k = v.replace(/^\s+|\s+$/g, '');
    if(!k || skipKey(k)) return null;
    var hit = D[k];
    if(hit === undefined){
      for(var pi=0; pi<PFX.length; pi++){
        var pfx = PFX[pi][0];
        if(k.length > pfx.length && k.indexOf(pfx) === 0){
          hit = PFX[pi][1] + k.slice(pfx.length) + PFX[pi][2];
          break;
        }
      }
    }
    if(hit === undefined) return null;
    var lead = v.length - v.replace(/^\s+/, '').length;
    var tail = v.length - v.replace(/\s+$/, '').length;
    return v.slice(0, lead) + hit + (tail ? v.slice(v.length - tail) : '');
  }
  function fixAttrs(el){
    if(!el || el.nodeType !== 1 || !el.getAttribute) return;
    // data-placeholder 由 React 受控，改了会被立刻重置，反而拖垮扫描预算，故不碰
    var list = ['placeholder','title','aria-label'];
    for(var i=0;i<list.length;i++){
      var a = list[i], v = el.getAttribute(a);
      if(!v) continue;
      var r = tr(v);
      if(r !== null && r !== v) el.setAttribute(a, r);
    }
  }
  function walk(node, inEditor, depth){
    if(depth > 120) return;
    if(node.nodeType === 3){
      if(inEditor) return;
      var r = tr(node.nodeValue);
      if(r !== null) node.nodeValue = r;
      return;
    }
    if(node.nodeType !== 1) return;
    var tag = node.tagName;
    if(tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') return;
    fixAttrs(node);
    if(tag === 'INPUT' || tag === 'TEXTAREA') return;
    var ed = inEditor || node.getAttribute('contenteditable') === 'true';
    for(var c=node.firstChild;c;c=c.nextSibling) walk(c, ed, depth + 1);
  }
  var pendingTimer = null, busy = false, budget = 240;
  function schedule(){
    if(pendingTimer || budget <= 0) return;
    pendingTimer = setTimeout(function(){
      pendingTimer = null;
      if(busy) return;
      busy = true; budget--;
      try { scan(document.body); } catch(e){}
      busy = false;
    }, 500);
  }
  function observe(root){
    if(!root || root.__apictlObs) return;
    root.__apictlObs = 1;
    // 注意：绝不能在 mutation 回调里同步改 DOM —— 会跟 React 的提交阶段互相触发死循环。
    // 统一延迟 500ms 后整树扫一遍。
    try {
      new MutationObserver(schedule).observe(root, {childList:true, subtree:true, characterData:true});
    } catch(e){}
  }
  function fixAllAttrs(){
    var sel = '[data-placeholder],[placeholder],[aria-label],[title]';
    function run(root){
      try {
        var els = root.querySelectorAll(sel);
        for(var i=0;i<els.length;i++) fixAttrs(els[i]);
        var all = root.querySelectorAll('*');
        for(var j=0;j<all.length;j++){ if(all[j].shadowRoot) run(all[j].shadowRoot); }
      } catch(e){}
    }
    run(document);
  }
  function scan(root){
    if(!root) return;
    try { walk(root, false, 0); } catch(e){}
    try { fixAllAttrs(); } catch(e){}
    observe(root);
    var all;
    try { all = root.querySelectorAll('*'); } catch(e){ return; }
    for(var i=0;i<all.length;i++){
      var el = all[i];
      var sr = el.shadowRoot;
      // 不能标记"扫过了"就跳过：影子根可能在早期注入时还是空的，后面才渲染
      if(sr && sr !== root) scan(sr);
    }
  }
  function start(){
    if(!document.body){ setTimeout(start, 300); return; }
    window.__apictlZh = {count: Object.keys(D).length, scan: scan, v: __VER__};
    scan(document.body);
    [800, 2000, 4000, 8000, 14000, 22000, 32000, 45000].forEach(
      function(t){ setTimeout(function(){ scan(document.body); }, t); }
    );
  }
  start();
  return Object.keys(D).length;
})()""".replace("__DICT__", data).replace("__SKIP__", skip).replace("__PFX__", pats).replace("__VER__", str(ZH_JS_VER))
