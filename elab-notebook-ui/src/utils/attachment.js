

const IMAGE_EXT = /\.(?:png|jpe?g|gif|webp|bmp|svg|avif)(?:$|[?#])/i


export const isImagePath = (url) => IMAGE_EXT.test(url || '')


export const fileNameFromUrl = (url) => {
  const raw = (url || '').split('/').pop() || url || ''
  try {
    return decodeURIComponent(raw)
  } catch {
    return raw
  }
}
