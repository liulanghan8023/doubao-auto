import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { request } from "../api/client";
import { artifactUrl } from "../utils/artifacts";
import { formatTimestamp, outputName } from "../utils/formatters";

const PROMPT_VARIABLE_PATTERN = /【([^】]+)】/g;

export function useAutomationConsole() {
  const status = ref(null);
  const busy = ref(false);
  const feedback = ref("");
  const selectedTaskId = ref("");
  const draftMode = ref(false);
  const activeNodeId = ref("image");
  const nodes = ref([]);
  const edges = ref([
    { id: "e-create-image", source: "create", target: "image", animated: true },
    { id: "e-image-video", source: "image", target: "video", animated: true },
  ]);
  const templateEditorId = ref("");
  const taskForm = reactive({
    name: "",
    templateId: "",
    imagePrompt: "",
    videoPrompt: "",
    videoReferenceImagePath: "",
    videoUseImageChat: true,
    referenceImage: null,
    selectedFileName: "",
    referenceImagePath: "",
  });
  const templateForm = reactive({
    name: "",
    imagePrompt: "",
    videoPrompt: "",
  });
  const taskTemplatePromptSource = reactive({
    imagePrompt: "",
    videoPrompt: "",
  });
  const taskVariableInputs = reactive({});

  let timerId = null;

  const tasks = computed(() => status.value?.tasks || []);
  const templates = computed(() => status.value?.templates || []);
  const activeTask = computed(
    () => (draftMode.value ? null : tasks.value.find(task => task.id === selectedTaskId.value) || null),
  );
  const editingTemplate = computed(
    () => templates.value.find(template => template.id === templateEditorId.value) || null,
  );
  const activeTaskMeta = computed(() => {
    if (!activeTask.value) {
      return "新任务草稿";
    }
    const updatedAt = formatTimestamp(activeTask.value.updated_at);
    return updatedAt ? `最近更新 ${updatedAt}` : "已选任务";
  });
  const formModeLabel = computed(() => (activeTask.value ? "编辑任务" : "新建任务"));
  const templateEditorModeLabel = computed(() => (editingTemplate.value ? "编辑模板" : "新建模板"));
  const latestImageOutput = computed(() => activeTask.value?.last_outputs?.[0] || "");
  const taskPromptVariables = computed(() => {
    const names = new Set();
    for (const name of extractPromptVariables(taskTemplatePromptSource.imagePrompt)) {
      names.add(name);
    }
    for (const name of extractPromptVariables(taskTemplatePromptSource.videoPrompt)) {
      names.add(name);
    }
    return Array.from(names);
  });
  const selectedVideoReferenceImage = computed(() => {
    const selectedPath = taskForm.videoReferenceImagePath;
    if (selectedPath && activeTask.value?.last_outputs?.includes(selectedPath)) {
      return selectedPath;
    }
    if (selectedPath && draftMode.value) {
      return selectedPath;
    }
    return latestImageOutput.value;
  });
  function getTemplateName(templateId) {
    return templates.value.find(template => template.id === templateId)?.name || "";
  }

  function hasPromptVariables(text) {
    return /【[^】]+】/.test(text || "");
  }

  function extractPromptVariables(text) {
    return Array.from((text || "").matchAll(PROMPT_VARIABLE_PATTERN), match => match[1].trim()).filter(Boolean);
  }

  function renderPromptWithVariables(text) {
    return (text || "").replace(PROMPT_VARIABLE_PATTERN, (placeholder, name) => {
      const value = taskVariableInputs[name.trim()];
      return value?.length ? value : placeholder;
    });
  }

  function clearTaskVariableInputs() {
    for (const key of Object.keys(taskVariableInputs)) {
      delete taskVariableInputs[key];
    }
  }

  function syncTaskVariableInputs(prompts, values = {}) {
    const names = new Set([
      ...extractPromptVariables(prompts.imagePrompt),
      ...extractPromptVariables(prompts.videoPrompt),
    ]);
    clearTaskVariableInputs();
    for (const name of names) {
      taskVariableInputs[name] = values[name] || "";
    }
  }

  function applyTaskPromptVariables() {
    if (!taskTemplatePromptSource.imagePrompt && !taskTemplatePromptSource.videoPrompt) {
      return;
    }
    taskForm.imagePrompt = renderPromptWithVariables(taskTemplatePromptSource.imagePrompt);
    taskForm.videoPrompt = renderPromptWithVariables(taskTemplatePromptSource.videoPrompt);
  }

  function initializeTaskTemplateBinding(template) {
    if (!template) {
      taskTemplatePromptSource.imagePrompt = "";
      taskTemplatePromptSource.videoPrompt = "";
      clearTaskVariableInputs();
      return;
    }
    taskTemplatePromptSource.imagePrompt = template.image_prompt || "";
    taskTemplatePromptSource.videoPrompt = template.video_prompt || "";
    syncTaskVariableInputs(taskTemplatePromptSource);
    applyTaskPromptVariables();
  }

  function defaultTemplate(snapshot) {
    return snapshot?.templates?.[0] || null;
  }

  function syncTaskDraftFromDefaults(snapshot) {
    const template = defaultTemplate(snapshot);
    taskForm.name = `任务 ${snapshot.tasks.length + 1}`;
    taskForm.templateId = template?.id || "";
    if (template) {
      initializeTaskTemplateBinding(template);
    } else {
      initializeTaskTemplateBinding(null);
      taskForm.imagePrompt = snapshot.task_defaults.image_prompt;
      taskForm.videoPrompt = snapshot.task_defaults.video_prompt;
    }
    taskForm.videoReferenceImagePath = "";
    taskForm.videoUseImageChat = true;
    taskForm.referenceImage = null;
    taskForm.selectedFileName = "";
    taskForm.referenceImagePath = snapshot.task_defaults.reference_image_path;
  }

  function loadTaskIntoForm(task) {
    if (!task) {
      if (status.value) {
        syncTaskDraftFromDefaults(status.value);
      }
      return;
    }
    taskForm.name = task.name;
    taskForm.templateId = task.template_id || "";
    taskForm.imagePrompt = task.image_prompt;
    taskForm.videoPrompt = task.video_prompt || status.value?.task_defaults?.video_prompt || "";
    const template = templates.value.find(item => item.id === task.template_id);
    if (template) {
      taskTemplatePromptSource.imagePrompt = template.image_prompt || "";
      taskTemplatePromptSource.videoPrompt = template.video_prompt || "";
      syncTaskVariableInputs(taskTemplatePromptSource);
    } else {
      initializeTaskTemplateBinding(null);
    }
    taskForm.videoReferenceImagePath = task.video_reference_image_path || task.last_outputs?.[0] || "";
    taskForm.videoUseImageChat = task.video_use_image_chat !== false;
    taskForm.referenceImage = null;
    taskForm.selectedFileName = "";
    taskForm.referenceImagePath = task.reference_image_path;
  }

  function resetTemplateForm() {
    templateEditorId.value = "";
    templateForm.name = "";
    templateForm.imagePrompt = status.value?.task_defaults?.image_prompt || "";
    templateForm.videoPrompt = status.value?.task_defaults?.video_prompt || "";
  }

  function loadTemplateIntoForm(template) {
    if (!template) {
      resetTemplateForm();
      return;
    }
    templateEditorId.value = template.id;
    templateForm.name = template.name;
    templateForm.imagePrompt = template.image_prompt;
    templateForm.videoPrompt = template.video_prompt;
  }

  function applyTemplateToTask(templateId) {
    taskForm.templateId = templateId;
    const template = templates.value.find(item => item.id === templateId);
    if (!template) {
      initializeTaskTemplateBinding(null);
      return;
    }
    initializeTaskTemplateBinding(template);
  }

  function updateTaskVariable(name, value) {
    taskVariableInputs[name] = value;
    applyTaskPromptVariables();
  }

  function taskFormImageHint() {
    if (taskForm.selectedFileName) {
      return taskForm.selectedFileName;
    }
    if (taskForm.referenceImagePath) {
      return `当前使用 ${taskForm.referenceImagePath}`;
    }
    return "请手动选择参考图";
  }

  function rebuildFlow() {
    const taskName = activeTask.value?.name || taskForm.name || "未选择任务";
    nodes.value = [
      {
        id: "create",
        type: "input",
        position: { x: 40, y: 150 },
        data: { label: `1. 任务配置\n${taskName}` },
        class: "flow-summary-node",
      },
      {
        id: "image",
        position: { x: 360, y: 110 },
        data: { label: `2. 图片生成\n${activeTask.value ? "可执行" : "待保存任务"}` },
        class: "flow-summary-node flow-summary-node-active",
      },
      {
        id: "video",
        type: "output",
        position: { x: 680, y: 150 },
        data: { label: `3. 视频生成\n${latestImageOutput.value ? "可提交" : "等待图片"}` },
        class: "flow-summary-node flow-summary-node-muted",
      },
    ];
  }

  async function refreshStatus() {
    const payload = await request("/api/status");
    const firstLoad = status.value === null;
    status.value = payload;

    if (firstLoad) {
      syncTaskDraftFromDefaults(payload);
      resetTemplateForm();
    }
    if (!draftMode.value && !selectedTaskId.value && payload.tasks.length) {
      selectedTaskId.value = payload.tasks[0].id;
    }
    if (
      !draftMode.value &&
      selectedTaskId.value &&
      !payload.tasks.find(task => task.id === selectedTaskId.value)
    ) {
      selectedTaskId.value = payload.tasks[0]?.id || "";
    }
    if (firstLoad) {
      loadTaskIntoForm(activeTask.value);
    }
    rebuildFlow();
  }

  async function invokeLogin() {
    busy.value = true;
    feedback.value = "";
    try {
      const payload = await request("/api/login", { method: "POST" });
      feedback.value = payload.message;
      await refreshStatus();
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  async function persistTask() {
    const formData = new FormData();
    formData.set("name", taskForm.name);
    formData.set("template_id", taskForm.templateId || "");
    formData.set("image_prompt", taskForm.imagePrompt);
    formData.set("video_prompt", taskForm.videoPrompt || status.value?.task_defaults?.video_prompt || "");
    formData.set("video_reference_image_path", taskForm.videoReferenceImagePath || "");
    formData.set("video_use_image_chat", taskForm.videoUseImageChat ? "true" : "false");
    if (taskForm.referenceImage) {
      formData.set("reference_image", taskForm.referenceImage);
    }
    const endpoint = activeTask.value ? `/api/tasks/${activeTask.value.id}` : "/api/tasks";
    const method = activeTask.value ? "PUT" : "POST";
    const payload = await request(endpoint, { method, body: formData });
    await refreshStatus();
    draftMode.value = false;
    selectedTaskId.value = payload.task.id;
    loadTaskIntoForm(payload.task);
    rebuildFlow();
    return payload.task;
  }

  async function executeTaskFlow() {
    busy.value = true;
    feedback.value = "";
    try {
      if (hasPromptVariables(taskForm.imagePrompt)) {
        throw new Error("图片提示词中仍包含【变量】占位符，请先手动修改后再提交生成。");
      }
      const savedTask = await persistTask();
      const formData = new FormData();
      formData.set("task_id", savedTask.id);
      formData.set("image_prompt", savedTask.image_prompt);
      const payload = await request("/api/run-once", { method: "POST", body: formData });
      feedback.value = payload.message;
      await refreshStatus();
      selectedTaskId.value = payload.task.id;
      loadTaskIntoForm(payload.task);
      activeNodeId.value = "image";
      rebuildFlow();
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  async function submitVideoTask() {
    busy.value = true;
    feedback.value = "";
    try {
      if (hasPromptVariables(taskForm.videoPrompt)) {
        throw new Error("视频提示词中仍包含【变量】占位符，请先手动修改后再提交生成。");
      }
      const savedTask = await persistTask();
      const formData = new FormData();
      formData.set("task_id", savedTask.id);
      const payload = await request("/api/run-video", { method: "POST", body: formData });
      feedback.value = payload.message;
      await refreshStatus();
      selectedTaskId.value = payload.task.id;
      loadTaskIntoForm(payload.task);
      activeNodeId.value = "video";
      rebuildFlow();
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  async function deleteTask(taskId) {
    const task = tasks.value.find(item => item.id === taskId);
    if (!task || !window.confirm(`删除任务“${task.name}”及其关联图片文件？`)) {
      return;
    }
    busy.value = true;
    feedback.value = "";
    try {
      const payload = await request(`/api/tasks/${taskId}`, { method: "DELETE" });
      const wasActive = selectedTaskId.value === taskId;
      await refreshStatus();
      if (!tasks.value.length) {
        draftMode.value = true;
        selectedTaskId.value = "";
        syncTaskDraftFromDefaults(status.value);
      } else if (wasActive) {
        draftMode.value = false;
        selectedTaskId.value = tasks.value[0].id;
        loadTaskIntoForm(activeTask.value);
      }
      activeNodeId.value = "create";
      rebuildFlow();
      feedback.value = payload.message;
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  async function saveTemplate() {
    busy.value = true;
    feedback.value = "";
    try {
      const endpoint = templateEditorId.value ? `/api/templates/${templateEditorId.value}` : "/api/templates";
      const method = templateEditorId.value ? "PUT" : "POST";
      const payload = await request(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: templateForm.name,
          image_prompt: templateForm.imagePrompt,
          video_prompt: templateForm.videoPrompt,
        }),
      });
      await refreshStatus();
      loadTemplateIntoForm(payload.template);
      if (taskForm.templateId === payload.template.id) {
        applyTemplateToTask(payload.template.id);
      }
      feedback.value = payload.message;
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  async function deleteTemplate(templateId) {
    const template = templates.value.find(item => item.id === templateId);
    if (!template || !window.confirm(`删除模板“${template.name}”？`)) {
      return;
    }
    busy.value = true;
    feedback.value = "";
    try {
      const payload = await request(`/api/templates/${templateId}`, { method: "DELETE" });
      await refreshStatus();
      if (templateEditorId.value === templateId) {
        resetTemplateForm();
      }
      if (taskForm.templateId === templateId) {
        const fallbackTemplate = defaultTemplate(status.value);
        taskForm.templateId = fallbackTemplate?.id || "";
        if (draftMode.value && fallbackTemplate) {
          initializeTaskTemplateBinding(fallbackTemplate);
        }
      }
      if (!draftMode.value && activeTask.value) {
        loadTaskIntoForm(activeTask.value);
      }
      rebuildFlow();
      feedback.value = payload.message;
    } catch (error) {
      feedback.value = error instanceof Error ? error.message : "Unknown error";
    } finally {
      busy.value = false;
    }
  }

  function resetDraft() {
    if (!status.value) {
      return;
    }
    draftMode.value = true;
    selectedTaskId.value = "";
    syncTaskDraftFromDefaults(status.value);
    activeNodeId.value = "create";
    feedback.value = "已切换到新任务草稿。";
    rebuildFlow();
  }

  function selectTask(taskId) {
    draftMode.value = false;
    selectedTaskId.value = taskId;
    loadTaskIntoForm(tasks.value.find(task => task.id === taskId) || null);
    activeNodeId.value = "create";
    rebuildFlow();
  }

  function selectTemplate(templateId) {
    loadTemplateIntoForm(templates.value.find(template => template.id === templateId) || null);
  }

  function onTaskFileChange(event) {
    const [file] = event.target.files || [];
    taskForm.referenceImage = file || null;
    taskForm.selectedFileName = file ? file.name : "";
  }

  function onNodeClick(event) {
    activeNodeId.value = event.node.id;
  }

  function selectVideoReferenceImage(path) {
    taskForm.videoReferenceImagePath = path;
  }

  onMounted(async () => {
    await refreshStatus();
    if (!tasks.value.length) {
      draftMode.value = true;
      syncTaskDraftFromDefaults(status.value);
    }
    timerId = window.setInterval(async () => {
      await refreshStatus();
    }, 3000);
  });

  onUnmounted(() => {
    if (timerId !== null) {
      window.clearInterval(timerId);
    }
  });

  return {
    status,
    busy,
    feedback,
    selectedTaskId,
    draftMode,
    activeNodeId,
    nodes,
    edges,
    taskForm,
    templateForm,
    templateEditorId,
    tasks,
    templates,
    activeTask,
    activeTaskMeta,
    formModeLabel,
    templateEditorModeLabel,
    latestImageOutput,
    selectedVideoReferenceImage,
    formatTimestamp,
    artifactUrl,
    outputName,
    getTemplateName,
    taskFormImageHint,
    taskPromptVariables,
    taskVariableInputs,
    refreshStatus,
    invokeLogin,
    executeTaskFlow,
    submitVideoTask,
    deleteTask,
    resetDraft,
    selectTask,
    onTaskFileChange,
    onNodeClick,
    selectVideoReferenceImage,
    applyTemplateToTask,
    updateTaskVariable,
    selectTemplate,
    saveTemplate,
    deleteTemplate,
    resetTemplateForm,
  };
}
