import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Button } from '../../components/ui/Button'
import { Callout } from '../../components/ui/Callout'
import { pushToast } from '../../components/ui/toastStore'
import { apiClient, ApiError, unwrap } from '../../lib/api/client'

export function MembersTab({ groupId }: { groupId: string }) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const enroll = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return unwrap(
        apiClient.POST('/groups/{group_id}/enroll-csv', {
          params: { path: { group_id: groupId } },
          // openapi-fetch pasa un FormData tal cual (no lo serializa a JSON)
          // solo si ya es una instancia de FormData — el tipo generado
          // espera { file: string } porque OpenAPI no distingue un campo
          // binario de uno de texto en multipart/form-data.
          body: formData as unknown as { file: string },
        }),
      )
    },
    onSuccess: (data) => {
      setError(null)
      pushToast(`${data.enrolled} estudiante(s) matriculados`, 'success')
    },
    onError: (err) => setError(err instanceof ApiError ? err.detail : 'No se pudo procesar el archivo'),
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) enroll.mutate(file)
    e.target.value = ''
  }

  function copy(text: string) {
    void navigator.clipboard.writeText(text)
    pushToast('Copiado', 'success')
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleFileChange}
        />
        <Button
          variant="secondary"
          disabled={enroll.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {enroll.isPending ? 'Procesando...' : 'Cargar CSV de estudiantes'}
        </Button>
        <span className="text-xs text-ink-secondary">Columnas: email, full_name, student_code</span>
      </div>

      {error && (
        <Callout tone="error" className="mb-4">
          {error}
        </Callout>
      )}

      {enroll.data && enroll.data.created_accounts.length > 0 && (
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-semibold text-ink">Cuentas creadas</h3>
          <div className="flex flex-col gap-1.5">
            {enroll.data.created_accounts.map((account) => (
              <div
                key={account.email}
                className="flex items-center justify-between rounded-btn border border-hairline-strong px-3 py-2 text-sm"
              >
                <span className="text-ink">{account.email}</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-ink-secondary">{account.temporary_password}</span>
                  <button
                    onClick={() => copy(account.temporary_password)}
                    className="text-xs text-primary hover:text-primary-hover"
                  >
                    copiar
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {enroll.data && enroll.data.errors.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-ink">Filas con error</h3>
          <div className="flex flex-col gap-1.5">
            {enroll.data.errors.map((rowError) => (
              <Callout key={rowError.row_number} tone="warning">
                Fila {rowError.row_number}: {rowError.reason}
              </Callout>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
