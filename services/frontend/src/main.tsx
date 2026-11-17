import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const media = window.matchMedia("(prefers-color-scheme: dark)");
const applyTheme = () => {
  const theme = localStorage.getItem("theme") || "system";
  document.documentElement.dataset.theme = theme;
  document.documentElement.classList.toggle("dark", theme === "dark" || (theme === "system" && media.matches));
};
media.addEventListener("change", applyTheme);
window.addEventListener("neurotrace-theme", applyTheme);
applyTheme();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
