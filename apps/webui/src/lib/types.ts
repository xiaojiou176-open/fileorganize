import type * as Generated from '../../../../contracts/api/generated/webui/types'

export * from '../../../../contracts/api/generated/webui/types'

export type LearnedSuggestion = Generated.LearnedSuggestion & {
  confidence_label?: 'weak' | 'medium' | 'high'
  strength?: 'weak' | 'medium' | 'strong'
  source?: string
  reason?: string
  explanation?: string
}

export type ManifestRow = Omit<Generated.ManifestRow, 'learned_suggestions' | 'row_id'> & {
  row_id?: string
  learned_suggestions?: LearnedSuggestion[]
}

export type LearnedRule = Generated.LearnedRule & {
  confidence_label?: 'weak' | 'medium' | 'high'
  strength?: 'weak' | 'medium' | 'strong'
  source?: string
  reason?: string
  explanation?: string
}

export type ReviewCopilotReason = Generated.ReviewCopilotReason

export type ReviewCopilotPriority = Generated.ReviewCopilotPriority

export type ReviewCopilotRuleOpportunity = Generated.ReviewCopilotRuleOpportunity

export type ReviewCopilotGuardrails = Generated.ReviewCopilotGuardrails

export type ReviewQueueBatchSuggestion = Generated.ReviewQueueBatchSuggestion

export type ReviewCopilotSummary = Generated.ReviewCopilotSummary

export interface ReviewRuleDraftExplainability {
  selected_count: number
  selected_row_ids: string[]
  shared_media_types: string[]
  shared_review_buckets: string[]
  shared_query: string
  inferred_actions: string[]
  save_allowed: boolean
  apply_allowed: boolean
}

export type ReviewRuleDraftResponse = Generated.ReviewRuleDraftResponse

export interface ReviewQueueBatchTriageMeta {
  applied_count: number
  mode: string
  execute_allowed: boolean
}

export type InboxAnalyzeResponse = Generated.InboxAnalyzeResponse
