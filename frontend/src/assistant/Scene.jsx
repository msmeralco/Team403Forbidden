// Liwa in 3D. Built from primitive shapes in code: no model, texture or font files.
// One canvas, one animation loop, 11 meshes.
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { RoundedBox } from '@react-three/drei/core/RoundedBox'

const ORANGE = '#F47B20'
const DARK = '#DD6A12'
const VISOR = '#1F2328'
const GLOW = '#FFB37A'
const STATES = ['listening', 'thinking', 'speaking', 'alert', 'success']
const EYE = [0.14, 0.12, 0.38]

function boltGeometry() {
  const s = new THREE.Shape()
  const pts = [[0.1, 0.5], [-0.26, -0.06], [-0.02, -0.06], [-0.12, -0.5], [0.26, 0.1], [0.02, 0.1]]
  s.moveTo(...pts[0])
  pts.slice(1).forEach((p) => s.lineTo(...p))
  s.closePath()
  return new THREE.ShapeGeometry(s)
}

// Where the pointer is relative to the middle of the canvas, roughly -1 to 1.
function usePointer() {
  const gl = useThree((s) => s.gl)
  const pointer = useRef({ x: 0, y: 0 })
  useEffect(() => {
    const move = (e) => {
      const r = gl.domElement.getBoundingClientRect()
      pointer.current.x = THREE.MathUtils.clamp((e.clientX - (r.left + r.width / 2)) / 500, -1, 1)
      pointer.current.y = THREE.MathUtils.clamp(-(e.clientY - (r.top + r.height / 2)) / 400, -1, 1)
    }
    window.addEventListener('pointermove', move, { passive: true })
    return () => window.removeEventListener('pointermove', move)
  }, [gl])
  return pointer
}

function Liwa({ state, still }) {
  const invalidate = useThree((s) => s.invalidate)
  const pointer = usePointer()
  const bolt = useMemo(boltGeometry, [])
  const mat = useMemo(() => ({
    body: new THREE.MeshStandardMaterial({ color: ORANGE, roughness: 0.42, metalness: 0.05 }),
    dark: new THREE.MeshStandardMaterial({ color: DARK, roughness: 0.5, metalness: 0.05 }),
    visor: new THREE.MeshStandardMaterial({ color: VISOR, roughness: 0.16, metalness: 0.35 }),
    eye: new THREE.MeshBasicMaterial({ color: GLOW }),
    shadow: new THREE.MeshBasicMaterial({ color: '#000000', transparent: true, opacity: 0.16, depthWrite: false }),
    tip: new THREE.MeshStandardMaterial({ color: GLOW, emissive: GLOW, emissiveIntensity: 0.9, roughness: 0.3 }),
    bolt: new THREE.MeshStandardMaterial({ color: '#FFFFFF', emissive: '#FFFFFF', emissiveIntensity: 0.12, roughness: 0.4, side: THREE.DoubleSide }),
  }), [])
  useEffect(() => () => {
    bolt.dispose()
    Object.values(mat).forEach((m) => m.dispose())
  }, [bolt, mat])

  const root = useRef(null)
  const eyes = useRef([])
  const hands = useRef([])
  const tip = useRef(null)
  const shadow = useRef(null)
  const anim = useRef({ w: Object.fromEntries(STATES.map((s) => [s, 0])), spin: 0, blinkAt: 2, blink: 0 })

  useEffect(() => { invalidate() }, [state, still, invalidate])

  // The one animation loop: blends toward the current state over about 300 ms and moves the parts.
  useFrame(({ clock }, dt) => {
    if (!root.current) return
    const a = anim.current
    const t = still ? 0 : clock.elapsedTime
    const k = still ? 1 : 1 - Math.exp(-Math.min(dt, 0.05) / 0.09)
    STATES.forEach((s) => { a.w[s] += ((state === s ? 1 : 0) - a.w[s]) * k })
    const { listening, thinking, speaking, alert, success } = a.w
    const calm = 1 - Math.max(thinking, speaking, alert, success)

    if (state === 'success') a.spin = Math.min(1, a.spin + (still ? 1 : dt / 0.9))     // one full spin, then settle
    else a.spin = 0
    const spin = still ? 0 : (1 - (1 - a.spin) ** 3) * Math.PI * 2

    const lift = Math.sin(t * 1.6) * 0.05 * calm + Math.abs(Math.sin(t * 11)) * 0.2 * alert
      + Math.abs(Math.sin(t * 6)) * 0.1 * success + Math.abs(Math.sin(t * 7)) * 0.045 * speaking
    root.current.position.set(0, lift, 0)
    root.current.scale.setScalar(1 + Math.sin(t * 14) * 0.03 * speaking)
    root.current.rotation.set(0.2 * listening + 0.05 * speaking, spin + pointer.current.x * 0.14 * calm, Math.sin(t * 0.9) * 0.04 * calm + 0.17 * thinking)

    // eyes: blink when calm, bouncing dots when thinking, a two-bar waveform when speaking
    if (!still && clock.elapsedTime > a.blinkAt) { a.blink = 0.14; a.blinkAt = clock.elapsedTime + 3 + Math.random() * 3 }
    a.blink = Math.max(0, a.blink - dt)
    const lid = a.blink > 0 ? 0.12 : 1
    eyes.current.forEach((eye, e) => {
      if (!eye) return
      const side = e === 0 ? -1 : 1
      const bar = still ? 1.5 : 0.5 + Math.abs(Math.sin(t * 10 + e * 1.9)) * 1.9
      eye.position.set(
        side * EYE[0] + pointer.current.x * 0.035 * calm + Math.sin(t * 3) * 0.03 * thinking,
        EYE[1] + pointer.current.y * 0.025 * calm + Math.abs(Math.sin(t * 5 + e * 1.4)) * 0.07 * thinking,
        EYE[2],
      )
      eye.scale.set(1 - 0.4 * thinking - 0.35 * speaking, (1 - 0.4 * thinking) * (1 - speaking) * lid * (1 + 0.25 * listening) + bar * speaking, 1)
    })

    // the antenna tip pulses while listening and flashes on an alert; the emblem flashes with it
    const flash = alert * (still ? 1 : Math.sin(t * 20) > 0 ? 1 : 0)
    mat.tip.emissiveIntensity = 0.9 + listening * (0.9 + Math.sin(t * 8) * 0.8) + flash * 2.4 + success * 0.8
    mat.bolt.emissiveIntensity = 0.12 + flash * 1.1 + success * 0.4
    if (tip.current) tip.current.scale.setScalar(1 + listening * 0.25 * (1 + Math.sin(t * 8)) + flash * 0.35)

    // hands float, wave while speaking and go up on success
    hands.current.forEach((hand, h) => {
      if (!hand) return
      const side = h === 0 ? -1 : 1
      hand.position.set(
        side * (0.5 + 0.06 * success),
        -0.45 + Math.sin(t * 1.9 + h * 2) * 0.035 * calm + 0.95 * success + Math.sin(t * 9 + h) * 0.07 * speaking + 0.12 * speaking,
        0.1,
      )
    })
    if (shadow.current) shadow.current.scale.setScalar(Math.max(0.55, 1 - lift * 1.4))
  })

  return (
    <>
      <ambientLight intensity={0.85} />
      <hemisphereLight args={['#ffffff', '#ffd9b8', 0.7]} />
      <directionalLight position={[2.5, 4, 5]} intensity={1.5} />
      <directionalLight position={[-3, 2, -2]} intensity={0.6} color="#ffe2c8" />

      <mesh ref={shadow} position={[0, -1.02, 0]} rotation={[-Math.PI / 2, 0, 0]} material={mat.shadow}><circleGeometry args={[0.42, 28]} /></mesh>
      <group ref={root}>
        <mesh position={[0, -0.5, 0]} scale={[1, 1.05, 0.92]} material={mat.body}><sphereGeometry args={[0.36, 24, 20]} /></mesh>
        <RoundedBox args={[0.82, 0.62, 0.66]} radius={0.24} smoothness={4} position={[0, 0.12, 0]} material={mat.body} />
        <RoundedBox args={[0.6, 0.3, 0.14]} radius={0.07} smoothness={3} position={[0, 0.12, 0.3]} material={mat.visor} />
        <mesh ref={(n) => { eyes.current[0] = n }} material={mat.eye}><sphereGeometry args={[0.05, 12, 10]} /></mesh>
        <mesh ref={(n) => { eyes.current[1] = n }} material={mat.eye}><sphereGeometry args={[0.05, 12, 10]} /></mesh>
        <mesh position={[0, 0.53, 0]} material={mat.dark}><cylinderGeometry args={[0.018, 0.018, 0.22, 8]} /></mesh>
        <mesh ref={tip} position={[0, 0.67, 0]} material={mat.tip}><sphereGeometry args={[0.065, 14, 12]} /></mesh>
        <mesh ref={(n) => { hands.current[0] = n }} material={mat.dark}><sphereGeometry args={[0.1, 14, 12]} /></mesh>
        <mesh ref={(n) => { hands.current[1] = n }} material={mat.dark}><sphereGeometry args={[0.1, 14, 12]} /></mesh>
        <mesh geometry={bolt} position={[0, -0.5, 0.335]} scale={0.2} material={mat.bolt} />
      </group>
    </>
  )
}

// state: idle | listening | thinking | speaking | alert | success
export default function Scene({ state, still, paused }) {
  return (
    <Canvas flat dpr={[1, 2]} gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
      camera={{ fov: 20, position: [0, -0.12, 8.2] }}
      frameloop={paused ? 'never' : still ? 'demand' : 'always'}
      style={{ background: 'transparent', pointerEvents: 'none' }}>
      <Liwa state={state} still={still} />
    </Canvas>
  )
}
