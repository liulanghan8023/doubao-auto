<script setup>
import { proxyRefs, ref } from "vue";
import TaskSidebar from "./components/TaskSidebar.vue";
import TemplateManager from "./components/TemplateManager.vue";
import WorkflowBoard from "./components/WorkflowBoard.vue";
import { useAutomationConsole } from "./composables/useAutomationConsole";

const consoleState = proxyRefs(useAutomationConsole());
const activeMenu = ref("tasks");
</script>

<template>
  <main class="admin-shell">
    <aside class="admin-sidebar">
      <div class="brand-block">
        <p class="eyebrow">Admin Console</p>
        <h1>Doubao</h1>
      </div>

      <nav class="menu-list">
        <button
          class="menu-item"
          :class="{ active: activeMenu === 'tasks' }"
          @click="activeMenu = 'tasks'"
        >
          <strong>任务管理</strong>
        </button>
        <button
          class="menu-item"
          :class="{ active: activeMenu === 'templates' }"
          @click="activeMenu = 'templates'"
        >
          <strong>模板管理</strong>
        </button>
      </nav>

      <div class="sidebar-tools">
        <span class="hero-pill">{{ consoleState.activeTaskMeta }}</span>
        <button class="ghost-button" @click="consoleState.invokeLogin" :disabled="consoleState.busy">
          打开登录窗口
        </button>
      </div>
    </aside>

    <section class="admin-main">
      <section v-if="activeMenu === 'tasks'" class="workspace-grid workspace-grid-admin">
        <aside class="panel sidebar-panel">
          <TaskSidebar
            :tasks="consoleState.tasks"
            :busy="consoleState.busy"
            :selected-task-id="consoleState.selectedTaskId"
            :format-timestamp="consoleState.formatTimestamp"
            :get-template-name="consoleState.getTemplateName"
            @reset-draft="consoleState.resetDraft"
            @refresh-status="consoleState.refreshStatus"
            @select-task="consoleState.selectTask"
            @delete-task="consoleState.deleteTask"
          />
        </aside>

        <div class="main-column">
          <WorkflowBoard
            :active-task="consoleState.activeTask"
            :busy="consoleState.busy"
            :status="consoleState.status"
            :feedback="consoleState.feedback"
            :active-node-id="consoleState.activeNodeId"
            :nodes="consoleState.nodes"
            :edges="consoleState.edges"
            :task-form="consoleState.taskForm"
            :templates="consoleState.templates"
            :task-prompt-variables="consoleState.taskPromptVariables"
            :task-variable-inputs="consoleState.taskVariableInputs"
            :latest-image-output="consoleState.latestImageOutput"
            :selected-video-reference-image="consoleState.selectedVideoReferenceImage"
            :form-mode-label="consoleState.formModeLabel"
            :format-timestamp="consoleState.formatTimestamp"
            :artifact-url="consoleState.artifactUrl"
            :output-name="consoleState.outputName"
            :task-form-image-hint="consoleState.taskFormImageHint"
            :get-template-name="consoleState.getTemplateName"
            @execute-task="consoleState.executeTaskFlow"
            @submit-video="consoleState.submitVideoTask"
            @node-click="consoleState.onNodeClick"
            @task-file-change="consoleState.onTaskFileChange"
            @task-template-change="consoleState.applyTemplateToTask"
            @task-variable-change="consoleState.updateTaskVariable"
            @select-video-reference-image="consoleState.selectVideoReferenceImage"
          />
        </div>
      </section>

      <section v-else class="panel template-page">
        <div class="page-header">
          <div>
            <p class="eyebrow">Prompt Templates</p>
            <h2>模板管理</h2>
            <p class="hint">维护图片和视频提示词模板，任务侧可直接选择并应用。</p>
          </div>
        </div>

        <TemplateManager
          :templates="consoleState.templates"
          :busy="consoleState.busy"
          :template-editor-id="consoleState.templateEditorId"
          :template-form="consoleState.templateForm"
          :template-editor-mode-label="consoleState.templateEditorModeLabel"
          :format-timestamp="consoleState.formatTimestamp"
          @reset-template="consoleState.resetTemplateForm"
          @select-template="consoleState.selectTemplate"
          @save-template="consoleState.saveTemplate"
          @delete-template="consoleState.deleteTemplate"
        />
      </section>
    </section>
  </main>
</template>
