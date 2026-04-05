<script setup>
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import { VueFlow } from "@vue-flow/core";

defineProps({
  activeTask: { type: Object, default: null },
  busy: { type: Boolean, required: true },
  status: { type: Object, default: null },
  feedback: { type: String, required: true },
  activeNodeId: { type: String, required: true },
  nodes: { type: Array, required: true },
  edges: { type: Array, required: true },
  taskForm: { type: Object, required: true },
  templates: { type: Array, required: true },
  taskPromptVariables: { type: Array, required: true },
  taskVariableInputs: { type: Object, required: true },
  latestImageOutput: { type: String, required: true },
  selectedVideoReferenceImage: { type: String, required: true },
  formModeLabel: { type: String, required: true },
  formatTimestamp: { type: Function, required: true },
  artifactUrl: { type: Function, required: true },
  outputName: { type: Function, required: true },
  taskFormImageHint: { type: Function, required: true },
  getTemplateName: { type: Function, required: true },
});

defineEmits([
  "execute-task",
  "submit-video",
  "node-click",
  "task-file-change",
  "task-template-change",
  "task-variable-change",
  "select-video-reference-image",
]);
</script>

<template>
  <section class="panel canvas-panel">
    <div class="panel-header">
      <h2>任务流程</h2>
    </div>

    <p class="feedback" :class="{ error: status && status.last_error }">
      {{ (status && status.last_error) || feedback || "系统正常。" }}
    </p>

    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :fit-view-on-init="true"
      :nodes-draggable="false"
      :zoom-on-scroll="false"
      :pan-on-drag="true"
      class="flow-canvas"
      @node-click="$emit('node-click', $event)"
    >
      <Background :gap="18" :size="1" pattern-color="rgba(15, 118, 110, 0.14)" />
      <Controls position="bottom-right" />
    </VueFlow>

    <div class="detail-grid">
      <section class="detail-card" :class="{ active: activeNodeId === 'create' }">
        <div class="detail-header">
          <span class="node-chip">节点 1</span>
          <h3>任务配置</h3>
        </div>
        <div class="detail-actions">
          <button class="primary-button" @click="$emit('execute-task')" :disabled="busy">执行图片生成</button>
        </div>
        <div class="section-caption">{{ formModeLabel }}</div>
        <label class="field">
          <span class="field-label">任务名</span>
          <input v-model="taskForm.name" class="text-input" :disabled="busy" />
        </label>
        <label class="field">
          <span class="field-label">参考图片</span>
          <input class="file-input" type="file" accept="image/*" @change="$emit('task-file-change', $event)" :disabled="busy" />
          <span class="field-hint">{{ taskFormImageHint() }}</span>
        </label>
        <label class="field">
          <span class="field-label">提示词模板</span>
          <select
            class="text-input"
            :value="taskForm.templateId"
            :disabled="busy"
            @change="$emit('task-template-change', $event.target.value)"
          >
            <option value="">不使用模板</option>
            <option v-for="template in templates" :key="template.id" :value="template.id">
              {{ template.name }}
            </option>
          </select>
          <span v-if="taskForm.templateId" class="field-hint">当前模板：{{ getTemplateName(taskForm.templateId) }}</span>
        </label>
        <section v-if="taskPromptVariables.length" class="variable-panel">
          <div class="variable-panel-header">
            <span class="field-label">模板变量</span>
            <span class="field-hint">填写后会自动同步到下方提示词</span>
          </div>
          <div class="variable-grid">
            <label v-for="name in taskPromptVariables" :key="name" class="field variable-field">
              <span class="variable-token">【{{ name }}】</span>
              <input
                :value="taskVariableInputs[name] || ''"
                class="text-input"
                :disabled="busy"
                @input="$emit('task-variable-change', name, $event.target.value)"
              />
            </label>
          </div>
        </section>
        <label class="field">
          <span class="field-label">图片提示词</span>
          <textarea v-model="taskForm.imagePrompt" class="prompt-input compact-textarea" rows="4" :disabled="busy" />
        </label>
        <label class="field">
          <span class="field-label">视频提示词</span>
          <textarea v-model="taskForm.videoPrompt" class="prompt-input compact-textarea" rows="4" :disabled="busy" />
        </label>
      </section>

      <section class="detail-card detail-card-emphasis" :class="{ active: activeNodeId === 'image' }">
        <div class="detail-header">
          <span class="node-chip">节点 2</span>
          <h3>图片生成</h3>
        </div>

        <div v-if="status && status.active_job === 'run-once'" class="job-banner">
          当前正在执行图片生成，完成后会自动刷新产物。
        </div>

        <div v-if="activeTask && activeTask.image_chat_url" class="status-card">
          <strong>最新图片任务</strong>
          <a class="status-link" :href="activeTask.image_chat_url" target="_blank" rel="noreferrer">打开豆包任务</a>
          <span>{{ formatTimestamp(activeTask.latest_output_created_at) || "刚刚生成" }}</span>
        </div>

        <div v-if="activeTask && activeTask.last_outputs && activeTask.last_outputs.length" class="node-output">
          <div class="node-output-header">
            <strong>任务产物</strong>
            <span>{{ activeTask.last_outputs.length }} 个文件</span>
          </div>
          <div class="gallery compact-gallery">
            <a
              v-for="path in activeTask.last_outputs"
              :key="path"
              class="gallery-card compact-card"
              :href="artifactUrl(path)"
              target="_blank"
              rel="noreferrer"
            >
              <img :src="artifactUrl(path)" :alt="path" />
              <span>{{ outputName(path) }}</span>
            </a>
          </div>
        </div>
      </section>

      <section class="detail-card detail-card-muted" :class="{ active: activeNodeId === 'video' }">
        <div class="detail-header">
          <span class="node-chip">节点 3</span>
          <h3>视频生成</h3>
        </div>
        <div v-if="activeTask && activeTask.video_status === 'submitted'" class="status-card">
          <strong>已提交</strong>
          <a v-if="activeTask.video_chat_url" class="status-link" :href="activeTask.video_chat_url" target="_blank" rel="noreferrer">
            打开豆包任务
          </a>
          <span>{{ formatTimestamp(activeTask.updated_at) || "刚刚提交" }}</span>
        </div>
        <div class="detail-actions">
          <button class="secondary-button" @click="$emit('submit-video')" :disabled="busy || !latestImageOutput">
            提交视频生成
          </button>
        </div>
        <div class="field">
          <span class="field-label">生成方式</span>
          <label class="checkbox-field">
            <input v-model="taskForm.videoUseImageChat" type="checkbox" :disabled="busy" />
            <span>在节点 2 对话框基础上生成视频</span>
          </label>
          <span class="field-hint">
            {{ taskForm.videoUseImageChat ? "默认打开节点 2 的豆包地址后切换到视频生成。" : "关闭后沿用当前独立视频生成流程。" }}
          </span>
        </div>
        <div v-if="status && status.active_job === 'run-video'" class="job-banner">
          当前正在提交视频生成任务。
        </div>
        <div v-if="activeTask && activeTask.last_outputs && activeTask.last_outputs.length" class="node-output">
          <div class="node-output-header">
            <strong>视频参考图</strong>
            <span>从节点 2 产物中选择</span>
          </div>
          <div class="gallery compact-gallery selectable-gallery">
            <button
              v-for="path in activeTask.last_outputs"
              :key="path"
              type="button"
              class="gallery-card compact-card gallery-select-card"
              :class="{ active: selectedVideoReferenceImage === path }"
              @click="$emit('select-video-reference-image', path)"
            >
              <img :src="artifactUrl(path)" :alt="path" />
              <span>{{ outputName(path) }}</span>
            </button>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
