"""学习组件模板过滤器。"""
from django import template

register = template.Library()

STATE_LABELS = {
    "not_started": "未开始", "in_progress": "进行中", "ready_for_review": "待验收",
    "completed": "已完成", "blocked": "有卡点",
}
TYPE_LABELS = {
    "concept_lab": "概念与实验", "environment_lab": "环境闭环", "integration": "集成",
    "review": "复盘", "documentation": "文档", "presentation": "表达",
    "final_assessment": "最终验收",
}


@register.filter
def learning_state_label(value):
    return STATE_LABELS.get(value, value or "未开始")


@register.filter
def learning_type_label(value):
    return TYPE_LABELS.get(value, value)


TASK_LABELS = {
    "reading": "阅读", "exercise": "练习",
    "experiment": "实验", "acceptance": "验收",
}


@register.filter
def learning_task_label(value):
    return TASK_LABELS.get(value, value)


@register.filter
def learning_week_title(titles, week):
    if isinstance(titles, dict):
        return titles.get(week, "")
    return ""
