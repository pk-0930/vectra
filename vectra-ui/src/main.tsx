import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { loadFeatures } from './services/features'
import { installTokens } from './design-system/tokens'
installTokens()

void loadFeatures().then(() => ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
))