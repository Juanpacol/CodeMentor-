import { lazy } from 'react'

// Ítem 12: cada página se separa en su propio chunk — antes todas (incluida
// @uiw/react-codemirror + @codemirror/*, la dependencia más pesada del
// bundle) se cargaban de una sola vez en /login. Exports nombrados en cada
// página → hay que envolver el import en `.then(m => ({ default: m.X }))`
// porque `lazy()` exige un módulo con `default`.
//
// Vive en su propio archivo (no en router.tsx) porque mezclar estos
// componentes con el export no-componente `router` confunde la heurística
// de Fast Refresh de oxlint (rompe el HMR en dev, cae a recarga completa).

export const LandingPage = lazy(() =>
  import('./features/landing/LandingPage').then((m) => ({ default: m.LandingPage })),
)
export const LoginPage = lazy(() =>
  import('./features/auth/LoginPage').then((m) => ({ default: m.LoginPage })),
)
export const RegisterPage = lazy(() =>
  import('./features/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })),
)
export const ResetRequestPage = lazy(() =>
  import('./features/auth/ResetRequestPage').then((m) => ({ default: m.ResetRequestPage })),
)
export const ResetConfirmPage = lazy(() =>
  import('./features/auth/ResetConfirmPage').then((m) => ({ default: m.ResetConfirmPage })),
)
export const NotFoundPage = lazy(() =>
  import('./features/NotFoundPage').then((m) => ({ default: m.NotFoundPage })),
)

export const StudentDashboardPage = lazy(() =>
  import('./features/student/StudentDashboardPage').then((m) => ({ default: m.StudentDashboardPage })),
)
export const GroupDetailPage = lazy(() =>
  import('./features/student/GroupDetailPage').then((m) => ({ default: m.GroupDetailPage })),
)
export const PracticePage = lazy(() =>
  import('./features/student/PracticePage').then((m) => ({ default: m.PracticePage })),
)
export const TakeEvaluationPage = lazy(() =>
  import('./features/student/TakeEvaluationPage').then((m) => ({ default: m.TakeEvaluationPage })),
)
export const EvaluationResultPage = lazy(() =>
  import('./features/student/EvaluationResultPage').then((m) => ({ default: m.EvaluationResultPage })),
)
export const ProgressPage = lazy(() =>
  import('./features/student/ProgressPage').then((m) => ({ default: m.ProgressPage })),
)

export const TeacherDashboardPage = lazy(() =>
  import('./features/teacher/TeacherDashboardPage').then((m) => ({ default: m.TeacherDashboardPage })),
)
export const TeacherGroupDetailPage = lazy(() =>
  import('./features/teacher/TeacherGroupDetailPage').then((m) => ({ default: m.TeacherGroupDetailPage })),
)
export const ExerciseBankPage = lazy(() =>
  import('./features/teacher/ExerciseBankPage').then((m) => ({ default: m.ExerciseBankPage })),
)
export const EvaluationBuilderPage = lazy(() =>
  import('./features/teacher/EvaluationBuilderPage').then((m) => ({ default: m.EvaluationBuilderPage })),
)
export const EvaluationManagePage = lazy(() =>
  import('./features/teacher/EvaluationManagePage').then((m) => ({ default: m.EvaluationManagePage })),
)
export const ApprovalsInboxPage = lazy(() =>
  import('./features/teacher/ApprovalsInboxPage').then((m) => ({ default: m.ApprovalsInboxPage })),
)
export const ActivityLogPage = lazy(() =>
  import('./features/teacher/ActivityLogPage').then((m) => ({ default: m.ActivityLogPage })),
)
export const AcademicPeriodsPage = lazy(() =>
  import('./features/admin/AcademicPeriodsPage').then((m) => ({ default: m.AcademicPeriodsPage })),
)
