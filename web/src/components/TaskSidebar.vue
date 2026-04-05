<script setup>
const props = defineProps({
  tasks: { type: Array, required: true },
  busy: { type: Boolean, required: true },
  selectedTaskId: { type: String, required: true },
  formatTimestamp: { type: Function, required: true },
  getTemplateName: { type: Function, required: true },
});

defineEmits(["reset-draft", "refresh-status", "select-task", "delete-task"]);

function taskStatus(task) {
  if (task.video_status === "submitted") {
    return "视频已提交";
  }
  if ((task.last_outputs || []).length) {
    return "图片已生成";
  }
  return "待生成";
}

function taskStatusClass(task) {
  if (task.video_status === "submitted") {
    return "status-submitted";
  }
  if ((task.last_outputs || []).length) {
    return "status-ready";
  }
  return "status-pending";
}

function outputCount(task) {
  return (task.last_outputs || []).length;
}
</script>

<template>
  <section class="sidebar-section">
    <div class="panel-header">
      <h2>任务列表</h2>
      <div class="panel-actions">
        <button class="ghost-button" @click="$emit('reset-draft')" :disabled="busy">新建</button>
        <button class="ghost-button" @click="$emit('refresh-status')" :disabled="busy">刷新</button>
      </div>
    </div>
    <div class="task-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="task-item"
        :class="{ active: selectedTaskId === task.id }"
      >
        <button class="task-item-main" @click="$emit('select-task', task.id)" :disabled="busy">
          <div class="task-item-top">
            <strong>{{ task.name }}</strong>
            <span class="task-status-badge" :class="taskStatusClass(task)">{{ taskStatus(task) }}</span>
          </div>
          <div class="task-meta-row">
            <span>{{ outputCount(task) }} 张产物</span>
            <span>{{ task.template_id ? "已套模板" : "未套模板" }}</span>
          </div>
          <small>{{ formatTimestamp(task.updated_at) }}</small>
          <small v-if="task.template_id" class="task-template-name">模板：{{ getTemplateName(task.template_id) }}</small>
        </button>
        <button
          class="task-delete-button"
          @click.stop="$emit('delete-task', task.id)"
          :disabled="busy"
          aria-label="删除任务"
          title="删除任务"
        >
          删除
        </button>
      </div>

      <div v-if="!tasks.length" class="task-empty-state">
        <strong>还没有任务</strong>
        <span>点击“新建”创建一个草稿，再上传参考图和提示词。</span>
      </div>
    </div>
  </section>
</template>
