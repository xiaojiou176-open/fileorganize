import '@fontsource/ibm-plex-sans/300.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'

import App from './App'
import './index.css'

const configuredBase = (import.meta.env.BASE_URL || '/').replace(/\/+$/, '')
const browserBase = configuredBase.length > 0 ? configuredBase : '/'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={browserBase}>
      <App />
      <Toaster
        closeButton
        mobileOffset={{ bottom: 16, left: 16, right: 16, top: 88 }}
        offset={{ right: 16, top: 88 }}
        position="top-right"
        richColors
      />
    </BrowserRouter>
  </StrictMode>,
)
