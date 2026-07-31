import { createBrowserRouter } from 'react-router'

import { AppShell } from './components/layout/AppShell'
import { suspended } from './components/layout/PageFallback'
import { RequireAuth, RequireRole } from './components/layout/RequireAuth'
import { RouteErrorBoundary } from './components/layout/RouteErrorBoundary'
import {
  ActivityLogPage,
  ApprovalsInboxPage,
  EvaluationBuilderPage,
  EvaluationManagePage,
  EvaluationResultPage,
  ExerciseBankPage,
  GroupDetailPage,
  LandingPage,
  LoginPage,
  NotFoundPage,
  PendingAssignmentsPage,
  PracticePage,
  ProgressPage,
  RegisterPage,
  ResetConfirmPage,
  ResetRequestPage,
  StudentDashboardPage,
  TakeEvaluationPage,
  TeacherDashboardPage,
  TeacherGroupDetailPage,
} from './lazyPages'

export const router = createBrowserRouter([
  {
    // Ruta sin path/element propios: solo declara el errorElement que
    // createBrowserRouter usa para TODO el árbol — un error de render en
    // cualquier página (o en RequireAuth/AppShell) cae aquí en vez de dejar
    // la pantalla en blanco.
    errorElement: <RouteErrorBoundary />,
    children: [
      { path: '/', element: suspended(<LandingPage />) },
      { path: '/login', element: suspended(<LoginPage />) },
      { path: '/registro', element: suspended(<RegisterPage />) },
      { path: '/recuperar', element: suspended(<ResetRequestPage />) },
      { path: '/recuperar/confirmar', element: suspended(<ResetConfirmPage />) },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell />,
            children: [
              {
                element: <RequireRole roles={['student']} />,
                children: [
                  { path: '/app', element: suspended(<StudentDashboardPage />) },
                  { path: '/app/grupos/:groupId', element: suspended(<GroupDetailPage />) },
                  { path: '/app/grupos/:groupId/practicar', element: suspended(<PracticePage />) },
                  {
                    path: '/app/evaluaciones/:evaluationId',
                    element: suspended(<TakeEvaluationPage />),
                  },
                  {
                    path: '/app/evaluaciones/:evaluationId/resultado',
                    element: suspended(<EvaluationResultPage />),
                  },
                  { path: '/app/progreso', element: suspended(<ProgressPage />) },
                ],
              },
              {
                element: <RequireRole roles={['teacher']} />,
                children: [
                  { path: '/app/docente', element: suspended(<TeacherDashboardPage />) },
                  {
                    path: '/app/docente/grupos/:groupId',
                    element: suspended(<TeacherGroupDetailPage />),
                  },
                  { path: '/app/docente/ejercicios', element: suspended(<ExerciseBankPage />) },
                  {
                    path: '/app/docente/evaluaciones/nueva',
                    element: suspended(<EvaluationBuilderPage />),
                  },
                  {
                    path: '/app/docente/evaluaciones/:evaluationId',
                    element: suspended(<EvaluationManagePage />),
                  },
                  { path: '/app/docente/bandeja', element: suspended(<ApprovalsInboxPage />) },
                  { path: '/app/docente/actividad', element: suspended(<ActivityLogPage />) },
                  {
                    path: '/app/docente/pendientes',
                    element: suspended(<PendingAssignmentsPage />),
                  },
                ],
              },
            ],
          },
        ],
      },
      // Catch-all: cualquier URL que no matchee ninguna ruta de arriba (en
      // vez de la pantalla en blanco por defecto de react-router).
      { path: '*', element: suspended(<NotFoundPage />) },
    ],
  },
])
