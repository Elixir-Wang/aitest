# 页面探索功能 - 部署指南

## 系统要求

### 后端
- Python 3.10+
- Node.js 18+ (用于playwright-cli)
- 2GB+ RAM
- 10GB+ 磁盘空间

### 前端
- Node.js 18+
- 现代浏览器（Chrome, Firefox, Safari, Edge）

---

## 安装步骤

### 1. 安装Playwright CLI

```bash
npm install -g @playwright/test
npx playwright install chromium
```

验证安装：
```bash
playwright-cli --version
```

### 2. 安装Python依赖

```bash
cd apps/backend
pip install -r requirements.txt
```

主要依赖：
- `fastapi` - Web框架
- `uvicorn` - ASGI服务器
- `pydantic` - 数据验证
- `pyyaml` - YAML处理
- `langchain` - Agent框架

### 3. 安装前端依赖

```bash
cd apps/frontend
npm install
```

主要依赖：
- `react` - UI框架
- `typescript` - 类型系统

---

## 配置

### 后端配置

创建 `apps/backend/.env`:

```env
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据目录
DATA_DIR=./data/projects

# Playwright配置
PLAYWRIGHT_TIMEOUT=30000
PLAYWRIGHT_BROWSER=chromium

# 日志级别
LOG_LEVEL=INFO
```

### 前端配置

创建 `apps/frontend/.env`:

```env
# API地址
REACT_APP_API_URL=http://localhost:8000
```

---

## 启动服务

### 开发环境

**后端：**
```bash
cd apps/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端：**
```bash
cd apps/frontend
npm start
```

访问：`http://localhost:3000`

### 生产环境

**后端：**
```bash
cd apps/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**前端：**
```bash
cd apps/frontend
npm run build
# 使用nginx或其他静态服务器托管build目录
```

---

## 验证部署

### 1. 检查后端健康

```bash
curl http://localhost:8000/health
```

期望响应：
```json
{"status": "healthy"}
```

### 2. 检查API文档

访问：`http://localhost:8000/docs`

应该看到Swagger UI界面。

### 3. 测试探索流程

```bash
# 创建探索任务
curl -X POST http://localhost:8000/api/exploration/runs \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-project",
    "start_url": "https://example.com",
    "max_depth": 2,
    "max_pages": 10
  }'

# 查询任务状态
curl http://localhost:8000/api/exploration/runs/{run_id}

# 测试SSE流
curl -N http://localhost:8000/api/exploration/runs/{run_id}/events
```

---

## 故障排查

### Playwright CLI找不到

**症状：** `playwright-cli: command not found`

**解决：**
```bash
npm install -g @playwright/test
export PATH=$PATH:$(npm bin -g)
```

### SSE连接失败

**症状：** 前端无法接收实时事件

**检查：**
1. 浏览器控制台是否有CORS错误
2. 后端日志是否有SSE相关错误
3. 网络中是否有代理或防火墙阻止

**解决：** 在后端添加CORS配置：
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 内存不足

**症状：** 探索大型网站时服务崩溃

**解决：**
1. 减小 `max_pages` 限制
2. 增加服务器内存
3. 调整Playwright内存限制

### 磁盘空间不足

**症状：** 无法写入产物文件

**解决：**
1. 清理旧的探索run目录
2. 设置自动清理策略
3. 增加磁盘空间

---

## 监控和日志

### 日志位置

- 后端日志: `apps/backend/logs/app.log`
- 探索日志: `data/projects/{project_id}/page_exploration/runs/{run_id}/logs/`

### 监控指标

推荐监控：
- API响应时间
- SSE连接数
- 探索任务成功率
- 磁盘使用率
- 内存使用率

### 日志分析

查看最近的错误：
```bash
tail -f apps/backend/logs/app.log | grep ERROR
```

---

## 性能优化

### 后端优化

1. **增加worker数量：**
```bash
uvicorn app.main:app --workers 8
```

2. **使用缓存：**
```python
# 添加Redis缓存
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
```

3. **数据库优化：**
如果使用数据库存储runs，添加索引：
```sql
CREATE INDEX idx_run_status ON exploration_runs(status);
CREATE INDEX idx_run_project ON exploration_runs(project_id);
```

### 前端优化

1. **代码分割：**
```tsx
const ExplorationProgressPanel = lazy(() => 
  import('./components/ExplorationProgressPanel')
);
```

2. **构建优化：**
```bash
npm run build -- --optimization
```

---

## 安全建议

### 1. API认证

添加JWT认证：
```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

@router.post("/runs")
async def create_run(
    request: CreateExplorationRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 验证token
    pass
```

### 2. 输入验证

所有URL输入都已通过Pydantic验证，但建议额外检查：
```python
def validate_url(url: str):
    # 禁止内网IP
    # 禁止file:// 协议
    # 限制域名白名单
    pass
```

### 3. 速率限制

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/runs")
@limiter.limit("10/minute")
async def create_run(...):
    pass
```

### 4. HTTPS

生产环境必须使用HTTPS：
```nginx
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location /api {
        proxy_pass http://localhost:8000;
    }
}
```

---

## 备份和恢复

### 备份策略

每日备份探索产物：
```bash
#!/bin/bash
BACKUP_DIR=/backups/page_exploration
DATE=$(date +%Y%m%d)

tar -czf $BACKUP_DIR/data_$DATE.tar.gz data/projects/
```

### 恢复

```bash
tar -xzf data_20260627.tar.gz -C /
```

---

## 升级指南

### 后端升级

```bash
cd apps/backend
git pull
pip install -r requirements.txt --upgrade
# 运行数据库迁移（如果有）
# 重启服务
systemctl restart page-exploration-api
```

### 前端升级

```bash
cd apps/frontend
git pull
npm install
npm run build
# 部署新的build目录
```

---

## Docker部署（可选）

### Dockerfile

**后端：**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**前端：**
```dockerfile
FROM node:18 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
```

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: ./apps/backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000

  frontend:
    build: ./apps/frontend
    ports:
      - "80:80"
    depends_on:
      - backend
```

启动：
```bash
docker-compose up -d
```

---

## 支持

如有问题，请查看：
- GitHub Issues: [项目地址]
- 文档: `/docs/superpowers/specs/`
- API文档: `http://localhost:8000/docs`
