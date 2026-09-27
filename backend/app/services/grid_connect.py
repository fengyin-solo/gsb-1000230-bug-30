"""并网调度业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "grid_connect"
REQUIRED_FIELDS = ["指令编号", "调度机构", "指令内容"]
STATUS_ORDER = ["待接收", "已接收", "已执行", "已反馈"]
ACTION_RULES = {"接收指令": "已接收", "确认执行": "已执行", "反馈结果": "已反馈"}
NEXT_ACTION = {"待接收": "接收指令", "已接收": "确认执行", "已执行": "反馈结果"}
# 回执时允许随动作回写的字段：执行人员、反馈情况、执行截止等不再被静默丢弃
ACTION_WRITABLE_FIELDS = ["调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "反馈情况"]
# 超期判定只对推进到「已执行 / 已反馈」的动作生效
OVERDUE_TARGETS = {"已执行", "已反馈"}


def _now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _display_status(entry: dict[str, Any]) -> str:
    """列表、详情、回执共用的展示状态：超期指令一律带出标记，不再显示成正常完成。"""
    status = str(entry.get("status") or STATUS_ORDER[0])
    return f"{status}（超期）" if entry.get("abnormal") else status


class GridConnectService:
    """并网调度指令的读写入口：所有页面按指令编号落到同一条记录、同一组字段。"""

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        org: str | None = None,
        content: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("指令编号", ""))]
        if org:
            rows = [row for row in rows if org in str(row.get("调度机构", ""))]
        if content:
            rows = [row for row in rows if content in str(row.get("指令内容", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def find_by_code(self, code: str) -> dict[str, Any] | None:
        """按指令编号定位记录：编号是业务唯一键，列表、详情、回执都以此为准。"""
        code = str(code or "").strip()
        for row in store.rows(MODULE):
            if str(row.get("指令编号", "")).strip() == code:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values["指令编号"]).strip()
        if self.find_by_code(code) is not None:
            return None, [f"指令编号 {code} 已存在，请勿重复登记"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + ACTION_WRITABLE_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = str(value).strip()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["指令状态"] = _display_status(entry)
        entry["处理记录"] = [self._log("登记指令", entry)]
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"调度指令 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于并网调度可执行范围"
        target = ACTION_RULES[action]
        current = str(entry.get("status") or STATUS_ORDER[0])
        current_idx = STATUS_ORDER.index(current) if current in STATUS_ORDER else -1
        target_idx = STATUS_ORDER.index(target)
        code = entry.get("指令编号", entry_id)
        if target_idx <= current_idx:
            return None, f"指令 {code} 已处于「{_display_status(entry)}」，「{action}」请勿重复回执"
        if target_idx > current_idx + 1:
            return None, f"指令 {code} 需先完成「{NEXT_ACTION[current]}」再执行「{action}」"
        # 回写随回执提交的字段：重新进入详情/回执页不再恢复旧值
        for field in ACTION_WRITABLE_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = str(value).strip()
        # 超期判定：以执行截止为准；超期一旦成立即留痕，不再被后续动作抹掉
        deadline = _parse_date(entry.get("执行截止"))
        overdue = bool(deadline and date.today() > deadline and target in OVERDUE_TARGETS)
        if overdue:
            entry["abnormal"] = True
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["指令状态"] = _display_status(entry)
        entry.setdefault("处理记录", []).append(self._log(action, entry))
        message = f"调度指令已{action}"
        if overdue:
            message += "，已超过执行截止，按超期记录"
        return entry, message

    def _log(self, action: str, entry: dict[str, Any]) -> dict[str, str]:
        """处理记录只追加不覆盖：每一次登记、接收、执行、回执都留痕。"""
        return {
            "时间": _now_text(),
            "动作": action,
            "结果状态": entry["指令状态"],
            "操作人": str(entry.get("执行人员") or "—"),
            "备注": "超期办理" if entry.get("abnormal") else "正常办理",
        }
