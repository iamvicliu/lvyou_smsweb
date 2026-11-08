# 绿邮X系列内网群控系统（lvyou-smsweb 定制版）

一个用于管理局域网内绿邮 X 系列开发板的 Web 管理平台：多板统一管理、短信收发、来电接管与录音、号码与通讯录、批量配置与 OTA，以及板子异常时的自动诊断。

本仓库是 [lovexme/lvyou_smsweb](https://github.com/lovexme/lvyou_smsweb) 的个人定制分支，在上游 v5.2 的基础上补充了多板日常使用需要的功能。与上游的差异见 [CHANGELOG.md](./CHANGELOG.md)。

## 功能特性

**设备管理**

- 局域网扫描发现新板子，加入面板后按首页顺序统一排序（首页、设置页、下拉框顺序一致）
- 卡片显示在线状态、固件版本、两个卡槽的运营商、信号与 SIM 状态；异常状态（拒绝、欠费、停机等）用红色标出，无卡用弱黄色，正常为绿色
- 设备详情：按需读取一次运行状态（固件、运行时长、内存、联网通道、号卡状态），支持重启卡槽、卡槽通电/断电、卡槽联网开关、整机重启、每日定时重启
- 批量操作：设置 WiFi、升级固件、改配置、开启消息推送、关闭卡槽联网、批量改板子管理员密码

**短信**

- 单条与批量发送，支持选择板子 → 卡槽 → 收件人，收件人可以记住、可以从通讯录挑
- 短信记录按板子、卡槽、方向、关键词筛选，支持同步板端最新记录、批量删除
- 发送结果按 `tid` 跟踪：已入队 → 板子已发出 → 已提交运营商 → 送达/失败
- 首页实时短信流，10 秒自动刷新，可手动立即刷新；有短信进来自动出现
- Bark 推送：收到短信、发送成功/失败/送达时推送到 iPhone

**通话**

- 通话记录与录音管理，录音可在网页直接播放（AMR 自动转 MP3）、下载、删除
- 通话接管：振铃/通话中可在面板接听、挂断、播放 TTS、发送 DTMF 按键、开始/停止录音
- 来电面板自动接听并录音，录音时长最长 60 秒（板子自带模式固定 15 秒），板子在通话结束后自动上传录音
- 来电、未接来电、去电未接通推送 Bark；有来电时首页顶部直接提示

**号码与通讯录**

- 号码页记录每张卡的本机号、套餐备注、分组；卡号填一次即可，板子离线也能保存
- 通讯录支持联系人、多个号码、分组、收藏，记录页用姓名显示号码

**设置与自愈**

- 消息推送（Bark）、录音上传、自动接听/录音、SIM 异常自愈集中在设置页，并纳入顶部导航
- SIM 异常自愈：收到 209 后观察 30 秒，必要时只发一次 `stat` 二次确认，再按卡槽状态决定重启卡槽还是转人工；24 小时滚动限流，重启失败不反复重试
- 心跳被动监测：依赖板子的 998 PING 判断在线，只在长时间收不到心跳时补拉记录，不做定时轮询
- 登录：httpOnly Cookie + CSRF，默认 30 天有效期，访问时自动续期

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite + httpx
- **前端**：Vue 3 + Vite + Pinia + Vue Router + axios
- **部署**：systemd / Docker，容器固定使用北京时间（Asia/Shanghai）

## 安装方式

### 方式一：Docker 部署（推荐）

```bash
git clone https://github.com/iamvicliu/lvyou_smsweb.git
cd lvyou_smsweb

# 面板登录密码，不设置则默认 admin
echo "BMUIPASS=your_strong_password" > .env

docker compose up -d --build      # 本仓库自带 Dockerfile，会本地构建 lvyou-smsweb:local
docker compose logs -f
```

默认访问 `http://<主机IP>:8000/`。容器使用 host 网络，才能扫描局域网；数据挂在 `./data`。

### 方式二：脚本安装

适用于 Ubuntu / Debian：

```bash
sudo bash install.sh install
```

安装过程中会提示输入服务端口（默认 8000）和 UI 登录密码。

```bash
sudo bash install.sh status    # 查看状态
sudo bash install.sh restart   # 重启
sudo bash install.sh logs      # 查看日志
lvyou pass                     # 更改密码
lvyou port                     # 更改端口
lvyou config                   # 查看配置
```

### 方式三：手动部署

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && pnpm install && pnpm run build
cd .. && ./start.sh            # 可选：./start.sh 9000 指定端口
```

录音转 MP3 需要 `ffmpeg`。容器里没有时，可放在数据目录的 `bin/ffmpeg`（例如 `/opt/board-manager/data/bin/ffmpeg`），或用 `BMRECORDINGFFMPEG` 指定路径；找不到时保留 AMR 原文件，Safari 可直接播放。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SERVER_PORT` | 8000 | 服务端口 |
| `BMUIUSER` | admin | 面板登录用户名 |
| `BMUIPASS` | admin | 面板登录密码，建议首次部署就改掉 |
| `BMDEVUSER` / `BMDEVPASS` | admin | 访问板子 `/ctrl` 的凭据 |
| `BMDB` | /opt/board-manager/data/data.db | SQLite 数据库路径 |
| `BMSTATIC` | /opt/board-manager/static | 前端静态文件目录 |
| `BMPANELURL` | （自动推断） | 面板对板子的可达地址，用于生成推送/录音上传地址；桥接网络算不出来时手动指定 |
| `BMHTTPTIMEOUT` | 5.0 | 访问板子的超时（秒） |
| `BMSCANCONCURRENCY` | 64 | 扫描并发数 |
| `BMSMSRATELIMIT` | 10 | 短信频率限制（次/分钟） |
| `BMLOGINRATELIMIT` | 5 | 登录频率限制（次/分钟） |
| `BMTOKENTTL` | 2592000 | 登录有效期（秒，默认 30 天） |
| `BMALLOWORIGINS` | （空） | CORS 允许的源 |
| `BMSIMGUARD` | 1 | 设为 0 关闭 SIM 异常自愈 |
| `BMRECORDINGMAX` | 8388608 | 单个录音上传大小上限（字节） |
| `BMRECORDINGSDIR` | `<数据目录>/recordings` | 录音存放目录 |
| `BMAUTOSCAN` | 1 | 设为 0 关闭自动扫描 |
| `BMAUTOSCANINTERVAL` | 900 | 自动扫描间隔（秒） |
| `BMMETRICS_TOKEN` | （空） | 设置后 `/metrics` 需要携带该 Token |
| `BMAUDITLOGFILE` | `<数据目录>/audit.log` | 审计日志路径 |

## 板子准备

每块板子需要做三件事，做完面板才能收到短信、来电和录音。设备列表选中板子后点「开启消息推送」，面板会自动完成前两步并回读校验；只有跨网段、桥接网络等算不出面板地址时，才需要手敲 `/ctrl`。

1. **上报地址指向本面板**（`<BOARD_TOKEN>` 是板子管理员 Token）：

   ```
   GET http://<板子IP>/ctrl?token=<BOARD_TOKEN>&cmd=setinf
       &p1=http://<面板IP>:<端口>/webhook?k=<WEBHOOK_TOKEN>&p2=post&p3=json
   ```

   用 `cmd=askinf` 复查，`method` 应为 `1`、`ctype` 应为 `1`。

2. **打开消息号上报**：

   ```
   GET http://<板子IP>/ctrl?token=<BOARD_TOKEN>&cmd=setallmsgcode
       &p1=204,205,209,402,501,502,503,601,602,603,620,621,622,623,695,696,998&p2=on&p3=replace
   ```

   用 `cmd=askallmsgcode` 复查。少一个消息号就少一类事件：没有 `998` 面板不知道板子在线，没有 `501/502` 短信进不了面板，没有 `209` 自愈收不到通知。

3. **录音上传地址**（只有用面板录音时才需要）：

   在「系统设置 → 录音上传」里查看上传地址，下发到板子即可。上传令牌可以随时更换。

短信回执依赖板子的 `402`（板子已处理）和 `502/503`（运营商回执）推送；只在面板点发送，拿到的响应只有 `type=401 / sending...`。

## 页面说明

| 页面 | 用途 |
|---|---|
| 设备 | 设备卡片、批量操作、消息发送、实时短信、来电提示 |
| 号码 | 每张卡的本机号、套餐备注、分组 |
| 通讯录 | 联系人、多个号码、分组、收藏 |
| 短信 | 短信记录，按板子/卡槽/方向/关键词筛选 |
| 通话 | 通话记录、录音播放与下载、通话接管 |
| 设置 | Bark 推送、录音上传、自动接听/录音、SIM 异常自愈、日志 |

常用快捷键：`Ctrl/Cmd+K` 聚焦搜索、`Space` 全选、`Delete` 批量删除、`R` 刷新、`Esc` 关闭弹窗。

## 自检

面板、五块板、信号和记录入库是否正常，用只读自检脚本确认：

```bash
cd /Users/vicliu/Github/lvyou_smsweb
./scripts/selfcheck.sh
```

脚本会检查面板健康、Bark 可达性、每块板的心跳/时钟/存储/推送开关/推送地址，并把板端短信和通话与面板数据库逐条对账。全程只读，不发短信、不拨号、不重启卡槽。完整说明见 [docs/selfcheck.md](./docs/selfcheck.md)。

## 项目结构

```
├── backend/
│   ├── main.py           # FastAPI 入口、中间件、生命周期
│   ├── config.py         # 环境变量
│   ├── db.py             # 模型与 Token
│   ├── device_client.py  # 板子通信（token/配置/OTA/WiFi）
│   ├── messages.py       # 短信/通话入库、补拉与推送解析
│   ├── autorecord.py     # 面板接管来电并录音
│   ├── recordings.py     # 录音存储与 AMR→MP3
│   ├── simguard.py       # 209 SIM 异常自愈
│   ├── clockguard.py     # 板子时钟校正
│   ├── routes/           # auth / devices / scan / config / settings
│   │                     # messages / recordings / control / contacts
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/        # Dashboard / Numbers / Contacts / Messages / Calls / Settings
│   │   ├── components/   # 设备卡片、消息面板、录音播放器、弹窗等
│   │   ├── composables/  # 业务逻辑
│   │   ├── stores/       # Pinia
│   │   └── styles/
│   └── package.json
├── scripts/              # selfcheck.py / selfcheck.sh / lvyou CLI
├── docs/selfcheck.md
├── Dockerfile
├── docker-compose.yml
├── install.sh
├── CHANGELOG.md
└── README.md
```

## 常见问题

| 现象 | 优先检查 |
|---|---|
| 板子在线但短信不进面板 | 板子是否开了 `501/502`，推送地址是否指向本面板（用自检脚本对账） |
| 短信只在通话后才出现 | 板子推送格式是 Bark 自定义模板，面板会解析并补拉；仍缺就查推送地址 |
| Bark 不推送 | N1/主机能不能上外网；短信入库不依赖 Bark |
| 录音只有 15 秒 | 用的是板子自带「接听并录音」，改开面板的自动接听/录音，上限 60 秒 |
| 手动挂断后通话又跳出来 | 已修；确认面板是当前版本 |
| 登录一段时间后失效 | 默认 30 天有效期，访问自动续期；改 `BMTOKENTTL` 可调整 |

## 安全说明

- 密码、Webhook Token、上传令牌都不回显完整值；访问日志里的 `k=` 会掩码成 `k=***`
- 认证使用 httpOnly Cookie + CSRF Token
- 设备 IP 必须在本机子网范围内（SSRF 防护）
- 登录、短信、拨号、OTA 各自独立限流
- 审计日志为结构化 JSON，支持轮转

## 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)

## 许可证

MIT License
