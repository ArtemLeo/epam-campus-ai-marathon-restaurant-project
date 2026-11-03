import type { DishTranslations } from '@/models/dishes/dish-list-response.model'

export type ParticipantType = 'Owner' | 'Guest'

export interface DishShort {
  id: string
  name: string
  price: number
  imageUrl?: string
  weight?: string
  translations?: DishTranslations
}

export interface ParticipantItem {
  dish: DishShort
  quantity: number
}

export interface Participant {
  id: string
  type: ParticipantType
  name: string
  items: ParticipantItem[]
  total: number
  isSubmitted: boolean
}
