<template>
  <section class="page" data-module="grid_connect">
    <header class="page-head">
      <div>
        <h2>并网调度管理</h2>
        <p class="page-desc">维护调度指令，围绕指令编号、调度机构、指令内容、下发时间做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">登记调度指令</button>
        <button class="btn" type="button" @click="exportRows">导出并网调度清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="filter-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>指令编号</span>
        <input v-model="keyword" placeholder="按指令编号检索" />
      </label>
      <label class="filter-item">
        <span>指令状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
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
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td
            v-for="column in columns"
            :key="column"
            :class="{ 'status-abnormal': column === '指令状态' && row.abnormal }"
          >
            {{ row[column] ?? '—' }}
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="goDetail(row)">详情</button>
            <button class="link" type="button" @click="goReceipt(row)">回执</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无并网调度数据，可先登记调度指令</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条并网调度记录</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/grid_connect'
const columns = ["指令编号", "调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "反馈情况", "指令状态"]
const statuses = ["待接收", "已接收", "已执行", "已反馈"]
const createFields = ["指令编号", "调度机构", "指令内容", "下发时间", "执行截止", "执行人员"]

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')
const showCreate = ref(false)
const createForm = reactive<Record<string, string>>({})

const stats = computed(() => [
  { label: '待执行指令', value: rows.value.filter((row) => row.status === '待接收' || row.status === '已接收').length },
  { label: '已执行指令', value: rows.value.filter((row) => row.status === '已执行' || row.status === '已反馈').length },
  { label: '超期指令', value: rows.value.filter((row) => row.abnormal).length },
])

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function goDetail(row: Row) {
  void router.push(`/grid_connect/${row.id}`)
}

function goReceipt(row: Row) {
  void router.push(`/grid_connect/${row.id}/receipt`)
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '调度指令登记失败')
    }
    noticeMessage.value = payload.message ?? '调度指令已登记'
    showCreate.value = false
    Object.keys(createForm).forEach((field) => delete createForm[field])
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度指令登记失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail ?? '调度指令列表读取失败')
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '并网调度列表读取失败'
  }
}

onMounted(reload)
</script>
