# CI 与自托管运行器

PR 检查显式 checkout 当前 PR 的完整 head SHA；各平台使用同一份提交。普通 CI 不发布资产、合并 PR 或建立版本标签。正式发布仍由 [Release 工作流](RELEASE.md) 对已合入主线的固定 SHA 重新验收。

## 检查范围

| 检查 | 运行环境 | 验收内容 |
| --- | --- | --- |
| CI / macOS ARM64 regression | `kevin-mac-coal`，macOS ARM64 自托管 | 完整 Python 回归、前端回归、桌面 shell 回归、显式 TypeScript 检查、Web 与桌面模式前端构建、版本清单核对 |
| CI / test | GitHub 托管 Ubuntu，Python 3.11 / Node 22 | 原有全部回归与前端构建，以及真实 Dockerfile 的 Linux amd64 镜像构建、新库与旧库 HTTP 验收 |
| Windows desktop / windows-x64 | GitHub 托管 Windows 2022，Python 3.11 / Node 22 | 原有全部回归、冻结后端、安装包与 ZIP 构建、NSIS 安装、已安装程序 Electron 操作、重启、卸载与用户数据保留 |

三项检查独立执行。Mac 成功不能替代 Linux 镜像或 Windows 安装验证；托管预算不足、下载失败或排队都不算通过。发布工作流和原平台验收要求保持不变。

## Mac 配置与隔离

运行器标签为 `[self-hosted, macOS, ARM64, local-mac, coal-web]`。机器需预装 `/opt/homebrew/bin/python3.12`（原生 ARM64）；作业先检查 Python 版本、架构与提交，再创建独立虚拟环境。Node 22 ARM64 由 `actions/setup-node` 提供。Mac 的 Python 3.12 回归补充 Linux/Windows 的 Python 3.11 覆盖。

仅在当前私有仓库、同仓库真人账号提交的 PR 或主线 push 上运行 Mac 作业。Fork、机器人 PR 和仓库变为公开后的事件不进入个人主机；Linux/Windows 托管检查仍执行。不使用 `pull_request_target`，权限仅为 `contents: read`，checkout 不持久化凭据，不传入部署密钥。

自托管运行器与本机用户共用权限，并非安全沙箱。维护者仍须确保同仓库分支和工作流修改可信。作业不执行 `sudo`、全局 Python 安装、Docker 清理或主机服务重启。

每次运行使用 `ci/<run-id>-<attempt>` checkout，Python 虚拟环境、npm 依赖及生成文件均位于该目录。结果上传后通过 `always()` 清理该次目录；同 PR 的旧 Mac 作业可被新提交取消。工具缓存由 Actions 管理。若进程强制退出或主机断电导致清理未执行，维护者应在确认没有活动作业后，仅清除该次遗留目录。

主机由两个仓库的 Runner 共用；作业要求启动时至少有 3 GiB 可用空间，还需保持代理和用户服务在线。服务安装、代理与启动方式由本机运维文档 `/Users/kevin/CodeWorkSpace/Ops/github-actions-runner.md` 管理，不向仓库复制私有环境文件或凭据。

## 结果核对与重试

1. 在 PR Checks 打开具体 Actions 作业，核对 checkout SHA 与最新 PR head 相同。
2. Mac 的 Job summary 与 `macos-ci-<sha>-<attempt>` 产物包含实际 Runner 名称、系统/架构、版本、Python/Node 版本、run ID，以及 pytest XML / 前端和 shell TAP 结果。身份文件本身不代表测试通过，须同时核对各步骤及最终结论。
3. `Build web and offline frontend` 两次构建均须成功。它们验证共享界面编译；Windows 的冻结、安装和界面操作仍由 Windows 作业负责。
4. 若 GitHub 注明 `The job was not started because an Actions budget is preventing further use.`，说明托管作业未启动；恢复 Actions 预算后重跑失败作业，无需改变代码或跳过门禁。
5. 源码变化后推送新提交，重新执行新 SHA 的全部检查。保留失败日志定位根因，不能用旧 SHA 的成功记录替代。
