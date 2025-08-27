"""
State management for events, archives, and seen hashes.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from models import Event, Statistics
from logging_utils import log_info, log_error, log_warning
from normalize import should_archive_event


class StateManager:
    """Manages persistent state for events, archives, and hashes."""
    
    def __init__(self, state_dir: str = "state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        
        self.events_file = self.state_dir / "events.json"
        self.archive_file = self.state_dir / "archive.json"
        self.seen_hashes_file = self.state_dir / "seen_hashes.json"
        self.last_run_file = self.state_dir / "last_run.json"
        self.tips_file = self.state_dir / "tips.json"
    
    def load_events(self) -> List[Event]:
        """Load current events from state."""
        if not self.events_file.exists():
            log_info("No existing events file found, starting fresh")
            return []
        
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            events = []
            for event_data in events_data:
                try:
                    # Convert ISO strings back to datetime
                    if event_data.get('start'):
                        event_data['start'] = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
                    if event_data.get('end'):
                        event_data['end'] = datetime.fromisoformat(event_data['end'].replace('Z', '+00:00'))
                    if event_data.get('first_seen'):
                        event_data['first_seen'] = datetime.fromisoformat(event_data['first_seen'].replace('Z', '+00:00'))
                    if event_data.get('last_seen'):
                        event_data['last_seen'] = datetime.fromisoformat(event_data['last_seen'].replace('Z', '+00:00'))
                    
                    event = Event(**event_data)
                    events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse event: {e}", source="state_manager")
            
            log_info(f"Loaded {len(events)} events from state")
            return events
            
        except Exception as e:
            log_error("state_manager", f"Failed to load events: {e}", url=str(self.events_file))
            return []
    
    def save_events(self, events: List[Event]) -> bool:
        """Save events to state file."""
        try:
            events_data = [event.to_dict() for event in events]
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.events_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
            
            temp_file.rename(self.events_file)
            log_info(f"Saved {len(events)} events to state")
            return True
            
        except Exception as e:
            log_error("state_manager", f"Failed to save events: {e}", url=str(self.events_file))
            return False
    
    def load_archive(self) -> List[Event]:
        """Load archived events."""
        if not self.archive_file.exists():
            return []
        
        try:
            with open(self.archive_file, 'r', encoding='utf-8') as f:
                archive_data = json.load(f)
            
            events = []
            for event_data in archive_data:
                try:
                    # Convert ISO strings back to datetime
                    if event_data.get('start'):
                        event_data['start'] = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
                    if event_data.get('end'):
                        event_data['end'] = datetime.fromisoformat(event_data['end'].replace('Z', '+00:00'))
                    if event_data.get('first_seen'):
                        event_data['first_seen'] = datetime.fromisoformat(event_data['first_seen'].replace('Z', '+00:00'))
                    if event_data.get('last_seen'):
                        event_data['last_seen'] = datetime.fromisoformat(event_data['last_seen'].replace('Z', '+00:00'))
                    
                    event = Event(**event_data)
                    events.append(event)
                except Exception as e:
                    log_warning(f"Failed to parse archived event: {e}", source="state_manager")
            
            log_info(f"Loaded {len(events)} archived events")
            return events
            
        except Exception as e:
            log_error("state_manager", f"Failed to load archive: {e}", url=str(self.archive_file))
            return []
    
    def save_archive(self, archived_events: List[Event]) -> bool:
        """Save archived events."""
        try:
            # Sort by start date (newest first)
            sorted_events = sorted(archived_events, key=lambda e: e.start, reverse=True)
            
            # Limit archive size (keep last 1000 events)
            if len(sorted_events) > 1000:
                sorted_events = sorted_events[:1000]
                log_info(f"Archive trimmed to {len(sorted_events)} events")
            
            archive_data = [event.to_dict() for event in sorted_events]
            
            temp_file = self.archive_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, ensure_ascii=False, indent=2)
            
            temp_file.rename(self.archive_file)
            log_info(f"Saved {len(sorted_events)} events to archive")
            return True
            
        except Exception as e:
            log_error("state_manager", f"Failed to save archive: {e}", url=str(self.archive_file))
            return False
    
    def load_seen_hashes(self) -> Set[str]:
        """Load seen event hashes."""
        if not self.seen_hashes_file.exists():
            return set()
        
        try:
            with open(self.seen_hashes_file, 'r', encoding='utf-8') as f:
                hashes_data = json.load(f)
            
            if isinstance(hashes_data, list):
                return set(hashes_data)
            elif isinstance(hashes_data, dict):
                # Legacy format: {hash: timestamp}
                return set(hashes_data.keys())
            else:
                return set()
                
        except Exception as e:
            log_error("state_manager", f"Failed to load seen hashes: {e}", url=str(self.seen_hashes_file))
            return set()
    
    def save_seen_hashes(self, seen_hashes: Set[str]) -> bool:
        """Save seen event hashes."""
        try:
            hashes_list = list(seen_hashes)
            
            temp_file = self.seen_hashes_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(hashes_list, f, ensure_ascii=False, indent=2)
            
            temp_file.rename(self.seen_hashes_file)
            log_info(f"Saved {len(hashes_list)} seen hashes")
            return True
            
        except Exception as e:
            log_error("state_manager", f"Failed to save seen hashes: {e}", url=str(self.seen_hashes_file))
            return False
    
    def load_last_run(self) -> Optional[Dict]:
        """Load last run statistics."""
        if not self.last_run_file.exists():
            return None
        
        try:
            with open(self.last_run_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error("state_manager", f"Failed to load last run: {e}", url=str(self.last_run_file))
            return None
    
    def save_last_run(self, stats: Statistics) -> bool:
        """Save run statistics."""
        try:
            stats_data = stats.model_dump()
            
            # Convert datetime objects to ISO strings
            for key, value in stats_data.items():
                if isinstance(value, datetime):
                    stats_data[key] = value.isoformat()
            
            temp_file = self.last_run_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            temp_file.rename(self.last_run_file)
            log_info("Saved run statistics")
            return True
            
        except Exception as e:
            log_error("state_manager", f"Failed to save last run: {e}", url=str(self.last_run_file))
            return False
    
    def load_public_tips(self) -> List[Dict]:
        """Load public tips/submissions."""
        if not self.tips_file.exists():
            return []
        
        try:
            with open(self.tips_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error("state_manager", f"Failed to load tips: {e}", url=str(self.tips_file))
            return []
    
    def archive_old_events(self, events: List[Event], archive_hours: int = 1) -> Tuple[List[Event], List[Event]]:
        """
        Separate events into current and to-be-archived.
        Returns: (current_events, events_to_archive)
        """
        current_events = []
        events_to_archive = []
        
        for event in events:
            if should_archive_event(event, archive_hours):
                event.status = "archived"
                events_to_archive.append(event)
            else:
                current_events.append(event)
        
        if events_to_archive:
            log_info(f"Archiving {len(events_to_archive)} old events")
        
        return current_events, events_to_archive
    
    def merge_new_events(self, existing_events: List[Event], new_events: List[Event]) -> Tuple[List[Event], int, int]:
        """
        Merge new events with existing ones.
        Returns: (merged_events, new_count, updated_count)
        """
        existing_by_id = {event.id: event for event in existing_events}
        
        merged_events = existing_events.copy()
        new_count = 0
        updated_count = 0
        
        for new_event in new_events:
            if new_event.id in existing_by_id:
                # Update existing event
                existing_event = existing_by_id[new_event.id]
                existing_event.last_seen = new_event.last_seen
                
                # Update fields that might have changed
                if new_event.description and not existing_event.description:
                    existing_event.description = new_event.description
                if new_event.url and not existing_event.url:
                    existing_event.url = new_event.url
                if new_event.ticket_url and not existing_event.ticket_url:
                    existing_event.ticket_url = new_event.ticket_url
                if new_event.image_url and not existing_event.image_url:
                    existing_event.image_url = new_event.image_url
                
                updated_count += 1
            else:
                # New event
                merged_events.append(new_event)
                new_count += 1
        
        return merged_events, new_count, updated_count
    
    def full_state_update(self, new_events: List[Event], archive_hours: int = 1) -> Dict[str, int]:
        """
        Perform a complete state update with new events.
        Returns statistics about the update.
        """
        # Load existing state
        existing_events = self.load_events()
        existing_archive = self.load_archive()
        
        # Merge new events
        all_events, new_count, updated_count = self.merge_new_events(existing_events, new_events)
        
        # Archive old events
        current_events, to_archive = self.archive_old_events(all_events, archive_hours)
        
        # Update archive
        updated_archive = existing_archive + to_archive
        
        # Save state
        self.save_events(current_events)
        if to_archive:
            self.save_archive(updated_archive)
        
        return {
            "total_events": len(current_events),
            "new_events": new_count,
            "updated_events": updated_count,
            "archived_events": len(to_archive),
            "total_archived": len(updated_archive)
        }
