// « Partager » (docs/project/designs/share-poster.md).

/** The final panel's one rule (D-SHARE-001): a render is presented as the poster's current file (« Votre affiche est prête »,
 *  the live « Prix affiché », its confirmation as current) only when no edit waits to be saved or is being saved, no poster
 *  read has shown a revision ahead of the one this tab saved (another tab saved), and it was made from the saved revision,
 *  or it is the confirmation a poster read named at that same revision (the server checked its image against that
 *  revision: an undo back to the same image). Otherwise the image may show another price than the editor: it is an
 *  earlier version, confirmed or not. `read`: the last poster read, its revision and the render it named (or null). */
export function presentedAsCurrent(render: { id: string; source_revision: number }, saved: number, dirty: boolean,
                                   read: { revision: number; render_id: string | null } | null) {
  if (dirty || (read && read.revision > saved)) return false
  return render.source_revision === saved || (read?.render_id === render.id && read.revision === saved)
}
