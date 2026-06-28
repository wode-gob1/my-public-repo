#!/usr/bin/env python3
"""
AI Coder v2 — 运行在 Linux 沙箱中的 AI 编程助手
大脑：Agnes AI (agnes-2.0-flash) | 身体：ReAct 循环 + 9 工具

用法：
  python3 ai_coder.py "你的中文指令"
  python3 ai_coder.py              # 从 task.txt 读取
"""

import os, sys, json, re, subprocess, time, urllib.request, urllib.error, traceback
from pathlib import Path

# ============================================================
# 配置
# ============================================================
API_KEY   = "sk-E9uN06wGYJQKTj5rSBB2adVIkyehJhcZxyLIWeMMDX2pJ6Gc"
API_URL   = "https://apihub.agnes-ai.com/v1/chat/completions"
MODEL     = "agnes-2.0-flash"
WORK_DIR  = os.getcwd()
MAX_ROUNDS = 30
MAX_TOKENS_CONTEXT = 80000
API_MAX_RETRIES = 3
API_RETRY_DELAY = 3  # 秒

# 阻塞命令关键词（自动添加 timeout 包裹）
BLOCKING_KEYWORDS = [
    "http.server", "flask run", "uvicorn", "gunicorn", "npm start",
    "npm run", "node server", "nodemon", "forever", "pm2", "serve",
    "python -m http", "python3 -m http", "nginx", "apache", "php -S",
    "watch", "tail -f", "top", "htop", "npx serve", "yarn start",
]

# ============================================================
# 工具系统
# ============================================================

def _safe_path(path: str) -> Path:
    """安全检查：防止路径遍历攻击"""
    full = (Path(WORK_DIR) / path).resolve()
    if not str(full).startswith(str(Path(WORK_DIR).resolve())):
        raise ValueError(f"路径越界: {path}")
    return full

def tool_bash(command: str, timeout: int = 120) -> str:
    """执行 shell 命令"""
    # 检测阻塞命令，自动添加 timeout
    cmd_lower = command.lower()
    for keyword in BLOCKING_KEYWORDS:
        if keyword in cmd_lower:
            # 如果命令本身没有 timeout，自动包裹
            if "timeout" not in cmd_lower:
                command = f"timeout {timeout} {command}"
            break

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout + 5, cwd=WORK_DIR, executable="/bin/bash"
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(out[:4000])
        if err:
            parts.append(f"[stderr]\n{err[:2000]}")
        parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return f"[提示] 命令超时（{timeout}秒）。如果这是服务端命令，说明已经启动成功。"
    except Exception as e:
        return f"[错误] 命令执行失败: {e}"

def tool_read_file(path: str, offset: int = 0, limit: int = 200) -> str:
    """读取文件内容"""
    try:
        full_path = _safe_path(path)
        if not full_path.exists():
            return f"[错误] 文件不存在: {path}"
        if full_path.stat().st_size > 5 * 1024 * 1024:  # 5MB 限制
            return f"[错误] 文件过大: {full_path.stat().st_size / 1024 / 1024:.1f}MB"

        lines = full_path.read_text(encoding="utf-8", errors="replace").split("\n")
        total = len(lines)
        chunk = lines[offset:offset + limit]
        header = f"=== {path} (共 {total} 行，显示第 {offset+1}-{min(offset+limit, total)} 行) ==="
        return header + "\n" + "\n".join(f"{i+offset+1:4d}|{l}" for i, l in enumerate(chunk))
    except ValueError as e:
        return f"[安全错误] {e}"
    except Exception as e:
        return f"[错误] 读取失败: {e}"

def tool_write_file(path: str, content: str) -> str:
    """创建或覆盖文件"""
    try:
        full_path = _safe_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"[成功] 文件已写入: {path} ({len(content)} 字符)"
    except ValueError as e:
        return f"[安全错误] {e}"
    except Exception as e:
        return f"[错误] 写入失败: {e}"

def tool_edit_file(path: str, old_str: str, new_str: str) -> str:
    """精确替换文件内容"""
    try:
        full_path = _safe_path(path)
        if not full_path.exists():
            return f"[错误] 文件不存在: {path}"
        content = full_path.read_text(encoding="utf-8")
        if old_str not in content:
            return f"[错误] 未找到要替换的内容，请先用 read_file 查看文件"
        count = content.count(old_str)
        if count > 1:
            return f"[错误] 匹配到 {count} 处，请扩大上下文使匹配唯一"
        new_content = content.replace(old_str, new_str, 1)
        full_path.write_text(new_content, encoding="utf-8")
        return f"[成功] 文件已编辑: {path}"
    except ValueError as e:
        return f"[安全错误] {e}"
    except Exception as e:
        return f"[错误] 编辑失败: {e}"

def tool_list_dir(path: str = ".") -> str:
    """列出目录内容"""
    try:
        full_path = _safe_path(path) if path != "." else Path(WORK_DIR)
        if not full_path.exists():
            return f"[错误] 目录不存在: {path}"
        items = sorted(full_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        lines = []
        for item in items:
            suffix = "/" if item.is_dir() else ""
            size_str = ""
            if item.is_file():
                s = item.stat().st_size
                if s < 1024:
                    size_str = f" ({s}B)"
                elif s < 1024 * 1024:
                    size_str = f" ({s/1024:.1f}K)"
                else:
                    size_str = f" ({s/1024/1024:.1f}M)"
            lines.append(f"  {item.name}{suffix}{size_str}")
        return f"=== {path}/ ({len(lines)} 项) ===\n" + "\n".join(lines)
    except ValueError as e:
        return f"[安全错误] {e}"
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
        return result.stdout.strip()[:5000] or "未找到匹配结果"
    except subprocess.TimeoutExpired:
        return "[错误] 搜索超时"
    except Exception as e:
        return f"[错误] {e}"

def tool_glob(pattern: str) -> str:
    """按通配符查找文件"""
    try:
        result = subprocess.run(
            ["find", ".", "-name", pattern, "-not", "-path", "./.git/*",
             "-not", "-path", "./node_modules/*"],
            capture_output=True, text=True, timeout=10, cwd=WORK_DIR
        )
        return result.stdout.strip()[:3000] or "未找到匹配文件"
    except subprocess.TimeoutExpired:
        return "[错误] 查找超时"
    except Exception as e:
        return f"[错误] {e}"

def tool_web_fetch(url: str) -> str:
    """下载网页内容"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Coder/2.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:5000]
    except urllib.error.HTTPError as e:
        return f"[错误] HTTP {e.code}: {url}"
    except Exception as e:
        return f"[错误] 下载失败: {e}"

def tool_web_search(query: str) -> str:
    """搜索网页"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.request.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            results = []
            for i, s in enumerate(snippets[:5]):
                s = re.sub(r"<[^>]+>", "", s).strip()
                results.append(f"{i+1}. {s}")
            return "\n".join(results) if results else "未找到结果"
    except Exception as e:
        return f"[错误] 搜索失败: {e}"

TOOLS = {
    "bash":        {"fn": tool_bash,      "desc": "执行 shell 命令。参数: command (字符串)", "ro": False},
    "read_file":   {"fn": tool_read_file, "desc": "读取文件。参数: path (路径), offset (起始行,可选), limit (行数,可选)", "ro": True},
    "write_file":  {"fn": tool_write_file,"desc": "创建/覆盖文件。参数: path (路径), content (完整内容)", "ro": False},
    "edit_file":   {"fn": tool_edit_file, "desc": "替换文件内容。参数: path, old_str (原文本), new_str (新文本)", "ro": False},
    "list_dir":    {"fn": tool_list_dir,  "desc": "列出目录。参数: path (路径,可选,默认.)", "ro": True},
    "grep":        {"fn": tool_grep,      "desc": "搜索文件内容。参数: pattern (关键词), path (目录,可选)", "ro": True},
    "glob":        {"fn": tool_glob,      "desc": "按模式查找文件。参数: pattern (如 *.py)", "ro": True},
    "web_fetch":   {"fn": tool_web_fetch, "desc": "下载网页文本。参数: url", "ro": True},
    "web_search":  {"fn": tool_web_search,"desc": "搜索互联网。参数: query (搜索词)", "ro": True},
}

# ============================================================
# AI 调用（带重试）
# ============================================================

def call_ai(messages: list) -> str:
    """调用 AI API，带重试"""
    data = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }).encode("utf-8")

    last_error = ""
    for attempt in range(API_MAX_RETRIES):
        try:
            req = urllib.request.Request(API_URL, data=data, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            })
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code == 429:  # Rate limit
                time.sleep(API_RETRY_DELAY * (attempt + 1))
            elif e.code >= 500:
                time.sleep(API_RETRY_DELAY * (attempt + 1))
            else:
                break  # 4xx 不重试
        except Exception as e:
            last_error = str(e)
            time.sleep(API_RETRY_DELAY)

    return f"[API 调用失败（重试{API_MAX_RETRIES}次）] {last_error}"

# ============================================================
# 上下文压缩（改进版）
# ============================================================

def estimate_tokens(text: str) -> int:
    return len(text) // 2

def compact_context(messages: list) -> list:
    """压缩上下文：保留 system + 最近 8 条，中间用精简摘要替代"""
    if len(messages) <= 10:
        return messages

    head = messages[:1]  # 只保留 system prompt
    middle = messages[1:-8]
    tail = messages[-8:]

    # 提取关键操作摘要
    ops = []
    for m in middle:
        content = m.get("content", "")
        if m.get("role") == "assistant":
            # 提取工具调用摘要
            if "TOOL:" in content:
                for line in content.split("\n"):
                    if line.strip().startswith("TOOL:"):
                        ops.append(f"  执行: {line.strip()}")
            elif "TASK_COMPLETE" in content:
                ops.append("  任务标记完成")
        elif m.get("role") == "user":
            # 提取执行结果摘要
            if "工具执行结果" in content:
                result_line = content.split("\n")[1] if "\n" in content else content
                ops.append(f"  结果: {result_line[:100]}")

    summary = {
        "role": "user",
        "content": f"[上下文摘要]\n已完成的操作:\n" + "\n".join(ops[-20:]) + "\n\n请基于以上摘要继续工作。"
    }
    return head + [summary] + tail

# ============================================================
# 工具调用解析（改进版）
# ============================================================

def parse_tool_call(text: str):
    """解析 AI 输出的工具调用，支持 markdown 代码块包裹"""
    # 先去掉可能的 markdown 代码块包裹
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    lines = cleaned.split("\n")
    tool_name = None
    args = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 匹配 TOOL: 行
        if line.startswith("TOOL:") and not tool_name:
            tool_name = line.replace("TOOL:", "").strip()
            if tool_name not in TOOLS:
                # 可能是不认识的工具名，尝试找真正的
                tool_name = None

        elif line.startswith("ARG:") and tool_name:
            rest = line[len("ARG:"):].strip()
            if ":" in rest:
                key, val = rest.split(":", 1)
                key = key.strip()
                val = val.strip()

                if val == "":
                    # 多行内容模式
                    content_lines = []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if next_line.startswith("ARG:") or next_line.startswith("TOOL:"):
                            break
                        content_lines.append(lines[j])
                        j += 1
                    args[key] = "\n".join(content_lines)
                    i = j - 1
                else:
                    args[key] = val
        i += 1

    return tool_name, args


def execute_tool(name: str, args: dict) -> str:
    if name not in TOOLS:
        return f"[错误] 未知工具: {name}。可用: {', '.join(TOOLS.keys())}"
    try:
        # 类型转换：offset/limit/timeout 应该是整数
        for int_key in ("offset", "limit", "timeout"):
            if int_key in args and isinstance(args[int_key], str):
                try:
                    args[int_key] = int(args[int_key])
                except ValueError:
                    pass
        return TOOLS[name]["fn"](**args)
    except TypeError as e:
        return f"[错误] 参数不匹配: {e}。说明: {TOOLS[name]['desc']}"
    except Exception as e:
        return f"[错误] 工具异常: {e}\n{traceback.format_exc()[-300:]}"

# ============================================================
# 自动保存
# ============================================================

def auto_save():
    """自动保存到 git，先 pull 再 push"""
    try:
        subprocess.run(["git", "config", "user.email", "ai-coder@github.com"], capture_output=True, cwd=WORK_DIR)
        subprocess.run(["git", "config", "user.name", "AI Coder"], capture_output=True, cwd=WORK_DIR)
        subprocess.run(["git", "add", "-A"], capture_output=True, cwd=WORK_DIR)

        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True, cwd=WORK_DIR)
        if diff.returncode == 0:
            return "没有需要保存的更改"

        commit = subprocess.run(
            ["git", "commit", "-m", f"AI Coder: {time.strftime('%Y-%m-%d %H:%M UTC')}"],
            capture_output=True, text=True, cwd=WORK_DIR
        )
        if commit.returncode != 0:
            return f"commit 失败: {commit.stderr[:200]}"

        # 先 pull（处理可能的冲突）
        pull = subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            capture_output=True, text=True, timeout=30, cwd=WORK_DIR
        )

        push = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, timeout=30, cwd=WORK_DIR
        )
        if push.returncode != 0:
            return f"push 失败: {push.stderr[:200]}"
        return "已保存到 GitHub 仓库"
    except Exception as e:
        return f"保存失败: {e}"

# ============================================================
# 核心：ReAct 循环
# ============================================================

def build_system_prompt() -> str:
    tools_desc = "\n".join(
        f"- {name}: {info['desc']} {'[只读]' if info['ro'] else '[可写]'}"
        for name, info in TOOLS.items()
    )

    return f"""你是 AI Coder v2，运行在 Linux 沙箱中的 AI 编程助手。

## 核心工作方式
每轮你只能做一件事：思考 → 调用一个工具 → 看到结果 → 再思考下一个工具。
完成任务后输出 "TASK_COMPLETE" 并总结。

## 可用工具
{tools_desc}

## 工具调用格式（严格）
TOOL: <工具名>
ARG: <参数名>: <参数值>

多行内容（如写文件）：
TOOL: write_file
ARG: path: test.py
ARG: content:
print("hello")
print("world")

## 重要规则
1. 每轮只调用一个工具
2. 不要用 markdown 代码块包裹 TOOL/ARG 格式
3. 绝对不要执行 python3 -m http.server 这类阻塞命令，用 timeout 包裹
4. 测试网页只需确认文件存在，不需要启动服务器
5. 命令失败后分析错误并修复，不要重复同样的错误
6. 创建文件前先用 list_dir 确认目录存在
7. Python 用 python3，Node.js 用 node
8. 写文件时 content 参数必须包含完整代码
9. 完成任务后输出 TASK_COMPLETE 并总结
10. 用中文思考和回复

## 当前工作目录
{WORK_DIR}"""


def run(task: str) -> str:
    print(f"\n{'='*60}")
    print(f"  AI Coder v2 启动")
    print(f"  任务: {task[:100]}{'...' if len(task) > 100 else ''}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": f"任务：{task}\n\n请开始执行。先分析任务，然后逐步完成。"},
    ]

    round_num = 0
    no_tool_count = 0  # 连续未调用工具计数器

    while round_num < MAX_ROUNDS:
        round_num += 1

        # 上下文压缩
        if estimate_tokens(json.dumps(messages, ensure_ascii=False)) > MAX_TOKENS_CONTEXT:
            messages = compact_context(messages)
            print(f"  [系统] 上下文已压缩 (当前第 {round_num} 轮)")

        # 调用 AI
        print(f"\n--- 第 {round_num} 轮 ---")
        response = call_ai(messages)

        if response.startswith("[API 调用失败"):
            print(f"  {response}")
            if round_num == 1:
                return response
            # 非首轮，尝试重试
            time.sleep(5)
            continue

        # 打印完整响应
        print(response)

        # 先解析工具调用（优先于 TASK_COMPLETE 检查）
        tool_name, args = parse_tool_call(response)

        if tool_name and tool_name in TOOLS:
            no_tool_count = 0

            arg_summary = ", ".join(
                f"{k}={str(v)[:80]}..." if len(str(v)) > 80 else f"{k}={v}"
                for k, v in args.items()
            )
            print(f"\n  >> {tool_name}({arg_summary})")

            result = execute_tool(tool_name, args)
            print(f"  >> {result[:500]}")

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"工具执行结果:\n{result}\n\n请继续下一步。"})

            # 工具执行后，如果 AI 同时输出了 TASK_COMPLETE，检查任务是否真的完成
            if "TASK_COMPLETE" in response:
                print(f"\n  [检测到 TASK_COMPLETE + 工具调用，工具已执行]")
                print(f"\n{'='*60}")
                print(f"  任务完成！共 {round_num} 轮")
                print(f"{'='*60}")
                return response

        elif "TASK_COMPLETE" in response:
            # 没有工具调用但有 TASK_COMPLETE
            print(f"\n{'='*60}")
            print(f"  任务完成！共 {round_num} 轮")
            print(f"{'='*60}")
            return response

        else:
            no_tool_count += 1

            # 检查是否有 ARG 但没有 TOOL（格式错误）
            has_arg = any(line.strip().startswith("ARG:") for line in response.split("\n"))
            has_tool = any(line.strip().startswith("TOOL:") for line in response.split("\n"))

            if has_arg and not has_tool:
                hint = "你的格式错误！缺少 TOOL: 行。正确格式：\nTOOL: write_file\nARG: path: guess.py\nARG: content:\n..."
            elif no_tool_count >= 3:
                hint = "请立即调用一个工具来推进任务！使用 TOOL/ARG 格式。如果任务已完成，输出 TASK_COMPLETE。"
            else:
                hint = "请继续执行任务。使用 TOOL/ARG 格式调用工具。"

            if no_tool_count >= 3:
                print(f"  [警告] 连续 {no_tool_count} 轮未调用工具")

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": hint})

    print(f"\n  达到最大轮数 ({MAX_ROUNDS})")
    return "达到最大轮数"


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
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
                # 备份后清空
                backup = Path(WORK_DIR) / "task.txt.bak"
                task_file.rename(backup)
                task_file.write_text("")
            else:
                print("task.txt 为空")
                sys.exit(1)
        else:
            print("用法: python3 ai_coder.py '你的指令'")
            print("或: 将指令写入 task.txt 后运行 python3 ai_coder.py")
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