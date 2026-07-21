# Locust 编写模式

## 基础结构

```python
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(1, 5)  # 请求间隔（秒）
    host = "https://api.example.com"

    def on_start(self):
        """用户启动时执行（如登录）"""
        response = self.client.post("/api/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        self.token = response.json().get("token")

    @task(3)  # 权重，越大概率被执行
    def get_products(self):
        self.client.get("/api/products")

    @task
    def get_product_detail(self):
        product_id = 123
        self.client.get(f"/api/products/{product_id}")

    @task(2)
    def search_products(self):
        self.client.get("/api/search", params={"q": "laptop"})

    def on_stop(self):
        """用户停止时执行（如清理）"""
        pass
```

## 认证用户模式

```python
from locust import HttpUser, task, between
import os

class AuthenticatedUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """登录获取 token"""
        response = self.client.post("/api/auth/login", json={
            "username": os.getenv("TEST_USER", "admin"),
            "password": os.getenv("TEST_PASS", "admin123")
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")

    @task
    def get_protected_resource(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/api/protected", headers=headers)
```

## CRUD 用户模式

```python
from locust import HttpUser, task, between
import random
import uuid

class CRUDUser(HttpUser):
    wait_time = between(1, 2)
    created_ids = []

    @task(5)
    def create_item(self):
        item_id = str(uuid.uuid4())
        response = self.client.post("/api/items", json={
            "name": f"Test Item {item_id}",
            "quantity": random.randint(1, 100)
        })
        if response.status_code == 201:
            data = response.json()
            self.created_ids.append(data.get("id"))

    @task(3)
    def read_item(self):
        if self.created_ids:
            item_id = random.choice(self.created_ids)
            self.client.get(f"/api/items/{item_id}")
        else:
            self.client.get("/api/items")

    @task(2)
    def update_item(self):
        if self.created_ids:
            item_id = random.choice(self.created_ids)
            self.client.put(f"/api/items/{item_id}", json={
                "quantity": random.randint(1, 100)
            })

    @task(1)
    def delete_item(self):
        if self.created_ids:
            item_id = self.created_ids.pop(0)
            self.client.delete(f"/api/items/{item_id}")
```

## 自定义负载形状

```python
from locust import HttpUser, task, between, LoadTestShape

class StagesShape(LoadTestShape):
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 5},   # 预热
        {"duration": 120, "users": 50, "spawn_rate": 10},  # 正常负载
        {"duration": 180, "users": 100, "spawn_rate": 20}, # 峰值
        {"duration": 240, "users": 200, "spawn_rate": 20}, # 压力
        {"duration": 300, "users": 0, "spawn_rate": 10},   # 逐渐停止
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]
        return None

class WebsiteUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def index(self):
        self.client.get("/")
```

## 峰值测试形状

```python
class SpikeShape(LoadTestShape):
    """模拟突发流量：正常 → 峰值 → 正常"""
    stages = [
        {"duration": 30, "users": 20, "spawn_rate": 5},   # 正常
        {"duration": 10, "users": 200, "spawn_rate": 50}, # 突发峰值
        {"duration": 60, "users": 20, "spawn_rate": 5},   # 恢复正常
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]
        return None
```

## 数据驱动模式

```python
from locust import HttpUser, task, between
import csv
import random

class DataDrivenUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        with open("tests/load/data/users.csv", "r") as f:
            reader = csv.DictReader(f)
            self.users = list(reader)
        self.current_user = random.choice(self.users)

    @task
    def browse_products(self):
        category = random.choice(["electronics", "books", "clothing"])
        self.client.get(f"/api/products?category={category}")
```

## 阈值检查

```python
from locust import events

@events.request.add_listener
def check_response_time(request_type, name, response_time, response_length, exception, **kwargs):
    # 关键接口响应时间检查
    if name == "/api/critical-endpoint":
        if response_time > 500:
            print(f"WARNING: Slow response for {name}: {response_time}ms")

@events.quitting.add_listener
def check_thresholds(environment, **kwargs):
    stats = environment.stats
    if stats.total.fail_ratio > 0.05:
        print(f"ERROR: Fail rate {stats.total.fail_ratio:.2%} exceeds 5% threshold")
```

## FastHttpUser（更高性能）

```python
from locust import task, between
from locust.contrib.fasthttp import FastHttpUser

class FastUser(FastHttpUser):
    wait_time = between(0.1, 0.5)  # 更短的等待时间
    host = "https://api.example.com"

    @task
    def get_items(self):
        self.client.get("/api/items")

    @task
    def post_item(self):
        self.client.post("/api/items", json={"name": "test"})
```
