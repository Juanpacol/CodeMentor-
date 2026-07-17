import { motion } from 'motion/react'
import { Link } from 'react-router-dom'

import { PublicNav } from '../../components/layout/PublicNav'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { useTilt } from '../../hooks/useTilt'
import { staggerContainer, staggerItem } from '../../lib/motion'

const DOTS = [
  { color: 'bg-tint-peach-fg', top: '12%', left: '8%', delay: 0 },
  { color: 'bg-tint-mint-fg', top: '22%', left: '82%', delay: 0.4 },
  { color: 'bg-tint-sky-fg', top: '68%', left: '12%', delay: 0.8 },
  { color: 'bg-tint-rose-fg', top: '78%', left: '88%', delay: 1.2 },
  { color: 'bg-tint-yellow-fg', top: '8%', left: '48%', delay: 0.6 },
]

const FEATURES = [
  {
    tint: 'lavender' as const,
    emoji: '🤖',
    title: 'Tutor con IA supervisada',
    description:
      'Pistas progresivas que nunca revelan la solución completa — siempre etiquetadas como IA, siempre bajo control docente.',
  },
  {
    tint: 'mint' as const,
    emoji: '🧪',
    title: 'Sandbox de ejecución real',
    description:
      'Python y PSeInt corren en un entorno aislado — retroalimentación inmediata en cada intento de práctica.',
  },
  {
    tint: 'sky' as const,
    emoji: '⏱️',
    title: 'Evaluaciones cronometradas',
    description: 'Alcance curricular validado por el servidor, ranking en vivo y revisión manual para respuestas abiertas.',
  },
  {
    tint: 'peach' as const,
    emoji: '🏅',
    title: 'Progreso e insignias',
    description: 'Dominio por tema y por lenguaje, con alertas de rezago para que ningún estudiante se quede atrás.',
  },
]

function FeatureCard({ feature }: { feature: (typeof FEATURES)[number] }) {
  const tilt = useTilt<HTMLDivElement>()
  return (
    <motion.div
      variants={staggerItem}
      ref={tilt.ref}
      onPointerMove={tilt.onPointerMove}
      onPointerLeave={tilt.onPointerLeave}
      style={{ transformStyle: 'preserve-3d', willChange: 'transform' }}
      className="transition-transform duration-150 ease-out"
    >
      <Card className="h-full">
        <span className="text-3xl" aria-hidden="true">
          {feature.emoji}
        </span>
        <h3 className="mt-4 text-lg font-semibold text-ink">{feature.title}</h3>
        <p className="mt-2 text-sm text-ink-secondary">{feature.description}</p>
      </Card>
    </motion.div>
  )
}

export function LandingPage() {
  return (
    <div className="min-h-screen bg-canvas">
      <div className="relative overflow-hidden bg-navy">
        <PublicNav />
        {DOTS.map((dot, i) => (
          <motion.span
            key={i}
            aria-hidden="true"
            className={`absolute size-3 rounded-full ${dot.color} opacity-70`}
            style={{ top: dot.top, left: dot.left }}
            animate={{ y: [0, -10, 0] }}
            transition={{
              duration: 3.5,
              repeat: Infinity,
              ease: 'easeInOut',
              delay: dot.delay,
            }}
          />
        ))}

        <div className="relative mx-auto max-w-3xl px-6 pb-24 pt-16 text-center md:pt-24">
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="text-4xl font-semibold tracking-tight text-white md:text-6xl"
          >
            Lógica de programación,
            <br />
            con acompañamiento de IA.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="mx-auto mt-5 max-w-xl text-lg text-white/70"
          >
            PSeInt y Python, práctica ilimitada, evaluaciones cronometradas y un tutor de IA que
            nunca da la respuesta — solo la siguiente pista.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8 flex flex-wrap items-center justify-center gap-3"
          >
            <Link to="/registro">
              <Button size="md">Crear cuenta gratis</Button>
            </Link>
            <Link to="/login">
              <Button variant="secondary" size="md" className="border-white/20 text-white hover:bg-white/10">
                Iniciar sesión
              </Button>
            </Link>
          </motion.div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="relative mx-auto max-w-4xl px-6 pb-16"
        >
          <div
            className="rounded-card border border-white/10 bg-raised p-4 shadow-[0_24px_48px_-8px_rgba(0,0,0,0.5)]"
          >
            <div className="flex gap-1.5 pb-3">
              <span className="size-2.5 rounded-full bg-error/70" />
              <span className="size-2.5 rounded-full bg-warning/70" />
              <span className="size-2.5 rounded-full bg-success/70" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2 rounded-btn bg-tint-lavender p-4">
                <p className="text-xs font-semibold text-tint-lavender-fg">✨ Tutor IA</p>
                <p className="mt-2 text-sm text-ink-secondary">
                  &ldquo;Piensa en qué instrucción repite un bloque de código varias veces...&rdquo;
                </p>
              </div>
              <div className="rounded-btn bg-tint-mint p-4">
                <p className="text-xs font-semibold text-tint-mint-fg">Práctica</p>
                <p className="mt-2 text-2xl font-semibold text-ink">92%</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <motion.div
          variants={staggerContainer}
          initial="initial"
          whileInView="animate"
          viewport={{ once: true, margin: '-80px' }}
          className="grid grid-cols-1 gap-5 sm:grid-cols-2"
        >
          {FEATURES.map((feature) => (
            <FeatureCard key={feature.title} feature={feature} />
          ))}
        </motion.div>
      </section>

      <footer className="border-t border-hairline px-6 py-10 text-center text-sm text-ink-secondary">
        Lógica&gt;_ — INEM José Félix de Restrepo
      </footer>
    </div>
  )
}
