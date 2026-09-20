"""PyInstaller entry point. stdout is reserved for the Electron handshake."""
import argparse
import getpass
import logging
import os
from pathlib import Path
import sys


def main():
    # Source execution also works from a working directory outside the repository.
    if not getattr(sys, 'frozen', False):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    parser = argparse.ArgumentParser(description='CBOS 本机后端；账号恢复前请完全关闭 CBOS。')
    parser.add_argument('--reset-password', metavar='USERNAME', help='仅重置现有本机账号的密码')
    parser.add_argument('--data-dir', type=Path, help='包含现有 coal_system.db 的绝对路径')
    args, unknown = parser.parse_known_args()
    if unknown:
        parser.error('不支持此命令参数；密码只能按提示隐藏输入，不能放在命令参数中')
    if args.reset_password:
        if not args.data_dir or not args.data_dir.is_absolute() or not (args.data_dir / 'coal_system.db').is_file():
            parser.error('恢复操作需要 --data-dir 指定现有数据库的绝对目录')
        # Set the desktop environment before importing config: never load a web .env.
        os.environ['CBOS_DESKTOP_DATA_DIR'] = str(args.data_dir)
        from desktop.runtime import exclusive_data_lock, reset_local_password
        try:
            with exclusive_data_lock(args.data_dir):
                password = getpass.getpass('新密码（至少 12 位）: ')
                confirm = getpass.getpass('再次输入新密码: ')
                if password != confirm:
                    raise ValueError('两次密码不一致，账号未修改')
                reset_local_password(args.data_dir, args.reset_password, password)
            print('密码已重置，全部会话已撤销。现在可重新启动 CBOS 登录。')
            return 0
        except (ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
    if args.data_dir:
        parser.error('--data-dir 仅用于 --reset-password')
    sys.dont_write_bytecode = True
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    protocol_stdout = sys.stdout
    sys.stdout = sys.stderr
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    try:
        from desktop.runtime import exclusive_data_lock, run_backend
        data_dir = os.environ.get('CBOS_DESKTOP_DATA_DIR', '')
        if not data_dir or not Path(data_dir).is_absolute():
            raise ValueError('CBOS_DESKTOP_DATA_DIR 必须是绝对路径')
        with exclusive_data_lock(Path(data_dir)):
            return run_backend(protocol_stdout=protocol_stdout)
    except Exception:
        logging.exception('桌面后端启动或运行失败')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
