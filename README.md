# UFW Manager

![Python](https://img.shields.io/badge/python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)

一个交互式的 UFW (Uncomplicated Firewall) 防火墙管理工具，旨在简化 Linux 系统上的防火墙规则管理。

## 功能特性

- **一键初始化**: 快速重置并配置基本的 UFW 防火墙设置
- **规则管理**: 添加、删除和查看防火墙规则
- **规则导入/导出**: 支持将规则导出为 YAML 格式，并可从 YAML 文件导入规则
- **规则整理**: 对导出的规则进行去重和排序
- **状态查看**: 实时查看 UFW 状态和规则列表
- **安全保护**: 自动检测 SSH 端口并确保其始终可访问，防止被锁定
- **彩色输出**: 使用彩色文本提供更好的用户体验
- **日志记录**: 自动记录操作日志和错误日志

## 安装要求

- Python 3.6+
- UFW (Uncomplicated Firewall)
- PyYAML 库

安装 PyYAML:
```bash
pip install PyYAML
```

## 使用方法

1. 克隆或下载此项目
2. 运行程序:
   ```bash
   python ufw_manager.py
   ```
3. 根据提示选择相应功能

## 功能说明

### 主菜单选项

1. **一键初始化**: 重置 UFW 到默认状态，设置默认策略，并确保 SSH 端口可访问
2. **添加规则**: 添加新的防火墙规则，支持简单模式和高级模式
3. **删除规则**: 删除现有的防火墙规则
4. **规则管理**: 导入、导出和整理规则
5. **UFW状态与规则**: 查看当前 UFW 状态和规则列表

### 规则管理子菜单

1. **导入规则**: 从 YAML 文件导入防火墙规则
2. **导出规则**: 将当前规则导出为 YAML 文件
3. **整理规则**: 对导出的规则进行去重和排序

## 目录结构

```
ufw-manager/
├── ufw_manager.py     # 主程序文件
├── README.md          # 说明文档
├── LICENSE            # MIT 许可证
├── .gitignore         # Git 忽略文件配置
├── logs/              # 日志文件目录
│   └── .gitkeep       # Git 占位文件
└── rules/             # 规则文件目录
    ├── backup/        # 备份目录
    ├── templates/     # 模板目录
    └── .gitkeep       # Git 占位文件
```

## 安全注意事项

- 程序会自动检测 SSH 端口并确保其在初始化过程中不会被阻止
- 所有操作都需要管理员权限(sudo)
- 程序会在执行危险操作前进行确认提示
- 操作日志和错误日志会自动记录到 `logs/` 目录

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。