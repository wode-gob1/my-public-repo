#!/usr/bin/env python3
"""
AI Coder - 运行在 Linux 沙箱中的 AI 编程助手
大脑：Agnes AI (agnes-2.0-flash)
身体：本脚本（ReAct 循环 + 工具系统）

用法：
  python3 ai_coder.py "你的中文指令"
  python3 ai_coder.py              # 从 task.txt 读取指令
"""

import os, sys, json, re, subprocess, time, hashlib, urllib.request
from pathlib import Path

# ============================================================
# 配置
# ============================================================
API_KEY  = "sk-E9uN06wGYJQKTj5rSBB2adVIkyehJhcZxyLIWeMMDX2pJ6Gc"
API_URL  = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL    = "agnes-2.0-flash"
WORK_DIR = os.getcwd()
MAX_ROUNDS = 30          # 最大循环轮数
MAX_TOKENS_CONTEXT = 80000  # 上下文接近此值触发压缩

# ============================================================
# 工具系统
# ============================================================

def tool_bash(command: str, timeout: int = 120) -> str:
    """执行 shell 命令，返回输出"""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=WORK_DIR, executable="/bin/bash"
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append(f"[stderr]\n{err}")
        parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"[错误] 命令超时（{timeout}秒）"

def tool_read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    """读取文件内容"""
    full_path = Path(WORK_DIR) / path
    if not full_path.exists():
        return f"[错误] 文件不存在: {path}"
    try:
        lines = full_path.read_text(encoding="utf-8", errors="replace").split("\n")
        total = len(lines)
        chunk = lines[offset:offset + limit]
        header = f"=== {path} (共 {total} 行，显示第 {offset+1}-{min(offset+limit, total)} 行) ==="
        return header + "\n" + "\n".join(f"{i+offset+1:4d}|{l}" for i, l in enumerate(chunk))
    except Exception as e:
        return f"[错误] 读取失败: {e}"

def tool_write_file(path: str, content: str) -> str:
    """创建或覆盖文件"""
    full_path = Path(WORK_DIR) / path
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"[成功] 文件已写入: {path} ({len(content)} 字符)"
    except Exception as e:
        return f"[错误] 写入失败: {e}"

def tool_edit_file(path: str, old_str: str, new_str: str) -> str:
    """精确替换文件中的内容"""
    full_path = Path(WORK_DIR) / path
    if not full_path.exists():
        return f"[错误] 文件不存在: {path}"
    try:
        content = full_path.read_text(encoding="utf-8")
        if old_str not in content:
            return f"[错误] 未找到要替换的内容，请使用 read_file 先查看文件内容"
        if content.count(old_str) > 1:
            return f"[错误] 匹配到 {content.count(old_str)} 处，请提供更精确的上下文"
        new_content = content.replace(old_str, new_str, 1)
        full_path.write_text(new_content, encoding="utf-8")
        return f"[成功] 文件已编辑: {path}"
    except Exception as e:
        return f"[错误] 编辑失败: {e}"

def tool_list_dir(path: str = ".") -> str:
    """列出目录内容"""
    full_path = Path(WORK_DIR) / path
    if not full_path.exists():
        return f"[错误] 目录不存在: {path}"
    try:
        items = sorted(full_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        lines = []
        for item in items:
            suffix = "/" if item.is_dir() else ""
            size = ""
            if item.is_file():
                s = item.stat().st_size
                if s < 1024:
                    size = f" ({s}B)"
                elif s < 1024 * 1024:
                    size = f" ({s/1024:.1f}K)"
                else:
                    size = f" ({s/1024/1024:.1f}M)"
            lines.append(f"  {item.name}{suffix}{size}")
        return f"=== {path}/ ({len(lines)} 项) ===\n" + "\n".join(lines)
    except Exception as e:
        return f"[错误] {e}"

def tool_grep(pattern: str, path: str = ".") -> str:
    """搜索文件内容"""
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts",
             "--include=*.html", "--include=*.css", "--include=*.json", "--include=*.txt",
             "--include=*.md", "--include=*.sh", "--include=*.yml", "--include=*.yaml",
             "--include=*.toml", "--include=*.cfg", "--include=*.ini",
             pattern, path], capture_output=True, text=True, timeout=10, cwd=WORK_DIR
        )
        out = result.stdout.strip()
        return out[:5000] if out else "未找到匹配结果"
    except Exception as e:
        return f"[错误] {e}"

def tool_glob(pattern: str) -> str:
    """按通配符查找文件"""
    try:
        result = subprocess.run(
            ["find", ".", "-name", pattern, "-not", "-path", "./.git/*", "-not", "-path", "./node_modules/*"],
            capture_output=True, text=True, timeout=10, cwd=WORK_DIR
        )
        out = result.stdout.strip()
        return out[:3000] if out else "未找到匹配文件"
    except Exception as e:
        return f"[错误] {e}"

def tool_web_fetch(url: str) -> str:
    """下载网页内容"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            # 简单提取文本
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:5000]
    except Exception as e:
        return f"[错误] 下载失败: {e}"

def tool_web_search(query: str) -> str:
    """搜索网页（简化版，使用 DuckDuckGo HTML）"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.request.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            # 提取搜索结果摘要
            snippets = re.findall(r'class="result__snippet[^"]*">(.*?)</a>', html, re.DOTALL)
            results = []
            for i, s in enumerate(snippets[:5]):
                s = re.sub(r"<[^>]+>", "", s).strip()
                results.append(f"{i+1}. {s}")
            return "\n".join(results) if results else "未找到搜索结果"
    except Exception as e:
        return f"[错误] 搜索失败: {e}"

# 工具注册表
TOOLS = {
    "bash":        {"fn": tool_bash,      "desc": "执行 shell 命令。参数: command (命令字符串)", "readonly": False},
    "read_file":   {"fn": tool_read_file, "desc": "读取文件。参数: path (文件路径), offset (起始行,可选), limit (行数,可选)", "readonly": True},
    "write_file":  {"fn": tool_write_file,"desc": "创建/覆盖文件。参数: path (文件路径), content (完整内容)", "readonly": False},
    "edit_file":   {"fn": tool_edit_file, "desc": "精确替换文件内容。参数: path, old_str (要替换的原文本), new_str (新文本)", "readonly": False},
    "list_dir":    {"fn": tool_list_dir,  "desc": "列出目录。参数: path (目录路径,可选,默认.)", "readonly": True},
    "grep":        {"fn": tool_grep,      "desc": "搜索文件内容。参数: pattern (正则), path (目录,可选)", "readonly": True},
    "glob":        {"fn": tool_glob,      "desc": "按通配符查找文件。参数: pattern (如 *.py)", "readonly": True},
    "web_fetch":   {"fn": tool_web_fetch, "desc": "下载网页文本。参数: url", "readonly": True},
    "web_search":  {"fn": tool_web_search,"desc": "搜索互联网。参数: query (搜索词)", "readonly": True},
}

# ============================================================
# AI 调用
# ============================================================

def call_ai(messages: list) -> str:
    """调用 Agnes AI API"""
    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }).encode("utf-8")

    req = urllib.request.Request(API_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[API 调用失败] {e}"

# ============================================================
# 上下文压缩
# ============================================================

def estimate_tokens(text: str) -> int:
    """粗略估算 token 数（中文约 1 字 = 1 token，英文约 4 字符 = 1 token）"""
    return len(text) // 2

def compact_context(messages: list) -> list:
    """压缩上下文：保留最近 6 条消息，其余用摘要替代"""
    if len(messages) <= 8:
        return messages

    # 前 2 条是 system + user，保留
    head = messages[:2]
    # 中间部分压缩
    middle = messages[2:-6]
    # 最后 6 条保留
    tail = messages[-6:]

    middle_text = "\n".join(
        m.get("content", "")[:500] for m in middle
        if m.get("role") in ("assistant", "user")
    )

    summary_prompt = {
        "role": "user",
        "content": f"[上下文总结 - 之前的工作摘要]\n{middle_text[:3000]}"
    }
    return head + [summary_prompt] + tail

# ============================================================
# 核心：ReAct 循环
# ============================================================

def build_system_prompt() -> str:
    """构建系统提示词"""
    tools_desc = "\n".join(
        f"- {name}: {info['desc']} {'(只读)' if info['readonly'] else '(可修改)'}"
        for name, info in TOOLS.items()
    )

    return f"""你是 AI Coder，一个运行在 Linux 沙箱中的 AI 编程助手。

## 工作方式
你会收到一个编程任务。你需要通过多轮思考来完成任务，每一轮：
1. 思考：分析当前状态，决定下一步该做什么
2. 行动：调用一个工具
3. 观察：查看工具返回的结果
4. 重复，直到任务完成

## 可用工具
{tools_desc}

## 调用工具的方式
当你想调用工具时，请严格用以下格式输出（不要用 markdown 代码块包裹）：

```
TOOL: <工具名>
ARG: <参数名>: <参数值>
ARG: <参数名>: <参数值>
```

多行内容用以下方式：
```
TOOL: write_file
ARG: path: hello.py
ARG: content:
print("Hello World")
for i in range(10):
    print(i)
```

## 重要规则
1. 每轮只调用一个工具，等待结果后再决定下一步
2. 如果命令执行失败，分析错误并修复
3. 完成任务后，输出 "TASK_COMPLETE" 并总结结果
4. 不要猜测，如果不确定就用工具去查
5. 创建文件前先确认目录存在
6. Python 代码默认用 python3 运行
7. 不要使用 sudo

## 当前工作目录
{WORK_DIR}

## 开始
现在开始执行任务。用中文思考和回复。"""


def parse_tool_call(text: str):
    """解析 AI 输出的工具调用"""
    lines = text.strip().split("\n")
    tool_name = None
    args = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("TOOL:") and not tool_name:
            tool_name = line.replace("TOOL:", "").strip()
        elif line.startswith("ARG:") and tool_name:
            rest = line.replace("ARG:", "", 1).strip()
            if ":" in rest:
                key, val = rest.split(":", 1)
                key = key.strip()
                val = val.strip()
                # 检查是否是多行内容
                if val == "":
                    # 收集后续行作为内容
                    content_lines = []
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith("ARG:") and not lines[j].strip().startswith("TOOL:"):
                        content_lines.append(lines[j])
                        j += 1
                    args[key] = "\n".join(content_lines)
                    i = j - 1
                else:
                    args[key] = val
        i += 1

    return tool_name, args


def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回结果"""
    if name not in TOOLS:
        return f"[错误] 未知工具: {name}。可用工具: {', '.join(TOOLS.keys())}"

    try:
        return TOOLS[name]["fn"](**args)
    except TypeError as e:
        return f"[错误] 参数不正确: {e}。参数说明: {TOOLS[name]['desc']}"
    except Exception as e:
        return f"[错误] 工具执行异常: {e}"


def auto_save():
    """自动保存到 git"""
    try:
        subprocess.run(["git", "config", "user.email", "ai-coder@github.com"], capture_output=True, cwd=WORK_DIR)
        subprocess.run(["git", "config", "user.name", "AI Coder"], capture_output=True, cwd=WORK_DIR)
        subprocess.run(["git", "add", "-A"], capture_output=True, cwd=WORK_DIR)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True, cwd=WORK_DIR)
        if result.returncode == 0:
            return "没有需要保存的更改"
        commit = subprocess.run(["git", "commit", "-m", "AI Coder: 任务执行结果"], capture_output=True, text=True, cwd=WORK_DIR)
        if commit.returncode != 0:
            return f"commit 失败: {commit.stderr}"
        push = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=30, cwd=WORK_DIR)
        if push.returncode != 0:
            return f"push 失败: {push.stderr}"
        return "已保存到 GitHub 仓库"
    except Exception as e:
        return f"保存失败: {e}"


def run(task: str) -> str:
    """主循环"""
    print(f"\n{'='*60}")
    print(f"  AI Coder 启动")
    print(f"  任务: {task[:100]}{'...' if len(task) > 100 else ''}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": f"任务：{task}\n\n开始执行。先分析任务，然后逐步完成。"},
    ]

    total_tokens = 0
    round_num = 0

    while round_num < MAX_ROUNDS:
        round_num += 1

        # 上下文压缩
        if estimate_tokens(json.dumps(messages)) > MAX_TOKENS_CONTEXT:
            messages = compact_context(messages)
            print(f"  [系统] 上下文已压缩")

        # 调用 AI
        print(f"\n--- 第 {round_num} 轮：AI 思考中... ---")
        response = call_ai(messages)

        if response.startswith("[API 调用失败]"):
            print(f"  {response}")
            break

        print(f"\n{response[:500]}{'...' if len(response) > 500 else ''}")

        # 检查是否任务完成
        if "TASK_COMPLETE" in response:
            print(f"\n{'='*60}")
            print(f"  任务完成！共 {round_num} 轮")
            print(f"{'='*60}")
            return response

        # 解析工具调用
        tool_name, args = parse_tool_call(response)

        if tool_name and tool_name in TOOLS:
            # 执行工具
            print(f"\n  >> 执行工具: {tool_name}({', '.join(f'{k}={v[:50]}...' if len(str(v)) > 50 else f'{k}={v}' for k, v in args.items())})")
            result = execute_tool(tool_name, args)
            print(f"  >> 结果: {result[:300]}{'...' if len(result) > 300 else ''}")

            # 把结果喂回 AI
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"工具执行结果:\n{result}\n\n请继续下一步。"})
        else:
            # AI 没有调用工具，可能是在思考或总结
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "请继续执行任务。如果需要调用工具，请使用 TOOL/ARG 格式。"})

    print(f"\n  达到最大轮数 ({MAX_ROUNDS})，自动保存并退出")
    return "达到最大轮数"


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    # 获取任务
    task = None

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task_file = Path(WORK_DIR) / "task.txt"
        if task_file.exists():
            content = task_file.read_text(encoding="utf-8").strip()
            if content:
                task = content
                print(f"从 task.txt 读取任务 ({len(task)} 字符)")
                # 清空 task.txt
                task_file.write_text("")
            else:
                print("task.txt 为空，请写入任务或通过命令行参数传入")
                sys.exit(1)
        else:
            print("用法: python3 ai_coder.py '你的指令'")
            print("或者: 将指令写入 task.txt 后运行 python3 ai_coder.py")
            sys.exit(1)

    # 运行
    final_result = run(task)

    # 自动保存
    print(f"\n{'='*60}")
    save_result = auto_save()
    print(f"  {save_result}")
    print(f"{'='*60}")

    # 输出最终结果
    print(f"\n{'='*60}")
    print(f"  最终输出")
    print(f"{'='*60}")
    print(final_result)