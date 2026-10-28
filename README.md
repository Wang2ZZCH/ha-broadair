# Broad Fresh Air (远大新风机) for Home Assistant

把**远大（Broad）EMD 洁净新风机**接入 Home Assistant 的自定义集成。

通过逆向远大官方 App（`远大空气`）的云端 API，实现新风机的**状态读取**和**频率（风量）控制**。全程走云端（`broadair.remotcon.mobi`），无需局域网直连设备。

> ⚠️ 本项目为个人自用的逆向工程成果，**非官方 SDK**，仅供学习交流。不保证长期可用（远大可能随时修改接口），请勿用于商业用途或高频轮询，以免给官方云服务造成负担。

---

## 功能

- **13 个传感器**：实时风量、运行频率、CO₂ 浓度、室内/室外温度、功率、PM2.5/PM10、三级滤网寿命、故障状态等
- **1 个风扇实体**：通过调节频率控制风量（EMD 无独立开关，频率 > 10Hz 即运行，= 10Hz 即停机）

## 支持设备

- **远大 EMD 洁净新风机**（变频机，频率范围约 10~30Hz）
- 理论支持同走 `GetFreshAir` / `SetFreshAir` 接口的其他远大新风机型号（未逐一实测）

> 注：远大的「肺保」系列走的是另一套接口（`SetFreshLung`），本集成不适用。

## 安装

### 方式一：HACS（推荐）

1. 在 HACS 中添加自定义仓库：`https://github.com/wangz2zch/ha-broadair`，类别选「Integration」
2. 安装并重启 Home Assistant

### 方式二：手动安装

1. 下载本仓库，将 `custom_components/broadair/` 整个目录复制到你的 HA 配置目录下的 `custom_components/` 中（最终路径应为 `<config>/custom_components/broadair/`）
2. 重启 Home Assistant

## 配置

1. 在 HA 中进入「设置 → 设备与服务 → 添加集成」，搜索 **Broad Fresh Air**
2. 输入你的**远大 App 账号**和**密码**（即你在 `远大空气` App 中注册登录的手机号与密码）
3. 从设备列表中选择你的新风机，完成配置

> 建议使用**设备的主绑定账号**（而非共享账号），以获得最完整的控制权限。若账号在别处（手机 App）登录，可能因 token 互踢导致集成掉线——远大云对同一账号采用「后登录者踢掉先登录者」策略。

## 工作原理

```
新风机 EMD ──串口──> 汉枫 HF-LPT230 WiFi 透传模块 ──WiFi──> 远大云 (broadair.remotcon.mobi:8201)
                                                              │
                                          ┌───────────────────┴───────────────────┐
                                       手机 App                                   HA (本集成)
```

本集成通过 HTTP 调用远大云 API：

- `POST /api/System/Login` — 登录，签名方式 `md5(APP_TOKEN + Nonce + Timestamp)`
- `POST /api/Equipment/GetEquipments` — 获取设备列表
- `POST /api/Equipment/GetFreshAir` — 读取状态（`sjx=1`）
- `POST /api/Equipment/SetFreshAir` — 下发控制（`sjx=4` + `cs=频率值` 调频）

### 关键命令码（实测结论）

| sjx | 含义 | 备注 |
|-----|------|------|
| 1   | 读取状态 | `cs` 为空 |
| 4   | 调频 | `cs` = 频率值（数字，10~30Hz），**必须传 int，不能传字符串** |

- EMD **没有独立的开关命令**（sjx=2/3 是肺保机型用的，对 EMD 无效）。开关通过频率实现：频率 > 10Hz 即运行，= 10Hz 即停机。
- 变频机设频后**存在延迟爬升和"凑整"**：`FREQUENCY_SET`（设定值）与 `FREQUENCY_RUN`（实际运行值）可能不一致，观察需等待 15 秒以上。
- EMD 内置 **CO₂ 自动调频**（阈值 CO₂ 1100/800 ppm），手动设频可能被自动逻辑覆盖。如需「定频」，请在 App 中关闭「新鲜度自控」。

## 免责声明

本项目通过抓包逆向官方 App 的私有 API，可能违反远大服务条款。使用本项目造成的任何后果（包括但不限于账号被封、设备异常、接口失效）由使用者自行承担。作者不提供任何担保。

## License

MIT
