<template>
  <article class="participant-card">
    <header class="participant-card__header">
      <div class="participant-card__heading">
        <h2 class="participant-card__title">{{ title }}</h2>
        <span v-if="participant.isSubmitted" class="chip chip--submitted">{{ t('orders.submitted') }}</span>
        <span v-else class="chip chip--pending">{{ t('orders.choosing') }}</span>
      </div>
      <button
        v-if="canRemove"
        type="button"
        class="participant-card__remove"
        :aria-label="t('orders.removePerson', { name: participant.name })"
        @click="emit('removeClick', participant)"
      >
        {{ t('orders.removeGuest') }}
      </button>
    </header>

    <ul v-if="participant.items.length" class="participant-card__items">
      <li v-for="item in participant.items" :key="item.dish.id" class="dish-row">
        <img
          v-if="item.dish.imageUrl"
          class="dish-row__avatar"
          :src="item.dish.imageUrl"
          alt=""
          width="40"
          height="40"
          loading="lazy"
        />
        <span v-else class="dish-row__avatar dish-row__avatar--initial" aria-hidden="true">
          {{ localizedDish(item.dish).name.charAt(0) }}
        </span>
        <p class="dish-row__name">{{ localizedDish(item.dish).name }}</p>
        <p class="dish-row__qty">× {{ item.quantity }}</p>
        <p class="dish-row__price">{{ formatCurrency(item.dish.price * item.quantity) }}</p>
      </li>
    </ul>
    <p v-else class="participant-card__empty">{{ t('orders.noDishes') }}</p>

    <p class="participant-card__subtotal">
      <span>{{ t('orders.subtotal') }}</span>
      <span>{{ formatCurrency(participant.total) }}</span>
    </p>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import type { Participant } from '@/models/group-orders/participant.model'
import { formatCurrency } from '@/utils/formatters'

const props = withDefaults(
  defineProps<{
    participant: Participant
    /** The Owner's own session: titled "My Pre-Order". */
    isMe?: boolean
    /** Show "Remove Guest" (guests only, while the group is still open). */
    canRemove?: boolean
  }>(),
  {
    isMe: false,
    canRemove: false,
  },
)

const emit = defineEmits<{ removeClick: [participant: Participant] }>()

const title = computed(() => {
  if (props.isMe) return t('orders.myOrder')
  const person = props.participant
  return t(person.type === 'Owner' ? 'orders.ownerName' : 'orders.guestName', { name: person.name })
})
</script>

<style scoped>
.participant-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--neutral-0);
  border-radius: var(--radius-md);
}

.participant-card__header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
}

.participant-card__heading {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.participant-card__title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  line-height: 28px;
  color: var(--neutral-900);
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
}

.chip--submitted {
  background: var(--green-100);
  color: var(--green-600);
}

.chip--pending {
  background: var(--orange-100);
  color: var(--orange-600);
}

.participant-card__remove {
  padding: 4px 8px;
  border: none;
  border-bottom: 1px solid var(--neutral-900);
  background: none;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-900);
  cursor: pointer;
}

.participant-card__remove:hover,
.participant-card__remove:focus-visible {
  color: var(--red-400);
  border-bottom-color: var(--red-400);
}

.participant-card__items {
  margin: 0;
  padding: 0;
  list-style: none;
}

.dish-row {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto 80px;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--neutral-200);
}

.dish-row p {
  margin: 0;
}

.dish-row__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
}

.dish-row__avatar--initial {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--green-100);
  color: var(--green-600);
  font-size: 16px;
}

.dish-row__name {
  font-weight: 500;
  overflow-wrap: anywhere;
}

.dish-row__qty {
  color: var(--neutral-600);
  white-space: nowrap;
}

.dish-row__price {
  text-align: right;
  font-weight: 500;
  white-space: nowrap;
}

.participant-card__empty {
  margin: 0;
  padding: 8px 0;
  color: var(--neutral-400);
}

.participant-card__subtotal {
  display: flex;
  justify-content: space-between;
  margin: 0;
  padding: 8px 12px 0;
  font-size: 16px;
  font-weight: 500;
}

@media (max-width: 480px) {
  .dish-row {
    grid-template-columns: 40px minmax(0, 1fr) auto;
    gap: 4px 12px;
  }

  .dish-row__price {
    grid-column: 2 / -1;
    text-align: left;
  }

  .participant-card__subtotal {
    padding-inline: 0;
  }
}
</style>
