import { useEffect, useState, type ImgHTMLAttributes } from 'react'
import { buildAuthHeaders, sessionGeneration } from '../services/session'

export default function ProtectedImage({ src, alt, ...props }: ImgHTMLAttributes<HTMLImageElement>) {
  const [object, setObject] = useState<{ source: string; url: string } | null>(null)
  useEffect(() => {
    if (!src) return
    const controller = new AbortController()
    const generation = sessionGeneration()
    let objectUrl = ''
    fetch(src, { headers: buildAuthHeaders(), signal: controller.signal, cache: 'no-store' })
      .then(response => { if (!response.ok) throw new Error('Image unavailable'); return response.blob() })
      .then(blob => {
        if (controller.signal.aborted || generation !== sessionGeneration()) return
        objectUrl = URL.createObjectURL(blob)
        setObject({ source: src, url: objectUrl })
      }).catch(() => { /* An unavailable image never falls back to a public URL. */ })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [src])
  return object && object.source === src ? <img {...props} src={object.url} alt={alt} /> : <span role="img" aria-label={alt}>Image unavailable</span>
}

