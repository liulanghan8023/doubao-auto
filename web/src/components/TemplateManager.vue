<script setup>
defineProps({
  templates: { type: Array, required: true },
  busy: { type: Boolean, required: true },
  templateEditorId: { type: String, required: true },
  templateForm: { type: Object, required: true },
  templateEditorModeLabel: { type: String, required: true },
  formatTimestamp: { type: Function, required: true },
});

defineEmits(["reset-template", "select-template", "save-template", "delete-template"]);
</script>

<template>
  <section class="template-manager">
    <div class="template-toolbar">
      <button class="primary-button" @click="$emit('reset-template')" :disabled="busy">新建模板</button>
    </div>

    <div class="template-layout">
      <div class="template-table-wrap">
        <table class="template-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>图片提示词</th>
              <th>视频提示词</th>
              <th>创建时间</th>
              <th class="template-actions-col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="template in templates" :key="template.id" :class="{ active: template.id === templateEditorId }">
              <td>{{ template.name }}</td>
              <td class="template-prompt-cell">{{ template.image_prompt }}</td>
              <td class="template-prompt-cell">{{ template.video_prompt }}</td>
              <td>{{ formatTimestamp(template.created_at) }}</td>
              <td class="template-actions-cell">
                <button class="ghost-button table-button" @click="$emit('select-template', template.id)" :disabled="busy">
                  编辑
                </button>
                <button class="ghost-button table-button danger-button" @click="$emit('delete-template', template.id)" :disabled="busy">
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="!templates.length">
              <td colspan="5" class="template-empty">暂无模板</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="template-editor panel">
        <div class="section-caption">{{ templateEditorModeLabel }}</div>
        <label class="field">
          <span class="field-label">模板名</span>
          <input v-model="templateForm.name" class="text-input" :disabled="busy" />
        </label>
        <label class="field">
          <span class="field-label">图片提示词</span>
          <textarea v-model="templateForm.imagePrompt" class="prompt-input compact-textarea" rows="4" :disabled="busy" />
        </label>
        <label class="field">
          <span class="field-label">视频提示词</span>
          <textarea v-model="templateForm.videoPrompt" class="prompt-input compact-textarea" rows="4" :disabled="busy" />
        </label>
        <div class="button-row">
          <button class="primary-button" @click="$emit('save-template')" :disabled="busy">保存模板</button>
        </div>
      </div>
    </div>
  </section>
</template>
