"""
🧠 Signal Brain - Zone Clustering
=================================
Clusters nearby levels into zones.

$684.39, $684.41, $684.43 → ONE zone at $684.41 with 3M combined volume
"""

import logging
import statistics
from typing import List, Dict, Optional
from dataclasses import dataclass

from .models import SupportZone, ZoneRank

logger = logging.getLogger(__name__)


class ZoneClusterer:
    """
    Clusters nearby price levels into zones.
    
    Levels within CLUSTER_THRESHOLD % of each other are combined.
    Combined volume determines zone rank (PRIMARY/SECONDARY/TERTIARY).
    """
    
    # Levels within 0.10% are same zone
    CLUSTER_THRESHOLD_PCT = 0.10
    
    # Volume thresholds for ranking
    VOLUME_PRIMARY = 2_000_000
    VOLUME_SECONDARY = 1_000_000
    VOLUME_TERTIARY = 500_000
    
    def __init__(self, cluster_threshold_pct: float = CLUSTER_THRESHOLD_PCT):
        self.cluster_threshold = cluster_threshold_pct
    
    def cluster_levels(
        self,
        levels: List[Dict],
        current_price: float,
        symbol: str = "SPY"
    ) -> tuple[List[SupportZone], List[SupportZone]]:
        """
        Cluster levels into support and resistance zones.
        
        Args:
            levels: List of {'price': float, 'volume': int} dicts
            current_price: Current market price
            symbol: Stock symbol
            
        Returns:
            Tuple of (support_zones, resistance_zones)
        """
        if not levels:
            return [], []
        
        # Sort by price
        sorted_levels = sorted(levels, key=lambda x: x['price'])
        
        # Cluster nearby levels
        clusters = self._find_clusters(sorted_levels)
        
        # Convert to zones
        support_zones = []
        resistance_zones = []
        
        for cluster in clusters:
            zone = self._create_zone(cluster, current_price, symbol)
            
            if zone.zone_type == "SUPPORT":
                support_zones.append(zone)
            else:
                resistance_zones.append(zone)
        
        # Sort by distance from current price
        support_zones.sort(key=lambda z: z.distance_pct)
        resistance_zones.sort(key=lambda z: z.distance_pct)
        
        logger.info(f"📊 Clustered {len(levels)} levels into {len(support_zones)} support + {len(resistance_zones)} resistance zones")
        
        return support_zones, resistance_zones
    
    def _find_clusters(self, sorted_levels: List[Dict]) -> List[List[Dict]]:
        """Find clusters of nearby levels."""
        clusters = []
        used = set()
        
        for i, level in enumerate(sorted_levels):
            if i in used:
                continue
            
            # Start new cluster
            cluster = [level]
            used.add(i)
            
            # Find all levels within threshold
            for j, other in enumerate(sorted_levels):
                if j in used:
                    continue
                
                # Check if within threshold of any level in cluster
                for c_level in cluster:
                    pct_diff = abs(other['price'] - c_level['price']) / c_level['price'] * 100
                    if pct_diff <= self.cluster_threshold:
                        cluster.append(other)
                        used.add(j)
                        break
            
            clusters.append(cluster)
        
        return clusters
    
    def _create_zone(
        self, 
        cluster: List[Dict], 
        current_price: float,
        symbol: str
    ) -> SupportZone:
        """Create a SupportZone from a cluster of levels."""
        prices = [l['price'] for l in cluster]
        volumes = [l['volume'] for l in cluster]
        
        center = statistics.mean(prices)
        combined_vol = sum(volumes)
        
        # Determine rank by volume
        if combined_vol >= self.VOLUME_PRIMARY:
            rank = ZoneRank.PRIMARY
        elif combined_vol >= self.VOLUME_SECONDARY:
            rank = ZoneRank.SECONDARY
        else:
            rank = ZoneRank.TERTIARY
        
        # Support or Resistance?
        zone_type = "SUPPORT" if current_price > center else "RESISTANCE"
        
        # Distance from current price
        distance_pct = abs(current_price - center) / center * 100
        
        return SupportZone(
            symbol=symbol,
            center_price=round(center, 2),
            min_price=round(min(prices), 2),
            max_price=round(max(prices), 2),
            combined_volume=combined_vol,
            level_count=len(cluster),
            levels=prices,
            rank=rank,
            zone_type=zone_type,
            distance_pct=round(distance_pct, 2),
        )
    
    def get_primary_zones(
        self, 
        support_zones: List[SupportZone], 
        resistance_zones: List[SupportZone]
    ) -> Dict[str, Optional[SupportZone]]:
        """Get the most important support and resistance zones."""
        primary_support = None
        primary_resistance = None
        
        # Primary = highest volume zone
        if support_zones:
            primary_support = max(support_zones, key=lambda z: z.combined_volume)
        
        if resistance_zones:
            primary_resistance = max(resistance_zones, key=lambda z: z.combined_volume)
        
        return {
            'primary_support': primary_support,
            'primary_resistance': primary_resistance,
        }





