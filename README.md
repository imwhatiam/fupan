# 每日复盘系统

将 A 股每日复盘分析工作流从 Jupyter Notebook 转化为可持续运行的 Web 服务。

---

## 功能

- **复盘主表**：展示当日涨跌幅 ≥ 8%、成交额 ≥ 8 亿元的股票，按上证 / 深证 × 涨 / 跌分组，支持一键复制全部股票代码
- **行业分析**：统计涨幅 > 5% 和全市场涨幅前 10% 股票的行业聚集情况，计算综合评分并生成柱状图
- **百日新高**：计算每只股票的 100 日最高 / 最低收盘价，按行业聚合展示，并生成近期占比走势图
- **自动初始化**：页面加载时调用 `/api/init/`，根据当前时间决定展示逻辑：
  - 当日为交易日且当前时间 **≥ 18:00** 但数据库尚无当日数据 → 后台异步下载，前端先展示最近一个交易日
  - 当日为交易日但当前时间 **< 18:00** → 仅提示"数据更新时间"，不触发下载
  - 当日为周末 / 节假日 → 展示最近一个有数据的交易日

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python | 推荐 3.12+（requirements.txt 未锁定版本） |
| 后端 | Django | `requirements.txt` 中未锁定版本，按最新稳定版安装 |
| 后端 | Django REST Framework | 同上 |
| 后端 | Gunicorn | 生产环境 WSGI 服务器 |
| 前端 | React | ^19.2.4 |
| 前端 | Vite | ^7.3.1 |
| 数据库 | SQLite（`stock_trade_info.sqlite3`） | 行情数据；Django 默认 `db.sqlite3` 仅用于框架内部 |
| 缓存 | Django LocMemCache（进程内，TTL 12 小时） | — |
| 数据源 | baostock（行业）、上交所 API（SSE）、深交所 API（SZSE） | — |
| 进程管理 | Supervisor | — |
| Web 服务器 | Nginx | — |

> `requirements.txt` 未锁定依赖版本，如需可重复构建，建议在部署时固化版本（`pip freeze > requirements.lock`）。

---

## 目录结构

```
fupan-main/
├── backend/
│   ├── fupan/                  # Django 项目配置
│   │   ├── settings.py         # 支持环境变量注入 SECRET_KEY 等
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── api/
│   │   ├── views.py            # API 端点（6 个）
│   │   ├── urls.py
│   │   ├── services/
│   │   │   ├── data_service.py         # 原始数据下载与读取
│   │   │   ├── db_service.py           # SQLite 读写层
│   │   │   ├── analysis_service.py     # 复盘 / 行业分析
│   │   │   └── hundred_day_service.py  # 百日新高 / 新低分析
│   │   └── management/
│   │       └── commands/
│   │           └── download_stock_data.py  # Django 管理命令（供 crontab 调用）
│   ├── stock_data/             # 原始数据文件（运行时自动创建）
│   ├── stock_trade_info.sqlite3  # 行情数据库（运行时自动创建）
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── index.html              # 注入 window.__API_BASE__ = '/api'
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── StockTable.jsx
│   │   │   ├── IndustryChart.jsx
│   │   │   └── HundredDayView.jsx
│   │   └── services/
│   │       └── api.js          # 统一 HTTP 客户端，读取 window.__API_BASE__
│   ├── vite.config.js
│   └── package.json
├── fupan-utils/                # 历史工具（Notebook 阶段遗留，不参与 Web 服务）
│   ├── fupan.ipynb
│   ├── main.py                 # 历史数据批量导入入口
│   ├── utils.py
│   └── logging_config.py
├── scripts/
│   └── cron_download.sh        # 定时下载 shell 脚本（路径需按实际部署修改）
├── .gitignore
└── README.md
```

---

## 数据库结构

行情数据库（`stock_trade_info.sqlite3`）包含一张表：

```sql
CREATE TABLE stock_trade_info (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    date     TEXT    NOT NULL,   -- YYYY-MM-DD
    code     TEXT    NOT NULL,   -- 6 位股票代码
    name     TEXT    NOT NULL,
    open     REAL,
    close    REAL,               -- 收盘价（SSE 原始字段名为 last，写入时映射为 close）
    pctChg   REAL,               -- 涨跌幅（%）
    amount   REAL,               -- 成交额（元）
    industry TEXT,
    UNIQUE(date, code)
)
```

> 注意：上交所 API 返回字段名为 `last`，`db_service.py` 写入时统一映射为 `close`。  
> Django 默认的 `db.sqlite3` 仅用于框架内部（session / auth），与行情数据无关。

---

## Web API

Base URL：`http://localhost:8000/api`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/init/` | 页面初始化，返回建议展示日期及提示（含异步下载触发逻辑） |
| `GET` | `/api/fupan/?date=YYYY-MM-DD` | 复盘主表 |
| `GET` | `/api/industry/?date=YYYY-MM-DD` | 行业分析 |
| `GET` | `/api/hundred-day/?date=YYYY-MM-DD` | 百日新高 / 新低 |
| `GET` | `/api/dates/` | 数据库中可用的交易日列表 |
| `GET` | `/api/health/` | 健康检查 |

### `/api/init/` 决策逻辑

```
今日为交易日？
├── 是
│   ├── 当前时间 >= 18:00
│   │   ├── DB 有今日数据 → 返回今日，hint: "Today's data loaded."
│   │   └── DB 无今日数据 → 启动后台线程下载，返回今日，hint: "Preparing…"
│   └── 当前时间 < 18:00 → 返回今日，hint: "Data updates at 18:00 on trading days"
│       （不触发下载）
└── 否（周末 / 节假日）
    ├── DB 有数据 → 返回最近交易日，hint 包含假期原因
    └── DB 无数据 → 返回今日，hint: "No data yet."
```

---

## 本地开发

### 后端

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt

python manage.py runserver 0.0.0.0:8000
```

### 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000，/api 自动代理到 :8000
```

> Node.js 要求 **≥ 20.19** 或 **≥ 22.12**（Vite 7 最低要求）。

### 手动下载数据

```bash
# 下载今日数据
python manage.py download_stock_data

# 下载指定日期数据（补历史数据）
python manage.py download_stock_data --date 2026-02-25
```

---

## 生产环境部署（Ubuntu）

以下步骤以 `/srv/fupan-system` 为项目根目录，用户为 `ubuntu` 为例。

### 1. 系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
                   nodejs npm nginx supervisor
```

> Node.js 建议通过 [nvm](https://github.com/nvm-sh/nvm) 安装，确保版本 ≥ 20.19：
> ```bash
> curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
> nvm install 22
> nvm use 22
> ```

### 2. 克隆代码

```bash
sudo mkdir -p /srv/fupan-system
sudo chown ubuntu:ubuntu /srv/fupan-system
git clone <your-repo-url> /srv/fupan-system
```

### 3. Python 环境

```bash
cd /srv/fupan-system
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. 构建前端

```bash
cd /srv/fupan-system/frontend
npm install
npm run build
# 产物输出至 frontend/dist/
```

### 5. 环境变量配置

创建 `/srv/fupan-system/.env`（不提交到 Git）：

```ini
DJANGO_SECRET_KEY=your-secure-random-key-here
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=your-domain.com,your-server-ip
```

生成强密钥的方法：

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 6. 创建必要目录

```bash
mkdir -p /srv/fupan-system/backend/stock_data
mkdir -p /var/log/fupan
sudo chown ubuntu:ubuntu /var/log/fupan
```

### 7. Supervisor 配置（管理 Gunicorn 进程）

创建配置文件：

```bash
sudo nano /etc/supervisor/conf.d/fupan.conf
```

写入以下内容：

```ini
[program:fupan]
command=/srv/fupan-system/venv/bin/gunicorn fupan.wsgi:application
    --bind 127.0.0.1:8000
    --workers 2
    --timeout 120
    --access-logfile /var/log/fupan/gunicorn_access.log
    --error-logfile /var/log/fupan/gunicorn_error.log
directory=/srv/fupan-system/backend
user=ubuntu
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/fupan/supervisor.log
stderr_logfile=/var/log/fupan/supervisor_error.log
environment=
    DJANGO_SETTINGS_MODULE="fupan.settings",
    DJANGO_SECRET_KEY="your-secure-random-key-here",
    DJANGO_DEBUG="false",
    DJANGO_ALLOWED_HOSTS="your-domain.com"
```

启动服务：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start fupan

# 查看状态
sudo supervisorctl status fupan
```

常用 Supervisor 命令：

```bash
sudo supervisorctl stop fupan      # 停止
sudo supervisorctl restart fupan   # 重启
sudo supervisorctl tail fupan      # 查看日志
```

### 8. Nginx 配置

```bash
sudo nano /etc/nginx/sites-available/fupan
```

写入以下内容：

```nginx
server {
    listen 80;
    server_name your-domain.com;   # 替换为你的域名或 IP

    # 前端静态文件（Vite 构建产物）
    location / {
        root /srv/fupan-system/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反向代理到 Gunicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    access_log /var/log/nginx/fupan_access.log;
    error_log  /var/log/nginx/fupan_error.log;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/fupan /etc/nginx/sites-enabled/
sudo nginx -t          # 测试配置语法
sudo systemctl reload nginx
```

### 9. 定时任务（crontab）

每个交易日 17:00 自动下载数据并写入数据库：

```bash
crontab -e
```

添加以下行（路径按实际部署调整）：

```cron
0 17 * * 1-5 /srv/fupan-system/scripts/cron_download.sh >> /var/log/fupan/cron.log 2>&1
```

确认脚本有执行权限：

```bash
chmod +x /srv/fupan-system/scripts/cron_download.sh
```

> **注意**：`cron_download.sh` 内目前硬编码了开发时路径（`/root/.python-3.12-venv/` 和 `/root/fupan/`），部署前需按实际路径修改，例如：
> ```bash
> /srv/fupan-system/venv/bin/python /srv/fupan-system/backend/manage.py download_stock_data
> ```

---

## 服务启动验证

```bash
# 检查 Gunicorn 是否正常
sudo supervisorctl status fupan
curl http://127.0.0.1:8000/api/health/

# 检查 Nginx 是否正常
sudo systemctl status nginx
curl http://your-domain.com/api/health/
```

返回 `{"status": "ok"}` 表示服务正常。

---

## 更新部署

```bash
cd /srv/fupan-system

# 拉取最新代码
git pull

# 重新构建前端
cd frontend && npm install && npm run build && cd ..

# 更新 Python 依赖（如有变化）
source venv/bin/activate
pip install -r backend/requirements.txt

# 重启后端
sudo supervisorctl restart fupan
```

---

## 历史数据导入

`fupan-utils/` 目录保留了项目迁移到 Web 服务之前的 Jupyter Notebook 工具，可用于批量导入历史数据到 SQLite：

```bash
cd fupan-utils
# 编辑 main.py 中的 end_date，然后运行：
python main.py
```

该目录不参与 Web 服务的正常运行，仅用于历史数据补录。
