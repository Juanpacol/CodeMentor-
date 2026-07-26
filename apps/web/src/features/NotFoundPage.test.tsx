import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { NotFoundPage } from './NotFoundPage'

function renderWithRouter(initialPath: string) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <div>Inicio</div> },
      { path: '*', element: <NotFoundPage /> },
    ],
    { initialEntries: [initialPath] },
  )
  return render(<RouterProvider router={router} />)
}

describe('NotFoundPage', () => {
  it('renders for an unmatched route', () => {
    renderWithRouter('/esto-no-existe')
    expect(screen.getByText('Página no encontrada')).toBeInTheDocument()
  })

  it('navigates home when the button is clicked', async () => {
    renderWithRouter('/esto-no-existe')
    await userEvent.click(screen.getByRole('button', { name: 'Volver al inicio' }))
    expect(await screen.findByText('Inicio')).toBeInTheDocument()
  })
})
