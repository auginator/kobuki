#!/usr/bin/env python3
"""
Interactive map selector for SLAM localization.

Lists all available maps in the maps directory and allows user to select one.
"""

import os
import sys
from pathlib import Path


class MapSelector:
    def __init__(self, maps_dir="/ros2_ws/maps"):
        self.maps_dir = Path(maps_dir)
        
    def find_maps(self):
        """Find all posegraph files in the maps directory."""
        if not self.maps_dir.exists():
            return []
        
        # Look for .posegraph files
        posegraph_files = list(self.maps_dir.glob("*.posegraph"))
        
        # Extract base names (without extension)
        map_names = []
        for pg_file in posegraph_files:
            base_name = pg_file.stem
            # Check if corresponding yaml and pgm files exist
            yaml_file = self.maps_dir / f"{base_name}.yaml"
            pgm_file = self.maps_dir / f"{base_name}.pgm"
            
            status = "Complete" if yaml_file.exists() and pgm_file.exists() else "Posegraph only"
            
            map_names.append({
                'name': base_name,
                'posegraph': str(pg_file),
                'yaml': str(yaml_file) if yaml_file.exists() else None,
                'pgm': str(pgm_file) if pgm_file.exists() else None,
                'status': status,
                'size_mb': pg_file.stat().st_size / (1024 * 1024)
            })
        
        # Sort by name
        map_names.sort(key=lambda x: x['name'])
        
        return map_names
    
    def display_maps(self, maps):
        """Display available maps in a formatted list."""
        print("\n" + "="*70)
        print("AVAILABLE MAPS FOR LOCALIZATION")
        print("="*70)
        
        if not maps:
            print("\nNo maps found in {}".format(self.maps_dir))
            print("Create a map first using the mapping launch file.")
            print("="*70 + "\n")
            return False
        
        print("\n{:<5} {:<30} {:<15} {:>10}".format(
            "ID", "Map Name", "Status", "Size (MB)"))
        print("-"*70)
        
        for idx, map_info in enumerate(maps, 1):
            print("{:<5} {:<30} {:<15} {:>10.2f}".format(
                idx, 
                map_info['name'], 
                map_info['status'],
                map_info['size_mb']
            ))
        
        print("="*70)
        return True
    
    def select_map(self):
        """Interactive map selection."""
        maps = self.find_maps()
        
        if not self.display_maps(maps):
            sys.exit(1)
        
        while True:
            try:
                print("\nEnter map ID to load (or 'q' to quit): ", end='', flush=True)
                choice = input().strip()
                
                if choice.lower() == 'q':
                    print("Exiting...")
                    sys.exit(0)
                
                map_id = int(choice)
                
                if 1 <= map_id <= len(maps):
                    selected_map = maps[map_id - 1]
                    print(f"\n✓ Selected: {selected_map['name']}")
                    print(f"  Posegraph: {selected_map['posegraph']}")
                    if selected_map['yaml']:
                        print(f"  Map files: {selected_map['yaml']}, {selected_map['pgm']}")
                    print()
                    return selected_map['posegraph']
                else:
                    print(f"Invalid ID. Please enter a number between 1 and {len(maps)}")
            
            except ValueError:
                print("Invalid input. Please enter a number or 'q'")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                sys.exit(0)


def main():
    selector = MapSelector()
    map_file = selector.select_map()
    
    # Output the selected map file path for the launch file to use
    print(f"MAP_FILE={map_file}")


if __name__ == '__main__':
    main()
