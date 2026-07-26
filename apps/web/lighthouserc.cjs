// Ítem 13: gate de Lighthouse en CI. Los umbrales van con margen respecto a
// una medición REAL post-ítem-12 (lazy loading por ruta), no una aspiración:
// tras separar cada página en su propio chunk, `/`, `/login`, `/registro` y
// `/recuperar` midieron performance 0.95, accessibility/best-practices/seo
// 1.00 (Chrome headless, sin throttling de red — mismo perfil que corre en
// el runner de GitHub Actions). Los mínimos quedan varios puntos por debajo
// de lo medido para absorber el ruido normal de una corrida en CI, sin
// dejar de detectar una regresión real.
module.exports = {
  ci: {
    collect: {
      // --prefix (no `cd apps/web &&`): mismo idioma que ya usa
      // scripts/gen_openapi_client.sh para invocar npm en el subpaquete web
      // sin depender del cwd desde el que se llame a `lhci`.
      startServerCommand: 'npm --prefix apps/web run preview -- --port 4173',
      startServerReadyPattern: 'Local:',
      url: [
        'http://localhost:4173/',
        'http://localhost:4173/login',
        'http://localhost:4173/registro',
        'http://localhost:4173/recuperar',
      ],
      numberOfRuns: 1,
    },
    assert: {
      assertions: {
        'categories:performance': ['error', { minScore: 0.85 }],
        'categories:accessibility': ['error', { minScore: 0.95 }],
        'categories:best-practices': ['error', { minScore: 0.9 }],
        'categories:seo': ['error', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
}
