import { ref } from 'vue'
import { OutputTrack } from '@/types'

export function useNavigation() {
  const currentStep = ref(1)
  const currentTrack = ref<OutputTrack | null>(null)
  const previousTrack = ref<OutputTrack>(OutputTrack.DIVERSITY)

  return { currentStep, currentTrack, previousTrack }
}
