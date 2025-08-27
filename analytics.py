"""
Advanced Event Analytics and Insights
Comprehensive analytics system for cultural event trends and insights
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import statistics

from models import Event
from database import get_database
from logging_utils import log_info, log_error


@dataclass
class TrendAnalysis:
    """Represents a trend analysis result"""
    trend_type: str
    period: str
    data_points: List[Dict[str, Any]]
    growth_rate: float
    trend_direction: str  # 'increasing', 'decreasing', 'stable'
    insights: List[str]


@dataclass
class EventInsight:
    """Represents an insight about events"""
    insight_type: str
    title: str
    description: str
    data: Dict[str, Any]
    confidence: float
    recommendations: List[str]


class EventAnalytics:
    """Advanced analytics engine for cultural events"""
    
    def __init__(self):
        self.analysis_cache = {}
        
    async def analyze_trends(self, days: int = 30) -> List[TrendAnalysis]:
        """Analyze various trends in event data"""
        log_info(f"🔍 Analyzing event trends for last {days} days...")
        
        db = await get_database()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        events = await db.get_events(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        if not events:
            return []
        
        trends = []
        
        # Analyze category trends
        category_trend = await self._analyze_category_trends(events, days)
        if category_trend:
            trends.append(category_trend)
        
        # Analyze venue popularity trends
        venue_trend = await self._analyze_venue_trends(events, days)
        if venue_trend:
            trends.append(venue_trend)
        
        # Analyze time distribution trends
        time_trend = await self._analyze_time_trends(events, days)
        if time_trend:
            trends.append(time_trend)
        
        # Analyze price trends
        price_trend = await self._analyze_price_trends(events, days)
        if price_trend:
            trends.append(price_trend)
        
        # Analyze source performance trends
        source_trend = await self._analyze_source_trends(events, days)
        if source_trend:
            trends.append(source_trend)
        
        log_info(f"✅ Generated {len(trends)} trend analyses")
        return trends
    
    async def _analyze_category_trends(self, events: List[Dict], days: int) -> Optional[TrendAnalysis]:
        """Analyze trends in event categories"""
        try:
            # Group events by category and week
            weekly_categories = defaultdict(lambda: defaultdict(int))
            
            for event in events:
                if not event.get('start_time'):
                    continue
                    
                event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                week = event_date.isocalendar()[1]  # ISO week number
                category = event.get('categories', '[]')
                
                # Parse categories JSON
                try:
                    categories = json.loads(category) if isinstance(category, str) else category
                    if categories and isinstance(categories, list):
                        primary_category = categories[0]
                        weekly_categories[week][primary_category] += 1
                except:
                    weekly_categories[week]['ukategorisert'] += 1
            
            if not weekly_categories:
                return None
            
            # Calculate trend for most popular categories
            all_categories = set()
            for week_data in weekly_categories.values():
                all_categories.update(week_data.keys())
            
            category_counts = Counter()
            for week_data in weekly_categories.values():
                category_counts.update(week_data)
            
            top_categories = [cat for cat, _ in category_counts.most_common(5)]
            
            data_points = []
            for week in sorted(weekly_categories.keys()):
                week_data = {'week': week}
                for category in top_categories:
                    week_data[category] = weekly_categories[week].get(category, 0)
                data_points.append(week_data)
            
            # Calculate growth rate for top category
            if len(data_points) >= 2 and top_categories:
                top_cat = top_categories[0]
                first_week = data_points[0][top_cat]
                last_week = data_points[-1][top_cat]
                
                if first_week > 0:
                    growth_rate = ((last_week - first_week) / first_week) * 100
                else:
                    growth_rate = 0.0
                
                if growth_rate > 10:
                    trend_direction = 'increasing'
                elif growth_rate < -10:
                    trend_direction = 'decreasing'
                else:
                    trend_direction = 'stable'
            else:
                growth_rate = 0.0
                trend_direction = 'stable'
            
            insights = []
            if top_categories:
                insights.append(f"Mest populære kategori: {top_categories[0]} ({category_counts[top_categories[0]]} events)")
                if growth_rate > 20:
                    insights.append(f"{top_categories[0]} events øker kraftig ({growth_rate:.1f}%)")
                elif growth_rate < -20:
                    insights.append(f"{top_categories[0]} events synker kraftig ({growth_rate:.1f}%)")
            
            return TrendAnalysis(
                trend_type='category',
                period=f'{days} days',
                data_points=data_points,
                growth_rate=growth_rate,
                trend_direction=trend_direction,
                insights=insights
            )
            
        except Exception as e:
            log_error("analytics", f"Category trend analysis failed: {e}")
            return None
    
    async def _analyze_venue_trends(self, events: List[Dict], days: int) -> Optional[TrendAnalysis]:
        """Analyze trends in venue popularity"""
        try:
            venue_counts = Counter()
            venue_weekly = defaultdict(lambda: defaultdict(int))
            
            for event in events:
                venue = event.get('venue', '').strip()
                if not venue:
                    continue
                
                venue_counts[venue] += 1
                
                if event.get('start_time'):
                    event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                    week = event_date.isocalendar()[1]
                    venue_weekly[week][venue] += 1
            
            top_venues = [venue for venue, _ in venue_counts.most_common(10)]
            
            data_points = []
            for week in sorted(venue_weekly.keys()):
                week_data = {'week': week}
                for venue in top_venues[:5]:  # Top 5 venues
                    week_data[venue] = venue_weekly[week].get(venue, 0)
                data_points.append(week_data)
            
            # Calculate growth for top venue
            growth_rate = 0.0
            trend_direction = 'stable'
            
            if len(data_points) >= 2 and top_venues:
                top_venue = top_venues[0]
                first_week = data_points[0].get(top_venue, 0)
                last_week = data_points[-1].get(top_venue, 0)
                
                if first_week > 0:
                    growth_rate = ((last_week - first_week) / first_week) * 100
                    trend_direction = 'increasing' if growth_rate > 10 else 'decreasing' if growth_rate < -10 else 'stable'
            
            insights = []
            if top_venues:
                insights.append(f"Mest aktive venue: {top_venues[0]} ({venue_counts[top_venues[0]]} events)")
                insights.append(f"Totalt {len(venue_counts)} forskjellige venues")
            
            return TrendAnalysis(
                trend_type='venue',
                period=f'{days} days',
                data_points=data_points,
                growth_rate=growth_rate,
                trend_direction=trend_direction,
                insights=insights
            )
            
        except Exception as e:
            log_error("analytics", f"Venue trend analysis failed: {e}")
            return None
    
    async def _analyze_time_trends(self, events: List[Dict], days: int) -> Optional[TrendAnalysis]:
        """Analyze trends in event timing"""
        try:
            time_distribution = defaultdict(int)
            day_distribution = defaultdict(int)
            
            for event in events:
                if not event.get('start_time'):
                    continue
                
                event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                
                # Time of day distribution
                hour = event_date.hour
                if 6 <= hour < 12:
                    time_distribution['morning'] += 1
                elif 12 <= hour < 17:
                    time_distribution['afternoon'] += 1
                elif 17 <= hour < 22:
                    time_distribution['evening'] += 1
                else:
                    time_distribution['night'] += 1
                
                # Day of week distribution
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                day_distribution[day_names[event_date.weekday()]] += 1
            
            data_points = [
                {
                    'time_of_day': time_distribution,
                    'day_of_week': dict(day_distribution)
                }
            ]
            
            insights = []
            if time_distribution:
                most_popular_time = max(time_distribution.items(), key=lambda x: x[1])
                insights.append(f"Mest populære tid: {most_popular_time[0]} ({most_popular_time[1]} events)")
            
            if day_distribution:
                most_popular_day = max(day_distribution.items(), key=lambda x: x[1])
                insights.append(f"Mest populære dag: {most_popular_day[0]} ({most_popular_day[1]} events)")
                
                weekend_events = day_distribution['Saturday'] + day_distribution['Sunday']
                weekday_events = sum(day_distribution.values()) - weekend_events
                if weekend_events > weekday_events:
                    insights.append("Flest events på helger")
                else:
                    insights.append("Flest events på hverdager")
            
            return TrendAnalysis(
                trend_type='timing',
                period=f'{days} days',
                data_points=data_points,
                growth_rate=0.0,
                trend_direction='stable',
                insights=insights
            )
            
        except Exception as e:
            log_error("analytics", f"Time trend analysis failed: {e}")
            return None
    
    async def _analyze_price_trends(self, events: List[Dict], days: int) -> Optional[TrendAnalysis]:
        """Analyze trends in event pricing"""
        try:
            price_distribution = {'free': 0, 'paid': 0, 'unknown': 0}
            price_ranges = {'0-100': 0, '100-300': 0, '300-500': 0, '500+': 0}
            
            for event in events:
                price_info = event.get('price_info', '').lower()
                
                if not price_info:
                    price_distribution['unknown'] += 1
                    continue
                
                if 'gratis' in price_info or 'free' in price_info or '0' in price_info:
                    price_distribution['free'] += 1
                else:
                    price_distribution['paid'] += 1
                    
                    # Extract price numbers for range analysis
                    import re
                    prices = re.findall(r'\d+', price_info)
                    if prices:
                        price = int(prices[0])
                        if price <= 100:
                            price_ranges['0-100'] += 1
                        elif price <= 300:
                            price_ranges['100-300'] += 1
                        elif price <= 500:
                            price_ranges['300-500'] += 1
                        else:
                            price_ranges['500+'] += 1
            
            data_points = [
                {
                    'price_distribution': price_distribution,
                    'price_ranges': price_ranges
                }
            ]
            
            insights = []
            total_events = sum(price_distribution.values())
            if total_events > 0:
                free_percentage = (price_distribution['free'] / total_events) * 100
                insights.append(f"{free_percentage:.1f}% av events er gratis")
                
                if free_percentage > 60:
                    insights.append("Høy andel gratis kulturevents")
                elif free_percentage < 30:
                    insights.append("Mange betalte kulturevents")
            
            return TrendAnalysis(
                trend_type='pricing',
                period=f'{days} days',
                data_points=data_points,
                growth_rate=0.0,
                trend_direction='stable',
                insights=insights
            )
            
        except Exception as e:
            log_error("analytics", f"Price trend analysis failed: {e}")
            return None
    
    async def _analyze_source_trends(self, events: List[Dict], days: int) -> Optional[TrendAnalysis]:
        """Analyze trends in event sources"""
        try:
            source_counts = Counter()
            
            for event in events:
                source = event.get('source', 'unknown')
                source_counts[source] += 1
            
            data_points = [
                {
                    'source_distribution': dict(source_counts)
                }
            ]
            
            insights = []
            if source_counts:
                top_source = source_counts.most_common(1)[0]
                insights.append(f"Mest produktive kilde: {top_source[0]} ({top_source[1]} events)")
                insights.append(f"Totalt {len(source_counts)} aktive kilder")
                
                # Check for source diversity
                total_events = sum(source_counts.values())
                if top_source[1] / total_events > 0.5:
                    insights.append("Lav kildediversitet - avhengig av få kilder")
                else:
                    insights.append("God kildediversitet")
            
            return TrendAnalysis(
                trend_type='sources',
                period=f'{days} days',
                data_points=data_points,
                growth_rate=0.0,
                trend_direction='stable',
                insights=insights
            )
            
        except Exception as e:
            log_error("analytics", f"Source trend analysis failed: {e}")
            return None
    
    async def generate_insights(self, events: List[Dict]) -> List[EventInsight]:
        """Generate actionable insights from event data"""
        log_info("🧠 Generating event insights...")
        
        insights = []
        
        # Popular event patterns
        pattern_insight = await self._analyze_popular_patterns(events)
        if pattern_insight:
            insights.append(pattern_insight)
        
        # Gap analysis
        gap_insight = await self._analyze_content_gaps(events)
        if gap_insight:
            insights.append(gap_insight)
        
        # Seasonal patterns
        seasonal_insight = await self._analyze_seasonal_patterns(events)
        if seasonal_insight:
            insights.append(seasonal_insight)
        
        # Competition analysis
        competition_insight = await self._analyze_competition(events)
        if competition_insight:
            insights.append(competition_insight)
        
        log_info(f"✅ Generated {len(insights)} insights")
        return insights
    
    async def _analyze_popular_patterns(self, events: List[Dict]) -> Optional[EventInsight]:
        """Analyze what makes events popular"""
        try:
            # This is a simplified analysis - in a real system you'd have engagement metrics
            
            # Analyze by category popularity
            category_counts = Counter()
            venue_counts = Counter()
            time_patterns = defaultdict(int)
            
            for event in events:
                # Categories
                category = event.get('categories', '[]')
                try:
                    categories = json.loads(category) if isinstance(category, str) else category
                    if categories and isinstance(categories, list):
                        category_counts[categories[0]] += 1
                except:
                    pass
                
                # Venues
                if event.get('venue'):
                    venue_counts[event['venue']] += 1
                
                # Time patterns
                if event.get('start_time'):
                    event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                    if event_date.weekday() >= 5:  # Weekend
                        time_patterns['weekend'] += 1
                    else:
                        time_patterns['weekday'] += 1
            
            recommendations = []
            
            if category_counts:
                top_category = category_counts.most_common(1)[0]
                recommendations.append(f"Fokuser på {top_category[0]} events - mest populær kategori")
            
            if venue_counts:
                top_venue = venue_counts.most_common(1)[0]
                recommendations.append(f"Samarbeid med {top_venue[0]} - mest aktive venue")
            
            if time_patterns['weekend'] > time_patterns['weekday']:
                recommendations.append("Prioriter helgarrangementer - høyere deltakelse")
            
            return EventInsight(
                insight_type='popularity_patterns',
                title='Populære event-mønstre',
                description='Analyse av hva som gjør events populære',
                data={
                    'top_categories': dict(category_counts.most_common(5)),
                    'top_venues': dict(venue_counts.most_common(5)),
                    'time_patterns': dict(time_patterns)
                },
                confidence=0.7,
                recommendations=recommendations
            )
            
        except Exception as e:
            log_error("analytics", f"Popular patterns analysis failed: {e}")
            return None
    
    async def _analyze_content_gaps(self, events: List[Dict]) -> Optional[EventInsight]:
        """Identify gaps in cultural content"""
        try:
            # Define expected cultural categories
            expected_categories = {
                'musikk', 'teater', 'utstilling', 'litteratur', 'dans', 
                'film', 'familie', 'workshop', 'foredrag', 'festival'
            }
            
            found_categories = set()
            category_counts = Counter()
            
            for event in events:
                category = event.get('categories', '[]')
                try:
                    categories = json.loads(category) if isinstance(category, str) else category
                    if categories and isinstance(categories, list):
                        found_categories.add(categories[0])
                        category_counts[categories[0]] += 1
                except:
                    pass
            
            missing_categories = expected_categories - found_categories
            underrepresented = []
            
            # Find underrepresented categories (less than 5% of events)
            total_events = sum(category_counts.values())
            if total_events > 0:
                for category, count in category_counts.items():
                    if count / total_events < 0.05:  # Less than 5%
                        underrepresented.append(category)
            
            recommendations = []
            if missing_categories:
                recommendations.append(f"Utvid dekning av: {', '.join(missing_categories)}")
            
            if underrepresented:
                recommendations.append(f"Øk fokus på underrepresenterte kategorier: {', '.join(underrepresented)}")
            
            return EventInsight(
                insight_type='content_gaps',
                title='Innhold hull-analyse',
                description='Identifiserte mangler i kulturelt innhold',
                data={
                    'missing_categories': list(missing_categories),
                    'underrepresented': underrepresented,
                    'category_distribution': dict(category_counts)
                },
                confidence=0.8,
                recommendations=recommendations
            )
            
        except Exception as e:
            log_error("analytics", f"Content gaps analysis failed: {e}")
            return None
    
    async def _analyze_seasonal_patterns(self, events: List[Dict]) -> Optional[EventInsight]:
        """Analyze seasonal patterns in events"""
        try:
            monthly_distribution = defaultdict(int)
            
            for event in events:
                if not event.get('start_time'):
                    continue
                
                event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                month = event_date.month
                monthly_distribution[month] += 1
            
            # Find peak and low seasons
            if monthly_distribution:
                peak_month = max(monthly_distribution.items(), key=lambda x: x[1])
                low_month = min(monthly_distribution.items(), key=lambda x: x[1])
                
                month_names = [
                    'Januar', 'Februar', 'Mars', 'April', 'Mai', 'Juni',
                    'Juli', 'August', 'September', 'Oktober', 'November', 'Desember'
                ]
                
                recommendations = [
                    f"Planlegg spesielle campaigns for {month_names[peak_month[0]-1]} (høysesong)",
                    f"Øk markedsføring i {month_names[low_month[0]-1]} (lavsesong)"
                ]
                
                return EventInsight(
                    insight_type='seasonal_patterns',
                    title='Sesongmønstre',
                    description='Analyse av sesongvariasjoner i events',
                    data={
                        'monthly_distribution': dict(monthly_distribution),
                        'peak_month': month_names[peak_month[0]-1],
                        'low_month': month_names[low_month[0]-1]
                    },
                    confidence=0.75,
                    recommendations=recommendations
                )
            
        except Exception as e:
            log_error("analytics", f"Seasonal patterns analysis failed: {e}")
            return None
    
    async def _analyze_competition(self, events: List[Dict]) -> Optional[EventInsight]:
        """Analyze competition between similar events"""
        try:
            # Group events by date and category
            date_category_events = defaultdict(list)
            
            for event in events:
                if not event.get('start_time'):
                    continue
                
                event_date = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                date_key = event_date.date()
                
                category = event.get('categories', '[]')
                try:
                    categories = json.loads(category) if isinstance(category, str) else category
                    if categories and isinstance(categories, list):
                        primary_category = categories[0]
                        date_category_events[(date_key, primary_category)].append(event)
                except:
                    pass
            
            # Find days with high competition
            high_competition_days = []
            for (date, category), day_events in date_category_events.items():
                if len(day_events) >= 3:  # 3+ events of same category on same day
                    high_competition_days.append({
                        'date': date.isoformat(),
                        'category': category,
                        'event_count': len(day_events)
                    })
            
            recommendations = []
            if high_competition_days:
                recommendations.append("Spred lignende events over flere dager for å redusere konkurranse")
                recommendations.append("Koordiner med andre arrangører for bedre planlegging")
            
            return EventInsight(
                insight_type='competition',
                title='Konkurranseanalyse',
                description='Analyse av overlappende events',
                data={
                    'high_competition_days': high_competition_days[:10],  # Top 10
                    'total_competition_days': len(high_competition_days)
                },
                confidence=0.6,
                recommendations=recommendations
            )
            
        except Exception as e:
            log_error("analytics", f"Competition analysis failed: {e}")
            return None
    
    async def export_analytics_report(self, filepath: str, days: int = 30):
        """Export comprehensive analytics report"""
        log_info(f"📊 Exporting analytics report to {filepath}...")
        
        # Get data for analysis
        db = await get_database()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        events = await db.get_events(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        # Generate analyses
        trends = await self.analyze_trends(days)
        insights = await self.generate_insights(events)
        
        # Compile report
        report = {
            'report_generated': datetime.now().isoformat(),
            'analysis_period': f'{days} days',
            'total_events_analyzed': len(events),
            'summary': {
                'trends_identified': len(trends),
                'insights_generated': len(insights)
            },
            'trends': [asdict(trend) for trend in trends],
            'insights': [asdict(insight) for insight in insights]
        }
        
        # Export to JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        log_info(f"✅ Analytics report exported to {filepath}")


# Global instance
_analytics: Optional[EventAnalytics] = None

def get_analytics() -> EventAnalytics:
    """Get global analytics instance"""
    global _analytics
    if _analytics is None:
        _analytics = EventAnalytics()
    return _analytics
