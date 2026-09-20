# CBOS 2.0 升级与安装说明

## 不兼容变化

2.0 引入账号权限、批次和化验修订。原煤种 ID 不再是唯一计算输入；优化请求必须提交化验修订 ID、比例边界与设置版本。旧录入写接口返回升级提示；旧历史和读取/导出接口保留。筛选试算已移除。

旧煤质原值迁入“历史迁入”批次。未知单位、基准、热值恒容/恒压定义、日期保持未知；即使煤名含“分析基”也不补元数据。迁入记录可能不能立即计算，请对照原报告创建新修订。原历史不利用当前煤值补写。

## 升级前备份

1. 记录旧版本与运行配置，停止写入。
2. Windows 完全退出 CBOS，复制整个用户数据目录（菜单“打开数据文件夹”），保留数据库、密钥、日志和既有备份。
3. Web SQLite 使用一致性备份或停服后复制；MySQL 使用数据库备份工具。保留旧镜像/旧安装包。
4. 在备份副本上演练升级，再升级实际部署。

Web 与桌面使用同一 Alembic 迁移规则。SQLite 检测到已登记的旧迁移版本时，在 `backups/` 生成一致性备份后升级。初始化只为新库种一次示例记录；之后归档或删除旧版本示例不会被重新灌入。

没有 alembic_version、版本不属于本应用或结构不明的数据库会停止升级，原数据不自动 stamp。先备份并由维护人员对照 migrations 核实 schema，不要对未知结构直接执行 stamp。迁移失败时保留错误日志，在备份副本定位后重试；需要回退时停止服务，恢复旧数据库和旧程序，两者版本必须匹配。

## 首次管理员及账号恢复

没有默认账号和密码。Windows 首次启动通过受本机通信令牌保护的页面创建管理员。Web 初始化后在服务器执行：

```sh
flask --app wsgi users create-admin --username admin
```

密码至少 12 位，交互输入两次。四角色权限见用户手册。管理员可重置密码、停用用户；最后一个有效管理员受保护。

Web 管理员遗忘密码时由服务器维护人员执行 `flask --app wsgi users reset-password --username admin`；其他管理员也可在用户管理页面重置密码。

Windows 上唯一管理员遗忘密码时，先完全退出 CBOS，再由有权访问该 Windows 用户数据目录的维护人员打开 PowerShell，运行安装包自带的后端程序，无需安装 Python：

```powershell
& 'C:\实际安装目录\resources\backend\cbos-backend.exe' --reset-password admin --data-dir "$env:LOCALAPPDATA\CBOS"
```

将程序路径、账号 `admin` 和数据目录替换为实际值；ZIP 版程序同样在其 `resources\backend` 目录中。按提示隐藏输入两次至少 12 位的新密码，不要把密码作为命令参数。该命令只修改现有账号，撤销该账号全部会话，不创建账号、不重建数据库。数据目录仍被 CBOS 使用时会拒绝恢复，关闭程序后再试。拥有此目录读写权限的操作系统用户可恢复账号，因此应同时保护 Windows 登录和数据备份。

恢复成功后重新启动 CBOS 登录。不要删除数据库规避登录，删除数据库会丢失所有本机数据。

## Windows 安装

下载同版本 `CBOS-2.0.0-windows-x64-setup.exe` 或免安装 ZIP，并核对 `SHA256SUMS.txt`。支持 Windows x64；首次安装无需另装 Python、Node 或服务器。安装包按当前用户安装，不需要管理员权限。ZIP 完整解压后运行 CBOS.exe，不要只复制单个 exe。

本次未配置 Windows 代码签名证书，资产未签名。系统可能提示未知发布者；先确认来源为本仓库同版本 Release 并核对散列。

```powershell
Get-FileHash .\CBOS-2.0.0-windows-x64-setup.exe -Algorithm SHA256
```

每次启动登录。数据在本机用户数据目录，与安装目录分开。更新程序保留数据；卸载保留数据。备份后可用同版本完整目录恢复；不要合并两份不同部署的 SQLite 文件。

## Docker 安装

在线使用 `ghcr.io/kevinalliswell/coal-database-blending-system-web:2.0.0`，或加载离线镜像：

```sh
gunzip -c cbos-web-2.0.0-docker-image.tar.gz | docker load
docker run -d --name cbos -p 127.0.0.1:5000:5000 -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:2.0.0
docker exec -it cbos flask --app wsgi users create-admin --username admin
```

镜像为 Linux amd64。容器启动先迁移再启动服务；日志确认成功后创建管理员。在远程网络使用时配置 HTTPS 反向代理和正确 PUBLIC_ORIGIN。数据库卷不能省略；重建不带卷的容器会丢失数据。

## 版本核对与发布资产

“关于”中的版本和构建提交应与 `build-manifest.json` 的完整 SHA 一致。镜像 digest、工作流运行编号及各平台验证摘要随资产提供。检查 SHA256SUMS.txt 后再安装；GitHub 标签源码归档对应同一提交。

Release 正文由 CHANGELOG.md 的对应版本章节生成。发布重试固定版本/SHA，不移动已存在标签，不覆盖公开资产。最终 latest 只在正式发布和下载核验成功后更新。

## 已知范围

- 不做跨设备账号与数据同步，不提供多人共享同一 SQLite 文件。
- 不预测非线性燃烧相互作用；数值可行方案仍需现场工艺评估。
- 恒压/定义不明热值只存档；不同高低位定义转换需要氢数据。
- Windows 安装包当前未签名；ARM Windows 不作为本期验收目标。
- 历史记录缺少的旧元数据保持缺失，不能追溯重建不存在的原始快照。
