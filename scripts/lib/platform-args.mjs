import { parseBenchmarkMode } from './benchmark-startup.mjs'

export function parsePlatformArgs(args) {
  const benchmarkArgs = []
  let startTopic2Upstream = true
  let startTopic3Diversity = true
  let startTopic3Difficulty = true
  let startTopic3Compliance = true
  let startTopic2FilterGuard = true
  let startTopic4InputWorkflow = true
  let startTopic3CulturalAssessment = true
  let startGovernanceWorker = true
  let startTopic1CorpusTools = true
  let seenTopic2UpstreamSkip = false
  let seenTopic3DiversitySkip = false
  let seenTopic3DifficultySkip = false
  let seenTopic3ComplianceSkip = false
  let seenTopic2FilterGuardSkip = false
  let seenTopic4InputWorkflowSkip = false
  let seenTopic3CulturalAssessmentSkip = false
  let seenGovernanceWorkerSkip = false

  for (const arg of args) {
    if (arg === '--no-topic1-corpus-tools') {
      if (!startTopic1CorpusTools) throw new Error('--no-topic1-corpus-tools may only be provided once')
      startTopic1CorpusTools = false
      continue
    }
    if (arg === '--no-topic2-upstream') {
      if (seenTopic2UpstreamSkip) {
        throw new Error('--no-topic2-upstream may only be provided once')
      }
      startTopic2Upstream = false
      seenTopic2UpstreamSkip = true
      continue
    }

    if (arg === '--no-topic3-diversity') {
      if (seenTopic3DiversitySkip) {
        throw new Error('--no-topic3-diversity may only be provided once')
      }
      startTopic3Diversity = false
      seenTopic3DiversitySkip = true
      continue
    }

    if (arg === '--no-topic3-difficulty') {
      if (seenTopic3DifficultySkip) {
        throw new Error('--no-topic3-difficulty may only be provided once')
      }
      startTopic3Difficulty = false
      seenTopic3DifficultySkip = true
      continue
    }

    if (arg === '--no-topic3-compliance') {
      if (seenTopic3ComplianceSkip) {
        throw new Error('--no-topic3-compliance may only be provided once')
      }
      startTopic3Compliance = false
      seenTopic3ComplianceSkip = true
      continue
    }

    if (arg === '--no-topic2-filterguard') {
      if (seenTopic2FilterGuardSkip) {
        throw new Error('--no-topic2-filterguard may only be provided once')
      }
      startTopic2FilterGuard = false
      seenTopic2FilterGuardSkip = true
      continue
    }

    if (arg === '--no-topic4-input-workflow') {
      if (seenTopic4InputWorkflowSkip) {
        throw new Error('--no-topic4-input-workflow may only be provided once')
      }
      startTopic4InputWorkflow = false
      seenTopic4InputWorkflowSkip = true
      continue
    }

    if (arg === '--no-topic3-cultural-assessment') {
      if (seenTopic3CulturalAssessmentSkip) {
        throw new Error('--no-topic3-cultural-assessment may only be provided once')
      }
      startTopic3CulturalAssessment = false
      seenTopic3CulturalAssessmentSkip = true
      continue
    }

    if (arg === '--no-governance-worker') {
      if (seenGovernanceWorkerSkip) {
        throw new Error('--no-governance-worker may only be provided once')
      }
      startGovernanceWorker = false
      seenGovernanceWorkerSkip = true
      continue
    }

    benchmarkArgs.push(arg)
  }

  return {
    benchmarkMode: parseBenchmarkMode(benchmarkArgs),
    startTopic2Upstream,
    startTopic3Diversity,
    startTopic3Difficulty,
    startTopic3Compliance,
    startTopic2FilterGuard,
    startTopic4InputWorkflow,
    startTopic3CulturalAssessment,
    startGovernanceWorker,
    startTopic1CorpusTools,
  }
}
