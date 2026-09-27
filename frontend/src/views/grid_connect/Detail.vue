<template>
  <section class="page" data-module="grid_connect">
    <header class="page-head">
      <div>
        <h2>调度指令详情</h2>
        <p class="page-desc">指令编号 {{ entry?.指令编号 ?? entryId }} 的完整信息与处理记录，与列表、回执页读同一份数据。</p>
      </div>
      <div class="page-actions">
        <button class="btn ghost" type="button" @click="goList">返回列表</button>
        <button class="btn" type="button" @click="goReceipt">前往回执页</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in displayFields" :key="field">
            <th>{{ field }}</th>
            <td>
              <input
                v-if="editing && editableFields.includes(field)"
                v-model="editForm[field]"
                :placeholder="`请输入${field}`"
              />
              <span v-else :class="{ 'status-abnormal': field === '指令状态' && entry.abnormal }">
                {{ entry[field] ?? '—' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="action-bar">
        <template v-if="!editing">
          <button class="btn" type="button" @click="startEdit">修改指令</button>
          <button
            v-for="action in availableActions"
            :key="action"
            class="btn primary"
            type="button"
            @click="runAction(action)"
          >
            {{ action }}
          </button>
          <span v-if="entry.status === '已反馈'" class="page-desc">指令已闭环，回执内容见回执页。</span>
        </template>
        <template v-else>
          <button class="btn primary" type="button" @click="saveEdit">保存修改</button>
          <button class="btn ghost" type="button" @click="cancelEdit">取消</button>
        </template>
      </div>
      <p v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</p>

      <h3 class="section-title">处理记录</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>动作</th>
            <th>操作人</th>
            <th>结果</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in history" :key="index">
            <td>{{ item.时间 }}</td>
            <td>{{ item.动作 }}</td>
            <td>{{ item.操作人 }}</td>
            <td>{{ item.结果 }}</td>
            <td>{{ item.说明 }}</td>
          </tr>
          <tr v-if="!history.length">
            <td colspan="5" class="empty-state">暂无处理记录</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Entry = Record<string, string | number | boolean | null> & {
  history?: Record<string, string>[]
}

const ENDPOINT = '/api/grid_connect'
const displayFields = ["指令编号", "调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "反馈情况", "指令状态"]
const editableFields = ["执行截止", "执行人员"]

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const entryId = String(route.params.id)

const entry = ref<Entry | null>(null)
const editing = ref(false)
const editForm = reactive<Record<string, string>>({})
const errorMessage = ref('')
const noticeMessage = ref('')

const history = computed(() => entry.value?.history ?? [])
const availableActions = computed(() => {
  if (entry.value?.status === '待接收') return ['接收指令']
  if (entry.value?.status === '已接收') return ['确认执行']
  return []
})

function goList() {
  void router.push('/grid_connect')
}

function goReceipt() {
  void router.push(`/grid_connect/${entryId}/receipt`)
}

function startEdit() {
  for (const field of editableFields) {
    editForm[field] = String(entry.value?.[field] ?? '')
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`, {
      method: 'PUT',
      body: JSON.stringify({ values: { ...editForm, 操作人: session.operator } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '调度指令保存失败')
    }
    noticeMessage.value = payload.message ?? '调度指令已更新'
    editing.value = false
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度指令保存失败'
  }
}

async function runAction(action: string) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, 操作人: session.operator } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '并网调度动作未生效')
    }
    noticeMessage.value = payload.message ?? `调度指令已${action}`
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '并网调度操作失败'
  }
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail ?? '调度指令读取失败')
    }
    entry.value = payload
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '调度指令读取失败'
  }
}

onMounted(load)
</script>
