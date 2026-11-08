# 绿邮X系列内网群控系统（lvyou-smsweb 定制版）

把家里或办公室的几块绿邮 X 开发板放在一个网页里管理：看它们在线不在线、收短信、打电话、听录音，板子出问题还能自己判断一下。

本仓库是 [lovexme/lvyou_smsweb](https://github.com/lovexme/lvyou_smsweb) 的个人定制分支，在上游 v5.2 的基础上补充了多板日常使用需要的功能。具体差异见 [CHANGELOG.md](./CHANGELOG.md)。

## 它能帮你做什么

**不用再一个个打开板子的后台**

- 一个页面看到所有板子：在线还是掉线、固件版本、两张卡分别是什么运营商、信号几格、卡能不能用。
- 卡片顺序可以自己拖，首页、设置页、下拉框都按同一个顺序，不会各排各的。
- 状态用颜色区分：正常绿色，无卡弱黄色，拒绝、欠费、停机这类问题用红色，一眼能扫出来。

**短信**

- 在面板里选板子、选卡、填号码就能发；收件人可以记住，下次不用重填，也能直接从通讯录挑。
- 板子收到的短信会自动进面板，按板子、卡槽、方向、关键词都能筛。
- 首页右边有实时短信，10 秒自己刷一次，也可以点“立即刷新”。
- 发出去的结果能看到走到哪一步：已交给板子 → 板子已发出 → 运营商已接收 → 送达或失败。
- 配了 Bark 的话，收到短信、发送成功或失败都会推到 iPhone。

**电话**

- 通话记录里有录音，网页上直接播放、下载、删除，不用再去板子后台翻。
- 电话响的时候可以在面板上接听、挂断、放一段语音、按数字键。
- 可以让面板自动接听并录音，最长 60 秒（板子自带的模式只有 15 秒），挂断后录音自动传回面板。
- 有来电、未接来电，首页顶部会直接提示，也会推送到手机。

**号码与通讯录**

- 每张卡的本机号、套餐备注、分组都能记下来；板子离线也能先填。
- 通讯录可以存联系人、一个人的多个号码、分组和收藏，短信和通话记录里直接显示姓名。

**板子出问题的时候**

- 卡槽报 SIM 错误时，面板会先观察半分钟，确认不是一时抖动，再决定重启卡槽还是提示你处理；同一天不会反复重启。
- 板子长时间没消息时才会去补拉一次记录，平时靠板子自己报心跳，不会定时去骚扰它。
- 一套只读自检脚本，能回答“面板、五块板、短信和通话现在到底有没有问题”。

## 日常怎么用

| 页面 | 用来做什么 |
|---|---|
| 设备 | 看板子卡片、批量操作、发短信/拨号、实时短信、来电提示 |
| 号码 | 每张卡的本机号、套餐备注、分组 |
| 通讯录 | 联系人、多个号码、分组、收藏 |
| 短信 | 短信记录，按板子/卡槽/方向/关键词筛选 |
| 通话 | 通话记录、录音播放与下载、通话接管 |
| 设置 | Bark 推送、录音上传、自动接听/录音、SIM 异常自愈 |

常用快捷键：`Ctrl/Cmd+K` 聚焦搜索、`Space` 全选、`Delete` 批量删除、`R` 刷新、`Esc` 关闭弹窗。

首页选中板子后可以批量做这些事：设置 WiFi、升级固件、改配置、开启消息推送、关闭卡槽联网、改板子管理员密码。

## 安装

### 用 Docker（推荐）

```bash
git clone https://github.com/iamvicliu/lvyou_smsweb.git
cd lvyou_smsweb

# 面板登录密码，不设置则默认 admin
echo "BMUIPASS=your_strong_password" > .env

docker compose up -d --build      # 用本仓库的 Dockerfile 构建 lvyou-smsweb:local
docker compose logs -f
```

装好后访问 `http://<主机IP>:8000/`。容器用 host 网络，这样才能扫描局域网；数据存在 `./data`。

### 用安装脚本

适用于 Ubuntu / Debian：

```bash
sudo bash install.sh install
```

安装时会问端口（默认 8000）和登录密码。

```bash
sudo bash install.sh status    # 查看状态
sudo bash install.sh restart   # 重启
sudo bash install.sh logs      # 查看日志
lvyou pass                     # 更改密码
lvyou port                     # 更改端口
lvyou config                   # 查看配置
```

### 手动部署

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && pnpm install && pnpm run build
cd .. && ./start.sh            # 可选：./start.sh 9000 指定端口
```

录音转 MP3 需要 `ffmpeg`。容器里没有的话，可以放在数据目录的 `bin/ffmpeg`，或用 `BMRECORDINGFFMPEG` 指定路径；找不到时保留 AMR 原文件，Safari 能直接播放。

## 新板子怎么接进来

扫描到板子、加进面板后，选中它点「开启消息推送」，面板会自动把推送地址和消息号写进板子，并回读确认。只有跨网段、桥接网络这种算不出面板地址的情况，才需要手敲命令：

1. **推送地址指向本面板**（`<BOARD_TOKEN>` 是板子管理员 Token）：

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

   用 `cmd=askallmsgcode` 复查。少一个消息号就少一类事件：没有 `998` 面板不知道板子在线，没有 `501/502` 短信进不了面板，没有 `209` 收不到 SIM 异常通知。

3. **录音上传**（只有用面板录音时才需要）：在「设置 → 录音上传」里看上传地址，下发到板子。上传令牌随时可以换。

短信回执依赖板子的 `402`（板子已处理）和 `502/503`（运营商回执）；只在面板点发送，拿到的响应只有 `type=401 / sending...`。

## 技术说明

### 架构

- **后端**：FastAPI + SQLAlchemy + SQLite + httpx
- **前端**：Vue 3 + Vite + Pinia + Vue Router + axios
- **部署**：systemd / Docker，容器和日志固定使用北京时间（Asia/Shanghai）

板子和面板之间是板子主动推送事件（短信、来电、心跳、SIM 异常），面板只在下发指令时访问板子。短信、通话这类关键记录，面板收到推送后入库，必要时用查询命令补拉并去重。

### 主要模块

```
backend/
├── main.py           # FastAPI 入口、中间件、生命周期
├── config.py         # 环境变量
├── device_client.py  # 板子通信（token/配置/OTA/WiFi）
├── messages.py       # 短信/通话入库、补拉、推送解析
├── autorecord.py     # 面板接听来电并录音
├── recordings.py     # 录音存储与 AMR→MP3
├── simguard.py       # 209 SIM 异常自愈
├── clockguard.py     # 板子时钟校正
└── routes/           # auth / devices / scan / config / settings
                      # messages / recordings / control / contacts
```

```
frontend/src/
├── views/        # Dashboard / Numbers / Contacts / Messages / Calls / Settings
├── components/   # 设备卡片、消息面板、录音播放器、各类弹窗
├── composables/  # 业务逻辑
├── stores/       # Pinia
└── styles/
```

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

### 安全

- 密码、Webhook Token、上传令牌都不回显完整值；访问日志里的 `k=` 会掩码成 `k=***`
- 认证使用 httpOnly Cookie + CSRF Token
- 设备 IP 必须在本机子网范围内（SSRF 防护）
- 登录、短信、拨号、OTA 各自独立限流
- 审计日志为结构化 JSON，支持轮转

### 自检脚本

想确认面板、五块板、信号和记录入库都正常，跑这个只读脚本：

```bash
cd /Users/vicliu/Github/lvyou_smsweb
./scripts/selfcheck.sh
```

它会检查面板健康、Bark 能不能通、每块板的心跳/时钟/存储/推送开关/推送地址，再把板子上的短信和通话与面板数据库逐条对账。全程只读，不发短信、不拨号、不重启卡槽。细节见 [docs/selfcheck.md](./docs/selfcheck.md)。

## 常见问题

| 现象 | 优先检查 |
|---|---|
| 板子在线但短信不进面板 | 板子是否开了 `501/502`，推送地址是否指向本面板（用自检脚本对账） |
| 短信只在通话后才出现 | 板子推送格式是 Bark 自定义模板，面板会解析并补拉；仍缺就查推送地址 |
| Bark 不推送 | N1/主机能不能上外网；短信入库不依赖 Bark |
| 录音只有 15 秒 | 用的是板子自带「接听并录音」，改开面板的自动接听/录音，上限 60 秒 |
| 手动挂断后通话又跳出来 | 已修；确认面板是当前版本 |
| 登录一段时间后失效 | 默认 30 天有效期，访问自动续期；改 `BMTOKENTTL` 可调整 |

## 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)

## 许可证

MIT License
