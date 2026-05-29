/**
 * MasterBriefPanels — kill chain verdict bar + compact macro edge strip.
 * UnifiedBriefView removed: it caused Groq 429 errors, re-rendered duplicate data,
 * and buried the kill chain verdict under 6 bloated components.
 */
import { ExploitationCommandCenter } from './ExploitationCommandCenter';
import { MacroEdgeStrip } from './MacroEdgeStrip';

export function MasterBriefPanels() {
  return (
    <>
      <ExploitationCommandCenter />
      <MacroEdgeStrip />
    </>
  );
}
