// While an interruption is open, everything on the map outside its zone is blurred and faded,
// so the eye stays inside the circle. A veil sits just above the basemap with a round hole cut
// in it; pins, lines and labels are drawn above the veil and stay sharp.
import { useEffect } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'

export default function ZoneFocus({ center, km }) {
  const map = useMap()
  const lat = center?.[0]
  const lon = center?.[1]
  useEffect(() => {
    if (lat == null) return undefined
    const pane = map.getPane('focus') ?? map.createPane('focus')
    pane.style.zIndex = 300                                     // above the basemap (200), under the network (350) and the pins
    pane.style.pointerEvents = 'none'
    const veil = L.DomUtil.create('div', 'zone-veil', pane)
    const place = () => {
      const size = map.getSize()
      L.DomUtil.setPosition(veil, map.containerPointToLayerPoint([0, 0]))      // the pane moves with the map; the veil stays over the view
      veil.style.width = `${size.x}px`
      veil.style.height = `${size.y}px`
      const middle = map.latLngToContainerPoint([lat, lon])
      const edge = map.latLngToContainerPoint([lat + km / 110.574, lon])
      const radius = Math.abs(middle.y - edge.y)
      const hole = `radial-gradient(circle at ${middle.x}px ${middle.y}px, transparent ${radius}px, #000 ${radius + 1}px)`
      veil.style.maskImage = hole
      veil.style.webkitMaskImage = hole
    }
    place()
    const events = 'move zoom zoomend moveend resize viewreset'
    map.on(events, place)
    return () => { map.off(events, place); veil.remove() }
  }, [map, lat, lon, km])
  return null
}
