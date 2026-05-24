/**
 * MasterBriefPanels — entry point for the Today's Brief page.
 *
 * ExploitationCommandCenter: compact kill-shots verdict bar (reconciled verdict,
 * SPY position, WAR_VETO warning, link to /signal-chain). Fetches independently.
 * UnifiedBriefView: Alpha Terminal V8 — full brief, owns its own data fetching.
 */

import { ExploitationCommandCenter } from './ExploitationCommandCenter';
import { UnifiedBriefView } from './UnifiedBriefView';

export function MasterBriefPanels() {
  return (
    <>
      <ExploitationCommandCenter />
      <UnifiedBriefView />
    </>
  );
}
