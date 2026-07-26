/** Fuerza abiertos todos los `<details>` (la tabla "Ver datos" de todo
 * gráfico, ítem 4) antes de imprimir, y los devuelve a su estado previo
 * después — no hay forma de hacer clic en un `<summary>` sobre papel, así
 * que el dato de respaldo debe verse siempre.
 *
 * Tiene que ser JS: `display: block !important` sobre los hijos de un
 * `<details>` cerrado NO revierte el colapso nativo del navegador
 * (verificado empíricamente en Chromium — el contenido sigue sin pintarse
 * pese al override de CSS). El `<summary>` se sigue ocultando por CSS
 * (theme.css, `@media print`), ya que eso sí es un `display: none` normal
 * sobre un elemento siempre presente en el DOM. */
export function watchPrintDetailsExpansion(): () => void {
  let previouslyOpen: HTMLDetailsElement[] = []

  function openAll() {
    const all = Array.from(document.querySelectorAll('details'))
    previouslyOpen = all.filter((d) => d.open)
    for (const details of all) details.open = true
  }

  function restore() {
    for (const details of document.querySelectorAll('details')) {
      details.open = previouslyOpen.includes(details)
    }
    previouslyOpen = []
  }

  window.addEventListener('beforeprint', openAll)
  window.addEventListener('afterprint', restore)
  return () => {
    window.removeEventListener('beforeprint', openAll)
    window.removeEventListener('afterprint', restore)
  }
}
