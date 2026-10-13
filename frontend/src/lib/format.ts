export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function formatDayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short" })
}

export function formatFileType(fileType: string): string {
  return fileType.toUpperCase()
}
