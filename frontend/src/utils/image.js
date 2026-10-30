// 图片压缩：上传/识别前把图片缩到最长边 1600px、JPEG 85%，减少视觉 token 与流量。
// 失败或压缩后更大时回退原图；小于 500KB 且无需缩放的小图直接跳过。
export async function compressImage(file) {
  if (!file || !file.type.startsWith('image/')) return file
  let bitmap = null
  try {
    bitmap = await createImageBitmap(file)
  } catch {
    return file
  }
  const maxSide = 1600
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  if (scale === 1 && file.size < 500 * 1024) {
    bitmap.close && bitmap.close()
    return file
  }
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
  bitmap.close && bitmap.close()
  if (!blob || blob.size >= file.size) return file
  const name = (file.name || 'photo').replace(/\.[^.]+$/, '') + '.jpg'
  return new File([blob], name, { type: 'image/jpeg' })
}
