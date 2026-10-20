import { useState } from 'react'
import ProtectedImage from './ProtectedImage'
import { Dialog, EmptyState } from '../design-system/components'
import { getClientProgressPhotoUrl } from '../services/clientApi'
import type { ProgressPhoto } from '../types/client'
export default function ProgressGallery({ photos }: { photos: ProgressPhoto[] }) {
  const [selected, setSelected] = useState<ProgressPhoto | null>(null)
  if (!photos.length) return <EmptyState title="A record of your progress">Add a check-in photo when you’re ready. Photos stay within your authorized workspace.</EmptyState>
  return <><div className="progress-gallery">{photos.map(photo => <figure key={photo.id}><button className="photo-button" onClick={() => setSelected(photo)} aria-label={`View progress photo from ${photo.captured_on}`}><ProtectedImage src={getClientProgressPhotoUrl(photo.blob_name)} alt={photo.caption || `Progress on ${photo.captured_on}`} loading="lazy" /></button><figcaption><strong>{new Date(`${photo.captured_on.slice(0, 10)}T12:00:00`).toLocaleDateString('en-IN')}</strong><span>{photo.timeline_type.replaceAll('_', ' ')} check-in</span>{photo.caption && <p>{photo.caption}</p>}</figcaption></figure>)}</div>
    <Dialog open={!!selected} title={selected ? `Progress · ${selected.captured_on}` : 'Progress photo'} onClose={() => setSelected(null)}>{selected && <><ProtectedImage className="photo-view" src={getClientProgressPhotoUrl(selected.blob_name)} alt={selected.caption || 'Progress photo'} /><p>{selected.caption}</p></>}</Dialog>
  </>
}
