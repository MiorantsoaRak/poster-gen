// Keep the preview compact so the mobile tools remain reachable; typing uses a 96 px strip.
export const POSTER_STRIP = 96
export const posterHeight = (visibleHeight: number) => Math.round(Math.min(180, Math.max(POSTER_STRIP, visibleHeight * .22)))
