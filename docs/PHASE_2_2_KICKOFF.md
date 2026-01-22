# Phase 2 #2: LLM Auto-Triage & Issue Classification

**Status**: KICKOFF 🚀
**Issue**: #801 (4-day effort)
**Relates to**: Phase 1 (Smart Selector) + Phase 2 #1 (Semantic Clustering)

## Objective

Implement automatic issue classification and triage using Large Language Models (LLMs). Enable intelligent labeling, priority suggestions, and team assignment based on issue content.

## Design Specification

### Architecture

```
┌─────────────────────────────────┐
│   Issue Text (Title + Body)     │
│   + Context (Labels, Priority)  │
└────────────────┬────────────────┘
                 │
         ┌───────▼────────┐
         │ LLMClassifier  │
         │ - Few-shot     │
         │ - Caching      │
         │ - Feedback     │
         └───────┬────────┘
                 │
     ┌───────────┼───────────┐
     │           │           │
┌────▼────┐ ┌───▼────┐ ┌────▼────┐
│ Labels  │ │Priority│ │  Team   │
│ [0,1]   │ │ [0,1]  │ │[0,1]    │
└─────────┘ └────────┘ └─────────┘
     │           │           │
     └───────────┼───────────┘
             ┌───▼────┐
             │ Scorer │
             │ w/ P2#1│
             └────────┘
```

### Components

1. **LLMClassifier** (200+ lines)
   - Model: OpenAI (GPT-4 recommended) or Anthropic Claude
   - Cache: Redis/in-memory with TTL (1hr)
   - Multi-label: Return up to 5 labels per issue
   - Priority: Suggest priority [P0, P1, P2, P3]
   - Team: Suggest owning team [platform, infra, uims, etc.]
   - Confidence scores: For each prediction

2. **Few-Shot Prompter** (100+ lines)
   - Template: System prompt + 3-5 examples
   - Dynamic selection: Choose examples similar to issue (use Phase 2 #1 clustering!)
   - Context window: Support long issue descriptions (truncate intelligently)

3. **Feedback Loop** (80+ lines)
   - Store: Actual labels → compare vs predicted
   - Accuracy tracking: Per-label, per-team metrics
   - Refinement: Update few-shot examples quarterly

4. **Integration** (50+ lines)
   - UIMS service: Call classifier before composite_score()
   - Dashboard: Show predictions + confidence + actual labels
   - Override: Allow manual override with feedback capture

## Implementation Plan

### Day 1: LLMClassifier Core (4-6 hours)
- [ ] Create `src/llm_triage/classifier.py`
  - `LLMClassifier` class
  - `predict(issue: dict) → ClassificationResult`
  - OpenAI/Claude API integration
  - Caching decorator
- [ ] Unit tests: 10+ tests for basic classification

### Day 2: Few-Shot Optimization (4-6 hours)
- [ ] Create `src/llm_triage/few_shot.py`
  - `FewShotSelector` class
  - `select_examples(issue) → List[Example]`
  - Integration with semantic clustering (Phase 2 #1)
- [ ] Tests: 8+ tests for example selection

### Day 3: Feedback & Metrics (4-6 hours)
- [ ] Create `src/llm_triage/feedback.py`
  - `FeedbackTracker` class
  - Accuracy metrics per label
  - Confusion matrix generation
- [ ] Dashboard: Metrics visualization
- [ ] Tests: 6+ tests for accuracy tracking

### Day 4: Integration & Validation (4-6 hours)
- [ ] Integrate into Smart Selector scorer
- [ ] Performance benchmarking
- [ ] Accuracy validation on 100+ real issues
- [ ] Documentation + runbooks

## Testing Strategy

**Unit Tests**: 30+ tests
- Classification accuracy (mock responses)
- Few-shot example selection
- Caching behavior
- Error handling (API failures, rate limits)

**Integration Tests**: 10+ tests
- End-to-end classification + scoring
- Feedback loop accuracy tracking
- Cache invalidation

**Performance Benchmarks**:
- Classification latency: <500ms p95 (with cache: <50ms)
- Memory: <100MB for cache + model
- API cost: ~$0.01 per issue classification

## Acceptance Criteria

- [ ] LLMClassifier predicts 3+ labels per issue with >85% accuracy
- [ ] Priority suggestions: >85% accuracy vs actual priorities
- [ ] Team assignment: >80% accuracy (harder task, more context-dependent)
- [ ] Performance: <500ms per issue (with cache: <50ms)
- [ ] Feedback loop: Tracks actual labels and feeds back into model
- [ ] Cost tracking: Monitor API spend, optimize caching
- [ ] Comprehensive test coverage: 85%+ code coverage
- [ ] Documentation: README + integration guide

## Success Metrics

| Metric | Target | Method |
|--------|--------|--------|
| Label Accuracy | 85%+ | Compare predictions vs actual |
| Priority Accuracy | 85%+ | Per-priority precision/recall |
| Team Accuracy | 80%+ | Simpler task (hint-based) |
| Latency p95 | 500ms | Benchmark on real issues |
| Cache Hit Rate | 40%+ | Similar issues reuse cache |
| API Cost | <$0.01/issue | Batch + caching optimization |
| Test Coverage | 85%+ | pytest coverage report |

## Out of Scope (Phase 3)

- [ ] Model fine-tuning (use few-shot only)
- [ ] Custom model training
- [ ] Embedding-based classification (Phase 2 #1 is for duplicates only)
- [ ] Real-time label suggestions during typing
- [ ] Multi-language support
- [ ] Sentiment analysis or topic modeling

## Related Work

- **Phase 1**: Smart Selector scorer (we'll integrate with)
- **Phase 2 #1**: Semantic clustering (for few-shot example selection)
- **UIMS**: Main consumer of classifications
- **GitHub API**: Issue data source

## Success Definition

✅ Deployed and active in staging UIMS
✅ 85%+ accuracy on multi-label classification
✅ 500ms <p95 latency
✅ 40%+ cache hit rate (cost optimization)
✅ Feedback loop active (capturing accuracy metrics)

---

Owner: UIMS Platform Team
Effort: 4 days (32 hours)
Priority: P0
Relates to: #800, #801, #544
