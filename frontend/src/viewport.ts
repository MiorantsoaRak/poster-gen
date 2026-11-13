// On one column, once a version exists, the real poster stays on top of the controls (D-POSTER-EDITOR-005): about a
// third of the visible height, so that the controls keep the rest; at most 420 px; never under the 96 px strip it
// collapses to while a text field has the focus (a short or landscape screen).
export const POSTER_STRIP = 96
export const posterHeight = (visibleHeight: number) => Math.round(Math.min(420, Math.max(POSTER_STRIP, visibleHeight * .34)))
