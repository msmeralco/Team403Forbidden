import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/manrope'
import 'leaflet/dist/leaflet.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles.css'
import App from './App'

createRoot(document.getElementById('root')).render(<App />)
