/** Fábrica central de query keys — evita strings mágicos repetidos y hace
 * explícitas las dependencias de invalidación entre queries. */
export const qk = {
  me: ['me'] as const,
  groups: {
    mine: ['groups', 'mine'] as const,
  },
  curriculum: (groupId: string) => ['curriculum', groupId] as const,
  groupEvaluations: (groupId: string) => ['group-evaluations', groupId] as const,
  languages: ['languages'] as const,
  topics: (languageId?: string) => ['topics', languageId ?? 'all'] as const,
  practice: (groupId: string) => ['practice', groupId] as const,
  progress: {
    me: ['progress', 'me'] as const,
    lagging: (groupId: string) => ['progress', 'lagging', groupId] as const,
  },
  exercises: (filters: { languageId?: string; topicId?: string } = {}) =>
    ['exercises', filters.languageId ?? 'all', filters.topicId ?? 'all'] as const,
  evaluation: {
    take: (id: string) => ['evaluation', 'take', id] as const,
    result: (id: string) => ['evaluation', 'result', id] as const,
    ranking: (id: string) => ['evaluation', 'ranking', id] as const,
    answers: (id: string) => ['evaluation', 'answers', id] as const,
    manualReview: (id: string) => ['evaluation', 'manual-review', id] as const,
    integrityAlerts: (id: string) => ['evaluation', 'integrity-alerts', id] as const,
  },
  ai: {
    tutorHistory: (groupId: string, exerciseId: string, studentId?: string) =>
      ['ai', 'tutor-history', groupId, exerciseId, studentId ?? 'self'] as const,
    agentConfig: (groupId: string) => ['ai', 'agent-config', groupId] as const,
    pendingApprovals: ['ai', 'pending-approvals'] as const,
  },
  reports: {
    job: (jobId: string) => ['reports', jobId] as const,
    gradebook: (groupId: string) => ['reports', 'gradebook', groupId] as const,
  },
  academicPeriods: ['academic-periods'] as const,
  observability: {
    errors: (filters: { statusCode?: number; path?: string; page: number }) =>
      ['observability', 'errors', filters.statusCode ?? 'all', filters.path ?? '', filters.page] as const,
    audit: (filters: { action?: string; page: number }) =>
      ['observability', 'audit', filters.action ?? '', filters.page] as const,
  },
}
