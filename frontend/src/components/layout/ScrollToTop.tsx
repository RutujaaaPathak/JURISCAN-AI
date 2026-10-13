import { useEffect } from "react"
import { useLocation } from "react-router-dom"

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

/**
 * Keeps navigation tidy: scrolls to an element when the URL has a hash (e.g.
 * "/#features") and otherwise returns to the top of the page on route change.
 */
export function ScrollToTop() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) {
      const id = hash.replace("#", "")
      const target = document.getElementById(id)
      if (target) {
        target.scrollIntoView({
          behavior: prefersReducedMotion() ? "auto" : "smooth",
          block: "start",
        })
        return
      }
    }
    window.scrollTo({ top: 0, left: 0, behavior: "auto" })
  }, [pathname, hash])

  return null
}
