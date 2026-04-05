export function formatTimestamp(timestamp) {
  if (!timestamp) {
    return "";
  }
  const date = new Date(Number(timestamp));
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function outputName(path) {
  return path.split("/").pop() || path;
}
