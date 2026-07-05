# startup.py
"""
量化交易系统 - 启动脚本

自动检测电脑上的MT4/MT5终端，让用户选择平台后启动系统。
双击 start.bat 即可运行。
"""

import os
import sys
import glob
import subprocess


def scan_mt5_terminals() -> list:
    """扫描电脑上安装的MT5终端"""
    candidates = []

    # 1. 已知路径
    known = [
        r"D:\交易盘\DLSM MT5\terminal64.exe",
        r"D:\交易盘\DLSM MT5\metatrader64.exe",
    ]
    for p in known:
        if os.path.isfile(p):
            candidates.append(p)

    # 2. 常见安装目录搜索
    search_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\\",
        r"D:\交易盘",
        r"D:\Program Files",
        r"E:\\",
        os.path.expanduser("~\\AppData\\Roaming"),
    ]
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        try:
            # 搜索两层目录下的 terminal64.exe
            for entry in os.listdir(base):
                dir_path = os.path.join(base, entry)
                if not os.path.isdir(dir_path):
                    continue
                # 直接在子目录找
                exe = os.path.join(dir_path, "terminal64.exe")
                if os.path.isfile(exe) and exe not in candidates:
                    candidates.append(exe)
                # 再深一层
                try:
                    for sub in os.listdir(dir_path):
                        sub_path = os.path.join(dir_path, sub)
                        if not os.path.isdir(sub_path):
                            continue
                        exe2 = os.path.join(sub_path, "terminal64.exe")
                        if os.path.isfile(exe2) and exe2 not in candidates:
                            candidates.append(exe2)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    # 3. 通过正在运行的进程查找
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

    # 去重 (规范化路径)
    seen = set()
    unique = []
    for p in candidates:
        norm = os.path.normpath(p)
        if norm.lower() not in seen:
            seen.add(norm.lower())
            unique.append(p)

    return unique


def scan_mt4_terminals() -> list:
    """扫描电脑上安装的MT4终端"""
    candidates = []

    # 1. 已知路径
    known = [
        r"D:\交易盘\DLSM MT4\terminal.exe",
    ]
    for p in known:
        if os.path.isfile(p):
            candidates.append(p)

    # 2. 常见安装目录搜索
    search_dirs = [
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"D:\\",
        r"D:\交易盘",
        r"D:\Program Files",
        r"E:\\",
        os.path.expanduser("~\\AppData\\Roaming"),
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
                    # 排除系统terminal.exe (Windows可能有)
                    if "meta" in dir_path.lower() or "mt4" in dir_path.lower() or "交易" in dir_path or "dlsm" in dir_path.lower():
                        candidates.append(exe)
                try:
                    for sub in os.listdir(dir_path):
                        sub_path = os.path.join(dir_path, sub)
                        if not os.path.isdir(sub_path):
                            continue
                        exe2 = os.path.join(sub_path, "terminal.exe")
                        if os.path.isfile(exe2) and exe2 not in candidates:
                            if "meta" in sub_path.lower() or "mt4" in sub_path.lower() or "交易" in sub_path or "dlsm" in sub_path.lower():
                                candidates.append(exe2)
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    # 3. 正在运行的进程
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

    # 去重
    seen = set()
    unique = []
    for p in candidates:
        norm = os.path.normpath(p)
        if norm.lower() not in seen:
            seen.add(norm.lower())
            unique.append(p)

    return unique


def select_from_list(items: list, item_type: str) -> str:
    """从列表中选择一项"""
    if not items:
        return None

    if len(items) == 1:
        print(f"  只找到一个{item_type}: {items[0]}")
        return items[0]

    print(f"\n  找到 {len(items)} 个{item_type}:")
    for i, path in enumerate(items, 1):
        print(f"    [{i}] {path}")

    while True:
        choice = input(f"  请选择 (1-{len(items)}): ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
        except ValueError:
            pass
        print("  输入无效，请重试")


def write_env(platform: str, mt5_path: str = "", mt4_path: str = ""):
    """写入.env配置文件"""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(project_dir, ".env")

    lines = [
        f"# 量化交易系统配置 (自动生成)",
        f"# 平台: {platform.upper()}",
        f"",
        f"PLATFORM={platform}",
        f"",
    ]

    if platform == "mt5" and mt5_path:
        lines.append(f"# MT5 终端配置")
        lines.append(f"MT5_PATH={mt5_path}")
        lines.append(f"MT5_LOGIN=")
        lines.append(f"MT5_PASSWORD=")
        lines.append(f"MT5_SERVER=")
    elif platform == "mt4" and mt4_path:
        lines.append(f"# MT4 终端配置")
        lines.append(f"MT4_PATH={mt4_path}")
        lines.append(f"MT4_ZMQ_HOST=tcp://127.0.0.1:5555")
        lines.append(f"MT4_ZMQ_PUSH_HOST=tcp://127.0.0.1:5556")

    lines.extend([
        f"",
        f"# 交易配置",
        f"DEFAULT_SYMBOL=XAUUSD",
        f"DEFAULT_TIMEFRAME=H1",
        f"INITIAL_CAPITAL=10000",
        f"",
        f"# 风控参数",
        f"MAX_RISK_PER_TRADE=0.02",
        f"MAX_DAILY_LOSS=0.05",
        f"MAX_POSITIONS=5",
        f"",
        f"# Web服务",
        f"WEB_HOST=127.0.0.1",
        f"WEB_PORT=8000",
    ])

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n  配置已写入: {env_path}")


def check_mt4_running() -> bool:
    """检查MT4终端是否在运行"""
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore"
        )
        # MT4进程名是 terminal.exe (32位)
        for line in result.stdout.splitlines():
            if "terminal.exe" in line.lower() and "terminal64" not in line.lower():
                return True
    except Exception:
        pass
    return False


def check_mt5_running() -> bool:
    """检查MT5终端是否在运行"""
    try:
        result = subprocess.run(
            ["tasklist"], capture_output=True, text=True, timeout=5,
            encoding="gbk", errors="ignore"
        )
        for line in result.stdout.splitlines():
            if "terminal64.exe" in line.lower():
                return True
    except Exception:
        pass
    return False


def launch_terminal(exe_path: str):
    """启动交易终端"""
    if not exe_path or not os.path.isfile(exe_path):
        print(f"  路径无效: {exe_path}")
        return False

    print(f"  正在启动: {exe_path}")
    try:
        os.startfile(exe_path)
        print("  终端启动中，请等待...")
        import time
        time.sleep(3)
        return True
    except Exception as e:
        print(f"  启动失败: {e}")
        return False


def main():
    """主函数"""
    # 设置工作目录为脚本所在目录
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    print()
    print("=" * 60)
    print("       量化交易系统 - 智能启动")
    print("=" * 60)
    print()

    # 第1步: 扫描MT4和MT5
    print("[1/4] 扫描交易平台...")
    print()

    mt5_list = scan_mt5_terminals()
    mt4_list = scan_mt4_terminals()

    mt5_found = len(mt5_list) > 0
    mt4_found = len(mt4_list) > 0

    if mt5_found:
        print(f"  [OK] 找到 MT5 ({len(mt5_list)}个)")
    else:
        print(f"  [--] 未找到 MT5")

    if mt4_found:
        print(f"  [OK] 找到 MT4 ({len(mt4_list)}个)")
    else:
        print(f"  [--] 未找到 MT4")

    if not mt5_found and not mt4_found:
        print()
        print("  未找到任何交易平台！")
        print("  请先安装MT4或MT5终端。")
        print("  安装后把终端放在 D:\\交易盘\\ 或重新运行本脚本。")
        input("\n  按回车键退出...")
        return

    # 第2步: 选择平台
    print()
    print("[2/4] 选择交易平台")
    print()
    print("  ┌─────────────────────────────────────────┐")
    print("  │                                         │")

    if mt5_found:
        print("  │   [1] MT5 (MetaTrader 5)               │")
        print("  │       Python直连，功能完整，推荐使用     │")
    else:
        print("  │   [1] MT5 (未检测到，不可用)            │")

    print("  │                                         │")

    if mt4_found:
        print("  │   [2] MT4 (MetaTrader 4)               │")
        print("  │       需先附加ZMQ桥接EA                 │")
    else:
        print("  │   [2] MT4 (未检测到，不可用)            │")

    print("  │                                         │")
    print("  └─────────────────────────────────────────┘")

    while True:
        choice = input("\n  请选择平台 (1/2): ").strip()

        if choice == "1" and mt5_found:
            platform = "mt5"
            break
        elif choice == "2" and mt4_found:
            platform = "mt4"
            break
        elif choice == "1" and not mt5_found:
            print("  MT5未检测到，请先安装或手动指定路径。")
        elif choice == "2" and not mt4_found:
            print("  MT4未检测到，请先安装或手动指定路径。")
        else:
            print("  输入无效，请输入 1 或 2")

    # 第3步: 选择终端路径 + 检查运行状态
    print()
    print(f"[3/4] 配置 {platform.upper()}")

    selected_path = ""
    if platform == "mt5":
        selected_path = select_from_list(mt5_list, "MT5终端")
        print(f"\n  选择: {selected_path}")

        is_running = check_mt5_running()
        if is_running:
            print("  [OK] MT5终端已在运行")
        else:
            print("  [!] MT5终端未运行")
            launch = input("  是否现在启动? (y/n): ").strip().lower()
            if launch == "y":
                launch_terminal(selected_path)

    elif platform == "mt4":
        selected_path = select_from_list(mt4_list, "MT4终端")
        print(f"\n  选择: {selected_path}")

        is_running = check_mt4_running()
        if is_running:
            print("  [OK] MT4终端已在运行")
        else:
            print("  [!] MT4终端未运行")
            launch = input("  是否现在启动? (y/n): ").strip().lower()
            if launch == "y":
                launch_terminal(selected_path)

        # MT4 需要ZMQ EA
        print()
        print("  [!] MT4模式说明:")
        print("      需要在MT4终端中附加 ZeroMQ 桥接EA。")
        print("      EA文件位置: mt4_bridge/dwx_zmq_bridge.mq4")
        print("      将EA拖到任意图表上即可。")
        ea_ready = input("  EA是否已附加? (y/n): ").strip().lower()
        if ea_ready != "y":
            print("  请先附加EA后再启动。")
            input("\n  按回车键退出...")
            return

    # 写入.env
    write_env(platform, mt5_path=selected_path if platform == "mt5" else "",
              mt4_path=selected_path if platform == "mt4" else "")

    # 第4步: 启动系统
    print()
    print("[4/4] 启动量化交易系统")
    print()
    print(f"  平台: {platform.upper()}")
    print(f"  品种: XAUUSD (黄金)")
    print(f"  地址: http://127.0.0.1:8000")
    print()
    print("-" * 60)
    print()

    input("  按回车键启动系统 (Ctrl+C 取消)...")

    # 启动main.py
    try:
        subprocess.run([sys.executable, "-u", "main.py"], cwd=project_dir)
    except KeyboardInterrupt:
        print("\n  用户取消")
    except Exception as e:
        print(f"\n  启动失败: {e}")
    finally:
        input("\n  按回车键退出...")


if __name__ == "__main__":
    main()
