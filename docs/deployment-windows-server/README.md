# Windows Server 部署说明

本文档记录 `coal-database-blending-system-web` 在 `ustb-win` Windows Server 上的实际部署经验，并提供下次部署可复用的辅助脚本。

本目录只保存可公开的部署模板和经验记录，不保存以下内容：

- `.env` 生产密钥
- TLS 私钥或证书
- SQLite 数据库
- 运行日志
- `tar.gz` 部署包
- 任何服务器账号密码

## 当前线上状态

- 访问地址：`https://8.161.230.61:8782/`
- 健康检查：`https://8.161.230.61:8782/health`
- 服务器连接：`ssh ustb-win`
- 应用目录：`C:\srv\cbos-web`
- 计划任务：`cbos-web`
- 服务端口：`8782`
- 日志文件：`C:\srv\cbos-web\logs\cbos-web.log`
- SQLite 数据：`C:\srv\cbos-web\data\coal_system.db`
- 防火墙规则：`CBOS Web 8782 HTTPS`

服务器上已有离线 Docker 镜像：

```text
C:\Users\Shi Jinpeng\cbos-web-1.0.1-docker-image.tar.gz
```

本次部署时服务器没有 Docker/Podman/WSL 入口，且该镜像是 Linux 容器镜像，不能直接在当前 Windows Server 2019 环境运行。因此实际采用源码部署：`Flask + SPA + SQLite` 保持项目生产契约，Windows 侧使用 Cheroot 作为 HTTPS WSGI 服务。

## 文件说明

```text
docs/deployment-windows-server/
  README.md
  windows/
    package-cbos-web.ps1         # 本地生成部署 tar.gz
    install-or-update-cbos.ps1   # 服务器安装/更新应用
    start-cbos.ps1               # 计划任务调用的启动脚本
    https_server.py              # Cheroot HTTPS WSGI 入口
    requirements.txt             # Windows 部署额外依赖
```

## 下次部署流程

在本地从仓库根目录生成部署包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\docs\deployment-windows-server\windows\package-cbos-web.ps1 `
  -SourceRepo .
```

默认输出：

```text
%TEMP%\cbos-web-deploy.tar.gz
```

上传部署包到服务器：

```powershell
scp "$env:TEMP\cbos-web-deploy.tar.gz" ustb-win:"C:/Users/Shi Jinpeng/cbos-web-deploy.tar.gz"
```

如果服务器上还没有部署辅助脚本目录，可以先复制本目录的 `windows` 子目录到服务器任意非 Git 工作目录，例如：

```powershell
ssh ustb-win "if not exist C:\srv\cbos-web-deploy-kit mkdir C:\srv\cbos-web-deploy-kit"
scp -r .\docs\deployment-windows-server\windows ustb-win:"C:/srv/cbos-web-deploy-kit/"
```

在服务器运行安装/更新脚本：

```powershell
ssh ustb-win "powershell -NoProfile -ExecutionPolicy Bypass -File C:\srv\cbos-web-deploy-kit\windows\install-or-update-cbos.ps1"
```

验证：

```powershell
curl.exe -k https://8.161.230.61:8782/health
curl.exe -k -I https://8.161.230.61:8782/
```

## 日常运维

检查计划任务：

```powershell
ssh ustb-win "schtasks /query /tn cbos-web"
```

重启服务：

```powershell
ssh ustb-win "schtasks /end /tn cbos-web"
ssh ustb-win "schtasks /run /tn cbos-web"
```

查看端口：

```powershell
ssh ustb-win "netstat -ano | findstr :8782"
```

查看日志：

```powershell
ssh ustb-win "type C:\srv\cbos-web\logs\cbos-web.log"
```

## TLS 证书

当前脚本会在没有正式证书时自动生成包含 `8.161.230.61` SAN 的自签名证书。浏览器会提示证书不受信任，这是预期现象。

如有正式证书，放到以下路径后重启 `cbos-web`：

```text
C:\srv\cbos-web\certs\server.crt
C:\srv\cbos-web\certs\server.key
```

## 内存与 pagefile 经验

服务器虚拟内存紧张时，导入 `pandas/scipy` 可能出现：

```text
The paging file is too small for this operation to complete.
```

本次部署已将服务器 pagefile 设置写为：

```text
InitialSize=8192
MaximumSize=24576
```

该设置通常在服务器下次重启后完全生效。启动脚本也限制了科学计算库线程数，降低低内存环境下的启动抖动：

```text
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1
```
