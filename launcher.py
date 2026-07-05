# -*- coding: utf-8 -*-
"""
量化交易系统 - GUI 启动器

独立运行，不依赖项目其他模块。
自动检测MT4/MT5终端，图形界面选择平台，一键启动系统。
用PyInstaller打包成单exe文件，可在任何Windows电脑运行。
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path


# ==================== 终端检测 ====================

def scan_mt5_terminals():
    """扫描MT5终端"""
    candidates = []
    known = [
        r"D:\交易盘\DLSM MT5\terminal64.exe",
        r"D:\交易盘\DLSM MT5\metatrader64.exe",
    ]
    for p in known:
        if os.path.isfile(p):
            candidates.append(p)

    search_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\\",
        r"D:\交易盘",
        r"D:\Program Files",
        r"E:\\",
        os.path.expanduser(r"~\AppData\Roaming"),
    ]
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.listdir(base):
                dir_path = os.path.join(base, entry)
                if not os.path.isdir(dir_path):
                    continue
                exe = os.path.join(dir_path, "terminal64.exe")
                if os.path.isfile(exe) and exe not in candidates:
                    candidates.append(exe)
                try:
                    for sub in os.listdir(dir_path):
                        sub_path = os.path.join(dir_path, sub)
                        if os.path.isdir(sub_path):
                            exe2 = os.path.join(sub_path, "terminal64.exe")
                            if os.path.isfile(exe2) and exe2 not in candidates:
                                candidates.append(exe2)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='terminal64.exe'", "get", "ExecutablePath"],
            capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore"
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.lower().endswith("terminal64.exe") and line not in candidates:
                    candidates.append(line)
    except Exception:
        pass

    seen = set()
    unique = []
    for p in candidates:
        norm = os.path.normpath(p).lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def scan_mt4_terminals():
    """扫描MT4终端"""
    candidates = []
    known = [r"D:\交易盘\DLSM MT4\terminal.exe"]
    for p in known:
        if os.path.isfile(p):
            candidates.append(p)

    search_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\\",
        r"D:\交易盘",
        r"D:\Program Files",
        r"E:\\",
        os.path.expanduser(r"~\AppData\Roaming"),
    ]
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        try:
            for entry in os.listdir(base):
                dir_path = os.path.join(base, entry)
                if not os.path.isdir(dir_path):
                    continue
                exe = os.path.join(dir_path, "terminal.exe")
                if os.path.isfile(exe) and exe not in candidates:
                    lower_path = dir_path.lower()
                    if any(k in lower_path for k in ["meta", "mt4", "交易", "dlsm"]):
                        candidates.append(exe)
                try:
                    for sub in os.listdir(dir_path):
                        sub_path = os.path.join(dir_path, sub)
                        if os.path.isdir(sub_path):
                            exe2 = os.path.join(sub_path, "terminal.exe")
                            if os.path.isfile(exe2) and exe2 not in candidates:
                                lower_sub = sub_path.lower()
                                if any(k in lower_sub for k in ["meta", "mt4", "交易", "dlsm"]):
                                    candidates.append(exe2)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    try:
        result = subprocess.run(
            ["wmic", "process", "where", "name='terminal.exe'", "get", "ExecutablePath"],
            capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore"
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.lower().endswith("terminal.exe") and line not in candidates:
                    candidates.append(line)
    except Exception:
        pass

    seen = set()
    unique = []
    for p in candidates:
        norm = os.path.normpath(p).lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def check_process_running(process_name):
    """检查进程是否在运行"""
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore"
        )
        return process_name.lower() in result.stdout.lower()
    except Exception:
        return False


# ==================== 颜色主题 ====================

class Colors:
    BG = "#0d1117"
    CARD_BG = "#161b22"
    CARD_BORDER = "#30363d"
    PRIMARY = "#58a6ff"
    SUCCESS = "#3fb950"
    WARNING = "#d29922"
    DANGER = "#f85149"
    TEXT = "#e6edf3"
    TEXT_DIM = "#8b949e"
    ENTRY_BG = "#0d1117"
    ENTRY_BORDER = "#30363d"


# ==================== GUI 主窗口 ====================

class LauncherApp:
    """量化交易系统启动器 - GUI主窗口"""

    def __init__(self, root):
        self.root = root
        self.project_dir = self._find_project_dir()
        self.mt5_list = []
        self.mt4_list = []
        self.selected_platform = tk.StringVar(value="mt5")
        self.mt5_path = tk.StringVar()
        self.mt4_path = tk.StringVar()

        self._setup_window()
        self._create_widgets()
        self._start_scan()

    def _find_project_dir(self):
        """查找项目目录"""
        # 优先查找标准位置
        candidates = [
            r"D:\project\Quant-trading",
            os.path.join(os.path.dirname(os.path.abspath(__file__))),
            os.path.dirname(os.path.abspath(sys.argv[0] if getattr(sys, 'frozen', False) else __file__)),
        ]
        for p in candidates:
            if os.path.isfile(os.path.join(p, "main.py")):
                return p
        # 如果都找不到，返回标准位置
        return r"D:\project\Quant-trading"

    def _setup_window(self):
        """配置窗口"""
        self.root.title("量化交易系统")
        self.root.geometry("640x680")
        self.root.resizable(False, False)
        self.root.configure(bg=Colors.BG)

        # 居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 640) // 2
        y = (self.root.winfo_screenheight() - 680) // 2
        self.root.geometry(f"640x680+{x}+{y}")

        # 图标 (如果有)
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    def _create_widgets(self):
        """创建界面组件"""

        style = ttk.Style()
        style.theme_use("clam")

        # ==================== 标题栏 ====================
        title_frame = tk.Frame(self.root, bg=Colors.BG)
        title_frame.pack(fill="x", padx=30, pady=(25, 5))

        tk.Label(
            title_frame, text="⚡ 量化交易系统",
            font=("Microsoft YaHei UI", 22, "bold"),
            bg=Colors.BG, fg=Colors.PRIMARY
        ).pack(side="left")

        # ==================== 副标题 ====================
        tk.Label(
            self.root,
            text="Quantitative Trading Platform  |  XAUUSD / Crypto",
            font=("Microsoft YaHei UI", 9),
            bg=Colors.BG, fg=Colors.TEXT_DIM
        ).pack(anchor="w", padx=30, pady=(0, 15))

        # ==================== 扫描状态 ====================
        self.scan_frame = tk.Frame(self.root, bg=Colors.BG)
        self.scan_frame.pack(fill="x", padx=30, pady=(0, 10))

        self.scan_label = tk.Label(
            self.scan_frame,
            text="🔍 正在扫描交易平台...",
            font=("Microsoft YaHei UI", 11),
            bg=Colors.BG, fg=Colors.WARNING
        )
        self.scan_label.pack(anchor="w")

        self.scan_progress = ttk.Progressbar(
            self.scan_frame, mode="indeterminate", length=580,
            style="TProgressbar"
        )
        style.configure("TProgressbar", troughcolor=Colors.CARD_BG, fieldcolor=Colors.CARD_BG)

        # ==================== 平台选择卡片 ====================
        self.card_frame = tk.Frame(self.root, bg=Colors.BG)
        self.card_frame.pack(fill="x", padx=30, pady=(10, 5))

        # MT5 卡片
        self.mt5_card = tk.Frame(
            self.card_frame, bg=Colors.CARD_BG,
            highlightbackground=Colors.CARD_BORDER, highlightthickness=1,
            cursor="hand2"
        )
        self.mt5_card.pack(fill="x", pady=(0, 8))

        mt5_header = tk.Frame(self.mt5_card, bg=Colors.CARD_BG)
        mt5_header.pack(fill="x", padx=15, pady=(12, 5))

        tk.Radiobutton(
            mt5_header, text="", variable=self.selected_platform, value="mt5",
            bg=Colors.CARD_BG, fg=Colors.PRIMARY, selectcolor=Colors.CARD_BG,
            activebackground=Colors.CARD_BG, activeforeground=Colors.PRIMARY,
            highlightthickness=0, bd=0, cursor="hand2",
            command=lambda: self._select_card("mt5")
        ).pack(side="left")

        tk.Label(
            mt5_header, text="  MT5  MetaTrader 5",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=Colors.CARD_BG, fg=Colors.TEXT
        ).pack(side="left")

        self.mt5_status_label = tk.Label(
            mt5_header, text="",
            font=("Microsoft YaHei UI", 9),
            bg=Colors.CARD_BG, fg=Colors.TEXT_DIM
        )
        self.mt5_status_label.pack(side="right")

        self.mt5_desc_label = tk.Label(
            self.mt5_card,
            text="Python 直连模式，功能完整，推荐使用",
            font=("Microsoft YaHei UI", 9),
            bg=Colors.CARD_BG, fg=Colors.TEXT_DIM,
            anchor="w"
        )
        self.mt5_desc_label.pack(anchor="w", padx=38, pady=(0, 10))

        self.mt5_combo = ttk.Combobox(
            self.mt5_card, textvariable=self.mt5_path,
            state="readonly", width=75,
            font=("Consolas", 9)
        )

        # MT4 卡片
        self.mt4_card = tk.Frame(
            self.card_frame, bg=Colors.CARD_BG,
            highlightbackground=Colors.CARD_BORDER, highlightthickness=1,
            cursor="hand2"
        )
        self.mt4_card.pack(fill="x", pady=(0, 8))

        mt4_header = tk.Frame(self.mt4_card, bg=Colors.CARD_BG)
        mt4_header.pack(fill="x", padx=15, pady=(12, 5))

        tk.Radiobutton(
            mt4_header, text="", variable=self.selected_platform, value="mt4",
            bg=Colors.CARD_BG, fg=Colors.PRIMARY, selectcolor=Colors.CARD_BG,
            activebackground=Colors.CARD_BG, activeforeground=Colors.PRIMARY,
            highlightthickness=0, bd=0, cursor="hand2",
            command=lambda: self._select_card("mt4")
        ).pack(side="left")

        tk.Label(
            mt4_header, text="  MT4  MetaTrader 4",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=Colors.CARD_BG, fg=Colors.TEXT
        ).pack(side="left")

        self.mt4_status_label = tk.Label(
            mt4_header, text="",
            font=("Microsoft YaHei UI", 9),
            bg=Colors.CARD_BG, fg=Colors.TEXT_DIM
        )
        self.mt4_status_label.pack(side="right")

        self.mt4_desc_label = tk.Label(
            self.mt4_card,
            text="ZeroMQ 桥接模式，需先附加 EA",
            font=("Microsoft YaHei UI", 9),
            bg=Colors.CARD_BG, fg=Colors.TEXT_DIM,
            anchor="w"
        )
        self.mt4_desc_label.pack(anchor="w", padx=38, pady=(0, 10))

        self.mt4_combo = ttk.Combobox(
            self.mt4_card, textvariable=self.mt4_path,
            state="readonly", width=75,
            font=("Consolas", 9)
        )

        # ==================== 终端状态 ====================
        status_frame = tk.Frame(self.root, bg=Colors.BG)
        status_frame.pack(fill="x", padx=30, pady=(5, 10))

        self.terminal_status = tk.Label(
            status_frame, text="",
            font=("Microsoft YaHei UI", 10),
            bg=Colors.BG, fg=Colors.TEXT_DIM
        )
        self.terminal_status.pack(anchor="w")

        # ==================== 配置区域 ====================
        config_frame = tk.Frame(self.root, bg=Colors.CARD_BG,
                                highlightbackground=Colors.CARD_BORDER, highlightthickness=1)
        config_frame.pack(fill="x", padx=30, pady=(5, 10))

        tk.Label(
            config_frame, text="⚙  交易配置",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg=Colors.CARD_BG, fg=Colors.TEXT
        ).pack(anchor="w", padx=15, pady=(10, 8))

        cfg_row = tk.Frame(config_frame, bg=Colors.CARD_BG)
        cfg_row.pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(cfg_row, text="品种:", font=("Microsoft YaHei UI", 10),
                 bg=Colors.CARD_BG, fg=Colors.TEXT_DIM).grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.symbol_var = tk.StringVar(value="XAUUSD")
        tk.Entry(cfg_row, textvariable=self.symbol_var, width=10,
                 font=("Consolas", 10), bg=Colors.ENTRY_BG, fg=Colors.TEXT,
                 insertbackground=Colors.TEXT, relief="solid", bd=1).grid(row=0, column=1, padx=(0, 20))

        tk.Label(cfg_row, text="周期:", font=("Microsoft YaHei UI", 10),
                 bg=Colors.CARD_BG, fg=Colors.TEXT_DIM).grid(row=0, column=2, padx=(0, 5), sticky="w")
        self.timeframe_var = tk.StringVar(value="H1")
        ttk.Combobox(cfg_row, textvariable=self.timeframe_var, width=6,
                     values=["M1", "M5", "M15", "M30", "H1", "H4", "D1"],
                     state="readonly", font=("Consolas", 10)).grid(row=0, column=3, padx=(0, 20))

        tk.Label(cfg_row, text="端口:", font=("Microsoft YaHei UI", 10),
                 bg=Colors.CARD_BG, fg=Colors.TEXT_DIM).grid(row=0, column=4, padx=(0, 5), sticky="w")
        self.port_var = tk.StringVar(value="8000")
        tk.Entry(cfg_row, textvariable=self.port_var, width=6,
                 font=("Consolas", 10), bg=Colors.ENTRY_BG, fg=Colors.TEXT,
                 insertbackground=Colors.TEXT, relief="solid", bd=1).grid(row=0, column=5)

        # ==================== 底部按钮 ====================
        btn_frame = tk.Frame(self.root, bg=Colors.BG)
        btn_frame.pack(side="bottom", fill="x", padx=30, pady=(5, 20))

        self.rescan_btn = tk.Button(
            btn_frame, text="🔄 重新扫描",
            font=("Microsoft YaHei UI", 10),
            bg=Colors.CARD_BG, fg=Colors.TEXT_DIM,
            activebackground=Colors.CARD_BORDER, activeforeground=Colors.TEXT,
            relief="solid", bd=1, padx=15, pady=8, cursor="hand2",
            command=self._start_scan
        )
        self.rescan_btn.pack(side="left")

        self.launch_btn = tk.Button(
            btn_frame, text="🚀 启动交易系统",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg=Colors.PRIMARY, fg="#ffffff",
            activebackground="#79b8ff", activeforeground="#ffffff",
            relief="flat", bd=0, padx=30, pady=10, cursor="hand2",
            command=self._launch
        )
        self.launch_btn.pack(side="right")

        # ==================== 项目路径提示 ====================
        self.proj_label = tk.Label(
            self.root,
            text=f"📁 {self.project_dir}",
            font=("Consolas", 8),
            bg=Colors.BG, fg=Colors.TEXT_DIM
        )
        self.proj_label.pack(side="bottom", fill="x", padx=30)

    def _select_card(self, platform):
        """选中某个平台卡片"""
        if platform == "mt5":
            self.mt5_card.config(highlightbackground=Colors.PRIMARY, highlightthickness=2)
            self.mt4_card.config(highlightbackground=Colors.CARD_BORDER, highlightthickness=1)
        else:
            self.mt5_card.config(highlightbackground=Colors.CARD_BORDER, highlightthickness=1)
            self.mt4_card.config(highlightbackground=Colors.PRIMARY, highlightthickness=2)

    def _start_scan(self):
        """启动扫描线程"""
        self.scan_label.config(text="🔍 正在扫描交易平台...", fg=Colors.WARNING)
        self.scan_progress.pack(fill="x", pady=(5, 0))
        self.scan_progress.start(10)

        self.launch_btn.config(state="disabled", bg=Colors.CARD_BORDER)
        self.rescan_btn.config(state="disabled")

        # 清空已有
        self.mt5_combo.pack_forget()
        self.mt4_combo.pack_forget()

        thread = threading.Thread(target=self._do_scan, daemon=True)
        thread.start()

    def _do_scan(self):
        """执行扫描（后台线程）"""
        mt5_list = scan_mt5_terminals()
        mt4_list = scan_mt4_terminals()
        self.root.after(0, lambda: self._scan_done(mt5_list, mt4_list))

    def _scan_done(self, mt5_list, mt4_list):
        """扫描完成回调"""
        self.mt5_list = mt5_list
        self.mt4_list = mt4_list

        self.scan_progress.stop()
        self.scan_progress.pack_forget()
        self.rescan_btn.config(state="normal")

        mt5_found = len(mt5_list) > 0
        mt4_found = len(mt4_list) > 0

        # 更新状态
        if mt5_found and mt4_found:
            self.scan_label.config(text="✅ 检测到 MT5 和 MT4", fg=Colors.SUCCESS)
        elif mt5_found:
            self.scan_label.config(text="✅ 检测到 MT5（未检测到 MT4）", fg=Colors.SUCCESS)
        elif mt4_found:
            self.scan_label.config(text="✅ 检测到 MT4（未检测到 MT5）", fg=Colors.SUCCESS)
        else:
            self.scan_label.config(text="❌ 未检测到任何交易平台", fg=Colors.DANGER)
            self.launch_btn.config(state="disabled")
            return

        # 更新 MT5 卡片
        if mt5_found:
            self.mt5_path.set(mt5_list[0])
            self.mt5_combo["values"] = mt5_list
            self.mt5_combo.current(0)
            self.mt5_combo.pack(fill="x", padx=15, pady=(0, 10))

            mt5_running = check_process_running("terminal64.exe")
            if mt5_running:
                self.mt5_status_label.config(text="● 运行中", fg=Colors.SUCCESS)
            else:
                self.mt5_status_label.config(text="○ 未运行", fg=Colors.WARNING)
        else:
            self.mt5_status_label.config(text="未检测到", fg=Colors.TEXT_DIM)
            self.mt5_desc_label.config(text="请先安装 MT5 终端")

        # 更新 MT4 卡片
        if mt4_found:
            self.mt4_path.set(mt4_list[0])
            self.mt4_combo["values"] = mt4_list
            self.mt4_combo.current(0)
            self.mt4_combo.pack(fill="x", padx=15, pady=(0, 10))

            mt4_running = check_process_running("terminal.exe")
            if mt4_running:
                self.mt4_status_label.config(text="● 运行中", fg=Colors.SUCCESS)
            else:
                self.mt4_status_label.config(text="○ 未运行", fg=Colors.WARNING)
        else:
            self.mt4_status_label.config(text="未检测到", fg=Colors.TEXT_DIM)
            self.mt4_desc_label.config(text="请先安装 MT4 终端")

        # 自动选择可用平台
        if mt5_found:
            self.selected_platform.set("mt5")
            self._select_card("mt5")
        elif mt4_found:
            self.selected_platform.set("mt4")
            self._select_card("mt4")

        # 更新终端状态
        if self.selected_platform.get() == "mt5":
            running = check_process_running("terminal64.exe")
            self.terminal_status.config(
                text=f"✅ MT5 终端{'已运行' if running else '未运行（启动时自动打开）'}"
            )
        else:
            running = check_process_running("terminal.exe")
            self.terminal_status.config(
                text=f"✅ MT4 终端{'已运行' if running else '未运行（启动时自动打开）'}"
            )

        self.launch_btn.config(state="normal", bg=Colors.PRIMARY)

    def _write_env(self):
        """写入.env配置文件"""
        platform = self.selected_platform.get()
        env_path = os.path.join(self.project_dir, ".env")

        lines = [
            "# 量化交易系统配置 (GUI启动器自动生成)",
            f"PLATFORM={platform}",
            "",
        ]

        if platform == "mt5":
            path = self.mt5_path.get()
            if path:
                lines.append(f"MT5_PATH={path}")
            lines.append("MT5_LOGIN=")
            lines.append("MT5_PASSWORD=")
            lines.append("MT5_SERVER=")
        elif platform == "mt4":
            path = self.mt4_path.get()
            if path:
                lines.append(f"MT4_PATH={path}")
            lines.append("MT4_ZMQ_HOST=tcp://127.0.0.1:5555")
            lines.append("MT4_ZMQ_PUSH_HOST=tcp://127.0.0.1:5556")

        lines.extend([
            "",
            f"DEFAULT_SYMBOL={self.symbol_var.get()}",
            f"DEFAULT_TIMEFRAME={self.timeframe_var.get()}",
            "INITIAL_CAPITAL=10000",
            "",
            "MAX_RISK_PER_TRADE=0.02",
            "MAX_DAILY_LOSS=0.05",
            "MAX_POSITIONS=5",
            "",
            f"WEB_HOST=127.0.0.1",
            f"WEB_PORT={self.port_var.get()}",
        ])

        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _launch(self):
        """启动交易系统"""
        platform = self.selected_platform.get()

        # 验证选择
        if platform == "mt5" and not self.mt5_path.get():
            messagebox.showwarning("提示", "请先选择 MT5 终端路径")
            return
        if platform == "mt4" and not self.mt4_path.get():
            messagebox.showwarning("提示", "请先选择 MT4 终端路径")
            return

        # 验证项目目录
        main_py = os.path.join(self.project_dir, "main.py")
        if not os.path.isfile(main_py):
            messagebox.showerror("错误",
                f"未找到项目文件: {main_py}\n\n"
                "请确保项目目录存在且包含 main.py")
            return

        # 写入配置
        self._write_env()

        # 关闭当前窗口
        self.root.destroy()

        # 启动终端 + 主程序
        if platform == "mt5":
            path = self.mt5_path.get()
            if not check_process_running("terminal64.exe") and os.path.isfile(path):
                try:
                    os.startfile(path)
                except Exception:
                    pass
        elif platform == "mt4":
            path = self.mt4_path.get()
            if not check_process_running("terminal.exe") and os.path.isfile(path):
                try:
                    os.startfile(path)
                except Exception:
                    pass

        # 启动main.py (新控制台窗口)
        try:
            subprocess.Popen(
                [sys.executable, "-u", "main.py"],
                cwd=self.project_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        except Exception as e:
            messagebox.showerror("启动失败", str(e))


def main():
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
