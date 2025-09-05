#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
UFW Manager - 交互式UFW防火墙管理工具
主程序文件
"""

import os
import sys
import subprocess
import re
import yaml
import getpass
import tempfile
import shutil
from datetime import datetime
from yaml.representer import SafeRepresenter

# 用于YAML字面块标量的自定义字符串类和相关函数
class LiteralString(str):
    """用于YAML字面块标量的自定义字符串类"""
    pass

def change_style(style, representer):
    """更改YAML标量样式的辅助函数"""
    def new_representer(dumper, data):
        scalar = representer(dumper, data)
        scalar.style = style
        return scalar
    return new_representer

# 创建字面块标量表示器
represent_literal_str = change_style('|', SafeRepresenter.represent_str)
yaml.add_representer(LiteralString, represent_literal_str)

class UFWManager:
    """UFW管理器主类"""
    
    def __init__(self):
        """初始化UFW管理器"""
        self.check_dependencies()
        self.setup_logging()
        self.ensure_directories()
        
    def check_dependencies(self):
        """检查依赖项"""
        try:
            import yaml
        except ImportError:
            self.print_error("缺少PyYAML依赖，请运行: pip install PyYAML")
            sys.exit(1)
    
    def setup_logging(self):
        """设置日志记录"""
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.operation_log = os.path.join(self.log_dir, 'operations.log')
        self.error_log = os.path.join(self.log_dir, 'errors.log')
        
    def ensure_directories(self):
        """确保必要的目录存在"""
        self.rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')
        self.backup_dir = os.path.join(self.rules_dir, 'backup')
        self.templates_dir = os.path.join(self.rules_dir, 'templates')
        
        for directory in [self.rules_dir, self.backup_dir, self.templates_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def print_color(self, text, color='white'):
        """打印彩色文本"""
        colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'white': '\033[97m',
            'reset': '\033[0m'
        }
        
        print(f"{colors.get(color, colors['white'])}{text}{colors['reset']}")
    
    def print_error(self, message):
        """打印错误信息"""
        self.print_color(f"错误: {message}", 'red')
        self.log_error(message)
    
    def print_success(self, message):
        """打印成功信息"""
        self.print_color(f"成功: {message}", 'green')
        self.log_operation(message)
    
    def print_warning(self, message):
        """打印警告信息"""
        self.print_color(f"警告: {message}", 'yellow')
        self.log_operation(f"警告: {message}")
    
    def print_info(self, message):
        """打印一般信息"""
        self.print_color(message, 'blue')
        self.log_operation(message)
    
    def log_operation(self, message):
        """记录操作日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(self.operation_log, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"无法记录操作日志: {e}")
    
    def log_error(self, message):
        """记录错误日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with open(self.error_log, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"无法记录错误日志: {e}")
    
    def check_sudo_privileges(self):
        """检查sudo权限"""
        try:
            # 检查是否以root用户运行
            if os.geteuid() == 0:
                self.print_info("已以root用户运行")
                return True
            
            # 检查sudo是否可用
            result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
            if result.returncode == 0:
                self.print_info("sudo权限已可用")
                return True
            
            # 提示用户输入sudo密码
            self.print_info("需要管理员权限来管理UFW")
            password = getpass.getpass("请输入sudo密码: ")
            
            # 验证密码
            result = subprocess.run(['sudo', '-S', 'true'], input=password + '\n',
                                 capture_output=True, text=True)
            
            if result.returncode == 0:
                self.print_success("权限验证成功")
                self.log_operation("sudo权限验证成功")
                return True
            else:
                self.print_error("密码错误或权限不足")
                return False
                
        except Exception as e:
            self.print_error(f"权限检查失败: {e}")
            return False
    
    def run_ufw_command(self, command):
        """运行UFW命令"""
        try:
            # 首先尝试无密码运行
            cmd = ['sudo', '-n'] + command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            
            # 如果无密码失败，提示用户输入密码
            if "password" in result.stderr.lower():
                self.print_info("需要输入sudo密码")
                password = getpass.getpass("请输入sudo密码: ")
                
                # 使用用户输入的密码运行命令
                cmd = ['sudo', '-S'] + command
                result = subprocess.run(cmd, input=password + '\n',
                                      capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.print_error("密码错误或权限不足")
                    return False, "", result.stderr
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            self.log_error(f"运行UFW命令失败: {e}")
            return False, "", str(e)
    
    def refresh_sudo_session(self):
        """刷新sudo会话，防止超时"""
        try:
            # 尝试刷新sudo会话
            result = subprocess.run(['sudo', '-n', '-v'], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_operation("sudo会话刷新成功")
                return True
            else:
                # 如果刷新失败，提示用户输入密码
                self.print_info("sudo会话已过期，需要重新验证")
                password = getpass.getpass("请输入sudo密码: ")
                
                result = subprocess.run(['sudo', '-S', '-v'], input=password + '\n',
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.log_operation("sudo会话刷新成功")
                    return True
                else:
                    self.print_warning("sudo会话刷新失败")
                    return False
                
        except Exception as e:
            self.log_error(f"刷新sudo会话失败: {e}")
            return False
    
    def detect_ssh_port(self):
        """检测SSH端口"""
        try:
            # 检查sshd_config文件
            ssh_config = '/etc/ssh/sshd_config'
            if os.path.exists(ssh_config):
                with open(ssh_config, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('Port ') and not line.startswith('#'):
                            port = line.split()[1]
                            return int(port)
            
            # 检查当前监听的SSH端口
            result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'sshd' in line:
                        match = re.search(r':(\d+)\s', line)
                        if match:
                            return int(match.group(1))
            
            # 默认返回22
            return 22
            
        except Exception as e:
            self.print_error(f"检测SSH端口失败: {e}")
            return 22
    
    def confirm_action(self, message, default_yes=True):
        """确认操作，默认选择是"""
        default = "Y" if default_yes else "N"
        prompt = f"{message} [{default}]: "
        
        while True:
            try:
                choice = input(prompt).strip().upper()
                if not choice:
                    return default_yes
                elif choice in ['Y', 'YES']:
                    return True
                elif choice in ['N', 'NO']:
                    return False
                else:
                    self.print_warning("请输入 Y 或 N")
            except KeyboardInterrupt:
                self.print_info("\n操作已取消")
                return False
    
    def initialize_ufw(self):
        """一键初始化UFW"""
        self.print_info("开始UFW初始化...")
        
        # 检测SSH端口
        ssh_port = self.detect_ssh_port()
        self.print_info(f"检测到SSH端口: {ssh_port}")
        
        # 让用户确认SSH端口
        try:
            user_port = input(f"请确认SSH端口 [{ssh_port}]: ").strip()
            if user_port:
                try:
                    ssh_port = int(user_port)
                except ValueError:
                    self.print_error("无效的端口号")
                    return
        except KeyboardInterrupt:
            self.print_info("\n操作已取消")
            return
        
        # 显示红色警告信息
        self.print_color("\n" + "="*50, 'red')
        self.print_color("警告: 此操作将重置UFW到默认状态", 'red')
        self.print_color("所有现有规则将被删除", 'red')
        self.print_color("但会保护SSH端口以防止被锁定", 'red')
        self.print_color("="*50, 'red')
        
        # 二次验证，默认Y
        if not self.confirm_action("确定要继续初始化吗？", default_yes=True):
            self.print_info("初始化已取消")
            return
        
        # 重置UFW（使用--force选项跳过确认）
        self.print_info("正在重置UFW...")
        success, stdout, stderr = self.run_ufw_command(['ufw', '--force', 'reset'])
        
        if not success:
            self.print_error(f"重置UFW失败: {stderr}")
            return
        
        # 设置默认策略
        self.print_info("设置默认策略...")
        self.run_ufw_command(['ufw', 'default', 'deny', 'incoming'])
        self.run_ufw_command(['ufw', 'default', 'allow', 'outgoing'])
        
        # 允许SSH端口
        self.print_info(f"允许SSH端口 {ssh_port}...")
        self.run_ufw_command(['ufw', 'allow', f'{ssh_port}/tcp'])
        
        # 启用UFW（使用--force选项跳过确认）
        self.print_info("启用UFW...")
        success, stdout, stderr = self.run_ufw_command(['ufw', '--force', 'enable'])
        
        if success:
            self.print_success("UFW初始化完成")
            self.print_success(f"SSH端口 {ssh_port} 已允许访问")
        else:
            self.print_error(f"启用UFW失败: {stderr}")
    
    def get_ufw_status(self):
        """获取UFW状态（使用verbose模式）"""
        success, stdout, stderr = self.run_ufw_command(['ufw', 'status', 'verbose'])
        if success:
            return stdout
        else:
            self.print_error(f"获取UFW状态失败: {stderr}")
            return None
    
    def is_rule_header(self, line):
        """检测是否为规则列表表头行"""
        return line.startswith('To') and line.endswith('From')
    
    def truncate_ufw_status(self, status_output):
        """截断UFW状态输出，只显示状态信息，不包含规则列表"""
        if not status_output:
            return ""
        
        lines = status_output.split('\n')
        truncated_lines = []
        
        # 只显示状态信息的前几行，不包含规则列表
        for line in lines:
            line = line.strip()
            if self.is_rule_header(line):
                # 遇到规则列表表头，停止收集
                break
            # 收集所有非空行，直到遇到规则表头
            if line:
                truncated_lines.append(line)
        
        return '\n'.join(truncated_lines)
    
    def get_ufw_status_numbered(self):
        """获取带编号的UFW状态"""
        success, stdout, stderr = self.run_ufw_command(['ufw', 'status', 'numbered'])
        if success:
            return stdout
        else:
            self.print_error(f"获取UFW状态失败: {stderr}")
            return None
    
    def extract_rules_from_numbered(self, numbered_output):
        """从编号状态输出中提取纯规则列表部分"""
        if not numbered_output:
            return ""
        
        lines = numbered_output.split('\n')
        rule_lines = []
        in_rules_section = False
        
        for line in lines:
            line = line.strip()
            # 跳过状态行
            if line.startswith('Status:'):
                continue
            # 开始规则部分
            if self.is_rule_header(line):
                in_rules_section = True
                rule_lines.append(line)
                continue
            # 收集规则行
            if in_rules_section and line:
                rule_lines.append(line)
        
        return '\n'.join(rule_lines)
    
    def show_ufw_status_and_rules(self):
        """显示UFW状态和规则列表"""
        self.print_info("获取UFW状态和规则...")
        
        # 获取状态信息（使用verbose模式）
        status = self.get_ufw_status()
        if status:
            self.print_color("\n=== UFW状态信息 ===", 'blue')
            # 截断状态信息，只显示状态部分，不包含规则列表
            truncated_status = self.truncate_ufw_status(status)
            print(truncated_status)
        
        # 获取编号规则列表
        numbered_status = self.get_ufw_status_numbered()
        if numbered_status:
            self.print_color("\n=== 规则列表 ===", 'blue')
            # 只显示规则列表部分
            rules_only = self.extract_rules_from_numbered(numbered_status)
            print(rules_only)
        
        # 提供操作选项
        self.print_color("\n=== 操作选项 ===", 'blue')
        print("1. 启用防火墙")
        print("2. 禁用防火墙")
        print("3. 重载防火墙")
        print("4. 返回主菜单")
        
        try:
            choice = input("\n请选择操作 [1-4]: ").strip()
            
            if choice == '1':
                self.enable_ufw()
            elif choice == '2':
                self.disable_ufw()
            elif choice == '3':
                self.reload_ufw()
            elif choice == '4':
                return
            else:
                self.print_warning("无效选择，将返回上一级菜单")
                return
                
        except KeyboardInterrupt:
            self.print_info("\n操作已取消")
    
    def enable_ufw(self):
        """启用UFW（使用--force选项跳过确认）"""
        success, stdout, stderr = self.run_ufw_command(['ufw', '--force', 'enable'])
        
        if success:
            self.print_success("UFW已启用")
        else:
            self.print_error(f"启用UFW失败: {stderr}")
    
    def disable_ufw(self):
        """禁用UFW"""
        success, stdout, stderr = self.run_ufw_command(['ufw', 'disable'])
        
        if success:
            self.print_success("UFW已禁用")
        else:
            self.print_error(f"禁用UFW失败: {stderr}")
    
    def reload_ufw(self):
        """重载UFW"""
        success, stdout, stderr = self.run_ufw_command(['ufw', 'reload'])
        
        if success:
            self.print_success("UFW已重载")
        else:
            self.print_error(f"重载UFW失败: {stderr}")
    
    def validate_port(self, port_str):
        """验证端口号"""
        try:
            # 检查单个端口
            if port_str.isdigit():
                port_num = int(port_str)
                if 1 <= port_num <= 65535:
                    return True, port_num
                else:
                    return False, "端口号必须在1-65535范围内"
            
            # 检查端口范围
            if '-' in port_str:
                parts = port_str.split('-')
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    start = int(parts[0])
                    end = int(parts[1])
                    if 1 <= start <= end <= 65535:
                        return True, port_str
                    else:
                        return False, "端口范围无效，必须在1-65535范围内且起始端口不大于结束端口"
            
            return False, "无效的端口格式"
            
        except Exception:
            return False, "无效的端口格式"
    
    def check_duplicate_rule(self, port, protocol, action='allow', direction='in', ip='any'):
        """检查是否已存在相同的规则"""
        try:
            # 获取当前规则列表
            numbered_status = self.get_ufw_status_numbered()
            if not numbered_status:
                return False
            
            # 构建要检查的规则字符串
            if protocol:
                rule_str = f"{action.upper()} {direction.upper()} {port}/{protocol}"
            else:
                rule_str = f"{action.upper()} {direction.upper()} {port}"
            
            if ip != 'any':
                rule_str += f" FROM {ip}"
            
            # 检查是否已存在相同规则
            for line in numbered_status.split('\n'):
                line = line.strip()
                if line.startswith('[') and ']' in line:
                    # 提取规则内容
                    parts = line.split(']', 1)
                    if len(parts) > 1:
                        rule_content = parts[1].strip()
                        # 标准化比较（忽略空格和大小写差异）
                        if rule_content.replace(' ', '').upper() == rule_str.replace(' ', '').upper():
                            return True
            
            return False
            
        except Exception:
            return False
    
    def format_rule_display(self, port, protocol, action='allow', direction='in', ip='any'):
        """格式化规则显示"""
        # 构建UFW命令
        cmd_parts = ['ufw', action]
        if direction != 'in':
            cmd_parts.append(direction)
        
        if protocol:
            port_spec = f"{port}/{protocol}"
        else:
            port_spec = port
        
        cmd_parts.append(port_spec)
        
        if ip != 'any':
            cmd_parts.append(f"from {ip}")
        
        ufw_command = ' '.join(cmd_parts)
        
        display_lines = [
            f"- 端口: {port}",
            f"- 协议: {protocol if protocol else 'TCP+UDP'}",
            f"- 动作: {action}",
            f"- 方向: {direction}",
            f"- 来源: {ip}",
            f"",
            f"UFW命令: {ufw_command}"
        ]
        return '\n   '.join(display_lines)
    
    def add_rule_simple(self, port, protocol):
        """简单模式添加规则"""
        # 设置默认值
        action = 'allow'
        direction = 'in'
        ip = 'any'
        
        # 检查重复规则
        if self.check_duplicate_rule(port, protocol, action, direction, ip):
            self.print_warning("相同的规则已存在")
            return False
        
        # 构建规则命令
        if protocol:
            rule_cmd = ['ufw', action, f"{port}/{protocol}"]
        else:
            rule_cmd = ['ufw', action, port]
        
        # 执行命令
        success, stdout, stderr = self.run_ufw_command(rule_cmd)
        
        if success:
            self.print_success("规则添加成功")
            return True
        else:
            self.print_error(f"添加规则失败: {stderr}")
            return False
    
    def add_rule_advanced(self, port, protocol):
        """高级模式添加规则"""
        self.print_color("\n=== 高级设置 ===", 'blue')
        
        # 显示已设置的部分
        print("已设置的部分:")
        print(f"- 端口: {port}")
        print(f"- 协议: {protocol if protocol else 'TCP+UDP'}")
        print()
        
        try:
            # 选择动作
            print("选择动作:")
            print("1. 允许 (allow) [默认]")
            print("2. 拒绝 (deny)")
            print("3. 拒绝并拒绝连接 (reject)")
            
            action_choice = input(f"请选择动作 [1-3] [默认: 1]: ").strip()
            if not action_choice:
                action = 'allow'
            elif action_choice == '1':
                action = 'allow'
            elif action_choice == '2':
                action = 'deny'
            elif action_choice == '3':
                action = 'reject'
            else:
                self.print_error("无效选择")
                return False
            
            # 选择方向
            print("\n选择方向:")
            print("1. 入站 (in) [默认]")
            print("2. 出站 (out)")
            print("3. 路由 (routed)")
            
            direction_choice = input(f"请选择方向 [1-3] [默认: 1]: ").strip()
            if not direction_choice:
                direction = 'in'
            elif direction_choice == '1':
                direction = 'in'
            elif direction_choice == '2':
                direction = 'out'
            elif direction_choice == '3':
                direction = 'routed'
            else:
                self.print_error("无效选择")
                return False
            
            # 输入IP地址
            ip = input("\n输入IP地址 (可选，留空表示所有IP): ").strip()
            if not ip:
                ip = 'any'
            
            # 显示最终规则
            print("\n最终规则:")
            print(self.format_rule_display(port, protocol, action, direction, ip))
            
            # 确认操作
            if not self.confirm_action("确定要添加此规则吗？"):
                self.print_info("添加规则已取消")
                return False
            
            # 检查重复规则
            if self.check_duplicate_rule(port, protocol, action, direction, ip):
                self.print_warning("相同的规则已存在")
                return False
            
            # 构建规则命令
            rule_parts = [action]
            if direction != 'in':
                rule_parts.append(direction)
            
            if protocol:
                port_spec = f"{port}/{protocol}"
            else:
                port_spec = port
            
            rule_parts.append(port_spec)
            
            if ip != 'any':
                rule_parts.append(f"from {ip}")
            
            rule_cmd = ['ufw'] + rule_parts
            
            # 执行命令
            success, stdout, stderr = self.run_ufw_command(rule_cmd)
            
            if success:
                self.print_success("规则添加成功")
                return True
            else:
                self.print_error(f"添加规则失败: {stderr}")
                return False
                
        except KeyboardInterrupt:
            self.print_info("\n操作已取消")
            return False
    
    def add_rule(self):
        """添加规则"""
        self.print_color("\n=== 添加防火墙规则 ===", 'blue')
        
        try:
            # 输入端口号
            while True:
                port = input("请输入端口号 (如 80, 443, 8080): ").strip()
                if not port:
                    self.print_error("端口不能为空")
                    continue
                
                is_valid, result = self.validate_port(port)
                if is_valid:
                    port = result
                    break
                else:
                    self.print_error(f"无效端口: {result}")
            
            # 选择协议
            print("\n选择协议:")
            print("1. TCP (tcp)")
            print("2. UDP (udp)")
            print("3. TCP+UDP (both)")
            
            protocol_choice = input(f"请选择协议 [1-3] [默认: 3]: ").strip()
            if not protocol_choice or protocol_choice == '3':
                protocol = ''  # both
            elif protocol_choice == '1':
                protocol = 'tcp'
            elif protocol_choice == '2':
                protocol = 'udp'
            else:
                self.print_error("无效选择")
                return
            
            # 选择操作
            print("\n选择操作:")
            print("1. 将要添加的规则:")
            print(f"   {self.format_rule_display(port, protocol)}")
            print("2. 高级设置")
            
            operation_choice = input(f"请选择操作 [1-2] [默认: 1]: ").strip()
            
            if not operation_choice or operation_choice == '1':
                # 规则展示模式
                return self.add_rule_simple(port, protocol)
            elif operation_choice == '2':
                # 高级设置模式
                return self.add_rule_advanced(port, protocol)
            else:
                self.print_error("无效选择")
                return False
                
        except KeyboardInterrupt:
            self.print_info("\n操作已取消")
            return False
    
    def delete_rule(self):
        """删除规则"""
        self.print_info("删除规则...")
        
        # 获取当前规则列表
        numbered_status = self.get_ufw_status_numbered()
        if not numbered_status:
            self.print_error("无法获取规则列表")
            return
        
        self.print_color("\n当前规则列表:", 'blue')
        print(numbered_status)
        
        try:
            # 输入要删除的规则编号
            rule_num = input("请输入要删除的规则编号: ").strip()
            if not rule_num.isdigit():
                self.print_error("请输入有效的数字")
                return
            
            # 确认操作
            if not self.confirm_action(f"确定要删除规则 {rule_num} 吗？"):
                self.print_info("删除规则已取消")
                return
            
            # 执行删除命令
            success, stdout, stderr = self.run_ufw_command(['ufw', 'delete', rule_num])
            
            if success:
                self.print_success(f"规则 {rule_num} 删除成功")
            else:
                self.print_error(f"删除规则失败: {stderr}")
                
        except KeyboardInterrupt:
            self.print_info("\n操作已取消")
    
    def export_rules_to_yaml(self):
        """导出规则到YAML文件"""
        self.print_info("导出规则到YAML文件...")
        
        try:
            # 获取编号规则
            numbered_status = self.get_ufw_status_numbered()
            if not numbered_status:
                self.print_error("无法获取规则列表")
                return
            
            # 解析规则
            rules = []
            for line in numbered_status.split('\n'):
                line = line.strip()
                if line.startswith('[') and ']' in line:
                    # 提取规则编号和内容
                    parts = line.split(']', 1)
                    rule_num = parts[0].strip('[] ')
                    rule_content = parts[1].strip()
                    
                    if rule_content and not rule_content.startswith('Status:'):
                        rules.append({
                            'number': rule_num,
                            'content': rule_content
                        })
            
            # 构建YAML数据结构（移除ufw_status字段）
            yaml_data = {
                'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'rules': rules
            }
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ufw_rules_{timestamp}.yaml"
            filepath = os.path.join(self.rules_dir, filename)
            
            # 写入YAML文件
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)
            
            self.print_success(f"规则已导出到: {filepath}")
            
        except Exception as e:
            self.print_error(f"导出规则失败: {e}")
    
    def import_rules_from_yaml(self):
        """从YAML文件导入规则"""
        self.print_info("从YAML文件导入规则...")
        
        try:
            # 列出可用的YAML文件
            yaml_files = [f for f in os.listdir(self.rules_dir) if f.endswith('.yaml')]
            if not yaml_files:
                self.print_error("没有找到YAML规则文件")
                return
            
            self.print_color("\n可用的YAML文件:", 'blue')
            for i, filename in enumerate(yaml_files, 1):
                print(f"{i}. {filename}")
            
            # 选择文件
            choice = input("请选择要导入的文件编号: ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(yaml_files):
                self.print_error("无效选择")
                return
            
            selected_file = yaml_files[int(choice) - 1]
            filepath = os.path.join(self.rules_dir, selected_file)
            
            # 读取YAML文件
            with open(filepath, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            if not yaml_data or 'rules' not in yaml_data:
                self.print_error("YAML文件格式错误")
                return
            
            # 显示规则信息
            self.print_info(f"文件: {selected_file}")
            self.print_info(f"导出时间: {yaml_data.get('export_time', '未知')}")
            self.print_info(f"规则数量: {len(yaml_data['rules'])}")
            
            # 确认导入
            if not self.confirm_action("确定要导入这些规则吗？"):
                self.print_info("导入规则已取消")
                return
            
            # 导入规则
            success_count = 0
            for rule in yaml_data['rules']:
                if 'content' in rule:
                    # 解析规则内容并重建命令
                    rule_content = rule['content']
                    
                    # 简单的规则解析（可以根据需要扩展）
                    if 'ALLOW' in rule_content.upper():
                        action = 'allow'
                    elif 'DENY' in rule_content.upper():
                        action = 'deny'
                    elif 'REJECT' in rule_content.upper():
                        action = 'reject'
                    else:
                        continue
                    
                    # 提取端口信息
                    port_match = re.search(r'(\d+)(?:\s|$)', rule_content)
                    if port_match:
                        port = port_match.group(1)
                        
                        # 构建命令
                        rule_cmd = ['ufw', action, port]
                        
                        # 执行命令
                        success, stdout, stderr = self.run_ufw_command(rule_cmd)
                        if success:
                            success_count += 1
                        else:
                            self.print_error(f"导入规则失败: {stderr}")
            
            self.print_success(f"成功导入 {success_count} 条规则")
            
        except Exception as e:
            self.print_error(f"导入规则失败: {e}")
    
    def organize_rules(self):
        """整理规则"""
        self.print_info("整理规则...")
        
        try:
            # 列出可用的YAML文件
            yaml_files = [f for f in os.listdir(self.rules_dir) if f.endswith('.yaml')]
            if not yaml_files:
                self.print_error("没有找到YAML规则文件")
                return
            
            self.print_color("\n可用的YAML文件:", 'blue')
            for i, filename in enumerate(yaml_files, 1):
                print(f"{i}. {filename}")
            
            # 选择文件
            choice = input("请选择要整理的文件编号: ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(yaml_files):
                self.print_error("无效选择")
                return
            
            selected_file = yaml_files[int(choice) - 1]
            filepath = os.path.join(self.rules_dir, selected_file)
            
            # 读取YAML文件
            with open(filepath, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)
            
            if not yaml_data or 'rules' not in yaml_data:
                self.print_error("YAML文件格式错误")
                return
            
            # 整理规则
            rules = yaml_data['rules']
            
            # 去重
            unique_rules = []
            seen_contents = set()
            for rule in rules:
                if 'content' in rule and rule['content'] not in seen_contents:
                    unique_rules.append(rule)
                    seen_contents.add(rule['content'])
            
            # 按端口排序
            def extract_port(rule):
                if 'content' in rule:
                    port_match = re.search(r'(\d+)', rule['content'])
                    if port_match:
                        return int(port_match.group(1))
                return 9999
            
            unique_rules.sort(key=extract_port)
            
            # 更新YAML数据
            yaml_data['rules'] = unique_rules
            yaml_data['organize_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            yaml_data['original_count'] = len(rules)
            yaml_data['organized_count'] = len(unique_rules)
            
            # 移除ufw_status字段（如果存在）
            if 'ufw_status' in yaml_data:
                del yaml_data['ufw_status']
            
            # 生成新文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"ufw_rules_organized_{timestamp}.yaml"
            new_filepath = os.path.join(self.rules_dir, new_filename)
            
            # 写入整理后的YAML文件
            with open(new_filepath, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)
            
            self.print_success(f"规则整理完成")
            self.print_info(f"原始规则数量: {yaml_data['original_count']}")
            self.print_info(f"整理后规则数量: {yaml_data['organized_count']}")
            self.print_success(f"整理后的文件: {new_filepath}")
            
        except Exception as e:
            self.print_error(f"整理规则失败: {e}")
    
    def show_rules_management_menu(self):
        """显示规则管理子菜单"""
        while True:
            self.print_color("\n=== 规则管理 ===", 'blue')
            print("1. 导入规则")
            print("2. 导出规则")
            print("3. 整理规则")
            print("4. 返回主菜单")
            
            try:
                choice = input("请选择操作 [1-4]: ").strip()
                
                if choice == '1':
                    self.import_rules_from_yaml()
                elif choice == '2':
                    self.export_rules_to_yaml()
                elif choice == '3':
                    self.organize_rules()
                elif choice == '4':
                    break
                else:
                    self.print_warning("无效选择，将返回上一级菜单")
                    return
                    
            except KeyboardInterrupt:
                self.print_info("\n操作已取消")
                break
    
    def show_main_menu(self):
        """显示主菜单"""
        while True:
            self.print_color("\n=== UFW 管理器 ===", 'blue')
            print("1. 一键初始化")
            print("2. 添加规则")
            print("3. 删除规则")
            print("4. 规则管理")
            print("5. UFW状态与规则")
            print("6. 退出")
            
            try:
                choice = input("请选择操作 [1-6]: ").strip()
                
                if choice == '1':
                    self.initialize_ufw()
                elif choice == '2':
                    self.add_rule()
                elif choice == '3':
                    self.delete_rule()
                elif choice == '4':
                    self.show_rules_management_menu()
                elif choice == '5':
                    self.show_ufw_status_and_rules()
                elif choice == '6':
                    self.print_info("感谢使用UFW管理器！")
                    break
                else:
                    self.print_warning("无效选择")
                    
            except KeyboardInterrupt:
                self.print_info("\n操作已取消")
                break
    
    def run(self):
        """运行UFW管理器"""
        try:
            self.print_info("欢迎使用UFW管理器！")
            
            # 检查权限
            if not self.check_sudo_privileges():
                self.print_error("权限不足，无法继续")
                return
            
            # 显示主菜单
            self.show_main_menu()
            
        except Exception as e:
            self.print_error(f"程序运行错误: {e}")
            self.log_error(f"程序运行错误: {e}")

def main():
    """主函数"""
    try:
        manager = UFWManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()