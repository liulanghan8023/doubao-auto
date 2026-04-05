export function artifactUrl(path) {
  return `/artifacts/${path.replace(/^runtime\//, "")}`;
}
