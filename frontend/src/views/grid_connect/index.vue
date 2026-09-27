<template>
  <section class="page" data-module="grid_connect">
    <header class="page-head">
      <div>
        <h2>并网调度管理</h2>
        <p class="page-desc">维护调度指令，围绕指令编号、调度机构、指令内容、下发时间做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记调度指令</button>
        <button class="btn" type="button" @click="exportRows">导出并网调度清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>指令状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td
            v-for="column in columns"
            :key="column"
            :class="{ 'overdue-text': column === '指令状态' && row.abnormal }"
          >
            {{ cell(row, column) }}
          </td>
          <td class="row-actions">
            <button
              v-if="nextAction(row)"
              class="link"
              type="button"
              @click="runAction(nextAction(row), row)"
            >
              {{ nextAction(row) }}
            </button>
            <button class="link" type="button" @click="openDetail(row)">详情/回执</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无并网调度数据，可先登记调度指令</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条并网调度记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="drawer-mask" @click.self="closeDetail">
      <aside class="drawer">
        <header class="drawer-head">
          <h3>指令详情 · {{ cell(detail, '指令编号') }}</h3>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </header>

        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd :class="{ 'overdue-text': column === '指令状态' && detail.abnormal }">
              {{ cell(detail, column) }}
            </dd>
          </template>
        </dl>

        <h4>处理记录</h4>
        <ul class="history-list">
          <li v-for="(item, index) in detailHistory" :key="index">
            <span class="history-time">{{ item.时间 }}</span>
            <span>{{ item.动作 }} → {{ item.结果状态 }}</span>
            <span class="history-meta">{{ item.操作人 }} · {{ item.备注 }}</span>
          </li>
          <li v-if="!detailHistory.length" class="empty-state">暂无处理记录</li>
        </ul>

        <template v-if="nextAction(detail)">
          <h4>回执 · {{ nextAction(detail) }}</h4>
          <form class="receipt-form" @submit.prevent="submitReceipt">
            <label class="filter-item">
              <span>执行人员</span>
              <input v-model="receiptForm.执行人员" placeholder="填写执行人员" />
            </label>
            <label class="filter-item">
              <span>反馈情况</span>
              <input v-model="receiptForm.反馈情况" placeholder="填写反馈情况" />
            </label>
            <label class="filter-item">
              <span>执行截止</span>
              <input v-model="receiptForm.执行截止" type="date" />
            </label>
            <button class="btn primary" type="submit">提交{{ nextAction(detail) }}</button>
          </form>
        </template>
        <p v-else class="page-desc">该指令已反馈办结，重复回执将被拒绝。</p>
      </aside>
    </div>

    <div v-if="createVisible" class="drawer-mask" @click.self="createVisible = false">
      <aside class="drawer">
        <header class="drawer-head">
          <h3>登记调度指令</h3>
          <button class="btn ghost" type="button" @click="createVisible = false">关闭</button>
        </header>
        <form class="receipt-form" @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field" class="filter-item">
            <span>{{ field }}</span>
            <input
              v-model="createForm[field]"
              :type="field === '下发时间' || field === '执行截止' ? 'date' : 'text'"
              :placeholder="`填写${field}`"
            />
          </label>
          <button class="btn primary" type="submit">提交登记</button>
        </form>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

interface HistoryItem {
  时间: string
  动作: string
  结果状态: string
  操作人: string
  备注: string
}

interface Row {
  id: number
  status?: string
  pending?: boolean
  abnormal?: boolean
  处理记录?: HistoryItem[]
  [key: string]: unknown
}

interface ActionPayload {
  ok: boolean
  message?: string
  detail?: string
  entry?: Row
}

const ENDPOINT = '/api/grid_connect'
const columns = ["指令编号", "调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "反馈情况", "指令状态"]
const statuses = ["待接收", "已接收", "已执行", "已反馈"]
const NEXT_ACTION: Record<string, string> = { 待接收: '接收指令', 已接收: '确认执行', 已执行: '反馈结果' }
const FILTER_PARAMS: Record<string, string> = { 指令编号: 'keyword', 调度机构: 'org', 指令内容: 'content' }
const filterFields = ['指令编号', '调度机构', '指令内容']
const createFields = ['指令编号', '调度机构', '指令内容', '下发时间', '执行截止', '执行人员']

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([
  { label: '待执行指令', value: 0 },
  { label: '已执行指令', value: 0 },
  { label: '待反馈指令', value: 0 },
  { label: '超期指令', value: 0 },
])
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const statusFilter = ref('')
const detail = ref<Row | null>(null)
const receiptForm = ref({ 执行人员: '', 反馈情况: '', 执行截止: '' })
const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})

const detailHistory = computed<HistoryItem[]>(() => {
  const list = detail.value?.处理记录
  return Array.isArray(list) ? list : []
})

function nextAction(row: Row | null): string {
  return NEXT_ACTION[String(row?.status ?? '')] ?? ''
}

function cell(row: Row, column: string): string {
  const value = row[column]
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function readError(payload: ActionPayload, fallback: string): string {
  return payload.message ?? payload.detail ?? fallback
}

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createVisible.value = true
}

function closeDetail() {
  detail.value = null
}

async function runAction(action: string, row: Row, extra: Record<string, string> = {}) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, ...extra } }),
    })
    const payload = (await response.json()) as ActionPayload
    if (!response.ok || !payload.ok) {
      throw new Error(readError(payload, '并网调度动作未生效，请稍后重试'))
    }
    noticeMessage.value = payload.message ?? `调度指令已${action}`
    await reload()
    if (detail.value && detail.value.id === row.id) {
      await refreshDetail(row.id)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '并网调度操作失败'
  }
}

async function openDetail(row: Row) {
  await refreshDetail(row.id)
  if (detail.value) {
    receiptForm.value = {
      执行人员: cell(detail.value, '执行人员') === '—' ? '' : cell(detail.value, '执行人员'),
      反馈情况: cell(detail.value, '反馈情况') === '—' ? '' : cell(detail.value, '反馈情况'),
      执行截止: cell(detail.value, '执行截止') === '—' ? '' : cell(detail.value, '执行截止'),
    }
  }
}

async function refreshDetail(id: number) {
  try {
    const response = await request(`${ENDPOINT}/${id}`)
    if (!response.ok) {
      throw new Error('调度指令详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度指令详情读取失败'
  }
}

async function submitReceipt() {
  const current = detail.value
  if (!current) return
  const action = nextAction(current)
  if (!action) return
  await runAction(action, current, { ...receiptForm.value })
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = (await response.json()) as ActionPayload
    if (!response.ok || !payload.ok) {
      throw new Error(readError(payload, '调度指令登记失败'))
    }
    noticeMessage.value = payload.message ?? '调度指令已登记'
    createVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度指令登记失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const [field, param] of Object.entries(FILTER_PARAMS)) {
    const value = filters.value[field]?.trim()
    if (value) params.set(param, value)
  }
  if (statusFilter.value) params.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('调度指令列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '并网调度列表读取失败'
  }
  await reloadStats()
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const all = (payload.items ?? []) as Row[]
    stats.value = [
      { label: '待执行指令', value: all.filter((row) => row.status === '待接收' || row.status === '已接收').length },
      { label: '已执行指令', value: all.filter((row) => row.status === '已执行' || row.status === '已反馈').length },
      { label: '待反馈指令', value: all.filter((row) => row.status === '已执行').length },
      { label: '超期指令', value: all.filter((row) => row.abnormal).length },
    ]
  } catch {
    // 统计卡片失败不阻塞列表展示
  }
}

onMounted(reload)
</script>

<style scoped>
.overdue-text { color: #b42318; font-weight: 600; }
.notice-text { color: #067647; }
.filter-item input, .filter-item select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.drawer-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.35); display: flex; justify-content: flex-end; z-index: 20; }
.drawer { width: 440px; max-width: 92vw; height: 100%; overflow-y: auto; background: #fff; padding: 16px 20px; }
.drawer-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.drawer-head h3 { margin: 0; font-size: 15px; }
.drawer h4 { margin: 16px 0 8px; font-size: 13px; color: var(--muted); }
.detail-grid { display: grid; grid-template-columns: 96px 1fr; gap: 6px 12px; margin: 0; font-size: 13px; }
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.history-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.history-list li { display: flex; flex-direction: column; gap: 2px; border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; }
.history-time, .history-meta { color: var(--muted); font-size: 12px; }
.receipt-form { display: flex; flex-direction: column; gap: 10px; }
</style>
