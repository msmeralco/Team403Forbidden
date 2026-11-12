// The crew's way in: one road route at a time, from the Meralco office to the pole that is picked.
// A dotted straight line stands in while the directions load, and stays if no road route is found.
import { useEffect, useState } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { directions } from './route'

const BLUE = '#0B57D0'

export default function RouteLayer({ from, to, onRoute }) {
  const map = useMap()
  const [found, setFound] = useState(null)          // { key, points, by }
  const key = from && to ? [...from, ...to].join(',') : null

  useEffect(() => {
    if (!key) { onRoute?.(null); return undefined }
    let alive = true
    onRoute?.('loading')
    directions(from, to).then((route) => {
      if (!alive) return
      setFound({ key, points: route?.points ?? null, by: route?.by ?? 'none' })
      onRoute?.(route?.by ?? 'none')
    })
    return () => { alive = false }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!key) return undefined
    const group = L.layerGroup().addTo(map)
    const draw = (points, weight, dash) => {
      L.polyline(points, { color: '#fff', weight: weight + 4, opacity: 0.95, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(group)
      L.polyline(points, { color: BLUE, weight, dashArray: dash, lineCap: 'round', lineJoin: 'round', interactive: false }).addTo(group)
    }
    const road = found?.key === key ? found.points : null
    if (road) {
      draw(road, 5)
      draw([from, road[0]], 3, '1 8')                           // from the office door to the road, and from the road to the pole
      draw([road[road.length - 1], to], 3, '1 8')
    } else {
      draw([from, to], 4, '1 9')
    }
    return () => { map.removeLayer(group) }
  }, [map, key, found]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}
