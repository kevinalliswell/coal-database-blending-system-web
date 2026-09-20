# CBOS 2.0 Web 部署

推荐使用正式 Release 的 Linux amd64 镜像与持久数据卷。完整升级、回滚、SHA-256 验证流程见 [2.0 升级说明](UPGRADE_2.0.md)。

## Docker

```sh
docker run -d --name cbos -p 127.0.0.1:5000:5000 \
  -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:2.0.0
docker logs cbos
docker exec -it cbos flask --app wsgi users create-admin --username admin
```

容器入口在 Gunicorn 启动前执行 initialize，完成新库初始化或备份后迁移。不会在每个请求自动建库或重复种数据。远程访问通过 HTTPS 反向代理，同源 API，无 wildcard CORS。公开地址必须与 CSRF Origin 检查一致；配置 PUBLIC_ORIGIN（如 https://cbos.example.com）及 Secure cookie。不要把数据库文件放到公开静态目录。

健康检查 `/health` 仅用于进程检查。业务接口必须登录；先创建首管理员再通过界面创建其他角色。无默认密码。

## 从源码运行

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
flask --app wsgi initialize
flask --app wsgi users create-admin --username admin
gunicorn -w 2 -b 127.0.0.1:5000 --timeout 180 wsgi:app
```

开发同样先 initialize；Vite 开发页代理同源 API。不要使用生产数据运行测试。

## 维护

修改数据库连接前备份。SQLite升级命令会在需要升级时生成一致性备份；MySQL部署必须自行先做一致性备份再迁移。没有迁移版本的库不会被猜测 stamp。

账号恢复：`flask --app wsgi users reset-password --username admin`，交互输入新密码，撤销旧会话。保留数据库、部署配置与密钥等完整备份。停止服务后恢复数据库时使用兼容程序版本。

## 发布

普通 PR 合并不发布。显式 Release 工作流接收完整主线 SHA 与版本，验证代码/文档/清单一致，执行 Linux 回归、真实 Docker 流程及 Windows 安装验收。最后建立附注标签、草稿 Release、上传资产、发布固定版本镜像，下载核验后公开并更新 latest。发布构建不重新定版，不创建版本提交，不移动已有标签。
