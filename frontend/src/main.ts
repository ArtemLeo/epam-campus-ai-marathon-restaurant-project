import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { i18n } from './i18n'
import App from './App.vue'
import router from './router'

import './styles/main.css'

async function bootstrap(): Promise<void> {
  // DEV-ONLY: `?demo` enables a mock login and backend for the group-order demo reservation.
  // `import.meta.env.DEV` is `false` in a production build, so this branch and its chunk are dropped.
  if (import.meta.env.DEV) {
    const { installDevMocks } = await import('./shared/mocks/install-dev-mocks')
    installDevMocks()
  }

  const app = createApp(App)
  app.use(createPinia())
  app.use(i18n)
  app.use(router)
  app.mount('#app')
}

void bootstrap()
