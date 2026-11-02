# Karing 国内候选订阅自动更新

把 Proxifly 的公开国内代理数据转换为带地区名称的标准 Clash YAML，供 Karing 导入。

**固定订阅地址：**

```text
https://raw.githubusercontent.com/sd19870720/karing-cn-sub/main/subscription.yaml
```

[查看订阅文件](subscription.yaml) · [查看更新任务](https://github.com/sd19870720/karing-cn-sub/actions/workflows/refresh.yml)

## iPhone 使用

1. 在 Karing 打开 **设置 → 添加配置 → 添加配置链接**，粘贴上面的完整网址。
2. 将 **更新时间间隔**设为 `1h`，按需要开启 **配置更新后重新加载**。
3. 在我的配置中点击该订阅的更新时间，手动更新一次并确认成功。
4. 回主屏手动选择需要的地区节点，检查 **全局**模式，再开启 VPN。
5. 先核对公网出口，再分别验证抖音实际属地；连接或延迟测试通过不等于抖音验收。

iOS 当前在打开或回到 Karing 时检查到期更新，不能保证锁屏后台严格按小时刷新。
旧的本地导入文件不会更新，可以先停用，避免与这个在线订阅混淆。

## 更新方式

GitHub Actions 每小时第 17 分钟尝试刷新，也支持在 Actions 页面手动运行。
只有候选配置变化时才提交；下载失败或没有有效候选时会失败并保留旧文件。
GitHub 定时任务可能延迟，不是严格准点服务；可以在上面的任务页面检查最近运行结果。

生成器只下载公开数据，不连接任何代理。筛选 CN、SOCKS5、已标注地区、
公共 IP 和有效端口的条目，并去重。名称使用来源地区标签与地址、端口，
尽量保持更新前后稳定。未知的英文地区标签保留原文。

## 验证边界

- 城市名称来自上游元数据，不代表本仓库实测归属地。
- 候选节点可能随时失效，UDP 能力未确认，所以关闭 UDP。
- 自动更新只刷新候选列表，不保证节点持续可用、始终同城或适配抖音。
- iPhone 导入、实际出口、抖音属地及作品推荐效果仍需在用户设备上分别验收。
- 换 IP 不保证作品推荐给目标城市。

## 来源与许可

- [上游数据](https://github.com/proxifly/free-proxy-list)
- [源码与第三方声明](THIRD_PARTY_NOTICES.md)
- [GPL-3.0 许可证](LICENSE)
- [Karing 添加配置说明](https://karing.app/app-manual/add-profiles)
- [Karing 我的配置说明](https://karing.app/app-manual/my-profiles)
