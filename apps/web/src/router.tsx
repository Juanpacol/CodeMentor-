import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { RequireAuth, RequireRole } from './components/layout/RequireAuth'
import { AcademicPeriodsPage } from './features/admin/AcademicPeriodsPage'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { ResetConfirmPage } from './features/auth/ResetConfirmPage'
import { ResetRequestPage } from './features/auth/ResetRequestPage'
import { LandingPage } from './features/landing/LandingPage'
import { ProgressPage } from './features/student/ProgressPage'
import { StudentDashboardPage } from './features/student/StudentDashboardPage'
import { ApprovalsInboxPage } from './features/teacher/ApprovalsInboxPage'
import { EvaluationBuilderPage } from './features/teacher/EvaluationBuilderPage'
import { ExerciseBankPage } from './features/teacher/ExerciseBankPage'
import { TeacherDashboardPage } from './features/teacher/TeacherDashboardPage'

export const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/registro', element: <RegisterPage /> },
  { path: '/recuperar', element: <ResetRequestPage /> },
  { path: '/recuperar/confirmar', element: <ResetConfirmPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            element: <RequireRole roles={['student']} />,
            children: [
              { path: '/app', element: <StudentDashboardPage /> },
              { path: '/app/progreso', element: <ProgressPage /> },
            ],
          },
          {
            element: <RequireRole roles={['teacher']} />,
            children: [
              { path: '/app/docente', element: <TeacherDashboardPage /> },
              { path: '/app/docente/ejercicios', element: <ExerciseBankPage /> },
              { path: '/app/docente/evaluaciones/nueva', element: <EvaluationBuilderPage /> },
              { path: '/app/docente/bandeja', element: <ApprovalsInboxPage /> },
              { path: '/app/admin/periodos', element: <AcademicPeriodsPage /> },
            ],
          },
        ],
      },
    ],
  },
])
