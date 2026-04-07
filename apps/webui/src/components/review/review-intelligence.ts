import type { LearnedRule, LearnedSuggestion, ManifestRow } from '@/lib/types'

import type { RuleStudioDraft } from './rule-studio-sheet'

type LearnedSource = LearnedRule | LearnedSuggestion

function toSignalLabel(signalKey: string): string {
  switch (signalKey) {
    case 'media_type':
      return 'media type'
    case 'collection_title':
      return 'collection'
    case 'category':
      return 'category'
    default:
      return signalKey.replaceAll('_', ' ')
  }
}

function toSuggestionLabel(suggestionType: string): string {
  switch (suggestionType) {
    case 'category':
      return 'set category'
    case 'ignore':
      return 'ignore row'
    default:
      return suggestionType.replaceAll('_', ' ')
  }
}

function toConfidenceLabel(label?: LearnedSource['confidence_label']): string {
  if (!label) {
    return ''
  }
  return `Confidence label: ${label}.`
}

function createBaseDraft(name: string, description: string): RuleStudioDraft {
  return {
    name,
    scope: 'manifest',
    description,
    version: 1,
    conditions: {
      query: '',
      statuses: [],
      media_types: [],
      categories: [],
      review_buckets: [],
    },
    actions: {},
  }
}

export function createRuleDraftFromLearnedSuggestion(
  suggestion: LearnedSource,
  options?: { reviewBucket?: ManifestRow['review_bucket']; descriptionPrefix?: string },
): RuleStudioDraft {
  const signalLabel = `${toSignalLabel(suggestion.signal_key)}=${suggestion.signal_value}`
  const descriptionPrefix = options?.descriptionPrefix ? `${options.descriptionPrefix}. ` : ''
  const draft = createBaseDraft(
    `Learned: ${suggestion.signal_value} -> ${suggestion.suggestion_value}`,
    `${descriptionPrefix}Promoted from learned signal ${signalLabel}. This stays review-only until you preview, save, or apply it yourself.`,
  )
  draft.draft_source = 'learned_suggestion_v1'
  draft.warnings = ['Learned suggestions stay advisory. Preview the draft before applying it to the overlay.']

  if (suggestion.signal_key === 'media_type') {
    draft.conditions.media_types = [suggestion.signal_value]
  } else if (suggestion.signal_key === 'category') {
    draft.conditions.categories = [suggestion.signal_value]
  } else {
    draft.conditions.query = suggestion.signal_value
  }

  if (options?.reviewBucket) {
    draft.conditions.review_buckets = [options.reviewBucket]
  }

  if (suggestion.suggestion_type === 'category') {
    draft.actions.set_category = suggestion.suggestion_value
  }
  if (suggestion.suggestion_type === 'ignore') {
    draft.actions.set_ignore = suggestion.suggestion_value.toLowerCase() !== 'false'
  }

  draft.explainability = {
    selected_count: 1,
    selected_row_ids: [],
    shared_media_types: suggestion.signal_key === 'media_type' ? [suggestion.signal_value] : [],
    shared_review_buckets: options?.reviewBucket ? [options.reviewBucket] : [],
    shared_query: suggestion.signal_key === 'media_type' ? '' : suggestion.signal_value,
    inferred_actions: [suggestion.suggestion_type],
    save_allowed: false,
    apply_allowed: false,
  }

  return draft
}

export function explainLearnedSuggestion(suggestion: LearnedSource): string {
  const explanation = suggestion.explanation?.trim()
  const source = suggestion.source?.trim()
  const confidenceLabel = toConfidenceLabel(suggestion.confidence_label)

  if (explanation) {
    return [explanation, confidenceLabel, source ? `Source: ${source}.` : ''].filter(Boolean).join(' ')
  }

  return [
    `Suggest ${toSuggestionLabel(suggestion.suggestion_type)} "${suggestion.suggestion_value}" because ${suggestion.count} prior review correction(s) linked ${toSignalLabel(suggestion.signal_key)} "${suggestion.signal_value}" to the same outcome at ${Math.round(suggestion.confidence * 100)}% confidence.`,
    confidenceLabel,
    source ? `Source: ${source}.` : '',
  ]
    .filter(Boolean)
    .join(' ')
}
