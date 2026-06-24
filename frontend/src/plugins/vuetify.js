import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { aliases, mdi } from 'vuetify/iconsets/mdi'
import '@mdi/font/css/materialdesignicons.css'

const customDarkTheme = {
  dark: true,
  colors: {
    background: '#080b11',
    surface: '#0d1117',
    primary: '#00f2fe',
    secondary: '#9b51e0',
    accent: '#ff007f',
    error: '#ff1744',
    info: '#2196F3',
    success: '#00e676',
    warning: '#ffb300',
  },
}

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'customDarkTheme',
    themes: {
      customDarkTheme,
    },
  },
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    },
  },
})
