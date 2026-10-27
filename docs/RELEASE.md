# 固定提交发布流程

`Release` 工作流仅手动触发。它不计算版本、不修改文件、不创建提交；版本准备和 CHANGELOG 定版必须先审查并合入 main。

## 输入与前提

- `version`：已经提交的 `X.Y.Z`，例如 `2.0.0`。
- `build_sha`：main 历史中完整的 40 位小写提交 SHA。禁止使用分支名、短 SHA 或未合并提交。
- `delivery_visibility`：明确指定 `private`（默认）或 `public`；仓库与 GHCR 包必须同时符合该值。这个选项只校验现有权限，不修改权限。
- 2.0 起，Python、前端 package/lock、桌面 package/lock 的版本必须一致。
- CHANGELOG.md 必须具有唯一的对应版本章节，例如 `## v2.0.0 (2026-09-20)`；`Unreleased` 不作为发布说明。
- GitHub Actions 需要在发布 job 中拥有 `contents: write`、`packages: write`。构建 job 只有读取权限。
- 私有发布验证授权下载；公开发布额外验证镜像可匿名拉取。正式发布表示 Release 不再是草稿，不代表私有仓库变为公开。元数据读取失败或可见性不匹配时停止，不把权限错误当作包不存在。
- 新建 GHCR 包默认私有。首次公开发布前需由所有者明确配置公开仓库与公开包；工作流不会扩大访问范围。

版本准备 PR 先修改唯一来源 `app/__version__.py`，再执行 `python desktop/scripts/build-backend.py --sync-version-only`，生成前端和桌面的 package/lock 版本，并将 CHANGELOG 的未发布内容定版。正常构建与正式发布不执行这个同步选项，也不会新增版本提交。

准备好并合入 main 后，可从 Actions 页面填写三个输入。等价命令如下，其中 SHA 必须替换为真实的已合并提交：

```bash
gh workflow run release-on-main.yml --ref main -f version=2.0.0 -f build_sha=完整40位SHA -f delivery_visibility=private
```

## 顺序与验收

1. 核对版本文件、干净的受跟踪工作树、CHANGELOG、main 祖先关系，以及既有标签/Release 是否属于同一 SHA。
2. Linux 与 Windows 并行检出这个 SHA，执行 Python、前端、桌面壳回归。
3. Linux 构建 amd64 Docker 镜像，验收新库和旧库升级、登录及核心 HTTP 操作；运行中报告的版本与 SHA 必须匹配。
4. Windows 冻结后端、打包 EXE/ZIP，在含空格和中文的目录实际安装，运行原有完整 Electron UI 验收；另安装固定 v2.0.0 正式包建立真实数据，再覆盖安装新版、重启登录、卸载及独立解压启动 ZIP。默认用户目录中的账号、化验、设置和完整历史必须保留，卸载前后数据库/密钥文件散列必须一致。脚本剥离子进程的构建环境变量，分别核对旧版固定身份和新版提交；发布门禁重新检查各阶段报告与数据快照，详见 [CI 完整生命周期](CI.md#windows-独立环境的完整生命周期)。
5. 只有两个 job 都成功，发布 job 才下载本次运行的两组资产，创建或检查附注标签和草稿 Release。
6. 每次运行独立的 `staging-SHA-run-attempt` GHCR 标签用于取得分发摘要；此时不更新固定版本或 latest。草稿附带构建清单、升级说明、平台验收摘要和完整散列清单，并重新下载全部文件逐个核对。
7. 将已经验收的镜像赋予固定版本标签，核对它与草稿清单中的摘要及访问范围相同；私有发布通过认证拉取校验，公开发布通过匿名拉取校验，然后正式发布 Release。
8. 再次下载已发布资产核验，最后才更新 GHCR `latest`，并检查它解析到同一个摘要。

Release 正文来自 CHANGELOG 对应版本章节，并附 Windows 未签名提示、完整提交、安装包、ZIP、Docker 离线镜像与升级说明链接。

注册表读取同时接受 OCI/Docker 的单镜像 manifest 和镜像索引。传统 Docker 本机镜像 ID 对应配置摘要；containerd 镜像存储也可能返回 manifest 或索引的分发摘要。发布和草稿恢复都要求本机实际 ID 与对应的完整摘要精确相同，不凭版本名或平台名称认定镜像相同。

公开仓库与公开包使用 `delivery_visibility=public`。例如发布已准备好的 2.0.2：

```bash
gh workflow run release-on-main.yml --ref main -f version=2.0.2 -f build_sha=完整40位SHA -f delivery_visibility=public
```

v2.0.1 在新 Runner 的 OCI 索引校验处中止；其附注标签保留，未完成的草稿不作为正式下载。修复及原界面改造由 v2.0.2 一并交付。

## 发布资产

- `CBOS-VERSION-windows-x64-setup.exe`
- `CBOS-VERSION-windows-x64.zip`
- `cbos-web-VERSION-docker-image.tar.gz`
- `UPGRADE_2.0.md`
- `validation-summary.md`
- `linux-validation.json`、`windows-validation.json`
- `build-manifest.json`（版本、SHA、访问范围、镜像分发摘要、运行编号、各资产散列）
- `SHA256SUMS.txt`（除自身外的全部资产）

`staging-*` 是发布中间标签，不是部署版本；部署使用固定版本或其 digest。临时标签可按仓库保留策略人工清理，流水线不删除已经发布的版本。

## 中断与重试

- 已有标签必须为附注标签且直接指向同一提交。不同 SHA 或轻量标签均停止流程，绝不强制移动。
- 固定镜像尚未推送时，同 SHA 草稿允许下载核验后重用相同文件，或替换重新构建但内容不同的草稿文件。已发布资产禁止替换。
- 固定镜像已推送、Release 仍为草稿时，重试下载**原草稿整套资产**，核对清单 SHA、镜像 digest 和离线 Docker 包加载后的配置摘要。通过后复用原资产继续正式发布，不把本次重新构建的文件混入原版本。
- Release 已发布时，重试不修改正文、标签或资产；核验现有文件和固定镜像后，从原离线包恢复并核对完整镜像，再继续尚未完成的 latest 推进。这样新 Runner 也能保留 OCI 索引中的附加 manifest，而不因普通 pull 只取当前平台而丢失内容。访问范围同样必须与原清单一致。
- 更高版本已成为最新 Release 时，旧版本重试会停止，避免把 latest 降级。
- 固定版本镜像与原草稿无法对应、散列不匹配、只有固定镜像而没有可验证草稿等情形均停止。保留证据排查，不覆盖原版本。

可优先使用 GitHub Actions 的“重新运行失败的作业”，保留同次运行中已经成功的构建和验收资产。整个流程重跑也必须使用原版本和完整 SHA；既有固定版本会遵循上述恢复规则。

## 访问私有发布

Release 资产需要使用获授权的 GitHub 账号登录下载。GHCR 镜像访问另受包权限控制，使用具有 `read:packages` 权限的 classic personal access token 登录；具体步骤见 [Web 部署](DEPLOYMENT.md#私有镜像认证)。

权限行为依据 [GitHub Container registry 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) 和 [Packages REST API](https://docs.github.com/en/rest/packages/packages)。
