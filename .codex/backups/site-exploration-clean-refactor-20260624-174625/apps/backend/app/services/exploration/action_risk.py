from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["safe", "guarded", "destructive"]

SAFE_TERMS = (
    "查看",
    "详情",
    "展开",
    "收起",
    "关闭",
    "切换",
    "搜索",
    "筛选",
    "过滤",
    "查询",
    "分页",
    "下一页",
    "上一页",
    "排序",
    "更多",
    "使用",
    "分析",
    "历史",
    "打开",
    "返回",
    "取消",
    "预览",
    "刷新",
    "view",
    "detail",
    "details",
    "open",
    "search",
    "filter",
    "sort",
    "more",
    "next",
    "previous",
    "back",
    "cancel",
    "close",
)

GUARDED_TERMS = (
    "新建",
    "创建",
    "编辑",
    "修改",
    "上传",
    "导入",
    "保存",
    "草稿",
    "提交",
    "复制",
    "导出",
    "批量",
    "选择全部",
    "授权",
    "绑定",
    "新增",
    "create",
    "new",
    "edit",
    "update",
    "upload",
    "import",
    "save",
    "submit",
    "copy",
    "export",
    "batch",
)

DESTRUCTIVE_TERMS = (
    "删除",
    "移除",
    "发布",
    "审批",
    "支付",
    "发送",
    "权限",
    "禁用",
    "启用",
    "清空",
    "重置",
    "覆盖",
    "注销",
    "退出登录",
    "delete",
    "remove",
    "publish",
    "approve",
    "pay",
    "send",
    "permission",
    "disable",
    "enable",
    "reset",
    "clear",
    "logout",
)


@dataclass(frozen=True)
class ActionRisk:
    level: RiskLevel
    reason: str


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    risk: ActionRisk
    reason: str
    suggested_action: str = ""


def classify_action(action: dict | None, element: dict | None = None) -> ActionRisk:
    action = action or {}
    element = element or {}
    action_type = str(action.get("type") or element.get("action_type") or "").strip().lower()
    text = " ".join(
        str(value or "")
        for value in (
            action.get("intent"),
            action.get("value"),
            element.get("name"),
            element.get("text"),
            element.get("role"),
            element.get("label"),
            element.get("id"),
        )
    ).strip().lower()

    if action_type in {"go_back", "close_modal", "wait", "record_state"}:
        return ActionRisk("safe", "返回、关闭、等待和记录状态属于只读探索动作。")

    if action_type == "navigate":
        return ActionRisk("safe", "导航到已知入口属于只读探索动作。")

    if action_type == "click" and _contains_any(text, ("排序", "sort")):
        return ActionRisk("safe", "排序控件属于只读探索动作。")

    if _contains_any(text, DESTRUCTIVE_TERMS):
        return ActionRisk("destructive", "动作名称命中删除、发布、权限、发送或重置等高风险关键词。")

    if action_type == "fill":
        if _contains_any(text, ("搜索", "筛选", "过滤", "查询", "search", "filter", "query")):
            return ActionRisk("safe", "填写搜索、筛选或查询字段属于只读探索动作。")
        return ActionRisk("guarded", "填写非搜索类字段可能修改业务数据。")

    if _contains_any(text, GUARDED_TERMS):
        return ActionRisk("guarded", "动作名称命中新建、编辑、保存、提交、上传或导出等受控关键词。")

    if _contains_any(text, SAFE_TERMS):
        return ActionRisk("safe", "动作名称符合查看、详情、搜索、筛选、分页、更多或使用等低风险探索入口。")

    if action_type == "click":
        return ActionRisk("safe", "未命中写入或破坏性关键词的点击按只读探索动作处理。")

    return ActionRisk("guarded", "动作风险无法确认，按写入动作处理。")


def evaluate_action(action: dict | None, element: dict | None = None) -> ActionDecision:
    risk = classify_action(action, element)
    return ActionDecision(True, risk, "探索任务允许执行完整探索 + CRUD 闭环验证；写操作需受 AI_EXPLORE_* 测试数据守卫约束。")


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in value for term in terms)
