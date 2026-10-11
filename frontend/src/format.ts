export const readable = (text: string) =>
  text.toLowerCase().replaceAll("_", " ");
export const time = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
export function navigate(view: string, id?: string) {
  window.location.hash = view + (id ? "/" + id : "");
}
