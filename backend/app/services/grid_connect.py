"""并网调度业务规则：状态流转、字段校验与筛选口径都收在这里。

列表、详情、回执三个页面读写的是同一份记录，所有写入都经过本服务的状态机：
一次流转里同步写 status（机器态）、指令状态（展示字段）、abnormal（超期标记）
和 history（处理记录），避免多处各写各的导致页面对不上。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "grid_connect"
REQUIRED_FIELDS = ["指令编号", "调度机构", "指令内容"]
EDITABLE_FIELDS = ["调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "反馈情况"]
STATUS_ORDER = ["待接收", "已接收", "已执行", "已反馈"]
# 动作 -> (前置状态, 目标状态)：只有当前状态等于前置状态时才允许流转
ACTION_RULES = {
    "接收指令": ("待接收", "已接收"),
    "确认执行": ("已接收", "已执行"),
    "反馈结果": ("已执行", "已反馈"),
}
# 执行类动作：越过执行截止才做这些动作时按超期处理
OVERDUE_ACTIONS = ("确认执行", "反馈结果")
DEFAULT_OPERATOR = "值班管理员"


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


class GridConnectService:
    """并网调度唯一写入口：按指令编号保证一条指令只有一份状态、一份处理记录。"""

    # ---------- 查询 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("指令编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is not None:
            self._ensure_history(entry)
        return entry

    def find_by_code(self, code: str) -> dict[str, Any] | None:
        """按指令编号定位记录：指令编号是业务主键，全模块按它对齐。"""
        code = str(code or "").strip()
        for row in store.rows(MODULE):
            if str(row.get("指令编号", "")).strip() == code:
                return row
        return None

    # ---------- 写入 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values["指令编号"]).strip()
        if self.find_by_code(code) is not None:
            return None, [f"指令编号 {code} 已存在，同一编号只允许登记一条调度指令"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in dict.fromkeys(REQUIRED_FIELDS + EDITABLE_FIELDS):
            value = str(values.get(field) or "").strip()
            if value:
                entry[field] = value
        entry.setdefault("下发时间", date.today().isoformat())
        entry.setdefault("执行截止", "")
        entry.setdefault("执行人员", "待指派")
        entry.setdefault("反馈情况", "待反馈")
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = []
        self._sync_status(entry)
        self._append_history(entry, "登记指令", self._operator(values), "指令登记入库")
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """更新可编辑字段（如执行截止）；指令编号是业务主键，不允许改。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"调度指令 {entry_id} 不存在或已归档"
        new_code = str(values.get("指令编号") or "").strip()
        if new_code and new_code != str(entry.get("指令编号", "")).strip():
            return None, "指令编号是调度指令的业务主键，不允许修改"
        changes: list[str] = []
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            value = str(values.get(field) or "").strip()
            if field in ("调度机构", "指令内容") and not value:
                return None, f"{field} 不能为空"
            old = str(entry.get(field) or "")
            if value != old:
                entry[field] = value
                changes.append(f"{field}：{old or '—'} → {value or '—'}")
        if not changes:
            return entry, "没有需要更新的字段"
        self._ensure_history(entry)
        self._sync_status(entry)
        self._append_history(entry, "修改指令", self._operator(values), "；".join(changes))
        return entry, "调度指令已更新"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"调度指令 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于并网调度可执行范围"
        source, target = ACTION_RULES[action]
        current = str(entry.get("status", ""))
        self._ensure_history(entry)
        # 幂等：已到达或越过目标状态时，重复提交直接返回原记录，
        # 不覆盖已确认的内容，也不重复记处理记录
        if current in STATUS_ORDER and STATUS_ORDER.index(current) >= STATUS_ORDER.index(target):
            return entry, f"该指令此前已{action}，本次重复提交已忽略，原记录保持不变"
        if current != source:
            return None, f"当前状态「{current}」不允许执行「{action}」，需先流转到「{source}」"
        if action == "反馈结果":
            feedback = str(values.get("反馈情况") or "").strip()
            if not feedback:
                return None, "提交回执前请填写反馈情况"
            entry["反馈情况"] = feedback
        overdue_note = ""
        if action in OVERDUE_ACTIONS and self._is_overdue(entry):
            entry["abnormal"] = True
            overdue_note = f"已超过执行截止 {entry.get('执行截止')}，按超期处理"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        self._sync_status(entry)
        self._append_history(entry, action, self._operator(values), overdue_note or "按期流转")
        suffix = "（超期）" if overdue_note else ""
        return entry, f"调度指令已{action}{suffix}"

    # ---------- 内部工具 ----------

    def _operator(self, values: dict[str, Any]) -> str:
        return str(values.get("操作人") or "").strip() or DEFAULT_OPERATOR

    def _is_overdue(self, entry: dict[str, Any]) -> bool:
        deadline = _parse_date(entry.get("执行截止"))
        return deadline is not None and date.today() > deadline

    def _sync_status(self, entry: dict[str, Any]) -> None:
        """机器态与展示字段在同一次写入里同步，三个页面读到的才是同一份状态。"""
        status = str(entry.get("status", STATUS_ORDER[0]))
        entry["指令状态"] = f"{status}（超期）" if entry.get("abnormal") else status

    def _ensure_history(self, entry: dict[str, Any]) -> None:
        """老数据没有处理记录时补一条登记记录，保证详情页有迹可循。"""
        if isinstance(entry.get("history"), list):
            return
        entry["history"] = [{
            "时间": str(entry.get("下发时间") or ""),
            "动作": "登记指令",
            "操作人": DEFAULT_OPERATOR,
            "结果": str(entry.get("指令状态") or entry.get("status") or ""),
            "说明": "指令登记入库",
        }]

    def _append_history(self, entry: dict[str, Any], action: str, operator: str, note: str) -> None:
        self._ensure_history(entry)
        entry["history"].append({
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "动作": action,
            "操作人": operator,
            "结果": str(entry.get("指令状态") or entry.get("status") or ""),
            "说明": note,
        })
