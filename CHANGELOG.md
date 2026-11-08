# Changelog

本项目的重要变更都会记录在此。

## [Unreleased]

### Added
- **设备运行状态**：设备详情新增「运行状态」卡片，按需读取一次 `stat`（不轮询），显示固件、运行时长、剩余内存、联网通道、WiFi、每日重启时间，以及两个卡槽的状态/信号/运营商/本机号
- **卡槽与整机控制**：详情页支持重启卡槽、卡槽通电/断电、卡槽联网开关、整机重启，以及每日定时重启的开关和小时设置；所有动作都要二次确认并写入审计日志
- **通话接管**：通话页顶部显示正在振铃/通话中的线路，可直接接听、挂断、播放 TTS、发送 DTMF 按键、开始/停止录音；面板只下发指令，不承载通话音频
- **短信任务状态**：新增 `sms_jobs` 表与 `GET /api/sms/jobs/{tid}`，按 `tid` 跟踪「已入队 → 板子已发出 → 已提交运营商 → 送达/失败」
- **Bark 推送**：支持在「系统设置」里配置完整 Bark 地址，收到短信、发送成功/失败/送达时推送；保存后只回显域名
- **接入推送按钮**：设备列表选中后可一键执行 `setinf` + `setallmsgcode`（`POST /api/devices/push/setup`），并回读校验，新板子不必再手敲 `/ctrl`
- **通话提醒**：来电、未接来电、去电未接通同时推送 Bark 和钉钉
- **本机卡号**：通知和短信/通话记录显示「卡1 · 本机号码」；号码在设备详情里填一次即可，板子离线也能保存
- **面板接听并录音**：振铃时由面板下发 `telanswer`，录音时长上限 60 秒（板子自带模式固定 15 秒）；板子离线或推送丢失时仍回落到板子自带接听
- **录音管理**：录音随通话结束上传到面板，AMR 原文件保留并转 MP3，网页内可播放、下载、删除；上传令牌可更换
- **通讯录**：联系人支持多个号码、分组、收藏；短信和通话记录用姓名显示号码
- **SIM 异常自愈**：收到 209 后观察 30 秒，必要时只做一次 `stat` 二次确认，按卡槽状态决定重启卡槽或转人工；24 小时滚动限流，重启后仍异常不重复重启
- **心跳被动监测**：用 998 PING 判断在线，只在长时间没收到心跳时补拉记录，不做定时轮询
- **首页实时流**：实时短信 10 秒自动刷新、可手动立即刷新；有来电时首页顶部直接提示
- **批量操作**：批量改板子管理员密码、批量开启消息推送、批量关闭卡槽联网，设置页与首页设备顺序统一
- **全套自检**：`scripts/selfcheck.sh` 只读检查面板、五块板的心跳/时钟/存储/推送开关，并把板端短信与通话和面板数据库逐条对账，说明见 `docs/selfcheck.md`

### Fixed
- **发短信没有回执**：板子 `402` 回执此前被丢弃，前端只能显示「已提交到板子」；现在会轮询任务并显示最终结果
- **Webhook Token 泄漏**：`/webhook?k=` 的访问日志改为 `k=***`
- **通话事件只走钉钉**：Bark 未配置钉钉时收不到任何来电提醒
- **未接来电漏推**：板子「本地推送」格式没有 `type` 字段，现已识别并补推一次
- **Bark 超时**：只有 IPv4 出口的主机上固定走 IPv4，失败重试一次，推送改为后台线程
- **短信漏入库**：板子用 Bark 自定义模板推送时没有顶层 `type/devId`，面板此前直接忽略；现在解析文本并补拉去重
- **手动挂断后回弹**：延迟到达的通话推送会把已挂断的线路重新显示，现已按本地挂断状态过滤
- **记录页宽度跳动**：记录条数变化和滚动条出现会让整页横向位移，现已固定计数宽度并常驻滚动条槽位
- **容器时区**：容器和日志固定使用北京时间
- **设备顺序不一致**：首页、设置页、SIM 自愈列表统一按首页排序

## [5.2.0] - 2026-06-01

### Added
- **审计日志模块**：`backend/audit.py` — 结构化 JSON 审计日志，支持文件轮转，可对接 Loki/ELK/Datadog
- **持久化限流器**：`backend/ratelimit.py` — SQLite 持久化限流，v4/v6 双进程共享同一计数器，重启不丢状态
- **HTTP 客户端模块**：`backend/http_client.py` — httpx 连接池 + ThreadPoolExecutor 统一生命周期管理
- **设备通信模块**：`backend/device_client.py` — 设备 token/配置/OTA/WiFi 操作抽为独立模块
- **前端 Composables**：`frontend/src/composables/` — useLoading/useNotice/useDeviceActions/useMessaging/useWifi/useOta/useConfigBatch/useDetail
- **前端新组件**：`ConfigModal.vue`、`DeviceGrid.vue`、`NumbersTable.vue`
- **独立样式文件**：`frontend/src/styles/app.css`

### Changed
- **main.py 瘦身**：从大杂烩重构为纯入口 + 中间件 + 生命周期管理，业务逻辑拆入 4 个独立模块
- **App.vue 瘦身**：业务逻辑拆入 composables，App.vue 仅保留布局组装
- **限流器改进**：从内存 dict 改为 SQLite 持久化，支持 v4/v6 双进程共享
- **RateLimiter 接口变更**：构造函数新增 `scope` 参数用于事件命名空间隔离
- **默认密码策略**：BMUIPASS 默认值从空改为 `admin`，启动时仅打警告不阻断，Docker/systemd 部署无需强制设置

### Fixed
- **systemd 双栈启动失败**：UIPASS 为空时 `Environment=BMUIPASS=` 覆盖 config.py 默认值，导致 v4/v6 服务启动失败

## [5.1.0] - 2026-05-29

### Added
- **路由模块化**：`main.py` 从 2379 行拆分为模块化结构
  - `backend/config.py` — 环境变量配置集中管理
  - `backend/db.py` — 数据库模型 + Token CRUD
  - `backend/security.py` — SSRF 防护、IP 校验、网络工具
  - `backend/routes/auth.py` — 登录/登出/健康检查路由
  - `backend/routes/devices.py` — 设备 CRUD/SMS/WiFi/SIM/Forward/OTA 路由
  - `backend/routes/scan.py` — 网络扫描路由
  - `backend/routes/config.py` — 批量配置读写路由
- **前端组件化**：从单文件 800+ 行拆分为 16 个 Vue 组件
  - `components/` — AppHeader、LoginView、MessagePanel、WifiModal、OtaModal、DetailModal 等
  - `stores/` — Pinia 状态管理（auth、devices、scan、notice、dialog）
  - `api/` — axios 封装（client.js、endpoints.js、auth.js）
  - `utils/` — 工具函数
- **CustomSelect 组件**：自定义深色下拉框，替换原生 `<select>` 解决白底刺眼问题
- **Prometheus 监控**：`/metrics` 端点，支持 HTTP 延迟/计数/状态码监控
- **服务端搜索分页**：`/api/devices` 支持 `q` 和 `group` 参数，服务端过滤
- **日志轮转**：`RotatingFileHandler`，防止日志文件无限增长
- **本地网络缓存**：SSRF 白名单检查加 TTL，避免每次请求 fork `ip` 命令
- **`/api/me` 接口**：SPA 启动时检查登录状态
- **`docker-entrypoint.sh`**：独立入口脚本，正确处理双进程信号转发
- **启动安全校验**：拒绝空/默认密码启动，Cookie 配置一致性检查

### Changed
- **Dockerfile**：双进程模式加 `trap` 信号转发，`docker stop` 正确 graceful shutdown
- **prewarm_neighbors**：从每 IP 一个 thread 改为复用共享 ThreadPoolExecutor
- **Cookie + CSRF 认证**：httpOnly cookie + X-CSRF-Token 双重防护，替代纯 Bearer Token
- **Token TTL**：从 8 小时缩短到 2 小时（可通过 `BMTOKENTTL` 配置）
- **登录限流**：从单维度改为 IP + 用户名双维度，成功登录重置用户窗口
- **BMUIPASS 默认值**：从 `admin` 改为空，强制要求设置强密码
- **用户正则替换**：引入 `regex` 库替代 `re`，支持超时防 ReDoS
- **移除 `aiosqlite`**：代码用同步 SQLAlchemy，该依赖未使用

### Fixed
- **OTA 接口 500 错误**：`request=None` 导致 `AttributeError`，改为 `request: Request`
- **深色主题下拉框白底**：原生 `<select>` 的 `<option>` 无法用 CSS 完全控制，改用自定义组件
- **pnpm-lock.yaml 不同步**：`package.json` 新增 `pinia` 依赖但 lockfile 未更新，导致 CI 构建失败

## [5.0.0] - 2026-04-15

### Added
- Web 登录界面
- 设备扫描
- 设备列表与号码列表
- 短信发送
- 电话拨号 / TTS
- 单台 SIM 编辑
- 批量 SIM 配置
- 批量 WiFi 配置
- 批量转发配置
- 批量设备配置（正则替换 + 预设模板）
- 批量 OTA 升级
- 设备别名 / 分组管理
- 审计日志
- FastAPI + SQLite 后端
- Vue + Vite 前端
- systemd 双服务部署（IPv4 + IPv6）
- Docker 部署支持
- 安全增强：SSRF 防护、频率限制、常量时间密码比较
