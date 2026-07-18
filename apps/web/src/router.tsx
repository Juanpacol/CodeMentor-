import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/layout/AppShell'
import { RequireAuth, RequireRole } from './components/layout/RequireAuth'
import { AcademicPeriodsPage } from './features/admin/AcademicPeriodsPage'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { ResetConfirmPage } from './features/auth/ResetConfirmPage'
import { ResetRequestPage } from './features/auth/ResetRequestPage'
import { LandingPage } from './features/landing/LandingPage'
import { EvaluationResultPage } from './features/student/EvaluationResultPage'
import { GroupDetailPage } from './features/student/GroupDetailPage'
import { PracticePage } from './features/student/PracticePage'
import { ProgressPage } from './features/student/ProgressPage'
import { StudentDashboardPage } from './features/student/StudentDashboardPage'
import { TakeEvaluationPage } from './features/student/TakeEvaluationPage'
import { ActivityLogPage } from './features/teacher/ActivityLogPage'
import { ApprovalsInboxPage } from './features/teacher/ApprovalsInboxPage'
import { EvaluationBuilderPage } from './features/teacher/EvaluationBuilderPage'
import { EvaluationManagePage } from './features/teacher/EvaluationManagePage'
import { ExerciseBankPage } from './features/teacher/ExerciseBankPage'
import { TeacherDashboardPage } from './features/teacher/TeacherDashboardPage'
import { TeacherGroupDetailPage } from './features/teacher/TeacherGroupDetailPage'

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
              { path: '/app/grupos/:groupId', element: <GroupDetailPage /> },
              { path: '/app/grupos/:groupId/practicar', element: <PracticePage /> },
              { path: '/app/evaluaciones/:evaluationId', element: <TakeEvaluationPage /> },
              {
                path: '/app/evaluaciones/:evaluationId/resultado',
                element: <EvaluationResultPage />,
              },
              { path: '/app/progreso', element: <ProgressPage /> },
            ],
          },
          {
            element: <RequireRole roles={['teacher']} />,
            children: [
              { path: '/app/docente', element: <TeacherDashboardPage /> },
              { path: '/app/docente/grupos/:groupId', element: <TeacherGroupDetailPage /> },
              { path: '/app/docente/ejercicios', element: <ExerciseBankPage /> },
              { path: '/app/docente/evaluaciones/nueva', element: <EvaluationBuilderPage /> },
              {
                path: '/app/docente/evaluaciones/:evaluationId',
                element: <EvaluationManagePage />,
              },
              { path: '/app/docente/bandeja', element: <ApprovalsInboxPage /> },
              { path: '/app/docente/actividad', element: <ActivityLogPage /> },
              { path: '/app/admin/periodos', element: <AcademicPeriodsPage /> },
            ],
          },
        ],
      },
    ],
  },
])
