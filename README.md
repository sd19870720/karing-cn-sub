# Karing 国内候选订阅自动更新

从 Proxifly、monosans、Databay Labs 和 Alex Vakhov 四个来源收集无需认证的 HTTP CONNECT / SOCKS5 候选，只有通过实际 HTTPS 请求及国内出口核验的节点才发布到 Karing 订阅。
当前节点数量与检查时间见 [status.json](status.json)。

**固定订阅地址：**

```text
https://raw.githubusercontent.com/sd19870720/karing-cn-sub/main/subscription.yaml
```

[查看订阅文件](subscription.yaml) · [查看更新任务](https://github.com/sd19870720/karing-cn-sub/actions/workflows/refresh.yml)

直链无法访问时，可尝试备用 CDN（存在缓存延迟）：

```text
https://cdn.jsdelivr.net/gh/sd19870720/karing-cn-sub@main/subscription.yaml
```

## 初版部署验证（2026-11-02）

- Actions 工作流已启用，两次由代码变更触发的运行均成功；[最近一次验证](https://github.com/sd19870720/karing-cn-sub/actions/runs/41408141222)。
- 已观察到 `github-actions[bot]` 自动提交更新，提交 `7e218e6cd4661c02cc286bdc66fcf7e8f5ddfd91`。
- 15:47（北京时间）核验直链 HTTP 200，内容与仓库当前订阅一致，包含 160 条候选。
- 备用 CDN 返回 HTTP 200，解析后的配置一致，但文件注释仍有缓存差异。
- 每小时调度已配置；本次验收为实际运行与自动提交，不把尚未等待到的下一次定时触发写成已实测。
- 以上不包含 iPhone 或抖音的真实使用验收。

初版只核验配置生成，没有验证节点连接。收到超时反馈后，本机对 160 个候选的
一次测试仅有 5 个成功访问国内 HTTPS 页面，进一步查询还发现部分出口显示为境外。
因此已将发布条件改成下面的实测筛选，不再把 160 条数据记录当作可用节点。

## 超时问题修复验证（2026-11-02）

- [修复后的工作流](https://github.com/sd19870720/karing-cn-sub/actions/runs/41415456394)成功，23 项离线回归测试通过。
- 16:46（北京时间）165 个候选中有 3 个通过国内 HTTPS 和 IPIP 出口检查，均显示北京；其余被剔除。
- 16:50 又从当前 Windows 电脑网络复测这 3 个节点，全部通过上述检查。
- 主订阅及备用 CDN 返回 HTTP 200，SHA256 均为 72d8e1b64812d741d159db8675f08feab65c83f9bb29bfee19e20082bb617234，与仓库文件一致。
- 这是当次检测结果，后续数量以 status.json 为准；仍不等于用户 iPhone 或抖音实际效果验收。

## iPhone 使用

1. 在 Karing 打开 **设置 → 添加配置 → 添加配置链接**，粘贴上面的完整网址。
2. 将 **更新时间间隔**设为 `1h`，按需要开启 **配置更新后重新加载**。
3. 在我的配置中点击该订阅的更新时间，手动更新一次并确认成功。
4. 回主屏手动选择需要的地区节点，检查 **全局**模式，再开启 VPN。
5. 先核对公网出口，再分别验证抖音实际属地；连接或延迟测试通过不等于抖音验收。

国内节点测延迟时，请在 **设置 → 延迟检测 → URL** 添加并选中
`https://connect.rom.miui.com/generate_204`，或 `https://www.baidu.com/`。
找不到入口时先关闭“新手模式”。默认 Google 检测地址可能不适合国内出口。

iOS 当前在打开或回到 Karing 时检查到期更新，不能保证锁屏后台严格按小时刷新。
旧的本地导入文件不会更新，可以先停用，避免与这个在线订阅混淆。

## 更新方式

GitHub Actions 每小时第 17 分钟尝试刷新，也支持在 Actions 页面手动运行。
更新脚本、依赖或工作流时也会触发运行；仅更新订阅文件不会循环触发。
每次发布检测状态，只保留本轮通过的节点。目标正常但没有节点通过时，会移除订阅文件，
避免继续分发已经失败的节点；这时请停用手机里的旧配置，Karing 可能继续保留旧缓存。
若上游或检测服务自身异常，最多保留上次通过验证且仍在两小时保留期内的配置；
后续任务发现过期会移除。任务停止运行、手机离线时不会自动清除手机缓存。
GitHub 定时任务可能延迟，不是严格准点服务；可以在上面的任务页面检查最近运行结果。

筛选 CN、HTTP CONNECT / SOCKS5、公共 IP 和有效端口后，使用显式 HTTP 或 SOCKS5h 代理请求百度公开 HTTPS 页面，
保留证书校验，并通过 HTTPS 出口查询核对实际出口是中国且不同于检测机直连出口。
上游城市缺失或标为 Unknown 时仍保留为待核验候选，不按缺失城市直接丢弃；通过检查后使用实际出口城市命名。
出口查询优先使用国内 IPIP 服务，避免国内节点无法访问境外检测站点而被误判；
只有国内查询服务自身不可用时，才尝试备用查询服务。
不发送账号、Cookie 或登录请求。国家未确认、境外出口、超时、握手失败都会剔除。
每轮最多 600 个候选、16 个并发、约 5 分钟探测预算；单请求最多 8 秒。
地区名称使用实际出口查询结果，可能与抖音数据库不同。未知英文地区保留原文。

## 验证边界

- 检测在 GitHub Actions 的网络环境运行，不保证国内手机网络也能连接。
- 候选节点可能随时失效，SOCKS5 的 UDP 能力未确认，配置中关闭 UDP；HTTP CONNECT 仅用于 TCP 连接。
- 自动更新只刷新候选列表，不保证节点持续可用、始终同城或适配抖音。
- iPhone 导入、实际出口、抖音属地及作品推荐效果仍需在用户设备上分别验收。
- 换 IP 不保证作品推荐给目标城市。

## 来源与许可

- [上游数据](https://github.com/proxifly/free-proxy-list)
- [补充来源 monosans/proxy-list](https://github.com/monosans/proxy-list)
- [补充来源 databay-labs/free-proxy-list](https://github.com/databay-labs/free-proxy-list)
- [补充来源 vakhov/fresh-proxy-list](https://github.com/vakhov/fresh-proxy-list)
- [源码与第三方声明](THIRD_PARTY_NOTICES.md)
- [GPL-3.0 许可证](LICENSE)
- [Karing 添加配置说明](https://karing.app/app-manual/add-profiles)
- [Karing 我的配置说明](https://karing.app/app-manual/my-profiles)
