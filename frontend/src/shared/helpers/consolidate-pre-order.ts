export interface Dish {
  id: string
  name: string
  price: number
}

export interface Participant<TDish extends Dish = Dish> {
  id: string
  name: string
  isSubmitted: boolean
  items: { dish: TDish; quantity: number }[]
}

export interface ConsolidatedOrder<TDish extends Dish = Dish> {
  items: { dish: TDish; quantity: number }[]
  total: number
}

/**
 * The order the restaurant receives: only submitted carts, the same dish merged into one line.
 * Generic over the dish type so callers keep their richer dish objects (image, weight…).
 */
export function consolidatePreOrder<TDish extends Dish>(participants: Participant<TDish>[]): ConsolidatedOrder<TDish> {
  const byDish = new Map<string, { dish: TDish; quantity: number }>()

  for (const participant of participants.filter((person) => person.isSubmitted)) {
    for (const item of participant.items) {
      const existing = byDish.get(item.dish.id)
      // always a NEW object — the input is never mutated
      byDish.set(item.dish.id, { dish: item.dish, quantity: (existing?.quantity ?? 0) + item.quantity })
    }
  }

  const items = [...byDish.values()]
  const total = items.reduce((sum, item) => sum + item.dish.price * item.quantity, 0)
  return { items, total }
}
