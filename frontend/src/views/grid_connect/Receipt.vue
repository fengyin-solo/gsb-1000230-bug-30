<template>
  <section class="page" data-module="grid_connect">
    <header class="page-head">
      <div>
        <h2>调度指令回执</h2>
        <p class="page-desc">指令编号 {{ entry?.指令编号 ?? entryId }} 的回执单；已回执的指令重复提交不会覆盖原记录。</p>
      </div>
      <div class="page-actions">
        <button class="btn ghost" type="button" @click="goDetail">返回详情</button>
        <button class="btn ghost" type="button" @click="goList">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in summaryFields" :key="field">
            <th>{{ field }}</th>
            <td>
              <span :class="{ 'status-abnormal': field === '指令状态' && entry.abnormal }">
                {{ entry[field] ?? '—' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="entry.status === '已反馈'" class="receipt-panel">
        <h3 class="section-title">回执信息</h3>
        <table class="data-table detail-table">
          <tbody>
            <tr>
              <th>反馈情况</th>
              <td>{{ entry.反馈情况 }}</td>
            </tr>
            <tr>
              <th>回执时间</th>
              <td>{{ receiptRecord?.时间 ?? '—' }}</td>
            </tr>
            <tr>
              <th>回执人</th>
              <td>{{ receiptRecord?.操作人 ?? '—' }}</td>
            </tr>
            <tr>
              <th>回执结果</th>
              <td>{{ receiptRecord?.结果 ?? entry.指令状态 }}</td>
            </tr>
          </tbody>
        </table>
        <p class="ok-text">该指令已完成回执，再次提交将被服务端忽略，以上原记录保持不变。</p>
      </div>

      <form v-else-if="entry.status === '已执行'" class="receipt-panel" @submit.prevent="submitReceipt">
        <h3 class="section-title">填写回执</h3>
        <p v-if="overdue" class="error-text">已超过执行截止 {{ entry.执行截止 }}，本次回执将被标记为超期。</p>
        <label class="filter-item receipt-field">
          <span>反馈情况</span>
          <textarea v-model="feedback" rows="3" placeholder="请输入指令执行与反馈情况"></textarea>
        </label>
        <div class="action-bar">
          <button class="btn primary" type="submit">提交回执</button>
          <span class="page-desc">回执人：{{ session.operator }}</span>
        </div>
      </form>

      <p v-else class="page-desc">
        当前状态为「{{ entry.指令状态 }}」，需先在详情页完成接收与执行流转后才能填写回执。
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Entry = Record<string, string | number | boolean | null> & {
  history?: Record<string, string>[]
}

const ENDPOINT = '/api/grid_connect'
const summaryFields = ["指令编号", "调度机构", "指令内容", "下发时间", "执行截止", "执行人员", "指令状态"]

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const entryId = String(route.params.id)

const entry = ref<Entry | null>(null)
const feedback = ref('')
const errorMessage = ref('')

const receiptRecord = computed(() => {
  const records = (entry.value?.history ?? []).filter((item) => item.动作 === '反馈结果')
  return records.length ? records[records.length - 1] : null
})

const overdue = computed(() => {
  const deadline = String(entry.value?.执行截止 ?? '')
  return Boolean(deadline) && deadline < new Date().toISOString().slice(0, 10)
})

function goDetail() {
  void router.push(`/grid_connect/${entryId}`)
}

function goList() {
  void router.push('/grid_connect')
}

async function submitReceipt() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: { action: '反馈结果', 反馈情况: feedback.value, 操作人: session.operator },
      }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.message ?? payload?.detail ?? '回执提交失败')
    }
    feedback.value = ''
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回执提交失败'
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
