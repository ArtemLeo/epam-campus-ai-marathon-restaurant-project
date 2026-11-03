export type CatalogLocale = 'en' | 'uk' | 'fr' | 'es' | 'de'
export type DishTranslations = Partial<Record<CatalogLocale, { name?: string; description?: string }>>

export interface DishListResponse {
  id: string
  name: string
  imageUrl: string | null
  price: number
  state: string
  weight: string
  dishType: string
  description: string
  translations?: DishTranslations
  calories: string
  proteins: string
  carbohydrates: string
  fats: string
  vitamins: string
  locationIds?: string[]
  status?: 'Confirmed' | 'Rejected' | 'Pending'
}
